# Yaru Glass 2.4.0

## What changed

- Independent **Yaru Glass Lock Screen** extension for GNOME 46 and 50,
  distributed as its own version-1 ZIP alongside the theme.
- Native session lock screen with independent wallpaper, clock format/weight,
  appearance options, responsive layout and scrolling notifications.
  GNOME retains authentication, notification grouping and privacy. GDM is unchanged.
- Standard extension Preferences with local image validation/preview,
  follow-desktop action and confirmed reset. No theme app or sync service required.
- Normal theme installation adds the companion without enabling it or turning
  customization on. `--no-extensions` and `--theme-only` skip installation.
  Compatible existing copies are retained; incompatible/symlinked collisions
  fail explicitly. Only newly added copies enter existing ownership records.
- Theme updater, transaction/archive format and app pages are unchanged.
  Activation stays in Extensions/Extension Manager; app integration is omitted.
- Release validation targets the theme, native app and extension.

## Updating existing accounts

Update the theme using **Settings → Updates** or `yaru-glass-update install`.
The preserving update does **not** install or update extensions.
Do not rerun the normal theme installer just to obtain the lock screen.

Download the separate extension ZIP and its checksum from this release.
In their download directory:

```bash
sha256sum --check lockscreen@yaru-glass-v1.shell-extension.zip.sha256
gnome-extensions install ./lockscreen@yaru-glass-v1.shell-extension.zip
```

Log out/in if the new extension is not listed. In Extensions or Extension Manager:

1. Enable **Yaru Glass Lock Screen**.
2. Open its **Preferences**.
3. Turn on **Custom lock-screen appearance** and choose your options.

If you already installed the private independent v1 ZIP, you do not need to
replace it just to update the theme. An older incompatible prototype is not
silently overwritten. For a deliberate replacement, close Preferences, inspect
the new ZIP, run `gnome-extensions install --force NEW_EXTENSION.zip`, then log out/in.

Older development updaters that reject contributor/security documents still
need the [existing verified bootstrap](MANUAL.md#one-time-bootstrap-for-existing-accounts).
There is no new updater migration for 2.4.0.

## Validation evidence and limits

- Independent extension validation passed on GNOME 46/50, including packed
  standalone Preferences, local companion installation, preservation/collision
  handling and the 36-case native allocation/scrolling matrix.
- The same private v1 ZIP opened real Preferences and rendered the custom native
  lock screen alongside active Blur my Shell in both VMs.
- The owner installed that ZIP on GNOME 46 and confirmed the custom lock screen
  works on their account.
- One bounded GNOME 50.1 standard disable/enable cycle passed in 0.53/0.19
  seconds. Shell remained responsive after 10 seconds with the same process ID;
  saved preferences and extension policy/order were preserved.
- An earlier intermittent GNOME 50 Shell freeze during uninstall/restoration
  has no established root cause or reliable reproduction. The successful
  standalone check does not prove a fix; no speculative workaround was added.
- Full native release suite: **220 tests passed without skips on each VM**,
  Ubuntu 24.04 / GNOME 46.0 and Ubuntu 26.04 / GNOME 50.1. Includes native
  Settings/Files rendering, extension Preferences/layout, updater, diagnostics,
  pipeline consumers and isolated packaging/install/upgrade/uninstall fixtures.
- Installer, uninstaller and packaging scripts passed Bash syntax checks.
- Packaging regressions passed in curated, default and custom-output modes,
  including checksum verification and the unchanged updater's safe extraction,
  archive exclusions, executable modes and profile preservation.

VM checks do not certify every GPU, monitor layout, accessibility configuration,
image provider or wallpaper. Earlier native password/privacy checks remain
historical evidence, not a new broad authentication audit.
Logo Menu remains omitted on GNOME 50. The released catalog still selects
version 45/tag 75631; a fresh read-only source check confirmed that its event
handler still forwards to `super.vfunc_event(event)`. It was not installed or
enabled for this release, and no new interaction-support claim is made.

## Distribution

The release contains the theme archive and SHA-256 file plus the standalone
extension ZIP and its SHA-256 file. Theme packaging uses curated repository
profiles without live desktop capture. Extension source is GPL-3.0-or-later;
its ZIP includes COPYING and NOTICE, not theme assets, fonts or wallpapers.
Checksums provide integrity, not an independent publisher signature.
Historical release archives remain unchanged.
