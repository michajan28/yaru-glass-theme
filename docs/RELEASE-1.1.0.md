# Yaru Glass 1.1.0

> Historical record: naming in this document has been normalized to Yaru Glass.
> Command examples do not identify preserved historical archives, which have not
> been renamed or rebuilt. Use the README for current installation instructions.

Target: Ubuntu 24.04, GNOME Shell 46, GTK 4.14/libadwaita 1.5, Nautilus 46.

## Included

- Readable, borderless Shell surfaces, plain calendar, flat Quick Settings controls.
- Frost/Crystal transparent tints, without wallpaper-only or live backdrop blur.
- Native Settings app with Shell, Applications and Wallpapers pages.
- Independent opt-in Settings-app and Files transparency, retaining solid controls
  and file content; separate light/dark wallpaper pickers with thumbnails.
- Files presets, actual-opacity readout, independent reset and confirmed restart.
- Updated standalone browser demo with three pages, separate Shell/app controls,
  solid file content and keyboard-accessible tabs. Wallpaper thumbnails in the
  demo are illustrative; browser controls never modify the desktop.

## Upgrade without resetting extension profiles

Extract the archive, then run from its directory:

```sh
./install.sh --no-apt --no-extensions --theme-only --yes
```

Use these flags for an existing working installation with dependencies/extensions
already present. For a new installation, use `./install.sh`.
The full installer intentionally applies its extension profiles unless
`--theme-only` is specified.

Close and reopen Settings. GTK apps may need a full restart for stylesheet changes.
Before using Restart Files, finish file operations; it closes all Files windows and
reopens Home, not the previous tabs.

Normal uninstall keeps preferences and restores backed-up appearance settings:

```sh
~/.local/share/yaru-glass/uninstall.sh
```

`--purge` removes preferences/generated files too. System packages remain installed.

## Validation performed, 2026-10-16

| Check | Result |
|---|---|
| Python/GTK regression suite | 72 tests passed |
| Shell script syntax | Installer and uninstaller passed |
| GNOME St/Clutter notification layout | Light/dark, LTR/RTL, normal/hover/focus/active passed |
| Settings rendered GTK textures | All three pages, both schemes/styles and transparency endpoints passed |
| Files-style rendered split pane | Sidebar/header alpha, solid content and other-window isolation passed |
| Text contrast | Sampled Shell foreground minimum 6.47:1; Settings explanatory text checked against 4.5:1 |
| Browser demo | Both schemes/styles at Shell levels 0/25/50; app/Files alpha, solid content, keyboard tabs and 390px layout passed |
| Isolated install and upgrade | Actual scripts, private HOME and D-Bus; all three preference files and first-install backup preserved |
| Isolated normal uninstall | Original GTK theme, font and user GTK4 stylesheet restored; preferences retained |

The lifecycle test used `--no-apt --no-extensions --theme-only` with the project GTK
theme inactive during builds, since no GNOME Shell extension process runs on its
private bus. User systemd calls were stubbed to avoid touching the real desktop.
Managed extension restoration and wallpaper ownership are covered by regression
tests and earlier live integration checks; this is not a fresh-machine/full-extension
installation certification. Purge was not executed during this release check.

### Still requiring manual desktop checks

GNOME denied real desktop screenshot capture (`Screenshot is not allowed`).
Browser screenshots and native GTK render/layout checks do not prove the
compositor's final output. The following are **not claimed as visually verified**:

- Real popup corners/shadows over bright and dark application windows.
- Real Files maximized layout, its dialogs, keyboard focus and disabled labels.
- All text on arbitrary wallpapers, applications and third-party extensions.

The Files split-pane tests model the installed Nautilus 46 hierarchy; they are not
screenshots of Nautilus itself. Existing manual feedback confirmed normal Files
transparency after a full process restart, but does not cover the entire matrix.
This release is a tested preview, pending that manual visual acceptance pass.

## Archive verification

From the directory containing the archive and checksum:

```sh
sha256sum -c yaru-glass-theme-1.1.0.tar.gz.sha256
```

The archive contains source, documentation, tests and bundled licensed fonts.
It excludes Python caches, installer state/backups, preferences and generated themes.
The previous 1.0.0 archive is not overwritten.
