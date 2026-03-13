import time
import os
import json
import requests
import pyautogui
import threading
import tkinter as tk
from PIL import Image
from dotenv import load_dotenv
from pynput import mouse, keyboard

# New multimodality components
from tts_helper import AriaTTS
from visual_overlay import VisualOverlay
from voice_input import AriaVoiceInput

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
        self.root.geometry("450x480+100+100")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(False)

        # ── Multimodality Components ─────────────────────────────────────
        self.tts = AriaTTS()
        self.visual_overlay = VisualOverlay(self.root)
        self.voice_input = AriaVoiceInput(callback=self.handle_voice_command)
        self.voice_input.start_listening()

        # ── UI Elements ──────────────────────────────────────────────────
        self.title_label = tk.Label(
            root, text="Aria is Watching 👵🤝🤖",
            font=("Arial", 16, "bold"), fg="#2c3e50"
        )
        self.title_label.pack(pady=10)

        self.status_label = tk.Label(
            root, text="Status: Ready",
            font=("Arial", 10), fg="green"
        )
        self.status_label.pack()

        # Confusion indicator
        self.confusion_label = tk.Label(
            root, text="🟢 User seems comfortable",
            font=("Arial", 9), fg="#27ae60"
        )
        self.confusion_label.pack(pady=(2, 0))

        self.guidance_box = tk.Text(
            root, height=5, width=40, font=("Arial", 14),
            wrap=tk.WORD, bg="#f9f9f9", padx=10, pady=10
        )
        self.guidance_box.pack(pady=10)
        self.guidance_box.insert(tk.END, "I'm here to help. Just use your computer normally.")

        # Interrupt / Mute Controls
        self.controls_frame = tk.Frame(root)
        self.controls_frame.pack(pady=5)

        self.is_muted = False
        self.mute_btn = tk.Button(
            self.controls_frame, text="🔇 Mute Aria", command=self.toggle_mute,
            bg="#ecf0f1", font=("Arial", 10)
        )
        self.mute_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(
            self.controls_frame, text="🛑 Stop Speaking (ESC)", command=self.stop_tts,
            bg="#fadbd8", font=("Arial", 10)
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.action_label = tk.Label(
            root, text="", font=("Arial", 12, "italic"), fg="#e67e22"
        )
        self.action_label.pack()

        # Track last spoken guidance to avoid repeating voice
        self.last_spoken = ""

        # Adaptive poll interval — updated by backend hint
        self.current_interval = INTERVAL

        # Mouse movement tracking
        self.movement_buffer = []
        self.last_move_recorded = 0

        # ── Start background threads ─────────────────────────────────────
        self.running = True

        # Screenshot → API loop
        self.thread = threading.Thread(target=self.run_logic_loop, daemon=True)
        self.thread.start()

        # Mouse listener for confusion detection (clicks + moves)
        self.mouse_listener = mouse.Listener(
            on_click=self.on_mouse_click,
            on_move=self.on_mouse_move
        )
        self.mouse_listener.start()

        # Keyboard listener for ESC to stop TTS
        self.key_listener = keyboard.Listener(on_press=self.on_key_press)
        self.key_listener.start()

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self.mute_btn.config(text="🔊 Unmute Aria" if self.is_muted else "🔇 Mute Aria")

    def stop_tts(self):
        # In a real implementation with a proper player, we'd kill the process
        # For now, we'll just skip the next speak call if it's currently running
        print("Stopping TTS playback...")
        if os.name == 'nt':
            os.system("taskkill /IM Microsoft.Photos.exe /F") # Just an example if it opened in a default app

    def on_key_press(self, key):
        if key == keyboard.Key.esc:
            self.stop_tts()

    def handle_voice_command(self, text):
        """Handle transcribed text from voice input."""
        print(f"Voice Command Received: {text}")
        # Could send to backend as a special prompt injection
        try:
            requests.post(
                f"{BACKEND_URL}/voice-input",
                json={"text": text},
                timeout=5
            )
        except Exception:
            pass

    def on_mouse_click(self, x, y, button, pressed):
        """Send every mouse press to backend for confusion tracking."""
        if pressed:
            try:
                requests.post(
                    f"{BACKEND_URL}/report-click",
                    json={"x": int(x), "y": int(y)},
                    timeout=2
                )
            except Exception:
                pass  # Never let click reporting crash the app

    def on_mouse_move(self, x, y):
        """Record mouse movement with throttling (max 10 samples per second)."""
        now = time.time()
        if now - self.last_move_recorded > 0.1:  # 100ms throttle
            self.movement_buffer.append((int(x), int(y), now))
            self.last_move_recorded = now
            # Keep buffer sane
            if len(self.movement_buffer) > 500:
                self.movement_buffer.pop(0)

    def update_ui(self, guidance, urgency, hint, confusion=None, response_ms=None, cache_hit=False):
        """Update all UI elements with latest data from backend."""
        # ── Guidance text ────────────────────────────────────────────────
        self.guidance_box.delete(1.0, tk.END)
        self.guidance_box.insert(tk.END, guidance)

        # ── Action hint ──────────────────────────────────────────────────
        self.action_label.config(text=f"Hint: {hint}" if hint else "")

        # ── Voice output (skip if same as last) ──────────────────────────
        if guidance != self.last_spoken and not self.is_muted:
            self.last_spoken = guidance
            threading.Thread(target=lambda: self.tts.speak(guidance), daemon=True).start()

        # ── Visual Highlights ────────────────────────────────────────────
        if hint:
            self.visual_overlay.draw_target(hint)

        # ── Urgency-based styling + response time in status ────────────────
        time_label = f" | {response_ms:.0f}ms{'⚡' if cache_hit else ''}" if response_ms else ""
        if urgency == "high":
            self.guidance_box.config(bg="#fff2f2")
            self.status_label.config(text=f"Status: Active Help{time_label}", fg="red")
        elif urgency == "medium":
            self.guidance_box.config(bg="#fffdf2")
            self.status_label.config(text=f"Status: Suggesting{time_label}", fg="orange")
        else:
            self.guidance_box.config(bg="#f2fff2")
            self.status_label.config(text=f"Status: Monitoring{time_label}", fg="green")

        # ── Confusion indicator ──────────────────────────────────────────
        if confusion and confusion.get("is_confused"):
            score_pct = int(confusion["score"] * 100)
            streak = confusion.get("streak", 0)
            reason = confusion.get("reason", "")
            self.confusion_label.config(
                text=f"🔴 Confused ({score_pct}%) — streak {streak} — {reason}",
                fg="#e74c3c"
            )
        else:
            self.confusion_label.config(
                text="🟢 User seems comfortable",
                fg="#27ae60"
            )

    def capture_and_process(self):
        """Single cycle: Capture screenshot → Send to backend → Update UI."""
        timestamp = int(time.time())
        file_path = os.path.join(SCREENSHOT_DIR, f"screen_{timestamp}.jpg")

        try:
            # 1. Capture & optimise
            screenshot = pyautogui.screenshot()
            screenshot.thumbnail((1280, 720))
            screenshot.save(file_path, "JPEG", quality=75, optimize=True)

            # 2. Send to backend
            movement_data = json.dumps(self.movement_buffer)
            self.movement_buffer = []  # Clear buffer after taking snapshot

            with open(file_path, "rb") as f:
                response = requests.post(
                    f"{BACKEND_URL}/process-screen",
                    files={"file": f},
                    data={"movement": movement_data},
                    timeout=15
                )

            # 3. Parse & update
            if response.status_code == 200:
                result = response.json()
                if result["status"] == "success":
                    data = result["data"]
                    confusion = result.get("confusion")
                    response_ms = result.get("response_ms")
                    cache_hit = result.get("cache_hit", False)

                    # Adaptive interval — use backend's hint, clamp between 1 and 8s
                    next_poll = result.get("next_poll_interval", INTERVAL)
                    self.current_interval = max(1, min(8, next_poll))

                    self.root.after(
                        0, self.update_ui,
                        data["guidance"], data["urgency"],
                        data.get("visual_target"), confusion,
                        response_ms, cache_hit
                    )

            # Cleanup screenshot
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            print(f"Loop Error: {e}")
            self.root.after(
                0, lambda: self.status_label.config(
                    text=f"Status: Error - {str(e)[:20]}...", fg="red"
                )
            )

    def run_logic_loop(self):
        """Background thread: continuous screenshot → process loop (adaptive interval)."""
        print("Starting background logic thread...")
        while self.running:
            self.capture_and_process()
            time.sleep(self.current_interval)  # Uses adaptive interval from backend


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
