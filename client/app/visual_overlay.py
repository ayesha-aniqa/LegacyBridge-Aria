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
            import ctypes
            # GWL_EXSTYLE = -20, WS_EX_LAYERED = 0x80000, WS_EX_TRANSPARENT = 0x20
            # Set layered and transparent styles
            ctypes.windll.user32.SetWindowLongW(self.winfo_id(), -20, 
                ctypes.windll.user32.GetWindowLongW(self.winfo_id(), -20) | 0x80000 | 0x20)

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.screen_width = self.winfo_screenwidth()
        self.screen_height = self.winfo_screenheight()

    def draw_target(self, coords_str):
        """
        Draw a pulsing red circle at normalized [y, x] coordinates.
        coords_str format: '[y, x]'
        """
        self.canvas.delete("hint")
        try:
            # Parse [y, x]
            coords = eval(coords_str)
            y_norm, x_norm = coords
            
            x = int((x_norm / 1000) * self.screen_width)
            y = int((y_norm / 1000) * self.screen_height)
            
            # Draw a pulsing circle
            self._pulse_circle(x, y, 30)
            
        except Exception as e:
            print(f"Overlay Error: {e}")

    def _pulse_circle(self, x, y, r, step=0):
        self.canvas.delete("hint")
        # Pulsing effect
        colors = ["#ff0000", "#ff4444", "#ff8888", "white"]
        color = colors[step % len(colors)]
        
        if color != "white":
            self.canvas.create_oval(
                x-r, y-r, x+r, y+r, 
                outline=color, width=5, tags="hint"
            )
            # Add an arrow-like indicator
            self.canvas.create_line(
                x, y-r-20, x, y-r-5, 
                arrow=tk.LAST, fill="red", width=5, tags="hint"
            )
            
        if step < 20: # Pulse for ~2 seconds
            self.after(100, self._pulse_circle, x, y, r, step + 1)
        else:
            self.canvas.delete("hint")
