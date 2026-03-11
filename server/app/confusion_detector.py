"""
Confusion Detection Module for LegacyBridge (Refined v2)
----------------------------------------------------------
Detects when an elderly user appears confused or stuck by analyzing:
  1. Repeated clicks in the same screen area (within a configurable radius)
  2. Repeated high-urgency Gemini responses (AI thinks user is stuck)
  3. Screen stagnation (same guidance text appearing multiple times)
  4. Rapid clicking (panic clicking — many clicks in a short burst)
  5. Inactivity timeout (no interaction at all for extended time)

Confusion score is a weighted float from 0.0 (calm) to 1.0 (very confused).
When confusion is detected, a dynamic prompt modifier is built for Gemini,
so Aria speaks with extra warmth and gives more precise, physical guidance.
"""

import time
import math
import os
import logging
from collections import deque
from typing import Dict, List, Tuple

logger = logging.getLogger("aria.confusion")

# ─── Configuration (overridable via .env) ────────────────────────────────────

CONFUSION_THRESHOLD = int(os.getenv("CONFUSION_THRESHOLD", "3"))
CLICK_RADIUS = int(os.getenv("CLICK_RADIUS", "80"))        # px — same-area radius
TIME_WINDOW = int(os.getenv("CONFUSION_TIME_WINDOW", "30")) # seconds
RAPID_CLICK_WINDOW = 3    # seconds — burst detection window
RAPID_CLICK_COUNT = 5     # clicks in burst window to trigger
INACTIVITY_TIMEOUT = 60   # seconds — no clicks at all


class ConfusionDetector:
    """Tracks user behaviour signals and determines if the user is confused."""

    def __init__(self):
        # (x, y, timestamp)
        self.click_history: deque = deque(maxlen=50)

        # (urgency_str, timestamp)
        self.urgency_history: deque = deque(maxlen=15)

        # (guidance_text, timestamp)
        self.guidance_history: deque = deque(maxlen=15)

        # Timestamp of last recorded click
        self.last_click_time: float = time.time()

        # Running state
        self.is_confused: bool = False
        self.confusion_score: float = 0.0
        self.confusion_reason: str = "none"
        self.consecutive_confused_cycles: int = 0

    # ─── Recording methods (called from endpoints) ───────────────────────

    def record_click(self, x: int, y: int):
        """Record a mouse click from the client."""
        self.click_history.append((x, y, time.time()))
        self.last_click_time = time.time()

    def record_response(self, guidance: str, urgency: str):
        """Record a Gemini response for pattern tracking."""
        now = time.time()
        self.urgency_history.append((urgency, now))
        self.guidance_history.append((guidance.strip().lower(), now))

    # ─── Windowed helpers ─────────────────────────────────────────────────

    def _recent_clicks(self, window: float = None) -> List[Tuple[int, int, float]]:
        cutoff = time.time() - (window or TIME_WINDOW)
        return [(x, y, t) for x, y, t in self.click_history if t > cutoff]

    def _recent_urgencies(self) -> List[str]:
        cutoff = time.time() - TIME_WINDOW
        return [u for u, t in self.urgency_history if t > cutoff]

    def _recent_guidances(self) -> List[str]:
        cutoff = time.time() - TIME_WINDOW
        return [g for g, t in self.guidance_history if t > cutoff]

    # ─── Detection checks ────────────────────────────────────────────────

    def _check_repeated_clicks(self) -> float:
        """User clicking same spot repeatedly → weight 0.35"""
        recent = self._recent_clicks()
        if len(recent) < CONFUSION_THRESHOLD:
            return 0.0

        last_n = recent[-CONFUSION_THRESHOLD:]
        cx = sum(c[0] for c in last_n) / len(last_n)
        cy = sum(c[1] for c in last_n) / len(last_n)

        all_close = all(
            math.hypot(c[0] - cx, c[1] - cy) <= CLICK_RADIUS
            for c in last_n
        )
        return 0.35 if all_close else 0.0

    def _check_rapid_clicks(self) -> float:
        """Panic clicking — many fast clicks in a short burst → weight 0.20"""
        recent = self._recent_clicks(window=RAPID_CLICK_WINDOW)
        return 0.20 if len(recent) >= RAPID_CLICK_COUNT else 0.0

    def _check_repeated_urgency(self) -> float:
        """Gemini keeps saying high urgency → weight 0.20"""
        recent = self._recent_urgencies()
        if len(recent) < CONFUSION_THRESHOLD:
            return 0.0
        last_n = recent[-CONFUSION_THRESHOLD:]
        return 0.20 if all(u == "high" for u in last_n) else 0.0

    def _check_screen_stagnation(self) -> float:
        """Same guidance repeated (user hasn't progressed) → weight 0.15"""
        recent = self._recent_guidances()
        if len(recent) < CONFUSION_THRESHOLD:
            return 0.0
        last_n = recent[-CONFUSION_THRESHOLD:]
        return 0.15 if len(set(last_n)) == 1 else 0.0

    def _check_inactivity(self) -> float:
        """No clicks for a long time (user might be frozen) → weight 0.10"""
        elapsed = time.time() - self.last_click_time
        return 0.10 if elapsed > INACTIVITY_TIMEOUT else 0.0

    # ─── Main evaluation ─────────────────────────────────────────────────

    def evaluate(self) -> Dict:
        """
        Run all confusion checks. Returns dict with:
          is_confused, score, reason, prompt_modifier
        """
        checks = {
            "repeated_clicks":  self._check_repeated_clicks(),
            "rapid_clicks":     self._check_rapid_clicks(),
            "high_urgency":     self._check_repeated_urgency(),
            "screen_stagnation": self._check_screen_stagnation(),
            "inactivity":       self._check_inactivity(),
        }

        score = min(sum(checks.values()), 1.0)
        triggered = [k for k, v in checks.items() if v > 0]

        self.confusion_score = score
        self.is_confused = score >= 0.20
        self.confusion_reason = ", ".join(triggered) if triggered else "none"

        # Track how many consecutive cycles showed confusion
        if self.is_confused:
            self.consecutive_confused_cycles += 1
        else:
            self.consecutive_confused_cycles = 0

        prompt_modifier = ""
        if self.is_confused:
            prompt_modifier = self._build_prompt_modifier(triggered)
            logger.info(
                "⚠️  Confusion detected | score=%.2f | reasons=%s | streak=%d",
                score, self.confusion_reason, self.consecutive_confused_cycles
            )

        return {
            "is_confused": self.is_confused,
            "score": round(self.confusion_score, 2),
            "reason": self.confusion_reason,
            "streak": self.consecutive_confused_cycles,
            "prompt_modifier": prompt_modifier
        }

    # ─── Dynamic prompt modifier ─────────────────────────────────────────

    def _build_prompt_modifier(self, reasons: List[str]) -> str:
        """Build extra prompt context for Gemini when user seems confused."""
        parts = [
            "\n⚠️ CONFUSION ALERT — The user appears to be struggling. Adjust your response:"
        ]

        if "repeated_clicks" in reasons:
            parts.append(
                "• They tapped the SAME spot multiple times. They can't find the right button. "
                "Describe the EXACT visual target using color, shape, and screen position (top/bottom/left/right)."
            )

        if "rapid_clicks" in reasons:
            parts.append(
                "• They are clicking very rapidly — this signals frustration or panic. "
                "Start your response with something calming like 'It's okay, let's slow down together.'"
            )

        if "high_urgency" in reasons:
            parts.append(
                "• You have flagged high urgency multiple times in a row. "
                "The user has not recovered. Offer a DIFFERENT, simpler instruction than before."
            )

        if "screen_stagnation" in reasons:
            parts.append(
                "• The screen hasn't changed — your previous guidance didn't work. "
                "Try a completely different approach. Describe the physical action step-by-step."
            )

        if "inactivity" in reasons:
            parts.append(
                "• The user has stopped interacting entirely. They may be frozen or confused. "
                "Gently ask if they need help: 'Are you still there? I'm here whenever you're ready.'"
            )

        # Escalation — if confused for many cycles, get even more direct
        if self.consecutive_confused_cycles >= 5:
            parts.append(
                "🚨 EXTENDED CONFUSION: The user has been stuck for over 5 cycles. "
                "Give the MOST direct, single-action instruction possible. "
                "Example: 'Put your finger on the big green circle at the very bottom of the screen.'"
            )

        parts.append(
            "Use an EXTRA warm, grandchild-like tone. Keep guidance under 15 words."
        )

        return "\n".join(parts)

    # ─── Status for API ──────────────────────────────────────────────────

    def get_status(self) -> Dict:
        """Return confusion status for API responses."""
        return {
            "is_confused": self.is_confused,
            "score": round(self.confusion_score, 2),
            "reason": self.confusion_reason,
            "streak": self.consecutive_confused_cycles
        }

    def reset(self):
        """Manually reset confusion state (e.g. when user says they're okay)."""
        self.click_history.clear()
        self.urgency_history.clear()
        self.guidance_history.clear()
        self.is_confused = False
        self.confusion_score = 0.0
        self.confusion_reason = "none"
        self.consecutive_confused_cycles = 0
        self.last_click_time = time.time()
