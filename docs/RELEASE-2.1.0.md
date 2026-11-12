# Yaru Glass 2.1.0

> Historical record: naming in this document has been normalized to Yaru Glass.
> Command examples do not identify preserved historical archives, which have not
> been renamed or rebuilt. Use the README for current installation instructions.

Local visual-coherence release for the Ubuntu 24.04 / GNOME Shell 46 and
Ubuntu 26.04 / GNOME Shell 50 dual-stack baseline established in 2.0.0.
The package is prepared locally; this is not a remote publication or a claim of
new platform validation.

## Changes

- Reset and repair confirmations now present named sections and readable
  before/after values instead of JSON. Invalid stored values are identified as
  unavailable rather than represented by an unsaved fallback. Cancel remains
  the default response; only listed fields change, and Files is never restarted
  automatically.
- Preset confirmations in native Settings and the browser demo use matching
  section names and readable state/value labels.
- Settings switches to compact page navigation for narrow windows. Content
  scrolls vertically without forcing horizontal overflow.
- The demo offers white, dark and busy sample backdrops to make visual
  comparison easier. These samples are illustrative and do not change desktop
  settings or certify compositor contrast.
- Existing Shell and GTK appearance rules, transparency defaults, independent
  opt-ins and protective tint were retained; the review found no verified
  appearance defect that justified changing those rules.

## Validation

- Native Settings checks passed on this Ubuntu 24.04 /
  GNOME Shell 46 Wayland host.
- Existing automated contrast coverage measured at least **6.47:1** for its
  sampled normal text/surface combinations. This is a scoped test result, not a
  blanket WCAG claim or validation of arbitrary backgrounds.
- Native Settings tests exercised small-window page sizing, vertical scrolling
  and compact navigation.
- `scripts/render-manual.py` could not regenerate `MANUAL.html` because
  `python3-markdown` is unavailable. The Markdown and corresponding HTML manual
  edits were kept aligned manually.
- No 100–200% desktop scaling matrix, large-text matrix or fresh GNOME 50
  compositor acceptance was performed for this package. The 2.0.0 dual-stack
  evidence remains historical; this release adds no new claim for GNOME 50.
- Logo Menu remains omitted from GNOME 50 installation/profile application.
  This host cannot repeat actual GNOME 50 menu/Activities interaction checks;
  the known-safe omission is unchanged.

## Package and installation

The local archive is `dist/releases/yaru-glass-theme-2.1.0.tar.gz`, with a
matching SHA-256 file. It retains the repository-supplied extension profiles;
the packaging process used an isolated copy and a private `dconf` stub rather
than exporting live host settings. Older archives are unchanged.

To update an existing installation with dependencies and extensions already
present while preserving its extension profile/settings:

```sh
sha256sum -c yaru-glass-theme-2.1.0.tar.gz.sha256
tar xzf yaru-glass-theme-2.1.0.tar.gz
cd yaru-glass-theme-2.1.0
./scripts/install.sh --no-apt --no-extensions --theme-only --yes
```

The install replaces the user-level theme payload, builds and activates the
current light/dark themes, refreshes the sync service, and installs the Settings
launcher and font. It does not download/enable extensions or apply extension
profiles. Close and reopen Settings after upgrading. Files CSS changes still
require a separate, explicitly confirmed Files restart after transfers finish.

The release is local; Git staging, commits and remote publication are separate
actions.
