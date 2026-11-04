"""Native GNOME light/dark wallpaper selection and conditional restoration."""
import json
from pathlib import Path

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gio, GLib

from theme_settings import CONFIG_DIR, atomic_write
import diagnostics

BACKUP = CONFIG_DIR / "wallpaper-backup.json"
KEYS = ("picture-uri", "picture-uri-dark")


def background():
    return Gio.Settings.new("org.gnome.desktop.background")


def read_backup():
    if not BACKUP.exists():
        return {}
    data = json.loads(BACKUP.read_text())
    if not isinstance(data, dict) or not set(data) <= set(KEYS):
        raise ValueError(f"Invalid wallpaper restoration record: {BACKUP}")
    for entry in data.values():
        if (not isinstance(entry, dict) or set(entry) != {"original", "last"}
                or not isinstance(entry["last"], str)
                or (entry["original"] is not None and not isinstance(entry["original"], str))):
            raise ValueError(f"Invalid wallpaper restoration record: {BACKUP}")
    return data


def store(data):
    if data:
        atomic_write(BACKUP, json.dumps(data, indent=2) + "\n")
    else:
        BACKUP.unlink(missing_ok=True)


@diagnostics.traced("wallpaper", "choose")
def set_wallpaper(key, filename):
    if key not in KEYS:
        raise ValueError("Unsupported wallpaper slot.")
    path = Path(filename).expanduser().resolve(strict=True)
    with path.open("rb"):
        pass
    info = GdkPixbuf.Pixbuf.get_file_info(str(path))
    if info[0] is None:
        raise ValueError("Choose a readable image file (for example JPEG or PNG).")
    image = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 128, 128, True)
    if image is None:
        raise ValueError("The selected image could not be decoded.")
    settings = background()
    if not settings.is_writable(key):
        raise ValueError("Wallpaper is locked by system policy.")
    uri = path.as_uri()
    records = read_backup()
    user_value = settings.get_user_value(key)
    current = settings.get_string(key)
    old_records = records.copy()
    if key not in records or current != records[key]["last"]:
        records[key] = {"original": user_value.print_(True) if user_value is not None else None, "last": uri}
    else:
        records[key] = {**records[key], "last": uri}
    store(records)
    if not settings.set_string(key, uri):
        store(old_records)
        raise ValueError("GNOME refused the wallpaper change.")
    Gio.Settings.sync()
    diagnostics.event("wallpaper", "choose", "confirmed", slot=key)


@diagnostics.traced("wallpaper", "restore")
def restore_slot(key):
    if key not in KEYS:
        raise ValueError("Unsupported wallpaper slot.")
    records = read_backup()
    if key not in records:
        return
    settings = background()
    record = records[key]
    if settings.get_string(key) == record["last"]:
        if not settings.is_writable(key):
            raise ValueError("Wallpaper is locked; the restoration record was kept.")
        if record["original"] is None:
            settings.reset(key)
        elif not settings.set_value(key, GLib.Variant.parse(GLib.VariantType("s"), record["original"])):
            raise ValueError("GNOME refused wallpaper restoration; the backup was kept.")
        Gio.Settings.sync()
    del records[key]
    store(records)


def restore():
    for key in KEYS:
        restore_slot(key)
