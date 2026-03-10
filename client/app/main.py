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
    """Captures and optimizes screenshot for faster backend processing."""
    timestamp = int(time.time())
    file_path = os.path.join(SCREENSHOT_DIR, f"screen_{timestamp}.jpg")
    
    # 1. Capture screen
    screenshot = pyautogui.screenshot()
    
    # 2. Optimization: Resize to 720p (Good balance of detail/speed)
    screenshot.thumbnail((1280, 720)) 
    
    # 3. Compression: Save as JPG with quality optimization (saves bandwidth)
    screenshot.save(file_path, "JPEG", quality=75, optimize=True)
    
    print(f"Captured/Optimized: {file_path}")
    return file_path

def process_screen_pipeline(file_path):
    """Sends screenshot to backend and processes the structured JSON response."""
    url = f"{BACKEND_URL}/process-screen"
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files)
            
        if response.status_code == 200:
            result = response.json()
            if result["status"] == "success":
                data = result["data"]
                guidance = data.get("guidance", "Aria is here.")
                urgency = data.get("urgency", "low")
                hint = data.get("action_hint", "Waiting for screen...")
                
                # Output formatted for CLI/Console (Later for Dev 2 to hook UI)
                print(f"\n--- ARIA'S GUIDANCE (Urgency: {urgency}) ---")
                print(f"Message: {guidance}")
                print(f"Action:  {hint}")
                print("-" * 40)
                
                return data
        else:
            print(f"Backend error: {response.status_code}")
            
    except Exception as e:
        print(f"Connection error: {e}")
    
    return None

def run_loop():
    """Main loop for periodic screen capture and structured processing."""
    print(f"Starting LegacyBridge Optimized Pipeline (Interval: {INTERVAL}s)...")
    try:
        while True:
            file_path = capture_screen()
            process_screen_pipeline(file_path)
            
            # Clean up old screenshots immediately
            if os.path.exists(file_path):
                os.remove(file_path)
                
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\nStopping client...")

if __name__ == "__main__":
    run_loop()
