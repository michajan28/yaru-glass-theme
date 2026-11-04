"""Coordinate package replacement with appearance and lifecycle operations."""
from contextlib import contextmanager
from contextvars import ContextVar
import argparse
import fcntl
import os
from pathlib import Path
import stat

_held = ContextVar("yaru_operation_lock", default=None)


class BusyError(RuntimeError):
    pass


def directory():
    path = Path.home() / ".local/share/yaru-glass-update"
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise PermissionError("Updater workspace must not traverse symlinks.")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise PermissionError("Updater workspace must be an owned directory.")
    if info.st_mode & 0o077:
        path.chmod(0o700)
    return path


def inherited():
    value = os.environ.get("YARU_GLASS_LOCK_FD", "")
    if not value.isdecimal():
        return None
    fd = int(value)
    try:
        info, expected = os.fstat(fd), (directory() / "lifecycle.lock").stat()
    except OSError:
        return None
    if (info.st_dev, info.st_ino) != (expected.st_dev, expected.st_ino):
        return None
    return fd, os.environ.get("YARU_GLASS_LOCK_MODE") == "exclusive"


@contextmanager
def locked(exclusive=False, recovery=False):
    existing = _held.get() or inherited()
    if existing:
        if exclusive and not existing[1]:
            raise BusyError("A lifecycle operation requires exclusive access.")
        yield existing[0]
        return
    path = directory()
    fd = os.open(path / "lifecycle.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise PermissionError("Invalid lifecycle lock.")
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BusyError("Yaru Glass is busy. Finish the current operation and retry.") from exc
        if not recovery and (path / "transaction/journal.json").exists():
            raise BusyError("An interrupted update needs recovery. Run yaru-glass-update recover; "
                            "see the manual if the installed command is unavailable.")
        token = _held.set((fd, exclusive))
        try:
            yield fd
        finally:
            _held.reset(token)
    finally:
        os.close(fd)


def child_environment(fd, exclusive=True):
    return {**os.environ, "YARU_GLASS_LOCK_FD": str(fd),
            "YARU_GLASS_LOCK_MODE": "exclusive" if exclusive else "shared"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--held", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.held:
        raise SystemExit(0 if inherited() and inherited()[1] else 1)
    if not args.command:
        parser.error("A command is required")
    try:
        with locked(exclusive=True) as fd:
            os.set_inheritable(fd, True)
            os.execvpe(args.command[0], args.command, child_environment(fd))
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f"yaru-glass: {exc}\n")


if __name__ == "__main__":
    main()
