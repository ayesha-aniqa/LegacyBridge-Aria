"""
Confusion Detection Module for LegacyBridge
---------------------------------------------
Detects when an elderly user appears confused or stuck by analyzing:
  1. Repeated clicks in the same screen area (within a radius)
  2. Repeated high-urgency Gemini responses (AI thinks user is stuck)
  3. Screen stagnation (same screen appearing multiple times in a row)

When confusion is detected, Aria's prompt is augmented to give
more proactive, reassuring guidance.
"""

import time
import math
import os
from collections import deque
from dotenv import load_dotenv

load_dotenv()

# How many repeated signals before we flag confusion
CONFUSION_THRESHOLD = int(os.getenv("CONFUSION_THRESHOLD", 3))

# Radius in pixels — clicks within this radius count as "same area"
CLICK_RADIUS = 80

# Time window in seconds — only consider events within this window
TIME_WINDOW = 30


class ConfusionDetector:
    """Tracks user behavior signals and determines if the user is confused."""

    def __init__(self):
        # Stores recent click positions as (x, y, timestamp)
        self.click_history = deque(maxlen=20)

        # Stores recent Gemini urgency levels as (urgency, timestamp)
        self.urgency_history = deque(maxlen=10)

        # Stores recent Gemini guidance texts to detect repetitive responses
        self.guidance_history = deque(maxlen=10)

        # Current confusion state
        self.is_confused = False
        self.confusion_reason = ""
        self.confusion_score = 0.0  # 0.0 (calm) to 1.0 (very confused)

    def record_click(self, x: int, y: int):
        """Record a mouse click position from the client."""
        self.click_history.append((x, y, time.time()))

    def record_response(self, guidance: str, urgency: str):
        """Record a Gemini API response for pattern analysis."""
        now = time.time()
        self.urgency_history.append((urgency, now))
        self.guidance_history.append((guidance, now))

    def _get_recent_clicks(self):
        """Return clicks within the active time window."""
        cutoff = time.time() - TIME_WINDOW
        return [(x, y, t) for x, y, t in self.click_history if t > cutoff]

    def _get_recent_urgencies(self):
        """Return urgency records within the active time window."""
        cutoff = time.time() - TIME_WINDOW
        return [(u, t) for u, t in self.urgency_history if t > cutoff]

    def _check_repeated_clicks(self) -> bool:
        """Detect if user clicked the same area multiple times (they're stuck)."""
        recent = self._get_recent_clicks()
        if len(recent) < CONFUSION_THRESHOLD:
            return False

        # Check if the last N clicks are all within CLICK_RADIUS of each other
        last_clicks = recent[-CONFUSION_THRESHOLD:]
        center_x = sum(c[0] for c in last_clicks) / len(last_clicks)
        center_y = sum(c[1] for c in last_clicks) / len(last_clicks)

        all_close = all(
            math.sqrt((c[0] - center_x) ** 2 + (c[1] - center_y) ** 2) <= CLICK_RADIUS
            for c in last_clicks
        )
        return all_close

    def _check_repeated_urgency(self) -> bool:
        """Detect if Gemini has been returning 'high' urgency repeatedly."""
        recent = self._get_recent_urgencies()
        if len(recent) < CONFUSION_THRESHOLD:
            return False

        last_urgencies = [u for u, t in recent[-CONFUSION_THRESHOLD:]]
        return all(u == "high" for u in last_urgencies)

    def _check_repeated_guidance(self) -> bool:
        """Detect if Gemini keeps giving the same guidance (screen hasn't changed)."""
        cutoff = time.time() - TIME_WINDOW
        recent = [g for g, t in self.guidance_history if t > cutoff]
        if len(recent) < CONFUSION_THRESHOLD:
            return False

        last_guidances = recent[-CONFUSION_THRESHOLD:]
        # If all recent guidances are identical, user hasn't progressed
        return len(set(last_guidances)) == 1

    def evaluate(self) -> dict:
        """
        Run all confusion checks and return the current confusion state.
        Returns a dict with: is_confused, score, reason, prompt_modifier
        """
        reasons = []
        score = 0.0

        # Check 1: Repeated clicks in same area
        if self._check_repeated_clicks():
            reasons.append("repeated_clicks")
            score += 0.4

        # Check 2: Gemini keeps saying urgency is high
        if self._check_repeated_urgency():
            reasons.append("repeated_high_urgency")
            score += 0.3

        # Check 3: Same guidance being given (user stuck on same screen)
        if self._check_repeated_guidance():
            reasons.append("screen_stagnation")
            score += 0.3

        # Clamp score to 1.0
        score = min(score, 1.0)

        self.is_confused = score >= 0.3
        self.confusion_score = score
        self.confusion_reason = ", ".join(reasons) if reasons else "none"

        # Build the prompt modifier for Gemini when confusion is detected
        prompt_modifier = ""
        if self.is_confused:
            prompt_modifier = self._build_prompt_modifier(reasons)

        return {
            "is_confused": self.is_confused,
            "score": round(self.confusion_score, 2),
            "reason": self.confusion_reason,
            "prompt_modifier": prompt_modifier
        }

    def _build_prompt_modifier(self, reasons: list) -> str:
        """Generate an extra prompt injection when confusion is detected."""
        parts = [
            "\n⚠️ CONFUSION DETECTED — The user appears to be struggling."
        ]

        if "repeated_clicks" in reasons:
            parts.append(
                "They have been tapping the same spot repeatedly. "
                "They may not know where to look next. "
                "Point them to the EXACT visual element with color and position."
            )

        if "repeated_high_urgency" in reasons:
            parts.append(
                "Multiple consecutive responses have been high urgency. "
                "Slow down your guidance. Be extra patient and reassuring."
            )

        if "screen_stagnation" in reasons:
            parts.append(
                "The screen has not changed for several cycles. "
                "The user may be frozen or unsure what to do. "
                "Offer a very simple, single next step."
            )

        parts.append(
            "Use an EXTRA warm tone. Start with something reassuring like "
            "'Don't worry, I'm right here with you.' Keep it under 15 words."
        )

        return " ".join(parts)

    def get_status(self) -> dict:
        """Return the current confusion status for API responses."""
        return {
            "is_confused": self.is_confused,
            "score": round(self.confusion_score, 2),
            "reason": self.confusion_reason
        }
