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

# Create model
model = genai.GenerativeModel('gemini-2.0-flash')

app = FastAPI(title="LegacyBridge Backend")

SYSTEM_PROMPT = """
You are Aria, a warm, patient, and kind AI assistant for the elderly. 
Your goal is to look at the provided screenshot and guide the user in natural language.
- Speak slowly and clearly (in text).
- Be extremely simple.
- Do not use tech jargon like 'click' (use 'tap' or 'press').
- If the user is on a common app (WhatsApp, YouTube, etc.), guide them to what they likely need.
- Keep responses short: 1-2 sentences max.
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
        prompt_parts = [
            SYSTEM_PROMPT,
            image
        ]
        
        # Generate response
        response = model.generate_content(prompt_parts)
        
        return {
            "status": "success",
            "guidance": response.text,
            "raw_response": response.to_dict() if hasattr(response, 'to_dict') else str(response)
        }
        
    except Exception as e:
        print(f"Error processing screen: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
