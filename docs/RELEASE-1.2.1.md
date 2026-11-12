# Yaru Glass 1.2.1

> Historical record: naming in this document has been normalized to Yaru Glass.
> Command examples do not identify preserved historical archives, which have not
> been renamed or rebuilt. Use the README for current installation instructions.

Control polish and live desktop acceptance for Ubuntu 24.04 / GNOME Shell 46.
The appearance model and saved values are unchanged from [1.2.0](RELEASE-1.2.0.md).

## Changes

- Replaced stock-looking demo controls with rounded preference groups, themed
  selectors, switches, buttons and sliders. Native HTML semantics, switch labels,
  keyboard focus, reduced-motion handling and a framework-free standalone page
  are retained. Confirmation dialogs follow the selected light/dark scheme.
- Fixed a real Nautilus 46 restart issue: `nautilus --quit` can return nonzero
  after Files has exited. Settings now checks session D-Bus ownership in this
  case, logs the command diagnostic, and reopens Home only after confirmed exit.
  A still-running service or failed verification remains an explicit error.
  No force kill, automatic restart or transfer-safety bypass was added.
- Kept the Settings-app percentage readout fully readable when its slider is
  disabled, consistently with the Files readout. Disabled sliders remain inactive.

## Completed live desktop acceptance

Checked on Ubuntu 24.04.5, GNOME Shell 46.0 / Mutter 46.2, Wayland,
GTK 4.14 / libadwaita 1.5, Nautilus 46.4, at 1920 × 1200.
Screenshot and input access used the normal desktop portals with explicit user
consent. Temporary appearance changes and Files restarts were separately approved.

| Case | Observed result |
|---|---|
| Calendar and Quick Settings, light/dark, white/dark/busy application backdrops | Rounded edges without doubled rims or rectangular blur; underlying windows, not just wallpaper, show through |
| Calendar empty state and real test notifications | Date, today marker, source, timestamp and notification body readable; banners and list cards stay bounded |
| Frost, Crystal and Solid comparison | Both tints show underlying windows; Solid hides the backdrop on the checked main fills |
| Readability boost in both schemes | Stronger tint without dimming text/icons; control distinctions retained |
| Files, maximized in both schemes | Solid content; translucent sidebar/header; no observed titlebar/layout regression |
| Real Files Properties dialogs, menus and location-entry focus | Readable solid dialogs/content, normal geometry, visible focus and rounded menus |
| Shell Run dialog in both schemes | Readable dialog and focused entry; no command executed |
| Native Settings, disabled sliders, keyboard focus and reset confirmations | Inactive controls distinguishable, value readouts readable, visible focus; confirmation defaults to Cancel |
| Native confirmed Files restart, both schemes | Actual quit/reopen reaches the saved-appearance confirmation, including the host's nonzero-quit case |
| Native GTK theme switching | Project theme becomes inactive and Files live-CSS status returns to unknown, rather than retaining a false restart guarantee |

The exact original preference and generated-CSS bytes, GTK theme, color scheme
and wallpaper URIs were restored and verified afterward. Files was reopened at
Home with the original appearance. Test notifications and temporary windows were
removed and the remote-desktop portal session was closed.
Private full-desktop captures are not distributed in the package.

These are scoped visual observations, not certification of every background,
display scale, GNOME/Nautilus version, third-party extension or accessibility
state. Default disabled slider marks retain their muted GTK treatment; no
disabled-state WCAG certification is claimed. Busy patterns can still distract
through transparent surfaces: use Readability boost or Solid when needed.
Files transparency remains experimental and unrelated applications are unchanged.

## Regression and release validation

- Python/GTK checks cover the nonzero-quit exit/owner/error paths,
  readable percentage labels and existing coordinated-update rollback tests.
- Extracted-release install/upgrade/uninstall under private HOME and D-Bus:
  old and new preference formats, original backup and wallpaper preservation.
- Executable modes, safe archive paths, version, shell syntax and SHA256 checked.
- No Shell theme CSS or opacity formula changes; the existing real St geometry,
  contrast and Solid-fill checks from 1.2.0 remain applicable.

The isolated installer skips apt/extensions and stubs user-systemd calls.
Fresh-machine extension installation and live purge are not certified.
Operational rollback does not promise filesystem-wide crash consistency.

## Upgrade and demo

With the existing dependencies/extensions installed:

```sh
tar xzf yaru-glass-theme-1.2.1.tar.gz
cd yaru-glass-theme-1.2.1
./install.sh --no-apt --no-extensions --theme-only --yes
```

This preserves profiles and saved appearance. Close/reopen Settings to load its
updated code. Open [the standalone demo](../demo/index.html) and reload an already-open
browser tab to see the new controls; it does not modify desktop settings.

```sh
sha256sum -c yaru-glass-theme-1.2.1.tar.gz.sha256
```

Earlier release archives are preserved.
