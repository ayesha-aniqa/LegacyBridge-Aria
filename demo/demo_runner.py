"""
LegacyBridge Demo Runner
--------------------------
Orchestrates a scripted demo by feeding mock screens to the backend in sequence,
simulating confusion clicks at cue points, and displaying a live console output.

This lets you record the YouTube demo video with full control over what Aria sees,
without needing to actually use an elderly person's phone in real time.

Usage:
  # Step 1: Generate mock screens (only needed once)
  python demo/mock_screen_generator.py

  # Step 2: Start the backend in another terminal
  $env:GOOGLE_APPLICATION_CREDENTIALS="C:\\Users\\User\\Downloads\\key.json"
  cd server && uvicorn app.main:app --reload

  # Step 3: Run the demo
  python demo/demo_runner.py

  # Optional: run a specific scenario by number (0-indexed)
  python demo/demo_runner.py --scenario 2
"""

import os
import sys
import io
import time
import argparse
import requests
import threading

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from demo.scenarios import DEMO_SCENARIOS

BACKEND_URL = "http://localhost:8000"
TIMEOUT = 20

# ─── Console colors ───────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
MAGENTA= "\033[95m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
CLEAR  = "\033[2J\033[H"


def banner():
    print(f"""
{BOLD}{CYAN}
╔══════════════════════════════════════════════════════════╗
║         LegacyBridge — DEMO RUNNER  🎬                  ║
║   Aria AI Screen Assistant for Elderly Users             ║
╚══════════════════════════════════════════════════════════╝
{RESET}""")


def check_backend():
    """Verify the backend is running before starting."""
    try:
        resp = requests.get(BACKEND_URL, timeout=5)
        data = resp.json()
        print(f"  {GREEN}✅ Backend online — {data.get('status')}{RESET}")
        return True
    except Exception as e:
        print(f"  {RED}❌ Backend not responding at {BACKEND_URL}{RESET}")
        print(f"     Start it with: cd server && uvicorn app.main:app --reload")
        return False


def send_mock_screen(screen_path: str) -> dict:
    """Send a mock screenshot file to the backend."""
    with open(screen_path, "rb") as f:
        files = {"file": ("screen.jpg", f, "image/jpeg")}
        resp = requests.post(f"{BACKEND_URL}/process-screen", files=files, timeout=TIMEOUT)
    return resp.json()


def simulate_clicks(click_coords: list, delay: float = 0.3):
    """Send simulated click events to the backend for confusion detection."""
    for x, y in click_coords:
        try:
            requests.post(
                f"{BACKEND_URL}/report-click",
                json={"x": x, "y": y},
                timeout=3
            )
            time.sleep(delay)
        except Exception:
            pass


def run_scenario(scenario: dict, index: int, total: int):
    """Execute a single demo scenario."""
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  SCENARIO {index + 1}/{total}: {scenario['name']}{RESET}")
    print(f"{'─'*60}{RESET}")
    print(f"\n  {YELLOW}📖 {scenario['description']}{RESET}\n")

    # Check the screen file exists
    if not os.path.exists(scenario["screen_file"]):
        print(f"  {RED}❌ Screen file not found: {scenario['screen_file']}{RESET}")
        print(f"     Run: python demo/mock_screen_generator.py")
        return

    # Reset confusion state at the start of each scenario
    try:
        requests.post(f"{BACKEND_URL}/reset-confusion", timeout=3)
    except Exception:
        pass

    # Simulate any clicks BEFORE sending the screen (triggers confusion)
    if scenario["simulate_clicks"]:
        print(f"  {MAGENTA}🖱️  Simulating {len(scenario['simulate_clicks'])} confusion clicks...{RESET}")
        click_thread = threading.Thread(
            target=simulate_clicks,
            args=(scenario["simulate_clicks"],)
        )
        click_thread.start()
        click_thread.join()

    # Send the mock screen to the backend
    print(f"  {CYAN}📸 Sending screen to Aria...{RESET}")
    t0 = time.perf_counter()
    result = send_mock_screen(scenario["screen_file"])
    elapsed = (time.perf_counter() - t0) * 1000

    if result.get("status") == "success":
        data = result["data"]
        confusion = result.get("confusion", {})
        cache_hit = result.get("cache_hit", False)

        print(f"\n  {GREEN}{'─'*50}{RESET}")
        print(f"  {BOLD}🗣️  Aria says:{RESET}")
        print(f"  {BOLD}{GREEN}  \"{data['guidance']}\"{RESET}")
        print(f"\n  📊 Details:")
        print(f"     Urgency      : {_urgency_color(data['urgency'])}")
        print(f"     Action Hint  : {data.get('action_hint') or 'None'}")
        print(f"     Screen       : {data.get('screen_context') or 'unknown'}")
        print(f"     Confidence   : {data.get('confidence', 0):.0%}")
        print(f"     Response time: {elapsed:.0f}ms {'⚡ (cached)' if cache_hit else ''}")

        if confusion.get("is_confused"):
            print(f"\n  {RED}⚠️  CONFUSION DETECTED{RESET}")
            print(f"     Score  : {confusion['score']:.0%}")
            print(f"     Reason : {confusion['reason']}")
            print(f"     Streak : {confusion['streak']} cycle(s)")

    else:
        print(f"  {RED}❌ Error: {result.get('message')}{RESET}")

    print(f"\n  {YELLOW}⏳ Holding for {scenario['hold']}s before next scenario...{RESET}")
    time.sleep(scenario["hold"])


def _urgency_color(urgency: str) -> str:
    colors = {"high": RED, "medium": YELLOW, "low": GREEN}
    return f"{colors.get(urgency, RESET)}{urgency.upper()}{RESET}"


def run_all_scenarios():
    """Run all demo scenarios in sequence."""
    banner()
    print(f"\n  Checking backend...")
    if not check_backend():
        sys.exit(1)

    total = len(DEMO_SCENARIOS)
    print(f"\n  {BOLD}▶  Starting demo — {total} scenarios{RESET}")
    print(f"  {YELLOW}Press Ctrl+C at any time to stop.{RESET}\n")
    time.sleep(2)

    for i, scenario in enumerate(DEMO_SCENARIOS):
        run_scenario(scenario, i, total)

    print(f"\n{BOLD}{GREEN}{'═'*60}{RESET}")
    print(f"{BOLD}{GREEN}  ✅  Demo complete! All {total} scenarios ran successfully.{RESET}")
    print(f"{BOLD}{GREEN}{'═'*60}{RESET}\n")


def run_single_scenario(index: int):
    """Run a single scenario by index."""
    banner()
    if not check_backend():
        sys.exit(1)
    if index < 0 or index >= len(DEMO_SCENARIOS):
        print(f"{RED}Invalid scenario index {index}. Valid range: 0–{len(DEMO_SCENARIOS)-1}{RESET}")
        for i, s in enumerate(DEMO_SCENARIOS):
            print(f"  [{i}] {s['name']}")
        sys.exit(1)
    run_scenario(DEMO_SCENARIOS[index], index, len(DEMO_SCENARIOS))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LegacyBridge Demo Runner")
    parser.add_argument("--scenario", type=int, default=-1,
                        help="Run a specific scenario by index (0-based). Default: run all.")
    parser.add_argument("--url", default=BACKEND_URL,
                        help="Backend URL (default: http://localhost:8000)")
    parser.add_argument("--list", action="store_true",
                        help="List all available scenarios and exit.")
    args = parser.parse_args()

    BACKEND_URL = args.url.rstrip("/")

    if args.list:
        banner()
        print(f"{BOLD}Available Demo Scenarios:{RESET}\n")
        for i, s in enumerate(DEMO_SCENARIOS):
            print(f"  [{i}] {s['name']}")
            print(f"       {YELLOW}{s['description'][:70]}...{RESET}\n")
        sys.exit(0)

    try:
        if args.scenario >= 0:
            run_single_scenario(args.scenario)
        else:
            run_all_scenarios()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}  Demo stopped by user.{RESET}\n")
