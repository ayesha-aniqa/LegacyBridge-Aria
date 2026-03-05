# LegacyBridge 👵🤝🤖

**LegacyBridge** is an always-on AI screen-watching agent designed to help elderly non-tech users navigate their devices using only natural voice guidance. 

> *Part of the Gemini Live Agent Challenge 2026.*

## 🚀 The Vision
- **Aria (Persona):** A warm, slow, patient voice (like a kind grandchild).
- **Pure Vision:** No DOM access, no app APIs — just Gemini 2.0 Flash "eyes".
- **Elderly First UX:** Large text, simple UI, proactive assistance.

## 📁 Directory Structure
- `client/`: Desktop agent (Python/Tkinter) — Screenshot capture & Overlay UI.
- `server/`: FastAPI Backend — Gemini Vision integration & TTS generation.
- `shared/`: Common schemas and utility functions.
- `infra/`: Docker & Google Cloud Run deployment scripts.
- `docs/`: Architecture, demo script, and blog post.

## 🛠️ Tech Stack
- **AI:** Gemini 2.0 Flash (Vision)
- **Backend:** FastAPI (Python)
- **Voice:** Google Cloud Text-to-Speech
- **UI:** Python Tkinter (Local Overlay)
- **Cloud:** Google Cloud Run + Docker

## 👥 Team & Roles
- **Dev 1 (Backend/AI):** Gemini integration, screenshot loop, confusion detection.
- **Dev 2 (Frontend/UX):** Overlay UI, TTS integration, elderly UX design.
- **Dev 3 (Cloud/Demo):** Infrastructure (Terraform/Docker), architecture, documentation.

## 📅 10-Day Sprint Plan
1. **Day 1-2:** MVP Core Loop (Screenshot -> Gemini -> Text).
2. **Day 3-4:** Voice Integration & Overlay UI.
3. **Day 5-6:** Confusion Detection & Refinement.
4. **Day 7-8:** Cloud Deployment & Stress Testing.
5. **Day 9-10:** Demo Video, Blog Post & Submission.

## 🏁 Getting Started
1. `cp .env.example .env` (Add your API keys)
2. `pip install -r client/requirements.txt`
3. `pip install -r server/requirements.txt`
