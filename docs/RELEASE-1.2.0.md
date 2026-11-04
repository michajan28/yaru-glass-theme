# Yaru Glass 1.2.0

> Historical record: naming in this document has been normalized to Yaru Glass.
> Command examples do not identify preserved historical archives, which have not
> been renamed or rebuilt. Use the README for current installation instructions.

Tested preview for Ubuntu 24.04 / GNOME Shell 46 / Nautilus 46.
This release adds coordinated control and recovery, not broader app support or blur.

## Changes

- Confirmed Solid, Balanced Frost and Clear Crystal presets, with before/after
  values and no wallpaper changes or automatic Files restart.
- Genuine opaque primary Shell fills in Solid mode; ordinary slider level 0
  retains its previous meaning. Nested hover/selection layers stay appropriate
  to their parent, and focus/today markers are preserved.
- Optional shared readability boost, off by default. It halves the remaining
  backdrop contribution (`alpha + (1-alpha)/2`); it never changes slider levels,
  enables integrations, dims text/icons, or makes file content translucent.
  Crystal/50 app minimum alpha becomes .85 light / .90 dark; Files becomes .85.
- Shared locked worker for coordinated updates, partial-field merging and
  handled-failure rollback of preference bytes, CSS and managed effects.
- Explicit saved/reload-requested/inactive/unknown/restart-required states and
  confirmed section resets. All retries for a failed preset retain the complete
  operation, rather than retrying just one integration.
- Full-foreground Settings explanatory labels even with app transparency off.
- Updated independent-window HTML demo, manuals and maintenance knowledge base.

Old preference files default missing `solid` and `readability_boost` to false.
Installing/rebuilding does not rewrite them or select a preset.
No new persistent preference file or runtime dependency was added.

## Upgrade

With existing dependencies/extensions installed, extract and run:

```sh
cd yaru-glass-theme-1.2.0
./install.sh --no-apt --no-extensions --theme-only --yes
```

These flags preserve extension profiles. First-time installation uses
`./install.sh`. Close and reopen Yaru Glass Settings to load its new code.
Finish transfers before an explicitly confirmed Files restart; tabs/windows
are not restored, only Home is opened.

Normal uninstall retains preferences and restores the original appearance backup:

```sh
~/.local/share/yaru-glass/uninstall.sh
```

## Automated validation

- 95 Python/GTK/WebKit regression tests, including migrations, invalid inputs,
  partial-field preservation, preset cancel/apply, reset isolation, retry,
  failed writes/generation/effects/reloads and explicit failed rollback.
- Rollback verifies byte preservation including CRLF and previously absent files.
- Native rendered Settings and Files-style split-pane alpha checks cover both
  schemes/styles, levels 0/25/50, enablement and boost. File content/controls stay
  opaque, whole-window opacity stays 1, unrelated windows stay unstyled.
- Normal foreground contrast is tested against sampled black/white/colored
  backdrops: Shell minimum 6.47:1 over the tested matrix; native Settings and
  Files-style normal text meet 4.5:1. Disabled-state accessibility and arbitrary
  backdrops are not certified by these tests.
- Real GNOME St layout covers both schemes/styles and normal/Solid/boost:
  bounded notification preferred/allocated width, LTR/RTL padding and opaque
  headers across normal/hover/focus/active. Additional St checks verify primary
  Solid fill alpha is 255, including panel, calendar/menu, dock, dialogs and OSD.
- Installed WebKit exercises 48 light/dark/style/level/solid/boost combinations,
  independent app/Files alpha, opaque content, preset cancel/apply, keyboard tabs
  and 390px layout. Rendered demo/native Settings snapshots were inspected.
- Extracted-release lifecycle: private HOME and D-Bus, actual install, old-config
  upgrade, new solid/boost upgrade and normal uninstall. Preferences, wallpaper
  URIs and original backup survive upgrades; uninstall restores original GTK
  theme/font/user stylesheet and retains preferences.
- Installer/uninstaller/package shell syntax and archive SHA256 checks.

The isolated installer uses `--no-apt --no-extensions --theme-only`; user systemd
calls are stubbed and builds run with the project GTK theme inactive because no
Shell extension process runs on the private bus. This is not full fresh-machine
extension-install certification. Live purge is not exercised.

Run regressions with `/usr/bin/python3 -m unittest discover -s tests`.
Native tests require a display and installed GI modules; browser tests additionally
use WebKit 6 when available and otherwise explicitly skip.

## Manual desktop acceptance: still pending

**Follow-up:** the checklist below records the original 1.2.0 preview status.
These checks have since been completed with consent-based desktop portals;
see [1.2.1 results and the discovered restart fix](RELEASE-1.2.1.md).

Desktop screenshot access was denied during 1.1.0 validation. Native snapshots,
WebKit renders and headless St actors do not prove final live compositor output.
No new screenshot permission bypass was attempted and no Files restart was
performed without confirmation. The following checklist remains user-assisted:

| Case | Required observation | Status |
|---|---|---|
| Light/dark popups over white, dark and busy windows | Rounded edges without doubled rims or rectangular bleed | Not verified |
| Calendar and notifications | Date, source, time, empty state and today's marker readable | Not verified live |
| Solid vs both transparent presets | Main fills opaque in Solid; underlying windows visible otherwise | Automated only |
| Boost off/on in both schemes | Stronger tint, unchanged text/icon opacity and control distinctions | Automated only |
| Maximized Files and dialogs | Solid file area, no layout or titlebar regression | Not verified |
| Keyboard focus and disabled controls | Focus visible; disabled state distinguishable and readable | Not verified live |
| Theme switching and restart-required status | No false claim that already-running Files loaded new CSS | Automated only |

For visual checks, record current preferences first and restore those exact values
afterward. Never close Files with active transfers. Supply screenshots or manual
observations for the rows above before describing this preview as fully
desktop-accepted.

Rollback handles reported operational failures, not arbitrary process termination
or filesystem-wide crash consistency. GTK/Nautilus live CSS is unknown on startup;
a successful restart request is not pixel-level verification. No transparency
guarantee is made for unrelated apps or every background.

## Verify download

```sh
sha256sum -c yaru-glass-theme-1.2.0.tar.gz.sha256
```

The archive root is `yaru-glass-theme-1.2.0/`. Caches, runtime backups/state,
preferences and generated themes are excluded. Earlier release archives remain
available and are not overwritten.
