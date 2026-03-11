import os
import io
import json
import base64
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from fastapi import FastAPI, UploadFile, File
from PIL import Image
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

# Load environment variables from root .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Initialize Vertex AI with project and location from env or defaults
vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "legacybridge-hackathon"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-east4")
)

# Create Gemini 2.0 Flash model via Vertex AI — low latency, JSON output
model = GenerativeModel(
    "gemini-2.0-flash",
    generation_config=GenerationConfig(
        response_mime_type="application/json"
    )
)

app = FastAPI(title="LegacyBridge Backend")

# Response Schema for structured parsing
class AriaGuidance(BaseModel):
    guidance: str
    urgency: str  # "low", "medium", "high"
    action_hint: Optional[str] = None  # e.g., "tap green circle"
    confidence: float

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

@app.post("/process-screen")
async def process_screen(file: UploadFile = File(...)):
    """Receives a screenshot and processes it with Gemini Vision (Vertex AI) for JSON output."""
    try:
        # Read the uploaded image bytes
        contents = await file.read()

        # Validate image by opening with Pillow
        image = Image.open(io.BytesIO(contents))

        # Convert image to base64 for Vertex AI Part
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        image_bytes = buffered.getvalue()

        # Build Vertex AI image Part
        image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")

        # Prepare prompt parts for Gemini
        prompt_parts = [
            SYSTEM_PROMPT,
            "Identify the current screen and tell the user what to do. Provide JSON.",
            image_part
        ]

        # Generate structured response via Vertex AI
        response = model.generate_content(prompt_parts)

        # Parse the JSON response
        try:
            data = json.loads(response.text)
            aria_response = AriaGuidance(**data)
            print(f"Aria Guidance: {aria_response.guidance} (Confidence: {aria_response.confidence})")

            return {
                "status": "success",
                "data": aria_response.dict()
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
