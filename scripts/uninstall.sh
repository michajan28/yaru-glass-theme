#!/usr/bin/env bash
# ============================================================================
#  Yaru Glass — uninstaller
#  Restores the settings saved before the first install.
#
#  Usage:  ~/.local/share/yaru-glass/scripts/uninstall.sh [options]
#    --purge              also delete the generated themes, the Inter font,
#                         the sync service, settings app/preferences and installed files
#    --remove-extensions  also uninstall extensions that the installer added
#    -h, --help           show this help
#  System packages installed with apt are kept (they are standard Ubuntu packages).
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIG="$ROOT/backup/original"
EXT_PATH=/org/gnome/shell/extensions
GTK4_CSS="$HOME/.config/gtk-4.0/gtk.css"
PURGE=0 REMOVE_EXT=0
for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=1 ;;
    --remove-extensions) REMOVE_EXT=1 ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (see --help)"; exit 1 ;;
  esac
done
[[ $EUID -ne 0 ]] || { echo "Run as your normal user, not root."; exit 1; }
if [[ $PURGE -eq 1 && "$ROOT" != "$HOME/.local/share/yaru-glass" ]]; then
  echo "Run --purge from ~/.local/share/yaru-glass/scripts/uninstall.sh, not the source checkout."
  exit 1
fi
if ! /usr/bin/python3 "$ROOT/src/yaru_glass/operation_lock.py" --held; then
  exec /usr/bin/python3 "$ROOT/src/yaru_glass/operation_lock.py" bash "$0" "$@"
fi

DIAGNOSTIC_CLI="$ROOT/bin/yaru-glass-logs"
LOGGING_PURGED=0
export YARU_GLASS_OPERATION_ID="${YARU_GLASS_OPERATION_ID:-$(/usr/bin/python3 "$DIAGNOSTIC_CLI" new-operation)}"
diagnostic() {
  /usr/bin/python3 "$DIAGNOSTIC_CLI" record uninstall "$@" ||
    printf 'yaru-glass: lifecycle diagnostics unavailable\n' >&2
}
diagnostic_exit() {
  local result=$?
  trap - EXIT
  if [[ $LOGGING_PURGED -eq 0 ]]; then
    if [[ $result -eq 0 ]]; then diagnostic uninstall success --exit-code 0;
    else diagnostic uninstall failure --exit-code "$result"; fi
  fi
  exit "$result"
}
trap diagnostic_exit EXIT
diagnostic uninstall start

echo "==> Stopping sync service"
systemctl --user disable --now yaru-glass-sync.service 2>/dev/null || true

echo "==> Restoring managed glass effects and wallpapers"
/usr/bin/python3 "$ROOT/bin/yaru-glass-sync" --restore-managed

echo "==> Removing GTK4 overrides"
if [[ -L "$GTK4_CSS" && "$(readlink "$GTK4_CSS")" == *Yaru-Glass* ]]; then
  rm "$GTK4_CSS"
  if [[ -e "$ORIG/gtk4-gtk.css" || -L "$ORIG/gtk4-gtk.css" ]]; then cp -P "$ORIG/gtk4-gtk.css" "$GTK4_CSS"; fi
fi

if [[ -f "$ORIG/keys.tsv" ]]; then
  echo "==> Restoring settings from $ORIG"
  for f in "$ORIG"/*.ini; do
    name="$(basename "$f" .ini)"
    [[ "$name" == dconf-full ]] && continue
    dconf reset -f "$EXT_PATH/$name/"
    [[ -s "$f" ]] && dconf load "$EXT_PATH/$name/" < "$f"
  done
  while IFS=$'\t' read -r key value; do
    if [[ -z "$value" ]]; then dconf reset "$key"; else dconf write "$key" "$value"; fi
  done < "$ORIG/keys.tsv"
else
  echo "!! No backup found in $ORIG — switching back to the default Yaru theme only."
  gsettings set org.gnome.desktop.interface gtk-theme 'Yaru'
  dconf reset $EXT_PATH/user-theme/name
fi

if [[ $REMOVE_EXT -eq 1 && -f "$ROOT/state/installed-extensions.txt" ]]; then
  echo "==> Removing extensions added by the installer"
  while read -r uuid; do
    [[ -n "$uuid" ]] || continue
    gnome-extensions uninstall "$uuid" 2>/dev/null || rm -rf "$HOME/.local/share/gnome-shell/extensions/$uuid"
    echo "    removed $uuid"
  done < "$ROOT/state/installed-extensions.txt"
  rm -f "$ROOT/state/installed-extensions.txt"
fi

if [[ $PURGE -eq 1 ]]; then
  echo "==> Deleting theme files"
  rm -rf "$HOME/.local/share/themes/Yaru-Glass" "$HOME/.local/share/themes/Yaru-Glass-dark"
  rm -rf "$HOME/.local/share/fonts/Inter" && fc-cache -f "$HOME/.local/share/fonts" >/dev/null 2>&1 || true
  rm -f "$HOME/.config/systemd/user/yaru-glass-sync.service" "$HOME/.local/bin/yaru-glass-sync"
  rm -f "$HOME/.local/share/applications/org.yaru.glass.Settings.desktop" "$HOME/.local/bin/yaru-glass-settings"
  rm -f "$HOME/.local/bin/yaru-glass-logs"
  rm -f "$HOME/.local/bin/yaru-glass-update"
  rm -rf "$HOME/.local/share/yaru-glass-update/runner" "$HOME/.local/share/yaru-glass-update/transaction"
  SETTINGS_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/yaru-glass"
  rm -f "$SETTINGS_DIR/settings.json" "$SETTINGS_DIR/app-appearance.json" "$SETTINGS_DIR/files-appearance.json" "$SETTINGS_DIR/build.lock"
  if [[ -d "$SETTINGS_DIR" ]]; then rmdir --ignore-fail-on-non-empty "$SETTINGS_DIR"; fi
  systemctl --user daemon-reload
  # Keep a copy of the backup outside the folder being deleted.
  [[ -d "$ROOT/backup" ]] && cp -r "$ROOT/backup" "$HOME/.local/share/yaru-glass-backup-$(date +%Y%m%d-%H%M%S)"
  diagnostic purge success
  /usr/bin/python3 "$DIAGNOSTIC_CLI" purge
  LOGGING_PURGED=1
  rm -rf "$ROOT"
fi

echo "Done. Log out and back in if some extensions still look themed."
