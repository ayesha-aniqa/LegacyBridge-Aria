"""
LegacyBridge — Performance Benchmark Suite
--------------------------------------------
Tests backend endpoint speed across real scenarios:
  1. Single request latency (cold start)
  2. Cache hit latency (same screenshot twice)
  3. Throughput — sequential requests over N seconds
  4. Image hashing speed
  5. Confusion detection overhead
  6. Stress test — rapid fire requests

Usage:
  # Start backend first:
  $env:GOOGLE_APPLICATION_CREDENTIALS="C:\\Users\\User\\Downloads\\key.json"
  cd server && uvicorn app.main:app --reload

  # Then run this script:
  python tests/test_performance.py
  python tests/test_performance.py --url http://localhost:8000 --rounds 10
"""

import time
import io
import sys
import json
import argparse
import requests
import statistics
from PIL import ImageGrab, Image, ImageDraw

# ─── Config ──────────────────────────────────────────────────────────────────
DEFAULT_URL = "http://localhost:8000"
TIMEOUT = 20  # seconds per request

# ─── ANSI colors ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✅ {msg}{RESET}")
def fail(msg):  print(f"  {RED}❌ {msg}{RESET}")
def warn(msg):  print(f"  {YELLOW}⚠️  {msg}{RESET}")
def info(msg):  print(f"  {CYAN}ℹ️  {msg}{RESET}")
def header(msg):print(f"\n{BOLD}{'='*55}\n  {msg}\n{'='*55}{RESET}")

# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_test_screenshot(width=1280, height=720, color=(30, 30, 30)) -> bytes:
    """Create a synthetic screenshot instead of capturing a real one (for speed)."""
    img = Image.new("RGB", (width, height), color)
    draw = ImageDraw.Draw(img)
    # Add some simple UI-like elements
    draw.rectangle([50, 50, 400, 100], fill=(255, 255, 255))
    draw.rectangle([50, 150, 300, 180], fill=(0, 150, 100))
    draw.ellipse([600, 300, 700, 400], fill=(255, 200, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    buf.seek(0)
    return buf.read()

def make_slightly_different_screenshot() -> bytes:
    """Slightly different screenshot (simulates small screen change)."""
    import random
    color = (random.randint(20, 40), random.randint(20, 40), random.randint(20, 40))
    return make_test_screenshot(color=color)

def post_screenshot(url: str, screenshot_bytes: bytes) -> dict:
    """POST a screenshot to /process-screen and return the JSON result."""
    files = {"file": ("screen.jpg", io.BytesIO(screenshot_bytes), "image/jpeg")}
    t0 = time.perf_counter()
    resp = requests.post(f"{url}/process-screen", files=files, timeout=TIMEOUT)
    elapsed = (time.perf_counter() - t0) * 1000
    result = resp.json()
    result["_client_ms"] = round(elapsed, 1)
    return result

def get_health(url: str) -> dict:
    return requests.get(f"{url}/health", timeout=5).json()

# ─── Tests ───────────────────────────────────────────────────────────────────

def test_health_check(url: str) -> bool:
    header("TEST 1 — Health Check")
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if resp.status_code == 200 and "Aria" in data.get("status", ""):
            ok(f"Server is online — {data['status']}")
            ok(f"Version: {data.get('version', 'unknown')}")
            return True
        else:
            fail(f"Unexpected response: {data}")
            return False
    except requests.ConnectionError:
        fail("Cannot connect — is the server running?")
        return False


def test_cold_start_latency(url: str) -> float:
    """Single request with a fresh screenshot (no cache)."""
    header("TEST 2 — Cold Start Latency (Gemini API Call)")
    shot = make_test_screenshot()

    # Clear confusion state first
    requests.post(f"{url}/reset-confusion", timeout=5)

    result = post_screenshot(url, shot)
    ms = result["_client_ms"]

    if result.get("status") == "success":
        gemini_ms = result.get("gemini_ms", "N/A")
        cache_hit = result.get("cache_hit", False)
        ok(f"Response received in {ms:.0f}ms (Gemini: {gemini_ms}ms | cache_hit: {cache_hit})")
        ok(f"Guidance: \"{result['data']['guidance']}\"")
        if ms < 5000:
            ok("Latency is under 5 seconds ✓")
        elif ms < 10000:
            warn(f"Latency {ms:.0f}ms is acceptable but could be improved")
        else:
            fail(f"Latency {ms:.0f}ms is too slow for real-time use")
    else:
        fail(f"Request failed: {result.get('message')}")
        ms = 99999

    return ms


def test_cache_hit_latency(url: str) -> float:
    """Send the SAME screenshot twice — second should be served from cache."""
    header("TEST 3 — Cache Hit Latency (Same Screen)")
    shot = make_test_screenshot()  # Same bytes = same hash

    # First request (cache miss)
    info("Sending first request (cache miss expected)...")
    r1 = post_screenshot(url, shot)
    ms1 = r1["_client_ms"]

    # Second request (cache hit expected)
    info("Sending identical screenshot (cache hit expected)...")
    r2 = post_screenshot(url, shot)
    ms2 = r2["_client_ms"]

    if r2.get("cache_hit"):
        ok(f"Cache hit confirmed ✓ | First: {ms1:.0f}ms → Second: {ms2:.0f}ms")
        speedup = ms1 / ms2 if ms2 > 0 else 0
        ok(f"Speedup: {speedup:.1f}x faster on cache hit")
    else:
        warn(f"Cache miss on second request (may be expected if TTL expired). ms={ms2:.0f}")

    return ms2


def test_throughput(url: str, duration_seconds: int = 10) -> dict:
    """How many requests can the server handle per second (sequential)?"""
    header(f"TEST 4 — Sequential Throughput ({duration_seconds}s)")
    shots = [make_test_screenshot(), make_slightly_different_screenshot()]
    latencies = []
    cache_hits = 0
    errors = 0

    info(f"Sending requests for {duration_seconds} seconds...")
    t_end = time.time() + duration_seconds
    i = 0
    while time.time() < t_end:
        shot = shots[i % 2]  # Alternate between 2 screenshots
        try:
            result = post_screenshot(url, shot)
            if result.get("status") == "success":
                latencies.append(result["_client_ms"])
                if result.get("cache_hit"):
                    cache_hits += 1
            else:
                errors += 1
        except Exception as e:
            errors += 1
        i += 1

    total = len(latencies) + errors
    rps = total / duration_seconds

    if latencies:
        ok(f"Completed {total} requests in {duration_seconds}s ({rps:.1f} req/s)")
        ok(f"Latency   — min: {min(latencies):.0f}ms | median: {statistics.median(latencies):.0f}ms | max: {max(latencies):.0f}ms")
        ok(f"Cache hits: {cache_hits}/{total} ({cache_hits/total*100:.0f}%)")
        if errors:
            warn(f"{errors} errors occurred")
    else:
        fail("No successful requests completed")

    return {"total": total, "rps": rps, "latencies": latencies, "errors": errors, "cache_hits": cache_hits}


def test_image_hashing_speed() -> None:
    """Benchmark image hashing locally — this should be < 5ms."""
    header("TEST 5 — Image Hashing Speed (Local)")
    from server.app.image_utils import _compute_phash, hamming_distance
    import asyncio, sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    try:
        from app.image_utils import _compute_phash, hamming_distance
        shots = [Image.open(io.BytesIO(make_test_screenshot())) for _ in range(10)]

        times = []
        for img in shots:
            t0 = time.perf_counter()
            h = _compute_phash(img)
            times.append((time.perf_counter() - t0) * 1000)

        avg_ms = statistics.mean(times)
        ok(f"Average hash time: {avg_ms:.2f}ms (min: {min(times):.2f}, max: {max(times):.2f})")
        if avg_ms < 5:
            ok("Hashing is fast enough for real-time use ✓")
        else:
            warn(f"Hashing is slow at {avg_ms:.2f}ms — may impact throughput")
    except ImportError as e:
        warn(f"Skipping local hash test (not running from server dir): {e}")


def test_confusion_detection_overhead(url: str) -> None:
    """Simulate rapid clicks and measure API overhead."""
    header("TEST 6 — Confusion Detection Overhead")
    click_times = []
    for i in range(10):
        t0 = time.perf_counter()
        requests.post(f"{url}/report-click", json={"x": 100+i, "y": 200}, timeout=3)
        click_times.append((time.perf_counter() - t0) * 1000)

    avg = statistics.mean(click_times)
    ok(f"/report-click avg latency: {avg:.1f}ms (10 rapid clicks)")

    # Check confusion was actually detected
    status = requests.get(f"{url}/confusion-status", timeout=3).json()
    c = status.get("confusion", {})
    if c.get("is_confused"):
        ok(f"Confusion detected correctly ✓ | score={c['score']} | reason={c['reason']}")
    else:
        info(f"Confusion not triggered (score={c.get('score', 0)}) — may need more clicks in same area")


def test_server_metrics(url: str) -> None:
    """Pull the /health endpoint and display all performance metrics."""
    header("TEST 7 — Server Performance Metrics")
    h = get_health(url)
    stats = h.get("stats", {})
    ok(f"Total requests    : {stats.get('total_requests', 0)}")
    ok(f"Cache hits        : {stats.get('cache_hits', 0)}")
    ok(f"Cache hit rate    : {stats.get('cache_hit_rate_pct', 0)}%")
    ok(f"Gemini API calls  : {stats.get('gemini_calls', 0)}")
    ok(f"Avg response time : {stats.get('avg_response_ms', 0)}ms")
    ok(f"Cache entries now : {h.get('cache_entries', 0)}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LegacyBridge Performance Benchmark")
    parser.add_argument("--url", default=DEFAULT_URL, help="Backend URL")
    parser.add_argument("--rounds", type=int, default=10, help="Throughput test duration (seconds)")
    args = parser.parse_args()

    url = args.url.rstrip("/")
    print(f"\n{BOLD}🔬 LegacyBridge Performance Benchmark{RESET}")
    print(f"   Target: {url}")
    print(f"   Time  : {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # ── Run tests ──────────────────────────────────────────────────────────
    if not test_health_check(url):
        print(f"\n{RED}Server unreachable. Aborting.{RESET}")
        sys.exit(1)

    cold_ms   = test_cold_start_latency(url)
    cache_ms  = test_cache_hit_latency(url)
    throughput = test_throughput(url, duration_seconds=args.rounds)
    test_image_hashing_speed()
    test_confusion_detection_overhead(url)
    test_server_metrics(url)

    # ── Summary report ─────────────────────────────────────────────────────
    header("SUMMARY")
    print(f"  Cold start latency  : {cold_ms:.0f}ms")
    print(f"  Cache hit latency   : {cache_ms:.0f}ms")
    print(f"  Throughput          : {throughput['rps']:.1f} req/s")
    print(f"  Cache hit rate      : {throughput['cache_hits']}/{throughput['total']} "
          f"({throughput['cache_hits']/max(throughput['total'],1)*100:.0f}%)")
    print(f"  Errors              : {throughput['errors']}\n")

    # Pass/Fail assessment
    passed = 0
    if cold_ms < 8000:   passed += 1; ok("Cold start < 8s ✓")
    else:                fail(f"Cold start {cold_ms:.0f}ms > 8s limit")

    if cache_ms < 200:   passed += 1; ok("Cache hit < 200ms ✓")
    else:                warn(f"Cache hit {cache_ms:.0f}ms (expected < 200ms)")

    if throughput['rps'] >= 0.3: passed += 1; ok("Throughput ≥ 0.3 req/s ✓")
    else:                fail(f"Throughput {throughput['rps']:.2f} req/s is too low")

    print(f"\n  {passed}/3 performance gates passed\n")

if __name__ == "__main__":
    main()
