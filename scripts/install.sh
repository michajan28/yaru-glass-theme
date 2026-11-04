#!/usr/bin/env bash
# ============================================================================
#  Yaru Glass — installer
#  Light/dark translucent glass-style themes built on Ubuntu's Yaru, plus the GNOME
#  Shell extensions and settings that complete the look.
#
#  Usage:  ./scripts/install.sh [options] (run as your normal user, not with sudo)
#    --no-apt         don't install system packages (no password prompt)
#    --no-extensions  don't download/enable GNOME Shell extensions
#    --theme-only     only install the themes, font and sync service;
#                     keep your dock/extension settings untouched
#    -y, --yes        don't ask for confirmation
#    -h, --help       show this help
#  Revert with: ~/.local/share/yaru-glass/scripts/uninstall.sh
# ============================================================================
set -euo pipefail

PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! /usr/bin/python3 "$PKG/src/yaru_glass/operation_lock.py" --held; then
  exec /usr/bin/python3 "$PKG/src/yaru_glass/operation_lock.py" bash "$0" "$@"
fi
DEST="$HOME/.local/share/yaru-glass"
LIGHT="Yaru-Glass"
DARK="Yaru-Glass-dark"
EXT_PATH=/org/gnome/shell/extensions

EXTENSIONS=(
  user-theme@gnome-shell-extensions.gcampax.github.com
  blur-my-shell@aunetx
  just-perfection-desktop@just-perfection
  auto-theme-switcher@amritashan.github.io
)
# Ubuntu built-ins that are part of the look (enabled if present).
SYSTEM_EXTENSIONS=(ubuntu-dock@ubuntu.com ubuntu-appindicators@ubuntu.com)

APT_PACKAGES=(
  yaru-theme-gtk yaru-theme-gnome-shell yaru-theme-icon yaru-theme-sound
  gnome-shell-extension-manager
  python3 python3-gi gir1.2-glib-2.0 gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gdkpixbuf-2.0 libglib2.0-bin dconf-cli
  curl unzip fontconfig
)
APT_EXTENSION_PACKAGES=()

# Settings saved before the first install so uninstall.sh can restore them.
BACKUP_KEYS=(
  /org/gnome/desktop/interface/gtk-theme
  /org/gnome/desktop/interface/color-scheme
  /org/gnome/desktop/interface/font-name
  /org/gnome/desktop/interface/document-font-name
  /org/gnome/desktop/wm/preferences/titlebar-font
  /org/gnome/shell/enabled-extensions
  /org/gnome/shell/disabled-extensions
  /org/gnome/shell/disable-user-extensions
)
BACKUP_DIRS=(blur-my-shell dash-to-dock just-perfection Logo-menu auto-theme-switcher user-theme)

DO_APT=1 DO_EXT=1 DO_PROFILE=1 ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --no-apt) DO_APT=0 ;;
    --no-extensions) DO_EXT=0 ;;
    --theme-only) DO_PROFILE=0 DO_EXT=0 ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (see --help)"; exit 1 ;;
  esac
done

bold=$'\e[1m' blue=$'\e[34m' yellow=$'\e[33m' red=$'\e[31m' green=$'\e[32m' reset=$'\e[0m'
DIAGNOSTIC_CLI="$PKG/bin/yaru-glass-logs"
export YARU_GLASS_OPERATION_ID="${YARU_GLASS_OPERATION_ID:-$(/usr/bin/python3 "$DIAGNOSTIC_CLI" new-operation)}"
diagnostic() {
  /usr/bin/python3 "$DIAGNOSTIC_CLI" record install "$@" ||
    printf 'yaru-glass: lifecycle diagnostics unavailable\n' >&2
}
diagnostic_exit() {
  local result=$?
  trap - EXIT
  if [[ $result -eq 0 ]]; then diagnostic install success --exit-code 0;
  else diagnostic install failure --exit-code "$result"; fi
  exit "$result"
}
trap diagnostic_exit EXIT
diagnostic install start
step() {
  printf '\n%s==>%s %s%s%s\n' "$blue" "$reset" "$bold" "$*" "$reset"
  local stage
  case "$1" in
    "System packages") stage=packages ;;
    "Installing files"*) stage=files ;;
    "Backing up"*) stage=backup ;;
    "Font:"*) stage=fonts ;;
    "GNOME Shell extensions") stage=extensions ;;
    "Building themes") stage=themes ;;
    "Appearance settings") stage=appearance ;;
    "Extension settings"*) stage=profiles ;;
    "Light/dark sync service") stage=service ;;
    "Activating theme") stage=activation ;;
    *) return ;;
  esac
  diagnostic stage start --stage "$stage"
}
info() { printf '    %s\n' "$*"; }
warn() { printf '    %s! %s%s\n' "$yellow" "$*" "$reset"; }
die()  { printf '%sError:%s %s\n' "$red" "$reset" "$*" >&2; exit 1; }

# ---------------------------------------------------------------- preflight
[[ $EUID -ne 0 ]] || die "run this script as your normal user (it asks for sudo itself when needed)."
command -v gnome-shell >/dev/null || die "GNOME Shell not found. This theme is for Ubuntu GNOME desktops."
[[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]] || die "run this from a terminal inside your GNOME desktop session."

SHELL_VERSION="$(gnome-shell --version | grep -oE '[0-9]+' | head -1)"
. /etc/os-release
VERSION_TXT="$(cat "$PKG/VERSION" 2>/dev/null || echo dev)"

printf '%sYaru Glass %s%s\n' "$bold" "$VERSION_TXT" "$reset"
info "System: ${PRETTY_NAME:-unknown}, GNOME Shell $SHELL_VERSION, ${XDG_SESSION_TYPE:-unknown} session"
[[ "${ID:-}" == ubuntu ]] || warn "Not Ubuntu — Yaru packages and Ubuntu Dock may be unavailable; results may differ."
case "$SHELL_VERSION" in
  46)
    APT_EXTENSION_PACKAGES=(
      gnome-shell-extension-ubuntu-dock=90ubuntu3
      gnome-shell-extension-appindicator=58-1ubuntu24.04.1
    )
    ;;
  50)
    APT_EXTENSION_PACKAGES=(gnome-shell-ubuntu-extensions=50.26.04.8ubuntu)
    ;;
  *)
    warn "Tested on GNOME Shell 46 (Ubuntu 24.04) and 50 (Ubuntu 26.04). This version is untested."
    [[ $DO_EXT -eq 0 ]] ||
      die "No exact extension release policy exists for GNOME Shell $SHELL_VERSION; rerun with --no-extensions."
    ;;
esac
if [[ "$SHELL_VERSION" == 50 ]]; then
  warn "Logo Menu is omitted on GNOME 50 because its released event handler fails there; using the standard Activities control."
else
  EXTENSIONS+=(logomenu@aryan_k)
fi

if [[ $ASSUME_YES -eq 0 ]]; then
  echo
  info "This will install the Yaru Glass themes, the Inter font$([[ $DO_APT -eq 1 ]] && echo ', required system packages')$([[ $DO_EXT -eq 1 ]] && echo ', GNOME extensions'),"
  info "and change your appearance settings (a backup is made first)."
  read -r -p "    Continue? [Y/n] " answer
  [[ -z "$answer" || "$answer" =~ ^[YyTt] ]] || exit 0
fi

# ---------------------------------------------------------------- packages
if [[ $DO_APT -eq 1 ]] && command -v apt-get >/dev/null; then
  step "System packages"
  missing=()
  for p in "${APT_PACKAGES[@]}"; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" && continue
    apt-cache show "$p" >/dev/null 2>&1 && missing+=("$p") || warn "package $p not available, skipping"
  done
  if [[ $DO_EXT -eq 1 ]]; then
    for spec in "${APT_EXTENSION_PACKAGES[@]}"; do
      package="${spec%%=*}"
      expected="${spec#*=}"
      installed="$(dpkg-query -W -f='${Version}' "$package" 2>/dev/null || true)"
      if [[ -n "$installed" ]]; then
        [[ "$installed" == "$expected" ]] ||
          die "$package is already installed at $installed; the exact supported package is $expected. It will not be upgraded or downgraded automatically."
        continue
      fi
      apt-cache show "$spec" >/dev/null 2>&1 &&
        missing+=("$spec") ||
        warn "exact package $spec unavailable; that optional Ubuntu extension will remain skipped"
    done
  fi
  if [[ ${#missing[@]} -gt 0 ]]; then
    info "Installing: ${missing[*]}"
    info "You may be asked for your password (sudo)."
    sudo apt-get update -qq
    sudo apt-get install -y "${missing[@]}"
  else
    info "All required packages are already installed."
  fi
elif [[ $DO_APT -eq 1 ]]; then
  warn "apt-get not found — install Yaru themes, python3-gi, dconf-cli, curl and unzip manually."
fi

for suffix in "" "-dark"; do
  for gtk in 3.0 4.0; do
    f="/usr/share/themes/Yaru-blue$suffix/gtk-$gtk/gtk.gresource"
    [[ -f "$f" ]] || die "missing $f — install yaru-theme-gtk."
  done
  [[ -f "/usr/share/gnome-shell/theme/Yaru-blue$suffix/gnome-shell.css" ||
     -f "/usr/share/gnome-shell/theme/Yaru$suffix/gnome-shell.css" ]] ||
    die "missing Yaru-blue$suffix or Yaru$suffix Shell stylesheet — install yaru-theme-gnome-shell."
done

# ---------------------------------------------------------------- files
step "Installing files to $DEST"
if [[ "$PKG" != "$DEST" ]]; then
  mkdir -p "$DEST"
  (cd "$PKG" && tar cf - --exclude='__pycache__' --exclude='*.py[cod]' --exclude='.git' README.md CHANGELOG.md AGENTS.md CONTRIBUTING.md SECURITY.md VERSION .github/skills src scripts bin assets docs tests) | (cd "$DEST" && tar xf -)
fi
# Remove the retired profile left by an upgrade; keep original backups and state.
rm -f "$DEST/assets/profiles/search-light.ini"
chmod +x "$DEST"/scripts/*.sh "$DEST"/scripts/*.py "$DEST"/bin/*
info "done"

# ---------------------------------------------------------------- settings app
step "Settings application"
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
ln -sf "$DEST/bin/yaru-glass-settings" "$HOME/.local/bin/yaru-glass-settings"
ln -sf "$DEST/bin/yaru-glass-logs" "$HOME/.local/bin/yaru-glass-logs"
ln -sf "$DEST/bin/yaru-glass-update" "$HOME/.local/bin/yaru-glass-update"
cat > "$HOME/.local/share/applications/org.yaru.glass.Settings.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Yaru Glass Settings
Comment=Choose glass style, transparency and light/dark wallpapers
Exec=/usr/bin/python3 "$DEST/bin/yaru-glass-settings"
Icon=preferences-desktop-theme
Terminal=false
Categories=Settings;DesktopSettings;
Keywords=theme;transparency;glass;wallpaper;appearance;Yaru;
StartupNotify=true
DBusActivatable=false
EOF
info "Open Yaru Glass Settings from the application launcher to adjust transparency."

# ---------------------------------------------------------------- backup
step "Backing up current settings"
ORIG="$DEST/backup/original"
if [[ -f "$ORIG/keys.tsv" ]]; then
  info "keeping the original backup from the first install ($ORIG)"
else
  mkdir -p "$ORIG"
  dconf dump / > "$ORIG/dconf-full.ini"
  for k in "${BACKUP_KEYS[@]}"; do printf '%s\t%s\n' "$k" "$(dconf read "$k")"; done > "$ORIG/keys.tsv"
  for d in "${BACKUP_DIRS[@]}"; do dconf dump "$EXT_PATH/$d/" > "$ORIG/$d.ini"; done
  [[ -e "$HOME/.config/gtk-4.0/gtk.css" ]] && cp -P "$HOME/.config/gtk-4.0/gtk.css" "$ORIG/gtk4-gtk.css" || true
  info "saved to $ORIG"
fi

# ---------------------------------------------------------------- font
step "Font: Inter"
mkdir -p "$HOME/.local/share/fonts/Inter"
cp "$DEST"/assets/fonts/Inter/* "$HOME/.local/share/fonts/Inter/"
fc-cache -f "$HOME/.local/share/fonts" >/dev/null
info "$(fc-match 'Inter Variable')"

# ---------------------------------------------------------------- extensions
NEW_EXT_FILE="$DEST/state/installed-extensions.txt"
before_count=$( [[ -f "$NEW_EXT_FILE" ]] && wc -l < "$NEW_EXT_FILE" || echo 0 )
ACTIVATION_RELOGIN=0
if [[ $DO_EXT -eq 1 ]]; then
  step "GNOME Shell extensions"
  /usr/bin/python3 "$DEST/bin/install-extensions.py" "$NEW_EXT_FILE" "${EXTENSIONS[@]}"
  ACTIVATE_EXTENSIONS=()
  for uuid in "${EXTENSIONS[@]}" "${SYSTEM_EXTENSIONS[@]}"; do
    [[ -f "$HOME/.local/share/gnome-shell/extensions/$uuid/metadata.json" ||
       -f "/usr/share/gnome-shell/extensions/$uuid/metadata.json" ]] || continue
    ACTIVATE_EXTENSIONS+=("$uuid")
  done
  if [[ ${#ACTIVATE_EXTENSIONS[@]} -gt 0 ]]; then
    if /usr/bin/python3 "$DEST/bin/enable-extension.py" "${ACTIVATE_EXTENSIONS[@]}"; then
      :
    else
      activation_status=$?
      if [[ $activation_status -eq 2 ]]; then
        ACTIVATION_RELOGIN=1
      else
        die "GNOME Shell could not enable the requested extensions; inspect Shell logs and retry."
      fi
    fi
  fi
elif [[ $DO_PROFILE -eq 1 && ( "$SHELL_VERSION" == 46 || "$SHELL_VERSION" == 50 ) ]]; then
  /usr/bin/python3 "$DEST/bin/install-extensions.py" --validate-only "${EXTENSIONS[@]}"
fi
after_count=$( [[ -f "$NEW_EXT_FILE" ]] && wc -l < "$NEW_EXT_FILE" || echo 0 )
NEEDS_RELOGIN=$(( after_count > before_count || ACTIVATION_RELOGIN ))

# ---------------------------------------------------------------- themes
step "Building themes"
/usr/bin/python3 "$DEST/scripts/build.py"

# ---------------------------------------------------------------- settings
step "Appearance settings"
gsettings set org.gnome.desktop.interface icon-theme 'Yaru'
gsettings set org.gnome.desktop.interface font-name 'Inter Variable 10.5'
gsettings set org.gnome.desktop.interface document-font-name 'Inter Variable 11'
gsettings set org.gnome.desktop.wm.preferences titlebar-font 'Inter Variable Semi-Bold 10.5'
info "fonts set to Inter, icons kept as Yaru"

if [[ $DO_PROFILE -eq 1 && ( "$SHELL_VERSION" == 46 || "$SHELL_VERSION" == 50 ) ]]; then
  step "Extension settings (profile)"
  for f in "$DEST"/assets/profiles/*.ini; do
    name="$(basename "$f" .ini)"
    [[ "$SHELL_VERSION" == 50 && "$name" == Logo-menu ]] && continue
    case "$name" in
      blur-my-shell) uuid=blur-my-shell@aunetx ;;
      just-perfection) uuid=just-perfection-desktop@just-perfection ;;
      auto-theme-switcher) uuid=auto-theme-switcher@amritashan.github.io ;;
      Logo-menu) uuid=logomenu@aryan_k ;;
      dash-to-dock) uuid=ubuntu-dock@ubuntu.com ;;
      user-theme) uuid=user-theme@gnome-shell-extensions.gcampax.github.com ;;
      *) continue ;;
    esac
    if [[ ! -f "$HOME/.local/share/gnome-shell/extensions/$uuid/metadata.json" &&
          ! -f "/usr/share/gnome-shell/extensions/$uuid/metadata.json" ]]; then
      info "$name: extension unavailable; profile remains skipped"
      continue
    fi
    if [[ "$name" == blur-my-shell ]]; then
      # Managed Glass owns its exact BMS pipelines; curated release-independent
      # profile data must not replace them with legacy Gaussian/refraction effects.
      sed '/^pipelines=/d' "$f" | dconf load "$EXT_PATH/$name/"
    else
      dconf load "$EXT_PATH/$name/" < "$f"
    fi
    info "applied $name"
  done
elif [[ $DO_PROFILE -eq 1 ]]; then
  warn "extension profiles skipped: GNOME Shell $SHELL_VERSION has no exact compatibility policy"
fi

# ---------------------------------------------------------------- service
step "Light/dark sync service"
mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user"
ln -sf "$DEST/bin/yaru-glass-sync" "$HOME/.local/bin/yaru-glass-sync"
cat > "$HOME/.config/systemd/user/yaru-glass-sync.service" <<EOF
[Unit]
Description=Keep Yaru Glass light/dark theme pair in sync
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=/usr/bin/python3 $DEST/bin/yaru-glass-sync
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
EOF
systemctl --user daemon-reload
systemctl --user enable yaru-glass-sync.service >/dev/null 2>&1
systemctl --user restart yaru-glass-sync.service
info "yaru-glass-sync: $(systemctl --user is-active yaru-glass-sync.service)"

# ---------------------------------------------------------------- activate
step "Activating theme"
if [[ "$(gsettings get org.gnome.desktop.interface color-scheme)" == "'prefer-dark'" ]]; then
  gsettings set org.gnome.desktop.interface gtk-theme "$DARK"
else
  gsettings set org.gnome.desktop.interface gtk-theme "$LIGHT"
fi
if ! /usr/bin/python3 "$DEST/bin/yaru-glass-sync" --once; then
  warn "Yaru Glass files were installed, but managed appearance could not be activated."
  die "Check Extension Manager, enable the required extensions, then log out/in and rerun the installer."
fi
info "active: $(gsettings get org.gnome.desktop.interface gtk-theme)"

echo
printf '%s✔ Yaru Glass installed.%s\n' "$green$bold" "$reset"
if [[ $NEEDS_RELOGIN -eq 1 ]]; then
  printf '%s  New extensions were installed — log out and log back in to finish.%s\n' "$yellow$bold" "$reset"
fi
info "Restart open applications to pick up the new look."
info "User manual: $DEST/docs/MANUAL.md"
