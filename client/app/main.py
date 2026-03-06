import time
import os
import requests
import pyautogui
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
INTERVAL = int(os.getenv("SCREENSHOT_INTERVAL", 2))
SCREENSHOT_DIR = "screenshots"

if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

def capture_screen():
    """Captures the current screen and saves it as a temporary file."""
    timestamp = int(time.time())
    file_path = os.path.join(SCREENSHOT_DIR, f"screen_{timestamp}.png")
    
    # Take screenshot using pyautogui
    screenshot = pyautogui.screenshot()
    screenshot.save(file_path)
    
    print(f"Captured screenshot: {file_path}")
    return file_path

def send_to_backend(file_path):
    """Sends the captured screenshot to the backend server."""
    url = f"{BACKEND_URL}/process-screen"
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files)
            
        if response.status_code == 200:
            print(f"Successfully processed: {response.json()}")
        else:
            print(f"Backend error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Connection error: {e}")

def run_loop():
    """Main loop for periodic screen capture."""
    print(f"Starting LegacyBridge Client Loop (Interval: {INTERVAL}s)...")
    try:
        while True:
            file_path = capture_screen()
            send_to_backend(file_path)
            
            # Clean up: optional, keep for now for debugging
            # os.remove(file_path) 
            
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\nStopping client...")

if __name__ == "__main__":
    run_loop()
