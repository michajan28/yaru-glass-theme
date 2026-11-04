#!/usr/bin/env python3
"""Export current extension settings into assets/profiles/*.ini for the installer.

Machine-specific keys (monitor connectors, location, brightness state, values
managed by yaru-glass-sync or chosen by the installer) are left out.
"""
import re
import subprocess
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parent.parent / "assets/profiles"

# dconf directory under /org/gnome/shell/extensions/ -> key patterns to skip
SECTIONS = {
    "blur-my-shell": [],
    "dash-to-dock": [r"preferred-monitor.*"],
    "just-perfection": [r"support-notifier-.*"],
    "Logo-menu": [],
    "auto-theme-switcher": [r"location-name", r"manual-.*", r"monitors.*", r"last-.*",
                            r"migration-.*", r"data-version"],
}


def filtered_dump(section: str, skip: list[str]) -> str:
    dump = subprocess.run(["dconf", "dump", f"/org/gnome/shell/extensions/{section}/"],
                          capture_output=True, text=True, check=True).stdout
    patterns = [re.compile(rf"^{p}=") for p in skip]
    lines = [line for line in dump.splitlines() if not any(p.match(line) for p in patterns)]
    # Drop sections that became empty.
    out, pending = [], None
    for line in lines:
        if line.startswith("["):
            pending = line
        elif line.strip():
            if pending:
                if out:
                    out.append("")
                out.append(pending)
                pending = None
            out.append(line)
    return "\n".join(out) + "\n" if out else ""


def main() -> None:
    PROFILE_DIR.mkdir(exist_ok=True)
    for section, skip in SECTIONS.items():
        content = filtered_dump(section, skip)
        target = PROFILE_DIR / f"{section}.ini"
        if content:
            target.write_text(content)
            print(f"exported {target.name}")
        elif target.exists():
            target.unlink()


if __name__ == "__main__":
    main()
