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

        # (phash, timestamp)
        self.phash_history: deque = deque(maxlen=15)

        # List of (x, y, timestamp) points received in batches
        self.movement_history: deque = deque(maxlen=1000)

        # Timestamp of last recorded user interaction (click or move)
        self.last_interaction_time: float = time.time()

        # Running state
        self.is_confused: bool = False
        self.confusion_score: float = 0.0
        self.confusion_reason: str = "none"
        self.consecutive_confused_cycles: int = 0

    # ─── Recording methods (called from endpoints) ───────────────────────

    def record_click(self, x: int, y: int):
        """Record a mouse click from the client."""
        now = time.time()
        self.click_history.append((x, y, now))
        self.last_interaction_time = now

    def record_movement(self, points: List[Tuple[int, int, float]]):
        """Record a batch of mouse movement points."""
        if not points:
            return
        now = time.time()
        for p in points:
            # points are (x, y, timestamp)
            self.movement_history.append(p)
        self.last_interaction_time = max(self.last_interaction_time, points[-1][2])

    def record_phash(self, phash: str):
        """Record the perceptual hash of the current screen."""
        self.phash_history.append((phash, time.time()))

    def record_response(self, guidance: str, urgency: str):
        """Record a Gemini response for pattern tracking."""
        now = time.time()
        self.urgency_history.append((urgency, now))
        self.guidance_history.append((guidance.strip().lower(), now))

    # ─── Windowed helpers ─────────────────────────────────────────────────

    def _recent_clicks(self, window: float = None) -> List[Tuple[int, int, float]]:
        cutoff = time.time() - (window or TIME_WINDOW)
        return [(x, y, t) for x, y, t in self.click_history if t > cutoff]

    def _recent_movements(self, window: float = None) -> List[Tuple[int, int, float]]:
        cutoff = time.time() - (window or TIME_WINDOW)
        return [(x, y, t) for x, y, t in self.movement_history if t > cutoff]

    def _recent_urgencies(self) -> List[str]:
        cutoff = time.time() - TIME_WINDOW
        return [u for u, t in self.urgency_history if t > cutoff]

    def _recent_phashes(self) -> List[str]:
        cutoff = time.time() - TIME_WINDOW
        return [p for p, t in self.phash_history if t > cutoff]

    # ─── Detection checks ────────────────────────────────────────────────

    def _check_vision_urgency(self) -> float:
        """Gemini flags HIGH urgency → weight 0.40"""
        recent = self._recent_urgencies()
        if not recent:
            return 0.0
        # If last N are high, or majority are high
        last_n = recent[-3:]
        high_count = sum(1 for u in last_n if u == "high")
        return (high_count / len(last_n)) * 0.40

    def _check_screen_stagnation(self) -> float:
        """Same phash for 3+ cycles → weight 0.25"""
        recent = self._recent_phashes()
        if len(recent) < 3:
            return 0.0
        last_3 = recent[-3:]
        # Use a small threshold for phash similarity if needed, but GEMINI.md says "same phash"
        # We'll use exact match for now as backend already filters near-duplicates
        if len(set(last_3)) == 1:
            return 0.25
        return 0.0

    def _check_mouse_drift(self) -> float:
        """Erratic cursor movement without clicks → weight 0.20"""
        recent_moves = self._recent_movements(window=10) # Look at last 10s
        recent_clicks = self._recent_clicks(window=10)

        if len(recent_moves) < 10 or len(recent_clicks) > 2:
            return 0.0

        # Calculate distances between consecutive points
        distances = []
        for i in range(1, len(recent_moves)):
            p1 = recent_moves[i-1]
            p2 = recent_moves[i]
            d = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            distances.append(d)

        if not distances:
            return 0.0

        avg_dist = sum(distances) / len(distances)
        variance = sum((d - avg_dist) ** 2 for d in distances) / len(distances)

        # If movement is significant but erratic (high variance)
        if avg_dist > 5 and variance > 50:
            return 0.20
        return 0.0

    def _check_inactivity(self) -> float:
        """No interaction (click/move) for 15+ seconds → weight 0.10"""
        elapsed = time.time() - self.last_interaction_time
        return 0.10 if elapsed > 15 else 0.0

    def _check_rapid_clicks(self) -> float:
        """Panic clicking — weight 0.05"""
        recent = self._recent_clicks(window=RAPID_CLICK_WINDOW)
        return 0.05 if len(recent) >= RAPID_CLICK_COUNT else 0.0

    # ─── Main evaluation ─────────────────────────────────────────────────

    def evaluate(self) -> Dict:
        """
        Run all confusion checks. Returns dict with:
          is_confused, score, reason, prompt_modifier
        """
        checks = {
            "vision_urgency":    self._check_vision_urgency(),
            "screen_stagnation": self._check_screen_stagnation(),
            "mouse_drift":       self._check_mouse_drift(),
            "inactivity":        self._check_inactivity(),
            "rapid_clicks":      self._check_rapid_clicks(),
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

        if "vision_urgency" in reasons:
            parts.append(
                "• You have flagged high urgency multiple times. The user is stuck. "
                "Offer a DIFFERENT, simpler instruction than before."
            )

        if "screen_stagnation" in reasons:
            parts.append(
                "• The screen hasn't changed despite your guidance. "
                "Try a completely different approach. Describe physical landmarks (color, shape)."
            )

        if "mouse_drift" in reasons:
            parts.append(
                "• The user is moving the mouse erratically but not clicking. They are searching. "
                "Gently point them to the correct area: 'Look towards the [position] for the [color] [shape].'"
            )

        if "rapid_clicks" in reasons:
            parts.append(
                "• They are clicking very rapidly — this signals frustration. "
                "Start with something calming: 'It's okay, let's take a breath and try one simple thing.'"
            )

        if "inactivity" in reasons:
            parts.append(
                "• The user has stopped interacting. They may be overwhelmed. "
                "Gently re-engage: 'Are you still there? I'm here to help whenever you're ready.'"
            )

        # Escalation
        if self.consecutive_confused_cycles >= 5:
            parts.append(
                "🚨 CRITICAL: User stuck for a long time. Suggest a break or offer to call family."
            )

        parts.append(
            "Use an EXTRA warm tone. Keep guidance under 15 words."
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
        self.phash_history.clear()
        self.movement_history.clear()
        self.is_confused = False
        self.confusion_score = 0.0
        self.confusion_reason = "none"
        self.consecutive_confused_cycles = 0
        self.last_interaction_time = time.time()
