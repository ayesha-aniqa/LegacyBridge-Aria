"""
LegacyBridge Backend — Optimised Server v3
-------------------------------------------
Speed optimisations applied in this version:
  1. Perceptual image hashing — skip Gemini call if screen hasn't changed (cache hit)
  2. LRU response cache — serve cached Aria response instantly on repeated screens
  3. Async image processing — Pillow runs in thread pool, frees the event loop
  4. Adaptive poll interval hint — tells client to slow down when urgency is low
  5. Timing metrics — every response includes server-side latency breakdown
  6. Gemini call timeout — prevents hanging requests from blocking the server
"""

import os
import io
import json
import time
import logging
import asyncio
from functools import lru_cache
from collections import OrderedDict
from typing import Optional, List

import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from PIL import Image

from app.confusion_detector import ConfusionDetector
from app.image_utils import process_image_async, is_similar

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("aria.backend")

# ─── Environment & Vertex AI init ────────────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "legacybridge-hackathon"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-east4")
)

# Gemini 2.0 Flash — tuned for latency and consistency
model = GenerativeModel(
    "gemini-2.0-flash",
    generation_config=GenerationConfig(
        response_mime_type="application/json",
        temperature=0.4,
        top_p=0.8,
        max_output_tokens=256   # Short answers = faster response
    )
)

# ─── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="LegacyBridge Backend",
    description="Aria — AI screen assistant for elderly users (Optimised v3)",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Shared state ─────────────────────────────────────────────────────────────
confusion_detector = ConfusionDetector()

# LRU-style response cache: maps image phash → (aria_response_dict, timestamp)
# Holds up to 10 unique screens — evicts oldest when full
_response_cache: OrderedDict = OrderedDict()
_CACHE_MAX_SIZE = 10
_CACHE_TTL_SECONDS = 8   # Cached response expires after 8s even if hash matches

# Track last screen hash for skip-logic
_last_phash: str = ""
_last_urgency: str = "low"

# Guidance anti-repetition cache
_recent_guidances: List[str] = []
_MAX_RECENT = 5

# Request timing stats (reset on each /health call)
_stats = {"total_requests": 0, "cache_hits": 0, "gemini_calls": 0, "total_ms": 0}

# ─── Pydantic schemas ────────────────────────────────────────────────────────

class AriaGuidance(BaseModel):
    guidance: str
    urgency: str
    action_hint: Optional[str] = None
    confidence: float
    screen_context: Optional[str] = None

class ClickReport(BaseModel):
    x: int
    y: int

# ─── System Prompt ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are **Aria**, a warm, patient AI assistant designed to help elderly people
use their phones and computers. You watch their screen and give simple,
spoken guidance — like a kind grandchild sitting beside them.

## Your Personality
- Calm, warm, encouraging. Never frustrated.
- Use simple everyday words. No tech jargon.
- If the user seems fine, just say something reassuring ("You're doing great!").

## Response Format — ALWAYS valid JSON:
{
  "guidance": "One short, clear sentence (max 15 words). This will be spoken aloud.",
  "urgency": "low | medium | high",
  "action_hint": "Physical description of what to do next (color, shape, position on screen). Null if not needed.",
  "confidence": 0.0 to 1.0,
  "screen_context": "Brief label of what app or screen you see (e.g. 'WhatsApp chat list', 'Home screen', 'Settings')"
}

## Language Rules
- NEVER use: app, icon, click, tap, swipe, scroll, menu, settings, toggle, URL, browser
- INSTEAD use: "the green circle", "the words at the top", "touch the picture",
  "move your finger up on the screen", "the big blue square"
- Describe by COLOR, SHAPE, POSITION (top/bottom/left/right/center)

## Urgency Rules
- **low**: User seems fine, screen looks normal, no action needed
- **medium**: User might need a nudge (e.g. a dialog box appeared, or a new screen)
- **high**: User is clearly stuck (error message, wrong screen, confusion detected)

## Important
- If the screen looks like a normal desktop or home screen with nothing happening,
  set urgency to "low" and say something encouraging.
- If you see an error dialog or popup, set urgency to "high" and explain what happened simply.
- NEVER repeat the exact same guidance twice in a row.
"""

# ─── Cache helpers ────────────────────────────────────────────────────────────

def _cache_get(phash: str) -> Optional[dict]:
    """Look up a cached response by image hash. Returns None if expired."""
    if phash in _response_cache:
        entry, ts = _response_cache[phash]
        if time.time() - ts < _CACHE_TTL_SECONDS:
            # Move to end (most recently used)
            _response_cache.move_to_end(phash)
            return entry
        else:
            # Expired — remove
            del _response_cache[phash]
    return None

def _cache_set(phash: str, response_dict: dict):
    """Store a response in the cache, evicting oldest if at capacity."""
    _response_cache[phash] = (response_dict, time.time())
    _response_cache.move_to_end(phash)
    if len(_response_cache) > _CACHE_MAX_SIZE:
        _response_cache.popitem(last=False)  # Evict oldest

# ─── Gemini call ─────────────────────────────────────────────────────────────

async def _call_gemini(image_bytes: bytes, instruction: str) -> str:
    """
    Call Gemini Vision in a thread pool with a timeout.
    Raises asyncio.TimeoutError if Gemini takes > 12 seconds.
    """
    image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")
    prompt_parts = [SYSTEM_PROMPT, instruction, image_part]

    loop = asyncio.get_event_loop()

    def _sync_call():
        return model.generate_content(prompt_parts)

    # Run the blocking Gemini call in the thread pool with a 12-second timeout
    response = await asyncio.wait_for(
        loop.run_in_executor(None, _sync_call),
        timeout=12.0
    )
    return response.text

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "status": "Aria is online",
        "version": "3.0.0",
        "confusion_monitoring": confusion_detector.get_status(),
        "cache_size": len(_response_cache)
    }

@app.get("/health")
async def health():
    """Performance metrics endpoint."""
    hit_rate = (
        round(_stats["cache_hits"] / _stats["total_requests"] * 100, 1)
        if _stats["total_requests"] > 0 else 0
    )
    avg_ms = (
        round(_stats["total_ms"] / _stats["total_requests"], 1)
        if _stats["total_requests"] > 0 else 0
    )
    return {
        "status": "ok",
        "stats": {
            **_stats,
            "cache_hit_rate_pct": hit_rate,
            "avg_response_ms": avg_ms,
        },
        "cache_entries": len(_response_cache)
    }

@app.post("/report-click")
async def report_click(click: ClickReport, background_tasks: BackgroundTasks):
    """Receive click coordinates — record in background so it doesn't add latency."""
    background_tasks.add_task(confusion_detector.record_click, click.x, click.y)
    return {"status": "recorded"}

@app.get("/confusion-status")
async def get_confusion_status():
    return {"confusion": confusion_detector.evaluate()}

@app.post("/reset-confusion")
async def reset_confusion():
    confusion_detector.reset()
    return {"status": "reset", "confusion": confusion_detector.get_status()}

@app.post("/process-screen")
async def process_screen(file: UploadFile = File(...)):
    """
    Optimised screen processing pipeline:
      1. Async image processing (thread pool)
      2. Perceptual hash → cache lookup (skip Gemini if screen unchanged)
      3. Confusion-aware prompt injection
      4. Async Gemini call with timeout
      5. Response caching + anti-repetition
      6. Adaptive poll interval in response
    """
    global _last_phash, _last_urgency, _recent_guidances
    t_start = time.perf_counter()
    _stats["total_requests"] += 1

    try:
        # ── 1. Async image processing ─────────────────────────────────────
        raw_bytes = await file.read()
        _, image_bytes, phash = await process_image_async(raw_bytes)
        t_image = time.perf_counter()

        # ── 2. Cache lookup ───────────────────────────────────────────────
        # Only use cache when confusion is not active (confused user needs fresh response)
        confusion_state = confusion_detector.evaluate()
        cached = _cache_get(phash) if not confusion_state["is_confused"] else None

        if cached and is_similar(phash, _last_phash):
            # Screen hasn't changed and confusion is not active — return cached response
            _stats["cache_hits"] += 1
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)
            _stats["total_ms"] += elapsed_ms
            logger.info("⚡ Cache hit | hash=%s | %.1fms", phash[:8], elapsed_ms)

            # Suggest the client slow down polling since nothing is changing
            return {
                "status": "success",
                "data": cached,
                "confusion": confusion_detector.get_status(),
                "cache_hit": True,
                "response_ms": elapsed_ms,
                "next_poll_interval": 4  # seconds — hint to client to poll less often
            }

        # ── 3. Build instruction with confusion + anti-repetition ─────────
        instruction = "Analyze this screenshot and guide the elderly user. Respond in JSON."

        if confusion_state["is_confused"]:
            instruction += "\n" + confusion_state["prompt_modifier"]
            logger.warning(
                "⚠️  Confusion | score=%.2f | reason=%s | streak=%d",
                confusion_state["score"], confusion_state["reason"],
                confusion_state["streak"]
            )

        if _recent_guidances:
            recent_text = " | ".join(_recent_guidances[-3:])
            instruction += (
                f"\n\nDo NOT repeat these recent guidances: [{recent_text}]. "
                "Say something new or rephrase."
            )

        # ── 4. Call Gemini (async + timeout) ─────────────────────────────
        t_pre_gemini = time.perf_counter()
        try:
            response_text = await _call_gemini(image_bytes, instruction)
        except asyncio.TimeoutError:
            logger.error("⏱️  Gemini timeout after 12s")
            return {"status": "error", "message": "Gemini request timed out — try again"}

        _stats["gemini_calls"] += 1
        t_post_gemini = time.perf_counter()
        gemini_ms = round((t_post_gemini - t_pre_gemini) * 1000, 1)

        # ── 5. Parse response ─────────────────────────────────────────────
        try:
            data = json.loads(response_text)
            aria = AriaGuidance(**data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Parse error: %s | Raw: %s", e, response_text[:200])
            return {"status": "error", "message": "Failed to parse Aria's response", "raw": response_text}

        # Record in confusion detector (background — don't add to latency)
        confusion_detector.record_response(aria.guidance, aria.urgency)

        # Update caches
        _last_phash = phash
        _last_urgency = aria.urgency
        aria_dict = aria.dict()
        _cache_set(phash, aria_dict)

        _recent_guidances.append(aria.guidance)
        if len(_recent_guidances) > _MAX_RECENT:
            _recent_guidances = _recent_guidances[-_MAX_RECENT:]

        # ── 6. Adaptive poll interval hint ────────────────────────────────
        # Tell the client how long to wait before the next screenshot
        if aria.urgency == "high" or confusion_state["is_confused"]:
            next_poll = 1   # Check rapidly when user needs help
        elif aria.urgency == "medium":
            next_poll = 2
        else:
            next_poll = 4   # Slow down when everything looks fine

        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)
        _stats["total_ms"] += elapsed_ms

        logger.info(
            "🗣️  Aria: \"%s\" | urgency=%s | conf=%.2f | gemini=%.0fms | total=%.0fms",
            aria.guidance, aria.urgency, aria.confidence, gemini_ms, elapsed_ms
        )

        return {
            "status": "success",
            "data": aria_dict,
            "confusion": confusion_detector.get_status(),
            "cache_hit": False,
            "response_ms": elapsed_ms,
            "gemini_ms": gemini_ms,
            "next_poll_interval": next_poll
        }

    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", workers=1)
