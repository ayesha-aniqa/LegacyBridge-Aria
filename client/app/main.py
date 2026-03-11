import time
import os
import requests
import pyautogui
import threading
import tkinter as tk
from PIL import Image
from dotenv import load_dotenv
from pynput import mouse
import pyttsx3

engine = pyttsx3.init()
# Slower, easier speed for elderly users
engine.setProperty('rate', 150) 

# Load environment variables
load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
INTERVAL = int(os.getenv("SCREENSHOT_INTERVAL", 2))
SCREENSHOT_DIR = "screenshots"

if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

class LegacyBridgeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LegacyBridge - Aria")
        self.root.geometry("450x400+100+100") # Positioned top-left
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(False) # Keep window decorations for now
        
        # UI Elements
        self.title_label = tk.Label(root, text="Aria is Watching 👵🤝🤖", font=("Arial", 16, "bold"), fg="#2c3e50")
        self.title_label.pack(pady=10)
        
        self.status_label = tk.Label(root, text="Status: Ready", font=("Arial", 10), fg="green")
        self.status_label.pack()
        
        # Confusion indicator label
        self.confusion_label = tk.Label(root, text="", font=("Arial", 9), fg="#7f8c8d")
        self.confusion_label.pack()
        
        self.guidance_box = tk.Text(root, height=5, width=40, font=("Arial", 14), wrap=tk.WORD, bg="#f9f9f9", padx=10, pady=10)
        self.guidance_box.pack(pady=15)
        self.guidance_box.insert(tk.END, "I'm here to help. Just use your computer normally.")
        
        self.action_label = tk.Label(root, text="", font=("Arial", 12, "italic"), fg="#e67e22")
        self.action_label.pack()

        # Start the processing thread
        self.running = True
        self.thread = threading.Thread(target=self.run_logic_loop, daemon=True)
        self.thread.start()

        # Start the mouse click listener for confusion detection
        self.click_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.click_listener.start()

    def on_mouse_click(self, x, y, button, pressed):
        """Callback for mouse clicks — sends click position to backend for confusion tracking."""
        if pressed:  # Only on press, not release
            try:
                requests.post(
                    f"{BACKEND_URL}/report-click",
                    json={"x": int(x), "y": int(y)},
                    timeout=2
                )
            except Exception:
                pass  # Don't let click reporting crash the app

    def update_ui(self, guidance, urgency, hint, confusion=None):
        """Updates the UI elements with data from the backend."""
        self.guidance_box.delete(1.0, tk.END)
        self.guidance_box.insert(tk.END, guidance)
        
        self.action_label.config(text=f"Hint: {hint}" if hint else "")

        # --- TO ACTIVATE VOICE ---
        def speak():
            try:
                engine.say(guidance)
                engine.runAndWait()
            except Exception as e:
                print(f"Voice Error: {e}")
        
        threading.Thread(target=speak, daemon=True).start()
        
        # Change UI color based on urgency
        if urgency == "high":
            self.guidance_box.config(bg="#fff2f2") # Light red
            self.status_label.config(text="Status: Active Help", fg="red")
        elif urgency == "medium":
            self.guidance_box.config(bg="#fffdf2") # Light yellow
            self.status_label.config(text="Status: Suggesting", fg="orange")
        else:
            self.guidance_box.config(bg="#f2fff2") # Light green
            self.status_label.config(text="Status: Monitoring", fg="green")

        # Update confusion indicator if data is available
        if confusion and confusion.get("is_confused"):
            score_pct = int(confusion["score"] * 100)
            self.confusion_label.config(
                text=f"🔴 Confusion detected ({score_pct}%) — Aria is giving extra help",
                fg="#e74c3c"
            )
        else:
            self.confusion_label.config(text="🟢 User seems comfortable", fg="#27ae60")

    def capture_and_process(self):
        """Single step: Capture -> Send -> Get Response."""
        timestamp = int(time.time())
        file_path = os.path.join(SCREENSHOT_DIR, f"screen_{timestamp}.jpg")
        
        try:
            # 1. Capture
            screenshot = pyautogui.screenshot()
            screenshot.thumbnail((1280, 720))
            screenshot.save(file_path, "JPEG", quality=75, optimize=True)
            
            # 2. Send to Backend
            url = f"{BACKEND_URL}/process-screen"
            with open(file_path, "rb") as f:
                response = requests.post(url, files={"file": f}, timeout=10)
            
            # 3. Parse and Update
            if response.status_code == 200:
                result = response.json()
                if result["status"] == "success":
                    data = result["data"]
                    confusion = result.get("confusion")
                    # Schedule UI update on the main thread
                    self.root.after(
                        0, self.update_ui,
                        data['guidance'], data['urgency'],
                        data.get('action_hint'), confusion
                    )
            
            # Cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
                
        except Exception as e:
            print(f"Loop Error: {e}")
            self.root.after(0, lambda: self.status_label.config(text=f"Status: Error - {str(e)[:20]}...", fg="red"))

    def run_logic_loop(self):
        """Background thread for the continuous processing loop."""
        print("Starting background logic thread...")
        while self.running:
            self.capture_and_process()
            time.sleep(INTERVAL)

def main():
    root = tk.Tk()
    app = LegacyBridgeApp(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.running = False
        app.click_listener.stop()
        root.destroy()

if __name__ == "__main__":
    main()
