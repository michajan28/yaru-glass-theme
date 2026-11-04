# Yaru Glass 2.0.0

> Historical record: naming in this document has been normalized to Yaru Glass.
> Command examples do not identify preserved historical archives, which have not
> been renamed or rebuilt. Use the README for current installation instructions.

Dual-stack release for **Ubuntu 24.04 / GNOME Shell 46** and
**Ubuntu 26.04 / GNOME Shell 50**, retaining both light/dark theme names and
existing settings, independent opt-ins, original backups and rollback behavior.
Prepared locally on 26 October 2026; this date is not a remote publication date.

## Changes

- Build Shell themes from Ubuntu 26.04's `Yaru` / `Yaru-dark` bases while keeping
  the colored 24.04 bases preferred. GTK still uses the Yaru-blue resources.
- Replace modern dynamic accent tokens and override modern Yaru panel rules so
  the light panel, overview, status icons and workspace indicators remain coherent.
- Detect the running Blur my Shell effect layout and recover managed appearance
  when the extension becomes active after login. Do not reactivate a project
  theme after the user selects another GTK theme.
- Validate extension releases against both the service compatibility map and
  downloaded archive metadata. Incompatible archives and schema failures are
  explicit errors; unavailable optional releases are reported.
- Keep Logo Menu on Ubuntu 24.04, but omit its installation, enabling and profile
  application on GNOME 50. Standard Activities is retained instead.
- Remove Search Light integration and the ImageMagick dependency on both stacks.
  Independently installed copies, original backups and legacy ownership records
  are preserved; GNOME's built-in search remains available.
- Use the stable `src/`, `scripts/`, `bin/`, `assets/` and `docs/` layout.
  Runtime commands and installed backup/preference paths stay compatible.
- Keep Files transparency experimental, now verified on Nautilus 46 and 50;
  remove the stale GNOME-46-only description from Settings.

## Test environments

| Component | Ubuntu 24.04 | Ubuntu 26.04 |
|---|---|---|
| Ubuntu | 24.04.5 | 26.04.1 |
| Shell / Mutter | 46.0 / 46.2 | 50.1 / 50.1 |
| Nautilus | 46.4 | 50.2.2 |
| GTK / libadwaita | 4.14.5 / 1.5.0 | 4.22.4 / 1.9.1 |
| Yaru | 24.04.2 | 26.04.5.1 |
| Session | Wayland | Wayland, software-rendered VM |

The 26.04 environment is an isolated persistent VM made from a verified official
cloud image with Ubuntu Desktop installed, not a Desktop ISO installation test.
Finish Ubuntu's first-run wizard before installing the theme: its appearance page
can reset the selected GTK theme at each unfinished login.

## Completed validation

- **116 Python/GTK/WebKit tests passed on each stack, with no skips**, including
  the new isolated lifecycle test and Settings wording regression.
- **48 real St/Mutter stylesheet combinations per stack** checked notification
  geometry, panel opacity, icon foreground inheritance and Solid fills.
- **14 real Files 50 cases / 28 desktop captures** covered both schemes,
  Frost/Crystal, boost off/on, level 0 and the independent opt-in disabled.
  Sidebar/header effective opacity matched the formulas within 0.3 percentage
  points; sampled file-content pixels stayed unchanged between black/white
  backdrops and fully opaque.
- **Eight GNOME 50 Shell/Settings configurations / 48 captures** covered both
  schemes with Frost, Crystal, boosted Crystal and Solid. Actual Quick Settings,
  calendar, notification banners and all Settings pages were inspected.
  Accessibility controls and managed-effect keys matched the selected cases.
- Real Settings interactions verified preset Cancel without preference/CSS
  changes and Apply saving the coordinated snapshot while preserving boost and
  wallpapers without restarting Files. Separate Files restart Cancel retained
  the process; Confirm replaced it and reported success.
- Guest installation, preference-preserving upgrade and a clean reboot were
  checked. Original guest appearance/CSS bytes were restored after acceptance.
  No new CSS, Shell JavaScript or sync errors were observed in those checks.
- Actual install, theme-only upgrade, uninstall and purge scripts passed in
  copied fixtures on both stacks with private HOME/XDG and session D-Bus.
  User-systemd, extension removal and font-cache calls were stubbed. Checks
  cover original backups, mixed preferences, legacy records, managed effects,
  conditional wallpapers, original GTK CSS and extension ownership boundaries.
- The checksum-verified original **1.2.1 archive** was installed in a separate
  Ubuntu 24.04 fixture and upgraded/restored with the new scripts. All three
  preferences and original backups stayed byte-identical, legacy extension
  state survived, and the dark scheme was respected.
- Installer/uninstaller/packager Bash syntax passed. Packaging regression checks
  default/custom output, checksums, executable modes and extracted build imports.

The existing Ubuntu 24.04 live desktop evidence is recorded in
[1.2.1 release notes](RELEASE-1.2.1.md). No live host install, sync or uninstall
was performed during the 2.0.0 work.

## Extension recheck and limitations

The release-time GNOME 50 Logo Menu query still selects **release 45 / 25.2**.
Its archive still calls `super.vfunc_event(event)` in `extension.js`, the same
event path that produced the observed StWidget error during guest validation.
It remains omitted on GNOME 50; it was not re-enabled solely to reproduce the
known failure. Recheck the released upstream fix and actual menu interaction
before restoring this integration in a later release.

These results do **not** certify arbitrary wallpaper accessibility, every submenu
or display scale, hardware rendering on 26.04, X11, Desktop ISO installation,
fresh-machine apt/extension downloads or live desktop purge. Automated guest UI
fixtures still warn about missing default Adwaita JXL wallpapers; the actual
desktop previews use installed Ubuntu images successfully. Files transparency
remains opt-in and experimental. Use Readability boost or Solid for distracting
backgrounds; no opacity formula or whole-window fade was introduced.

## Local package and upgrade

The local archive is `dist/releases/yaru-glass-theme-2.0.0.tar.gz`, accompanied by
`yaru-glass-theme-2.0.0.tar.gz.sha256`. It contains the repository-supplied profiles,
not a capture of the build machine's desktop settings. Packaging runs in a copied
tree with isolated HOME/XDG and a private `dconf` stub that supplies those existing
profiles to the unchanged exporter. Source profiles and older archives are kept.
No Git commands, commits, pushes or remote publication are part of this release.

For an existing installation with dependencies/extensions already present:

```sh
sha256sum -c yaru-glass-theme-2.0.0.tar.gz.sha256
tar xzf yaru-glass-theme-2.0.0.tar.gz
cd yaru-glass-theme-2.0.0
./scripts/install.sh --no-apt --no-extensions --theme-only --yes
```

The upgrade preserves appearance preferences and the original first-install
backup. Close/reopen Settings after upgrading. Files CSS changes need a separate,
explicit restart after transfers finish. Fresh installation uses
`./scripts/install.sh`; do not run either installer with sudo.

The next proposed milestone is **2.1 visual coherence**, followed by **2.2 reliable
releases** and **2.3 personal appearance profiles**; see the [roadmap](ROADMAP.md).
