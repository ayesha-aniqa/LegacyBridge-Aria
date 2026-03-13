import requests
from PIL import ImageGrab
import io

# Backend URL
BACKEND_URL = "http://127.0.0.1:8000/process-screen"

def get_backend_guidance():
    """
    Captures the current screen, sends it to the backend,
    and returns Aria's guidance text.
    """
    try:
        # 1️⃣ Capture screenshot (full screen)
        screenshot = ImageGrab.grab()
        img_bytes = io.BytesIO()
        screenshot.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # 2️⃣ Send POST request with image
        files = {"file": ("screenshot.png", img_bytes, "image/png")}
        response = requests.post(BACKEND_URL, files=files, timeout=10)

        # 3️⃣ Parse backend response
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                guidance = data["data"].get("guidance", "No guidance returned")
                return guidance
            else:
                print(f"Backend error: {data.get('message')}")
                return "Sorry, I couldn't get guidance from backend."
        else:
            print(f"HTTP error: {response.status_code}")
            return "Sorry, backend is not responding."
    except Exception as e:
        print(f"Backend connector error: {e}")
        return "Error communicating with backend."