import psutil, os, json, time, winsound
import tkinter as tk
from tkinter import filedialog, messagebox
import sys, shutil  

APP_NAME = "DopamineLottery"

# Stable, user-writable folder (persists across reboots & onefile runs)
def _app_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path

APP_DIR = _app_dir()

PROGRESS_FILE = os.path.join(APP_DIR, "progress.json")
CHANCE_FILE   = os.path.join(APP_DIR, "chances.txt")
TIME_REQUIRED = 60 * 60  # 1 hour

# ---------------- chance utils ----------------
def load_chances():
    try:
        with open(CHANCE_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return 0

def save_chances(ch):
    try:
        with open(CHANCE_FILE, "w", encoding="utf-8") as f:
            f.write(str(int(ch)))
    except Exception:
        pass

def add_chance():
    save_chances(load_chances() + 1)

def use_chance():
    ch = load_chances()
    if ch > 0:
        save_chances(ch - 1)
        return True
    return False

# ---------------- carry-over seconds ----------------
def _load_progress(exe_name: str) -> int:
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return int(data.get(exe_name, 0))
    except Exception:
        pass
    return 0

def _save_progress(exe_name: str, seconds: int) -> None:
    try:
        data = {}
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[exe_name] = int(max(0, seconds))
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

# ---------------- helpers ----------------
def _fmt_hhmmss(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _find_asset(name: str) -> str | None:
    """Search APP_DIR, script dir, PyInstaller _MEIPASS, and CWD."""
    candidates = [
        os.path.join(APP_DIR, name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), name),
        (os.path.join(getattr(sys, "_MEIPASS", ""), name)
         if getattr(sys, "_MEIPASS", None) else None),
        os.path.join(os.getcwd(), name),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

def _ensure_asset(name: str):
    """If bundled file exists but not in APP_DIR, copy it there once."""
    try:
        src = _find_asset(name)
        if not src:
            return
        dst = os.path.join(APP_DIR, name)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
    except Exception:
        pass

# call once at import so files are available in APP_DIR
_ensure_asset("good.wav")
_ensure_asset("cheer.wav")

def _play_cat_sound():
    path = _find_asset("good.wav")
    if path:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    else:
        # tiny fallback so you still hear something
        winsound.Beep(900, 120)

# ---------------- main loop ----------------
# Celebrate on every multiple of `rolls_per_multi`; start UI from saved seconds
# and honor an external stop_event.
# tracker.py
def track_process(
    target_process,
    time_label,
    is_paused_func,
    cheer_callback,
    time_required=None,
    stop_event=None,
    *,
    rolls_per_multi: int = 10,
    on_chance_update=None,         # ★ calls back to update the chance label & buttons
):
    import threading, psutil, time

    if stop_event is None:
        stop_event = threading.Event()
    if time_required is None:
        time_required = TIME_REQUIRED

    try:
        rolls_per_multi = max(1, int(rolls_per_multi))
    except Exception:
        rolls_per_multi = 10

    tracked_time = _load_progress(target_process)
    total_tracked_time = tracked_time

    # Show carry-over immediately
    try:
        hhmmss = _fmt_hhmmss(total_tracked_time)
        time_label.after(0, lambda t=hhmmss: time_label.config(text=f"Tracked Time: {t}"))
    except Exception:
        pass

    target_lower = (target_process or "").lower()

    while not stop_event.is_set():
        if is_paused_func():
            if stop_event.wait(0.2):   # ★ more responsive while paused
                break
            continue

        # Is target process running?
        try:
            running = any(
                (p.info.get('name') or '').lower() == target_lower
                for p in psutil.process_iter(['name'])
            )
        except Exception:
            running = False

        if running:
            tracked_time += 1
            total_tracked_time += 1

            # hh:mm:ss tick
            try:
                hhmmss = _fmt_hhmmss(total_tracked_time)
                time_label.after(0, lambda t=hhmmss: time_label.config(text=f"Tracked Time: {t}"))
            except Exception:
                pass

            # Convert tracked seconds -> chances
            while tracked_time >= time_required:
                tracked_time -= time_required
                add_chance()

                # ★ Instant UI refresh for chance label & multi button
                if on_chance_update:
                    try:
                        time_label.after(0, on_chance_update)
                    except Exception:
                        pass

                total = load_chances()
                if total % rolls_per_multi == 0:
                    time_label.after(0, lambda n=rolls_per_multi:
                        time_label.config(text=f"🎉 {n} chances reached!"))
                    time_label.after(0, cheer_callback)
                else:
                    _play_cat_sound()
                    time_label.after(0, lambda:
                        time_label.config(text="🎉 1 chance added!"))

        _save_progress(target_process, tracked_time)

        # ★ Responsive stop (don’t hard-sleep a full second)
        if stop_event.wait(1.0):
            break
