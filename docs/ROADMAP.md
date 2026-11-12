# Yaru Glass development roadmap

Readable glass. Consistent controls. Safe upgrades.

**Current delivery:** 2.4.0 — independent native Lock Screen companion<br />
**Status:** Independent extension implemented and owner-tested; app/theme updates stay separate<br />
**Target stacks:** Ubuntu 24.04 / GNOME 46 and Ubuntu 26.04 / GNOME 50, Wayland  
**Limits:** VM coverage is not certification of every GPU, backdrop or monitor layout

This roadmap covers the light `Yaru-Glass` and dark
`Yaru-Glass-dark` variants, the native Settings app, installer, updater and
independent Lock Screen extension. The browser preview is not a validation gate.
Future version numbers are planning labels; scope must be approved before
implementation. Releases are quality-gated, not tied to calendar deadlines.

## 1. Product direction

Build a coherent glass-inspired Ubuntu desktop without sacrificing Yaru identity,
text readability or the user's control of their system.

- **Readable first:** transparency must not wash out text, icons or focus.
- **Real layered glass:** illuminated tints and rounded dynamic Shell blur, with
  an independent off switch. No wallpaper-only or rectangular blur artifacts;
  native app integrations remain tint-only.
- **Ubuntu underneath:** keep Ubuntu icons, branding and native application behavior.
- **Explicit opt-in:** Settings-app and Files transparency remain independent;
  unrelated apps must not acquire experimental transparency.
- **Safe by default:** preserve wallpapers, profiles and original backups.
  Never restart Files automatically or force-kill it.
- **Honest status:** saved settings, reload requests and confirmed restarts are
  distinct from verified pixels or a running application's actual CSS.

## 2. Where we are: 2.4.0

| Area | Delivered | Remaining boundary |
|---|---|---|
| Shell | Light/dark Frost and Crystal, relative transparency, true Solid fills, readability boost | Not certified for every backdrop, extension or display scale |
| Native Settings | Coordinated presets, previews, confirmed resets, async workers, Diagnostics and Updates | Reload requests are not proof of compositor output |
| Application integration | Independent Settings-app transparency; experimental Nautilus sidebar/header transparency | File content stays solid; arbitrary GTK/libadwaita apps are not supported integrations |
| Lock Screen | Independent GNOME 46/50 extension, own Preferences, wallpaper/clock/appearance options, responsive native notifications | Activation stays in Extensions; no Yaru Glass app page or GDM customization |
| Updating | Confirmed stable GitHub app/theme updates with checksums, staging, rollback and recovery | Theme updates do not install or update the companion extension |
| Validation | 220 native tests passed without skips on each GNOME 46/50 VM; real extension smoke and owner manual acceptance | Headless CI has explicit GUI skips; broader hardware/background coverage is not certified |
| Distribution | Theme archive/checksum and separate extension ZIP/checksum; curated profiles without desktop capture | Existing accounts install the extension ZIP explicitly; published status is shown on GitHub Releases |

See [2.4.0 validation and installation](RELEASE-2.4.0.md),
the [manual](MANUAL.md) and [maintenance knowledge base](KNOWLEDGE_BASE.md).

## 3. Release sequence

| Stage | Status | Outcome | Evidence / boundary |
|---|---|---|---|
| Maintenance | Continuous | Fix verified regressions without appearance drift | Reproducible issue on a supported configuration |
| 2.0.0: dual-stack compatibility | Implemented | Ubuntu 24.04 / GNOME 46 and Ubuntu 26.04 / GNOME 50 together | Historical controlled desktop and isolated lifecycle checks |
| 2.1.0: visual coherence | Implemented | Readable confirmations, controls and status | Scoped contrast and native UI checks; historical broader acceptance limits retained |
| 2.2.0: Layered glass and reliable integration | Implemented | Rounded live blur, exact extension policy, dock dashes and curated packaging | Pipeline encoding required the subsequent 2.2.1 correction |
| 2.2.1 / 2.2.2: maintenance | Implemented | Repair rejected/cached pipelines; notification animation improvement | Separate release notes |
| 2.2.3: private diagnostics | Implemented | Bounded local logs, sanitized report export, Settings viewer and CLI | Privacy/concurrency/rollback/lifecycle checks; no automatic uploads |
| 2.2.4: maintenance | Implemented | Remove the square notification halo; labeled Diagnostics header button | Native St regression and controlled compositor captures |
| 2.3.0: app updater | Delivered | Check and install stable GitHub releases; inline Diagnostics/Updates, readable logs and app-grid feedback | Verified staging, recovery and bootstrap; GNOME 46 checks; GNOME 50/VM revalidation deferred |
| 2.3.1: report export | Delivered | Retained native save chooser; documented older-updater bootstrap | Save/cancel/close ownership and package/updater checks |
| 2.4.0: independent lock screen | Implemented | Native companion with its own Preferences and ZIP | 220 native tests pass per GNOME stack; owner confirmed manual experience; required CI gates publication |
| Personal appearance profiles | Later, unnumbered | Safely save, preview and restore appearance choices | Approve format and reuse validated transactions |

Maintenance fixes need not wait for the next feature milestone.
Diagnostics ships in 2.2.3; 2.2.4 makes it discoverable and fixes the notification halo.
2.3.0 delivers app updates; 2.4.0 adds the independent Lock Screen companion.
Logs are enabled by
default for key actions/warnings/errors, with optional verbose mode; private
10 MiB rotation and sanitized local reports do not collect full preferences,
personal paths or journal dumps. Ordinary uninstall retains logs; purge removes
known logs/preferences but keeps the coordination inode and user-owned reports.
Historical evidence and unverified configurations remain in each release's notes.
Check [GitHub Releases](https://github.com/michajan28/yaru-glass-theme/releases)
for published artifacts; implementation status does not imply publication.

## 4. Historical milestone: 2.0.0 — dual-stack compatibility

The work packages below describe the completed milestone, not upcoming work.

**Goal:** support Ubuntu 24.04 / GNOME 46 and Ubuntu 26.04 / GNOME 50 in one
release, without dropping the existing stack or changing saved appearance.
Wayland is the 26.04 session target. Record the actual Nautilus, GTK, libadwaita,
Mutter and Yaru versions in the test environments rather than inferring them.

### Delivered work packages

1. **Provision the test environment.** Create an isolated persistent Ubuntu 26.04
   desktop VM, verify the official image checksum/signature and record its
   package versions. Keep the host desktop unchanged. A cloud image with Ubuntu
   Desktop installed is a compatibility environment, not Desktop ISO installer
   validation. Containers and CSS string tests cannot replace compositor checks.
2. **Audit before adapting.** Inspect actual Yaru resource paths and palettes,
   Shell selectors, Nautilus widgets, libadwaita behavior, extension releases and
   schemas on both stacks. Verify existing fixes before proposing duplicate work.
3. **Implement evidence-based compatibility.** Reuse common code and selectors
   where they work on both stacks; gate only confirmed differences. Diagnose
   unavailable extensions and integrations explicitly. Do not promise that every
   third-party extension has a Shell 50 release or force unsupported versions.
   Logo Menu stays on 24.04 but is omitted on 26.04 while its released event
   handler fails; recheck upstream and live behavior before every project release.
4. **Preserve lifecycle contracts.** Keep installed command/theme names,
   preferences, independent opt-ins, backup paths, partial updates and rollback.
   Files restarts remain separate and confirmed; no new app integrations or
   unrelated UI modernization are included.
5. **Validate both stacks.** Run targeted and full applicable tests, isolated
   install/upgrade/uninstall checks and a consent-based desktop acceptance matrix.
   Check light/dark, Frost/Crystal/Solid, readability boost, panel, Quick Settings,
   calendar, notifications, dock, Settings and Files. Record skips, software
   rendering limits and unavailable integrations.
6. **Prepare the release only after validation.** Update support documentation
   and release notes with observed results. Bump `VERSION` to 2.0.0 and package
   only at the approved release step; do not overwrite historical archives.

### Exit criteria

- Both named stacks pass regression and applicable real-rendering checks.
- Upgrade from 1.2.1 on 24.04 preserves preferences and original backups.
- Extension availability and platform/integration limits are documented truthfully.
- A persistent 26.04 environment is available for ongoing regression checks.
- If a required integration fails, record it and resolve the scope explicitly;
  do not advertise full support based only on successful theme generation.

## 5. Historical milestone: 2.1.0 — visual coherence and readability

The work packages below retain the original scope and its validation limits.

**Goal:** make controls, dialogs and status feel like one deliberate theme.
Do not expand transparency to additional applications in this milestone.

### Work packages

1. **Native confirmation polish.** Replace raw JSON reset summaries with readable
   before/after rows, clear section names and explicit consequences. Reuse the
   existing confirmation and worker paths; Cancel remains the safe default.
2. **Readability and state audit.** Review disabled slider marks, subtitles,
   inactive window controls, selections, errors and keyboard focus in both
   schemes. Keep value readouts readable without making disabled controls look
   interactive. Do not weaken the current protective tint to gain transparency.
3. **Surface consistency.** Review spacing, radii and focus treatment across
   supported Shell popups, native Settings, GTK overrides and demo controls.
   Preserve intentional differences between Shell, GTK and browser rendering.
4. **Responsive Settings.** Check default-size and small-screen scrolling, long
   labels, larger text and 100%/125%/150%/200% display scaling on available
   environments. Record untested combinations rather than claiming coverage.
5. **Demo parity.** Keep names, preset values, warnings and disabled states aligned
   with native Settings. Improve sample backdrop choices for evaluating contrast;
   demo actions must remain local and must not change desktop settings.

### Exit criteria

- Normal text on supported, sampled surfaces meets at least **4.5:1** contrast;
  large text and meaningful non-text control/focus indicators target **3:1**.
  Document disabled-control exceptions separately; do not claim blanket WCAG compliance.
- No notification width overflow, clipped labels, rectangular corner bleed or
  doubled popup rims in the recorded light/dark acceptance matrix.
- Keyboard navigation reaches every action, focus remains visible, and dialogs
  cancel without changes. Reduced motion continues to work in the demo.
- Existing preferences retain their appearance; any deliberate default or visual
  change is documented and reviewed rather than silently applied.

**Main validated surfaces:** native Settings, GTK overrides and Shell CSS.

The local 2.1.0 package passed native checks on Ubuntu 24.04 / GNOME 46.
The measured contrast result covers only existing automated sample cases.
100–200% desktop scaling, broader large-text cases and fresh GNOME 50 compositor
acceptance remain unverified; see [2.1.0 release notes](RELEASE-2.1.0.md).

## 6. Historical milestone: 2.2.0 — Layered glass and reliable integration

The work packages describe the historical local release. Its saved pipeline
format was subsequently corrected in 2.2.1.

**Goal:** deliver more realistic Frost/Crystal lighting and rounded live Shell
background blur, with reliable integrations and a quality-gated local release.

### Work packages

1. **Deliver Layered Frost/Crystal.** Light/dark Shell surfaces, independent
   Settings/Files opt-ins and matching demo; preserve protective tints and solid content.
2. **Audit every used extension.** Select exact candidate releases per GNOME
   stack, enforce supported versions at install/enable/runtime boundaries, and
   preserve the GNOME 50 Logo Menu omission until real event-handler acceptance.
3. **Manage rounded dynamic blur.** Default on for Shell only, independent off
   switch, Solid suppression without preference loss, and reversible owned settings.
4. **Native dock indicators.** Ubuntu Dock DASHES in each icon's dominant color;
   preserve native window counts, demo parity and uninstall restoration.
5. **Validate both isolated desktops.** GNOME 46 and 50 compositor/extension
   checks, both schemes/styles, Solid, blur on/off, boost, white/dark/busy backdrops,
   rounded corners and moving windows. Containers or metadata are not substitutes.
6. **Exercise recovery and lifecycle.** Partial updates, corrupted preferences,
   failures/rollback, old ownership backups, upgrade, uninstall and purge.
7. **Prepare the local release.** Update manuals/roadmap, package supplied
   profiles using `--curated-profiles`, verify checksum, payload and extracted
   tests. No host changes, live profile capture, Git commit or publication.

### Exit criteria

- Packaging leaves source profiles, live preferences and wallpapers unchanged.
- Under the same recorded inputs/toolchain, two builds produce matching payloads;
  track archive hashes separately until metadata is normalized and verified.
- Release records identify host Yaru/resource versions and test environments,
  because generated themes depend on system resources.
- An extracted archive passes the release checks; upgrade preserves preferences
  and original backups; removal restores the documented original appearance.
- A diagnostic report excludes wallpaper paths, personal filenames and other
  private data by default; nothing is uploaded automatically.

**Dependency:** retain the accepted 2.1 visual baseline. Tooling must not become
a reason to rewrite the theme or add a large build framework.

## 7. Delivered: 2.3.0 — app updater

**Goal:** make upgrades convenient across machines and accounts, without resetting
each user's appearance or requiring a GitHub account.

- Manual **Check for updates** and confirmed **Install update** in Settings,
  backed by an equivalent CLI and public stable GitHub release assets.
- Verify SHA-256, validate archive paths and payload, stage the new app/themes,
  and recover failed or interrupted replacement.
- Preserve preferences, wallpapers, customized profiles, extension versions and
  ownership, original backups, and the previous sync-service state.
- Provide a verified-archive bootstrap for existing installations; subsequent
  updates use Settings or CLI. Updates are per account, not remote administration.
- No unattended updates, sudo, profile resets, automatic Files restarts or theme
  activation. Describe reload requests separately from verified visual output.
- Cover network failures, invalid assets, concurrency, rollback, bootstrap and a
  subsequent update in isolated fixtures on the supported stacks.

Tracking: [implementation issue #6](https://github.com/michajan28/yaru-glass-theme/issues/6).
See [release evidence and limits](RELEASE-2.3.0.md). Diagnostics and Updates are
inline pages after Wallpapers; local logs are formatted for reading while export
remains JSON. Rendering fixtures synchronize to GTK's painted frame. Validation
for this milestone is on GNOME 46; no GNOME 50/VM revalidation is claimed.

### Implemented: 2.4.0 — independent native lock screen

- UUID `lockscreen@yaru-glass`, independently versioned extension ZIP and local
  GSettings schema for GNOME 46/50.
- Own standard GNOME Preferences: customization switch, local wallpaper/preview,
  follow desktop, clock format/weight, appearance and confirmed reset.
- Preserve native account identity, authentication, notification grouping/privacy
  and responsive scrolling. Do not collect credentials or modify GDM.
- Fresh normal theme installation adds the companion without activation.
  `--no-extensions` and `--theme-only` skip it; compatible existing copies stay
  untouched. Existing accounts install the separate ZIP explicitly.
- Activation remains in Extensions/Extension Manager. Yaru Glass app integration
  was explicitly dropped; the theme updater is unchanged.
- GNOME 46/50 VM checks passed, and the owner confirmed the installed custom
  lock-screen experience. One bounded GNOME 50 disable/enable cycle also passed.

The earlier intermittent GNOME 50 uninstall/restoration freeze has no established
root cause and did not reproduce in the independent toggle check. Do not claim
a fix or resume speculative investigation without reproduction or a new decision.
See [2.4.0 release notes](RELEASE-2.4.0.md) and
[issue #10](https://github.com/michajan28/yaru-glass-theme/issues/10).

## 8. Later, unnumbered — personal appearance profiles

**Goal:** save and compare favorite appearances without losing independent controls.

### Work packages

- Save, rename and delete user appearance profiles beside the built-in presets.
- Preview complete before/after values before applying through the existing
  coordinated transaction. Preserve independent Shell, Settings-app and Files values.
- Validate imports with an explicit schema/version, reject unknown or invalid
  fields with a useful error, and make export portable.
- Offer a confirmed restore of the previous successful appearance. Label it as
  appearance history, not a promise of crash-safe whole-system rollback.

### Exit criteria

- Built-in presets remain available and unchanged; migration is backward compatible.
- Preview, import validation and Cancel never modify saved appearance.
- Apply either completes through the existing validated transaction or reports
  failure and rollback status; no partial success is hidden.
- Profiles exclude wallpapers, extension configuration and private paths by
  default. Files restarts remain separate and explicitly confirmed.

**Decision gate:** approve the profile format, storage and history limit before
implementation. Do not add a database or service unless a demonstrated need exists.

## 9. Not planned without a new decision

- Refraction/distortion shaders, automatic wallpaper sampling or automatic transparency changes.
- Global window opacity or transparent content in every native application.
- Replacing Ubuntu icons/branding or cloning another operating system pixel-for-pixel.
- Automatic Files restarts, forced termination, or restoring tabs without a
  supported and verified mechanism.
- Cloud sync, telemetry, automatic uploads or a permanent screen-control service.
- Guaranteed support for every GNOME extension, application or Ubuntu release.

## 10. Definition of done for every release

1. Approve the scope and user-visible behavior before implementation.
2. Keep defaults, migrations and unknown-field/error handling explicit; protect
   user changes and original backups.
3. Run targeted tests during development and the full applicable suite on the
   final extracted package. Skips and environment limits must be recorded.
4. Use real St/GTK checks for geometry, alpha and contrast where relevant.
   Inspect actual compositor output for desktop-facing visual changes.
5. Test light/dark, Solid/transparent, boost off/on, disabled/focus/error states
   and white/dark/busy backdrops for affected surfaces.
6. Obtain consent for desktop capture/input, appearance changes and restarts.
   Use test-only windows/data; restore original state and close helpers afterward.
7. Verify install/upgrade/removal behavior, executable modes, safe archive paths,
   version consistency and SHA256. Never overwrite earlier release archives.
8. Update the manual, demo, knowledge base and release notes where relevant.
   List observed results separately from automated checks and unverified claims.

The current native suite has 220 tests. Add coverage for behavior changes,
not arbitrary numeric targets; keep the browser preview outside validation.

## 11. Distribution and next decisions

The **2.4.0** release uses required signed-commit/PR checks and the tag-triggered
packaging workflow. Its distribution consists of the theme archive/checksum and
independent extension ZIP/checksum together, with separate installation steps.
Existing private v1 extension users do not need to reinstall just to update
the theme.

Prioritize reproducible native-product maintenance issues.
Personal appearance profiles remain the next unnumbered feature candidate;
their format, storage and behavior need owner approval before implementation.
No new version or schedule is assigned.

## 12. Maintaining this roadmap

`ROADMAP.md` is the content source of truth; `ROADMAP.html` is its matching,
offline-readable presentation. Update both in the same change. After each
release, move delivered work into release notes, record deferred decisions and
re-prioritize the next milestone. This document does not change the installed
theme, saved settings or release version.
