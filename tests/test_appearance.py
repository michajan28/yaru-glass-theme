import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/yaru_glass"))
sys.path.insert(0, str(ROOT / "scripts"))
import build
import diagnostics
import files_appearance as files
import theme_settings as settings


class AppearanceModelTests(unittest.TestCase):
    def test_migration_roundtrip_and_field_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"transparency": 15, "glass_mode": "crystal"}')
            migrated = settings.load_settings(path)
            self.assertFalse(migrated["solid"])
            self.assertFalse(migrated["readability_boost"])
            self.assertTrue(migrated["background_blur"])
            migrated.update(solid=True, readability_boost=True)
            settings.save_settings(migrated, path)
            settings.save_transparency(35, path)
            self.assertEqual(settings.load_settings(path), {**migrated, "transparency": 35})
            for key in ("solid", "readability_boost", "background_blur"):
                for invalid in (None, 1, "false"):
                    with self.subTest(key=key, value=invalid), self.assertRaises(ValueError):
                        settings.validate_settings({**migrated, key: invalid})

    def test_presets_are_derived_and_do_not_set_boost(self):
        for name in ("Solid", "Balanced Frost", "Clear Crystal"):
            value = settings.preset_values(name)
            self.assertNotIn("readability_boost", value["shell"])
            self.assertEqual(settings.preset_name(value), name)
            value["shell"]["readability_boost"] = True
            self.assertEqual(settings.preset_name(value), name)
            value["app"]["transparency"] = 13
            self.assertEqual(settings.preset_name(value), "Custom")
        with self.assertRaises(ValueError):
            settings.preset_values("unknown")

    def test_blur_preference_is_independent_of_presets_and_solid(self):
        for name in ("Solid", "Balanced Frost", "Clear Crystal"):
            patch_ = settings.preset_values(name)
            self.assertNotIn("background_blur", patch_["shell"])
            saved = settings.validate_settings({**patch_["shell"], "background_blur": False})
            self.assertFalse(saved["background_blur"])

    def test_layered_tokens_keep_surface_alpha_in_light_and_dark(self):
        for variant in build.VARIANTS:
            for mode in ("frost", "crystal"):
                for solid in (False, True):
                    colors = settings.shell_colors(variant["shell"], 50, mode, solid, True)
                    for key in settings.PRIMARY_SURFACES:
                        self.assertEqual(colors[key + "_top"].rsplit(",", 1)[1],
                                         colors[key].rsplit(",", 1)[1])
                    self.assertIn("12px", settings.gtk_material(mode, variant["dark"]))

    def test_solid_primary_surfaces_and_boost_are_monotonic(self):
        for variant in build.VARIANTS:
            for mode in ("frost", "crystal"):
                for level in (0, 25, 50):
                    normal = settings.shell_colors(variant["shell"], level, mode)
                    boosted = settings.shell_colors(variant["shell"], level, mode, readability_boost=True)
                    solid = settings.shell_colors(variant["shell"], level, mode, solid=True)
                    both = settings.shell_colors(variant["shell"], level, mode, True, True)
                    self.assertEqual(solid, both)
                    for token in normal:
                        if token.removesuffix("_top") in settings.PRIMARY_SURFACES:
                            alpha = lambda color: float(color.rsplit(",", 1)[1].rstrip(")"))
                            self.assertEqual(alpha(solid[token]), 1)
                            self.assertGreaterEqual(alpha(boosted[token]), alpha(normal[token]))
                        else:
                            self.assertEqual(normal[token], boosted[token])
                    for enabled in (False, True):
                        value = {"enabled": enabled, "transparency": level}
                        app = settings.app_opacity(value, mode, variant["dark"])
                        boosted_app = settings.app_opacity(value, mode, variant["dark"], True)
                        self.assertGreaterEqual(boosted_app, app)
                        self.assertGreaterEqual(files.opacity(value, mode, True), files.opacity(value, mode))
                        if not enabled:
                            self.assertEqual(boosted_app, 1)
                            self.assertEqual(files.opacity(value, mode, True), 1)


class AppearanceTransactionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.config = self.root / "config"
        self.config.mkdir()
        lock_directory = self.root / "updater"
        lock_directory.mkdir()
        self.themes = self.root / "themes"
        self.paths = [self.themes / variant["name"] / child for variant in build.VARIANTS
                      for child in ("gnome-shell/gnome-shell.css", "gtk-4.0/libadwaita.css")]
        for path in self.paths:
            path.parent.mkdir(parents=True)
            path.write_text("/* previous CSS */")
        self.shell_path = self.config / "settings.json"
        settings.save_settings({"transparency": 15, "glass_mode": "crystal",
                                "readability_boost": True}, self.shell_path)
        for patcher in (
            patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / "state")}),
            patch.object(build.operation_lock, "directory", return_value=lock_directory),
            patch.object(build, "CONFIG_DIR", self.config),
            patch.object(build, "THEMES_DIR", self.themes),
            patch.object(build, "load_settings", side_effect=lambda: settings.load_settings(self.shell_path)),
            patch.object(build, "project_theme_active", return_value=False),
            patch.object(build, "reload_shell_theme"),
            patch.object(build, "build_shell", side_effect=self.write_shell),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_shell(self, variant, output, *args, **kwargs):
        (output / "gnome-shell/gnome-shell.css").write_text("/* new CSS */")

    def snapshot(self):
        return {p: p.read_bytes() if p.exists() else None for p in
                self.paths + [self.config / name for name in
                              ("settings.json", "app-appearance.json", "files-appearance.json")]}

    def test_preset_saves_all_sections_and_preserves_boost(self):
        result = build.apply_locked(settings.preset_values("Clear Crystal"), True, True)
        self.assertTrue(result["shell"]["readability_boost"])
        self.assertEqual(settings.load_settings(self.shell_path), result["shell"])
        self.assertEqual(settings.load_app_appearance(self.config / "app-appearance.json"), result["app"])
        self.assertIn("0.850000", self.paths[1].read_text())

    def test_partial_update_merges_latest_and_avoids_shell_for_app_only(self):
        before = self.shell_path.read_bytes()
        with patch.object(build, "build_shell") as shell, patch.object(build, "reload_shell_theme") as reload:
            result = build.apply_locked({"app": {"enabled": True}}, True, True)
            shell.assert_not_called()
            reload.assert_not_called()
        self.assertEqual(self.shell_path.read_bytes(), before)
        self.assertEqual(result["app"], {"enabled": True, "transparency": 25})
        build.apply_locked({"shell": {"transparency": 10}}, True, True)
        result = build.apply_locked({"shell": {"solid": True}}, True, True)
        self.assertEqual(result["shell"]["transparency"], 10)
        self.assertTrue(result["shell"]["readability_boost"])

    def test_write_failure_restores_all_preferences_and_css_including_absent_files(self):
        self.shell_path.write_bytes(self.shell_path.read_bytes().replace(b"\n", b"\r\n"))
        self.paths[0].write_bytes(b"/* previous CSS */\r\n")
        before = self.snapshot()
        write = build.save_app_appearance
        count = 0

        def fail_second(value, path):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("preference disk full")
            write(value, path)

        with patch.object(build, "save_app_appearance", side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, "Previous appearance restored"):
                build.apply_locked(settings.preset_values("Solid"), True, True)
        self.assertEqual(self.snapshot(), before)

    def test_each_generation_and_reload_failure_restores_previous_state(self):
        for target in ("build_shell", "reload_shell_theme", "atomic_write"):
            before = self.snapshot()
            original = getattr(build, target)
            count = 0

            def fail_once(*args, **kwargs):
                nonlocal count
                count += 1
                if count == 1:
                    raise OSError("injected failure")
                return original(*args, **kwargs)

            with self.subTest(target=target), patch.object(build, target, side_effect=fail_once):
                with self.assertRaisesRegex(RuntimeError, "injected failure"):
                    build.apply_locked(settings.preset_values("Balanced Frost"), True, True)
            self.assertEqual(self.snapshot(), before)

    def test_rollback_failure_is_explicit(self):
        with patch.object(build, "reload_shell_theme", side_effect=OSError("reload refused")):
            with self.assertRaisesRegex(RuntimeError, "Restoration errors:.*reload refused"):
                build.apply_locked(settings.preset_values("Balanced Frost"), True, True)
        records = diagnostics.read_records()["records"]
        rollback = [record for record in records if record["action"] == "rollback"]
        self.assertEqual([record["phase"] for record in rollback], ["start", "failure"])
        self.assertEqual(rollback[-1]["level"], "ERROR")
        self.assertEqual(len({record["operation"] for record in records}), 1)

    def test_completed_rollback_is_logged_before_apply_failure(self):
        with patch.object(build, "build_shell", side_effect=OSError("private failure")):
            with self.assertRaises(RuntimeError):
                build.apply_locked({"shell": {"transparency": 40}}, True, True)
        records = diagnostics.read_records()["records"]
        self.assertEqual([(r["action"], r["phase"]) for r in records],
                         [("apply", "start"), ("rollback", "start"),
                          ("rollback", "success"), ("apply", "failure")])
        self.assertNotIn("private failure", json.dumps(records))

    def test_worker_stdout_stays_one_json_object_with_or_without_diagnostics(self):
        for unavailable in (False, True):
            with self.subTest(unavailable=unavailable), \
                    patch.object(sys, "argv", ["build.py", "--shell-only",
                                              "--appearance-patch", '{"app":{"enabled":true}}']), \
                    contextlib.redirect_stdout(io.StringIO()) as output, \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                if unavailable:
                    with patch.object(diagnostics, "_prepare", side_effect=PermissionError("private")), \
                            patch.object(diagnostics, "_warned", False):
                        build.main()
                else:
                    build.main()
                self.assertEqual(len(output.getvalue().splitlines()), 1)
                self.assertTrue(json.loads(output.getvalue())["app"]["enabled"])
                if unavailable:
                    self.assertIn("storage unavailable", errors.getvalue())

    def test_invalid_patch_never_changes_files(self):
        before = self.snapshot()
        for value in ([], {"unknown": {}}, {"shell": {"solid": 1}}, {"app": {"surprise": True}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build.apply_locked(value, True, True)
            self.assertEqual(self.snapshot(), before)

    def test_invalid_config_requires_explicit_complete_replacement(self):
        self.shell_path.write_text("{bad json")
        with self.assertRaisesRegex(ValueError, "Reset the affected section"):
            build.apply_locked({"shell": {"transparency": 25}}, True, True)
        with patch("sys.stderr"):
            result = build.apply_locked({"shell": {"transparency": 25, "glass_mode": "frost",
                                                   "solid": False, "readability_boost": False,
                                                   "background_blur": True}}, True, True)
        self.assertEqual(settings.load_settings(self.shell_path), result["shell"])
        (self.config / "app-appearance.json").write_text("{bad")
        (self.config / "files-appearance.json").write_text("{bad")
        with patch("sys.stderr"):
            result = build.apply_locked({"app": {"enabled": False, "transparency": 25},
                                         "files": {"enabled": False, "transparency": 25}}, True, True)
        self.assertEqual(result["app"], {"enabled": False, "transparency": 25})
        self.assertEqual(result["files"], result["app"])

    def test_effect_failure_restores_ownership_record_and_files(self):
        import managed_glass
        backup = self.config / "glass-backup.json"
        before = self.snapshot()

        def fail_apply(_mode, _blur, _solid):
            backup.write_text('{"new": "backup"}')
            raise RuntimeError("effect refused")

        with patch.object(build, "project_theme_active", return_value=True), \
             patch.object(managed_glass, "BACKUP", backup), \
             patch.object(managed_glass, "verify_capabilities"), \
             patch.object(managed_glass, "read_key", return_value="'before'"), \
             patch.object(managed_glass, "pipelines", return_value={}), \
             patch.object(managed_glass, "apply", side_effect=fail_apply), \
             patch.object(managed_glass, "restore_snapshot") as restore:
            with self.assertRaisesRegex(RuntimeError, "effect refused"):
                build.apply_locked(settings.preset_values("Solid"), True, True)
        restore.assert_called_once()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(backup.exists())

    def test_cli_preserves_new_flags_and_releases_lock_on_failure(self):
        with patch.object(sys, "argv", ["build.py", "--shell-only", "--transparency", "9",
                                       "--glass-mode", "frost", "--save-setting"]):
            build.main()
        result = settings.load_settings(self.shell_path)
        self.assertTrue(result["readability_boost"])
        self.assertEqual(result["transparency"], 9)
        with patch.object(sys, "argv", ["build.py", "--shell-only", "--transparency", "10", "--save-setting"]), \
             patch.object(build, "build_shell", side_effect=OSError("failed")):
            with self.assertRaises(RuntimeError):
                build.main()
        import fcntl
        with (self.config / "build.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
