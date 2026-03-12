"""
Demo Scenario Definitions for LegacyBridge
--------------------------------------------
Each scenario maps a mock screen to a description and expected Aria behavior.
Used by demo_runner.py to feed controlled screens to the backend.
"""

import os

MOCK_SCREENS_DIR = os.path.join(os.path.dirname(__file__), "mock_screens")

def screen(name: str) -> str:
    return os.path.join(MOCK_SCREENS_DIR, f"{name}.jpg")


# Each scenario:
# - name        : display name shown in the demo runner console
# - screen_file : path to the mock screenshot
# - description : what this scenario demonstrates (narrate during recording)
# - hold        : seconds to pause on this screen before advancing
# - simulate_clicks : list of (x, y) clicks to send to /report-click
#                     (simulates user confusion / panic clicking)

DEMO_SCENARIOS = [
    {
        "name": "Normal Home Screen",
        "screen_file": screen("home_screen"),
        "description": (
            "Aria watches a calm home screen. "
            "She gives a reassuring, low-urgency message."
        ),
        "hold": 4,
        "simulate_clicks": [],
    },
    {
        "name": "WhatsApp Chat List",
        "screen_file": screen("whatsapp_chat_list"),
        "description": (
            "User is trying to read their messages. "
            "Aria identifies WhatsApp and guides them to the right conversation."
        ),
        "hold": 4,
        "simulate_clicks": [],
    },
    {
        "name": "User Stuck on Settings (Confusion Trigger)",
        "screen_file": screen("stuck_on_settings"),
        "description": (
            "User is tapping the wrong option in Settings repeatedly. "
            "Confusion detection kicks in — Aria gives specific physical guidance."
        ),
        "hold": 6,
        # Simulate 4 clicks in the same area (tapping wrong item)
        "simulate_clicks": [(650, 380), (655, 395), (648, 388), (660, 375), (645, 390)],
    },
    {
        "name": "Incoming Video Call",
        "screen_file": screen("video_call_incoming"),
        "description": (
            "Urgent scenario: daughter is calling via video. "
            "Aria immediately switches to high urgency and tells them how to answer."
        ),
        "hold": 5,
        "simulate_clicks": [],
    },
    {
        "name": "Missed Call Detected",
        "screen_file": screen("missed_call"),
        "description": (
            "User missed a call and sees the notification. "
            "Aria guides them calmly to call back."
        ),
        "hold": 4,
        "simulate_clicks": [],
    },
    {
        "name": "WhatsApp Open Chat (Reply Needed)",
        "screen_file": screen("whatsapp_chat_open"),
        "description": (
            "User opened a chat. Aria guides them to the microphone button "
            "to send a voice note — no typing needed."
        ),
        "hold": 5,
        "simulate_clicks": [],
    },
    {
        "name": "Error Popup (Confusion + High Urgency)",
        "screen_file": screen("error_popup"),
        "description": (
            "System error dialog appeared. User is confused and keeps tapping. "
            "Aria explains calmly and tells them to press the big OK button."
        ),
        "hold": 5,
        "simulate_clicks": [(640, 300), (640, 300), (640, 300)],  # Panic clicking error
    },
]
