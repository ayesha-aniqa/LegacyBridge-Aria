import tkinter as tk
import os

if os.name == 'nt':
    import ctypes

class VisualOverlay(tk.Toplevel):
    """
    Transparent fullscreen overlay for drawing visual hints (arrows, circles).
    """
    def __init__(self, master=None):
        super().__init__(master)
        self.attributes("-topmost", True)
        self.attributes("-transparentcolor", "white")
        self.attributes("-fullscreen", True)
        self.overrideredirect(True)
        self.config(bg="white")
        
        # Make it click-through on Windows
        if os.name == 'nt':
            # GWL_EXSTYLE = -20, WS_EX_LAYERED = 0x80000, WS_EX_TRANSPARENT = 0x20
            ctypes.windll.user32.SetWindowLongW(
                self.winfo_id(), -20, 
                ctypes.windll.user32.GetWindowLongW(self.winfo_id(), -20) | 0x80000 | 0x20
            )

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.screen_width = self.winfo_screenwidth()
        self.screen_height = self.winfo_screenheight()

    def draw_target(self, hint, size=30, color="red"):
        """
        Draw a pulsing circle at normalized [y, x] coordinates.
        hint: [y, x] or "[y, x]" string
        size: radius of the circle in pixels
        color: circle color
        """
        self.canvas.delete("hint")
        try:
            # Convert string to list if needed
            if isinstance(hint, str):
                coords = eval(hint)
            else:
                coords = hint
            y_norm, x_norm = coords

            # Map normalized 0-1000 to screen pixels
            x = int((x_norm / 1000) * self.screen_width)
            y = int((y_norm / 1000) * self.screen_height)

            # Draw pulsing circle
            self._pulse_circle(x, y, size, color)
        except Exception as e:
            print(f"Overlay Error: {e}")

    def _pulse_circle(self, x, y, r, color="red", step=0):
        self.canvas.delete("hint")
        # Pulsing effect colors
        pulse_colors = [color, "#ff6666", "#ffaaaa", "white"]
        current_color = pulse_colors[step % len(pulse_colors)]

        if current_color != "white":
            self.canvas.create_oval(
                x-r, y-r, x+r, y+r,
                outline=current_color, width=5, tags="hint"
            )
            # Arrow indicator
            self.canvas.create_line(
                x, y-r-20, x, y-r-5,
                arrow=tk.LAST, fill=color, width=5, tags="hint"
            )

        if step < 20:  # Pulse for ~2 seconds
            self.after(100, self._pulse_circle, x, y, r, color, step + 1)
        else:
            self.canvas.delete("hint")