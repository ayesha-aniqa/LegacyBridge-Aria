import requests
import io
from PIL import ImageGrab

BACKEND_URL = "http://localhost:8000"

def test_health():
    """Test 1: Check if the server is running and Aria is online."""
    print("=" * 50)
    print("TEST 1: Health Check (GET /)")
    print("=" * 50)
    try:
        response = requests.get(f"{BACKEND_URL}/")
        print(f"  Status Code : {response.status_code}")
        print(f"  Response    : {response.json()}")
        if response.status_code == 200 and response.json().get("status") == "Aria is online":
            print("  ✅ PASSED — Server is running!\n")
            return True
        else:
            print("  ❌ FAILED — Unexpected response.\n")
            return False
    except requests.ConnectionError:
        print("  ❌ FAILED — Could not connect. Is the server running on port 8000?\n")
        return False

def test_process_screen():
    """Test 2: Capture current screen, send to /process-screen, and display Aria's guidance."""
    print("=" * 50)
    print("TEST 2: Process Screen (POST /process-screen)")
    print("=" * 50)
    try:
        # Capture a screenshot of the current screen
        print("  📸 Capturing screenshot...")
        screenshot = ImageGrab.grab()

        # Convert screenshot to JPEG bytes for upload
        buffer = io.BytesIO()
        screenshot.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)

        # Send screenshot to the backend
        print("  📤 Sending screenshot to backend...")
        files = {"file": ("screenshot.jpg", buffer, "image/jpeg")}
        response = requests.post(f"{BACKEND_URL}/process-screen", files=files)

        print(f"  Status Code : {response.status_code}")
        data = response.json()

        if data.get("status") == "success":
            aria = data["data"]
            print(f"  🗣️  Guidance   : {aria['guidance']}")
            print(f"  ⚡ Urgency    : {aria['urgency']}")
            print(f"  👆 Action Hint: {aria.get('action_hint', 'N/A')}")
            print(f"  🎯 Confidence : {aria['confidence']}")
            print("  ✅ PASSED — Gemini Vision pipeline is working!\n")
            return True
        else:
            print(f"  ❌ FAILED — {data.get('message', 'Unknown error')}")
            if "raw" in data:
                print(f"  Raw response: {data['raw'][:200]}")
            print()
            return False

    except requests.ConnectionError:
        print("  ❌ FAILED — Could not connect. Is the server running on port 8000?\n")
        return False
    except Exception as e:
        print(f"  ❌ FAILED — {e}\n")
        return False

if __name__ == "__main__":
    print("\n🔬 LegacyBridge Backend Test Suite\n")

    health_ok = test_health()

    if health_ok:
        test_process_screen()
    else:
        print("⚠️  Skipping Test 2 — server is not reachable.")

    print("=" * 50)
    print("Done!")
