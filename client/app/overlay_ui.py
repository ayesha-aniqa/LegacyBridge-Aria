import tkinter as tk

class AriaOverlay(tk.Toplevel):
    """
    Modular Overlay Component for Aria Assistant.
    Can be used by the main loop to display guidance.
    """
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Aria Assistant")
        self.geometry("450x300+100+100")
        self.attributes("-topmost", True)
        
        self.title_label = tk.Label(self, text="Aria Assistant 👵🤝🤖", font=("Arial", 16, "bold"))
        self.title_label.pack(pady=10)
        
        self.guidance_box = tk.Text(self, height=5, width=40, font=("Arial", 14), wrap=tk.WORD)
        self.guidance_box.pack(pady=10)
        
        self.status_label = tk.Label(self, text="Ready", font=("Arial", 10), fg="green")
        self.status_label.pack()

    def update_guidance(self, text, color="#f2fff2"):
        self.guidance_box.delete(1.0, tk.END)
        self.guidance_box.insert(tk.END, text)
        self.guidance_box.config(bg=color)

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw() # Hide the main root window
    app = AriaOverlay(root)
    app.update_guidance("This is a modular test of the Aria Overlay.")
    root.mainloop()
