"""Opt-in, Files-only GTK4 overrides in the existing managed theme stylesheets."""
import fcntl
import json
from pathlib import Path

import diagnostics
from theme_settings import (
    CONFIG_DIR, atomic_write, load_app_appearance, load_settings,
    validate_app_appearance, validate_glass_mode, boosted_opacity, gtk_material,
)

SETTINGS_FILE = CONFIG_DIR / "files-appearance.json"
THEMES = Path.home() / ".local/share/themes"
CSS_PATHS = tuple(THEMES / name / "gtk-4.0/libadwaita.css"
                  for name in ("Yaru-Glass", "Yaru-Glass-dark"))
START = "/* BEGIN YARU FILES APPEARANCE */"
END = "/* END YARU FILES APPEARANCE */"


def load():
    return load_app_appearance(SETTINGS_FILE)


def opacity(value, mode, boost=False):
    validate_app_appearance(value)
    validate_glass_mode(mode)
    if not value["enabled"]:
        return 1.0
    return boosted_opacity(1 - .30 * value["transparency"] / 50 * (1 if mode == "crystal" else .7), boost)


def css(value, mode, boost=False):
    validate_app_appearance(value)
    validate_glass_mode(mode)
    if not value["enabled"]:
        return ""
    # A single root tint avoids accumulating alpha across nested GTK surfaces.
    alpha = opacity(value, mode, boost)
    return f"""{START}
window.nautilus-window {{
  background-color: alpha(@window_bg_color, {alpha:.6f});
  {gtk_material(mode)}
}}
window.nautilus-window overlay-split-view > .sidebar-pane,
window.nautilus-window overlay-split-view > .content-pane,
window.nautilus-window overlay-split-view > .sidebar-pane > toolbarview,
window.nautilus-window overlay-split-view > .sidebar-pane placessidebar,
window.nautilus-window overlay-split-view > .sidebar-pane .navigation-sidebar,
window.nautilus-window overlay-split-view > .sidebar-pane > toolbarview > .top-bar,
window.nautilus-window overlay-split-view > .content-pane > toolbarview > .top-bar,
window.nautilus-window overlay-split-view > .sidebar-pane headerbar,
window.nautilus-window overlay-split-view > .content-pane headerbar {{
  background-color: transparent;
  background-image: none;
}}
window.nautilus-window overlay-split-view > .sidebar-pane {{
  color: @window_fg_color;
}}
window.nautilus-window overlay-split-view > .content-pane .view {{
  background-color: @view_bg_color;
}}
{END}
"""


def replace_css(text, value, mode, boost=False):
    if START in text:
        before, rest = text.split(START, 1)
        if END not in rest:
            raise ValueError("Files appearance CSS block is incomplete; rebuild the theme.")
        _, after = rest.split(END, 1)
        text = before.rstrip() + after
    return text.rstrip() + "\n" + css(value, mode, boost)


def refresh(mode):
    """Caller holds the shared build lock."""
    value = load()
    boost = load_settings()["readability_boost"]
    previous = {path: path.read_text() for path in CSS_PATHS}
    changed = False
    try:
        for path, text in previous.items():
            updated = replace_css(text, value, mode, boost)
            if updated != text:
                atomic_write(path, updated)
                changed = True
    except (OSError, ValueError) as exc:
        restore_css(previous, exc)
    if changed:
        diagnostics.event("files", "apply", "success", mode=mode)


def restore_css(previous, cause):
    diagnostics.event("files", "rollback", "start", level="WARNING", error=cause)
    errors = []
    for path, text in previous.items():
        try:
            atomic_write(path, text)
        except OSError as rollback:
            errors.append(str(rollback))
    detail = " Previous CSS restored." if not errors else " Restoration errors: " + "; ".join(errors)
    diagnostics.event("files", "rollback", "failure" if errors else "success",
                      level="ERROR" if errors else "INFO", count=len(errors))
    raise RuntimeError(f"Could not update Files appearance: {cause}.{detail}") from cause


@diagnostics.traced("files", "apply")
def save(value):
    value = validate_app_appearance(value)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with (CONFIG_DIR / "build.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        settings = load_settings()
        mode = settings["glass_mode"]
        previous = {path: path.read_text() for path in CSS_PATHS}
        updated = {path: replace_css(text, value, mode, settings["readability_boost"]) for path, text in previous.items()}
        try:
            for path, text in updated.items():
                atomic_write(path, text)
            atomic_write(SETTINGS_FILE, json.dumps(value, indent=2) + "\n")
        except (OSError, ValueError) as exc:
            restore_css(previous, exc)
