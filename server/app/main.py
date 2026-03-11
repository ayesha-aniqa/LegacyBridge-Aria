import os
import io
import json
import google.generativeai as genai
from fastapi import FastAPI, UploadFile, File
from PIL import Image
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

# Import the confusion detection module
from app.confusion_detector import ConfusionDetector

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Create model - using flash for low latency
# Gemini 2.0 Flash supports controlled JSON output
model = genai.GenerativeModel(
    'gemini-2.0-flash',
    generation_config={"response_mime_type": "application/json"}
)

app = FastAPI(title="LegacyBridge Backend")

# Initialize the confusion detector (shared state across requests)
confusion_detector = ConfusionDetector()

# Response Schema for structured parsing
class AriaGuidance(BaseModel):
    guidance: str
    urgency: str  # "low", "medium", "high"
    action_hint: Optional[str] = None  # e.g., "tap green circle"
    confidence: float

# Schema for click reports from the client
class ClickReport(BaseModel):
    x: int
    y: int

SYSTEM_PROMPT = """
You are Aria, a warm, patient AI assistant for the elderly.
Analyze the provided screenshot and respond ONLY in JSON format.

JSON Structure:
{
  "guidance": "A single, simple sentence for the user (max 12 words).",
  "urgency": "low/medium/high (high if they look stuck or clicked wrong many times)",
  "action_hint": "Brief physical description of the next step (e.g. 'green circle at bottom')",
  "confidence": 0.0 to 1.0
}

Aria's Voice Guidelines:
- Reassuring, kind tone.
- No technical jargon (no 'app', 'icon', 'click').
- Use physical descriptions (colors, shapes, positions).
- If on a clear app like WhatsApp, focus on the 'phone' or 'chat' visual.
"""

@app.get("/")
async def root():
    return {"status": "Aria is online"}

@app.post("/report-click")
async def report_click(click: ClickReport):
    """Receives click coordinates from the client for confusion tracking."""
    confusion_detector.record_click(click.x, click.y)
    status = confusion_detector.evaluate()
    return {
        "status": "recorded",
        "confusion": status
    }

@app.get("/confusion-status")
async def confusion_status():
    """Returns the current confusion detection state."""
    status = confusion_detector.evaluate()
    return {"confusion": status}

@app.post("/process-screen")
async def process_screen(file: UploadFile = File(...)):
    """Receives a screenshot and processes it with Gemini Vision for JSON output."""
    try:
        # Read and basic processing (ensure it's a valid image)
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # Evaluate confusion state BEFORE generating response
        confusion_state = confusion_detector.evaluate()

        # Build the prompt — inject confusion context if detected
        base_instruction = "Identify the current screen and tell the user what to do. Provide JSON."
        if confusion_state["is_confused"]:
            # Append the confusion-aware prompt modifier
            instruction = base_instruction + confusion_state["prompt_modifier"]
            print(f"⚠️  Confusion detected! Score: {confusion_state['score']} | Reason: {confusion_state['reason']}")
        else:
            instruction = base_instruction

        # Prepare content for Gemini
        prompt_parts = [
            SYSTEM_PROMPT,
            instruction,
            image
        ]

        # Generate structured response
        response = model.generate_content(prompt_parts)

        # Parse the JSON response
        try:
            data = json.loads(response.text)
            aria_response = AriaGuidance(**data)
            print(f"Aria Guidance: {aria_response.guidance} (Confidence: {aria_response.confidence})")

            # Record the response in the confusion detector for pattern tracking
            confusion_detector.record_response(aria_response.guidance, aria_response.urgency)

            return {
                "status": "success",
                "data": aria_response.dict(),
                "confusion": confusion_detector.get_status()
            }
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Parsing error: {e} | Raw: {response.text}")
            return {
                "status": "error",
                "message": "Failed to parse Aria's response",
                "raw": response.text
            }

    except Exception as e:
        print(f"Error processing screen: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
