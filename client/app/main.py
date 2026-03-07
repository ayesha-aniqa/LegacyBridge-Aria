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
    
    # Optimization: Reduce image size for faster API processing
    screenshot.thumbnail((1280, 720)) # Resize to 720p to save bandwidth/latency
    screenshot.save(file_path, "PNG")
    
    print(f"Captured screenshot: {file_path}")
    return file_path

def process_screen_pipeline(file_path):
    """Pipeline: Sends screenshot to backend and returns the text guidance."""
    url = f"{BACKEND_URL}/process-screen"
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files)
            
        if response.status_code == 200:
            result = response.json()
            if result["status"] == "success":
                guidance = result.get("guidance", "Aria is here.")
                print(f"--- ARIA'S GUIDANCE: {guidance} ---")
                return guidance
        else:
            print(f"Backend error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Connection error: {e}")
    
    return None

def run_loop():
    """Main loop for periodic screen capture and processing."""
    print(f"Starting LegacyBridge Pipeline (Interval: {INTERVAL}s)...")
    try:
        while True:
            # Step 1: Capture
            file_path = capture_screen()
            
            # Step 2 & 3: API call & Text Output
            guidance = process_screen_pipeline(file_path)
            
            # Step 4: UI integration (future step for Dev 2)
            # if guidance:
            #     update_overlay(guidance)
            
            # Clean up old screenshots to save space
            if os.path.exists(file_path):
                os.remove(file_path)
                
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\nStopping client...")

if __name__ == "__main__":
    run_loop()
