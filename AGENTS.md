# Project Guidance

## Progress Reporting

- For every task and progress update, show the user a visible TODO checklist.
  Mark completed steps with `[x]` and remaining steps with `[ ]`; keep it current
  as work proceeds. Include the checklist in the final outcome as well.

## Start Here

- This is an Ubuntu GNOME theme/tooling project: Python, Bash, GTK CSS, and a
  framework-free HTML demo. There is no npm build; do not add `package.json`
  unless a requested feature introduces a real Node dependency or workflow.
- Read [README.md](README.md) for layout/commands and
  [docs/KNOWLEDGE_BASE.md](docs/KNOWLEDGE_BASE.md) for the relevant architecture.
- Check [CHANGELOG.md](CHANGELOG.md) and `VERSION` before release-related work.
  Historical release-note examples use the current branding, not necessarily
  the filenames or layouts of preserved archives. Never rewrite those archives.

## Code Boundaries

- Edit theme inputs in `src/theme/`, not generated themes in `dist/` or the home directory.
- Shared Python modules live in `src/yaru_glass/`; existing entrypoints explicitly
  add that directory to `sys.path`. Preserve flat imports unless a package migration
  is specifically requested. Keep repository-root paths separate from import paths.
- Runtime entrypoints stay in `bin/`; build/install/release tools stay in `scripts/`.
  Keep installed command names, backup/state paths, and existing preferences compatible.
- Reuse adjacent tests and helpers. Avoid new dependencies, unrelated cleanup,
  and generated-file churn. Preserve font licenses and binary assets.
- Changes to settings must preserve independent opt-ins, partial-field updates,
  rollback behavior, and truthful reload/restart status. Consult the knowledge base
  and existing transaction tests before altering these contracts.

## Verification

Use Ubuntu's system interpreter: GI bindings are system packages, and shell
`python3` may resolve to an unconfigured version-manager shim.

```sh
/usr/bin/python3 -m unittest discover -s tests -p 'test_*.py' -q
bash -n scripts/install.sh scripts/uninstall.sh scripts/make-package.sh
```

- Avoid repetitive testing. Batch coherent changes, then run the smallest relevant
  test set once. After a relevant failure, fix it and rerun only the affected
  tests; do not repeatedly rerun passing slices.
- For shared changes, run the full suite once after focused checks. Ask before
  repeating a full suite or investigating unrelated flaky/rendering failures;
  report those failures instead of chasing them automatically.
  Run a slice with `-p test_transparency.py`, `test_appearance.py`,
  `test_glass_wallpapers.py`, `test_settings_ui.py`, `test_files_appearance.py`,
  `test_demo.py`, or `test_repository_layout.py` as appropriate.
- Run `test_lifecycle.py` for isolated install/upgrade/uninstall/purge changes;
  it uses copied payloads, private HOME/XDG and D-Bus, with user-systemd stubbed.
- UI tests need a display and GI libraries; browser tests also need WebKit 6.
  Report skips and unavailable tools rather than claiming those paths passed.
- Packaging tests use temporary copies, a stub `dconf`, and isolated HOME/XDG paths.
  Preserve that isolation. Do not run tests against a real install for convenience.

## Desktop And Release Safety

- `scripts/build.py` writes live `~/.local/share/themes`; install/uninstall and
  sync commands change the desktop. These are not routine smoke tests. Obtain
  explicit permission for live changes, Files restarts, installs, or uninstalls.
- `scripts/make-package.sh` exports live dconf settings into tracked profiles and
  may overwrite a same-version archive. Do not invoke it casually; use isolated
  packaging tests for validation and the release skill for an approved release.
- Rendering `docs/MANUAL.html` needs `python3-markdown`. If unavailable, disclose
  that regeneration was not performed; keep any edited HTML aligned with Markdown.
- Never bypass desktop screenshot/input permissions. Automated GTK/demo checks
  do not prove the final compositor output or arbitrary-background accessibility.
- Keep unreleased changes in `CHANGELOG.md`; do not bump `VERSION`, rewrite old
  archives, stage/commit, configure Git identity, add remotes, or push unless asked.

For feature work and bug fixes, use
[the development skill](.github/skills/yaru-development/SKILL.md).
For release preparation, use
[the release skill](.github/skills/yaru-release/SKILL.md).
