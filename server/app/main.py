"""
LegacyBridge Backend — Optimised Server v4
"""

import os
import io
import json
import time
import logging
import asyncio
from collections import OrderedDict
from typing import Optional, List

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from PIL import Image

from app.confusion_detector import ConfusionDetector
from app.image_utils import process_image_async, is_similar
from app.ai_optimizer import WarmUpManager, parse_with_retry, RETRY_PROMPT
from app.adk_wrapper import LegacyBridgeAgent

# ─── Logging ─────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("aria.backend")

# ─── Environment ─────────────────────────────────────────────────

load_dotenv()

vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "legacybridge-hackathon"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
)

# ─── Gemini Model ───────────────────────────────────────────────

model = GenerativeModel(
    "gemini-2.0-flash",
    generation_config=GenerationConfig(
        response_mime_type="application/json",
        temperature=0.4,
        top_p=0.8,
        max_output_tokens=256
    )
)

# ─── System Prompt ──────────────────────────────────────────────

SYSTEM_PROMPT = """
You are Aria, a warm and patient AI assistant helping elderly users navigate their devices.

Speak calmly and give simple instructions.

RESPONSE FORMAT (strict JSON):
{
  "guidance": "Short instruction for the user.",
  "urgency": "LOW | MEDIUM | HIGH",
  "poll_interval_hint": 2,
  "confusion_assessment": "Brief note",
  "visual_target": "[y,x] optional",
  "screen_description": "One sentence"
}
"""

# ─── FastAPI App ───────────────────────────────────────────────

app = FastAPI(
    title="LegacyBridge Backend",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ─── Managers ──────────────────────────────────────────────────

warmup_manager = WarmUpManager()
confusion_detector = ConfusionDetector()
aria_agent = LegacyBridgeAgent(model, SYSTEM_PROMPT)

# ─── Startup Warmup ─────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    await warmup_manager.warmup(model, SYSTEM_PROMPT)

# ─── Cache ─────────────────────────────────────────────────────

_response_cache: OrderedDict = OrderedDict()
_CACHE_MAX_SIZE = 10
_CACHE_TTL_SECONDS = 8

_last_phash = ""
_last_urgency = "low"
_last_image_bytes: Optional[bytes] = None

_recent_guidances: List[str] = []
_recent_descriptions: List[str] = []

_MAX_RECENT = 5
_MAX_HISTORY = 3

_stats = {
    "total_requests": 0,
    "cache_hits": 0,
    "gemini_calls": 0,
    "total_ms": 0
}

# ─── Schemas ───────────────────────────────────────────────────

class AriaGuidance(BaseModel):
    guidance: str
    urgency: str
    poll_interval_hint: int
    confusion_assessment: str
    visual_target: Optional[str] = None
    screen_description: Optional[str] = None


class ClickReport(BaseModel):
    x: int
    y: int


class VoiceInput(BaseModel):
    text: str


# ─── Cache Helpers ─────────────────────────────────────────────

def _cache_get(phash: str):

    if phash in _response_cache:

        entry, ts = _response_cache[phash]

        if time.time() - ts < _CACHE_TTL_SECONDS:

            _response_cache.move_to_end(phash)
            return entry

        else:
            del _response_cache[phash]

    return None


def _cache_set(phash: str, data: dict):

    _response_cache[phash] = (data, time.time())

    _response_cache.move_to_end(phash)

    if len(_response_cache) > _CACHE_MAX_SIZE:
        _response_cache.popitem(last=False)


# ─── Gemini Call ───────────────────────────────────────────────

async def _call_gemini(image_bytes: bytes, instruction: str):

    try:

        response = await asyncio.wait_for(
            aria_agent.analyze_and_act(image_bytes, instruction),
            timeout=12
        )

        return response

    except asyncio.TimeoutError:

        logger.error("Gemini timeout")

        raise


# ─── Root ──────────────────────────────────────────────────────

@app.get("/")
async def root():

    return {
        "status": "Aria is online",
        "cache_entries": len(_response_cache)
    }


# ─── Health ────────────────────────────────────────────────────

@app.get("/health")
async def health():

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
            "avg_response_ms": avg_ms
        },
        "cache_entries": len(_response_cache)
    }


# ─── Click Tracking ────────────────────────────────────────────

@app.post("/report-click")
async def report_click(click: ClickReport, background_tasks: BackgroundTasks):

    background_tasks.add_task(
        confusion_detector.record_click,
        click.x,
        click.y
    )

    return {"status": "recorded"}


# ─── Voice Input ───────────────────────────────────────────────

@app.post("/voice-input")
async def voice_input(input_data: VoiceInput):

    global _last_image_bytes

    if _last_image_bytes is None:

        return {
            "status": "success",
            "data": {
                "guidance": "I cannot see your screen yet.",
                "urgency": "LOW",
                "poll_interval_hint": 2,
                "confusion_assessment": "waiting"
            }
        }

    instruction = f'User said: "{input_data.text}"'

    async def retry():
        return await _call_gemini(_last_image_bytes, RETRY_PROMPT)

    try:

        response = await _call_gemini(_last_image_bytes, instruction)

        aria_dict = await parse_with_retry(response, retry)

        return {
            "status": "success",
            "data": aria_dict
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }


# ─── Screen Processing ─────────────────────────────────────────

@app.post("/process-screen")
async def process_screen(
    file: UploadFile = File(...),
    movement: Optional[str] = Form(None)
):

    global _last_phash
    global _last_image_bytes

    t_start = time.perf_counter()
    _stats["total_requests"] += 1

    try:

        raw_bytes = await file.read()

        _, image_bytes, phash = await process_image_async(raw_bytes)

        _last_image_bytes = image_bytes

        confusion_detector.record_phash(phash)

        confusion_state = confusion_detector.evaluate()

        cached = _cache_get(phash)

        if cached and is_similar(phash, _last_phash):

            _stats["cache_hits"] += 1

            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)

            _stats["total_ms"] += elapsed_ms

            return {
                "status": "success",
                "data": cached,
                "cache_hit": True,
                "response_ms": elapsed_ms
            }

        instruction = "Analyze screenshot and guide user."

        if confusion_state["is_confused"]:
            instruction += "\nUser seems confused."

        response_text = await _call_gemini(image_bytes, instruction)

        async def retry():
            return await _call_gemini(image_bytes, RETRY_PROMPT)

        aria_dict = await parse_with_retry(response_text, retry)

        if aria_dict is None:

            return {
                "status": "error",
                "message": "Parsing failed"
            }

        confusion_detector.record_response(
            aria_dict["guidance"],
            aria_dict["urgency"]
        )

        _cache_set(phash, aria_dict)

        _last_phash = phash

        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)

        _stats["total_ms"] += elapsed_ms

        return {
            "status": "success",
            "data": aria_dict,
            "cache_hit": False,
            "response_ms": elapsed_ms
        }

    except Exception as e:

        logger.error("Processing error: %s", e)

        return {
            "status": "error",
            "message": str(e)
        }


# ─── Run Server ─────────────────────────────────────────────────

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )