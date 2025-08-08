import psutil
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import time

CHANCE_FILE = "chances.txt"
TIME_REQUIRED = 60 * 60  # 1 hour in seconds

def use_chance():
    chances = load_chances()
    if chances > 0:
        chances -= 1
        save_chances(chances)
        return True
    return False

def load_chances():
    try:
        with open(CHANCE_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return 0

def save_chances(chances):
    with open(CHANCE_FILE, "w") as f:
        f.write(str(chances))

def add_chance():
    chances = load_chances()
    chances += 1
    save_chances(chances)

def select_exe():
    root = tk.Tk()
    root.withdraw()
    filepath = filedialog.askopenfilename(
        title="Select an executable to track",
        filetypes=[("Executable files", "*.exe")]
    )
    if filepath:
        exe_name = os.path.basename(filepath)
        messagebox.showinfo("Tracking Started", f"Now tracking: {exe_name}\n1 chance every 1 hour.")
        return exe_name
    return None

def track_process(target_process, time_label, is_paused_func, cheer_callback):
    tracked_time = 0
    check_interval = 5

    while True:
        if not is_paused_func():
            found = any(proc.name().lower() == target_process.lower() for proc in psutil.process_iter(['name']))
            if found:
                tracked_time += check_interval
                mins = tracked_time // 60
                # ✅ Update label safely from thread
                time_label.after(0, lambda m=mins: time_label.config(text=f"Tracked Time: {m} min"))
                print(f"{target_process} is running... {mins} min tracked.")
            else:
                print(f"{target_process} not running.")

            if tracked_time >= TIME_REQUIRED:
                print("🎉 You've earned 1 lottery chance!")
                add_chance()
                tracked_time = 0

                total = load_chances()
                if total == 10:
                    time_label.after(0, lambda: time_label.config(text="🎉 10 chances reached!"))
                    cheer_callback()
                else:
                    time_label.after(0, lambda: time_label.config(text="🎉 1 chance added!"))

        time.sleep(check_interval)
