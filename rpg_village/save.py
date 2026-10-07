"""Save / load: several JSON slots kept in the player's user folder (works from the .exe too).

Windows: %APPDATA%\\Hearthmoor\\      other systems: ~/.hearthmoor/
Files:   save_1.json ... save_5.json (manual slots) and autosave.json (written automatically).
An old single-slot save.json is migrated into slot 1 the first time the game looks.
"""
import json
import os
import time

VERSION = 1
SLOTS = 5            # manual slots, numbered 1..SLOTS
AUTO = "auto"        # the autosave slot id


def save_dir():
    base = os.environ.get("APPDATA")
    if base:
        return os.path.join(base, "Hearthmoor")
    return os.path.join(os.path.expanduser("~"), ".hearthmoor")


def slot_ids(include_auto=True):
    ids = list(range(1, SLOTS + 1))
    return ([AUTO] if include_auto else []) + ids


def save_path(slot=1):
    name = "autosave.json" if slot == AUTO else "save_%d.json" % int(slot)
    return os.path.join(save_dir(), name)


def _migrate():
    """Move the legacy single save.json into slot 1 (only when slot 1 is empty)."""
    old = os.path.join(save_dir(), "save.json")
    if os.path.isfile(old) and not os.path.isfile(save_path(1)):
        try:
            os.replace(old, save_path(1))
        except OSError:
            pass


def exists(slot):
    _migrate()
    return os.path.isfile(save_path(slot))


def any_exists():
    return any(exists(s) for s in slot_ids())


def write(data, slot=1):
    """Write atomically so a crash mid-save can never corrupt the old save."""
    os.makedirs(save_dir(), exist_ok=True)
    data = dict(data, version=VERSION, saved_at=time.time())
    path = save_path(slot)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def read(slot=1):
    """Returns the save dict, or None when missing / unreadable."""
    _migrate()
    try:
        with open(save_path(slot), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data.get("version") == VERSION else None
    except (OSError, ValueError):
        return None


def delete(slot):
    try:
        os.remove(save_path(slot))
        return True
    except OSError:
        return False


def info(slot):
    """Small summary for the slot list: None if empty, {'broken': True} if unreadable."""
    if not exists(slot):
        return None
    d = read(slot)
    if d is None:
        return dict(broken=True)
    return dict(broken=False, saved_at=d.get("saved_at", 0), meta=d.get("meta", {}),
                hp=d.get("hp"), max_hp=d.get("max_hp"), time=d.get("time"),
                scene=d.get("scene"), level=d.get("level"), kills=d.get("kills", 0),
                boss=d.get("boss_defeated", False))


def latest():
    """Slot id of the most recently written valid save, or None."""
    best, best_t = None, -1
    for s in slot_ids():
        i = info(s)
        if i and not i["broken"] and i["saved_at"] > best_t:
            best, best_t = s, i["saved_at"]
    return best
