# LegacyBridge 👵🤝🤖

**LegacyBridge** is an always-on AI screen-watching agent that helps elderly non-tech users navigate their devices using only natural voice guidance — no DOM access, no app APIs, purely vision-based.

> *Gemini Live Agent Challenge 2026 — UI Navigator Category*

---

## 🚀 The Problem & Solution

**1 billion+ elderly people** worldwide struggle with smartphones and computers. They get confused, click the wrong things, and have no one to help in real time.

**Aria** watches their screen every few seconds using **Gemini 2.0 Flash Vision**, understands what is happening, detects confusion, and speaks calm guidance like:
> *"I see your daughter Sara is calling. Touch the big green circle on the right."*

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| AI Model | Gemini 2.0 Flash (Vertex AI) |
| Backend | FastAPI (Python) + Uvicorn |
| Voice | pyttsx3 (local TTS) |
| Client UI | Python Tkinter overlay |
| Cloud | Google Cloud Run + Docker |
| Auth | Google Service Account (key.json) |

---

## 📁 Directory Structure

```
LegacyBridge/
├── server/
│   ├── app/
│   │   ├── main.py               # FastAPI server (Gemini Vision endpoint)
│   │   ├── confusion_detector.py # Confusion detection engine (5 strategies)
│   │   ├── image_utils.py        # Perceptual hashing + async image processing
│   │   └── ai_optimizer.py       # Warm-up, auto-retry, response sanitizer
│   └── requirements.txt
├── client/
│   ├── app/
│   │   └── main.py               # Tkinter overlay + click tracking
│   └── requirements.txt
├── demo/
│   ├── mock_screen_generator.py  # Generate synthetic demo screenshots
│   ├── scenarios.py              # Demo scenario definitions
│   ├── demo_runner.py            # Scripted demo orchestrator
│   └── start_demo.ps1            # One-click Windows launcher
├── tests/
│   ├── test_backend.py           # Backend health + Gemini Vision tests
│   ├── test_performance.py       # Latency, throughput, cache benchmarks
│   └── test_ai_quality.py        # AI response quality validation
├── infra/                        # Docker + Cloud Run deployment
├── docs/                         # Architecture diagram, blog post
└── .env.example                  # Environment variable template
```

---

## 🏁 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/ayesha-aniqa/LegacyBridge-Hackathon
cd LegacyBridge-Hackathon
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r server/requirements.txt
pip install -r client/requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
GOOGLE_APPLICATION_CREDENTIALS=C:\Users\User\Downloads\key.json
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-ecentral1
```

### 3. Start the Backend

```bash
cd server
uvicorn app.main:app --reload --port 8000
```

Backend available at: `http://localhost:8000`
API docs: `http://localhost:8000/docs`

### 4. Start the Client

```bash
cd client
python app/main.py
```

---

## 🎬 Demo Setup (For Recording)

### One-Click Launch (Windows)

```powershell
.\demo\start_demo.ps1 -KeyPath "C:\Users\User\Downloads\key.json"
```

### Manual Demo Steps

```bash
# Step 1 — Generate mock screens (one time)
python demo/mock_screen_generator.py

# Step 2 — Start backend (separate terminal)
cd server && uvicorn app.main:app --reload

# Step 3 — Run the full demo sequence
python demo/demo_runner.py

# Run a specific scenario:
python demo/demo_runner.py --scenario 2   # Confusion detection demo
python demo/demo_runner.py --list          # Show all scenarios
```

### Demo Scenarios

| # | Scenario | What Aria does |
|---|---|---|
| 0 | Home Screen | Reassuring low-urgency guidance |
| 1 | WhatsApp Chat List | Guides to daughter's conversation |
| 2 | Stuck on Settings ⚠️ | **Confusion detected** — physical guidance |
| 3 | Incoming Video Call 🔴 | **High urgency** — answer instructions |
| 4 | Missed Call | Calm callback guidance |
| 5 | WhatsApp Open Chat | Voice note instructions |
| 6 | Error Popup 🔴 | **Confusion + error** — OK button guidance |

---

## 🧠 Core Agent Loop

```
Screenshot (every 1-4s)
       ↓
Perceptual Hash → Cache Hit? → Return cached response instantly
       ↓ (cache miss)
Vertex AI Gemini 2.0 Flash Vision
       ↓
Confusion Detector evaluates: clicks, urgency, stagnation, inactivity
       ↓
Confusion-aware prompt injected if needed
       ↓
Aria guidance text → pyttsx3 voice + Tkinter overlay
       ↓
Client adapts poll interval (1s urgent / 4s calm)
```

---

## 🧪 Running Tests

```bash
# Backend health + Gemini Vision
python tests/test_backend.py

# Performance benchmarks
python tests/test_performance.py

# AI response quality
python tests/test_ai_quality.py
```

---

## 👥 Team & Roles

| Member | Role |
|---|---|
| **Hammad** | Backend / AI — Gemini integration, confusion detection, optimization |
| **Rameesha** | Frontend / UX — Tkinter overlay, TTS, elderly UX design |
| **Ayesha** | Cloud / Demo — Docker, Cloud Run, architecture, demo video |

---

## 🏆 Hackathon Submission

- **Contest:** Gemini Live Agent Challenge (Google × Devpost)
- **Deadline:** March 16, 2026
- **Category:** UI Navigator
- **Demo Video:** *(YouTube link here)*
- **Blog Post:** *(Medium/dev.to link here)*
