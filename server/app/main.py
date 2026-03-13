import os
import io
import json
import google.generativeai as genai
from fastapi import FastAPI, UploadFile, File
from PIL import Image
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

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
    """Receives a screenshot and processes it with Gemini Vision for JSON output."""
    try:
        # Read and basic processing (ensure it's a valid image)
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # Prepare content for Gemini
        prompt_parts = [
            SYSTEM_PROMPT,
            "Identify the current screen and tell the user what to do. Provide JSON.",
            image
        ]

        # Generate structured response
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