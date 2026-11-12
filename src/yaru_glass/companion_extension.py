"""Build and install the independent local companion without enabling it."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import zipfile

from extension_compatibility import ExtensionCompatibilityError, validate_extension_schemas

UUID = "lockscreen@yaru-glass"
SCHEMA = "org.yaru.glass.lockscreen"
SOURCE = Path(__file__).resolve().parents[1] / "gnome-shell-extension"
FILES = ("metadata.json", "extension.js", "layout.js", "stylesheet.css",
         "prefs.js", "preferences.js", "settings.js", "COPYING", "NOTICE",
         f"schemas/{SCHEMA}.gschema.xml")


def check_path(path):
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ExtensionCompatibilityError("Lock Screen paths must not traverse symlinks.")


def validate_metadata(value, shell=None):
    if (not isinstance(value, dict) or value.get("uuid") != UUID or
            value.get("yaru-glass-managed") is not True or
            value.get("settings-schema") != SCHEMA or
            value.get("session-modes") != ["user", "unlock-dialog"] or
            value.get("shell-version") != ["46", "50"] or
            type(value.get("version")) is not int or value["version"] != 1):
        raise ExtensionCompatibilityError(
            "Lock Screen requires the compatible independent version 1. "
            "An existing incompatible copy will not be replaced.")
    if shell is not None and shell not in value["shell-version"]:
        raise ExtensionCompatibilityError(f"Lock Screen does not support GNOME Shell {shell}.")
    return value


def validate_tree(root, shell=None):
    check_path(root)
    if not root.is_dir():
        raise ExtensionCompatibilityError("Lock Screen source or installed extension is missing.")
    for name in FILES:
        path = root / name
        check_path(path)
        if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
            raise ExtensionCompatibilityError(f"Lock Screen is missing a valid {name}.")
    try:
        value = validate_metadata(json.loads((root / "metadata.json").read_text()), shell)
        validate_extension_schemas(UUID, value, {SCHEMA: (root / FILES[-1]).read_bytes()})
    except (ValueError, OSError) as exc:
        raise ExtensionCompatibilityError(f"Invalid Lock Screen source: {exc}") from exc
    return value


def installed(shell):
    user = Path.home() / ".local/share/gnome-shell/extensions" / UUID
    system = Path("/usr/share/gnome-shell/extensions") / UUID
    for root in (user, system):
        check_path(root)
        if os.path.lexists(root):
            validate_tree(root, shell)
            compiled = root / "schemas/gschemas.compiled"
            check_path(compiled)
            if not compiled.is_file():
                raise ExtensionCompatibilityError("Installed Lock Screen schema is not compiled.")
            return root
    return None


def validate_archive(path):
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            names = [entry.filename for entry in members]
            allowed = {*FILES, "schemas/", "schemas/gschemas.compiled"}
            if (len(names) != len(set(names)) or set(names) - allowed or
                    not set(FILES) <= set(names) or
                    sum(entry.file_size for entry in members) > 8 * 1024 * 1024 or
                    any(stat.S_ISLNK(entry.external_attr >> 16) for entry in members)):
                raise ExtensionCompatibilityError("Invalid Lock Screen ZIP payload.")
            metadata = validate_metadata(json.loads(archive.read("metadata.json")))
            validate_extension_schemas(UUID, metadata, {SCHEMA: archive.read(FILES[-1])})
            return metadata
    except (zipfile.BadZipFile, ValueError, KeyError) as exc:
        raise ExtensionCompatibilityError("Malformed Lock Screen ZIP.") from exc


def build(output, source=SOURCE):
    metadata = validate_tree(source)
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"{UUID}-v{metadata['version']}.shell-extension.zip"
    if os.path.lexists(target):
        raise ExtensionCompatibilityError(f"Refusing to overwrite {target}.")
    with tempfile.TemporaryDirectory(prefix="yaru-lock-pack-") as directory:
        command = ["gnome-extensions", "pack", str(source), "--out-dir", directory]
        for name in ("layout.js", "preferences.js", "settings.js", "COPYING", "NOTICE"):
            command += ["--extra-source", name]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExtensionCompatibilityError(f"Cannot run GNOME extension packaging: {exc}") from exc
        if result.returncode:
            raise ExtensionCompatibilityError("Lock Screen packaging failed: " + result.stderr.strip())
        archive = Path(directory) / f"{UUID}.shell-extension.zip"
        validate_archive(archive)
        with archive.open("rb") as src, target.open("xb") as dest:
            shutil.copyfileobj(src, dest)
    return target


def install(shell, state):
    if installed(shell) is not None:
        print(f"  Lock Screen: compatible existing copy retained.")
        return
    target = Path.home() / ".local/share/gnome-shell/extensions" / UUID
    check_path(target)
    with tempfile.TemporaryDirectory(prefix="yaru-lock-install-") as directory:
        archive = build(Path(directory))
        try:
            result = subprocess.run(["gnome-extensions", "install", str(archive)],
                                    capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExtensionCompatibilityError(f"Cannot run GNOME extension installation: {exc}") from exc
        if result.returncode:
            raise ExtensionCompatibilityError("Lock Screen install failed: " + result.stderr.strip())
    state.parent.mkdir(parents=True, exist_ok=True)
    with state.open("a") as stream:
        stream.write(UUID + "\n")
    if installed(shell) != target:
        raise ExtensionCompatibilityError("Lock Screen did not install in the user extension directory.")
    print("  Lock Screen installed, not enabled. Log out/in if it is not listed, "
          "then enable it and open its Preferences in Extension Manager.")
