"""Private, bounded, allowlisted diagnostics shared by runtime entrypoints."""
from contextlib import contextmanager
from contextvars import ContextVar
from collections import deque
from datetime import datetime, timezone
import errno
import fcntl
from functools import wraps
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from time import monotonic
import uuid

MAX_BYTES = 2 * 1024 * 1024
BACKUPS = 4
MAX_RECORD = 4096
COMPONENTS = frozenset({"settings", "worker", "sync", "glass", "files", "wallpaper",
                        "extensions", "install", "uninstall", "diagnostics", "updater"})
ACTIONS = frozenset({"startup", "apply", "rollback", "repair", "restart", "activate",
                     "deactivate", "restore", "choose", "preview", "retry", "worker",
                     "install", "uninstall", "stage", "compatibility", "export",
                     "read", "verbose", "purge", "protocol", "reload"})
PHASES = frozenset({"start", "success", "failure", "requested", "confirmed", "pending"})
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
FIELDS = {
    "section": {"shell", "app", "files", "wallpapers"},
    "mode": {"frost", "crystal"},
    "slot": {"picture-uri", "picture-uri-dark"},
    "stage": {"preflight", "packages", "files", "backup", "fonts", "extensions",
              "themes", "appearance", "profiles", "service", "activation"},
    "theme": {"Yaru-Glass", "Yaru-Glass-dark", "other"},
}
EXTENSIONS = frozenset({
    "user-theme@gnome-shell-extensions.gcampax.github.com", "blur-my-shell@aunetx",
    "just-perfection-desktop@just-perfection", "auto-theme-switcher@amritashan.github.io",
    "logomenu@aryan_k", "ubuntu-dock@ubuntu.com", "ubuntu-appindicators@ubuntu.com",
})
SOURCE_FILES = frozenset({"diagnostics.py", "diagnostics_ui.py", "managed_glass.py",
                          "files_appearance.py", "wallpapers.py", "theme_settings.py",
                          "build.py", "yaru-glass-settings", "yaru-glass-sync",
                          "install-extensions.py", "enable-extension.py",
                          "updates.py", "update_transaction.py", "operation_lock.py",
                          "yaru-glass-update", "updates_ui.py"})
ERROR_TYPES = frozenset({"OSError", "PermissionError", "FileNotFoundError", "ValueError",
                         "TypeError", "RuntimeError", "TimeoutError", "KeyError",
                         "JSONDecodeError", "CalledProcessError", "Error",
                         "ExtensionCompatibilityError", "SystemExit"})
_operation = ContextVar("yaru_glass_operation", default=None)
_warned = False


def directory():
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    if not base.is_absolute():
        raise ValueError("XDG_STATE_HOME must be absolute")
    return base / "yaru-glass"


def _warn():
    global _warned
    if not _warned:
        print("yaru-glass: diagnostic storage unavailable; action continues. "
              "Check Diagnostics or `yaru-glass-logs show`.", file=sys.stderr, flush=True)
        _warned = True


def new_operation():
    return uuid.uuid4().hex


def operation_id():
    value = _operation.get() or os.environ.get("YARU_GLASS_OPERATION_ID", "")
    return value if re.fullmatch(r"[a-f0-9]{32}", value) else new_operation()


def version():
    value = (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()
    return value if re.fullmatch(r"\d+\.\d+\.\d+", value) else "unknown"


def _prepare():
    path = directory()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise PermissionError("Diagnostic directory is not a private owned directory")
    if info.st_mode & 0o077:
        path.chmod(0o700)
    return path


def _open(path, flags):
    fd = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise PermissionError("Diagnostic file must be an owned regular file")
        os.fchmod(fd, 0o600)
    except (OSError, ValueError):
        os.close(fd)
        raise
    return fd


@contextmanager
def _locked():
    path = _prepare()
    fd = _open(path / "diagnostics.lock", os.O_CREAT | os.O_RDWR)
    try:
        deadline = monotonic() + .2
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if monotonic() >= deadline:
                    raise TimeoutError("Diagnostic storage is busy") from None
                time.sleep(.01)
        yield path
    finally:
        os.close(fd)


def _read(path, limit):
    try:
        fd = _open(path, os.O_RDONLY)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        if os.fstat(stream.fileno()).st_size > limit:
            raise ValueError("Diagnostic file exceeds its configured bound")
        return stream.read(limit + 1)


def _settings(path):
    data = _read(path / "diagnostics.json", 1024)
    if data is None:
        return False
    value = json.loads(data)
    if not isinstance(value, dict) or set(value) != {"verbose"} or type(value["verbose"]) is not bool:
        raise ValueError("Invalid diagnostic preferences")
    return value["verbose"]


def verbose():
    with _locked() as path:
        return _settings(path)


def set_verbose(enabled):
    if type(enabled) is not bool:
        raise ValueError("Verbose must be boolean")
    with _locked() as path:
        fd = _open(path / "diagnostics.json", os.O_CREAT | os.O_WRONLY)
        with os.fdopen(fd, "wb") as stream:
            stream.write(json.dumps({"verbose": enabled}).encode())
            stream.truncate()
    event("diagnostics", "verbose", "success", enabled=enabled)


def safe_fields(fields):
    result = {}
    for key, allowed in FIELDS.items():
        if isinstance(fields.get(key), str) and fields[key] in allowed:
            result[key] = fields[key]
    if isinstance(fields.get("extension"), str) and fields["extension"] in EXTENSIONS:
        result["extension"] = fields["extension"]
    for key in ("enabled", "reload_requested", "solid", "background_blur"):
        if type(fields.get(key)) is bool:
            result[key] = fields[key]
    for key, ceiling in (("exit_code", 255), ("duration_ms", 86400000),
                         ("transparency", 50), ("count", 100000)):
        if type(fields.get(key)) is int and 0 <= fields[key] <= ceiling:
            result[key] = fields[key]
    return result


def _error(exc):
    frames = []
    trace = exc.__traceback__
    while trace:
        name = Path(trace.tb_frame.f_code.co_filename).name
        if name in SOURCE_FILES:
            frames.append({"file": name, "line": trace.tb_lineno})
        trace = trace.tb_next
    kind = type(exc).__name__
    result = {"type": kind if kind in ERROR_TYPES else "Error", "frames": frames[-8:]}
    if isinstance(exc, OSError) and exc.errno in errno.errorcode:
        result["errno"] = errno.errorcode[exc.errno]
    return result


def event(component, action, phase, level="INFO", operation=None, error=None, **fields):
    if component not in COMPONENTS or action not in ACTIONS or phase not in PHASES or level not in LEVELS:
        raise ValueError("Unknown diagnostic event")
    try:
        with _locked() as path:
            if level == "DEBUG" and not _settings(path):
                return
            op = operation or operation_id()
            if not isinstance(op, str) or not re.fullmatch(r"[a-f0-9]{32}", op):
                raise ValueError("Invalid operation identifier")
            record = {"schema": 1, "timestamp": datetime.now(timezone.utc).isoformat(),
                      "level": level, "component": component, "action": action,
                      "phase": phase, "operation": op, "version": version(),
                      "pid": os.getpid(), "fields": safe_fields(fields)}
            if error is not None:
                record["error"] = _error(error)
            data = (json.dumps(record, separators=(",", ":")) + "\n").encode()
            if len(data) > MAX_RECORD:
                raise ValueError("Diagnostic record exceeds its bound")
            active = path / "events.jsonl"
            fd = _open(active, os.O_CREAT | os.O_WRONLY | os.O_APPEND)
            if os.fstat(fd).st_size + len(data) > MAX_BYTES:
                os.close(fd)
                for index in range(BACKUPS, 0, -1):
                    source = active if index == 1 else path / f"events.jsonl.{index-1}"
                    if source.is_symlink():
                        raise PermissionError("Refusing diagnostic log symlink")
                    try:
                        source.replace(path / f"events.jsonl.{index}")
                    except FileNotFoundError:
                        continue
                fd = _open(active, os.O_CREAT | os.O_WRONLY | os.O_APPEND)
            with os.fdopen(fd, "ab") as stream:
                stream.write(data)
    except (OSError, ValueError):
        _warn()


@contextmanager
def operation(component, action, **fields):
    token = _operation.set(operation_id())
    started = monotonic()
    event(component, action, "start", **fields)
    try:
        yield
    except (Exception, SystemExit) as exc:
        # Never store exception messages, command arguments or source lines.
        success = isinstance(exc, SystemExit) and exc.code in (None, 0)
        event(component, action, "success" if success else "failure",
              level="INFO" if success else "ERROR", error=None if success else exc, **fields)
        raise
    else:
        event(component, action, "success",
              duration_ms=int((monotonic() - started) * 1000), **fields)
    finally:
        _operation.reset(token)


def traced(component, action):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with operation(component, action):
                return function(*args, **kwargs)
        return wrapped
    return decorate


def _clean_record(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid record")
    required = {"schema", "timestamp", "level", "component", "action", "phase",
                "operation", "version", "pid", "fields"}
    if (set(value) - (required | {"error"}) or not required <= value.keys()
            or type(value["schema"]) is not int or value["schema"] != 1):
        raise ValueError("Unsupported record")
    if (value["component"] not in COMPONENTS or value["action"] not in ACTIONS
            or value["phase"] not in PHASES or value["level"] not in LEVELS):
        raise ValueError("Invalid event")
    if (not isinstance(value["timestamp"], str)
            or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00", value["timestamp"])
            or not isinstance(value["operation"], str)
            or not re.fullmatch(r"[a-f0-9]{32}", value["operation"])
            or not isinstance(value["version"], str)
            or not re.fullmatch(r"(?:\d+\.\d+\.\d+|unknown)", value["version"])
            or type(value["pid"]) is not int or value["pid"] < 1
            or not isinstance(value["fields"], dict)):
        raise ValueError("Invalid record fields")
    result = {key: value[key] for key in required}
    result["fields"] = safe_fields(value["fields"])
    if "error" in value:
        failure = value["error"]
        if not isinstance(failure, dict) or failure.get("type") not in ERROR_TYPES:
            raise ValueError("Invalid error")
        frames = failure.get("frames")
        if (not isinstance(frames, list) or len(frames) > 8
                or any(not isinstance(frame, dict) or frame.get("file") not in SOURCE_FILES
                       or type(frame.get("line")) is not int or frame["line"] < 1 for frame in frames)):
            raise ValueError("Invalid stack locations")
        result["error"] = {"type": failure["type"],
                           "frames": [{"file": f["file"], "line": f["line"]} for f in frames]}
        if isinstance(failure.get("errno"), str) and failure["errno"] in errno.errorcode.values():
            result["error"]["errno"] = failure["errno"]
    return result


def read_records(limit=200, level="DEBUG"):
    if type(limit) is not int or not 1 <= limit <= 2000 or level not in LEVELS:
        raise ValueError("Invalid diagnostic read bounds")
    records, invalid = deque(maxlen=limit), 0
    snapshots = []
    with _locked() as path:
        for index in range(BACKUPS, -1, -1):
            filename = "events.jsonl" + (f".{index}" if index else "")
            data = _read(path / filename, MAX_BYTES)
            if data is not None:
                snapshots.append(data)
    for data in snapshots:
        for line in data.splitlines():
            try:
                if len(line) > MAX_RECORD:
                    raise ValueError("Oversized record")
                value = _clean_record(json.loads(line))
            except (ValueError, TypeError, KeyError, RecursionError):
                invalid += 1
                continue
            if LEVELS.index(value["level"]) >= LEVELS.index(level):
                records.append(value)
    return {"records": list(records), "invalid_records": invalid}


def report(limit=1000):
    data = read_records(limit)
    data.update({"schema": 1, "project_version": version(),
                 "notice": "Local sanitized report. Review before sharing."})
    import platform
    data["python_version"] = platform.python_version()
    release = Path("/etc/os-release")
    if release.is_file():
        values = dict(line.split("=", 1) for line in release.read_text().splitlines()
                      if "=" in line and not line.startswith("#"))
        if values.get("ID", "").strip('"') == "ubuntu":
            value = values.get("VERSION_ID", "").strip('"')
            if re.fullmatch(r"\d\d\.\d\d", value):
                data["ubuntu_version"] = value
    # Only public version identifiers and known extension states, never paths.
    from gi.repository import Gio
    import managed_glass
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        major = managed_glass.running_shell_major(connection)
        if major in ("46", "50"):
            data["gnome_shell"] = major
            states = {}
            for extension in sorted(EXTENSIONS):
                info = managed_glass.running_extension_info(connection, extension)
                state = info.get("state")
                release = info.get("version")
                states[extension] = {
                    "state": int(state) if type(state) in (int, float)
                    and 0 <= state <= 100 and int(state) == state else "unknown",
                    "version": release if type(release) in (int, float) and 0 <= release < 10000 else "unknown",
                }
                try:
                    managed_glass.validate_running_extension(extension, info, shell_version=major)
                except ValueError:
                    states[extension]["compatibility"] = "not-validated"
                else:
                    states[extension]["compatibility"] = "supported"
            data["extensions"] = states
        else:
            data["runtime_status"] = "unsupported"
    except (OSError, ValueError, managed_glass.GLib.Error):
        data["runtime_status"] = "unavailable"
    return data


def export_report(destination, limit=1000):
    destination = Path(destination)
    content = (json.dumps(report(limit), indent=2) + "\n").encode()
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        try:
            stream = os.fdopen(fd, "wb")
        except OSError:
            os.close(fd)
            raise
        with stream:
            stream.write(content)
    except OSError:
        destination.unlink(missing_ok=True)
        raise
    event("diagnostics", "export", "success")


def purge():
    with _locked() as path:
        for name in ("diagnostics.json", "events.jsonl",
                     *(f"events.jsonl.{i}" for i in range(1, BACKUPS + 1))):
            file = path / name
            if file.is_symlink():
                raise PermissionError("Refusing diagnostic purge symlink")
            file.unlink(missing_ok=True)
    # Keep the coordination inode: unlinking it races a concurrent writer.


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Private Yaru Glass diagnostics; no automatic uploads.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("show", "follow"):
        command = commands.add_parser(name)
        command.add_argument("--limit", type=int, default=200)
        command.add_argument("--level", choices=LEVELS, default="INFO")
    command = commands.add_parser("export")
    command.add_argument("destination")
    command = commands.add_parser("verbose")
    command.add_argument("state", choices=("on", "off"))
    command = commands.add_parser("record")
    command.add_argument("component", choices=sorted(COMPONENTS))
    command.add_argument("action", choices=sorted(ACTIONS))
    command.add_argument("phase", choices=sorted(PHASES))
    command.add_argument("--stage", choices=sorted(FIELDS["stage"]))
    command.add_argument("--exit-code", type=int)
    commands.add_parser("new-operation")
    commands.add_parser("purge")
    args = parser.parse_args(argv)
    try:
        if args.command == "new-operation":
            print(new_operation())
        elif args.command == "record":
            event(args.component, args.action, args.phase,
                  level="ERROR" if args.phase == "failure" else "INFO",
                  stage=args.stage, exit_code=args.exit_code)
        elif args.command == "verbose":
            set_verbose(args.state == "on")
        elif args.command == "purge":
            purge()
        elif args.command == "export":
            with operation("diagnostics", "export"):
                export_report(args.destination)
        else:
            seen = set()
            while True:
                data = read_records(args.limit, args.level)
                if data["invalid_records"]:
                    print(f"yaru-glass-logs: {data['invalid_records']} invalid records omitted", file=sys.stderr)
                current = set()
                for record in data["records"]:
                    text = json.dumps(record, sort_keys=True)
                    current.add(text)
                    if text not in seen:
                        print(text, flush=True)
                seen = current
                if args.command != "follow":
                    break
                time.sleep(1)
    except (OSError, ValueError) as exc:
        # Fixed category only: even errors can contain private paths.
        print(f"yaru-glass-logs: operation failed ({type(exc).__name__}); "
              "check diagnostic storage or export destination.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0
