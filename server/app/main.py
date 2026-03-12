"""
LegacyBridge Backend — Optimised Server v4
-------------------------------------------
Speed optimisations applied in this version:
  1. Perceptual image hashing — skip Gemini call if screen hasn't changed (cache hit)
  2. LRU response cache — serve cached Aria response instantly on repeated screens
  3. Async image processing — Pillow runs in thread pool, frees the event loop
  4. Adaptive poll interval hint — tells client to slow down when urgency is low
  5. Timing metrics — every response includes server-side latency breakdown
  6. Gemini call timeout — prevents hanging requests from blocking the server
  7. Warm-up call on startup — eliminates cold start on first real user request
  8. Auto-retry with simplified prompt + response sanitizer
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
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from PIL import Image

from app.confusion_detector import ConfusionDetector
from app.image_utils import process_image_async, is_similar
from app.ai_optimizer import WarmUpManager, parse_with_retry, sanitize_response, RETRY_PROMPT

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
    description="Aria — AI screen assistant for elderly users (Optimised v4)",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Warm-up manager ─────────────────────────────────────────────────────────
warmup_manager = WarmUpManager()

@app.on_event("startup")
async def on_startup():
    """Fire a warm-up Gemini call so the first real user request is fast."""
    await warmup_manager.warmup(model, SYSTEM_PROMPT)

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
    poll_interval_hint: int
    confusion_assessment: str
    visual_target: Optional[str] = None

class ClickReport(BaseModel):
    x: int
    y: int

# ─── System Prompt ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are Aria, a warm and patient AI assistant helping elderly users navigate their devices.

PERSONA RULES:
- Speak like a kind, calm grandchild — never condescending
- Use short sentences. One instruction at a time.
- Never use: click, URL, browser, app, API, icon, interface, menu, navigate, cursor
- Instead use: "the green circle", "the words at the top", "the big blue button on the left"
- Always be encouraging. Never make the user feel stupid.
- If unsure what the user wants, ask ONE simple question.

RESPONSE FORMAT (return strict JSON):
{
  "guidance": "Your spoken guidance here. One or two sentences max.",
  "urgency": "LOW | MEDIUM | HIGH",
  "poll_interval_hint": 2,
  "confusion_assessment": "Brief note on whether user seems stuck",
  "visual_target": "Optional: describe exact screen location of key element"
}

SCREEN ANALYSIS RULES:
- Describe what you see plainly before deciding on guidance
- If an error dialog is visible and unaddressed, urgency is HIGH
- If the screen looks normal with no clear user goal, urgency is LOW
- If the user appears mid-task but stuck, urgency is MEDIUM
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
async def process_screen(
    file: UploadFile = File(...),
    movement: Optional[str] = Form(None)
):
    """
    Optimised screen processing pipeline:
      1. Async image processing (thread pool)
      2. Perceptual hash → record in confusion detector + cache lookup
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

        # ── 2. Confusion state & Cache lookup ─────────────────────────────
        # Record phash and movement data
        confusion_detector.record_phash(phash)
        if movement:
            try:
                move_points = json.loads(movement)
                confusion_detector.record_movement(move_points)
            except Exception as e:
                logger.error("Failed to parse movement data: %s", e)

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

        # ── 5. Parse response (with auto-retry + sanitize) ───────────────
        async def _retry_call():
            """Simplified retry prompt if first parse fails."""
            return await _call_gemini(image_bytes, RETRY_PROMPT)

        aria_dict = await parse_with_retry(response_text, _retry_call)
        if aria_dict is None:
            return {"status": "error", "message": "Failed to parse Aria's response"}

        # Record in confusion detector
        confusion_detector.record_response(aria_dict["guidance"], aria_dict["urgency"])

        # Update caches
        _last_phash = phash
        _last_urgency = aria_dict["urgency"]
        _cache_set(phash, aria_dict)

        _recent_guidances.append(aria_dict["guidance"])
        if len(_recent_guidances) > _MAX_RECENT:
            _recent_guidances = _recent_guidances[-_MAX_RECENT:]

        # ── 6. Adaptive poll interval hint ────────────────────────────────
        # Use Gemini's hint if provided, otherwise fallback to urgency-based
        next_poll = aria_dict.get("poll_interval_hint", 2)
        
        # Override if confusion is active to ensure responsiveness
        if confusion_state["is_confused"] or aria_dict["urgency"].lower() == "high":
            next_poll = 1

        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)
        _stats["total_ms"] += elapsed_ms

        logger.info(
            "🗣️  Aria: \"%s\" | urgency=%s | conf=%.2f | gemini=%.0fms | total=%.0fms",
            aria_dict["guidance"], aria_dict["urgency"],
            aria_dict.get("confidence", 0), gemini_ms, elapsed_ms
        )

        return {
            "status": "success",
            "data": aria_dict,
            "confusion": confusion_detector.get_status(),
            "cache_hit": False,
            "response_ms": elapsed_ms,
            "gemini_ms": gemini_ms,
            "next_poll_interval": next_poll,
            "warmup": warmup_manager.get_status()
        }

    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", workers=1)
