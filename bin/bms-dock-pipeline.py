#!/usr/bin/env python3
"""Compatibility entrypoint: reapply managed Shell glass, including the dock."""
import fcntl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src/yaru_glass"))
import managed_glass
from theme_settings import CONFIG_DIR, load_settings


def main() -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with (CONFIG_DIR / "build.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            settings = load_settings()
            managed_glass.apply(settings["glass_mode"], settings["background_blur"], settings["solid"])
    except (*managed_glass.ERRORS, RuntimeError) as exc:
        print(f"Could not reapply managed glass: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("Blur my Shell: managed Shell glass reapplied, including the dock")


if __name__ == "__main__":
    main()
