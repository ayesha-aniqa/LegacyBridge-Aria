"""
AI Processing Optimizer for LegacyBridge
------------------------------------------
Provides optimizations that wrap around the core Gemini API calls:
  1. Warm-up call on startup — eliminates cold start latency on first real user request
  2. Response validator — ensures Gemini output meets schema before returning
  3. Auto-retry with simplified prompt — if Gemini returns invalid JSON, retry once
     with a stricter, shorter prompt to recover gracefully
  4. Response post-processing — trims guidance to max word limit, validates urgency
"""

import json
import time
import asyncio
import logging
from typing import Optional, Tuple

logger = logging.getLogger("aria.ai_optimizer")

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_GUIDANCE_WORDS = 15
VALID_URGENCIES = {"low", "medium", "high"}
DEFAULT_FALLBACK_RESPONSE = {
    "guidance": "I'm here to help. Take your time.",
    "urgency": "low",
    "action_hint": None,
    "confidence": 0.5,
    "screen_context": "unknown"
}

# ─── Simplified retry prompt ─────────────────────────────────────────────────
RETRY_PROMPT = """
You are a helpful assistant. Respond ONLY with this exact JSON and nothing else:
{
  "guidance": "One short sentence (under 15 words) telling the user what to do.",
  "urgency": "low",
  "action_hint": null,
  "confidence": 0.8,
  "screen_context": "unknown"
}
"""


def validate_response(data: dict) -> Tuple[bool, list]:
    """
    Validate a Gemini response dict against the AriaGuidance schema.
    Returns (is_valid, list_of_errors).
    """
    errors = []

    # Required fields
    if "guidance" not in data or not isinstance(data["guidance"], str):
        errors.append("Missing or invalid 'guidance' field")
    elif not data["guidance"].strip():
        errors.append("'guidance' is empty")

    if "urgency" not in data:
        errors.append("Missing 'urgency' field")
    elif data["urgency"] not in VALID_URGENCIES:
        errors.append(f"Invalid urgency '{data['urgency']}' — must be low/medium/high")

    if "confidence" not in data:
        errors.append("Missing 'confidence' field")
    elif not isinstance(data["confidence"], (float, int)):
        errors.append("'confidence' must be a number")
    elif not (0.0 <= float(data["confidence"]) <= 1.0):
        errors.append(f"'confidence' {data['confidence']} out of range [0.0, 1.0]")

    # Optional field checks
    if "action_hint" in data and data["action_hint"] is not None:
        if not isinstance(data["action_hint"], str):
            errors.append("'action_hint' must be a string or null")

    return len(errors) == 0, errors


def sanitize_response(data: dict) -> dict:
    """
    Clean up a Gemini response — fix minor issues without rejecting it:
    - Trim guidance to max word count
    - Normalize urgency to lowercase
    - Clamp confidence to [0.0, 1.0]
    - Ensure screen_context is present
    """
    # Trim guidance to word limit
    if "guidance" in data and isinstance(data["guidance"], str):
        words = data["guidance"].split()
        if len(words) > MAX_GUIDANCE_WORDS:
            data["guidance"] = " ".join(words[:MAX_GUIDANCE_WORDS])
            logger.debug("Trimmed guidance from %d to %d words", len(words), MAX_GUIDANCE_WORDS)

    # Normalize urgency
    if "urgency" in data:
        data["urgency"] = str(data["urgency"]).lower()
        if data["urgency"] not in VALID_URGENCIES:
            logger.warning("Invalid urgency '%s' → defaulting to 'low'", data["urgency"])
            data["urgency"] = "low"

    # Clamp confidence
    if "confidence" in data:
        try:
            data["confidence"] = round(max(0.0, min(1.0, float(data["confidence"]))), 2)
        except (TypeError, ValueError):
            data["confidence"] = 0.5

    # Ensure all expected fields are present
    data.setdefault("action_hint", None)
    data.setdefault("screen_context", "unknown")

    return data


async def parse_with_retry(
    response_text: str,
    retry_fn,   # async callable () -> str — used if first parse fails
) -> Optional[dict]:
    """
    Parse Gemini's response text as JSON with one automatic retry.
    If the first parse fails, calls retry_fn() to get a fresh response
    with the simplified RETRY_PROMPT, then tries to parse that.
    Falls back to DEFAULT_FALLBACK_RESPONSE if both fail.
    """
    # ── First attempt ──────────────────────────────────────────────────────
    try:
        data = json.loads(response_text)
        is_valid, errors = validate_response(data)
        if is_valid:
            return sanitize_response(data)
        else:
            logger.warning("Gemini response invalid: %s | Raw: %s", errors, response_text[:200])
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("JSON parse error: %s | Raw: %s", e, response_text[:200])

    # ── Retry with simplified prompt ───────────────────────────────────────
    logger.info("Retrying with simplified prompt...")
    try:
        retry_text = await retry_fn()
        data = json.loads(retry_text)
        is_valid, errors = validate_response(data)
        if is_valid:
            logger.info("Retry succeeded ✓")
            return sanitize_response(data)
        else:
            logger.error("Retry also failed validation: %s", errors)
    except Exception as e:
        logger.error("Retry failed with exception: %s", e)

    # ── Final fallback ─────────────────────────────────────────────────────
    logger.warning("Using fallback response")
    return DEFAULT_FALLBACK_RESPONSE.copy()


class WarmUpManager:
    """
    Sends a warm-up request to Gemini on server startup.
    This prevents the first real user request from experiencing
    cold-start latency from Vertex AI's model loading.
    """

    def __init__(self):
        self.is_warmed_up = False
        self.warmup_time_ms: Optional[float] = None

    async def warmup(self, model, system_prompt: str):
        """
        Send a lightweight dummy request to warm up the Gemini model.
        Called from FastAPI's startup event.
        """
        from vertexai.generative_models import Part
        from PIL import Image
        import io

        logger.info("🔥 Starting Gemini warm-up call...")
        t0 = time.perf_counter()

        try:
            # Create a tiny 64x64 JPEG as a dummy image
            dummy = Image.new("RGB", (64, 64), (128, 128, 128))
            buf = io.BytesIO()
            dummy.save(buf, format="JPEG")
            buf.seek(0)
            image_part = Part.from_data(data=buf.read(), mime_type="image/jpeg")

            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: model.generate_content([
                        system_prompt,
                        "This is a warmup call. Respond with a minimal valid JSON.",
                        image_part
                    ])
                ),
                timeout=15.0
            )

            elapsed = (time.perf_counter() - t0) * 1000
            self.is_warmed_up = True
            self.warmup_time_ms = round(elapsed, 1)
            logger.info("✅ Gemini warm-up complete in %.0fms", elapsed)

        except Exception as e:
            logger.warning("⚠️  Warm-up failed (non-critical): %s", e)
            self.is_warmed_up = False

    def get_status(self) -> dict:
        return {
            "warmed_up": self.is_warmed_up,
            "warmup_ms": self.warmup_time_ms
        }
