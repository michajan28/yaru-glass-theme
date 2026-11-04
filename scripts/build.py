#!/usr/bin/env python3
"""Build the Yaru-Glass / Yaru-Glass-dark theme pair.

Themes are generated into ~/.local/share/themes from the system Yaru-blue
theme (GTK resources are linked, not copied) plus the overrides in ./src/theme.
Re-run after Yaru package updates:  ~/.local/share/yaru-glass/scripts/build.py
"""
import argparse
import fcntl
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src/yaru_glass"))
import files_appearance
import diagnostics

from theme_settings import (
    CONFIG_DIR, atomic_write, load_settings, save_settings, shell_colors,
    validate_settings, validate_app_appearance, load_app_appearance, save_app_appearance,
)

HOME = Path.home()
SRC = ROOT / "src/theme"
THEMES_DIR = HOME / ".local/share/themes"
SYS_THEMES = Path("/usr/share/themes")
SYS_SHELL = Path("/usr/share/gnome-shell/theme")
YARU_ACCENT = "#0073E5"

COMMON_TL = {
    "glass_tl_close": "#ff5f57",
    "glass_tl_minimize": "#febc2e",
    "glass_tl_maximize": "#28c840",
}

VARIANTS = [
    {
        "name": "Yaru-Glass",
        "base": "Yaru-blue",
        "dark": False,
        "gtk_colors": {
            "glass_accent": "#007AFF",
            "glass_tl_rim": "rgba(0, 0, 0, 0.18)",
            "glass_tl_inactive": "#d6d6d6",
            "glass_sidebar_selected": "rgba(0, 0, 0, 0.09)",
        },
        "shell": {
            "variant_suffix": "",
            "accent": "#007AFF",
            "accent_rgb": "0, 122, 255",
            "accent_hover": "#1a87ff",
            "accent_active": "#0062cc",
            "accent_glow": "rgba(0, 122, 255, 0.35)",
            "fg": "#1d1d1f",
            "fg_dim": "rgba(29, 29, 31, 0.5)",
            "panel_bg": "rgba(246, 246, 248, 0.62)",
            "panel_fg": "#1d1d1f",
            "panel_border": "rgba(0, 0, 0, 0.06)",
            "panel_hover": "rgba(0, 0, 0, 0.08)",
            "panel_active": "rgba(0, 0, 0, 0.14)",
            "menu_bg": "rgba(246, 246, 248, 0.80)",
            "dialog_bg": "rgba(246, 246, 248, 0.92)",
            "notification_bg": "rgba(246, 246, 248, 0.84)",
            "glass_border": "rgba(0, 0, 0, 0.10)",
            "glass_highlight": "rgba(255, 255, 255, 0.60)",
            "glass_shadow": "rgba(0, 0, 0, 0.18)",
            "submenu_bg": "rgba(0, 0, 0, 0.04)",
            "separator": "rgba(0, 0, 0, 0.10)",
            "hover_bg": "rgba(0, 0, 0, 0.07)",
            "tile_bg": "rgba(0, 0, 0, 0.06)",
            "tile_hover": "rgba(0, 0, 0, 0.10)",
            "tile_active": "rgba(0, 0, 0, 0.15)",
            "card_bg": "rgba(255, 255, 255, 0.55)",
            "card_hover": "rgba(255, 255, 255, 0.78)",
            "dock_bg": "rgba(255, 255, 255, 0.30)",
            "dock_border": "rgba(255, 255, 255, 0.55)",
            "dot": "rgba(0, 0, 0, 0.60)",
            "entry_bg": "rgba(255, 255, 255, 0.60)",
            "entry_hover": "rgba(255, 255, 255, 0.75)",
            "entry_focus": "#ffffff",
            "slider_trough": "rgba(0, 0, 0, 0.12)",
        },
    },
    {
        "name": "Yaru-Glass-dark",
        "base": "Yaru-blue-dark",
        "dark": True,
        "gtk_colors": {
            "glass_accent": "#0A84FF",
            "glass_tl_rim": "rgba(0, 0, 0, 0.30)",
            "glass_tl_inactive": "#56565a",
            "glass_sidebar_selected": "rgba(255, 255, 255, 0.10)",
        },
        "shell": {
            "variant_suffix": "-dark",
            "accent": "#0A84FF",
            "accent_rgb": "10, 132, 255",
            "accent_hover": "#3395ff",
            "accent_active": "#0070e0",
            "accent_glow": "rgba(10, 132, 255, 0.40)",
            "fg": "#f5f5f7",
            "fg_dim": "rgba(245, 245, 247, 0.5)",
            "panel_bg": "rgba(28, 28, 30, 0.45)",
            "panel_fg": "#f5f5f7",
            "panel_border": "rgba(255, 255, 255, 0.06)",
            "panel_hover": "rgba(255, 255, 255, 0.12)",
            "panel_active": "rgba(255, 255, 255, 0.20)",
            "menu_bg": "rgba(36, 36, 38, 0.80)",
            "dialog_bg": "rgba(36, 36, 38, 0.94)",
            "notification_bg": "rgba(36, 36, 38, 0.86)",
            "glass_border": "rgba(255, 255, 255, 0.12)",
            "glass_highlight": "rgba(255, 255, 255, 0.08)",
            "glass_shadow": "rgba(0, 0, 0, 0.45)",
            "submenu_bg": "rgba(255, 255, 255, 0.05)",
            "separator": "rgba(255, 255, 255, 0.12)",
            "hover_bg": "rgba(255, 255, 255, 0.10)",
            "tile_bg": "rgba(255, 255, 255, 0.10)",
            "tile_hover": "rgba(255, 255, 255, 0.15)",
            "tile_active": "rgba(255, 255, 255, 0.22)",
            "card_bg": "rgba(255, 255, 255, 0.07)",
            "card_hover": "rgba(255, 255, 255, 0.12)",
            "dock_bg": "rgba(30, 30, 32, 0.35)",
            "dock_border": "rgba(255, 255, 255, 0.16)",
            "dot": "rgba(255, 255, 255, 0.75)",
            "entry_bg": "rgba(255, 255, 255, 0.10)",
            "entry_hover": "rgba(255, 255, 255, 0.14)",
            "entry_focus": "rgba(30, 30, 32, 0.90)",
            "slider_trough": "rgba(255, 255, 255, 0.16)",
        },
    },
]


def replace_accent(text: str, accent: str, accent_rgb: str) -> str:
    text = re.sub(re.escape(YARU_ACCENT), accent, text, flags=re.IGNORECASE)
    text = re.sub(r"-st-accent-(fg-)?color\b",
                  lambda match: "#ffffff" if match.group(1) else accent, text)
    return re.sub(r"rgba\(\s*0,\s*115,\s*229,", f"rgba({accent_rgb},", text)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def link(path: Path, target: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        path.unlink()
    path.symlink_to(target)


def build_gtk(v: dict, out: Path, glass_mode: str | None = None) -> None:
    base = v["base"]
    colors = {**COMMON_TL, **v["gtk_colors"]}
    color_css = "".join(f"@define-color {k} {val};\n" for k, val in colors.items())

    gtk3 = out / "gtk-3.0"
    link(gtk3 / "gtk.gresource", SYS_THEMES / base / "gtk-3.0/gtk.gresource")
    write(gtk3 / "colors.css", color_css)
    shutil.copy(SRC / "gtk-3.0/glass.css", gtk3 / "glass.css")
    write(gtk3 / "gtk.css",
          f'@import url("resource:///com/ubuntu/themes/{base}/3.0/gtk.css");\n'
          '@import url("colors.css");\n@import url("glass.css");\n')
    # Apps that explicitly request a dark variant (gtk-dark.css) get dark traffic-light greys.
    dark_colors = {**COMMON_TL, **VARIANTS[1]["gtk_colors"]}
    write(gtk3 / "colors-dark.css",
          "".join(f"@define-color {k} {val};\n" for k, val in dark_colors.items()))
    write(gtk3 / "gtk-dark.css",
          f'@import url("resource:///com/ubuntu/themes/{base}/3.0/gtk-dark.css");\n'
          '@import url("colors-dark.css");\n@import url("glass.css");\n')

    gtk4 = out / "gtk-4.0"
    link(gtk4 / "gtk.gresource", SYS_THEMES / base / "gtk-4.0/gtk.gresource")
    write(gtk4 / "gtk.css", f'@import url("resource:///com/ubuntu/themes/{base}/4.0/gtk.css");\n')
    write(gtk4 / "gtk-dark.css", f'@import url("resource:///com/ubuntu/themes/{base}/4.0/gtk-dark.css");\n')
    write(gtk4 / "libadwaita.css", files_appearance.replace_css(
        (SRC / "gtk-4.0/libadwaita.css").read_text(),
        files_appearance.load(), glass_mode or load_settings()["glass_mode"]))

    link(out / "gtk-2.0", SYS_THEMES / base / "gtk-2.0")


def build_shell(v: dict, out: Path, transparency: int, css_only: bool = False,
                glass_mode: str = "frost", solid: bool = False, readability_boost: bool = False) -> None:
    candidates = (SYS_SHELL / v["base"], SYS_SHELL / ("Yaru-dark" if v["dark"] else "Yaru"))
    base_dir = next((path for path in candidates if (path / "gnome-shell.css").is_file()), None)
    if base_dir is None:
        raise FileNotFoundError(
            f"Missing Yaru Shell stylesheet in {candidates[0]} or {candidates[1]}; "
            "install yaru-theme-gnome-shell.")
    shell_out = out / "gnome-shell"
    if css_only and not (shell_out / "gnome-shell.css").is_file():
        raise FileNotFoundError(f"Theme not installed at {out}. Run install.sh first.")
    if not css_only and shell_out.exists():
        shutil.rmtree(shell_out)
    shell_out.mkdir(parents=True, exist_ok=True)

    s = shell_colors(v["shell"], transparency, glass_mode, solid, readability_boost)
    for asset in ([] if css_only else base_dir.iterdir()):
        if asset.name == "gnome-shell.css" or not asset.is_file():
            continue
        if asset.suffix == ".svg":
            write(shell_out / asset.name,
                  replace_accent(asset.read_text(), s["accent"], s["accent_rgb"]))
        else:
            shutil.copy(asset, shell_out / asset.name)

    css = (base_dir / "gnome-shell.css").read_text()

    def local_url(m: re.Match) -> str:
        name = m.group(1)
        return f'url("{name}")' if (shell_out / name).exists() else m.group(0)

    css = re.sub(r'url\("resource:///org/gnome/shell/theme/([^"/]+)"\)', local_url, css)
    css = replace_accent(css, s["accent"], s["accent_rgb"])
    overrides = Template((SRC / "gnome-shell/glass.css.in").read_text()).substitute(s)
    atomic_write(shell_out / "gnome-shell.css", css + "\n\n" + overrides)


def build_index(v: dict, out: Path) -> None:
    write(out / "index.theme", f"""[Desktop Entry]
Name={v['name']}
Type=X-GNOME-Metatheme
Comment=Yaru with a translucent glass look ({'dark' if v['dark'] else 'light'})
Encoding=UTF-8

[X-GNOME-Metatheme]
GtkTheme={v['name']}
MetacityTheme={v['base']}
IconTheme=Yaru
CursorTheme=Yaru
CursorSize=24
X-Yaru-Dark={'true' if v['dark'] else 'false'}
X-Yaru-Accent-Name=blue
X-Yaru-Accent-Color={v['gtk_colors']['glass_accent']}
""")


def reload_shell_theme() -> bool:
    """Make User Themes re-read the stylesheet if one of our themes is active."""
    key = "/org/gnome/shell/extensions/user-theme/name"
    current = subprocess.run(["dconf", "read", key], capture_output=True, text=True, check=True).stdout.strip()
    if current.strip("'") in {v["name"] for v in VARIANTS}:
        try:
            subprocess.run(["dconf", "write", key, "''"], check=True)
        finally:
            subprocess.run(["dconf", "write", key, current], check=True)
        return True
    return False


def project_theme_active() -> bool:
    from gi.repository import Gio
    return Gio.Settings.new("org.gnome.desktop.interface").get_string("gtk-theme") in {v["name"] for v in VARIANTS}


@diagnostics.traced("worker", "apply")
def apply_locked(patch: dict, shell_only: bool, save: bool) -> dict:
    """Apply a validated partial update. Caller owns build.lock."""
    import managed_glass
    paths = {name: CONFIG_DIR / filename for name, filename in
             (("shell", "settings.json"), ("app", "app-appearance.json"), ("files", "files-appearance.json"))}
    validators = {"shell": validate_settings, "app": validate_app_appearance, "files": validate_app_appearance}
    allowed = {"shell": {"transparency", "glass_mode", "solid", "readability_boost", "background_blur"},
               "app": {"enabled", "transparency"}, "files": {"enabled", "transparency"}}
    if not isinstance(patch, dict) or patch.keys() - allowed.keys():
        raise ValueError("Unknown appearance section.")
    for section, fields in patch.items():
        if not isinstance(fields, dict) or fields.keys() - allowed[section]:
            raise ValueError(f"Unknown fields in {section} appearance.")
    old = {}
    for section in paths:
        try:
            old[section] = (validate_settings(load_settings()) if section == "shell"
                            else load_app_appearance(paths[section]))
        except ValueError as exc:
            if set(patch.get(section, {})) != allowed[section]:
                raise ValueError(f"{exc} Reset the affected section to replace its invalid settings.") from exc
            old[section] = validators[section](patch[section])
            print(f"Replacing invalid {section} configuration after explicit complete update: {exc}",
                  file=sys.stderr)
    desired = {section: validators[section]({**value, **patch.get(section, {})})
               for section, value in old.items()}
    shell = desired["shell"]
    shell_changed = not shell_only or bool(patch.get("shell")) or not patch
    files_changed = not shell_only or shell_changed or bool(patch.get("files"))
    active = project_theme_active()
    effects_snapshot = None
    if active and shell_changed:
        keys = managed_glass.desired_keys(shell["glass_mode"], shell["background_blur"], shell["solid"])
        managed_glass.verify_capabilities(keys)
        effects_snapshot = ({key: managed_glass.read_key(key) for key in keys}, managed_glass.pipelines())
    css_paths = []
    if shell_changed:
        css_paths += [THEMES_DIR / v["name"] / "gnome-shell/gnome-shell.css" for v in VARIANTS]
    gtk_paths = [THEMES_DIR / v["name"] / "gtk-4.0/libadwaita.css" for v in VARIANTS]
    if files_changed:
        css_paths += gtk_paths
    tracked = css_paths + [paths[section] for section in patch]
    if effects_snapshot:
        tracked.append(managed_glass.BACKUP)
    before = {path: path.read_bytes() if path.exists() else None for path in tracked}
    reload_requested = False
    try:
        if shell_changed:
            for v in VARIANTS:
                out = THEMES_DIR / v["name"]
                if not shell_only:
                    out.mkdir(parents=True, exist_ok=True)
                    build_index(v, out)
                    build_gtk(v, out, shell["glass_mode"])
                build_shell(v, out, shell["transparency"], css_only=shell_only,
                            glass_mode=shell["glass_mode"], solid=shell["solid"],
                            readability_boost=shell["readability_boost"])
            if active:
                managed_glass.apply(shell["glass_mode"], shell["background_blur"], shell["solid"])
        if files_changed:
            for path in gtk_paths:
                if path.exists():
                    atomic_write(path, files_appearance.replace_css(
                        path.read_text(), desired["files"], shell["glass_mode"], shell["readability_boost"]))
                elif patch.get("files"):
                    raise FileNotFoundError(f"Theme not installed at {path}. Run install.sh first.")
        if shell_changed:
            reload_requested = bool(reload_shell_theme())
        if save:
            for section in patch:
                if section == "shell":
                    save_settings(shell, paths[section])
                else:
                    save_app_appearance(desired[section], paths[section])
    except (*managed_glass.ERRORS, RuntimeError) as exc:
        diagnostics.event("worker", "rollback", "start", level="WARNING", error=exc)
        errors = []
        for path, content in before.items():
            try:
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, content)
            except OSError as rollback:
                errors.append(str(rollback))
        if effects_snapshot:
            try:
                managed_glass.restore_snapshot(*effects_snapshot)
            except RuntimeError as rollback:
                errors.append(str(rollback))
        if shell_changed:
            try:
                reload_shell_theme()
            except (OSError, subprocess.CalledProcessError) as rollback:
                errors.append(str(rollback))
        detail = " Previous appearance restored." if not errors else " Restoration errors: " + "; ".join(errors)
        diagnostics.event("worker", "rollback", "failure" if errors else "success",
                          level="ERROR" if errors else "INFO", count=len(errors))
        raise RuntimeError(f"Theme update failed: {exc}.{detail}") from exc
    diagnostics.event("worker", "reload", "requested", reload_requested=reload_requested)
    return {**desired, "shell_reload_requested": reload_requested}


@diagnostics.traced("worker", "worker")
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell-only", action="store_true", help="Update installed Shell CSS without rebuilding GTK or assets")
    parser.add_argument("--transparency", type=int, help="Relative surface opacity reduction, 0–50 (default: saved setting or 25)")
    parser.add_argument("--glass-mode", choices=("frost", "crystal"), help="Glass treatment (default: saved setting or frost)")
    parser.add_argument("--save-setting", action="store_true", help="Save the level after building and reloading successfully")
    parser.add_argument("--appearance-patch", help="Validated JSON section/field update; saves all affected preferences")
    args = parser.parse_args()
    if args.appearance_patch and (args.transparency is not None or args.glass_mode is not None or args.save_setting):
        parser.error("--appearance-patch cannot be combined with individual setting arguments")
    if args.save_setting and args.transparency is None and args.glass_mode is None:
        parser.error("--save-setting requires --transparency or --glass-mode")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with (CONFIG_DIR / "build.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        patch = json.loads(args.appearance_patch) if args.appearance_patch else {}
        if args.transparency is not None:
            patch.setdefault("shell", {})["transparency"] = args.transparency
        if args.glass_mode is not None:
            patch.setdefault("shell", {})["glass_mode"] = args.glass_mode
        desired = apply_locked(patch, args.shell_only, bool(args.appearance_patch) or args.save_setting)
        print(json.dumps(desired))


if __name__ == "__main__":
    main()
