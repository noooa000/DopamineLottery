import os

CHANCE_FILE = os.path.join(os.path.dirname(__file__), "chances.txt")


def load_chances():
    try:
        with open(CHANCE_FILE, "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return 0

def save_chances(chances):
    with open(CHANCE_FILE, "w") as f:
        f.write(str(chances))

def add_chance():
    chances = load_chances()
    chances += 1
    save_chances(chances)

def use_chance():
    chances = load_chances()
    if chances > 0:
        chances -= 1
        save_chances(chances)
        return True
    return False