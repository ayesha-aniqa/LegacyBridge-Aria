import os
import io
import google.generativeai as genai
from fastapi import FastAPI, UploadFile, File
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Create model - using flash for low latency
model = genai.GenerativeModel('gemini-2.0-flash')

app = FastAPI(title="LegacyBridge Backend")

# SYSTEM_PROMPT refined for better elderly UX
SYSTEM_PROMPT = """
You are Aria, a warm, patient, and kind AI assistant for the elderly.
You are looking at the user's screen through their eyes.

Your goal: Provide extremely simple, ONE-SENTENCE natural language guidance.
Guidelines:
- Use a calm, reassuring tone (like a kind grandchild).
- Avoid all technical terms: don't say 'click', 'icon', 'button', or 'app'.
- Use physical descriptions: say 'the green circle', 'the picture of a phone', 'the top of the screen'.
- Focus on the most likely next step for a confused user.
- If the screen is empty or on a desktop, suggest opening something common like 'the green phone picture to call someone'.
- MAX 15 WORDS per response.
"""

@app.get("/")
async def root():
    return {"status": "Aria is online"}

@app.post("/process-screen")
async def process_screen(file: UploadFile = File(...)):
    """Receives a screenshot and processes it with Gemini Vision."""
    try:
        # Read the file into memory
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        # Prepare content for Gemini
        # Flash 2.0 supports direct image objects in the list
        prompt_parts = [
            SYSTEM_PROMPT,
            "Look at this screen. What should the user do next? Speak as Aria.",
            image
        ]
        
        # Generate response
        response = model.generate_content(prompt_parts)
        
        guidance_text = response.text.strip() if response.text else "I'm watching and ready to help."
        
        print(f"Aria says: {guidance_text}")
        
        return {
            "status": "success",
            "guidance": guidance_text
        }
        
    except Exception as e:
        print(f"Error processing screen: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
