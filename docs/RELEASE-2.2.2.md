# Yaru Glass 2.2.2

## Scope and cause

Local demo reliability hotfix for Ubuntu 24.04 / GNOME 46 and Ubuntu 26.04 /
GNOME 50. Native themes, pipeline management, extension policy, settings and
installation behavior are unchanged from 2.2.1.

The GNOME 46 mobile-overflow failures were not harmless test noise. During the
notification entry animation WebKit could resolve the percentage-based horizontal
translation to zero. A captured 390px viewport had its banner's left edge at 195px,
right edge at 569px and desktop scroll width of 569px. Notification timing made
an unrelated Files or Settings action appear to cause the failure.

The banner now centers through opposing insets and automatic margins. Its
animation changes vertical position and opacity only, preserving slide/fade,
responsive width and reduced motion. No global overflow clipping, suppressed
notifications, disabled animations or weakened mobile assertions were added.

Separately, a locked guest session reproduced the 1100x650 stale-allocation
resize timeouts. Idle inhibition does not unlock an already locked desktop.
Tests were run on an unlocked 1920x1080 guest session with temporary inhibition;
the user's lock preferences and WebKit sandbox were not disabled.

## Executed validation

- A new regression samples the real notification animation at 0/10/50/99% of
  its duration, at 1100/320/390/680px viewport widths, checking exact bounds,
  centering and desktop overflow. All 16 cases fail against the old CSS on
  GNOME 46; the fix passes. A second test verifies reduced-motion centering.
- Ten independent full demo processes pass on **each** stack: 29 tests per run,
  **290 tests on GNOME 46 and 290 on GNOME 50**, without skips or retries.
  This includes integrated login, file/HTTP navigation and the unchanged original
  mobile overflow and floating-window tests.
- GNOME 46 retains its explicitly selected guest-only AppArmor test profile;
  WebKit sandboxing and the global user-namespace restriction remain enabled.
- Complete source suite: **178 tests pass on each stack**, without skips,
  including native UI, actual pipeline consumers and isolated packaging/lifecycle.
- Installer, uninstaller and packaging scripts pass Bash syntax validation.
  The published Logo Menu Shell 50 release remains tag 75631, already inspected
  for its incompatible event forwarding; the existing omission is unchanged.

Test-development failures are not counted as passes: an early reduced-motion
test tried to inspect an external `file:` stylesheet through CSSOM and received
the expected cross-origin denial. Its final version uses a test-owned inline
copy of the real CSS. Repetition uses independent processes, matching normal
suite execution rather than accumulating GTK/WebKit objects across repeated
class lifecycles in one process.

## Limits and release boundary

Guests use software rendering. EGL/software-renderer and known libadwaita accent
warnings do not establish hardware rendering support. These runs do not certify
all browsers, fractional scales or arbitrary backgrounds. Tests still require
an unlocked, unblanked display with sufficient space for their requested viewport.

The package uses curated repository profiles, without capturing live desktop
settings: `dist/releases/yaru-glass-theme-2.2.2.tar.gz` and its SHA256 file.
Historical archives are preserved; no Git commit, push or publication
is included. This release does not install itself on the host. Structured logging
is a separate feature to plan after this hotfix, before native lockscreen work.
