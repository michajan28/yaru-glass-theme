#!/usr/bin/python3
"""Build the independent Lock Screen ZIP without changing desktop preferences."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/yaru_glass"))
import companion_extension


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Output directory; existing ZIPs are never overwritten")
    args = parser.parse_args()
    try:
        print(companion_extension.build(args.output))
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f"yaru-glass-lock-screen: {exc}\n")


if __name__ == "__main__":
    main()
