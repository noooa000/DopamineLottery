import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os, sys
import random
import winsound
from tracker import load_chances, use_chance, add_chance, track_process, _load_progress
from PIL import Image, ImageTk
import win32api
import win32con
import win32ui
import win32gui
import ctypes
from ctypes import wintypes
import time
import webbrowser


# =============================
# Globals & Config
# =============================

current_tracking = None
tracking_paused = False
last_button = None
last_label = None
track_count = 0
tracking_thread = None
tracking_stop_event = None

# 🎇 TEST
TEST_TIME_PER_CHANCE = None  # seconds

APP_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "DopamineLottery")
os.makedirs(APP_DIR, exist_ok=True)

SETTINGS_FILE = os.path.join(APP_DIR, "settings.txt")
LAST_APP_FILE = os.path.join(APP_DIR, "last_app.txt")
ROLLS_PER_MULTI = 8  # default; overwritten by settings loader
VERSION = "0.72"
COPYRIGHT = "火火火因"
REPO_URL = "https://github.com/noooa000/DopamineLottery"



# =============================
# Settings helpers
# =============================

def _settings_load_rolls() -> int:
    """Read ROLLS_PER_MULTI from SETTINGS_FILE if present; clamp to [1, 50]."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ROLLS_PER_MULTI="):
                        val = int(line.split("=", 1)[1])
                        return max(1, min(50, val))
    except Exception:
        pass
    return 10


def _settings_save_rolls(n: int) -> None:
    """Save only ROLLS_PER_MULTI into SETTINGS_FILE as plain text."""
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
try:
    root.iconbitmap(resource_path("icon2.ico"))
except Exception:
    pass  # icon optional

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
try:
    icon_img = Image.open(resource_path("icon2.ico")).resize((16, 16))
    icon_tk_small = ImageTk.PhotoImage(icon_img)
    icon_label_title = tk.Label(title_bar, image=icon_tk_small, bg=BG_COLOR)
    icon_label_title.pack(side="left", padx=8)
except Exception:
    icon_label_title = tk.Label(title_bar, text="🎯", bg=BG_COLOR)
    icon_label_title.pack(side="left", padx=8)



def _minimize():
    x, y = root.winfo_x(), root.winfo_y()
    root.overrideredirect(False)
    root.update_idletasks()
    root.iconify()


def _on_restore(_=None):
    root.overrideredirect(True)
    root.update_idletasks()
    
    try:
        root.after(0, update_chance_label)
    except Exception:
        pass

root.bind("<Map>", _on_restore)

# Make the title icon show hand cursor for About
try:
    icon_label_title.config(cursor="hand2")
except Exception:
    pass

# Close button
close_btn = tk.Button(
    title_bar, text="✕", bg=BG_COLOR, relief="flat",
    activebackground=BG_COLOR, command=root.destroy, cursor="hand2"
)
close_btn.pack(side="right")

# Settings menu in the title bar
settings_mb = tk.Menubutton(title_bar, text="⚙", bg=BG_COLOR,
                            relief="flat", activebackground=BG_COLOR, cursor="hand2")
settings_menu = tk.Menu(settings_mb, tearoff=0)
settings_mb.config(menu=settings_menu)
settings_mb.pack(side="right", padx=(0, 4))

# shows which mode is active; drives radio checks
rolls_var = tk.IntVar(value=ROLLS_PER_MULTI)

# Drag window by title bar or icon
_drag = {"x": 0, "y": 0, "moved": False}


def _start_drag(e):
    _drag.update(x=e.x_root - root.winfo_x(), y=e.y_root - root.winfo_y(), moved=False)


def _on_drag(e):
    root.geometry(f"+{e.x_root - _drag['x']}+{e.y_root - _drag['y']}")
    _drag["moved"] = True

def _on_icon_release(e):
    # treat as click on the title icon (no drag) -> show About
    if not _drag.get("moved"):
        try:
            show_about()
        except Exception:
            pass

for w in (title_bar, icon_label_title):
    w.bind("<Button-1>", _start_drag)
    w.bind("<B1-Motion>", _on_drag)
# Click (no drag) on the left icon opens About
icon_label_title.bind("<ButtonRelease-1>", _on_icon_release)

# Spacer under titlebar
tk.Frame(root, height=30, bg=BG_COLOR).pack(fill="x")

# Lottery chance display
chance_label = tk.Label(root, text="", font=("Helvetica", 16))
chance_label.pack(pady=10)
# load chances from chances.txt immediately on launch
try:
    chance_label.after(0, update_chance_label)
except Exception:
    pass

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


def _fmt_hhmmss(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


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


def show_about():
    """Show a small About window (Spotify-style) when the title icon is clicked."""
    about = tk.Toplevel(root)
    about.title("About Dopamine Lottery")
    about.resizable(False, False)
    w, h = 360, 220
    ax = root.winfo_x() + (root.winfo_width() // 2) - (w // 2)
    ay = root.winfo_y() + (root.winfo_height() // 2) - (h // 2)
    about.geometry(f"{w}x{h}+{ax}+{ay}")

    bg = "#121212"; fg = "#ffffff"; sub = "#b3b3b3"
    frame = tk.Frame(about, bg=bg, padx=16, pady=16)
    frame.pack(fill="both", expand=True)

    # App icon (optional)
    try:
        _img = Image.open(resource_path("icon2.ico")).resize((32, 32))
        _tk = ImageTk.PhotoImage(_img)
        lbl_icon = tk.Label(frame, image=_tk, bg=bg)
        lbl_icon.image = _tk
        lbl_icon.grid(row=0, column=0, rowspan=2, sticky="w")
    except Exception:
        lbl_icon = tk.Label(frame, text="🎲", bg=bg, fg=fg)
        lbl_icon.grid(row=0, column=0, rowspan=2, sticky="w")

    lbl_title = tk.Label(frame, text="Dopamine Lottery", font=("Helvetica", 16, "bold"), bg=bg, fg=fg)
    lbl_title.grid(row=0, column=1, sticky="w", padx=(10, 0))
    lbl_ver = tk.Label(frame, text=f"Version {VERSION}", font=("Helvetica", 12), bg=bg, fg=sub)
    lbl_ver.grid(row=1, column=1, sticky="w", padx=(10, 0))
    lbl_copy = tk.Label(frame, text=f"copyright @ {COPYRIGHT}", font=("Helvetica", 11), bg=bg, fg=sub)
    lbl_copy.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(10, 0))

    # GitHub button with icon 
    try:
        gh_img = Image.open(resource_path("github.png")).resize((22, 22))
        gh_icon = ImageTk.PhotoImage(gh_img)
    except Exception:
        gh_icon = None

    def _open_repo():
        try:
            webbrowser.open(REPO_URL)
        except Exception:
            pass

    gh_btn = tk.Button(frame, text=" GitHub", image=gh_icon, compound="left",
                       cursor="hand2", relief="groove", command=_open_repo,
                       bg="#1f1f1f", fg="#ffffff", activebackground="#2a2a2a", activeforeground="#ffffff")
    gh_btn.image = gh_icon
    gh_btn.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=(12, 0))

    

    about.transient(root)
    about.grab_set()

# =============================
# Lottery
# =============================

def _show_or_hide_multi_button():
    """Safely show/hide the multi-roll button (only when Play is visible)."""
    current = load_chances()

    # Is the Play button managed by pack and visible?
    try:
        play_btn_packed = (play_button.winfo_manager() == 'pack' and play_button.winfo_ismapped())
    except Exception:
        play_btn_packed = False

    if not play_btn_packed:
        try:
            if play_multi_button.winfo_manager() == 'pack' and play_multi_button.winfo_ismapped():
                play_multi_button.pack_forget()
        except Exception:
            pass
        return

    try:
        if current >= ROLLS_PER_MULTI:
            if play_multi_button.winfo_manager() != 'pack' or not play_multi_button.winfo_ismapped():
                play_multi_button.pack(after=play_button, pady=2)
        else:
            if play_multi_button.winfo_manager() == 'pack' and play_multi_button.winfo_ismapped():
                play_multi_button.pack_forget()
    except Exception:
        try:
            if current >= ROLLS_PER_MULTI:
                play_multi_button.pack(pady=2)
            else:
                play_multi_button.pack_forget()
        except Exception:
            pass


def update_chance_label():
    current = load_chances()
    chance_label.config(text=f"Chances Left: {current}")
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
    """Multi-run uses dynamic ROLLS_PER_MULTI."""
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
            if index >= ROLLS_PER_MULTI:
                summary = "\n".join(results)
                label.config(text=summary, font=("Helvetica", 12), justify="left")
                return
            if not use_chance():
                result = f"Roll {index + 1}: ❌ No more chances!"
                results.append(result)
                label.config(text=result)
                play_fail_sound()
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
    if os.path.exists(LAST_APP_FILE):
        with open(LAST_APP_FILE, "r", encoding="utf-8") as f:
            path = f.read().strip()
        if os.path.exists(path):
            exe = os.path.basename(path)
            icon_img = extract_icon_image(path)
            if icon_img:
                last_icon_tk = ImageTk.PhotoImage(icon_img)
                last_button = tk.Button(resume_frame, image=last_icon_tk,
                                        command=lambda p=path: start_tracking_from_path(p), cursor="hand2")
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
    popup.after(2500, popup.destroy)  # short = snappier UI

    # play asynchronously so Stop stays responsive
    threading.Thread(
        target=lambda: winsound.PlaySound(
            resource_path("cheer.wav"),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        ),
        daemon=True
    ).start()


def toggle_pause():
    global tracking_paused
    tracking_paused = not tracking_paused
    pause_button.config(text=("▶ Resume Tracking" if tracking_paused else "⏸ Pause Tracking"))
    if not stop_button.winfo_ismapped():
        stop_button.pack(pady=2)


# =============================
# Tracking start/stop
# =============================

def _start_tracker(exe_name: str):
    """Start/restart the background tracker thread with instant UI updates."""
    global tracking_thread, tracking_stop_event

    # stop any previous tracker cleanly
    if tracking_thread and tracking_thread.is_alive():
        try:
            tracking_stop_event.set()
            tracking_thread.join(timeout=1.5)
        except Exception:
            pass

    tracking_stop_event = threading.Event()
    tracking_thread = threading.Thread(
        target=track_process,
        args=(
            exe_name,
            tracked_time_label,
            lambda: tracking_paused,
            show_cheer_popup,
            TEST_TIME_PER_CHANCE,
            tracking_stop_event,
        ),
        # push instant UI update when a chance is added
        kwargs=dict(
            rolls_per_multi=ROLLS_PER_MULTI,
            on_chance_update=update_chance_label,
        ),
        daemon=True
    )
    tracking_thread.start()


def start_tracking_from_path(path: str):
    global current_tracking, last_button, last_label

    if last_label:
        last_label.pack_forget(); last_label = None
    if last_button:
        last_button.pack_forget(); last_button = None

    exe = os.path.basename(path)
    current_tracking = exe
    tracking_label.config(text=f"Tracking: {exe}", fg="green")

    # Prefill UI with carry-over seconds
    try:
        saved = _load_progress(exe)
        tracked_time_label.config(text=f"Tracked Time: {_fmt_hhmmss(saved)}")
    except Exception:
        pass

    # Save last app path
    try:
        with open(LAST_APP_FILE, "w", encoding="utf-8") as f:
            f.write(path)
    except Exception:
        pass

    # Set icon
    icon_img = extract_icon_image(path)
    if icon_img:
        icon_tk = ImageTk.PhotoImage(icon_img)
        icon_label.config(image=icon_tk, text="")
        icon_label.image = icon_tk
    else:
        icon_label.config(image="", text="❓")
        icon_label.image = None

    # Start sound (short)
    winsound.Beep(600, 120)

    # Hide selection & play buttons
    for btn in (track_button, play_button, play_multi_button):
        try:
            if btn.winfo_ismapped():
                btn.pack_forget()
        except Exception:
            pass

    # Show pause/stop
    if not pause_button.winfo_ismapped():
        pause_button.config(text="⏸ Pause Tracking")
        pause_button.pack(pady=5)
    if not stop_button.winfo_ismapped():
        stop_button.pack(pady=2)

    _start_tracker(exe)


def start_tracking():
    global current_tracking, last_button, last_label

    if last_label:
        last_label.pack_forget(); last_label = None
    if last_button:
        last_button.pack_forget(); last_button = None

    filepath = filedialog.askopenfilename(
        title="Select EXE to Track",
        filetypes=[("Executable Files", "*.exe")]
    )
    if not filepath:
        return

    exe = os.path.basename(filepath)
    current_tracking = exe
    tracking_label.config(text=f"Tracking: {exe}", fg="green")

    # Prefill UI with carry-over seconds
    try:
        saved = _load_progress(exe)
        tracked_time_label.config(text=f"Tracked Time: {_fmt_hhmmss(saved)}")
    except Exception:
        pass

    # Set icon
    icon_img = extract_icon_image(filepath)
    if icon_img:
        icon_tk = ImageTk.PhotoImage(icon_img)
        icon_label.config(image=icon_tk, text="")
        icon_label.image = icon_tk
    else:
        icon_label.config(image="", text="❓")
        icon_label.image = None

    # Short start sound
    winsound.Beep(600, 120)

    # Hide selection & play buttons
    for btn in (track_button, play_button, play_multi_button):
        try:
            if btn.winfo_ismapped():
                btn.pack_forget()
        except Exception:
            pass

    # Show pause/stop
    if not pause_button.winfo_ismapped():
        pause_button.config(text="⏸ Pause Tracking")
        pause_button.pack(pady=5)
    if not stop_button.winfo_ismapped():
        stop_button.pack(pady=2)

    # Persist last app path
    try:
        with open(LAST_APP_FILE, "w", encoding="utf-8") as f:
            f.write(filepath)
    except Exception:
        pass

    _start_tracker(exe)


def stop_tracking():
    """Stop tracker thread and restore UI fast."""
    global tracking_paused, current_tracking, tracking_thread, tracking_stop_event

    tracking_paused = False
    current_tracking = None

    if tracking_stop_event:
        try:
            tracking_stop_event.set()
        except Exception:
            pass

    t = tracking_thread
    tracking_thread = None  # detach from UI immediately

    if t and t.is_alive():
        def _join_bg(th):
            try:
                th.join(timeout=5)
            except Exception:
                pass
        threading.Thread(target=_join_bg, args=(t,), daemon=True).start()

    winsound.PlaySound(None, winsound.SND_PURGE)

    tracking_label.config(text="Tracking: None", fg="gray")
    tracked_time_label.config(text="Tracked Time: 00:00:00")
    icon_label.config(image=""); icon_label.image = None

    if pause_button.winfo_ismapped():
        pause_button.pack_forget()
    if stop_button.winfo_ismapped():
        stop_button.pack_forget()

    # Hide multi to avoid pack-after errors when Play isn't packed yet
    try:
        if play_multi_button.winfo_manager() == 'pack' and play_multi_button.winfo_ismapped():
            play_multi_button.pack_forget()
    except Exception:
        pass

    track_button.pack(pady=20)
    play_button.pack(pady=10)

        # Refresh chances + 6/8/10 button immediately after stopping
    root.after_idle(update_chance_label)
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
track_button = tk.Button(root, text="🎯 Select App to Track", command=start_tracking, font=("Helvetica", 14), cursor="hand2")
track_button.pack(pady=20)

play_button = tk.Button(root, text="🎲 Play Lottery", command=run_lottery, font=("Helvetica", 18), cursor="hand2")
play_button.pack(pady=10)

# generic multi button; text set after loading settings
play_multi_button = tk.Button(root, text="10 🎲", font=("Helvetica", 14), command=run_lottery_multi, cursor="hand2")

pause_button = tk.Button(root, text="⏸ Pause Tracking", command=toggle_pause, font=("Helvetica", 12), cursor="hand2")
stop_button  = tk.Button(root, text="🛑 Stop Tracking",  command=stop_tracking,  font=("Helvetica", 12), cursor="hand2")

resume_frame = tk.Frame(root)
resume_frame.pack(pady=5)


# =============================
# Settings menu wiring (dynamic ROLLS_PER_MULTI)
# =============================

def _sync_settings_ui():
    """Reflect current setting (radio checks, multi-roll label, visibility)."""
    try:
        settings_mb.config(text="⚙")  # keep icon only
    except Exception:
        pass
    try:
        rolls_var.set(ROLLS_PER_MULTI)
    except Exception:
        pass
    if play_multi_button is not None:
        play_multi_button.config(text=f"{ROLLS_PER_MULTI} 🎲")
    # Defer the very first show/hide until the window is mapped, so winfo_ismapped() is reliable
    try:
        root.after_idle(update_chance_label)
    except Exception:
        pass


def _apply_rolls(n: int):
    """Apply & persist new ROLLS_PER_MULTI and refresh UI immediately.
    Restart tracker so downstream logic picks the new setting.
    """
    global ROLLS_PER_MULTI
    ROLLS_PER_MULTI = int(n)
    _settings_save_rolls(ROLLS_PER_MULTI)
    _sync_settings_ui()
    if current_tracking:
        try:
            if tracking_thread and tracking_thread.is_alive():
                tracking_stop_event.set()
                tracking_thread.join(timeout=2)
        except Exception:
            pass
        _start_tracker(current_tracking)

# Populate menu (examples 6/8/10)
# Populate menu (examples 6/8/10)
settings_menu.add_radiobutton(label="Relax (6)",  variable=rolls_var, value=6,  command=lambda: _apply_rolls(6))
settings_menu.add_radiobutton(label="Normal (8)", variable=rolls_var, value=8,  command=lambda: _apply_rolls(8))
settings_menu.add_radiobutton(label="十连 (10)",   variable=rolls_var, value=10, command=lambda: _apply_rolls(10))


# =============================
# Init (load settings before first label update)
# =============================
ROLLS_PER_MULTI = _settings_load_rolls()  # load from txt
_sync_settings_ui()
resume_last_tracking()
auto_refresh_chance()

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
