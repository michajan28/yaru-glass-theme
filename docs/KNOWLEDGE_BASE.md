# Yaru Glass Theme — Project Knowledge Base

This document summarizes the project as represented by its source, scripts, profiles,
and user manual. It is intended as a starting point for future maintenance.

## Project at a glance

- **Purpose:** provide light and dark glass-inspired desktop themes for Ubuntu
  GNOME, while retaining Ubuntu's Yaru foundation, icons, and logo.
- **Release in this tree:** `2.3.0` (`VERSION`), distributed through public GitHub
  Releases with a versioned archive and SHA-256 companion.
- **Tested targets:** Ubuntu 24.04 LTS / GNOME Shell 46 and Ubuntu 26.04 LTS /
  GNOME Shell 50, Wayland. Other Ubuntu/GNOME versions are not guaranteed.
- **Dual-stack validation:** Ubuntu 26.04 / GNOME 50 alongside 24.04.
  A persistent Ubuntu 26.04.1 Wayland VM runs Shell/Mutter 50.1, Nautilus 50.2.2,
  GTK 4.22.4, libadwaita 1.9.1 and Yaru 26.04.5.1. Automated GTK/WebKit tests,
  theme installation/upgrade, a clean reboot, headless St notification geometry,
  controlled live desktop checks and isolated lifecycle acceptance have run there.
  Broader hardware/background coverage remains separate. See
  [2.0.0 release evidence and limits](RELEASE-2.0.0.md).
  Finish Ubuntu's first-run wizard before installing/testing a custom theme: its
  appearance page can reset GTK theme preferences on each unfinished login.
- **Theme variants:** `Yaru-Glass` and `Yaru-Glass-dark`.
- **Main visual elements:** translucent, rounded GNOME Shell surfaces; blue accents;
  glass-style traffic-light window controls; Inter font; and a transparent dock.
- **Theme preview:** [integrated login and desktop simulation](../demo/index.html)
  for login/lock/logout flows, light/dark surfaces, relative transparency, and contrast wallpapers.
- **Nature of the project:** this is not a self-contained GTK theme. At build time it
  takes Yaru theme resources from the host system, adds local overrides, and uses
  GNOME extensions and user settings for the complete desktop experience.

## Source of truth and file map

| Path | Responsibility |
|---|---|
| `scripts/build.py` | Theme generator, shared appearance transaction (`apply_locked`) and canonical light/dark colors (`VARIANTS`). |
| `src/yaru_glass/theme_settings.py` | Validated settings, presets, shared alpha helpers and atomic writes. |
| `src/yaru_glass/managed_glass.py` | Reversible project-owned Frost/Crystal pipelines for Blur my Shell. |
| `src/yaru_glass/wallpapers.py` | Validated native light/dark wallpapers and conditional original-value restoration. |
| `src/yaru_glass/diagnostics.py` | Private JSONL events, operation correlation, bounded rotation, CLI and sanitized reports (2.2.3). |
| `src/yaru_glass/diagnostics_ui.py` | Asynchronous Settings diagnostic viewer and explicit local export (2.2.3). |
| `bin/yaru-glass-logs` | Installed diagnostic CLI and safe lifecycle event bridge. |
| `bin/yaru-glass-settings` | GTK 4/libadwaita app with responsive page navigation, readable before/after preset and reset confirmations, debounced 0–50% transparency slider, and paired wallpaper pickers. |
| `src/theme/gnome-shell/glass.css.in` | GNOME Shell CSS overrides. `${...}` values are substituted from `scripts/build.py`. |
| `src/theme/gtk-3.0/glass.css` | GTK 3 window-control, menu, focus, sidebar, button, and tooltip overrides. |
| `src/theme/gtk-4.0/libadwaita.css` | GTK 4/libadwaita accent, window-control, corner, menu, sidebar, and tooltip overrides. |
| `scripts/install.sh` | Interactive user-level installation, backup, extension setup, appearance configuration, and service setup. |
| `scripts/uninstall.sh` | Restores pre-install settings; optional extension removal and purge. |
| `assets/profiles/*.ini` | dconf settings applied to supported GNOME Shell extensions. |
| `bin/yaru-glass-sync` | Keeps the GTK theme, color scheme, Shell theme and GTK 4 override link aligned. |
| `bin/bms-dock-pipeline.py` | Adds/updates the named Blur my Shell dock pipeline without replacing existing pipelines. |
| `bin/install-extensions.py` | Downloads extension releases matching the running GNOME Shell version and records extensions it installed. |
| `bin/enable-extension.py` | Marks extensions enabled when immediate activation is unavailable, such as before a Wayland relogin. |
| `scripts/export-profile.py` | Exports current extension settings to profiles while excluding selected machine-specific or runtime-managed keys. |
| `scripts/make-package.sh` | Exports profiles, attempts to render the manual, then builds a versioned tarball and SHA-256 file. |
| `scripts/render-manual.py` | Renders `docs/MANUAL.md` into `docs/MANUAL.html`; requires the Python `markdown` module. |
| `docs/MANUAL.md` / `docs/MANUAL.html` | User-facing installation, usage, customization, troubleshooting, and licensing documentation. |
| `assets/fonts/Inter/` | Bundled Inter variable font files and their SIL Open Font License. |
| `docs/screenshots/` | Light app, dark app, dock, and menu bar screenshots used by the manual. |
| `demo/index.html` | Offline browser simulation that opens on a fictional account login, routes to the desktop on sign-in, and returns to a lock screen or login after Lock or Log Out. The isolated views are `desktop-view.html` and `login-view.html`; bundled assets live under `demo/demo-assets/`. |
| `demo/demo-assets/desktop/` | Desktop styles, behavior, and bundled Yaru icons; symbolic icons are inlined because WebKit blocks `file://` mask images. |
| `demo/demo-assets/lockscreen/` | Lock-screen wallpapers, avatars, and icons. |

`assets/profiles/` is the installer-applied baseline, not the theme's CSS source. The package
builder refreshes profiles from the machine where it runs, so those settings can vary
between packages.

`dist/releases/` contains only the current release archive and checksum; historical
release notes remain in `docs/` and `CHANGELOG.md`. Generated theme snapshots are not
source inputs and are not required for packaging. `scripts/build.py` writes generated
themes to `~/.local/share/themes`, using the host's `/usr/share/themes` and
`/usr/share/gnome-shell/theme` resources.

## Build and theme structure

`scripts/build.py` generates both variants into `~/.local/share/themes`:

1. It reads the corresponding GTK base (`Yaru-blue` or `Yaru-blue-dark`).
   For Shell CSS/assets it prefers those names on 24.04, falling back to `Yaru`
   or `Yaru-dark` on 26.04, where colored Shell directories are no longer shipped.
2. It writes the theme `index.theme` and GTK 3/GTK 4 imports and overrides.
3. GTK resource bundles and GTK 2 theme directories are symlinked to the system Yaru
   theme; generated shell assets are copied and their accent colors are rewritten.
4. The generated shell stylesheet appends the values from `VARIANTS` to
   `src/theme/gnome-shell/glass.css.in`.
5. If one generated Shell theme is active, the builder toggles the User Themes setting
   so GNOME Shell reloads its stylesheet.

The source color model is intentionally centralized: edit `VARIANTS` for variant
colors and `src/theme/gnome-shell/glass.css.in` for Shell styling. The light accent is
`#007AFF`; the dark accent is `#0A84FF`. Yaru's base accent `#0073E5` and modern
`-st-accent-color` tokens are replaced when generating Shell CSS/SVG resources;
`-st-accent-fg-color` becomes white. This preserves the fixed project palette
without changing the user's system accent setting. `VARIANTS` stores original surface alpha values.
`theme_settings.shell_colors` scales an explicit allowlist by `1 - transparency / 100`.
Text-bearing panel/menu/dialog/notification fills use a protective tint:
`floor + (1 - floor) * base_alpha * factor * style_factor`, where floor is 0.58 light /
0.70 dark and style factor is 1 Frost / 0.55 Crystal. This intentionally strengthens
readability compared with the earlier straight-alpha theme. Text uses opaque foreground
colors; GTK app styling and solid accents are unchanged.

The settings app remembers the level in `~/.config/yaru-glass/settings.json`
and groups controls in five Gtk.Stack pages: Shell, Applications, Wallpapers,
Diagnostics and Updates. The latter two are lazily created inline Gtk.Box pages,
not popup windows. Their confirmation/export dialogs remain explicitly invoked.
The diagnostic viewer formats sanitized records as newest-first summaries and
detail blocks; JSON storage/export and the CLI protocol remain unchanged.
A keyboard-accessible StackSwitcher stays above independent scrollers. Page changes
never save/rebuild. Error handlers select the relevant page; Files status distinguishes
saved/restart-required from confirmed restart and does not claim live CSS on startup.
The settings path respects `XDG_CONFIG_HOME`. The app debounces appearance changes and
serializes asynchronous worker operations.
`scripts/build.py --shell-only --transparency N --glass-mode frost|crystal --save-setting`
updates installed shell CSS and managed effects, reloads an active project theme,
then saves settings while preserving new solid/boost fields. It leaves another selected theme alone.
Full builds read the saved level; all builds share a file lock. Invalid configuration,
build, reload, or save errors are surfaced rather than silently replaced with defaults.
The HTML preview is independent and does not change the saved desktop preference.
Its native semantic HTML controls are custom-styled, including switches, select,
buttons and sliders; keyboard focus and reduced-motion preferences are retained.
See [1.2.1 validation](RELEASE-1.2.1.md) for completed consent-based desktop
acceptance. Nautilus may return a nonzero quit status after exiting; Settings
checks session D-Bus ownership before treating that case as a failed restart,
logs the diagnostic, and never force-kills Files.

Version 1.2.0 adds `solid` and `readability_boost` booleans to Shell settings, both
false when absent (1.1.0 appearance unchanged). Solid forces `PRIMARY_SURFACES`
alpha to 1, including the dock; other tokens/overlays are unchanged. Boost halves
remaining backdrop contribution on those fills and enabled app/Files roots.
`app_opacity`, `boosted_opacity` and Files `opacity` are shared with UI/readouts.

Coordinated presets are pure partial snapshots in `preset_values`; `preset_name`
derives a match excluding boost. Solid is Frost/0/solid with app/Files off/25;
Balanced Frost enables both apps at 25; Clear Crystal enables both at 50.
Preview/cancel has no side effects. Each preset preserves boost and wallpapers.

`scripts/build.py --shell-only --appearance-patch '{"app":{"enabled":true}}'` is the UI's
worker API. It validates allowed sections/fields, reads latest values under the
single `build.lock`, merges only edited fields, generates affected CSS and reloads
Shell if required, then saves affected preference files. App-only edits never
rebuild/reload Shell. Handled failures restore prior bytes/existence and managed
effects/ownership backup, reporting rollback errors. It is not crash-atomic.
Incomplete patches cannot replace corrupt configuration; an explicit complete
section reset can, with a visible warning. No new preference file is introduced.

All app/Files controls now use the worker, not UI-thread saves. During a worker
operation or confirmed Files restart conflicting UI operations are disabled.
Section resets and per-slot wallpaper restoration require confirmation. Files
restart success is session-local, invalidated by style/boost/Files changes or GTK
theme changes; cold-start live CSS is unknown. No polling or automatic restart.

Old transparency-only JSON migrates to Frost. `src/yaru_glass/managed_glass.py` preserves unrelated
pipelines and snapshots only owned keys in `glass-backup.json` before first takeover.
Starting with 2.2.0, `background_blur` defaults to true and manages
dynamic panel, popup and dock backgrounds (`static-blur=false`). Solid suppresses
effective blur without rewriting the saved preference; presets omit this field.
Ordinary rounded transparency remains available with the blur switch off. The earlier
GNOME 46 blur path lacked corner-radius support and no Blur typelib was installed;
that limitation must not be generalized to newer Blur my Shell rendering paths.
The installed Blur my Shell v77 supports live backdrop capture and rounded masking,
including dedicated calendar corners; user-provided desktop captures show rounded,
blurred calendar popups. The 2.2.0 checks did not prove consumer acceptance:
the serializer rewrote four-number colors as `av`, making v77 reject the entire
library and use defaults. Version 2.2.1 uses `(dddd)` for numeric colors (both
tuples and legacy lists), retaining `av` for effects. `pipeline_variant` is shared
by application and restoration. `pipelines_match` compares serialized variants,
not only unpacked dictionaries, so an unchanged affected library is still repaired.
Format repair alone restarts BMS via `DisableExtension`/`EnableExtension`, waiting
for states 2/1 and attempting reenable even if disabling fails. A quick blur-key
toggle was not reliable on GNOME 46; `ReloadExtension` is not implemented on 50.
The restart clears Default pipelines cached by all three components. Failures
surface through the existing rollback path; ordinary valid applies do not restart.
`tests/check_bms_pipelines.js` imports the installed upstream parser, settings and
manager. Its default mode requires the memory backend; `--live frost|crystal`
is read-only. Real guest actor probes and preferences checks on both stacks are
recorded in [2.2.1 release evidence](RELEASE-2.2.1.md).
Frost/Crystal now differ in tint, lighting and blur strength. Existing named
pipelines remain for compatibility/restoration and are active only when effective
blur is enabled. Layered St gradients keep the tint alpha; popup/dock inset
reflections add no border geometry. GTK lighting is confined to the opted-in root.
Old ownership backups are extended with newly managed popup corner keys before
the first write, without resnapshotting previously owned values.
Capability checks use the running extension's reported directory, supporting legacy
Gaussian effects (flat or nested) and newer Dual Kawase effects. Newer pipelines
omit manual corner effects because the extension handles surface rounding itself.
The exact policy in `src/yaru_glass/extension_compatibility.py` limits
active BMS to v77. Detection of older layouts is retained in the helper
but is not a promise of support outside the policy. Schema checks use the running
extension's directory rather than a shadowing system installation. Dynamic blur
requires `render/dynamic_surface.js` and `render/rounded_pipeline.js`.
Curated BMS profiles do not replace the pipeline library or select legacy IDs;
the installer filters pipeline imports and managed Glass creates only owned IDs.
Application blur is disabled in the supplied profile. The retained
`bin/bms-dock-pipeline.py` compatibility command reuses the shared lock, saved
blur/Solid preferences, exact policy and reversible Shell effects rather than
adding an unowned Gaussian/refraction dock pipeline.
Notification source icons, titles and timestamps use the opaque foreground in both
banners and the calendar list. Calendar and Quick Settings retain 28px CSS corners.
Borderless notifications must reset padding in both `:ltr` and `:rtl`: system Yaru
sets negative directional message padding, which overflows unsigned St sizing when
the border is removed. `tests/check_notification_layout.js` checks actual St/Clutter
preferred and allocated widths in an isolated headless Mutter context, not just CSS
syntax. `test_transparency.py` runs it on a private D-Bus session when GJS and the
GNOME Shell St/Mutter typelibs are installed; otherwise it is skipped.
Notification banners use a compact 1px-offset/3px-blur shadow inside their 6px
margins, rather than a 10px blur that can be clipped by the banner container.
Banners must not use a Layered `background-gradient`. On GNOME 46 and 50, Shell
then draws the banner's outer shadow as a square gray halo around the rounded
banner, independent of Blur my Shell. The OSD uses the same combination without
this defect, so do not generalize the rule without compositor evidence.
The same native check enforces shadow bounds, the absent gradient, LTR/RTL and
interactive states, while retaining the inset keyboard focus ring.
The sync service restores managed effects when leaving the theme, and reapplies on
activation. Uninstall restores effects before the original installation backup.
Build errors attempt CSS/effect rollback and report incomplete restoration.

### Local diagnostics (2.2.3)

`diagnostics.py` is the shared flat-import module. Schema 1 records contain UTC
timestamp, level, component/action/phase, project version, PID, 32-hex operation ID,
allowlisted fields and optional safe error category/stack locations. Never pass
messages, arbitrary stdout, argv, environment or paths into new fields.
`operation`/`traced` log and rethrow the original error; meaningful changes use
INFO, no-op detail uses opt-in DEBUG. Sync deduplicates repeated failures and
records recovery. Settings propagates the operation ID through a worker environment
variable; the worker's stdout remains exactly its existing JSON response.

Storage is private XDG state: `events.jsonl` plus four 2 MiB rotations. A dedicated
flock (not the appearance lock) bounds contention to 200ms; failures warn once per
process on stderr and do not alter action results. Read snapshots are bounded and
parsed outside the lock. Unknown/malformed records are omitted with a count;
report export revalidates every field. Files use no-follow/nonblocking opens,
owned regular-file checks, 0600 and single-link enforcement. The directory is 0700.
Purge removes only named log/preference files, retaining the coordination inode
because unlinking it would let concurrent writers lock different files.

`diagnostics_ui.py` performs reads, preference writes and report generation off
the GTK thread. A failed verbose write restores the last confirmed switch state;
export requires confirmation and a new local file. Reports query only known
extension UUIDs and public versions/states; no arbitrary journal access.
The page owns its native export chooser until response or page closure. A local
variable alone lets PyGObject destroy the chooser during asynchronous folder
loading, cancelling the destination selection.
`tests/test_diagnostics.py` covers storage, privacy, malformed inputs, concurrency,
rotation, CLI/report/export and failure behavior. Adjacent appearance/UI/sync and
lifecycle tests cover stdout, rollback, correlation, responsiveness, retention and
safe purge. Keep all test XDG state private; do not install on the host as a test.

Wallpapers live in GNOME's `picture-uri` / `picture-uri-dark`, not project settings.
An opt-in Settings-window-only transparency control uses `app-appearance.json`,
separate from Shell preferences, but sharing the build lock on worker saves. A window-class-scoped GTK
provider changes only background/titlebar fills, retaining opaque boxed controls.
The separate 0-50 slider defaults to 25 with the feature disabled; 0 is opaque.
Tint follows the last successfully applied Shell glass style and Adw.StyleManager's
dark state. Save happens before appearance changes, with a visible error/Retry on
failure. No global GTK CSS changes or other-app effects. Purge removes this file.
GTK render tests sample actual texture alpha for both schemes/styles and endpoints,
including full opacity on controls and no whole-window opacity changes.
With boost off, Settings-window minimum tint is 70% in light / 80% in dark at maximum Crystal
transparency; explanatory dim labels, subtitles and titlebar labels use full
foreground/opacity. Computed foreground checks enforce 4.5:1 against sampled
black/white backdrops at the minimum tint. This differs from Shell tint floors.

`src/yaru_glass/files_appearance.py` adds separately opt-in Nautilus transparency, stored in
`files-appearance.json`. All generated selectors start with `window.nautilus-window`
(confirmed in Nautilus 46.4 and exercised on the real Nautilus 50.2.2 window). The layout uses
AdwOverlaySplitView's `.sidebar-pane`/`.content-pane`, ToolbarView top bars and
`placessidebar`. One root alpha tint prevents stacked translucency; sidebar/header
backgrounds are cleared, while content `.view` keeps `@view_bg_color`.
The two generated `libadwaita.css` files receive a marked managed block. Files
controls save under the shared build lock with CSS rollback on failure. Full builds,
Shell mode changes and theme activation regenerate this block. The user GTK4 link
is still owned by the sync service; no changes to unrelated apps' stylesheets.
Running GTK processes may require a full restart for CSS updates/deactivation.
Closing Files windows is not sufficient if its background application service is
still running: compare process startup with CSS modification time. Quit Files
only with user approval and no active transfers, then reopen through normal D-Bus
activation. At Files transparency 10%, Crystal root tint is 94% opaque.
The UI never quits Files automatically. A Restart Files action requires confirmation
(Cancel by default, warning about transfers), sends normal `nautilus --quit`,
watches `org.gnome.Nautilus` disappear with a 10-second timeout, then D-Bus activates
Home. It never force-kills or restores old windows/tabs; failures are visible.
The Settings window cannot close mid-restart. Presets save one complete snapshot:
Solid off/0, Subtle on/10, Balanced on/25, Clear on/50. Reset is off/25.
An actual-opacity label uses the same helper as CSS generation, reflects only saved
values and last successfully applied glass mode, not live Files reload state.
Disable + restart restores the
normal appearance. Purge removes the preference. Render tests use actual libadwaita
split panes to verify sidebar/header alpha, solid content, both schemes/styles,
slider endpoints and isolation of a window without the Nautilus class.

GNOME 50 guest compositor acceptance on 2026-10-26 covered 14 actual Files cases:
both light/dark variants, Frost/Crystal at maximum transparency with boost off/on,
level 0 in both modes, and the independent Files opt-in disabled. Each case used
approved normal Files quit/reopen and black/white desktop captures. Sidebar/header
effective opacity measured 69.8% Crystal / 78.8% Frost without boost and
85.1% / 89.4% with boost, within 0.3 percentage points of the shared formulas.
Level 0 and disabled cases measured 100%; sampled file-content pixels remained
unchanged between backdrops in all cases. Text, icons and controls remained
visually intact. Original preference and generated stylesheet bytes were restored
and verified afterwards; no new CSS, Shell JavaScript or sync errors were logged.
This is software-rendered VM evidence on flat backdrops, not hardware-renderer or
arbitrary-wallpaper accessibility certification.

Additional GNOME 50 desktop acceptance covered eight configurations: light/dark
with Frost, Crystal, boosted Crystal and Solid Shell backgrounds. Forty-eight
captures were inspected across actual Quick Settings, calendar, notification
banners and the Settings Shell/Applications/Wallpapers pages. Expected menu
controls and notification text were also checked through accessibility; managed
effect keys matched the selected mode in each case. The existing app/Files opt-ins
were kept independent rather than implicitly following Solid Shell backgrounds.
Actual Settings interactions verified that preset Cancel left preference/CSS
bytes unchanged, while Apply saved the coordinated Solid snapshot without
changing boost/wallpapers or restarting Files. The explicit Files restart dialog
preserved the process on Cancel and replaced it only after confirmation, with a
truthful success status. Original guest appearance bytes were restored afterwards.
No new CSS, JavaScript or sync error was observed. This remains a controlled,
software-rendered desktop sample, not certification of arbitrary backgrounds,
every submenu, hardware rendering or Desktop ISO installation.

`wallpaper-backup.json` tracks pre-edit user values and this app's last value per slot.
Restore/uninstall only restores a slot still equal to the app's last edit, keeping
new external choices. Images remain at their original local paths.

The date menu uses the popup's single glass background. Calendar cells, headings,
week numbers, and embedded date-menu cards remain transparent, including on hover.
Today's date retains a blue marker; keyboard focus and the selected date use an
outline instead of another background fill.

The GTK 4 override file contains shared rules for both variants. It is linked into
`~/.config/gtk-4.0/gtk.css` by the sync service only while a Yaru Glass theme is active.
The service targets the light variant's `libadwaita.css`, whose rules are designed to
work in both color schemes.

## Installation and runtime behavior

Run `./scripts/install.sh` as the logged-in desktop user, not with `sudo`. It expects a GNOME
session and checks for the system Yaru-blue GTK and Shell resources. It may use `sudo
apt-get` to install missing packages; extension downloads require internet access.

The installer:

1. Copies the package to `~/.local/share/yaru-glass`.
2. Saves the original selected appearance settings, extension settings, and GTK 4 CSS
   link on first install. Re-running installation does not overwrite this backup.
3. Installs Inter to `~/.local/share/fonts/Inter`.
4. Installs/enables the requested GNOME extensions unless `--no-extensions` is used.
   Ubuntu Dock and AppIndicators are enabled if available. Newly installed extensions
   may require logging out and back in.
5. Runs `scripts/build.py`, sets Inter fonts, and keeps the Yaru icon theme.
6. Applies the `assets/profiles/*.ini` settings and adds the dock blur pipeline unless
   `--theme-only` is used.
7. Installs/enables the per-user `yaru-glass-sync.service` and selects the theme that
   matches the current GNOME color scheme.

Installer options:

- `--no-apt`: do not install system packages.
- `--no-extensions`: skip extension downloads and enabling.
- `--theme-only`: skip the extension profile and dock customization while still
  installing themes, font, and sync service.
- `-y` / `--yes`: skip the confirmation prompt.

The sync process watches `org.gnome.desktop.interface`'s `gtk-theme` and
`color-scheme` settings. While either project theme is selected, it aligns those two
settings, the User Themes Shell theme and the GTK 4 stylesheet link.
Selecting another GTK theme removes its own Shell-theme selection and GTK 4
link. The service starts with the graphical user session and can be inspected with
`systemctl --user status yaru-glass-sync`.
It also subscribes to `ExtensionStateChanged` and queues a debounced refresh when
any policy-governed integration becomes active. This recovers login-time
activation failures without polling or reactivating a project theme after the user
has chosen another GTK theme. Errors remain visible in the service log.
One-shot `--once` execution exits nonzero after a managed appearance error;
the installer reports incomplete activation rather than a success message.
Extension enabling updates the enabled/disabled lists once per batch, then waits
for Shell state. Do not combine a list update with a second per-extension enable
request: GNOME 46 can attempt duplicate activation while loading asynchronously.

`Automatic Theme Switcher` is configured to select the light/dark pair automatically.
The user can also use GNOME's Dark Style control. Search uses GNOME's built-in
overview. Search Light is no longer installed, profiled or synchronized on either
stack; the installer no longer changes keyboard-layout shortcuts. Upgrades remove
only the stale installed profile file, retaining existing extension settings,
original backups and installer ownership records for uninstall compatibility.

## Uninstall and data behavior

### App updater (2.3.0)

`bin/yaru-glass-update` shares bounded release/asset validation in
`src/yaru_glass/updates.py` with the asynchronous native `updates_ui.py` window.
The public latest stable release must have exact versioned archive/checksum
assets. Same-release checksums are integrity checks, not independent signatures.
The CLI uses no gh/git, login, package manager or external Python dependency.
The archive allowlist includes the top-level contributor/security documents.
Older development validators without those entries reject released archives;
use the verified local-archive bootstrap from 2.3.1 rather than the old updater.
Packaging regressions must verify and extract the actual script-generated
archive through `updates.py`, in addition to checking its tar listing.

`update_transaction.py` is deliberately not a wrapper around `install.sh`,
which reapplies fonts/profiles and activation. It preserves saved preferences,
customized profiles, original backups and extension ownership while staging
complete app/theme trees. `build.py --stage-themes NEW_DIRECTORY` reads saved
preferences and system Yaru resources but never activates or reloads the desktop.
Keep this path free of managed-effect application and preference writes.

`operation_lock.py` coordinates shared appearance/sync activity with exclusive
update/install/uninstall activity. An inherited validated descriptor allows
installer children to participate without deadlocking. Lock order is lifecycle
then build; the updater also holds build.lock during staging/commit to exclude
old bootstrap-era appearance workers. A pending journal blocks normal mutations.
Sync defers while busy rather than changing the desktop during replacement.

The private canonical same-filesystem workspace is
`~/.local/share/yaru-glass-update/`. Orchestration runs from its retained
`runner/bin/yaru-glass-update`; the runner can execute `recover` when the installed
package is unavailable. Journal each replacement intent before renaming, preserve
complete old trees, and retain evidence when restoration fails. Commit follows
reload and original-service restoration; directory replacement is recoverable,
not multi-directory atomic. Do not enable a previously disabled sync service,
restart Files, import profiles, or select an inactive project theme.

Bootstrap requires a verified local release archive/checksum and the same
transaction against an owned canonical installation. Existing Settings windows
must be closed first. Tests cover a synthetic 2.2.4 layout followed by an
installed-CLI update with mocked downloads, real staged Yaru generation, private
HOME/XDG/D-Bus and stubbed systemd. `test_updates.py` additionally injects archive,
network, concurrency, generation, replacement/reload/service and recovery errors.
This is not certification of arbitrary historical layouts or both live desktops.

For 2.3.0, Settings and Files render fixtures use
`tests/gtk_rendering.py:snapshot_widget` to request/wait for GTK after-paint before
sampling the paintable cache. Fixed sleeps alone could sample the previous
opaque/translucent frame. Keep the existing alpha/content assertions; do not
raise tolerances to hide capture timing. GNOME 50/VM revalidation is deferred for
this release; retain Logo Menu's GNOME 50 exclusion until actual interaction
validation is available.

- `~/.local/share/yaru-glass/scripts/uninstall.sh` restores the original backed-up settings.
- `--remove-extensions` also removes extensions recorded as installed by this installer;
  already-present extensions are not recorded as installer-added.
- `--purge` removes generated themes, the installed Inter font, service/helper links,
  and the installed package directory. Before deleting that directory, it copies the
  backup to `~/.local/share/yaru-glass-backup-<timestamp>`.
- Standard system packages installed through apt are deliberately retained.
- If the backup is absent, the uninstaller can only switch GTK back to Yaru and reset
  the User Themes selection; it cannot reconstruct the prior settings.

`tests/test_lifecycle.py` executes actual installation, theme-only upgrade, normal
uninstall and purge/removal in a copied payload with a private HOME/XDG and session
D-Bus. User-systemd, extension uninstall and font-cache commands are fixture stubs;
no live desktop service is started, packages installed or extensions downloaded.
Real system Yaru generation and dconf restoration run on each stack. The checks
cover original backup bytes, mixed independent preferences, legacy Search Light
records, managed pipeline removal, original GTK CSS, conditional wallpaper
restoration, extension ownership boundaries and retained purge backups.
Run it independently with `/usr/bin/python3 -m unittest discover -s tests -p test_lifecycle.py -v`.
The 2.2.0 full suite passes 168 tests on each Ubuntu stack, with no skips.
See the [release evidence](RELEASE-2.2.0.md) for environments and validation limits.

A separate isolated Ubuntu 24.04 check verified the preserved 1.2.1 archive
checksum, installed its original flat-layout payload, upgraded with the current
installer, and restored through the current uninstaller. All three preference
files and original backup files stayed byte-identical, legacy extension ownership
survived, and the dark scheme was respected. This also used theme-only/no-download
installation and stubbed user-systemd; it does not certify live extension upgrade
or a live desktop uninstall/purge. Historical archives were not modified.

## Dependencies and constraints

- Host Yaru resources: `yaru-theme-gtk` and `yaru-theme-gnome-shell`; the installer also
  lists Ubuntu icon/sound themes and Ubuntu dock/appindicator packages.
- Runtime tools include GNOME Shell, Python 3 with PyGObject/GLib bindings, dconf,
  `systemd --user`, fontconfig, curl, and unzip.
- The installer downloads extensions from extensions.gnome.org for the detected
  Shell version, checking both the release map and archive metadata.
  Missing or unsupported releases are reported as warnings; incompatible archives
  and schema compilation failures stop installation explicitly.
- Logo Menu remains part of the 24.04 integration, but is omitted from extension
  install/enabling and profile application on Shell 50. Release 45 and current
  upstream code still call `super.vfunc_event` where StWidget has no implementation.
  Do not patch third-party files silently or enable it merely because its metadata
  lists 50. Recheck the released upstream fix and actual runtime at every release;
  existing independently installed copies and original backups are preserved.
- GTK themes stored under the home directory may not be visible to sandboxed Snap
  applications; the manual identifies Firefox/Thunderbird Snap apps as an example.
- The manual recommends rebuilding after system Yaru updates because the generated
  theme reuses host Yaru resources.
- Run focused standard-library tests with `python3 -m unittest discover -s tests`.
  Visual behavior still needs validation on the target Ubuntu/GNOME version.
- Guest UI tests need a logged-in, unlocked and unblanked display; a locked VM can
  retain stale GTK snapshots and stop resize/frame updates. Use a sufficiently
  large guest display and record software-rendering limits. GTK snapshot fixtures
  retain their `Gtk.WidgetPaintable` through frame updates.

### Guest WebKit test launch

The Python WebKit harness needs permission to create its sandbox's user
namespaces. A test launched inside VS Code may inherit that permission from its
AppArmor profile, while identical Python/WebKit packages launched over SSH do not.
A bubblewrap UID-map denial is a harness launch failure, not evidence that the
HTML demo is incompatible with the guest's GNOME version.

For an explicitly approved disposable Ubuntu guest, a dedicated AppArmor profile
can grant this permission only when selected for the test command. The validated
guest uses `/etc/apparmor.d/yaru-glass-webkit-tests`:

```text
abi <abi/4.0>,
include <tunables/global>

profile yaru-glass-webkit-tests flags=(unconfined) {
  userns,
}
```

Load that profile using `sudo apparmor_parser -r` with the exact profile path.
This follows Ubuntu's named application-profile mechanism; it is not a confined
application policy. Do not attach it to all Python processes, disable AppArmor,
turn off the global user-namespace restriction, or disable WebKit's sandbox.
Do not install test policies on the user's host as part of theme installation.

Use the guest's real session bus/runtime paths and Wayland display. Ensure the
session is unlocked and the display can accommodate the largest tested viewport
(currently 1366px wide). Run from the guest checkout:

```sh
gnome-session-inhibit --inhibit idle --reason "Yaru Glass guest UI regression validation" \
  aa-exec -p yaru-glass-webkit-tests -- \
  /usr/bin/python3 -m unittest discover -s tests -p 'test_*.py' -q
```

Idle inhibition lasts only for the command; it does not change lock preferences.
It does not unlock a session that was already locked. Confirm the guest is
unlocked before starting: a locked GNOME 46 session reproduced stale
1100x650 allocations and viewport-resize timeouts despite idle inhibition.

Version 2.2.2 separately fixes the real intermittent mobile overflow: WebKit on
GNOME 46 could resolve the notification banner's animated `translateX(-50%)` to
zero during early layout. Captured geometry at 390px showed a banner from x=195
to x=569 and desktop `scrollWidth=569`. The banner now uses opposing insets and
automatic inline margins; animation changes only vertical translation/opacity.
Do not hide notifications, disable all animations, add retry-until-pass logic or
relax the mobile overflow assertion to mask this defect. The new regression
pauses the actual animation at four positions at 1100/320/390/680px and asserts
bounds and centering. Reduced motion uses a separate check; its test-owned inline
copy of the real stylesheet avoids forbidden `file:` cross-origin CSSOM access.
Ten independent complete 29-test demo runs passed per stack with sandboxing and
`kernel.apparmor_restrict_unprivileged_userns=1` retained. See
[2.2.2 release evidence](RELEASE-2.2.2.md).

## Maintenance workflow

1. Read `MANUAL.md` and this knowledge base before changing installation/runtime
   behavior.
2. Make CSS changes in the relevant `src/` file; change light/dark tokens in
   `scripts/build.py`'s `VARIANTS`.
3. On a supported Ubuntu GNOME system with the Yaru dependencies installed, run
   `python3 scripts/build.py` (or the installed copy at `~/.local/share/yaru-glass/scripts/build.py`).
4. Check both variants, GTK 3 and GTK 4 applications, Shell menus/Quick Settings, and
   the dock. Restart affected applications; Shell extension changes may need a relogin.
   Open `../demo/index.html` in a browser to preview the simulated login and glass
   desktop; it is a browser approximation, not the GNOME Shell runtime.
5. Keep Blur my Shell and dock corner radii aligned with the CSS dock radius (24 px in
   the current dock pipeline/profile).
6. Update `MANUAL.md` when user-facing behavior changes. Regenerate `MANUAL.html` with
   `scripts/render-manual.py` when the Markdown renderer is available.
7. Before making a release, update `VERSION` and run `scripts/make-package.sh [output-dir]`.
   This updates `assets/profiles/*.ini` from the current machine, may update `MANUAL.html`, and
   writes a `.tar.gz` plus `.sha256` file to the output directory.

## Licensing and attribution

The project builds on Ubuntu community Yaru files already present on the user's system.
GTK resources are linked; generated Shell themes contain copied and modified Yaru
stylesheets and assets. The manual documents component-specific licensing and
redistribution obligations, including GPL and CC BY-SA terms where applicable.
Inter is bundled under SIL Open Font License 1.1. Extensions remain under their
authors' licenses. This is an unofficial derivative, not endorsed by the Yaru
project or Canonical.
