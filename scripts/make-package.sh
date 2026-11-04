#!/usr/bin/env bash
# Create a distributable package in dist/releases (or the given directory).
# Use --curated-profiles to package supplied profiles without desktop capture.
# Usage: scripts/make-package.sh [--curated-profiles] [output-dir]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT/dist/releases"
CURATED=false
OUTPUT_SET=false
for argument in "$@"; do
  case "$argument" in
    --curated-profiles) CURATED=true ;;
    --*) echo "Unknown option: $argument" >&2; exit 2 ;;
    *)
      if $OUTPUT_SET; then
        echo "Only one output directory is allowed" >&2
        exit 2
      fi
      OUT_DIR="$argument"
      OUTPUT_SET=true
      ;;
  esac
done
VERSION="$(cat "$ROOT/VERSION")"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid release version: $VERSION" >&2
  exit 1
fi
NAME="yaru-glass-theme-$VERSION"
for output in "$OUT_DIR/$NAME.tar.gz" "$OUT_DIR/$NAME.tar.gz.sha256"; do
  if [[ -e "$output" || -L "$output" ]]; then
    echo "Refusing to overwrite $output; choose an empty output directory" >&2
    exit 1
  fi
done

if ! $CURATED; then
  /usr/bin/python3 "$ROOT/scripts/export-profile.py"
fi
if /usr/bin/python3 -c 'import markdown' >/dev/null 2>&1; then
  /usr/bin/python3 "$ROOT/scripts/render-manual.py"
else
  echo "python3-markdown unavailable; packaging the existing MANUAL.html without regeneration" >&2
  if [[ ! -s "$ROOT/docs/MANUAL.html" ]]; then
    echo "A pre-rendered MANUAL.html is required when python3-markdown is unavailable" >&2
    exit 1
  fi
fi
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/$NAME"
(cd "$ROOT" && tar cf - --exclude='__pycache__' --exclude='*.py[cod]' --exclude='.git' README.md CHANGELOG.md AGENTS.md CONTRIBUTING.md SECURITY.md VERSION .github/skills src scripts bin assets docs demo tests) | (cd "$STAGE/$NAME" && tar xf -)
chmod +x "$STAGE/$NAME"/scripts/*.sh "$STAGE/$NAME"/scripts/*.py "$STAGE/$NAME"/bin/*

mkdir -p "$OUT_DIR"
tar -C "$STAGE" -czf "$OUT_DIR/$NAME.tar.gz" "$NAME"
(cd "$OUT_DIR" && sha256sum "$NAME.tar.gz" > "$NAME.tar.gz.sha256")
echo "Package: $OUT_DIR/$NAME.tar.gz"
