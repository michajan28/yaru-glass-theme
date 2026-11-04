"""Preservation-only replacement with durable, restartable failure recovery."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import re

import operation_lock
from updates import UpdateError, PAYLOAD, read_version, version

SERVICE = "yaru-glass-sync.service"
THEME_NAMES = ("Yaru-Glass", "Yaru-Glass-dark")


def installed_root():
    return Path.home() / ".local/share/yaru-glass"


def targets():
    return {"package": installed_root(),
            "light": Path.home() / ".local/share/themes" / THEME_NAMES[0],
            "dark": Path.home() / ".local/share/themes" / THEME_NAMES[1],
            "launcher": Path.home() / ".local/bin/yaru-glass-update"}


def remove(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def journal_write(workspace, value):
    path = workspace / "journal.json"
    temporary = workspace / "journal.tmp"
    with temporary.open("w") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    sync_directory(workspace)


def run(command, fd=None, timeout=60):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                                env=operation_lock.child_environment(fd) if fd is not None else None,
                                pass_fds=(fd,) if fd is not None else ())
    except subprocess.TimeoutExpired as exc:
        raise UpdateError("An update operation timed out; inspect diagnostics and retry recovery.") from exc
    if result.returncode:
        raise UpdateError(f"{Path(command[0]).name} failed during update: "
                          f"{result.stderr.strip() or result.stdout.strip() or result.returncode}")
    return result.stdout.strip()


def service_active():
    result = subprocess.run(["systemctl", "--user", "is-active", SERVICE],
                            capture_output=True, text=True, timeout=15)
    if result.returncode == 0:
        return True
    if result.returncode in (3, 4) and result.stdout.strip() in {"inactive", "failed", "unknown"}:
        return False
    raise UpdateError("Cannot determine sync service state. Check the user systemd session.")


def reload_theme():
    key = "/org/gnome/shell/extensions/user-theme/name"
    current = run(["dconf", "read", key])
    if current.strip("'") not in THEME_NAMES:
        return False
    try:
        run(["dconf", "write", key, "''"])
    finally:
        run(["dconf", "write", key, current])
    return True


def preflight():
    if os.geteuid() == 0:
        raise UpdateError("Run updates as the logged-in user, never root or sudo.")
    root = installed_root()
    for path in (root, *root.parents):
        if path.is_symlink():
            raise UpdateError("The installed package path must not traverse symlinks.")
    if not root.is_dir() or root.stat().st_uid != os.getuid() or (root / ".git").exists():
        raise UpdateError("An owned installed Yaru Glass package is required; source checkouts cannot be updated.")
    for name in ("VERSION", "scripts/build.py", "bin/yaru-glass-sync", "src/yaru_glass/theme_settings.py"):
        if not (root / name).is_file():
            raise UpdateError("Unsupported installation layout. Use the documented migration instructions.")
    read_version(root)
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        raise UpdateError("Run installation inside your GNOME desktop session.")
    shell = run(["gnome-shell", "--version"])
    if not re.search(r"\b(?:46|50)(?:\.|\s|$)", shell):
        raise UpdateError("Updates support GNOME Shell 46 and 50 only.")
    for name in THEME_NAMES:
        path = targets()["light" if name == THEME_NAMES[0] else "dark"]
        if not path.is_dir() or path.is_symlink() or path.stat().st_uid != os.getuid():
            raise UpdateError("Both owned installed theme directories are required.")
    for key, path in targets().items():
        if key != "launcher" and path.is_symlink():
            raise UpdateError("Update targets must not be symlinks.")
        if any(parent.is_symlink() for parent in path.parents):
            raise UpdateError("Update target parent must not be a symlink.")
    launcher = targets()["launcher"]
    if os.path.lexists(launcher) and not (launcher.is_symlink() and
                                        os.readlink(launcher) == str(root / "bin/yaru-glass-update")):
        raise UpdateError("The updater command path is occupied by an unrelated file.")


def stage_package(payload, destination):
    shutil.copytree(payload, destination, symlinks=False,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
    old = installed_root()
    for path in old.iterdir():
        if path.name not in PAYLOAD:
            target = destination / path.name
            if path.is_dir() and not path.is_symlink():
                shutil.copytree(path, target, symlinks=True)
            elif path.is_symlink():
                target.symlink_to(os.readlink(path))
            else:
                shutil.copy2(path, target)
    profiles = destination / "assets/profiles"
    if (old / "assets/profiles").is_dir():
        remove(profiles)
        shutil.copytree(old / "assets/profiles", profiles, symlinks=True)


def capture_effects():
    import managed_glass
    keys = [managed_glass.PREFIX + key for key in managed_glass.desired_keys("frost")]
    keys += [managed_glass.PREFIX + "pipelines", "/org/gnome/shell/extensions/user-theme/name"]
    return {key: run(["dconf", "read", key]) for key in keys}


def recover(workspace):
    path = workspace / "journal.json"
    if not path.exists():
        return False
    if workspace.is_symlink() or path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
        raise UpdateError("Unsafe update recovery journal; keep it for inspection.")
    data = json.loads(path.read_text())
    if (not isinstance(data, dict) or data.get("schema") != 1 or
            not isinstance(data.get("entries"), dict) or
            type(data.get("committed")) is not bool or
            type(data.get("service_active")) is not bool or
            not isinstance(data.get("effects"), dict)):
        raise UpdateError("Unknown update recovery format. Keep the recovery workspace for inspection.")
    for label, entry in data["entries"].items():
        if label not in targets() or not isinstance(entry, dict) or type(entry.get("present")) is not bool:
            raise UpdateError("Invalid replacement record; keep recovery data for inspection.")
    for key, value in data["effects"].items():
        if (not isinstance(key, str) or not key.startswith("/org/gnome/shell/extensions/") or
                not isinstance(value, str)):
            raise UpdateError("Invalid effect recovery record; keep recovery data for inspection.")
    glass_bytes = data.get("glass_backup")
    if glass_bytes is not None:
        if not isinstance(glass_bytes, str):
            raise UpdateError("Invalid managed backup recovery record.")
        try:
            bytes.fromhex(glass_bytes)
        except ValueError as exc:
            raise UpdateError("Invalid managed backup recovery record.") from exc
    if not data.get("committed"):
        run(["systemctl", "--user", "stop", SERVICE])
        errors = []
        for label, target in reversed(list(targets().items())):
            entry = data["entries"].get(label)
            if not entry:
                continue
            backup = workspace / ("old-" + label)
            try:
                if os.path.lexists(backup):
                    remove(target)
                    backup.rename(target)
                    sync_directory(target.parent)
                    sync_directory(workspace)
                elif not entry["present"]:
                    remove(target)
                    sync_directory(target.parent)
            except OSError as exc:
                errors.append(f"{label}: {exc}")
        for key, value in data.get("effects", {}).items():
            try:
                run(["dconf", "write", key, value] if value else ["dconf", "reset", key])
            except (OSError, UpdateError) as exc:
                errors.append(f"effect restoration: {exc}")
        config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "yaru-glass"
        glass_backup = config / "glass-backup.json"
        if "glass_backup" in data:
            try:
                if data["glass_backup"] is None:
                    glass_backup.unlink(missing_ok=True)
                else:
                    glass_backup.write_bytes(bytes.fromhex(data["glass_backup"]))
            except OSError as exc:
                errors.append(f"managed backup restoration: {exc}")
        try:
            reload_theme()
            if data["service_active"]:
                run(["systemctl", "--user", "start", SERVICE])
                if not service_active():
                    raise UpdateError("Previous sync service did not become active.")
        except (OSError, UpdateError) as exc:
            errors.append(f"runtime restoration: {exc}")
        if errors:
            raise UpdateError("Rollback incomplete; recovery data retained. " + "; ".join(errors))
    remove(workspace)
    sync_directory(workspace.parent)
    return True


def generate(payload, output, fd):
    run(["/usr/bin/python3", str(payload / "scripts/build.py"),
         "--stage-themes", str(output)], fd, timeout=180)


def flush_tree(root):
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir() and not path.is_symlink():
            sync_directory(path)
    sync_directory(root)


def install(payload, workspace, fd):
    preflight()
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "yaru-glass"
    config.mkdir(parents=True, exist_ok=True)
    with (config / "build.lock").open("a") as build_lock:
        try:
            fcntl.flock(build_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise operation_lock.BusyError("An appearance operation is still running; retry.") from exc
        return _install(payload, workspace, fd, config)


def _install(payload, workspace, fd, config):
    old_version, new_version = read_version(installed_root()), read_version(payload)
    if version(new_version) <= version(old_version):
        raise UpdateError("The selected release is not newer than the installed version.")
    package = workspace / "new-package"
    stage_package(payload, package)
    themes = workspace / "themes"
    generate(package, themes, fd)
    for label, name in (("light", THEME_NAMES[0]), ("dark", THEME_NAMES[1])):
        (themes / name).rename(workspace / ("new-" + label))
    themes.rmdir()
    launcher = workspace / "new-launcher"
    launcher.symlink_to(installed_root() / "bin/yaru-glass-update")
    for target in targets().values():
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.parent.stat().st_dev != workspace.stat().st_dev:
            raise UpdateError("Package, themes and updater staging must share a filesystem.")
    needed = sum(path.stat().st_size for path in workspace.rglob("*")
                 if path.is_file() and not path.is_symlink())
    if shutil.disk_usage(workspace).free < needed + 16 * 1024 * 1024:
        raise UpdateError("Insufficient free space for a recoverable update.")
    flush_tree(workspace)
    backup = config / "glass-backup.json"
    data = {"schema": 1, "entries": {}, "service_active": service_active(),
            "effects": capture_effects(), "committed": False,
            "glass_backup": backup.read_bytes().hex() if backup.exists() else None}
    journal_write(workspace, data)
    try:
        run(["systemctl", "--user", "stop", SERVICE])
        for label, target in targets().items():
            data["entries"][label] = {"present": os.path.lexists(target)}
            journal_write(workspace, data)
            if os.path.lexists(target):
                target.rename(workspace / ("old-" + label))
                sync_directory(target.parent)
                sync_directory(workspace)
            (workspace / ("new-" + label)).rename(target)
            sync_directory(target.parent)
            sync_directory(workspace)
        requested = reload_theme()
        if data["service_active"]:
            run(["systemctl", "--user", "start", SERVICE])
            if not service_active():
                raise UpdateError("Updated sync service did not become active.")
        data["committed"] = True
        journal_write(workspace, data)
    except (OSError, RuntimeError) as exc:
        try:
            recover(workspace)
        except (OSError, RuntimeError) as rollback:
            raise UpdateError(f"Update failed: {exc}. {rollback}") from exc
        raise UpdateError(f"Update failed; previous version restored. {exc}") from exc
    remove(workspace)
    return {"status": "installed", "installed_version": new_version,
            "previous_version": old_version, "shell_reload_requested": requested,
            "settings_relaunch_required": True, "files_restart_required": True}
