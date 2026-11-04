"""Persistent settings and surface opacity shared by the builder and settings app."""
import json
import os
import re
import tempfile
from pathlib import Path

DEFAULT_TRANSPARENCY = 25
DEFAULT_GLASS_MODE = "frost"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "yaru-glass"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
APP_SETTINGS_FILE = CONFIG_DIR / "app-appearance.json"
SURFACE_TOKENS = frozenset({
    "panel_bg", "panel_hover", "panel_active", "menu_bg", "dialog_bg",
    "notification_bg", "submenu_bg", "hover_bg", "tile_bg", "tile_hover",
    "tile_active", "card_bg", "card_hover", "dock_bg", "entry_bg",
    "entry_hover", "entry_focus",
})
PRIMARY_SURFACES = frozenset({"panel_bg", "menu_bg", "dialog_bg", "notification_bg", "dock_bg"})


def validate_settings(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Settings must be an object.")
    result = {
        "transparency": validate_transparency(value.get("transparency")),
        "glass_mode": validate_glass_mode(value.get("glass_mode", DEFAULT_GLASS_MODE)),
    }
    for key in ("solid", "readability_boost", "background_blur"):
        flag = value.get(key, key == "background_blur")
        if type(flag) is not bool:
            raise ValueError(f"{key} must be boolean.")
        result[key] = flag
    return result


def validate_transparency(value: int) -> int:
    if type(value) is not int or not 0 <= value <= 50:
        raise ValueError("Transparency must be a whole number from 0 to 50.")
    return value


def validate_glass_mode(value: str) -> str:
    if value not in ("frost", "crystal"):
        raise ValueError("Glass mode must be frost or crystal.")
    return value


def load_settings(path: Path = SETTINGS_FILE) -> dict:
    try:
        text = path.read_text()
    except FileNotFoundError:
        return validate_settings({"transparency": DEFAULT_TRANSPARENCY})
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid settings in {path}: {exc.msg}") from exc
    if not isinstance(data, dict) or "transparency" not in data:
        raise ValueError(f"Invalid settings in {path}: missing transparency value.")
    try:
        return validate_settings(data)
    except ValueError as exc:
        raise ValueError(f"Invalid settings in {path}: {exc}") from exc


def load_transparency(path: Path = SETTINGS_FILE) -> int:
    return load_settings(path)["transparency"]


def atomic_write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb" if isinstance(content, bytes) else "w") as stream:
            stream.write(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def save_settings(value: dict, path: Path = SETTINGS_FILE) -> None:
    data = validate_settings(value)
    atomic_write(path, json.dumps(data, indent=2) + "\n")


def save_transparency(value: int, path: Path = SETTINGS_FILE) -> None:
    validate_transparency(value)
    data = load_settings(path)
    data["transparency"] = value
    save_settings(data, path)


def validate_app_appearance(value: dict) -> dict:
    if not isinstance(value, dict) or type(value.get("enabled")) is not bool:
        raise ValueError("App appearance must contain a boolean enabled value.")
    return {"enabled": value["enabled"],
            "transparency": validate_transparency(value.get("transparency"))}


def load_app_appearance(path: Path = APP_SETTINGS_FILE) -> dict:
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {"enabled": False, "transparency": DEFAULT_TRANSPARENCY}
    try:
        return validate_app_appearance(json.loads(text))
    except ValueError as exc:
        raise ValueError(f"Invalid app appearance in {path}: {exc}") from exc


def save_app_appearance(value: dict, path: Path = APP_SETTINGS_FILE) -> None:
    atomic_write(path, json.dumps(validate_app_appearance(value), indent=2) + "\n")


def boosted_opacity(alpha: float, enabled: bool) -> float:
    # Reduce the remaining backdrop contribution by half, without changing text.
    return alpha + (1 - alpha) / 2 if enabled else alpha


def material_highlight(mode: str, dark: bool) -> str:
    validate_glass_mode(mode)
    alpha = (.18 if dark else .32) if mode == "frost" else (.30 if dark else .48)
    return f"rgba(255, 255, 255, {alpha:.2f})"


def gtk_material(mode: str, dark: bool = False) -> str:
    return (f"background-image: linear-gradient(to bottom, {material_highlight(mode, dark)}, "
            "transparent 12px);\n"
            f"  box-shadow: inset 0 1px {material_highlight(mode, dark)};")


def app_opacity(value: dict, mode: str, dark: bool, boost: bool = False) -> float:
    validate_app_appearance(value)
    validate_glass_mode(mode)
    if not value["enabled"]:
        return 1.0
    floor = .80 if dark else .70
    alpha = 1 - (1 - floor) * value["transparency"] / 50 * (1 if mode == "crystal" else .7)
    return boosted_opacity(alpha, boost)


def preset_values(name: str) -> dict:
    if name not in ("Solid", "Balanced Frost", "Clear Crystal"):
        raise ValueError(f"Unknown appearance preset: {name}")
    solid = name == "Solid"
    level = 50 if name == "Clear Crystal" else 25
    return {
        "shell": {"transparency": 0 if solid else level,
                  "glass_mode": "crystal" if name == "Clear Crystal" else "frost", "solid": solid},
        "app": {"enabled": not solid, "transparency": level},
        "files": {"enabled": not solid, "transparency": level},
    }


def preset_name(snapshot: dict) -> str:
    for name in ("Solid", "Balanced Frost", "Clear Crystal"):
        if all(all(snapshot[section].get(key, False) == value for key, value in fields.items())
               for section, fields in preset_values(name).items()):
            return name
    return "Custom"


def shell_colors(colors: dict[str, str], transparency: int, glass_mode: str = "frost",
                 solid: bool = False, readability_boost: bool = False) -> dict[str, str]:
    validate_settings({"transparency": transparency, "glass_mode": glass_mode,
                       "solid": solid, "readability_boost": readability_boost})
    validate_glass_mode(glass_mode)
    factor = 1 - validate_transparency(transparency) / 100
    result = colors.copy()
    for token in SURFACE_TOKENS & colors.keys():
        match = re.fullmatch(r"rgba\(([\d\s,]+),\s*([\d.]+)\)", colors[token])
        if match:
            alpha = float(match.group(2)) * factor
            # A protective tint keeps normal popup text readable even over white/black.
            if token in {"menu_bg", "dialog_bg", "notification_bg", "panel_bg"}:
                dark = colors["fg"] == "#f5f5f7"
                floor = 0.70 if dark else 0.58
                alpha = floor + (1 - floor) * alpha * (0.55 if glass_mode == "crystal" else 1)
            if token in PRIMARY_SURFACES:
                alpha = 1 if solid else boosted_opacity(alpha, readability_boost)
            result[token] = f"rgba({match.group(1)}, {alpha:.6g})"
    result["material_highlight"] = material_highlight(glass_mode, colors["fg"] == "#f5f5f7")
    for token in ("panel_bg", "menu_bg", "dialog_bg", "notification_bg", "dock_bg"):
        match = re.fullmatch(r"rgba\(([\d\s,]+),\s*([\d.]+)\)", result[token])
        channels = [min(255, int(channel.strip()) + (5 if glass_mode == "frost" else 12))
                    for channel in match.group(1).split(",")]
        result[token + "_top"] = f"rgba({', '.join(map(str, channels))}, {match.group(2)})"
    return result
