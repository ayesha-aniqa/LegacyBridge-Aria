import os
import io
import json
import logging
import base64
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional, List

# Import the refined confusion detection module
from app.confusion_detector import ConfusionDetector

# ─── Logging setup ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("aria.backend")

# ─── Environment ─────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# ─── Vertex AI initialization ────────────────────────────────────────────────
vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "legacybridge-hackathon"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-east4")
)

# Gemini 2.0 Flash — low latency, controlled JSON output
model = GenerativeModel(
    "gemini-2.0-flash",
    generation_config=GenerationConfig(
        response_mime_type="application/json",
        temperature=0.4,       # Lower = more consistent, less hallucination
        top_p=0.8,
        max_output_tokens=256  # Keep responses short for elderly
    )
)

# ─── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="LegacyBridge Backend",
    description="Aria — AI screen assistant for elderly users",
    version="2.0.0"
)

# Allow frontend to connect from any origin during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Shared confusion detector instance ──────────────────────────────────────
confusion_detector = ConfusionDetector()

# Keep a small history of the last few guidances to avoid Gemini repeating itself
recent_guidance_cache: List[str] = []
MAX_CACHE = 5

# ─── Pydantic schemas ────────────────────────────────────────────────────────

class AriaGuidance(BaseModel):
    guidance: str
    urgency: str            # "low", "medium", "high"
    action_hint: Optional[str] = None
    confidence: float
    screen_context: Optional[str] = None   # what app/screen is detected

class ClickReport(BaseModel):
    x: int
    y: int

# ─── Refined System Prompt ───────────────────────────────────────────────────

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

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "Aria is online",
        "version": "2.0.0",
        "confusion_monitoring": confusion_detector.get_status()
    }

@app.post("/report-click")
async def report_click(click: ClickReport):
    """Receive click coordinates from the client for confusion tracking."""
    confusion_detector.record_click(click.x, click.y)
    status = confusion_detector.evaluate()
    return {"status": "recorded", "confusion": status}

@app.get("/confusion-status")
async def get_confusion_status():
    """Return current confusion detection state."""
    return {"confusion": confusion_detector.evaluate()}

@app.post("/reset-confusion")
async def reset_confusion():
    """Manually reset confusion state."""
    confusion_detector.reset()
    return {"status": "reset", "confusion": confusion_detector.get_status()}

@app.post("/process-screen")
async def process_screen(file: UploadFile = File(...)):
    """
    Core endpoint: receives a screenshot, processes it through Gemini Vision,
    and returns structured guidance with confusion-aware prompt augmentation.
    """
    global recent_guidance_cache

    try:
        # ── 1. Read & validate image ─────────────────────────────────────
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # Convert to optimised JPEG for Vertex AI
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=80)
        image_bytes = buffered.getvalue()
        image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")

        logger.info("📸 Screenshot received (%d bytes)", len(image_bytes))

        # ── 2. Evaluate confusion BEFORE asking Gemini ───────────────────
        confusion_state = confusion_detector.evaluate()

        # ── 3. Build the instruction prompt ──────────────────────────────
        instruction = "Analyze this screenshot and guide the elderly user. Respond in JSON."

        # Inject confusion context if detected
        if confusion_state["is_confused"]:
            instruction += "\n" + confusion_state["prompt_modifier"]
            logger.warning(
                "⚠️  Confusion active | score=%.2f | reason=%s | streak=%d",
                confusion_state["score"],
                confusion_state["reason"],
                confusion_state["streak"]
            )

        # Inject anti-repetition hint if we have cached guidance
        if recent_guidance_cache:
            recent_text = " | ".join(recent_guidance_cache[-3:])
            instruction += (
                f"\n\nDo NOT repeat these recent guidances: [{recent_text}]. "
                "Say something new or rephrase if the situation is the same."
            )

        # ── 4. Call Gemini ───────────────────────────────────────────────
        prompt_parts = [SYSTEM_PROMPT, instruction, image_part]
        response = model.generate_content(prompt_parts)

        # ── 5. Parse response ────────────────────────────────────────────
        try:
            data = json.loads(response.text)
            aria = AriaGuidance(**data)

            # Record in confusion detector
            confusion_detector.record_response(aria.guidance, aria.urgency)

            # Update anti-repetition cache
            recent_guidance_cache.append(aria.guidance)
            if len(recent_guidance_cache) > MAX_CACHE:
                recent_guidance_cache = recent_guidance_cache[-MAX_CACHE:]

            logger.info(
                "🗣️  Aria: \"%s\" | urgency=%s | conf=%.2f | screen=%s",
                aria.guidance, aria.urgency, aria.confidence,
                aria.screen_context or "unknown"
            )

            return {
                "status": "success",
                "data": aria.dict(),
                "confusion": confusion_detector.get_status()
            }

        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Parse error: %s | Raw: %s", e, response.text[:200])
            return {
                "status": "error",
                "message": "Failed to parse Aria's response",
                "raw": response.text
            }

    except Exception as e:
        logger.error("Error processing screen: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
