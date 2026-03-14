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
            root,
            text="Aria is Watching 👵🤝🤖",
            font=("Arial", 16, "bold"),
            fg="#2c3e50"
        )
        self.title_label.pack(pady=10)

        self.status_label = tk.Label(
            root,
            text="Status: Ready",
            font=("Arial", 10),
            fg="green"
        )
        self.status_label.pack()

        # Confusion indicator
        self.confusion_label = tk.Label(
            root,
            text="🟢 User seems comfortable",
            font=("Arial", 9),
            fg="#27ae60"
        )
        self.confusion_label.pack(pady=(2, 0))

        self.guidance_box = tk.Text(
            root,
            height=5,
            width=40,
            font=("Arial", 14),
            wrap=tk.WORD,
            bg="#f9f9f9",
            padx=10,
            pady=10
        )
        self.guidance_box.pack(pady=10)
        self.guidance_box.insert(
            tk.END,
            "I'm here to help. Just use your computer normally."
        )

        # ── Controls ─────────────────────────────────────────────────────
        self.controls_frame = tk.Frame(root)
        self.controls_frame.pack(pady=5)

        self.is_muted = False

        self.mute_btn = tk.Button(
            self.controls_frame,
            text="🔇 Mute Aria",
            command=self.toggle_mute,
            bg="#ecf0f1",
            font=("Arial", 10)
        )
        self.mute_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(
            self.controls_frame,
            text="🛑 Stop Speaking (ESC)",
            command=self.stop_tts,
            bg="#fadbd8",
            font=("Arial", 10)
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.action_label = tk.Label(
            root,
            text="",
            font=("Arial", 12, "italic"),
            fg="#e67e22"
        )
        self.action_label.pack()

        # ── State Variables ──────────────────────────────────────────────
        self.last_spoken = ""
        self.current_interval = INTERVAL

        self.movement_buffer = []
        self.last_move_recorded = 0

        self.running = True

        # ── Background Thread ────────────────────────────────────────────
        self.thread = threading.Thread(
            target=self.run_logic_loop,
            daemon=True
        )
        self.thread.start()

        # Mouse listener
        self.mouse_listener = mouse.Listener(
            on_click=self.on_mouse_click,
            on_move=self.on_mouse_move
        )
        self.mouse_listener.start()

        # Keyboard listener
        self.key_listener = keyboard.Listener(
            on_press=self.on_key_press
        )
        self.key_listener.start()

    # ────────────────────────────────────────────────────────────────────
    # Controls
    # ────────────────────────────────────────────────────────────────────

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self.mute_btn.config(
            text="🔊 Unmute Aria" if self.is_muted else "🔇 Mute Aria"
        )

    def stop_tts(self):
        print("Stopping TTS playback...")
        if os.name == "nt":
            os.system("taskkill /IM Microsoft.Photos.exe /F")

    def on_key_press(self, key):
        if key == keyboard.Key.esc:
            self.stop_tts()

    # ────────────────────────────────────────────────────────────────────
    # Voice Input
    # ────────────────────────────────────────────────────────────────────

    def handle_voice_command(self, text):

        print(f"Voice Command Received: {text}")

        try:
            requests.post(
                f"{BACKEND_URL}/voice-input",
                json={"text": text},
                timeout=5
            )
        except Exception:
            pass

    # ────────────────────────────────────────────────────────────────────
    # Mouse Tracking
    # ────────────────────────────────────────────────────────────────────

    def on_mouse_click(self, x, y, button, pressed):

        if pressed:
            try:
                requests.post(
                    f"{BACKEND_URL}/report-click",
                    json={"x": int(x), "y": int(y)},
                    timeout=2
                )
            except Exception:
                pass

    def on_mouse_move(self, x, y):

        now = time.time()

        if now - self.last_move_recorded > 0.1:
            self.movement_buffer.append((int(x), int(y), now))
            self.last_move_recorded = now

            if len(self.movement_buffer) > 500:
                self.movement_buffer.pop(0)

    # ────────────────────────────────────────────────────────────────────
    # UI Update
    # ────────────────────────────────────────────────────────────────────

    def update_ui(
        self,
        guidance,
        urgency,
        hint,
        confusion=None,
        response_ms=None,
        cache_hit=False
    ):

        self.guidance_box.delete(1.0, tk.END)
        self.guidance_box.insert(tk.END, guidance)

        self.action_label.config(text=f"Hint: {hint}" if hint else "")

        # Voice output
        if guidance != self.last_spoken and not self.is_muted:
            self.last_spoken = guidance

            threading.Thread(
                target=lambda: self.tts.speak(guidance),
                daemon=True
            ).start()

        # Visual overlay
        if hint:
            self.visual_overlay.draw_target(hint)

        # Status styling
        time_label = (
            f" | {response_ms:.0f}ms{'⚡' if cache_hit else ''}"
            if response_ms else ""
        )

        if urgency == "high":
            self.guidance_box.config(bg="#fff2f2")
            self.status_label.config(
                text=f"Status: Active Help{time_label}",
                fg="red"
            )

        elif urgency == "medium":
            self.guidance_box.config(bg="#fffdf2")
            self.status_label.config(
                text=f"Status: Suggesting{time_label}",
                fg="orange"
            )

        else:
            self.guidance_box.config(bg="#f2fff2")
            self.status_label.config(
                text=f"Status: Monitoring{time_label}",
                fg="green"
            )

        # ── Confusion UI (Day 5 Feature) ────────────────────────────────
        if confusion and confusion.get("is_confused"):

            score_pct = int(confusion["score"] * 100)
            streak = confusion.get("streak", 0)
            reason = confusion.get("reason", "")

            self.confusion_label.config(
                text=f"🔴 Confused ({score_pct}%) — streak {streak} — {reason}",
                fg="#e74c3c",
                font=("Arial", 10, "bold")
            )

            self.guidance_box.config(bg="#ffe6e6")

            self.root.after(
                500,
                lambda: self.guidance_box.config(bg="#f9f9f9")
            )

            if not self.is_muted:
                threading.Thread(
                    target=lambda: self.tts.speak(
                        f"User confusion detected: {score_pct} percent"
                    ),
                    daemon=True
                ).start()

        else:

            self.confusion_label.config(
                text="🟢 User seems comfortable",
                fg="#27ae60",
                font=("Arial", 9)
            )

            self.guidance_box.config(bg="#f9f9f9")

    # ────────────────────────────────────────────────────────────────────
    # Screenshot Loop
    # ────────────────────────────────────────────────────────────────────

    def capture_and_process(self):

        timestamp = int(time.time())
        file_path = os.path.join(
            SCREENSHOT_DIR,
            f"screen_{timestamp}.jpg"
        )

        try:

            screenshot = pyautogui.screenshot()
            screenshot.thumbnail((1280, 720))

            screenshot.save(
                file_path,
                "JPEG",
                quality=75,
                optimize=True
            )

            movement_data = json.dumps(self.movement_buffer)
            self.movement_buffer = []

            with open(file_path, "rb") as f:

                response = requests.post(
                    f"{BACKEND_URL}/process-screen",
                    files={"file": f},
                    data={"movement": movement_data},
                    timeout=15
                )

            if response.status_code == 200:

                result = response.json()

                if result["status"] == "success":

                    data = result["data"]

                    confusion = result.get("confusion")
                    response_ms = result.get("response_ms")
                    cache_hit = result.get("cache_hit", False)

                    next_poll = result.get(
                        "next_poll_interval",
                        INTERVAL
                    )

                    self.current_interval = max(
                        1,
                        min(8, next_poll)
                    )

                    self.root.after(
                        0,
                        self.update_ui,
                        data["guidance"],
                        data["urgency"],
                        data.get("visual_target"),
                        confusion,
                        response_ms,
                        cache_hit
                    )

            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:

            print(f"Loop Error: {e}")

            self.root.after(
                0,
                lambda: self.status_label.config(
                    text=f"Status: Error - {str(e)[:20]}...",
                    fg="red"
                )
            )

    # ────────────────────────────────────────────────────────────────────

    def run_logic_loop(self):

        print("Starting background logic thread...")

        while self.running:

            self.capture_and_process()
            time.sleep(self.current_interval)


# ────────────────────────────────────────────────────────────────────────

def main():

    root = tk.Tk()
    app = LegacyBridgeApp(root)

    try:
        root.mainloop()

    except KeyboardInterrupt:

        app.running = False
        app.mouse_listener.stop()
        root.destroy()


if __name__ == "__main__":
    main()