# Yaru Glass 2.3.0

## What changed

- **App updates:** manually check public stable GitHub releases and confirm
  installation from Settings or `yaru-glass-update`. No GitHub login, sudo,
  unattended update service or telemetry.
- **Preserving upgrades:** bounded HTTPS downloads, exact release assets,
  SHA-256 verification, safe archive staging, complete package/theme replacement
  and durable interrupted-update recovery. Keep saved preferences, wallpapers,
  customized profiles, extensions, ownership and the first-install backup.
- **Integrated Settings:** Shell, Applications, Wallpapers, Diagnostics and
  Updates share one navigation group. Diagnostics/Updates are inline pages, not
  popup windows. Narrow layouts use the same five-page dropdown.
- **Readable logs:** newest-first local timestamps/UTC offsets, emphasized
  severity/action summaries, indented fields/errors and correlation IDs.
  Copy uses readable text; storage and sanitized export remain structured JSON.
- **App grid:** clearer hover, keyboard focus and pressed states for tiles and
  folders, with more icon/label spacing.
- **Contributor workflow:** issue-linked PRs, CI and tag-triggered draft release
  packaging; visible progress checklists and bounded testing in project guidance.

## Updating

Existing 2.2.4 installations do not already contain the updater. Close old
Settings windows, download this release's archive and SHA-256 companion, verify
them, then run the extracted updater's local-archive bootstrap as described in
[Updating](MANUAL.md#6-updating). Bootstrap uses the same preserving transaction;
do not rerun the normal installer for a preservation-only upgrade.

Fresh installations still use `scripts/install.sh`. Later releases can be checked
from **Settings → Updates** or `yaru-glass-update check`. Updates apply to one
user account on one machine. No Files restart or inactive-theme activation is
forced. Close/reopen Settings after successful replacement.

Recovery is available through `yaru-glass-update recover`, or the retained
`~/.local/share/yaru-glass-update/runner/bin/yaru-glass-update` when the installed
command is unavailable. Rollback errors retain evidence and are shown explicitly.
Checksums hosted alongside the archive establish integrity against GitHub release
metadata, not an independent publisher signature.

## Validation evidence

- Updater coverage includes mocked network/API failures, unsafe archives,
  checksums, concurrent operations, staging/replacement failures, service/reload
  failures, interruptions and retryable recovery.
- An isolated private HOME/XDG/D-Bus fixture bootstraps a synthetic 2.2.4 install,
  then performs another release update using the installed CLI, with real
  staged Yaru generation and systemd/network stubs.
- Settings tests cover inline five-page navigation at normal/narrow widths,
  asynchronous update results/gates, readable diagnostics, privacy and JSON export.
- Investigated intermittent Settings/Files render failures: tests could capture
  an old paintable frame after stylesheet changes. Fixtures now request and wait
  for GTK's after-paint signal before sampling. The three affected tests pass
  together; expected alpha, unrelated-window opacity and solid-content
  assertions were not relaxed.
- Final source-tree regression gate on GNOME 46: **242 tests passed, no skips**.
  This includes isolated lifecycle and packaging checks. Shell syntax and
  `git diff --check` pass.
- Packaging now carries the upstream contributor/security documents referenced
  by README. The three affected package/lifecycle/bootstrap checks also pass
  after that payload-only adjustment.
- The manual was regenerated with Ubuntu's `python3-markdown` package extracted
  into a private session directory; no system package installation was needed.
  The roadmap HTML was updated alongside its Markdown source.
- Distribution checks verify the archive's checksum, version, required payload,
  safe extraction, executable updater, and absence of Git/caches/runtime state.

## Compatibility and limits

The existing target stacks remain Ubuntu 24.04/GNOME 46 and Ubuntu 26.04/GNOME 50.
This release is validated on the available **GNOME 46** environment only.
Ubuntu VM/GNOME 50 revalidation is explicitly deferred by the project owner.
Earlier dual-stack evidence is not certification of this update on GNOME 50.

Logo Menu stays omitted on GNOME 50. Its released version 45/tag 75631 still maps
to Shell 50, and released upstream `v25.2_280926` source still calls
`super.vfunc_event(event)`. No new GNOME 50 menu/Activities interaction checks
were available; metadata alone does not justify restoring the integration.

The owner visually accepted the inline UI and readable logs. No new compositor
captures certify arbitrary backgrounds, GPUs or scales, and no new live
install/uninstall/extension-upgrade matrix is claimed. Desktop themes, profiles
and preferences were not changed while preparing this release.

## Distribution

Package with curated repository profiles, without live dconf capture:
`dist/releases/yaru-glass-theme-2.3.0.tar.gz` and
`dist/releases/yaru-glass-theme-2.3.0.tar.gz.sha256`.
Historical archives/releases are not overwritten. The release tag is `v2.3.0`;
publication assets are attached to the GitHub release.
