"""Project-owned Blur my Shell effects, with reversible settings ownership."""
import json
import math
import subprocess
import time
from pathlib import Path

from gi.repository import Gio, GLib

from theme_settings import CONFIG_DIR, atomic_write, validate_glass_mode
from extension_compatibility import policy_extension_uuids, validate_running_extension
import diagnostics

BACKUP = CONFIG_DIR / "glass-backup.json"
PREFIX = "/org/gnome/shell/extensions/blur-my-shell/"
SCHEMA = "org.gnome.shell.extensions.blur-my-shell"
UUID = "blur-my-shell@aunetx"
OWNED_IDS = {f"pipeline_yaru_glass_{mode}_{area}"
             for mode in ("frost", "crystal") for area in ("panel", "popup", "dock")}
ERRORS = (OSError, ValueError, GLib.Error, subprocess.CalledProcessError)


def pack(value):
    if isinstance(value, bool):
        return GLib.Variant("b", value)
    if isinstance(value, int):
        return GLib.Variant("i", value)
    if isinstance(value, float):
        return GLib.Variant("d", value)
    if isinstance(value, str):
        return GLib.Variant("s", value)
    if isinstance(value, dict):
        return GLib.Variant("a{sv}", {key: pack(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        if (len(value) == 4 and
                all(type(item) in (int, float) and math.isfinite(item) for item in value)):
            # BMS deep_unpack requires primitive doubles, not nested variants.
            return GLib.Variant("(dddd)", value)
        return GLib.Variant("av", [pack(item) for item in value])
    raise TypeError(f"Unsupported pipeline value: {value!r}")


def extension_settings(section="", path=None):
    source = Gio.SettingsSchemaSource.get_default()
    roots = (Path(path),) if path else (
        Path("/usr/share/gnome-shell/extensions") / UUID,
        Path.home() / ".local/share/gnome-shell/extensions" / UUID)
    for root in roots:
        schemas = root / "schemas"
        if (schemas / "gschemas.compiled").is_file():
            source = Gio.SettingsSchemaSource.new_from_directory(str(schemas), source, False)
    schema = source.lookup(SCHEMA + (f".{section}" if section else ""), True)
    if schema is None:
        raise ValueError("Blur my Shell schemas are unavailable. Install/enable Blur my Shell, then retry.")
    return Gio.Settings.new_full(schema, None, None)


def read_key(key):
    return subprocess.run(["dconf", "read", PREFIX + key], text=True,
                          capture_output=True, check=True).stdout.strip() or None


def write_key(key, value):
    command = ["dconf", "reset", PREFIX + key] if value is None else ["dconf", "write", PREFIX + key, value]
    subprocess.run(command, check=True, capture_output=True, text=True)


def pipelines():
    return extension_settings().get_value("pipelines").unpack()


def pipeline_variant(value):
    return GLib.Variant("a{sa{sv}}", {
        name: {key: pack(item) for key, item in pipeline.items()}
        for name, pipeline in value.items()
    })


def pipelines_match(value):
    return extension_settings().get_value("pipelines").equal(pipeline_variant(value))


def write_pipelines(value):
    write_key("pipelines", pipeline_variant(value).print_(True))


def desired_keys(mode, background_blur=True, solid=False):
    validate_glass_mode(mode)
    if type(background_blur) is not bool or type(solid) is not bool:
        raise ValueError("Background blur and Solid must be boolean.")
    result = {}
    for section, area in (("panel", "panel"), ("popup", "popup"), ("dash-to-dock", "dock")):
        result[f"{section}/blur"] = "true" if background_blur and not solid else "false"
        result[f"{section}/static-blur"] = "false"
        result[f"{section}/override-background"] = "false"
        result[f"{section}/pipeline"] = f"'pipeline_yaru_glass_{mode}_{area}'"
    result.update({
        "panel/corner-radius": "0",
        "popup/corner-radius": "16", "popup/menu-corner-radius": "16",
        "popup/quick-settings-corner-radius": "28", "popup/notification-corner-radius": "20",
        "popup/dialog-corner-radius": "22", "popup/osd-corner-radius": "22",
        "popup/calendar-corner-radius": "28", "popup/osd-window-corner-radius": "22",
        "popup/rounded-corners": "0",
    })
    return result


def managed_pipelines(blur_type="native_static_gaussian_blur"):
    result = {}
    for mode in ("frost", "crystal"):
        for area in ("panel", "popup", "dock"):
            name = f"pipeline_yaru_glass_{mode}_{area}"
            effects = [{
                "type": blur_type, "id": name + "_blur",
                "params": {"unscaled_radius": 30 if mode == "frost" else 6, "brightness": 1.0},
            }]
            # Popup actors apply their own target-specific corner mask.
            if area == "dock" and blur_type == "native_static_gaussian_blur":
                effects.append({
                    "type": "corner", "id": name + "_corner",
                    "params": {"radius": 24, "corners_top": True, "corners_bottom": True},
                })
            result[name] = {"name": f"Yaru Glass {mode.title()} {area}", "effects": effects}
    return result


def running_extension_info(connection, uuid):
    return connection.call_sync(
        "org.gnome.Shell.Extensions", "/org/gnome/Shell/Extensions",
        "org.gnome.Shell.Extensions", "GetExtensionInfo",
        GLib.Variant("(s)", (uuid,)), GLib.VariantType("(a{sv})"),
        Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]


@diagnostics.traced("glass", "restart")
def reload_blur_extension():
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def request(enabled):
        method = "EnableExtension" if enabled else "DisableExtension"
        result = connection.call_sync(
            "org.gnome.Shell.Extensions", "/org/gnome/Shell/Extensions",
            "org.gnome.Shell.Extensions", method,
            GLib.Variant("(s)", (UUID,)), GLib.VariantType("(b)"),
            Gio.DBusCallFlags.NONE, 15000, None)
        if not result.unpack()[0]:
            raise ValueError(f"Blur my Shell refused {method} during pipeline repair.")
        expected = 1 if enabled else 2
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if running_extension_info(connection, UUID).get("state") == expected:
                return
            time.sleep(0.1)
        raise ValueError(f"Blur my Shell did not finish {method} during pipeline repair. Log out/in and retry.")

    try:
        request(False)
    finally:
        request(True)


def running_shell_major(connection):
    version = connection.call_sync(
        "org.gnome.Shell", "/org/gnome/Shell", "org.freedesktop.DBus.Properties", "Get",
        GLib.Variant("(ss)", ("org.gnome.Shell", "ShellVersion")),
        GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
    if not isinstance(version, str) or not version:
        raise ValueError("Could not determine the running GNOME Shell version.")
    return version.split(".", 1)[0]


def verify_capabilities(keys):
    shell = Gio.Settings.new("org.gnome.shell")
    enabled = shell.get_strv("enabled-extensions")
    disabled = shell.get_strv("disabled-extensions")
    if shell.get_boolean("disable-user-extensions") or UUID not in enabled or UUID in disabled:
        raise ValueError("Blur my Shell must be enabled for Frost/Crystal effects. Enable it and retry.")
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    info = running_extension_info(connection, UUID)
    if info.get("state") != 1:
        raise ValueError("Blur my Shell is not running. Check Extension Manager, or log out/in after installing it.")
    major = running_shell_major(connection)
    validate_running_extension(UUID, info, shell_version=major)
    for uuid in policy_extension_uuids(major):
        if uuid == UUID:
            continue
        other = running_extension_info(connection, uuid)
        if other.get("state") == 1 or (uuid in enabled and uuid not in disabled):
            validate_running_extension(uuid, other, shell_version=major)
    path = info.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError("Could not locate the running Blur my Shell extension. Log out/in and retry.")
    extension_settings(path=path)
    for key in keys:
        section, name = key.split("/")
        schema = extension_settings(section, path=path)
        if name not in schema.props.settings_schema.list_keys() or not schema.is_writable(name):
            raise ValueError(f"Blur my Shell does not support writable {key}. Update the extension and retry.")
    if not extension_settings(path=path).is_writable("pipelines"):
        raise ValueError("Blur my Shell pipelines are locked by system policy.")
    if any(value == "true" for key, value in keys.items() if key.endswith("/blur")):
        if not all((Path(path) / "render" / name).is_file()
                   for name in ("dynamic_surface.js", "rounded_pipeline.js")):
            raise ValueError("Blur my Shell lacks the required rounded dynamic rendering. Reinstall the supported version.")
    effects = Path(path) / "effects"
    if (effects / "blur/dual_kawase_blur.js").is_file():
        # Newer releases round surfaces themselves; corner is an internal effect.
        return "dual_kawase_blur"
    for directory in (effects, effects / "blur"):
        if ((directory / "native_static_gaussian_blur.js").is_file()
                and any(candidate.is_file() for candidate in
                        (effects / "corner.js", effects / "corner/corner.js"))):
            return "native_static_gaussian_blur"
    raise ValueError("Blur my Shell lacks the required blur/corner effects. Update it and retry.")


@diagnostics.traced("glass", "rollback")
def restore_snapshot(keys, old_pipelines):
    errors = []
    for key, value in keys.items():
        try:
            write_key(key, value)
        except ERRORS as exc:
            errors.append(str(exc))
    try:
        write_pipelines(old_pipelines)
    except ERRORS as exc:
        errors.append(str(exc))
    if errors:
        raise RuntimeError("Could not restore previous glass effects: " + "; ".join(errors))


def apply(mode, background_blur=True, solid=False):
    validate_glass_mode(mode)
    keys = desired_keys(mode, background_blur, solid)
    blur_type = verify_capabilities(keys)
    current_pipelines = pipelines()
    repairing = not pipelines_match(current_pipelines)
    previous_keys = {key: read_key(key) for key in keys}
    new_pipelines = {**current_pipelines, **managed_pipelines(blur_type)}
    if not BACKUP.exists():
        backup = {
            "keys": previous_keys,
            "pipelines": {key: value for key, value in current_pipelines.items() if key in OWNED_IDS},
        }
        atomic_write(BACKUP, json.dumps(backup, indent=2) + "\n")
    else:
        backup = read_backup()
        missing = keys.keys() - backup["keys"].keys()
        if missing:
            backup["keys"].update({key: previous_keys[key] for key in missing})
            atomic_write(BACKUP, json.dumps(backup, indent=2) + "\n")
    if previous_keys == keys and current_pipelines == new_pipelines and not repairing:
        diagnostics.event("glass", "apply", "success", level="DEBUG", mode=mode)
        return
    try:
        write_pipelines(new_pipelines)
        for key, value in keys.items():
            if previous_keys[key] != value:
                write_key(key, value)
        if repairing:
            diagnostics.event("glass", "repair", "requested", mode=mode)
            # Recreate actors that cached Default while the old library was rejected.
            reload_blur_extension()
    except ERRORS as exc:
        restore_snapshot(previous_keys, current_pipelines)
        raise RuntimeError(f"Glass effects were not applied; previous effects restored: {exc}") from exc
    diagnostics.event("glass", "apply", "success", mode=mode, background_blur=background_blur,
                      solid=solid)


def read_backup():
    data = json.loads(BACKUP.read_text())
    expected = set(desired_keys("frost"))
    previous = expected - {"popup/calendar-corner-radius", "popup/osd-window-corner-radius",
                           "popup/rounded-corners"}
    supported = (expected, previous, expected | {"dash-to-dock/corner-radius"},
                 previous | {"dash-to-dock/corner-radius"})
    if (not isinstance(data, dict) or not isinstance(data.get("keys"), dict)
            or set(data["keys"]) not in supported
            or not isinstance(data.get("pipelines"), dict)
            or not set(data["pipelines"]) <= OWNED_IDS
            or any(value is not None and not isinstance(value, str) for value in data["keys"].values())):
        raise ValueError(f"Invalid glass restoration record: {BACKUP}")
    return data


def restore():
    if not BACKUP.exists():
        return
    data = read_backup()
    current = pipelines()
    updated = {key: value for key, value in current.items() if key not in OWNED_IDS}
    updated.update(data["pipelines"])
    restore_snapshot(data["keys"], updated)
    BACKUP.unlink()
    diagnostics.event("glass", "restore", "success")
