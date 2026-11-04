---
name: yaru-release
description: 'Use when preparing a Yaru Glass release, packaging a tarball, updating VERSION or changelog entries, verifying archive checksums, or validating install/upgrade/uninstall changes without modifying the live desktop.'
---

# Yaru Glass Release Workflow

## Inputs And Boundaries

Read the root [agent guidance](../../../AGENTS.md),
[changelog](../../../CHANGELOG.md), and [VERSION](../../../VERSION).
The [maintenance guide](../../../docs/KNOWLEDGE_BASE.md) explains runtime ownership
and rollback; release notes under `docs/` record version-specific evidence.

Confirm whether the request is validation only, release preparation, or actual
packaging. Do not infer permission for live desktop changes, profile capture,
version bumps, Git commits, publishing, or overwriting an existing archive.

## Procedure

1. Inspect current edits and the requested version. Keep unrelated changes intact.
   Source paths use the current repository layout; preserved historical archives
   retain their original layouts. Never repackage an old archive in place.
2. Summarize evidence-backed changes from Unreleased. Move them to a new version
   section only when a version/release is approved. Update `VERSION`, README
   version references, and release notes together; do not invent publication dates
   or claim checks that were not executed.
3. Run focused tests for touched modules, then shared release gates from the root:

   Recheck Logo Menu's released GNOME 50 event handling on every release.
   The installer currently omits it on Shell 50; restore integration only after
   the upstream release passes actual menu/Activities interaction checks without
   `StWidget` virtual-function errors. Metadata declaring support is insufficient.

   ```sh
   /usr/bin/python3 -m unittest discover -s tests -p 'test_*.py' -q
   bash -n scripts/install.sh scripts/uninstall.sh scripts/make-package.sh
   ```

   Record skipped GUI tests and missing dependencies. The packaging test in
   [test_repository_layout.py](../../../tests/test_repository_layout.py) copies
   the payload, stubs `dconf`, isolates HOME/XDG, checks both output modes and
   checksums, and imports the extracted build through safe `--help` execution.
   [test_lifecycle.py](../../../tests/test_lifecycle.py) exercises real lifecycle
   scripts against copied payloads and a private HOME/XDG/session bus, with
   user-systemd and extension removal stubbed. It checks ownership/restoration,
   not real extension downloads, live service startup or desktop uninstall.
4. Check documentation paths and manual consistency. Render with
   `/usr/bin/python3 scripts/render-manual.py` only when `python3-markdown` is
   available. Do not silently install system packages or describe an unchanged
   pre-rendered HTML file as freshly generated.
5. Before actual packaging, inspect
   [make-package.sh](../../../scripts/make-package.sh). It exports current
   extension settings into tracked `assets/profiles/`, optionally renders the
   manual, and writes `dist/releases/` by default. Get approval before capturing
   the live profiles; otherwise use a temporary copied tree with a stub `dconf`
   as the existing packaging test does. Never stub commands in the user's real PATH.
6. Choose a new approved version or an empty explicit output directory if that
   version's archive already exists. For an approved real package, run
   `./scripts/make-package.sh /approved/output/directory` from the project root.
   Review profile/manual diffs; do not revert pre-existing user edits.
7. Verify `sha256sum -c yaru-glass-theme-VERSION.tar.gz.sha256` from the output
   directory, substituting the actual version. Inspect `tar -tzf` output: expected
   root/version, changelog, sources, scripts, runtime commands, docs, profiles,
   licensed fonts, and tests must be present. Git metadata, `dist/`, caches,
   backups, and runtime state must be absent. Preserve executable permissions.
8. Do not execute an extracted installer/uninstaller or start the live sync service
   as a smoke test. Lifecycle validation requires a copied fixture, private HOME
   and D-Bus, and stubbed user-systemd calls. Any real desktop test, screenshot,
   or confirmed Files restart needs explicit user permission.
9. Report the version, artifact location, checksum result, checks actually run,
   skips, profile changes, and remaining platform/visual limitations. Leave Git
   staging, commits, remote setup, and publishing to separately authorized work.
