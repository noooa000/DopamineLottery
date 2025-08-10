import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os, sys
import random
import winsound
from tracker import load_chances, use_chance, add_chance, track_process
from PIL import Image, ImageTk
import win32api
import win32con
import win32ui
import win32gui
import ctypes
from ctypes import wintypes
import time


# =============================
# Globals & Config
# =============================
current_tracking = None
tracking_paused = False
last_button = None
last_label = None
track_count = 0
tracking_thread = None            # ★ unchanged comment retained
tracking_stop_event = None        # ★ unchanged comment retained

# 🎇 TEST
TEST_TIME_PER_CHANCE = None  #  seconds (kept as is)


SETTINGS_FILE = "settings.txt"  # plain text persistence only
ROLLS_PER_MULTI = 10             # ★ NEW: default fallback


def _settings_load_rolls() -> int:
    """★ NEW: Read ROLLS_PER_MULTI from SETTINGS_FILE if present."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ROLLS_PER_MULTI="):
                        val = int(line.split("=", 1)[1])
                        return max(1, min(50, val))  # clamp to sane range
    except Exception:
        pass
    return 10


def _settings_save_rolls(n: int) -> None:
    """★ NEW: Save only ROLLS_PER_MULTI into SETTINGS_FILE as plain text."""
    try:
        lines = []
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith("ROLLS_PER_MULTI="):
                lines[i] = f"ROLLS_PER_MULTI={n}"
                found = True
                break
        if not found:
            lines.append(f"ROLLS_PER_MULTI={n}")
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:
        # Silently ignore persistence errors
        pass


# =============================
# Utility
# =============================

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# =============================
# UI Setup
# =============================
root = tk.Tk()

# window meta
root.title("Dopamine Lottery")
root.iconbitmap(resource_path("icon2.ico"))

# center the window
window_width = 400
window_height = 480
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x = int((screen_width / 2) - (window_width / 2))
y = int((screen_height / 2) - (window_height / 2))
root.geometry(f"{window_width}x{window_height}+{x}+{y}")

BG_COLOR = "#f0f0f0"
root.overrideredirect(True)

# Title bar
title_bar = tk.Frame(root, bg=BG_COLOR, height=28, bd=0, relief="flat")
title_bar.pack(fill="x", side="top")

# App icon
icon_img = Image.open(resource_path("icon2.ico")).resize((16, 16))
icon_tk_small = ImageTk.PhotoImage(icon_img)
icon_label_title = tk.Label(title_bar, image=icon_tk_small, bg=BG_COLOR)
icon_label_title.pack(side="left", padx=8)

# minimize support for overrideredirect windows

def _minimize():
    x, y = root.winfo_x(), root.winfo_y()
    root.overrideredirect(False)
    root.update_idletasks()
    root.iconify()


def _on_restore(_=None):
    root.overrideredirect(True)
    root.update_idletasks()

root.bind("<Map>", _on_restore)

# Close button
close_btn = tk.Button(
    title_bar, text="✕", bg=BG_COLOR, relief="flat",
    activebackground=BG_COLOR, command=root.destroy
)
close_btn.pack(side="right")

# ★ NEW: Settings (gear) in the title bar — stored in SETTINGS_FILE (txt)
settings_mb = tk.Menubutton(title_bar, text="⚙", bg=BG_COLOR,
                            relief="flat", activebackground=BG_COLOR)
settings_menu = tk.Menu(settings_mb, tearoff=0)
settings_mb.config(menu=settings_menu)
settings_mb.pack(side="right", padx=(0, 4))

# Drag window by title bar or icon
_drag = {"x": 0, "y": 0}


def _start_drag(e):
    _drag.update(x=e.x_root - root.winfo_x(), y=e.y_root - root.winfo_y())


def _on_drag(e):
    root.geometry(f"+{e.x_root - _drag['x']}+{e.y_root - _drag['y']}")

for w in (title_bar, icon_label_title):
    w.bind("<Button-1>", _start_drag)
    w.bind("<B1-Motion>", _on_drag)

# Spacer under titlebar
tk.Frame(root, height=30, bg=BG_COLOR).pack(fill="x")

# Lottery chance display
chance_label = tk.Label(root, text="", font=("Helvetica", 16))
chance_label.pack(pady=10)

# Tracked time label
tracked_time_label = tk.Label(root, text="Tracked Time: 00:00:00",
                              fg="green", font=("Helvetica", 14))
tracked_time_label.pack(pady=5)

# Currently tracked app area
tracking_frame = tk.Frame(root)
tracking_frame.pack(pady=5)
icon_label = tk.Label(tracking_frame)
icon_label.pack(side="left", padx=5)
tracking_label = tk.Label(tracking_frame, text="Tracking: None",
                          fg="gray", font=("Helvetica", 12))
tracking_label.pack(side="left")


# =============================
# Sounds & Small Utils
# =============================

def play_click_sound():
    winsound.Beep(800, 100)


def play_win_sound():
    winsound.Beep(1200, 200)


def play_jackpot_sound():
    winsound.Beep(1500, 500)


def play_fail_sound():
    winsound.Beep(500, 300)


# =============================
# Icon extraction
# =============================

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


# =============================
# UI helpers
# =============================

def show_lottery_popup(text, *, ms=3000, sound=None, title="🎲 Lottery Result"):
    popup = tk.Toplevel(root)
    popup.title(title)
    popup.geometry("400x200")
    popup.resizable(False, False)
    popup_x = root.winfo_x() + (root.winfo_width() // 2) - 200
    popup_y = root.winfo_y() + (root.winfo_height() // 2) - 100
    popup.geometry(f"+{popup_x}+{popup_y}")
    tk.Label(popup, text=text, font=("Helvetica", 14), justify="center").pack(expand=True)
    popup.after(ms, popup.destroy)
    if sound:
        threading.Thread(target=sound, daemon=True).start()


# =============================
# Lottery
# =============================

def _show_or_hide_multi_button():
    """★ NEW: centralize visibility so changing 10→6/8 shows/hides immediately."""
    try:
        current = load_chances()
    except Exception:
        current = 0
    if current >= ROLLS_PER_MULTI:
        if not play_multi_button.winfo_ismapped():
            play_multi_button.pack(after=play_button, pady=2)
    else:
        if play_multi_button.winfo_ismapped():
            play_multi_button.pack_forget()


def update_chance_label():
    current = load_chances()
    chance_label.config(text=f"Chances Left: {current}")
    # ★ CHANGED: ensure the multi button reflects the latest threshold right away
    _show_or_hide_multi_button()


def run_lottery():
    if not use_chance():
        show_lottery_popup("❌ No lottery chances left!", ms=3000, sound=play_fail_sound)
        return
    play_click_sound()
    roll = random.random()
    if roll < 0.49:
        prize = random.randint(1, 20)
        msg, snd, dur = f"You won ${prize}!", play_win_sound, 3000
    elif roll < 0.51:
        msg, snd, dur = "🎉 Jackpot!\nYou won 100% of the prize!\n($100)", play_jackpot_sound, 30000
    else:
        msg, snd, dur = "Keep working!", play_fail_sound, 3000
    show_lottery_popup(msg, ms=dur, sound=snd)
    update_chance_label()


def run_lottery_multi():
    """★ CHANGED: multi-run uses dynamic ROLLS_PER_MULTI."""
    def run_all():
        results = []
        popup = tk.Toplevel(root)
        popup.title("🎲 Multi-roll Results")
        popup.geometry("400x200")
        popup.resizable(False, False)
        popup_x = root.winfo_x() + (root.winfo_width() // 2) - 200
        popup_y = root.winfo_y() + (root.winfo_height() // 2) - 100
        popup.geometry(f"+{popup_x}+{popup_y}")
        label = tk.Label(popup, text="", font=("Helvetica", 16), justify="center")
        label.pack(expand=True, fill="both")

        def show_next_result(index):
            # Stop conditions: performed desired rolls OR ran out of chances
            if index >= ROLLS_PER_MULTI:
                summary = "\n".join(results)
                label.config(text=summary, font=("Helvetica", 12), justify="left")
                return
            if not use_chance():
                result = f"Roll {index + 1}: ❌ No more chances!"
                results.append(result)
                label.config(text=result)
                play_fail_sound()
                # After out of chances, finalize early
                popup.after(800, lambda: label.config(text="\n".join(results)))
                return

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
            popup.after(800, lambda: show_next_result(index + 1))

        show_next_result(0)

    threading.Thread(target=run_all, daemon=True).start()


# =============================
# Tracking controls
# =============================

def resume_last_tracking():
    global last_icon_tk, last_button, last_label
    if last_button:
        last_button.pack_forget(); last_button = None
    if last_label:
        last_label.pack_forget(); last_label = None
    if os.path.exists("last_app.txt"):
        with open("last_app.txt", "r", encoding="utf-8") as f:
            path = f.read().strip()
        if os.path.exists(path):
            exe = os.path.basename(path)
            icon_img = extract_icon_image(path)
            if icon_img:
                last_icon_tk = ImageTk.PhotoImage(icon_img)
                last_button = tk.Button(resume_frame, image=last_icon_tk,
                                        command=lambda p=path: start_tracking_from_path(p))
                last_label = tk.Label(resume_frame, text=f"Last tracked: {exe}", font=("Helvetica", 12))
                last_button.pack(pady=2)
                last_label.pack(pady=2)


def show_cheer_popup():
    popup = tk.Toplevel(root)
    popup.title("🎉 Celebration!")
    popup.geometry("200x150")
    popup.resizable(False, False)
    popup_x = root.winfo_x() + (root.winfo_width() // 2) - 100
    popup_y = root.winfo_y() + (root.winfo_height() // 2) - 75
    popup.geometry(f"+{popup_x}+{popup_y}")
    tk.Label(popup, text="🎉", font=("Helvetica", 60)).pack(expand=True)
    popup.after(30000, popup.destroy)
    threading.Thread(
        target=lambda: winsound.PlaySound(resource_path("cheer.wav"), winsound.SND_FILENAME),
        daemon=True
    ).start()


def toggle_pause():
    global tracking_paused
    tracking_paused = not tracking_paused
    pause_button.config(text=("▶ Resume Tracking" if tracking_paused else "⏸ Pause Tracking"))
    if not stop_button.winfo_ismapped():
        stop_button.pack(pady=2)


# =============================
# Tracking start/stop (★ pass rolls_per_multi into track_process)
# =============================

def _start_tracker(exe_name: str):
    """★ NEW: shared starter to avoid duplication and ensure consistent args."""
    global tracking_thread, tracking_stop_event
    # stop any previous tracker cleanly
    if tracking_thread and tracking_thread.is_alive():
        try:
            tracking_stop_event.set()
            tracking_thread.join(timeout=2)
        except Exception:
            pass
    tracking_stop_event = threading.Event()
    tracking_thread = threading.Thread(
        target=track_process,
        args=(exe_name, tracked_time_label, lambda: tracking_paused, show_cheer_popup, TEST_TIME_PER_CHANCE, tracking_stop_event),
        kwargs=dict(rolls_per_multi=ROLLS_PER_MULTI),  # ★ CHANGED: forward current setting
        daemon=True
    )
    tracking_thread.start()


def start_tracking_from_path(path):
    global current_tracking, last_button, last_label
    if last_label:
        last_label.pack_forget(); last_label = None
    exe = os.path.basename(path)
    current_tracking = exe
    tracking_label.config(text=f"Tracking: {exe}", fg="green")
    winsound.Beep(600, 150)
    with open("last_app.txt", "w", encoding="utf-8") as f:
        f.write(path)
    icon_img = extract_icon_image(path)
    if icon_img:
        icon_tk = ImageTk.PhotoImage(icon_img)
        icon_label.config(image=icon_tk)
        icon_label.image = icon_tk
    else:
        icon_label.config(image="", text="❓")
    track_button.pack_forget(); play_button.pack_forget()
    if last_button:
        last_button.pack_forget(); last_button = None
    if not pause_button.winfo_ismapped():
        pause_button.config(text="⏸ Pause Tracking"); pause_button.pack(pady=5)
    if not stop_button.winfo_ismapped():
        stop_button.pack(pady=2)
    _start_tracker(exe)


def start_tracking():
    global current_tracking, last_button, last_label
    if last_label:
        last_label.pack_forget(); last_label = None
    filepath = filedialog.askopenfilename(title="Select EXE to Track", filetypes=[("Executable Files", "*.exe")])
    if not filepath:
        return
    exe = os.path.basename(filepath)
    current_tracking = exe
    tracking_label.config(text=f"Tracking: {exe}", fg="green")
    icon_img = extract_icon_image(filepath)
    if icon_img:
        icon_tk = ImageTk.PhotoImage(icon_img)
        icon_label.config(image=icon_tk); icon_label.image = icon_tk
    else:
        icon_label.config(image="", text="❓")
    winsound.Beep(600, 150)
    track_button.pack_forget(); play_button.pack_forget()
    if last_button:
        last_button.pack_forget(); last_button = None
    if not pause_button.winfo_ismapped():
        pause_button.config(text="⏸ Pause Tracking"); pause_button.pack(pady=5)
    if not stop_button.winfo_ismapped():
        stop_button.pack(pady=2)
    with open("last_app.txt", "w", encoding="utf-8") as f:
        f.write(filepath)
    _start_tracker(exe)


def stop_tracking():
    global tracking_paused, current_tracking, tracking_thread, tracking_stop_event
    tracking_paused = False
    current_tracking = None
    if tracking_stop_event:
        tracking_stop_event.set()
    if tracking_thread:
        tracking_thread.join(timeout=2)
    tracking_thread = None
    winsound.PlaySound(None, winsound.SND_PURGE)
    tracking_label.config(text="Tracking: None", fg="gray")
    tracked_time_label.config(text="Tracked Time: 00:00:00")
    icon_label.config(image=""); icon_label.image = None
    if pause_button.winfo_ismapped():
        pause_button.pack_forget()
    if stop_button.winfo_ismapped():
        stop_button.pack_forget()
    track_button.pack(pady=20)
    play_button.pack(pady=10)
    root.after(100, resume_last_tracking)


def on_close():
    stop_tracking()
    root.destroy()


# =============================
# Auto-refresh chances
# =============================

def auto_refresh_chance():
    update_chance_label()
    root.after(5000, auto_refresh_chance)  # every 5 sec


# =============================
# Buttons
# =============================
track_button = tk.Button(root, text="🎯 Select App to Track", command=start_tracking, font=("Helvetica", 14))
track_button.pack(pady=20)

play_button = tk.Button(root, text="🎲 Play Lottery", command=run_lottery, font=("Helvetica", 18))
play_button.pack(pady=10)

# ★ CHANGED: generic multi button; text set after loading settings
play_multi_button = tk.Button(root, text="10 🎲", font=("Helvetica", 14), command=run_lottery_multi)

pause_button = tk.Button(root, text="⏸ Pause Tracking", command=toggle_pause, font=("Helvetica", 12))
stop_button  = tk.Button(root, text="🛑 Stop Tracking",  command=stop_tracking,  font=("Helvetica", 12))

resume_frame = tk.Frame(root)
resume_frame.pack(pady=5)


# =============================
# Settings menu wiring (★ dynamic ROLLS_PER_MULTI)
# =============================

def _apply_rolls(n: int):
    """★ CHANGED: apply & persist new ROLLS_PER_MULTI and update button immediately."""
    global ROLLS_PER_MULTI
    ROLLS_PER_MULTI = int(n)
    _settings_save_rolls(ROLLS_PER_MULTI)
    # update the multi button label
    if play_multi_button is not None:
        play_multi_button.config(text=f"{ROLLS_PER_MULTI} 🎲")
    # ★ NEW: show/hide instantly based on new threshold
    _show_or_hide_multi_button()
    # keep label fresh
    update_chance_label()
    # if currently tracking, restart so downstream logic can use new setting
    if current_tracking:
        try:
            if tracking_thread and tracking_thread.is_alive():
                tracking_stop_event.set()
                tracking_thread.join(timeout=2)
        except Exception:
            pass
        _start_tracker(current_tracking)

# Populate menu (examples 6/8/10)
settings_menu.add_command(label="Relax (6)",   command=lambda: _apply_rolls(6))
settings_menu.add_command(label="Normal (8)",  command=lambda: _apply_rolls(8))
settings_menu.add_command(label="十连 (10)",    command=lambda: _apply_rolls(10))


# =============================
# Init (★ load settings before first label update)
# =============================
ROLLS_PER_MULTI = _settings_load_rolls()  # ★ NEW: load from txt
play_multi_button.config(text=f"{ROLLS_PER_MULTI} 🎲")  # ★ NEW: reflect loaded value
# ★ NEW: ensure initial visibility is correct for the loaded threshold
_show_or_hide_multi_button()

update_chance_label()
resume_last_tracking()
auto_refresh_chance()

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
