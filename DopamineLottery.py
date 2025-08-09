import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
import random
import winsound
from tracker import load_chances, use_chance, add_chance, track_process
from PIL import Image, ImageTk
import win32api
import win32con
import win32ui
import win32gui
from PIL import Image, ImageTk
import ctypes
from ctypes import wintypes
import sys
import os
import time


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

current_tracking = None
tracking_paused = False
last_button = None
last_label = None
track_count = 0




# ---------------- UI Setup ------------------


root = tk.Tk()
resume_frame = tk.Frame(root)


root.title("Dopamine Lottery")
root.iconbitmap(resource_path("icon2.ico"))

last_icon_tk = None




# Celebration emoji label (initially hidden)
cheer_label = tk.Label(root, text="🎉", font=("Helvetica", 36))


# Center the window
window_width = 400
window_height = 450
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x = int((screen_width / 2) - (window_width / 2))
y = int((screen_height / 2) - (window_height / 2))
root.geometry(f"{window_width}x{window_height}+{x}+{y}")

# Lottery chance display
chance_label = tk.Label(root, text="", font=("Helvetica", 16))
chance_label.pack(pady=10)

# Tracked time label
tracked_time_label = tk.Label(root, text="Tracked Time: 0 min", fg="green", font=("Helvetica", 14))
tracked_time_label.pack(pady=5)

# Currently tracked app
# Icon and name container
tracking_frame = tk.Frame(root)
tracking_frame.pack(pady=5)

# EXE icon
icon_label = tk.Label(tracking_frame)
icon_label.pack(side="left", padx=5)

# EXE name
tracking_label = tk.Label(tracking_frame, text="Tracking: None", fg="gray", font=("Helvetica", 12))
tracking_label.pack(side="left")



# Result Label
result_label = tk.Label(root, text="", fg="blue", font=("Helvetica", 20))
result_label.pack(pady=10)



# ---------------- Logic ------------------

def resume_last_tracking():
    global last_icon_tk, last_button, last_label

    # Remove old buttons/labels if they exist
    if last_button:
        last_button.pack_forget()
        last_button = None
    if last_label:
        last_label.pack_forget()
        last_label = None

 

    # Load last tracked app
    if os.path.exists("last_app.txt"):
        with open("last_app.txt", "r") as f:
            path = f.read().strip()
            if os.path.exists(path):
                exe = os.path.basename(path)
                icon_img = extract_icon_image(path)
                if icon_img:
                    last_icon_tk = ImageTk.PhotoImage(icon_img)
                    last_button = tk.Button(resume_frame, image=last_icon_tk, command=lambda: start_tracking_from_path(path))
                    last_label = tk.Label(resume_frame, text=f"Last tracked: {exe}", font=("Helvetica", 12))

                    # ✅ Pack these *after* the 10x button
                    last_button.pack(pady=2)
                    last_label.pack(pady=2)



def start_tracking_from_path(path):
    global current_tracking, last_button, last_label

    if last_label:
        last_label.pack_forget()
        last_label = None

    exe = os.path.basename(path)
    current_tracking = exe
    tracking_label.config(text=f"Tracking: {exe}", fg="green")
    
    # Short "start" sound
    winsound.Beep(600, 150)  # frequency=1000Hz, duration=150ms
    


    # ✅ Save path to file
    with open("last_app.txt", "w") as f:
        f.write(path)

    # ✅ Display icon for currently tracked app
    icon_img = extract_icon_image(path)
    if icon_img:
        icon_tk = ImageTk.PhotoImage(icon_img)
        icon_label.config(image=icon_tk)
        icon_label.image = icon_tk  # prevent GC
    else:
        icon_label.config(image="", text="❓")

    # Hide buttons like in start_tracking
    track_button.pack_forget()
    play_button.pack_forget()
    if last_button:
        last_button.pack_forget()
        last_button = None

    # Show pause button
    if not pause_button.winfo_ismapped():
        pause_button.pack(pady=5)

    # Start tracking thread
    thread = threading.Thread(
    target=track_process,
    args=(exe, tracked_time_label, lambda: tracking_paused, show_cheer_popup),
    daemon=True
)

    thread.start()





def play_click_sound():
    winsound.Beep(800, 100)

def extract_icon_image(filepath):
    large, _ = win32gui.ExtractIconEx(filepath, 0)
    if not large:
        return None
    hicon = large[0]
    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
    hbmp = win32ui.CreateBitmap()
    hbmp.CreateCompatibleBitmap(hdc, 32, 32)
    hdc = hdc.CreateCompatibleDC()
    hdc.SelectObject(hbmp)
    win32gui.DrawIconEx(hdc.GetHandleOutput(), 0, 0, hicon, 32, 32, 0, None, win32con.DI_NORMAL)
    bmpinfo = hbmp.GetInfo()
    bmpstr = hbmp.GetBitmapBits(True)
    icon_img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)
    win32gui.DestroyIcon(hicon)
    return icon_img


def play_win_sound():
    winsound.Beep(1200, 200)

def play_jackpot_sound():
    winsound.Beep(1500, 500)

def play_fail_sound():
    winsound.Beep(500, 300)

def update_chance_label():
    current = load_chances()
    chance_label.config(text=f"Chances Left: {current}")

def run_lottery():
    if not use_chance():
        result_label.config(text="❌ No lottery chances left!")
        return

    play_click_sound()
    roll = random.random()

    popup = tk.Toplevel(root)
    popup.title("🎲 Lottery Result")
    popup.geometry("300x180")
    popup.resizable(False, False)

    # Center popup on screen
    popup_x = root.winfo_x() + (root.winfo_width() // 2) - 150
    popup_y = root.winfo_y() + (root.winfo_height() // 2) - 90
    popup.geometry(f"+{popup_x}+{popup_y}")

    result = ""
    sound_func = None

    if roll < 0.49:
        prize = random.randint(1, 20)
        result = f"You won ${prize}!"
        sound_func = play_win_sound
    elif roll < 0.51:
        result = "🎉 Jackpot!\nYou won 100% of the prize!\n($100)"
        sound_func = play_jackpot_sound
    else:
        result = "Keep working!"
        sound_func = play_fail_sound

    label = tk.Label(popup, text=result, font=("Helvetica", 14), justify="center")
    label.pack(expand=True)

    popup.after(30000, popup.destroy)  # Auto close after 30s
    threading.Thread(target=sound_func, daemon=True).start()

    update_chance_label()

def run_lottery_10x():
    def run_all():
        results = []
        popup = tk.Toplevel(root)
        popup.title("🎲 10x Lottery Results")
        popup.geometry("400x200")
        popup.resizable(False, False)

        # Center the popup
        popup_x = root.winfo_x() + (root.winfo_width() // 2) - 200
        popup_y = root.winfo_y() + (root.winfo_height() // 2) - 100
        popup.geometry(f"+{popup_x}+{popup_y}")

        label = tk.Label(popup, text="", font=("Helvetica", 16), justify="center")
        label.pack(expand=True, fill="both")

        def show_next_result(index):
            if index >= 10 or index >= load_chances() + len(results):
                # Show all results together after finishing
                summary = "\n".join(results)
                label.config(text=summary, font=("Helvetica", 12), justify="left")
                return

            if not use_chance():
                result = f"Roll {index + 1}: ❌ No more chances!"
                results.append(result)
                label.config(text=result)
                play_fail_sound()
            else:
                roll = random.random()
                if roll < 0.49:
                    prize = random.randint(1, 20)
                    result = f"Roll {index + 1}: ✅ You won ${prize}"
                    sound_func = play_win_sound
                elif roll < 0.51:
                    result = f"Roll {index + 1}: 🎉 JACKPOT! You won $100"
                    sound_func = play_jackpot_sound
                else:
                    result = f"Roll {index + 1}: ✖ Keep working!"
                    sound_func = play_fail_sound

                results.append(result)
                label.config(text=result)
                threading.Thread(target=sound_func, daemon=True).start()
                update_chance_label()

            popup.after(1000, lambda: show_next_result(index + 1))

        show_next_result(0)

    threading.Thread(target=run_all, daemon=True).start()





def start_tracking():
    global current_tracking, last_button
    # Hide last tracked icon and label
    global last_label
    if last_label:
        last_label.pack_forget()
        last_label = None




    filepath = filedialog.askopenfilename(
        title="Select EXE to Track",
        filetypes=[("Executable Files", "*.exe")]
    )
    if filepath:
        exe = os.path.basename(filepath)
        current_tracking = exe

        # Update label with name
        tracking_label.config(text=f"Tracking: {exe}", fg="green")

        # Update icon
        icon_img = extract_icon_image(filepath)
        if icon_img:
            icon_tk = ImageTk.PhotoImage(icon_img)
            icon_label.config(image=icon_tk)
            icon_label.image = icon_tk  # Prevent GC
        else:
            icon_label.config(image="", text="❓")

        # Short "start" sound
        winsound.Beep(600, 150)


        # Hide other buttons
        track_button.pack_forget()
        play_button.pack_forget()

        # Hide last tracked app button if shown
        if last_button:
            last_button.pack_forget()
            last_button = None

        # Show pause button
        if not pause_button.winfo_ismapped():
            pause_button.pack(pady=5)

        # Start tracking thread
        thread = threading.Thread(
            target=track_process,
            args=(exe, tracked_time_label, lambda: tracking_paused, show_cheer_popup),
            daemon=True
            )

        thread.start()

        # ✅ Save last app path
        with open("last_app.txt", "w") as f:
            f.write(filepath)



def stop_tracking():
    global tracking_paused, current_tracking
    tracking_paused = False
    current_tracking = None
    tracking_label.config(text="Tracking: None", fg="gray")
    tracked_time_label.config(text="Tracked Time: 0 min")
    icon_label.config(image="")
    icon_label.image = None

    if pause_button.winfo_ismapped():
        pause_button.pack_forget()
    if stop_button.winfo_ismapped():
        stop_button.pack_forget()

    track_button.pack(pady=20)
    play_button.pack(pady=10)

    # Call resume after Play button and Track button are shown
    root.after(100, resume_last_tracking)

    

def show_cheer_popup():
    popup = tk.Toplevel(root)
    popup.title("🎉 Celebration!")
    popup.geometry("200x150")
    popup.resizable(False, False)

    # Center popup on screen
    popup_x = root.winfo_x() + (root.winfo_width() // 2) - 100
    popup_y = root.winfo_y() + (root.winfo_height() // 2) - 75
    popup.geometry(f"+{popup_x}+{popup_y}")

    label = tk.Label(popup, text="🎉", font=("Helvetica", 60))
    label.pack(expand=True)

    # Auto close after 30s
    popup.after(30000, popup.destroy)

    # Play cheer sound
    threading.Thread(
        target=lambda: winsound.PlaySound(resource_path("cheer.wav"), winsound.SND_FILENAME),
        daemon=True
    ).start()

       
  




def toggle_pause():
    global tracking_paused
    tracking_paused = not tracking_paused
    if tracking_paused:
        pause_button.config(text="▶ Resume Tracking")
    else:
        pause_button.config(text="⏸ Pause Tracking")

    # Always show Stop button when tracking is toggled
    if not stop_button.winfo_ismapped():
        stop_button.pack(pady=2)



def extract_icon_image(exe_path):

    large, small = win32gui.ExtractIconEx(exe_path, 0)
    if large:
        hicon = large[0]
        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, 32, 32)
        hdc = hdc.CreateCompatibleDC()
        hdc.SelectObject(hbmp)
        win32gui.DrawIconEx(hdc.GetHandleOutput(), 0, 0, hicon, 32, 32, 0, None, win32con.DI_NORMAL)

        bmpinfo = hbmp.GetInfo()
        bmpstr = hbmp.GetBitmapBits(True)
        img = Image.frombuffer(
            'RGBA',
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
            bmpstr, 'raw', 'BGRA', 0, 1
        )
        return img
    return None

def update_chance_label():
    current = load_chances()
    chance_label.config(text=f"Chances Left: {current}")

    # Show or hide the 10x button based on chances
    if current >= 10:
        if not play_10_button.winfo_ismapped():
            play_10_button.pack(after=play_button, pady=2)
    else:
        if play_10_button.winfo_ismapped():
            play_10_button.pack_forget()

def auto_refresh_chance():
    update_chance_label()
    root.after(5000, auto_refresh_chance)  # every 5 sec


# ---------------- Buttons ------------------




# Track app button
track_button = tk.Button(root, text="🎯 Select App to Track", command=start_tracking, font=("Helvetica", 14))
track_button.pack(pady=20)


# Play button
play_button = tk.Button(root, text="🎲 Play Lottery", command=run_lottery, font=("Helvetica", 18))
play_button.pack(pady=10)


# Play 10x button (initially hidden, below Play Lottery button)
play_10_button = tk.Button(root, text="10 🎲", font=("Helvetica", 14), command=run_lottery_10x)



# Pause/Stop (initially hidden)
pause_button = tk.Button(root, text="⏸ Pause Tracking", command=toggle_pause, font=("Helvetica", 12))
stop_button = tk.Button(root, text="🛑 Stop Tracking", command=stop_tracking, font=("Helvetica", 12))

# Frame for last tracked
resume_frame = tk.Frame(root)
resume_frame.pack(pady=5)


# Init
update_chance_label()
resume_last_tracking()  
auto_refresh_chance()


root.mainloop()
