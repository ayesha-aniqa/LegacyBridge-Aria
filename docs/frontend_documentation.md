# LegacyBridge — Frontend Client Documentation

## 👵 Overview: The "Aria" Client

The **LegacyBridge Client** is the user-facing component of the system. It acts as an always-on, non-intrusive companion named **Aria** that watches the user's screen and provides warm, natural voice guidance and visual cues. 

Unlike traditional accessibility tools, Aria uses **pure vision** (multimodal AI) to understand the screen context, meaning it requires no deep integration with other apps or the operating system's accessibility APIs.

---

## 🏗️ Client Architecture

The client is built using **Python 3.11** and **Tkinter**, designed to be lightweight and responsive. It follows a reactive **Research → Guidance → Action** loop.

### Core Agent Loop
1.  **Capture**: Every $N$ seconds (adaptive), the client captures a screenshot using `pyautogui` and `Pillow`.
2.  **Monitor**: `pynput` listeners track mouse movements and clicks to detect behavioral signals (hesitation, erratic movement, stagnation).
3.  **Analyze**: The screenshot and movement data are sent to the **LegacyBridge Backend** via a POST request.
4.  **Act**: The backend returns a JSON response containing:
    *   `guidance`: Aria's warm spoken instruction.
    *   `urgency`: Help level (LOW/MEDIUM/HIGH) which updates the UI color.
    *   `visual_target`: Screen coordinates for drawing a visual hint.
    *   `poll_interval_hint`: Adaptive timing for the next capture cycle.
5.  **Deliver**: The client speaks the guidance using **Google Cloud TTS**, updates the on-screen text box, and draws a pulsing circle/arrow on a transparent overlay.

---

## 🛠️ Key Components (`client/app/`)

### 1. `main.py` (The Orchestrator)
The heart of the client application.
- **`LegacyBridgeApp` Class**: Manages the Tkinter lifecycle, background threads, and UI updates.
- **Adaptive Polling**: Dynamically adjusts the screenshot frequency based on the `poll_interval_hint` (e.g., polling faster when the user is stuck).
- **Confusion Signal Collection**: Aggregates mouse drift and click data into a `movement_buffer` to assist the backend's confusion detection logic.

### 2. `tts_helper.py` (Aria's Voice)
Uses **Google Cloud Text-to-Speech** to bring the "Aria" persona to life.
- **Persona Settings**: Uses the `en-US-Wavenet-F` voice with a slowed speaking rate (0.85x) to ensure clarity for elderly ears.
- **Non-Blocking Playback**: TTS runs in a separate thread using `playsound` so the UI remains interactive.

### 3. `visual_overlay.py` (Visual Guidance)
A specialized, transparent fullscreen window that draws over everything else.
- **Click-Through Transparency**: Utilizes Windows-specific `SetWindowLongW` (via `ctypes`) to ensure the overlay doesn't block user clicks.
- **Pulsing Targets**: Draws animated circles and arrows at normalized coordinates returned by Gemini Vision.
- **Large Assets**: Uses high-contrast, large indicators (35px+) to ensure visibility for users with visual impairments.

### 4. `voice_input.py` (Bidirectional Audio)
Enables the user to talk back to Aria.
- **Google Cloud Speech-to-Text**: Listens for wake phrases like *"Aria"* or *"Help me"*.
- **Interactive Feedback**: When a voice command is detected, it's sent to the backend to refine the AI's guidance strategy.

---

## 🎨 UI Design for Elderly Users

Every design decision in the client is guided by the **Aria Persona**:

| Feature | Design Choice | Reason |
| :--- | :--- | :--- |
| **Font Size** | 16pt Bold (Arial) | Maximum readability for older eyes. |
| **Urgency Colors** | Green 🟢 / Yellow 🟡 / Red 🔴 | Simple, universal signals for "All good" vs. "I'm here to help." |
| **Controls** | Large, high-contrast buttons | Prevents misclicks; clearly labeled ("Mute Aria"). |
| **Feedback** | Live "Aria is Watching" status | Provides reassurance that the help system is active. |

---

## 🚦 Urgency & Adaptive Polling

The client dynamically changes its behavior based on the backend's assessment of user confusion:

- **🟢 LOW (Monitoring)**: Green UI, 6–8 second polling. Aria is silent unless she sees something worth mentioning.
- **🟡 MEDIUM (Suggesting)**: Yellow UI, 2–3 second polling. Aria offers gentle hints.
- **🔴 HIGH (Active Help)**: Red UI, 1 second polling. Aria provides direct, step-by-step guidance.

---

## ⚙️ Technical Requirements

### Dependencies
- **UI**: `tkinter`
- **Vision**: `pyautogui`, `Pillow`
- **Input**: `pynput`, `PyAudio`
- **Networking**: `requests`, `python-dotenv`
- **Google Cloud**: `google-cloud-texttospeech`, `google-cloud-speech`

### Environment Variables (`.env`)
- `BACKEND_URL`: URL of the Cloud Run or local FastAPI server.
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to the service account JSON for TTS/STT.
- `SCREENSHOT_INTERVAL`: Default polling rate (e.g., `2`).

---

## 🚀 Running the Client

Ensure you are in the project root and have your virtual environment active:

```bash
# Install dependencies
pip install -r client/requirements.txt

# Run the client
python client/app/main.py
```
