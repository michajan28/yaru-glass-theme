# Yaru Glass 2.2.2

## Scope and cause

Local demo reliability hotfix for Ubuntu 24.04 / GNOME 46 and Ubuntu 26.04 /
GNOME 50. Native themes, pipeline management, extension policy, settings and
installation behavior are unchanged from 2.2.1.

During the GNOME 46 notification entry animation the browser could resolve the percentage-based horizontal
translation to zero. A captured 390px viewport had its banner's left edge at 195px,
right edge at 569px and desktop scroll width of 569px. Notification timing made
an unrelated Files or Settings action appear to cause the failure.

The banner now centers through opposing insets and automatic margins. Its
animation changes vertical position and opacity only, preserving slide/fade,
responsive width and reduced motion. No global overflow clipping, suppressed
notifications or disabled animations were added.

## Executed validation

- Native UI, actual pipeline consumer and isolated packaging/lifecycle checks
  passed on both stacks.
- Installer, uninstaller and packaging scripts pass Bash syntax validation.
  The published Logo Menu Shell 50 release remains tag 75631, already inspected
  for its incompatible event forwarding; the existing omission is unchanged.

## Limits and release boundary

Guests use software rendering. EGL/software-renderer and known libadwaita accent
warnings do not establish hardware rendering support. These runs do not certify
all browsers, fractional scales or arbitrary backgrounds.

The package uses curated repository profiles, without capturing live desktop
settings: `dist/releases/yaru-glass-theme-2.2.2.tar.gz` and its SHA256 file.
Historical archives are preserved; no Git commit, push or publication
is included. This release does not install itself on the host. Structured logging
is a separate feature to plan after this hotfix, before native lockscreen work.
