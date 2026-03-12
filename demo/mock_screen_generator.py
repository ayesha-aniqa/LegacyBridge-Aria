"""
Mock Screen Generator for LegacyBridge Demo
---------------------------------------------
Generates realistic-looking synthetic screenshots for each demo scenario.
These are used instead of real screens during demo recording so we can:
  - Control exactly what Aria sees and says
  - Reproduce the demo reliably without relying on a live device
  - Trigger specific confusion/guidance scenarios on cue

Scenarios covered:
  - home_screen         : Android-like home screen (normal, urgency=low)
  - whatsapp_chat_list  : WhatsApp main screen (normal, urgency=low)
  - whatsapp_open_chat  : Inside a chat, user needs to type (urgency=medium)
  - missed_call         : Missed call notification (urgency=medium)
  - stuck_on_settings   : Settings screen, user tapping wrong option (urgency=high)
  - wrong_app_open      : User opened camera instead of WhatsApp (urgency=high)
  - error_popup         : System error dialog (urgency=high)
  - video_call_incoming : Incoming video call ringing (urgency=high)
"""

from PIL import Image, ImageDraw, ImageFont
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "mock_screens")
W, H = 1280, 720

# Color palette
BG_DARK        = (30,  30,  35)
BG_WHITE       = (245, 245, 245)
GREEN_WA       = (37,  211, 102)
GREEN_DARK     = (18,  140, 126)
BLUE_NOTIF     = (66,  133, 244)
RED_ERR        = (220, 50,  50)
ORANGE_WARN    = (255, 160, 0)
GREY           = (120, 120, 120)
WHITE          = (255, 255, 255)
BLACK          = (20,  20,  20)
PURPLE         = (103, 58,  183)


def _save(img: Image.Image, name: str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{name}.jpg")
    img.save(path, "JPEG", quality=90)
    print(f"  ✅ Generated: {name}.jpg")
    return path


def text(draw, xy, txt, size=24, color=WHITE, bold=False):
    """Draw text at position (handles font gracefully)."""
    try:
        font = ImageFont.truetype("arial.ttf", size)
    except:
        font = ImageFont.load_default()
    draw.text(xy, txt, fill=color, font=font)


def _rounded_rect(draw, xy, radius=20, fill=WHITE):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


# ─── Scenario generators ──────────────────────────────────────────────────────

def make_home_screen():
    img = Image.new("RGB", (W, H), (25, 25, 35))
    draw = ImageDraw.Draw(img)
    # Wallpaper gradient simulation
    for y in range(H):
        r = int(25 + (y / H) * 30)
        b = int(60 + (y / H) * 60)
        draw.line([(0, y), (W, y)], fill=(r, 25, b))

    # Status bar
    draw.rectangle([0, 0, W, 30], fill=(0, 0, 0, 180))
    text(draw, (20, 5), "9:41 AM", 16, WHITE)
    text(draw, (W - 120, 5), "📶 🔋 100%", 16, WHITE)

    # App grid — 4x3 icons
    icons = [
        ("📞", "Phone", (0, 150, 136)),
        ("💬", "Messages", GREEN_WA),
        ("📷", "Camera", (100, 100, 100)),
        ("🌐", "Browser", BLUE_NOTIF),
        ("⚙️", "Settings", (120, 120, 120)),
        ("📧", "Email", (234, 67, 53)),
        ("🗓️", "Calendar", BLUE_NOTIF),
        ("🎵", "Music", PURPLE),
    ]
    cols, rows = 4, 2
    icon_w, icon_h = 130, 130
    start_x = (W - cols * icon_w - (cols - 1) * 20) // 2
    start_y = 80

    for i, (emoji, label, color) in enumerate(icons):
        col = i % cols
        row = i // cols
        x = start_x + col * (icon_w + 20)
        y = start_y + row * (icon_h + 40)
        _rounded_rect(draw, [x, y, x + icon_w, y + icon_h], radius=24, fill=color)
        text(draw, (x + 35, y + 30), emoji, 48, WHITE)
        text(draw, (x + 15, y + icon_h + 8), label, 18, WHITE)

    # Bottom nav bar
    draw.rectangle([0, H - 80, W, H], fill=(15, 15, 20))
    for i, label in enumerate(["📞", "🏠", "⬅️"]):
        x = W // 4 * (i + 1) - 20
        text(draw, (x, H - 60), label, 36, WHITE)

    return _save(img, "home_screen")


def make_whatsapp_chat_list():
    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([0, 0, W, 70], fill=GREEN_DARK)
    text(draw, (20, 20), "WhatsApp", 28, WHITE)
    text(draw, (W - 120, 20), "🔍  ⋮", 24, WHITE)

    # Chat list
    chats = [
        ("👩 Daughter Sara", "Are you okay? Call me when free 💛", "2 min ago", True),
        ("👨 Son Ahmed", "Dad, I sent you money, check balance", "1 hr ago", False),
        ("👩‍⚕️ Dr. Fatima", "Your appointment is tomorrow at 10 AM", "Yesterday", False),
        ("👥 Family Group", "Haha 😂 seen by 12", "Yesterday", False),
    ]
    for i, (name, preview, time_str, unread) in enumerate(chats):
        y = 80 + i * 90
        draw.rectangle([0, y, W, y + 88], fill=WHITE if i % 2 == 0 else (248, 248, 248))
        draw.ellipse([15, y + 15, 75, y + 73], fill=GREEN_DARK)
        text(draw, (90, y + 10), name, 22, BLACK)
        text(draw, (90, y + 42), preview[:55] + "...", 17, GREY)
        text(draw, (W - 160, y + 10), time_str, 16, GREY)
        if unread:
            draw.ellipse([W - 50, y + 40, W - 20, y + 68], fill=GREEN_WA)
            text(draw, (W - 43, y + 45), "2", 18, WHITE)

    # WhatsApp bottom tabs
    draw.rectangle([0, H - 65, W, H], fill=(WHITE[0], WHITE[1], WHITE[2]))
    draw.rectangle([0, H - 65, W, H - 63], fill=GREEN_WA)
    for i, (tab, label) in enumerate([("💬", "Chats"), ("📊", "Status"), ("📞", "Calls")]):
        x = W // 4 * (i + 1) - 30
        text(draw, (x, H - 55), tab, 28, GREEN_DARK if i == 0 else GREY)
        text(draw, (x - 10, H - 25), label, 16, GREEN_DARK if i == 0 else GREY)

    return _save(img, "whatsapp_chat_list")


def make_whatsapp_chat_open():
    img = Image.new("RGB", (W, H), (230, 221, 211))
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([0, 0, W, 70], fill=GREEN_DARK)
    draw.ellipse([15, 8, 65, 58], fill=GREEN_WA)
    text(draw, (80, 8), "👩 Daughter Sara", 24, WHITE)
    text(draw, (80, 38), "Last seen today at 9:30 AM", 15, (180, 230, 200))
    text(draw, (W - 80, 20), "📞  ⋮", 22, WHITE)

    # Messages
    messages = [
        ("Sara", "Abbu, are you okay? 💛", "9:30 AM", False),
        ("Sara", "Please send me a voice note when you see this 🙏", "9:31 AM", False),
        ("You", "Yes beta, I am fine 😊", "9:45 AM", True),
        ("Sara", "Okay! Love you! 💛", "9:46 AM", False),
    ]
    y = 90
    for sender, msg, time_str, is_me in messages:
        bubble_color = (220, 248, 198) if is_me else WHITE
        x = W - 600 if is_me else 20
        _rounded_rect(draw, [x, y, x + 580, y + 55], radius=12, fill=bubble_color)
        text(draw, (x + 12, y + 8), msg, 18, BLACK)
        text(draw, (x + 520, y + 35), time_str, 13, GREY)
        y += 70

    # Input bar
    draw.rectangle([0, H - 70, W, H], fill=WHITE)
    _rounded_rect(draw, [60, H - 58, W - 80, H - 15], radius=25, fill=(240, 240, 240))
    text(draw, (80, H - 48), "Type a message...", 18, GREY)
    draw.ellipse([W - 68, H - 62, W - 15, H - 9], fill=GREEN_WA)
    text(draw, (W - 55, H - 53), "🎤", 28, WHITE)

    return _save(img, "whatsapp_chat_open")


def make_missed_call():
    img = Image.new("RGB", (W, H), (30, 30, 35))
    draw = ImageDraw.Draw(img)
    # Dark background
    for y in range(H):
        draw.line([(0, y), (W, y)], fill=(30, 30, int(35 + y * 0.05)))

    # Notification card
    _rounded_rect(draw, [W//2 - 280, 150, W//2 + 280, 380], radius=24, fill=(50, 50, 60))
    draw.ellipse([W//2 - 45, 170, W//2 + 45, 260], fill=RED_ERR)
    text(draw, (W//2 - 22, 190), "📞", 48, WHITE)
    text(draw, (W//2 - 120, 275), "Missed Call", 28, RED_ERR)
    text(draw, (W//2 - 95, 315), "👩 Daughter Sara", 22, WHITE)
    text(draw, (W//2 - 60, 348), "Just now", 18, GREY)

    # Call back button
    _rounded_rect(draw, [W//2 - 150, 420, W//2 + 150, 480], radius=28, fill=GREEN_WA)
    text(draw, (W//2 - 95, 438), "📞 Call Back", 24, WHITE)

    return _save(img, "missed_call")


def make_stuck_on_settings():
    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W, 65], fill=(50, 50, 50))
    text(draw, (20, 18), "⬅  Settings", 26, WHITE)

    settings = [
        ("🔔", "Notifications", "On"),
        ("📶", "Wi-Fi", "Connected"),
        ("🔵", "Bluetooth", "Off"),
        ("🔋", "Battery", "85%"),
        ("🔒", "Lock Screen", ""),
        ("🌐", "Language", "English"),
    ]
    # Highlight the wrong one (red border — user keeps tapping wrong item)
    for i, (icon, label, value) in enumerate(settings):
        y = 75 + i * 75
        color = (255, 235, 235) if i == 4 else WHITE
        draw.rectangle([0, y, W, y + 73], fill=color)
        text(draw, (20, y + 18), icon, 32, BLACK)
        text(draw, (80, y + 20), label, 22, BLACK)
        if value:
            text(draw, (W - 150, y + 20), value, 20, GREY)
        text(draw, (W - 40, y + 22), "›", 30, GREY)
        draw.line([(0, y + 73), (W, y + 73)], fill=(220, 220, 220))

    # Red highlight indication on wrong tapped item
    draw.rectangle([0, 75 + 4*75, 6, 75 + 5*75], fill=RED_ERR)

    return _save(img, "stuck_on_settings")


def make_error_popup():
    img = Image.new("RGB", (W, H), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    # Dim background (blurred effect simulation)
    draw.rectangle([0, 0, W, H], fill=(0, 0, 0, 120))

    # Error dialog
    _rounded_rect(draw, [W//2 - 280, H//2 - 160, W//2 + 280, H//2 + 160], radius=20, fill=WHITE)
    draw.ellipse([W//2 - 35, H//2 - 145, W//2 + 35, H//2 - 75], fill=RED_ERR)
    text(draw, (W//2 - 12, H//2 - 133), "!", 54, WHITE)
    text(draw, (W//2 - 80, H//2 - 55), "Something went wrong", 22, BLACK)
    text(draw, (W//2 - 170, H//2 - 20), "The action could not be completed.", 18, GREY)
    text(draw, (W//2 - 80, H//2 + 10), "Please try again later.", 18, GREY)

    # Buttons
    draw.line([(W//2 - 280, H//2 + 65), (W//2 + 280, H//2 + 65)], fill=(220, 220, 220))
    _rounded_rect(draw, [W//2 - 130, H//2 + 78, W//2 + 130, H//2 + 130], radius=14, fill=BLUE_NOTIF)
    text(draw, (W//2 - 25, H//2 + 92), "OK", 26, WHITE)

    return _save(img, "error_popup")


def make_video_call_incoming():
    img = Image.new("RGB", (W, H), (15, 15, 20))
    draw = ImageDraw.Draw(img)

    # Ripple circles
    for r in [180, 220, 260]:
        draw.ellipse([W//2 - r, H//2 - r - 80, W//2 + r, H//2 + r - 80], outline=(37, 211, 102, 100), width=2)

    # Contact avatar
    draw.ellipse([W//2 - 90, H//2 - 250, W//2 + 90, H//2 - 70], fill=GREEN_WA)
    text(draw, (W//2 - 30, H//2 - 215), "👩", 64, WHITE)

    text(draw, (W//2 - 140, H//2 - 40), "Daughter Sara", 30, WHITE)
    text(draw, (W//2 - 120, H//2 + 5), "Incoming Video Call...", 22, GREY)

    # Accept/Reject buttons
    draw.ellipse([W//2 - 200, H//2 + 80, W//2 - 100, H//2 + 180], fill=RED_ERR)
    text(draw, (W//2 - 180, H//2 + 100), "📵", 52, WHITE)

    draw.ellipse([W//2 + 100, H//2 + 80, W//2 + 200, H//2 + 180], fill=GREEN_WA)
    text(draw, (W//2 + 110, H//2 + 100), "📹", 52, WHITE)

    text(draw, (W//2 - 165, H//2 + 188), "Decline", 18, GREY)
    text(draw, (W//2 + 115, H//2 + 188), "Accept", 18, GREY)

    return _save(img, "video_call_incoming")


# ─── Main ─────────────────────────────────────────────────────────────────────

def generate_all():
    print("\n🎨 Generating demo mock screens...\n")
    make_home_screen()
    make_whatsapp_chat_list()
    make_whatsapp_chat_open()
    make_missed_call()
    make_stuck_on_settings()
    make_error_popup()
    make_video_call_incoming()
    print(f"\n✅ All screens saved to: demo/mock_screens/\n")


if __name__ == "__main__":
    generate_all()
