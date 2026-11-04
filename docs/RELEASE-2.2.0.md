# Yaru Glass 2.2.0

## Status

**Correction:** subsequent use exposed an invalid color encoding that makes
Blur my Shell reject the complete pipeline library. Saved keys and captures below
did not establish that the six Yaru pipelines were accepted or actually active.
The old tests incorrectly expected colors as variant arrays. Use
[2.2.1](RELEASE-2.2.1.md), which fixes the format and verifies the real parser,
preferences and running panel/popup/dock actors. The 2.2.0 archive is unchanged.

Local release for Ubuntu 24.04 / GNOME 46 and Ubuntu 26.04 / GNOME 50.
The complete 168-test suite, including all 27 demo tests, passes on both stacks.
The earlier GNOME 46 guest launch failure was a test-environment issue, not a
GNOME compatibility defect.

This release implements Layered Frost/Crystal, independently controlled dynamic
Shell blur, exact extension-release enforcement, dominant-icon-color dock dashes,
and the integrated demo fixes. See the [changelog](../CHANGELOG.md#220) and the
[exact extension matrix](MANUAL.md#220-extension-policy).
Custom native lockscreen work remains scheduled for 2.3.0, not this release.

## Executed validation

Desktop validation and captures below were explicitly authorized inside disposable
guests. The original GNOME 50 VM was preserved. A subsequent host clean reinstall
was separately requested; it is not substituted for isolated acceptance.

| Environment | Evidence |
|---|---|
| Ubuntu 24.04 / Shell 46.0 host, system Python | Full suite: 168 tests passed; lifecycle shell syntax passed |
| Ubuntu 26.04.1 / Shell 50.1 / Mutter 50.1 guest | Complete 168-test native/browser/lifecycle suite passed without skips, including all 27 demo tests |
| Ubuntu 24.04.5 / Shell 46.0 / Mutter 46.2 guest | Complete 168-test native/browser/lifecycle suite passed without skips, including all 27 demo tests |
| Both guests | 18 material combinations per stack: light/dark, Frost/Crystal, levels 0/25/50, Solid, readability boost, and blur off/on |
| Both guests | Generated light/dark styles passed native St notification width, allocation, padding and foreground checks in LTR/RTL and all tested interaction states; Solid opacity assertions passed |
| Both guests | Actual saved settings and effective panel/popup/dock blur values matched each material case |
| Both guests | Reviewed rounded Quick Settings/calendar captures over a controlled high-contrast background; Solid was opaque and blur-off retained sharp underlying detail |
| GNOME 50 | Quick Settings followed a maximized application backdrop, rather than continuing to show wallpaper-only blur |
| Both guests | Disabled integrations reactivated through the corrected single-batch enable path, reporting all exact releases active |
| Both guests | Real preserved 2.1.1 archive upgrade, preference/backup byte preservation, old managed-record migration, native dock settings, uninstall, and purge passed |
| Both guests | Real light/dark notification, logout-dialog cancellation, switcher and volume OSD interactions; opt-in Settings/Files surfaces exercised with opaque file content |
| Both guests | Native dock dashes reviewed with multiple Files windows and a different-colored Settings icon |
| GNOME 46 | Logo Menu opened/closed and Activities displayed normally in light/dark; GNOME 50 retains standard Activities |

GNOME 46 used GTK 4.14.5, libadwaita 1.5.0 and Nautilus 46.4.
GNOME 50 used GTK 4.22.4, libadwaita 1.9.1 and Nautilus 50.2.2.
The extension matrix includes the observed Ubuntu 26.04 extension bundle
`50.26.04.8ubuntu`; an older proposed package pin was corrected before acceptance.
The preserved 2.1.1 archive checksum still passes.

## Corrected guest test setup

The GNOME 46 host and guest have identical GNOME Shell, AppArmor, bubblewrap and
WebKit package versions. The host test process inherits VS Code's named AppArmor
profile, which permits user namespaces. Plain Python launched over SSH did not;
AppArmor denied bubblewrap's UID-map setup before the demo could load.

The disposable guest now has a dedicated, explicitly selected
`yaru-glass-webkit-tests` profile granting `userns`, following Ubuntu's named
application-profile mechanism. It does not attach to Python globally.
WebKit sandboxing remains enabled; the kernel's
`apparmor_restrict_unprivileged_userns` remains `1`. This profile is test
infrastructure, not an installed theme dependency or a change to the host.

Guest UI runs also need an unlocked, unblanked session and a display large enough
for the requested 1366px viewport. Transient GNOME session idle inhibition keeps
frames updating during tests. A remapping workaround explored while diagnosing
stale frames was removed: the final passing runs use the original demo tests and
unchanged viewport, alpha, layout and interaction assertions.
See the [guest validation procedure](KNOWLEDGE_BASE.md#guest-webkit-test-launch).

## Validation limits

- Repeated same-session install/uninstall/extension cycles on GNOME 46 eventually
  timed out Shell D-Bus calls. Restarting the guest desktop session recovered
  activation; the complete upgrade/lifecycle check passed from a clean 2.1.1
  login. A hot-session recovery guarantee is not claimed.
- Native interactions were checked at 1920x1080 and 100% scale, with a busy
  high-contrast background; earlier popup checks also used the stock photo.
  Automated small-layout and alpha/contrast checks passed. Arbitrary wallpapers,
  fractional scaling, every application/icon and all animation frames are not
  certified. Settings values and native geometry checks alone do not prove pixels.
- Logo Menu 41 was checked on GNOME 46. It remains omitted on GNOME 50 because
  the audited upstream event handler is incompatible; no third-party patch was
  installed to force it on.
- The guests use software rendering. No hardware performance or arbitrary-
  background accessibility certification follows from these observations.
- Guest logs included unavailable stock wallpaper-preview assets and the known
  libadwaita warning for the custom `Yaru-Glass` accent name. EGL/software-renderer
  warnings were also observed; they are not described as passing hardware tests.

## Release boundary

The local archive is `dist/releases/yaru-glass-theme-2.2.0.tar.gz`, with its
adjacent SHA256 file. It uses curated repository profiles, not live dconf capture.
The historical 2.1.1 archive is preserved. Validate the checksum before extracting
or installing. Final acceptance includes the full suite from the extracted
payload on both guest stacks. No Git commit, push or remote publication is included.
