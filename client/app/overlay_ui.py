import tkinter as tk

# --------- Functions for Dummy Responses ---------

def ask_help():
    output.delete(1.0, tk.END)
    output.insert(tk.END,
    "I detected several icons on your screen.\n"
    "Please click the Gmail icon to open your email.")
    
    status_label.config(text="Status: Help response generated")

def scan_screen():
    output.delete(1.0, tk.END)
    output.insert(tk.END,
    "Scanning screen...\n"
    "Detected WhatsApp icon on the left side.\n"
    "Please click the highlighted icon.")
    
    status_label.config(text="Status: Screen scanned")

def read_guidance():
    output.insert(tk.END,
    "\n\n(TTS will read this instruction aloud)")
    
    status_label.config(text="Status: Reading guidance")

# --------- Main Window ---------

root = tk.Tk()
root.title("LegacyBridge Assistant")

# Overlay style
root.geometry("520x450")
root.attributes("-topmost", True)

# --------- Title ---------

title = tk.Label(root,
                 text="LegacyBridge Assistant",
                 font=("Arial",20,"bold"))
title.pack(pady=10)

# --------- Screen Status ---------

screen_status = tk.Label(root,
                         text="Screen Monitoring Active",
                         bg="#EAEAEA",
                         width=40,
                         height=4,
                         font=("Arial",14))
screen_status.pack(pady=10)

# --------- Buttons ---------

button_frame = tk.Frame(root)
button_frame.pack()

ask_button = tk.Button(button_frame,
                       text="Ask for Help",
                       font=("Arial",16),
                       width=15,
                       height=2,
                       command=ask_help)

ask_button.grid(row=0, column=0, padx=10, pady=10)

scan_button = tk.Button(button_frame,
                        text="Scan Screen",
                        font=("Arial",16),
                        width=15,
                        height=2,
                        command=scan_screen)

scan_button.grid(row=0, column=1, padx=10, pady=10)

read_button = tk.Button(root,
                        text="Read Guidance",
                        font=("Arial",16),
                        width=25,
                        height=2,
                        command=read_guidance)

read_button.pack(pady=10)

# --------- Guidance Output ---------

output = tk.Text(root,
                 height=6,
                 width=50,
                 font=("Arial",13))

output.pack(pady=10)

# --------- Status Bar ---------

status_label = tk.Label(root,
                        text="Status: Ready",
                        font=("Arial",12),
                        fg="green")

status_label.pack()

# --------- Run UI ---------

root.mainloop()