# Yaru Glass 2.1.1

> Local release record. This is not a remote publication or a claim of new
> platform validation.

Local branding and lock-screen demo release on the Ubuntu 24.04 / GNOME Shell 46
and Ubuntu 26.04 / GNOME Shell 50 dual-stack baseline established in 2.0.0.

## Changes

- Completed the Yaru Glass project rename across sources, commands, Python
  modules, CSS, theme names, app IDs, services, profiles, documentation and
  browser demos. This is a breaking rename without legacy aliases or automatic
  migration; earlier installations must be removed with their own uninstaller.
- Clarified Yaru attribution, component-specific reuse and redistribution
  obligations, and the project's unofficial, non-endorsed status. Generated
  themes contain copied and modified Yaru Shell stylesheets and assets.
- Added a standalone, offline lock-screen concept with bundled photographic
  wallpapers, clock and appearance controls, fictional profile customization,
  mock notifications and simulated unlock/relock. It does not collect passwords,
  integrate with GNOME locking or change desktop settings.
- Added browser coverage for lock-screen transitions, keyboard focus, privacy,
  local assets, clock formats and narrow/short viewport layouts.

## Fixed

- Fixed managed Blur my Shell pipeline serialization for tuple-valued settings,
  including RGBA colors returned by the extension.

## Validation

- The complete repository suite passed: 130 tests on this Ubuntu host.
- `bash -n` passed for `scripts/install.sh`, `scripts/uninstall.sh`, and
  `scripts/make-package.sh`.
- `python3-markdown` is unavailable, so `docs/MANUAL.html` was not regenerated.
- No fresh GNOME 50 compositor acceptance or arbitrary-background validation was
  performed for this release; the 2.0.0 platform evidence remains historical.

## Package and installation

The local archive is `dist/releases/yaru-glass-theme-2.1.1.tar.gz`, with a
matching SHA-256 file. The package uses the repository-supplied extension
profiles; live host settings are not exported as part of this release.

To update an existing installation while preserving its extension settings:

```sh
sha256sum -c yaru-glass-theme-2.1.1.tar.gz.sha256
tar xzf yaru-glass-theme-2.1.1.tar.gz
cd yaru-glass-theme-2.1.1
./scripts/install.sh --no-apt --no-extensions --theme-only --yes
```

The update replaces the user-level payload, builds and activates the current
light/dark themes, refreshes the sync service, and installs the Settings launcher
and font. It does not download/enable extensions or apply extension profiles.
The original installation backup and saved extension settings are retained.
Close and reopen Settings after upgrading. Files CSS changes still require a
separate, explicitly confirmed Files restart after transfers finish.
