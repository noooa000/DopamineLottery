import os, json, time, threading, winsound, psutil

# --- Paths ---
HERE = os.path.dirname(__file__)
DATA_FILE     = os.path.join(HERE, "app_data.json")   # unified store
CHANCE_FILE   = os.path.join(HERE, "chances.txt")     # legacy (for migration)
PROGRESS_FILE = os.path.join(HERE, "progress.json")   # legacy (for migration)
TIME_REQUIRED = 60 * 60  # 1 hour default

LOCK = threading.Lock()

# ---------- JSON helpers ----------
def _load_json():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_json(data: dict):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)

# ---------- One-time migration from legacy files ----------
def _migrate_if_needed():
    data = _load_json()
    changed = False

    # chances -> data["chances"]
    if "chances" not in data and os.path.exists(CHANCE_FILE):
        try:
            with open(CHANCE_FILE, "r", encoding="utf-8") as f:
                data["chances"] = int(f.read().strip() or "0")
            changed = True
            # optional cleanup:
            try: os.remove(CHANCE_FILE)
            except Exception: pass
        except Exception:
            data.setdefault("chances", 0)

    # progress -> data["progress"] (dict of exe -> seconds)
    if "progress" not in data and os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                legacy = json.load(f)
            if isinstance(legacy, dict):
                data["progress"] = {k: int(v) for k, v in legacy.items()}
                changed = True
                try: os.remove(PROGRESS_FILE)
                except Exception: pass
        except Exception:
            data.setdefault("progress", {})

    # ensure keys exist
    data.setdefault("chances", 0)
    data.setdefault("progress", {})

    if changed:
        _save_json(data)

# call migration once on import
_migrate_if_needed()

# ---------- Chances API (JSON-backed) ----------
def load_chances() -> int:
    with LOCK:
        data = _load_json()
        return int(data.get("chances", 0))

def _save_chances(n: int):
    with LOCK:
        data = _load_json()
        data["chances"] = max(0, int(n))
        _save_json(data)

def add_chance(k: int = 1):
    with LOCK:
        _save_chances(load_chances() + int(k))

def use_chance() -> bool:
    with LOCK:
        c = load_chances()
        if c <= 0:
            return False
        _save_chances(c - 1)
        return True

# ---------- Progress carry-over (JSON-backed) ----------
def _load_progress(exe_name: str) -> int:
    with LOCK:
        data = _load_json()
        return int(data.get("progress", {}).get(exe_name, 0))

def _save_progress(exe_name: str, seconds: int) -> None:
    with LOCK:
        data = _load_json()
        prog = data.get("progress", {})
        prog[exe_name] = int(max(0, seconds))
        data["progress"] = prog
        _save_json(data)

# ---------- Helpers ----------
def _fmt_hhmmss(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def _play_cat_sound():
    wav_path = os.path.join(HERE, "good.wav")
    if os.path.exists(wav_path):
        winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)

# ---------- Main tracking loop ----------
def track_process(target_process, time_label, is_paused_func, cheer_callback, *,
                  rolls_per_multi, time_required=None, stop_event=None):
    """
    target_process: exe name string (e.g., 'notepad.exe')
    time_label: Tk label to update
    is_paused_func: callable -> bool
    cheer_callback: callable() for big milestone
    rolls_per_multi: int (milestone count)
    time_required: seconds for +1 chance (default TIME_REQUIRED)
    stop_event: threading.Event to stop loop
    """
    if stop_event is None:
        stop_event = threading.Event()
    if time_required is None:
        time_required = TIME_REQUIRED

    tracked_time = _load_progress(target_process)
    total_tracked_time = 0

    while not stop_event.is_set():
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

            # FIXED INDENTATION: these lines must be inside the while-block
            while tracked_time >= time_required:
                tracked_time -= time_required
                add_chance()

                total = load_chances()
                if total % rolls_per_multi == 0:
                    # milestone each multiple of rolls_per_multi
                    time_label.after(0, lambda rp=rolls_per_multi:
                        time_label.config(text=f"🎉 {rp} chances reached!")
                    )
                    cheer_callback()
                else:
                    _play_cat_sound()
                    time_label.after(0, lambda: time_label.config(text="🎉 1 chance added!"))

        _save_progress(target_process, tracked_time)
        time.sleep(1)
