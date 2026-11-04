#!/usr/bin/env python3
"""Render MANUAL.md to a self-contained MANUAL.html (needs python3-markdown)."""
import sys
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("python3-markdown not installed; skipping MANUAL.html")

ROOT = Path(__file__).resolve().parent.parent
CSS = """
:root { color-scheme: light dark; --accent: #007AFF; --bg: #f5f5f7; --card: #fff; --fg: #1d1d1f; --muted: #6e6e73; --line: rgba(0,0,0,.1); }
@media (prefers-color-scheme: dark) { :root { --accent: #0A84FF; --bg: #1c1c1e; --card: #2c2c2e; --fg: #f5f5f7; --muted: #a1a1a6; --line: rgba(255,255,255,.12); } }
body { margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.6 "Inter Variable", Inter, "Ubuntu Sans", sans-serif; }
main { max-width: 860px; margin: 40px auto; padding: 40px 48px; background: var(--card); border-radius: 22px; box-shadow: 0 10px 40px rgba(0,0,0,.08); }
h1 { font-size: 2.2em; margin-top: 0; letter-spacing: -.02em; }
h2 { margin-top: 2.2em; padding-top: .6em; border-top: 1px solid var(--line); letter-spacing: -.01em; }
a { color: var(--accent); text-decoration: none; } a:hover { text-decoration: underline; }
img { max-width: 100%; border-radius: 14px; margin: 6px 6px 6px 0; box-shadow: 0 6px 24px rgba(0,0,0,.15); vertical-align: top; }
p > img { max-width: 48%; }
code { font: 13px/1.5 "Ubuntu Sans Mono", ui-monospace, monospace; background: rgba(127,127,127,.14); padding: 2px 6px; border-radius: 6px; }
pre { background: #1d1d1f; color: #f5f5f7; padding: 14px 18px; border-radius: 12px; overflow-x: auto; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 14px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; }
blockquote { margin: 1em 0; padding: 10px 16px; border-left: 4px solid var(--accent); background: rgba(0,122,255,.08); border-radius: 0 10px 10px 0; }
hr { border: none; }
"""


def main() -> None:
    text = (ROOT / "docs/MANUAL.md").read_text()
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "sane_lists"])
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Yaru Glass — User Manual</title><style>{CSS}</style></head>
<body><main>{body}</main></body></html>
"""
    (ROOT / "docs/MANUAL.html").write_text(html)
    print(f"rendered {ROOT / 'docs/MANUAL.html'}")


if __name__ == "__main__":
    main()
