# Yaru Glass 2.2.3

## Scope

Private local diagnostics and compact native notification shadows for Ubuntu
24.04 / GNOME 46 and Ubuntu 26.04 / GNOME 50. Native lockscreen work remains the
planned 2.3.0 milestone. No telemetry or automatic uploads are introduced.

### Diagnostics

- Key Settings, worker, sync, managed-effect, wallpaper, extension and lifecycle
  events are recorded by default. Optional verbose mode adds safe DEBUG events.
- Settings has an asynchronous Diagnostics window with level filtering,
  refresh, copy, verbose toggle and explicit local report export.
- `yaru-glass-logs` provides show/follow, verbosity and sanitized JSON export.
  Existing report files are never overwritten.
- Private XDG state stores one active 2 MiB log and four rotations (10 MiB total).
  Owned files are 0600; the directory is 0700. A separate bounded lock serializes
  append/rotation without sharing the appearance lock.
- Records contain allowlisted actions/outcomes, operation IDs, selected safe
  fields and error categories/repository stack locations, not exception messages,
  credentials, personal paths, full preferences, backups, raw commands or journals.
- Settings/worker and lifecycle/helper operation IDs correlate failures with
  rollback. Worker stdout remains its single JSON response. Unavailable logging
  warns explicitly without changing the appearance action result.
- Normal upgrade/uninstall retains logs. Purge removes only known diagnostic
  log/preference files, retaining the empty coordination inode to avoid writer
  races. User-exported reports and unknown files are left untouched.

### Notifications

Native banner shadows change from 10px blur/3px offset to 3px/1px, inside their
existing 6px margins. Rounded glass, notification geometry and the inset keyboard
focus ring are preserved. Other popup shadows and the demo animation are unchanged.

## Validation

The implementation passed **209 tests on each GNOME 46/50 stack**, without skips,
including native GTK/WebKit, actual Blur my Shell consumers, diagnostic privacy,
permissions, concurrency, rotation, malformed input, export failures, UI async
behavior, worker stdout, rollback, sync recovery and isolated lifecycle/package
checks. Final runs verify the outer diagnostic state is untouched by the tests.

Actual St/Mutter notification checks pass **64 cases per stack** across light/
dark, Frost/Crystal, Solid, LTR/RTL and interactive states. The old 10px shadow
fails the new compact-shadow assertion. Bash syntax checks pass for installer,
uninstaller and packaging scripts. Markdown manual and roadmap HTML are regenerated.

The released Logo Menu GNOME 50 candidate was rechecked: version 45, tag 75631,
still calls `super.vfunc_event(event)` in `extension.js`. The existing omission
on GNOME 50 remains; metadata support is not interaction certification.

## Distribution and limits

The local package uses curated repository profiles, without live dconf capture:
`dist/releases/yaru-glass-theme-2.2.3.tar.gz` and its SHA256 file.
Earlier archives are preserved. No Git staging, commit, push or remote publication
is included. Installation is a separately requested in-place upgrade that retains
preferences and original backups, not a clean reinstall.

Guests use software rendering. GTK/WebKit checks and native St shadow bounds do
not certify every hardware driver, display scale, compositor capture or arbitrary
white/colored background. No final host screenshot or Files restart is included.
Reload requested is not proof of compositor pixels; appearance status retains
that distinction. See the [manual](MANUAL.md#local-diagnostics) for usage/privacy.
