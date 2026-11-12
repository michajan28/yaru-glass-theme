---
name: yaru-development
description: 'Use when developing or debugging Yaru Glass features: Python settings and appearance transactions, GNOME Shell or GTK theme CSS, native Settings UI, Nautilus transparency, wallpapers, sync behavior, or the HTML demo. Includes source-to-test routing and isolated regression workflows; use yaru-release for packaging and version changes.'
---

# Yaru Glass Development

## Start With The Owning Code

Read [AGENTS.md](../../../AGENTS.md) for project conventions and desktop safety.
Use [the maintenance guide](../../../docs/KNOWLEDGE_BASE.md) only for the relevant
subsystem, rather than rereading the entire project for every task.

| Change | Start here | Focused test pattern |
|---|---|---|
| Settings validation, defaults, presets | [theme_settings.py](../../../src/yaru_glass/theme_settings.py) | `test_appearance.py`, `test_transparency.py` |
| Worker transactions, CSS generation, rollback | [build.py](../../../scripts/build.py) | `test_appearance.py`, `test_transparency.py` |
| Shell surfaces, colors, opacity | [Shell template](../../../src/theme/gnome-shell/glass.css.in), `scripts/build.py` | `test_transparency.py`, `test_glass_wallpapers.py` |
| GTK theme overrides | [GTK 3](../../../src/theme/gtk-3.0/glass.css), [GTK 4](../../../src/theme/gtk-4.0/libadwaita.css) | `test_transparency.py`, `test_files_appearance.py` |
| Native controls, async workers, Files restart | [settings launcher](../../../bin/yaru-glass-settings) | `test_settings_ui.py` |
| Nautilus-scoped generated CSS | [files_appearance.py](../../../src/yaru_glass/files_appearance.py) | `test_files_appearance.py`, `test_settings_ui.py` |
| Managed effects, wallpaper ownership, activation | [managed_glass.py](../../../src/yaru_glass/managed_glass.py), [wallpapers.py](../../../src/yaru_glass/wallpapers.py), [sync launcher](../../../bin/yaru-glass-sync) | `test_glass_wallpapers.py` |
| Layout, imports, installation payload | [maintenance scripts](../../../scripts/), [layout tests](../../../tests/test_repository_layout.py) | `test_repository_layout.py` |

## Implement And Verify

1. Reproduce the requested behavior with the nearest existing test or a small
   isolated fixture. State the suspected cause and the check that could disprove
   it. Inspect the actual branch/caller before changing code; do not infer behavior
   solely from a symbol name or an old release note.
2. Choose the owning layer from the table. For UI requests, follow the launcher
   into the worker or shared model if that is where the behavior is decided.
   Add a regression case to the adjacent existing test file where practical.
3. Make the smallest implementation change, then immediately rerun the selected
   test slice from the repository root. For example:

   ```sh
   /usr/bin/python3 -m unittest discover -s tests -p test_appearance.py -v
   ```

   Substitute one test pattern from the table; run multiple patterns separately.
   Tests should not depend on another test file first importing `build` or adding
   a search path. Reproduce import failures with the affected slice alone.
4. On failure, distinguish incorrect behavior from unavailable display/GI
   dependencies. Repair the touched behavior and rerun the same check before
   widening scope. Preserve existing fixture isolation and report actual skips.
5. Run the full suite when changing shared models, CSS generation, worker behavior,
   or cross-component contracts:

   ```sh
   /usr/bin/python3 -m unittest discover -s tests -p 'test_*.py' -q
   ```

   For shell changes also run `bash -n` on the touched scripts. Documentation-only
   work needs link/frontmatter checks, not a live rebuild or a redundant UI run.

## Subsystem Checks

### Python And Native UI

- Keep settings validation and opacity formulas in shared helpers rather than
  duplicating them in controls or readouts. Test legacy defaults, invalid inputs,
  and preservation of fields the user did not edit.
- For worker changes, cover partial merges, write/generation failures, restoration
  of original bytes or absent files, and visible rollback errors. Use existing
  mocks for dconf, effects, reloads, and subprocesses instead of the real desktop.
- Keep slow work off the GTK UI thread. Exercise success, failure, retry, and
  conflicting-operation states in the existing UI fixtures. A saved preference
  or successful subprocess request is not proof of live Shell/Files CSS reload.
- Wallpaper and managed-effect restoration must respect ownership and preserve
  unrelated user changes; use temporary configuration files for those tests.

### Theme CSS And Preview

- Edit source templates, not generated themes. Check both light/dark variants and
  Frost/Crystal/Solid behavior where relevant; level 0 and Solid are not synonyms.
- Validate shared appearance behavior with native GTK render tests.
  Keep file content/controls opaque and
  unrelated windows unstyled when adjusting scoped app transparency.
- Shell notification sizing has directional St/Clutter behavior that CSS string
  assertions cannot prove. For notification geometry changes, inspect
  [check_notification_layout.js](../../../tests/check_notification_layout.js)
  and its isolated headless Mutter requirements in the maintenance guide.
  This is a GJS/GNOME test, not a Node/npm test; disclose if it cannot be run.
- The HTML demo is independent of desktop preferences. Preserve semantic controls,
  keyboard focus, confirmation/cancel behavior, reduced motion, narrow layouts,
  and parity with the shared appearance model without adding a framework by default.
  Keep the browser preview outside automated validation and release gates.

## Close Out

Update user-facing documentation and the Unreleased changelog for behavior changes.
Report the change, exact checks run, skips, and remaining live-visual limitations.
Do not run live builds, sync, installs, Files restarts, or profile capture as an
extra confidence check. Use the release skill only when release work is requested.
