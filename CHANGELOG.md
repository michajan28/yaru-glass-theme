# Changelog

Notable changes to Yaru Glass, newest first. `VERSION` is the release version;
repository-only changes remain under Unreleased until a release is prepared.
Release dates are omitted because the available records do not consistently
record them. Validation dates are not treated as publication dates.

## Unreleased

### Added

- Manual stable GitHub release checks and confirmed app/theme updates through
  Settings **Updates** and `yaru-glass-update`, without GitHub login, sudo,
  unattended updates or extension/profile resets.
- Bounded HTTPS downloads, exact release assets and SHA-256 verification,
  validated archive staging, complete generated-theme replacement, lifecycle
  coordination, and persistent recovery for failed/interrupted updates.
- Verified local-archive bootstrap for existing installations, with isolated
  synthetic 2.2.4-to-feature and subsequent installed-CLI upgrade regressions.
  Settings distinguishes installation, reload requests and relaunch/Files
  restart requirements; no Files restart or inactive-theme activation is forced.

### Changed

- The next feature milestone is **2.3.0 app updater**; custom lock screen moves
  to Later, unnumbered. No release/version bump is included.
- Installer, uninstaller, generation and sync coordinate with the updater.
  Purge removes updater-owned runner/staging data and its launcher, retaining
  the coordination inode. Native updater and failure/recovery tests use private
  HOME/XDG and mocked networking or isolated desktop services.

## 2.2.4

Notification halo and Diagnostics discoverability fix. See
[release evidence and validation limits](docs/RELEASE-2.2.4.md).

### Fixed

- Notification banners no longer show a square gray halo around their rounded
  corners. GNOME Shell drew the banner's outer shadow as a rectangle when the
  Layered gradient was also applied; banners now keep a flat tint with the small
  rounded shadow. The 2.2.3 shadow-size change alone did not fix this; real
  compositor captures on GNOME 46 and 50 confirm the fix.
- Settings now shows a labeled **Diagnostics** button at the start of the header
  instead of an unlabeled information icon beside the window controls.

### Tests

- The native St notification check now runs in the unit suite on a private
  D-Bus session and rejects a gradient on notification banners. It skips when
  GNOME Shell St/Mutter typelibs are unavailable. A Settings UI test checks that
  the Diagnostics button stays visible and labeled at default and narrow sizes
  and opens the viewer.

## 2.2.3

Local diagnostic logging and native notification shadow release. See
[release evidence and validation limits](docs/RELEASE-2.2.3.md).

### Added

- Private local diagnostic logging for meaningful Settings, worker, sync,
  managed-effect, wallpaper, extension and lifecycle actions/errors. Default
  logging excludes personal paths, exception text, commands and full preferences;
  verbose mode is independent of appearance settings.
- Native Settings Diagnostics viewer with level filtering, refresh, copy,
  verbose toggle and explicit sanitized local JSON export. The installed
  `yaru-glass-logs` command provides show/follow, verbosity and export.
- Private bounded log rotation (five files, 2 MiB each), correlated operations,
  safe error locations and isolated privacy/concurrency/lifecycle regressions.
  Normal uninstall keeps diagnostics; purge removes known log/preference files,
  retaining the empty coordination lock to avoid concurrent-writer races.

### Fixed

- Reduce native notification banner shadows from 10px blur/3px vertical offset
  to 3px/1px, fitting inside the existing 6px margins. Preserve the keyboard
  focus ring, rounded glass and notification layout.

### Validation

- Full suite: 209 tests pass, no skips, on each isolated GNOME 46/50 stack.
  Final runs confirm the tests leave their outer diagnostic state untouched.
- Native St notification checks pass 64 light/dark, Frost/Crystal, Solid,
  LTR/RTL and interactive-state cases per stack; the previous 10px shadow fails
  the new compact-shadow assertion. This does not certify every live backdrop
  or hardware/compositor configuration.
- Related Markdown/HTML documentation regenerated. The package uses curated
  profiles without live desktop capture; historical archives are preserved.

## 2.2.2

Local demo reliability hotfix. See
[release evidence and validation limits](docs/RELEASE-2.2.2.md).

### Fixed

- Center desktop-demo notification banners with opposing insets and automatic
  margins instead of an animated percentage translation. GNOME 46 WebKit could
  resolve that translation to zero during early animation layout, putting the
  banner off-center and overflowing mobile widths. Vertical slide/fade animation
  and reduced-motion behavior are preserved.

### Validation

- New regression checks exact banner bounds and centering at four animation
  positions across four viewport widths; it fails against the old CSS. A separate
  reduced-motion check confirms centered, non-animated notifications.
- Ten independent complete demo runs pass on each GNOME stack: 29 tests per run,
  290 per stack, with the original mobile overflow assertions unchanged.
- Locked guest sessions independently reproduce the viewport-resize timeouts.
  UI checks require an unlocked, unblanked session; no desktop locking policy or
  sandbox restriction was changed by the fix.

## 2.2.1

Local pipeline compatibility hotfix. See
[release evidence and validation limits](docs/RELEASE-2.2.1.md).

### Fixed

- Encode Blur my Shell color parameters as native four-double tuples, not arrays
  of variants. The old encoding caused the whole library to be rejected, hiding
  Yaru Frost/Crystal pipelines and falling back to Default for panel, popup and dock.
- Repair already-affected libraries even when unpacked settings and assignments
  are unchanged. Preserve unrelated pipelines, color values, preferences and
  ownership records; restoration uses the corrected encoding too.
- On format repair only, restart Blur my Shell through its supported enable/disable
  API, confirming disabled/active state and clearing already-cached Default
  actors on all three components. Ordinary reapplication remains idempotent.
  Activation failures are reported and managed settings rolled back.

### Validation

- Full 176-test suite passes on GNOME 46 and GNOME 50 without skips.
- New regressions use the installed extension's actual GJS parser, settings and
  pipeline manager, rejecting the old encoding and accepting all six managed IDs.
- Disposable guests reproduce corruption with the real old writer, then verify
  actual panel, popup and dock actors use Frost/Crystal with effects attached.
  Native preferences show all six named pipelines; blur-off, Solid, unrelated
  pipelines, idempotency and restoration are checked as well.

## 2.2.0

Local Layered glass and integration release. See
[release evidence and validation limits](docs/RELEASE-2.2.0.md).

### Changed

- Combined the desktop and lock-screen previews into one offline demo. It starts
  at account selection, opens the desktop after simulated login, returns to the
  lock screen when locked, and returns to account selection after logout.
- The lock-screen concept demo now has three fictional accounts, a **Switch user**
  action, a login-style account list with session status, simulated log in and
  log out, and separate mock notifications for each account. It remains an
  offline simulation and does not change desktop settings or authentication.
- The theme demo is now a clickable Ubuntu desktop simulation with Yaru Glass
  applied: top bar, Quick Settings, calendar and notifications, dock,
  Activities overview with window previews, app grid, and Settings, Files and
  Terminal windows. It uses bundled Yaru icons, Shell-style regular-weight
  text, Adwaita-style scrollbars, and photo, white and dark wallpapers for
  contrast checks.
- Layered Frost/Crystal now add illuminated gradients and inset reflections to
  Shell surfaces and independently enabled Settings/Files backgrounds. The
  desktop demo delivers Layered by default; exploratory sample choices are removed.
- Added a default-on **Dynamic background blur** preference for managed Shell
  panel, popup and dock backgrounds. Solid suppresses blur without losing the
  preference; presets preserve it. Rounded Blur my Shell backgrounds use live
  window content, not wallpaper-only blur. Settings and Files remain unblurred.
- Ubuntu Dock running indicators use native **DASHES** and each icon's dominant
  color, with window-count semantics and matching demo indicators.
- The desktop demo opens Settings as a floating 540px window after login, matching
  the native layout. Preset/style selectors use Ubuntu-style custom popovers with
  selected-row indicators, keyboard navigation and focus restoration.
- Added `--curated-profiles` packaging without live dconf capture and refusal to
  overwrite an existing archive or checksum. Missing Markdown rendering is
  reported explicitly when packaging the existing HTML manual.
- Extension installation/enabling enforces exact per-stack tested releases and
  Ubuntu package versions. Existing mismatches are diagnosed, not silently replaced.
  Managed blur checks the active release and rounded dynamic renderer. Curated
  profiles no longer import legacy/refraction pipelines or enable application blur.
  The legacy dock helper now reuses reversible managed effects and saved opt-ins.

### Fixed

- Extension activation uses one batch request and waits for reported Shell state,
  avoiding duplicate enable requests observed on GNOME 46.
- One-shot sync failures return an error status. Installation reports incomplete
  managed appearance instead of printing a successful activation message.
- Files preset/action buttons wrap on narrow native Settings windows, preserving
  the existing small-window width requirement on newer GTK/libadwaita.
- Fixed real login messages from offline demo iframes: Chromium reports their
  origin as `null`. The exception is restricted to `file:` pages and still
  requires the exact expected iframe sender.

### Validation

- The full 168-test suite, including all 27 demo tests, now passes on both stacks.
  The GNOME 46 guest launch issue was a test-environment configuration error, not
  missing GNOME 46 demo support: a dedicated AppArmor test profile permits
  WebKit's sandbox namespaces, and idle inhibition preserves live UI frames.
  No demo assertions were weakened or sandbox disabled. See
  [release evidence and validation limits](docs/RELEASE-2.2.0.md).

## 2.1.1

Local branding and lock-screen demo release. See
[release notes and validation limits](docs/RELEASE-2.1.1.md).

### Changed

- Renamed the project to Yaru Glass throughout sources, commands, Python modules,
  CSS files/tokens, theme names, app IDs, services, profiles, documentation and
  browser demos. Removed platform-specific branding and font comparisons.
  This is a breaking rename with no legacy aliases or automatic migration;
  earlier installations must be removed with their own uninstaller first.
  Existing desktop installations and historical archives are not modified.
- Documented Yaru attribution, component-specific reuse and redistribution
  obligations, and unofficial/non-endorsed status in the README and both manuals.
  Corrected the blanket claim that Yaru material is not redistributed: generated
  themes contain copied and modified Yaru Shell stylesheets and assets.

### Added

- Added an independent, offline lock-screen browser concept with three photographic
  wallpapers, clock format/weight controls, light/dark appearance, fictional profile
  customization, privacy-aware mock notifications, and simulated unlock/relock.
  It does not collect passwords, integrate with GNOME locking or change the desktop.
- Added WebKit coverage for lock-screen transitions, keyboard focus, notification
  privacy, local assets, clock formats and narrow/short viewport layouts.

### Fixed

- Fixed managed Blur my Shell pipeline serialization for tuple-valued settings,
  including RGBA colors returned by the extension.

## 2.1.0

Local visual-coherence release. See [release notes, checks and limits](docs/RELEASE-2.1.0.md).

### Changed

- Replaced raw reset summaries with named before/after values grouped by Shell,
  Settings app and Files. Invalid saved values are identified as unavailable
  instead of presenting fallback defaults as the previous state; Cancel remains
  the default response, and Files never restarts automatically.
- Made demo preset previews use the same named sections and readable values as
  native Settings.
- Added compact page navigation for narrow Settings windows and prevented
  scrolling pages from forcing horizontal overflow.

### Added

- Added white, dark and busy sample backdrops to the standalone demo for
  comparing sampled surface contrast without changing desktop settings.
- Added focused regression coverage for confirmation content, small Settings
  windows, and demo backdrops and preset parity.

## 2.0.0

Local dual-stack release for Ubuntu 24.04 / GNOME 46 and Ubuntu 26.04 / GNOME 50.
See [release notes, checks and limitations](docs/RELEASE-2.0.0.md).

### Changed

- Kept Logo Menu on Ubuntu 24.04 but omitted its install/enabling and profile
  application on GNOME 50 due to the released extension's event-handler error.
  Recheck upstream compatibility before each release; existing copies are not removed.
- Removed Search Light installation, profiles, shortcut customization, color
  synchronization and the ImageMagick dependency on both Ubuntu stacks. Use
  GNOME's built-in search instead. Upgrades preserve existing extension settings,
  original backups and ownership records for uninstall compatibility.
- Prioritized dual-stack Ubuntu 24.04 / GNOME 46 and Ubuntu 26.04 / GNOME 50
  compatibility for 2.0.0; moved the former 1.3/1.4/1.5 roadmap milestones
  to 2.1/2.2/2.3. The two stacks share appearance preferences and rollback contracts.
- Flattened the version-named project directory into a stable repository root.
- Separated Python modules and theme sources under `src/`, maintenance tools
  under `scripts/`, runtime commands under `bin/`, and fonts/profiles under `assets/`.
- Moved manuals, roadmap, and maintenance documentation into `docs/`.
- Preserved historical archives/checksums in `dist/releases/` and generated theme
  snapshots in `dist/themes/`, both excluded from Git.
- Updated runtime imports, installer paths, documentation links, and packaging
  defaults for the new layout. Maintenance scripts use Ubuntu's system Python.

### Added

- Recorded eight GNOME 50 light/dark Shell/Settings desktop configurations,
  including actual preset Cancel/Apply and confirmed Files restart interactions.
- Added private-HOME/private-D-Bus install, upgrade, uninstall and purge coverage
  for both Ubuntu stacks, including preferences, legacy records, conditional
  wallpapers, managed effects and extension ownership. Separately verified the
  original 1.2.1 archive's theme-only upgrade/restoration on Ubuntu 24.04.
- Recorded consent-based real Files 50 compositor checks on Ubuntu 26.04:
  14 light/dark, Frost/Crystal, boost and independent opt-in cases matched the
  intended sidebar/header opacity while sampled file content stayed opaque.
  Software-rendered VM checks do not certify arbitrary backgrounds,
  every hardware renderer or every desktop configuration.
- Local Git setup instructions, ignore rules, and text/binary attributes.
- This changelog, project agent guidance, and an on-demand release workflow skill.
- Isolated packaging tests for default/custom output, checksums, payload contents,
  extracted build imports, and protection against purging a source checkout.

### Fixed

- Removed the stale "Nautilus 46 only" Settings description after verifying
  Files 50, keeping the feature experimental and documenting validation limits.
- Sync retries managed appearance when Blur my Shell becomes active after login,
  instead of leaving a startup activation failure unrecovered. Selecting another
  GTK theme still prevents automatic project-theme reactivation.
- Extension downloads verify the requested Shell version in both the service's
  compatibility map and the archive metadata instead of installing an incompatible
  fallback release. Schema compilation errors are no longer ignored.
- Shell generation and installer preflight accept Ubuntu 26.04's uncolored
  `Yaru` / `Yaru-dark` Shell bases while retaining the 24.04 colored bases.
  Modern Shell accent tokens use the matching light/dark project blue palette.
- Panel tint and overview transparency override Ubuntu 26.04 Yaru's forced
  dark-panel rules, preventing dark text on an opaque dark panel in light mode.
- Managed glass detects effect files in the running Blur my Shell extension,
  supporting both legacy Gaussian and newer Dual Kawase layouts without writing
  obsolete blur types or manual corner effects to newer versions.
- Shell appearance no longer requires Blur my Shell's optional Dock corner-radius
  setting; the managed Dock pipeline supplies its rounding and older restoration
  records remain supported.
- Installation and packaging now select an explicit payload rather than copying
  the entire repository, excluding Git metadata, release outputs, and local state.
- The uninstaller refuses `--purge` when invoked from a source checkout.

## 1.2.1

### Changed

- Polished the standalone demo with themed controls, rounded preference groups,
  scheme-aware confirmation dialogs, keyboard focus, and reduced-motion support.
- Recorded consent-based live desktop acceptance on Ubuntu 24.04 / GNOME 46,
  including popup geometry, transparency, Files dialogs, and restart behavior.

### Fixed

- Handled Nautilus 46 returning a nonzero quit status after exiting: verify
  session D-Bus ownership before reopening Home, and report unverifiable exits.
- Kept the Settings-app percentage readout readable when its slider is disabled.

Appearance formulas and saved values are unchanged from 1.2.0. Files transparency
remains experimental; live observations do not certify every backdrop or platform.
See [1.2.1 release notes](docs/RELEASE-1.2.1.md).

## 1.2.0

### Added

- Confirmed Solid, Balanced Frost, and Clear Crystal presets with before/after values.
- Truly opaque primary Shell surfaces in Solid mode, without redefining slider level 0.
- Optional readability boost that strengthens tint without dimming text/icons,
  changing sliders, enabling integrations, or making file content translucent.
- Shared locked appearance transactions with partial-field merging and rollback
  for reported preference, CSS, managed-effect, and reload failures.
- Explicit saved, reload-requested, inactive, unknown, and restart-required states;
  confirmed section resets and retries that retain the complete operation.

### Changed

- Preserved existing preference behavior through defaults for missing Solid/boost flags.
- Kept explanatory Settings labels at full foreground contrast.
- Updated the independent-window demo, manuals, and maintenance documentation.
- Expanded regression, geometry, contrast, and isolated lifecycle validation.

No broader app support or backdrop blur was introduced. See
[1.2.0 release notes](docs/RELEASE-1.2.0.md).

## 1.1.0

### Added

- Native Settings pages for Shell, Applications, and Wallpapers.
- Independent opt-in Settings-app and Files transparency with solid controls/content.
- Separate light/dark wallpaper pickers with thumbnails, Files presets,
  actual-opacity readout, independent reset, and confirmed restart.

### Changed

- Refined readable borderless Shell surfaces, the calendar, and Quick Settings.
- Provided Frost/Crystal transparent tints, not wallpaper-only or live backdrop blur.
- Updated the browser demo with three pages, independent appearance controls,
  solid file content, and keyboard-accessible tabs.
- Documented profile-preserving upgrades and expanded automated/native validation.

The browser demo never modifies the desktop. A confirmed Files restart closes
existing windows and reopens Home, not previous tabs. See
[1.1.0 release notes](docs/RELEASE-1.1.0.md).

## 1.0.0

### Added

- Initial translucent glass-style light and dark themes for Ubuntu 24.04, built on
  Yaru while retaining Ubuntu icons.
- User-level installation and uninstall commands.
- Markdown/HTML user manuals and theme screenshots.

This baseline is reconstructed from the README in the preserved
`yaru-glass-theme-1.0.0.tar.gz` archive. Later entries summarize the corresponding
release notes; their detailed validation scope and limitations remain authoritative.
