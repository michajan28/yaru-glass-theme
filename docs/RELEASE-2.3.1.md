# Yaru Glass 2.3.1

## What changed

- **Save diagnostic reports:** Settings now retains the native destination
  chooser until you save, cancel, or close Settings. Previously its Python
  wrapper could be destroyed while the chooser loaded a folder, cancelling
  selection. Duplicate chooser requests are ignored and closing Settings
  destroys the pending dialog. Existing local-only, private JSON export and
  no-overwrite behavior are preserved.
- **Recover older development updaters:** the installed development validator
  reported in issue #8 rejects `CONTRIBUTING.md` and `SECURITY.md` in released
  archives. The released validator accepts both documents. Documentation now
  provides the verified 2.3.1 bootstrap needed to replace that older validator.
- **Package/updater compatibility:** packaging tests now run actual generated
  archives through the updater's checksum verification and safe extraction in
  all three packaging modes. A regression reproduces the older allowlist
  rejection and checks acceptance of both contributor/security documents.

## Updating

For released 2.3.0 installations, check and confirm the update through
**Settings → Updates** or `yaru-glass-update install`.

If Settings reports **Unexpected release payload path**, its older installed
validator cannot update itself using the same rejected archive. Close Settings,
download the 2.3.1 archive and checksum, and follow the
[verified local-archive bootstrap](MANUAL.md#one-time-bootstrap-for-existing-accounts).
This also applies to 2.2.4 installations without an updater. Use the updater
from the extracted 2.3.1 package, not the old installed command. The preserving
transaction retains preferences, wallpapers, customized profiles, extensions
and original backups. Do not rerun the normal installer for this repair.

Reopen Settings after installation. No Files restart or inactive-theme
activation is forced. No live installation was performed while preparing this
release.

## Validation evidence

- Native save-dialog lifetime reproduced before the fix: the chooser's weak
  reference was dead immediately after `choose_export` returned and garbage
  collection ran, without opening an actual desktop chooser.
- The public 2.3.0 archive downloads, verifies and extracts using the current
  validator. Read-only inspection confirmed that the reported installed
  development validator lacks the two top-level documentation entries.
- Focused suites pass: **59 Settings UI tests**, **23 updater tests**, and
  **9 repository-layout/packaging tests**. Settings checks include native chooser
  ownership, modal parent, cancellation, duplicate requests, cleanup on close
  and existing export success/no-overwrite/failure behavior.
- Shell syntax and whitespace checks pass. The Markdown manual was regenerated
  using Ubuntu's `python3-markdown` extracted into a private session directory,
  without installing system packages.
- Isolated lifecycle and preserving-bootstrap regressions pass in the full
  suite, using private HOME/XDG/D-Bus and mocked network/systemd operations.

## Compatibility and limits

Target stacks remain Ubuntu 24.04/GNOME 46 and Ubuntu 26.04/GNOME 50.
GNOME 50/VM revalidation and final live compositor/file-chooser interaction
checks were not performed. Automated ownership/export tests are not proof of
every desktop portal, filesystem provider, GPU or backdrop.

Logo Menu remains omitted on GNOME 50. The extension catalog still maps Shell
50 to version 45/tag 75631, and the latest upstream release remains
`v25.2_280926`; its released event handler still calls
`super.vfunc_event(event)`. No new GNOME 50 menu/Activities interaction checks
justify restoring it.

## Distribution

The `v2.3.1` release carries `yaru-glass-theme-2.3.1.tar.gz` and
`yaru-glass-theme-2.3.1.tar.gz.sha256`, built with curated repository profiles
without live dconf capture. Checksums provide integrity, not an independent
publisher signature. Historical releases and archives are unchanged.
