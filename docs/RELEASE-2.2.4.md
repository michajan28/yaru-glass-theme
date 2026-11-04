# Yaru Glass 2.2.4

## Scope

Maintenance release for Ubuntu 24.04 / GNOME 46 and Ubuntu 26.04 / GNOME 50.
It fixes two defects reported against 2.2.3. No new settings, extensions or
preference formats are introduced.

### Notification halo

On bright backgrounds, 2.2.3 notification banners showed a square gray
rectangle around their rounded corners. The 2.2.3 shadow reduction did not
address the cause. Real compositor captures isolated it:

- turning off Blur my Shell popup blur left the halo unchanged;
- removing the banner shadow removed it, and so did removing the Layered
  `background-gradient` while keeping the shadow.

GNOME Shell draws the banner's outer shadow as a square when that banner also
has a gradient. Notification banners now use a flat tint with the compact
rounded shadow. Other popups keep the Layered gradient; the OSD, which uses the
same combination, was captured without the defect.

### Diagnostics discoverability

The 2.2.3 Settings header showed Diagnostics only as an unlabeled information
icon beside the window controls. It is now a labeled **Diagnostics** button at
the start of the header. The viewer itself is unchanged.

## Validation

- Compositor captures on the GNOME 46 and 50 test VMs, Frost at 35% with dynamic
  blur over a white/colored pattern: light on both stacks and dark on GNOME 46
  show rounded banners without the square halo.
- Settings was launched on the GNOME 46 VM and showed the labeled button.
- The native St/Mutter notification check now runs in the unit suite on a
  private D-Bus session. It rejects a banner gradient; reintroducing the 2.2.3
  gradient was confirmed to fail it. It skips without GNOME Shell typelibs.
- A Settings UI test checks the Diagnostics button is mapped, labeled and inside
  the header at default and narrow sizes, and that it opens the viewer.
- Full suite: **211 tests per GNOME 46/50 stack**, without skips. Bash syntax
  checks pass for installer, uninstaller and packaging scripts.
- Logo Menu's GNOME 50 release was rechecked: version 45, tag 75631, still calls
  `super.vfunc_event(event)`. It remains omitted on GNOME 50.

## Distribution and limits

The local package uses curated repository profiles without live dconf capture:
`dist/releases/yaru-glass-theme-2.2.4.tar.gz` and its SHA256 file. Earlier
archives are preserved. No Git staging, commit, push or publication.

Test VMs use software rendering. Captures do not certify every GPU driver,
display scale or background. No host screenshot is included.
