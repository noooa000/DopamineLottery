import psutil, os, json, time, winsound
import tkinter as tk
from tkinter import filedialog, messagebox

PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "progress.json")
CHANCE_FILE   = os.path.join(os.path.dirname(__file__), "chances.txt")
TIME_REQUIRED = 60 * 60  # 1 hour

# ---------------- chance utils ----------------
def load_chances():
    try:
        with open(CHANCE_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return 0

def save_chances(ch):
    with open(CHANCE_FILE, "w", encoding="utf-8") as f:
        f.write(str(ch))

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
def _fmt_hhmmss(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _play_cat_sound():
    wav_path = os.path.join(os.path.dirname(__file__), "cat.wav")
    if os.path.exists(wav_path):
        winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)

# ---------------- main loop ----------------
# add a stop_event param and honor it
def track_process(target_process, time_label, is_paused_func, cheer_callback,
                  time_required=None, stop_event=None):                       # ★
    import time, psutil, threading
    if stop_event is None:                                                    # ★
        stop_event = threading.Event()                                        # ★
    if time_required is None:
        time_required = TIME_REQUIRED

    tracked_time = _load_progress(target_process)
    total_tracked_time = 0

    while not stop_event.is_set():                                            # ★ loop exits on stop
        if is_paused_func():
            time.sleep(1)
            continue

        running = any((p.info.get('name') or '').lower() == target_process.lower()
                      for p in psutil.process_iter(['name']))
        if running:
            tracked_time += 1
            total_tracked_time += 1
            hhmmss = _fmt_hhmmss(total_tracked_time)
            time_label.after(0, lambda t=hhmmss: time_label.config(text=f"Tracked Time: {t}"))

            while tracked_time >= time_required:
                tracked_time -= time_required
                add_chance()
                
                total = load_chances()
                if total == 10:
                    time_label.after(0, lambda: time_label.config(text="🎉 10 chances reached!"))
                    cheer_callback()
                else:
                    _play_cat_sound()
                    time_label.after(0, lambda: time_label.config(text="🎉 1 chance added!"))

        _save_progress(target_process, tracked_time)
        time.sleep(1)
