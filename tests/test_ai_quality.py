"""
LegacyBridge — AI Response Quality Tests
------------------------------------------
Validates that Gemini responses meet the quality bar required for elderly users:
  1. JSON schema compliance (all required fields present and typed correctly)
  2. Language rule compliance (no banned jargon)
  3. Guidance length (max 15 words spoken aloud)
  4. Urgency validity (only "low", "medium", "high")
  5. Confidence in valid range (0.0 - 1.0)
  6. Anti-repetition (two identical screens don't get identical guidance twice)

Usage:
  python tests/test_ai_quality.py
"""

import io
import sys
import time
import requests
import statistics
from PIL import Image, ImageDraw

BACKEND_URL = "http://localhost:8000"
TIMEOUT = 20

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✅ {msg}{RESET}")
def fail(msg):  print(f"  {RED}❌ {msg}{RESET}")
def warn(msg):  print(f"  {YELLOW}⚠️  {msg}{RESET}")
def header(msg):print(f"\n{BOLD}{'='*55}\n  {msg}\n{'='*55}{RESET}")

# ─── Banned jargon that Aria must NEVER say ───────────────────────────────────
BANNED_WORDS = [
    "app", "icon", "click", "swipe", "scroll", "menu",
    "settings", "toggle", "url", "browser", "widget",
    "button", "checkbox", "dropdown", "navigate", "interface"
]

def make_image(label: str = "test screen") -> bytes:
    img = Image.new("RGB", (1280, 720), (40, 40, 40))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 600, 120], fill=(255, 255, 255))
    draw.rectangle([50, 200, 300, 250], fill=(0, 200, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    buf.seek(0)
    return buf.read()

def send(shot: bytes) -> dict:
    files = {"file": ("screen.jpg", io.BytesIO(shot), "image/jpeg")}
    resp = requests.post(f"{BACKEND_URL}/process-screen", files=files, timeout=TIMEOUT)
    return resp.json()

# ─── Tests ────────────────────────────────────────────────────────────────────

def test_schema_validation():
    header("TEST 1 — JSON Schema Validation")
    shot = make_image()
    result = send(shot)

    if result.get("status") != "success":
        fail(f"Request failed: {result.get('message')}")
        return False

    data = result["data"]
    passed = True

    # Required fields
    required = {"guidance": str, "urgency": str, "confidence": float}
    for field, ftype in required.items():
        if field not in data:
            fail(f"Missing required field: '{field}'")
            passed = False
        elif not isinstance(data[field], (ftype, int)):  # int is also valid for float fields
            fail(f"'{field}' has wrong type: expected {ftype.__name__}, got {type(data[field]).__name__}")
            passed = False
        else:
            ok(f"'{field}' present and typed correctly ({type(data[field]).__name__})")

    # Optional but expected
    if "screen_context" in data:
        ok(f"'screen_context' present: \"{data['screen_context']}\"")
    else:
        warn("'screen_context' missing (optional but good to have)")

    return passed


def test_language_rules():
    header("TEST 2 — Language Rule Compliance (No Jargon)")
    shot = make_image()
    violations = []
    guidance_samples = []

    for i in range(3):
        result = send(shot)
        if result.get("status") == "success":
            g = result["data"]["guidance"].lower()
            guidance_samples.append(result["data"]["guidance"])
            for word in BANNED_WORDS:
                if word in g:
                    violations.append((result["data"]["guidance"], word))

    if not violations:
        ok(f"No banned words found in {len(guidance_samples)} responses ✓")
        for g in guidance_samples:
            ok(f"Sample: \"{g}\"")
    else:
        for guidance, word in violations:
            fail(f"Banned word '{word}' found in: \"{guidance}\"")

    return len(violations) == 0


def test_guidance_length():
    header("TEST 3 — Guidance Length (Max 15 Words)")
    shot = make_image()
    passed = True

    for i in range(3):
        result = send(shot)
        if result.get("status") == "success":
            g = result["data"]["guidance"]
            word_count = len(g.split())
            if word_count <= 15:
                ok(f"{word_count} words: \"{g}\"")
            else:
                fail(f"{word_count} words (exceeds 15): \"{g}\"")
                passed = False

    return passed


def test_urgency_validity():
    header("TEST 4 — Urgency Value Validity")
    valid_urgencies = {"low", "medium", "high"}
    shot = make_image()
    passed = True

    for i in range(3):
        result = send(shot)
        if result.get("status") == "success":
            urgency = result["data"]["urgency"]
            if urgency in valid_urgencies:
                ok(f"urgency='{urgency}' ✓")
            else:
                fail(f"Invalid urgency value: '{urgency}' (must be low/medium/high)")
                passed = False

    return passed


def test_confidence_range():
    header("TEST 5 — Confidence Score Range (0.0 - 1.0)")
    shot = make_image()
    passed = True

    for i in range(3):
        result = send(shot)
        if result.get("status") == "success":
            conf = result["data"]["confidence"]
            if 0.0 <= conf <= 1.0:
                ok(f"confidence={conf} ✓")
            else:
                fail(f"confidence={conf} out of range [0.0, 1.0]")
                passed = False

    return passed


def test_anti_repetition():
    header("TEST 6 — Anti-Repetition (Guidance Must Vary Over Time)")
    shot = make_image()
    guidances = []

    for i in range(4):
        result = send(shot)
        if result.get("status") == "success":
            guidances.append(result["data"]["guidance"])

    unique = set(guidances)
    if len(unique) >= 2:
        ok(f"{len(unique)}/{len(guidances)} unique guidances — anti-repetition working ✓")
    elif len(unique) == 1:
        warn(f"All {len(guidances)} responses were identical: \"{list(unique)[0]}\"")
        warn("Anti-repetition may not be working correctly")
    else:
        warn("Not enough samples to evaluate anti-repetition")

    for g in guidances:
        print(f"    → \"{g}\"")

    return len(unique) >= 2


def test_confusion_prompt_modification():
    header("TEST 7 — Confusion Mode Prompt Modification")

    # Simulate panic clicking in the same spot
    for i in range(5):
        requests.post(f"{BACKEND_URL}/report-click", json={"x": 150, "y": 300}, timeout=3)
        time.sleep(0.1)

    status = requests.get(f"{BACKEND_URL}/confusion-status", timeout=3).json()
    c = status.get("confusion", {})

    if c.get("is_confused"):
        ok(f"Confusion state active ✓ | score={c['score']} | reason={c['reason']}")
        # Now send a screenshot — guidance should be more empathetic
        result = send(make_image())
        if result.get("status") == "success":
            g = result["data"]["guidance"]
            ok(f"Confused-mode guidance: \"{g}\"")
    else:
        warn(f"Confusion not triggered (score={c.get('score', 0)}) — threshold may need adjustment")

    # Reset confusion state
    requests.post(f"{BACKEND_URL}/reset-confusion", timeout=3)
    ok("Confusion state reset ✓")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{BOLD}🤖 LegacyBridge AI Quality Test Suite{RESET}")
    print(f"   Target: {BACKEND_URL}")

    # Verify server is up
    try:
        resp = requests.get(BACKEND_URL, timeout=5)
        if resp.status_code != 200:
            print(f"{RED}Server not responding. Start it first.{RESET}")
            sys.exit(1)
    except:
        print(f"{RED}Cannot connect to {BACKEND_URL}. Start the server first.{RESET}")
        sys.exit(1)

    results = {
        "Schema"         : test_schema_validation(),
        "Language Rules" : test_language_rules(),
        "Guidance Length": test_guidance_length(),
        "Urgency"        : test_urgency_validity(),
        "Confidence"     : test_confidence_range(),
        "Anti-Repetition": test_anti_repetition(),
    }
    test_confusion_prompt_modification()

    header("QUALITY TEST SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total  = len(results)
    for name, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {status}  {name}")

    print(f"\n  {BOLD}{passed}/{total} quality gates passed{RESET}\n")

if __name__ == "__main__":
    main()
