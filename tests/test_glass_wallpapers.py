import copy
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/yaru_glass"))
sys.path.insert(0, str(ROOT / "scripts"))
import managed_glass as glass
import wallpapers
import theme_settings
import build
from gi.repository import GLib


def setUpModule():
    state = tempfile.TemporaryDirectory(prefix="yaru-glass-wallpaper-state-")
    unittest.addModuleCleanup(state.cleanup)
    environment = patch.dict(os.environ, {"XDG_STATE_HOME": state.name})
    environment.start()
    unittest.addModuleCleanup(environment.stop)


class PipelineSerializationTests(unittest.TestCase):
    def test_repair_reload_requires_active_extension(self):
        connection = Mock()
        connection.call_sync.return_value = GLib.Variant("(b)", (True,))
        with patch.object(glass.Gio, "bus_get_sync", return_value=connection), \
                patch.object(glass, "running_extension_info",
                             side_effect=[{"state": 2}, {"state": 1}]):
            glass.reload_blur_extension()
            self.assertEqual([call.args[3] for call in connection.call_sync.call_args_list],
                             ["DisableExtension", "EnableExtension"])
            self.assertEqual(connection.call_sync.call_args.args[4].unpack(), (glass.UUID,))
        connection.reset_mock()
        connection.call_sync.return_value = GLib.Variant("(b)", (False,))
        with patch.object(glass.Gio, "bus_get_sync", return_value=connection):
            with self.assertRaisesRegex(ValueError, "refused EnableExtension"):
                glass.reload_blur_extension()
        self.assertEqual([call.args[3] for call in connection.call_sync.call_args_list],
                         ["DisableExtension", "EnableExtension"])

    def test_reload_timeout_still_attempts_reenable(self):
        connection = Mock()
        connection.call_sync.return_value = GLib.Variant("(b)", (True,))
        with patch.object(glass.Gio, "bus_get_sync", return_value=connection), \
                patch.object(glass.time, "monotonic", side_effect=[0, 16, 20, 20]), \
                patch.object(glass, "running_extension_info", return_value={"state": 1}):
            with self.assertRaisesRegex(ValueError, "did not finish DisableExtension"):
                glass.reload_blur_extension()
        self.assertEqual([call.args[3] for call in connection.call_sync.call_args_list],
                         ["DisableExtension", "EnableExtension"])

    def test_write_pipelines_accepts_tuple_values(self):
        for color in ((1.0, 1.0, 1.0, 0.25), [1.0, 1.0, 1.0, 0.25]):
            with self.subTest(color=color):
                value = glass.pack(color)
                self.assertEqual(value.get_type_string(), "(dddd)")
                self.assertEqual(value.unpack(), (1.0, 1.0, 1.0, 0.25))

    def test_four_effects_remain_variant_array_not_color_tuple(self):
        effects = [{"type": "noise", "id": f"effect_{i}", "params": {}} for i in range(4)]
        value = glass.pack(effects)
        self.assertEqual(value.get_type_string(), "av")
        self.assertEqual(value.unpack(), effects)

    def test_serialized_comparison_detects_invalid_220_color_array(self):
        library = {"pipeline_default": {"name": "Default", "effects": [{
            "type": "color", "id": "effect_color", "params": {"color": [1., 1., 1., .25]},
        }]}}
        valid = glass.pipeline_variant(library)
        broken = valid.print_(True).replace(
            "(1.0, 1.0, 1.0, 0.25)", "[<1.0>, <1.0>, <1.0>, <0.25>]")
        invalid = GLib.Variant.parse(None, broken, None, None)
        self.assertEqual(invalid.unpack(), library)
        settings = Mock()
        settings.get_value.return_value = invalid
        with patch.object(glass, "extension_settings", return_value=settings):
            self.assertFalse(glass.pipelines_match(library))
            settings.get_value.return_value = valid
            self.assertTrue(glass.pipelines_match(library))

    def test_snapshot_restoration_uses_valid_color_tuple_encoding(self):
        library = {"pipeline_user": {"name": "User", "effects": [{
            "type": "color", "id": "effect_user", "params": {"color": [1., 1., 1., .25]},
        }]}}
        with patch.object(glass, "write_key") as write:
            glass.restore_snapshot({}, library)
        key, text = write.call_args.args
        self.assertEqual(key, "pipelines")
        restored = GLib.Variant.parse(None, text, None, None).unpack()
        self.assertEqual(restored["pipeline_user"]["effects"][0]["params"]["color"],
                         (1., 1., 1., .25))

    def test_upstream_bms_parser_and_manager_accept_all_managed_pipelines(self):
        roots = (Path.home() / ".local/share/gnome-shell/extensions" / glass.UUID,
                 Path("/usr/share/gnome-shell/extensions") / glass.UUID)
        root = next((p for p in roots if (p / "settings/pipeline_settings.js").is_file()), None)
        if root is None or shutil.which("gjs") is None:
            self.skipTest("Installed Blur my Shell pipeline parser and GJS are required")
        settings = glass.extension_settings(path=root)
        stock = settings.get_default_value("pipelines").unpack()
        custom = {"pipeline_user_test": {"name": "Unrelated color", "effects": [{
            "type": "color", "id": "effect_user_color", "params": {"color": [0.2, 0.3, 0.4, 0.5]},
        }]}}
        library = {**stock, **custom, **glass.managed_pipelines("dual_kawase_blur")}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipelines.variant"
            with patch.object(glass, "write_key") as write:
                glass.write_pipelines(library)
            path.write_text(write.call_args.args[1])
            result = subprocess.run(
                ["gjs", "-m", str(ROOT / "tests/check_bms_pipelines.js"), str(root), str(path)],
                env={**os.environ, "GSETTINGS_BACKEND": "memory"},
                text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("panel, popup, dock: Frost and Crystal accepted", result.stdout)
            valid_text = path.read_text()
            invalid_text = valid_text.replace(
                glass.pack([.2, .3, .4, .5]).print_(True), "[<0.2>, <0.3>, <0.4>, <0.5>]")
            self.assertNotEqual(valid_text, invalid_text)
            path.write_text(invalid_text)
            rejected = subprocess.run(
                ["gjs", "-m", str(ROOT / "tests/check_bms_pipelines.js"), str(root), str(path)],
                env={**os.environ, "GSETTINGS_BACKEND": "memory"},
                text=True, capture_output=True, timeout=30)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("unsupported value", rejected.stderr)


class GlassTests(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.backup = Path(directory.name) / "glass.json"
        self.keys = {key: None for key in glass.desired_keys("frost")}
        self.keys["popup/pipeline"] = "'existing'"
        self.pipelines = {"existing": {"name": "Unrelated", "effects": []}}
        self.original_keys = self.keys.copy()
        self.original_pipelines = copy.deepcopy(self.pipelines)
        for patcher in (
            patch.object(glass, "BACKUP", self.backup),
            patch.object(glass, "verify_capabilities", return_value="native_static_gaussian_blur"),
            patch.object(glass, "read_key", side_effect=lambda key: self.keys[key]),
            patch.object(glass, "write_key", side_effect=self.write_key),
            patch.object(glass, "pipelines", side_effect=lambda: copy.deepcopy(self.pipelines)),
            patch.object(glass, "write_pipelines", side_effect=self.write_pipelines),
            patch.object(glass, "pipelines_match", return_value=True),
            patch.object(glass, "reload_blur_extension"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_key(self, key, value):
        self.keys[key] = value

    def write_pipelines(self, value):
        self.pipelines = copy.deepcopy(value)

    def test_modes_and_restore_preserve_unrelated_pipelines(self):
        glass.apply("frost")
        self.assertEqual(self.keys, glass.desired_keys("frost"))
        backup = self.backup.read_text()
        glass.apply("crystal")
        self.assertEqual(self.keys, glass.desired_keys("crystal"))
        self.assertEqual(self.backup.read_text(), backup)
        self.pipelines["added_later"] = {"name": "User pipeline", "effects": []}
        glass.restore()
        self.assertEqual(self.keys, self.original_keys)
        self.assertEqual(self.pipelines["existing"], self.original_pipelines["existing"])
        self.assertIn("added_later", self.pipelines)
        self.assertFalse(glass.OWNED_IDS & self.pipelines.keys())
        self.assertFalse(self.backup.exists())
        glass.apply("crystal")
        self.assertTrue(self.backup.exists())

    def test_restore_accepts_legacy_dock_radius_backup(self):
        legacy_key = "dash-to-dock/corner-radius"
        self.keys[legacy_key] = "'24'"
        self.backup.write_text(json.dumps({
            "keys": {**self.original_keys, legacy_key: "'18'"},
            "pipelines": {},
        }))

        glass.restore()

        self.assertEqual(self.keys[legacy_key], "'18'")
        self.assertFalse(self.backup.exists())

    def test_idempotent_apply_does_not_reconfigure(self):
        glass.apply("frost")
        with patch.object(glass, "write_key") as write, patch.object(glass, "write_pipelines") as pipelines:
            glass.apply("frost")
            write.assert_not_called()
            pipelines.assert_not_called()

    def test_apply_repairs_220_serialization_even_when_unpacked_values_match(self):
        for mode in ("frost", "crystal"):
            with self.subTest(mode=mode):
                glass.apply(mode)
                events = Mock()
                with patch.object(glass, "pipelines_match", return_value=False), \
                        patch.object(glass, "write_pipelines", wraps=self.write_pipelines) as write, \
                        patch.object(glass, "write_key", wraps=self.write_key) as key_write, \
                        patch.object(glass, "reload_blur_extension") as reload:
                    events.attach_mock(write, "library")
                    events.attach_mock(reload, "reload")
                    glass.apply(mode)
                    write.assert_called_once_with(self.pipelines)
                    key_write.assert_not_called()
                self.assertEqual([event[0] for event in events.mock_calls], ["library", "reload"])
                for area, section in (("panel", "panel"), ("popup", "popup"), ("dock", "dash-to-dock")):
                    self.assertEqual(self.keys[f"{section}/pipeline"],
                                     f"'pipeline_yaru_glass_{mode}_{area}'")

    def test_reload_failure_rolls_back_library_and_selected_keys(self):
        with patch.object(glass, "pipelines_match", return_value=False), \
                patch.object(glass, "reload_blur_extension", side_effect=ValueError("not active")):
            with self.assertRaisesRegex(RuntimeError, "previous effects restored: not active"):
                glass.apply("frost")
        self.assertEqual(self.keys, self.original_keys)
        self.assertEqual(self.pipelines, self.original_pipelines)

    def test_dynamic_blur_can_be_disabled_or_suppressed_by_solid(self):
        for mode in ("frost", "crystal"):
            glass.apply(mode)
            for section in ("panel", "popup", "dash-to-dock"):
                self.assertEqual(self.keys[f"{section}/blur"], "true")
                self.assertEqual(self.keys[f"{section}/static-blur"], "false")
                self.assertEqual(self.keys[f"{section}/override-background"], "false")
            for blur, solid in ((False, False), (True, True), (False, True)):
                glass.apply(mode, blur, solid)
                for section in ("panel", "popup", "dash-to-dock"):
                    self.assertEqual(self.keys[f"{section}/blur"], "false")
            self.assertEqual(glass.desired_keys(mode)["popup/calendar-corner-radius"], "28")

    def test_upgrade_snapshots_only_new_owned_keys(self):
        added = {"popup/calendar-corner-radius", "popup/osd-window-corner-radius", "popup/rounded-corners"}
        old = {key: value for key, value in self.original_keys.items() if key not in added}
        self.backup.write_text(json.dumps({"keys": old, "pipelines": {}}))
        self.keys["popup/calendar-corner-radius"] = "30"
        glass.apply("frost")
        migrated = glass.read_backup()["keys"]
        self.assertEqual({key: migrated[key] for key in old}, old)
        self.assertEqual(migrated["popup/calendar-corner-radius"], "30")
        glass.restore()
        self.assertEqual(self.keys["popup/calendar-corner-radius"], "30")

    def test_backup_upgrade_failure_does_not_change_effects(self):
        added = {"popup/calendar-corner-radius", "popup/osd-window-corner-radius", "popup/rounded-corners"}
        old = {key: value for key, value in self.original_keys.items() if key not in added}
        self.backup.write_text(json.dumps({"keys": old, "pipelines": {}}))
        before = self.backup.read_bytes()
        with patch.object(glass, "atomic_write", side_effect=OSError("backup denied")), \
             patch.object(glass, "write_key") as write:
            with self.assertRaisesRegex(OSError, "backup denied"):
                glass.apply("crystal")
        write.assert_not_called()
        self.assertEqual(self.backup.read_bytes(), before)
        self.assertEqual(self.keys, self.original_keys)

    def test_legacy_dock_entrypoint_respects_saved_blur_and_solid(self):
        helper = runpy.run_path(str(ROOT / "bin/bms-dock-pipeline.py"))
        for blur, solid in ((False, False), (True, True)):
            saved = theme_settings.validate_settings({
                "transparency": 25, "glass_mode": "crystal",
                "background_blur": blur, "solid": solid})
            with patch.dict(helper["main"].__globals__, {
                "CONFIG_DIR": self.backup.parent, "load_settings": lambda: saved,
            }), patch.object(glass, "apply") as apply, patch("builtins.print"):
                helper["main"]()
                apply.assert_called_once_with("crystal", blur, solid)

    def test_curated_profile_does_not_import_pipelines_or_enable_app_blur(self):
        import configparser
        profile = configparser.ConfigParser()
        profile.read(ROOT / "assets/profiles/blur-my-shell.ini")
        self.assertFalse(profile.getboolean("applications", "blur"))
        self.assertNotIn("pipelines", profile["/"])
        for section in profile.sections():
            self.assertNotIn("pipeline", profile[section])
        for section in ("panel", "popup", "dash-to-dock"):
            self.assertFalse(profile.getboolean(section, "static-blur"))
        for pipelines in glass.managed_pipelines("dual_kawase_blur").values():
            self.assertEqual([effect["type"] for effect in pipelines["effects"]], ["dual_kawase_blur"])

    def test_dock_rounding_uses_pipeline_without_optional_extension_setting(self):
        self.assertNotIn("dash-to-dock/corner-radius", glass.desired_keys("crystal"))
        dock_effects = glass.managed_pipelines()["pipeline_yaru_glass_crystal_dock"]["effects"]
        corner = next(effect for effect in dock_effects if effect["type"] == "corner")
        self.assertEqual(corner["params"]["radius"], 24)

    def test_new_extension_uses_kawase_without_manual_corner_effect(self):
        with patch.object(glass, "verify_capabilities", return_value="dual_kawase_blur"):
            glass.apply("frost")
        for name in glass.OWNED_IDS:
            effects = self.pipelines[name]["effects"]
            self.assertEqual([effect["type"] for effect in effects], ["dual_kawase_blur"])
        self.assertEqual(self.keys, glass.desired_keys("frost"))
        glass.restore()
        self.assertEqual(self.keys, self.original_keys)
        self.assertEqual(self.pipelines, self.original_pipelines)

    def test_upgrade_from_static_blur_keeps_original_restoration_record(self):
        glass.apply("frost")
        backup = self.backup.read_text()
        for section in ("panel", "popup", "dash-to-dock"):
            self.keys[f"{section}/blur"] = "true"
            self.keys[f"{section}/static-blur"] = "true"
        glass.apply("crystal")
        self.assertEqual(self.keys, glass.desired_keys("crystal"))
        self.assertEqual(self.backup.read_text(), backup)
        glass.restore()
        self.assertEqual(self.keys, self.original_keys)

    def test_apply_failure_rolls_back_and_retains_backup(self):
        count = 0
        def fail_once(key, value):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError("failed write")
            self.write_key(key, value)
        with patch.object(glass, "write_key", side_effect=fail_once):
            with self.assertRaisesRegex(RuntimeError, "previous effects restored"):
                glass.apply("crystal")
        self.assertEqual(self.keys, self.original_keys)
        self.assertEqual(self.pipelines, self.original_pipelines)
        self.assertTrue(self.backup.exists())

    def test_restore_failure_keeps_record(self):
        glass.apply("crystal")
        with patch.object(glass, "write_key", side_effect=OSError("read only")):
            with self.assertRaisesRegex(RuntimeError, "Could not restore"):
                glass.restore()
        self.assertTrue(self.backup.exists())

    def test_no_refraction_rim_and_modes_have_distinct_blur(self):
        pipelines = glass.managed_pipelines()
        for item in pipelines.values():
            self.assertNotIn("refraction", [effect["type"] for effect in item["effects"]])
        frost = pipelines["pipeline_yaru_glass_frost_popup"]["effects"][0]["params"]
        crystal = pipelines["pipeline_yaru_glass_crystal_popup"]["effects"][0]["params"]
        self.assertGreater(frost["unscaled_radius"], crystal["unscaled_radius"])
        self.assertEqual(frost["brightness"], 1.0)
        self.assertNotIn("corner", [effect["type"] for effect in pipelines["pipeline_yaru_glass_crystal_popup"]["effects"]])

    def test_missing_extension_aborts_before_backup_or_writes(self):
        with patch.object(glass, "verify_capabilities", side_effect=ValueError("Enable Blur my Shell")), \
             patch.object(glass, "write_key") as write:
            with self.assertRaisesRegex(ValueError, "Enable Blur"):
                glass.apply("crystal")
            write.assert_not_called()
            self.assertFalse(self.backup.exists())

    def test_sync_reactivation_and_deactivation_manage_effects(self):
        sync = runpy.run_path(str(ROOT / "bin/yaru-glass-sync"), run_name="sync_test")
        method = sync["Sync"].update_glass
        with patch.dict(method.__globals__, {"CONFIG_DIR": self.backup.parent,
                                             "load_settings": lambda: theme_settings.validate_settings(
                                                 {"glass_mode": "crystal", "transparency": 25})}):
            with patch.object(method.__globals__["files_appearance"], "refresh") as refresh:
                instance = object.__new__(sync["Sync"])
                instance.update_glass(True)
                self.assertEqual(self.keys, glass.desired_keys("crystal"))
                instance.update_glass(False)
                self.assertEqual(self.keys, self.original_keys)
                instance.update_glass(True)
                self.assertEqual(self.keys, glass.desired_keys("crystal"))
                self.assertEqual(refresh.call_count, 2)
                refresh.assert_called_with("crystal")

    def test_sync_deduplicates_diagnostic_failure_then_reports_recovery(self):
        sync = runpy.run_path(str(ROOT / "bin/yaru-glass-sync"), run_name="sync_test")
        instance = object.__new__(sync["Sync"])
        with patch.dict(sync["Sync"].update_glass.__globals__,
                        {"CONFIG_DIR": self.backup.parent,
                         "load_settings": lambda: theme_settings.validate_settings({"transparency": 25})}), \
                patch.object(glass, "apply", side_effect=[ValueError("private"),
                                                         ValueError("private"), None]), \
                patch.object(sync["files_appearance"], "refresh"), \
                patch.object(sync["diagnostics"], "event") as event:
            instance.update_glass(True)
            instance.update_glass(True)
            instance.update_glass(True)
        self.assertEqual([call.args[:3] for call in event.call_args_list],
                         [("sync", "apply", "failure"), ("sync", "apply", "success")])
        self.assertIsNone(instance.last_error)

    def test_sync_retries_when_extension_becomes_active_without_reactivating_other_themes(self):
        sync = runpy.run_path(str(ROOT / "bin/yaru-glass-sync"), run_name="sync_test")
        instance = object.__new__(sync["Sync"])
        instance.policy_uuids = (glass.UUID, "ubuntu-dock@ubuntu.com")
        instance.iface = Mock()
        instance.on_changed = Mock()
        for uuid, state, theme, retry in (
            (glass.UUID, 1, sync["LIGHT"], True),
            (glass.UUID, 1, sync["DARK"], True),
            ("ubuntu-dock@ubuntu.com", 1, sync["LIGHT"], True),
            (glass.UUID, 2, sync["LIGHT"], False),
            (glass.UUID, 1, "Yaru", False),
            ("unrelated@example", 1, sync["LIGHT"], False),
        ):
            with self.subTest(uuid=uuid, state=state, theme=theme), patch("builtins.print"):
                instance.iface.get_string.return_value = theme
                instance.on_changed.reset_mock()
                instance.on_extension_changed(None, None, None, None, None,
                    GLib.Variant("(sa{sv})", (uuid, {"state": GLib.Variant("d", state)})))
                if retry:
                    instance.on_changed.assert_called_once_with(None, "extensions")
                else:
                    instance.on_changed.assert_not_called()

    def test_extension_refresh_is_debounced_and_preserves_pending_theme_changes(self):
        sync = runpy.run_path(str(ROOT / "bin/yaru-glass-sync"), run_name="sync_test")
        for next_theme in ("Yaru", sync["DARK"]):
            with self.subTest(theme=next_theme), patch("builtins.print"), \
                    patch.object(GLib, "timeout_add", return_value=42) as schedule, \
                    patch.object(GLib, "source_remove") as cancel:
                instance = object.__new__(sync["Sync"])
                instance.policy_uuids = (glass.UUID,)
                values = {"gtk-theme": sync["LIGHT"], "color-scheme": "prefer-light"}
                instance.iface = Mock()
                instance.iface.get_string.side_effect = values.__getitem__
                instance.changed = set()
                instance.timeout_id = 0
                instance.activate = Mock()
                instance.deactivate = Mock()
                parameters = GLib.Variant("(sa{sv})", (
                    glass.UUID, {"state": GLib.Variant("d", 1)}))
                for _ in range(2):
                    instance.on_extension_changed(None, None, None, None, None, parameters)
                cancel.assert_called_once_with(42)
                self.assertEqual(schedule.call_count, 2)
                self.assertEqual(instance.changed, {"extensions"})
                values["gtk-theme"] = next_theme
                instance.changed.add("gtk-theme")
                instance.sync()
                if next_theme == "Yaru":
                    instance.deactivate.assert_called_once_with()
                    instance.activate.assert_not_called()
                else:
                    instance.iface.set_string.assert_called_once_with(
                        "color-scheme", "prefer-dark")
                    instance.activate.assert_called_once_with(True)
                    instance.deactivate.assert_not_called()

    def test_once_returns_failure_for_managed_integration_error(self):
        sync = runpy.run_path(str(ROOT / "bin/yaru-glass-sync"), run_name="sync_test")
        for error in (None, "unsupported active extension"):
            instance = Mock(last_error=error)
            with self.subTest(error=error), patch.dict(sync["main"].__globals__, {
                "Sync": lambda: instance,
            }), patch.object(sys, "argv", ["yaru-glass-sync", "--once"]):
                if error is None:
                    sync["main"]()
                else:
                    with self.assertRaises(SystemExit) as result:
                        sync["main"]()
                    self.assertEqual(result.exception.code, 1)
                instance.sync.assert_called_once()


class CapabilityTests(unittest.TestCase):
    def test_running_policy_checks_include_distro_enabled_integrations(self):
        shell = Mock()
        shell.get_boolean.return_value = False
        shell.get_strv.side_effect = lambda key: [glass.UUID] if key == "enabled-extensions" else []
        connection = Mock()
        connection.call_sync.return_value = GLib.Variant("(v)", (GLib.Variant("s", "50.1"),))
        dock = "ubuntu-dock@ubuntu.com"
        active = {"state": 1, "version": 77, "path": "/test"}
        other = {"state": 1, "version": 999}
        with patch.object(glass.Gio.Settings, "new", return_value=shell), \
             patch.object(glass.Gio, "bus_get_sync", return_value=connection), \
             patch.object(glass, "running_extension_info",
                          side_effect=lambda _connection, uuid: active if uuid == glass.UUID else other), \
             patch.object(glass, "policy_extension_uuids", return_value=(glass.UUID, dock)) as policy, \
             patch.object(glass, "validate_running_extension",
                          side_effect=[None, ValueError("unsupported dock release")]) as validate, \
             patch.object(glass, "extension_settings") as schemas:
            with self.assertRaisesRegex(ValueError, "unsupported dock release"):
                glass.verify_capabilities(glass.desired_keys("frost"))
        policy.assert_called_once_with("50")
        self.assertEqual(validate.call_args.args, (dock, other))
        self.assertEqual(validate.call_args.kwargs, {"shell_version": "50"})
        schemas.assert_not_called()

    def test_effect_layouts_are_checked_in_running_extension_directory(self):
        shell = Mock()
        shell.get_boolean.return_value = False
        shell.get_strv.side_effect = lambda key: [glass.UUID] if key == "enabled-extensions" else []
        connection = Mock()
        extension = Mock()
        extension.props.settings_schema.list_keys.return_value = [
            key.split("/")[1] for key in glass.desired_keys("frost")]
        extension.is_writable.return_value = True
        layouts = (
            (("native_static_gaussian_blur.js", "corner.js"), "native_static_gaussian_blur"),
            (("blur/native_static_gaussian_blur.js", "corner/corner.js"), "native_static_gaussian_blur"),
            (("blur/dual_kawase_blur.js",), "dual_kawase_blur"),
            (("native_static_gaussian_blur.js",), None),
            ((), None),
        )
        for files, expected in layouts:
            with self.subTest(files=files), tempfile.TemporaryDirectory() as directory:
                for name in ("dynamic_surface.js", "rounded_pipeline.js"):
                    path = Path(directory) / "render" / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                for name in files:
                    path = Path(directory) / "effects" / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                active = GLib.Variant("(a{sv})", ({
                    "state": GLib.Variant("d", 1.0), "path": GLib.Variant("s", directory),
                    "version": GLib.Variant("d", 77.0),
                },))
                connection.call_sync.side_effect = lambda _bus, _path, _interface, method, params, *_args: (
                    GLib.Variant("(v)", (GLib.Variant("s", "46.0"),)) if method == "Get" else
                    active if params.unpack()[0] == glass.UUID else GLib.Variant("(a{sv})", ({},)))
                with patch.object(glass.Gio.Settings, "new", return_value=shell), \
                     patch.object(glass.Gio, "bus_get_sync", return_value=connection), \
                     patch.object(glass, "extension_settings", return_value=extension):
                    if expected:
                        self.assertEqual(glass.verify_capabilities(glass.desired_keys("frost")), expected)
                    else:
                        with self.assertRaisesRegex(ValueError, "lacks the required"):
                            glass.verify_capabilities(glass.desired_keys("frost"))

    def test_enabled_but_not_running_extension_reports_error(self):
        shell = Mock()
        shell.get_boolean.return_value = False
        shell.get_strv.side_effect = lambda key: [glass.UUID] if key == "enabled-extensions" else []
        connection = Mock()
        connection.call_sync.return_value = GLib.Variant("(a{sv})", ({"state": GLib.Variant("d", 3.0)},))
        with patch.object(glass.Gio.Settings, "new", return_value=shell), \
             patch.object(glass.Gio, "bus_get_sync", return_value=connection):
            with self.assertRaisesRegex(ValueError, "not running"):
                glass.verify_capabilities(glass.desired_keys("frost"))


class FakeBackground:
    def __init__(self):
        self.values = {"picture-uri": "file:///light-before.jpg", "picture-uri-dark": "file:///dark-before.jpg"}
        self.writable = True
        self.refuse = False

    def get_string(self, key):
        return self.values[key]

    def get_user_value(self, key):
        return GLib.Variant("s", self.values[key])

    def is_writable(self, _key):
        return self.writable

    def set_string(self, key, value):
        if self.refuse:
            return False
        self.values[key] = value
        return True

    def set_value(self, key, value):
        return self.set_string(key, value.unpack())

    def reset(self, key):
        self.values[key] = ""


class WallpaperTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "sample.png"
        from gi.repository import GdkPixbuf
        image = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 2, 2)
        image.fill(0x334455ff)
        image.savev(str(self.path), "png", [], [])
        self.background = FakeBackground()
        for patcher in (
            patch.object(wallpapers, "BACKUP", self.root / "backup.json"),
            patch.object(wallpapers, "background", return_value=self.background),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_independent_slots_and_original_restoration(self):
        before = self.background.values.copy()
        wallpapers.set_wallpaper("picture-uri", self.path)
        self.assertEqual(self.background.values["picture-uri-dark"], before["picture-uri-dark"])
        wallpapers.set_wallpaper("picture-uri-dark", self.path)
        wallpapers.restore()
        self.assertEqual(self.background.values, before)
        self.assertFalse(wallpapers.BACKUP.exists())

    def test_external_choice_is_preserved(self):
        wallpapers.set_wallpaper("picture-uri", self.path)
        self.background.values["picture-uri"] = "file:///externally-chosen.jpg"
        wallpapers.restore()
        self.assertEqual(self.background.values["picture-uri"], "file:///externally-chosen.jpg")
        self.assertFalse(wallpapers.BACKUP.exists())

    def test_new_takeover_backs_up_latest_external_value(self):
        wallpapers.set_wallpaper("picture-uri", self.path)
        self.background.values["picture-uri"] = "file:///external.jpg"
        wallpapers.set_wallpaper("picture-uri", self.path)
        wallpapers.restore_slot("picture-uri")
        self.assertEqual(self.background.values["picture-uri"], "file:///external.jpg")

    def test_invalid_file_and_policy_error_do_not_change_settings(self):
        before = self.background.values.copy()
        invalid = self.root / "bad.png"
        invalid.write_text("not an image")
        with self.assertRaises(ValueError):
            wallpapers.set_wallpaper("picture-uri", invalid)
        with self.assertRaises(FileNotFoundError):
            wallpapers.set_wallpaper("picture-uri", self.root / "missing")
        self.background.writable = False
        with self.assertRaisesRegex(ValueError, "locked"):
            wallpapers.set_wallpaper("picture-uri", self.path)
        self.assertEqual(self.background.values, before)
        self.assertFalse(wallpapers.BACKUP.exists())

    def test_refused_write_preserves_backup_and_prior_value(self):
        self.background.refuse = True
        with self.assertRaisesRegex(ValueError, "refused"):
            wallpapers.set_wallpaper("picture-uri", self.path)
        self.assertFalse(wallpapers.BACKUP.exists())

    def test_failed_restore_keeps_record(self):
        wallpapers.set_wallpaper("picture-uri", self.path)
        self.background.writable = False
        with self.assertRaisesRegex(ValueError, "locked"):
            wallpapers.restore()
        self.assertTrue(wallpapers.BACKUP.exists())


def luminance(rgb):
    values = [v / 255 for v in rgb]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))


class AppearanceTests(unittest.TestCase):
    def test_migration_preserves_transparency_when_saving_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"transparency": 37}')
            value = theme_settings.load_settings(path)
            self.assertEqual(value, {"transparency": 37, "glass_mode": "frost",
                                     "solid": False, "readability_boost": False, "background_blur": True})
            value["glass_mode"] = "crystal"
            theme_settings.save_settings(value, path)
            theme_settings.save_transparency(12, path)
            self.assertEqual(theme_settings.load_settings(path), {"transparency": 12, "glass_mode": "crystal",
                                                                "solid": False, "readability_boost": False,
                                                                "background_blur": True})
            path.write_text('{"transparency": 25, "glass_mode": "bad"}')
            with self.assertRaises(ValueError):
                theme_settings.load_settings(path)

    def test_popup_text_contrast_over_black_white_and_sample_colors(self):
        worst = 100
        for variant in build.VARIANTS:
            fg = tuple(int(variant["shell"]["fg"][i:i+2], 16) for i in (1, 3, 5))
            for mode, boost, solid in ((mode, boost, solid) for mode in ("frost", "crystal")
                                       for boost in (False, True) for solid in (False, True)):
                for value in (0, 25, 50):
                    colors = theme_settings.shell_colors(variant["shell"], value, mode, solid, boost)
                    for token in ("panel_bg", "menu_bg", "notification_bg", "dialog_bg"):
                        rgba = [float(v) for v in re.findall(r"[\d.]+", colors[token])]
                        for backdrop in ((0, 0, 0), (255, 255, 255), (245, 45, 80), (40, 220, 190)):
                            effective = [rgba[i] * rgba[3] + backdrop[i] * (1 - rgba[3]) for i in range(3)]
                            a, b = sorted((luminance(fg), luminance(effective)))
                            contrast = (b + .05) / (a + .05)
                            worst = min(worst, contrast)
                            self.assertGreaterEqual(contrast, 4.5, (variant["name"], mode, value, token, backdrop, contrast))
        print(f"Lowest tested normal text contrast: {worst:.2f}:1")

    def test_popup_shapes_and_plain_calendar(self):
        css = (ROOT / "src/theme/gnome-shell/glass.css.in").read_text()
        self.assertRegex(css, r"\.datemenu-popover\s*\{\s*border-radius: 28px")
        self.assertIn("border-radius: 28px", css.split(".quick-toggle-menu {", 1)[1].split("\n}", 1)[0])
        self.assertIn("-arrow-border-width: 0", css)
        self.assertIn("#calendarArea .message-list .message-list-placeholder", css)
        self.assertIn("#calendarArea .datemenu-today-button:insensitive .date-label", css)
        self.assertIn(".quick-settings .quick-toggle-arrow:rtl", css)
        self.assertIn("box-shadow: none !important;", css)

    def test_outer_surfaces_have_no_border_strokes_or_inset_highlights(self):
        css = (ROOT / "src/theme/gnome-shell/glass.css.in").read_text()
        for selector in (".candidate-popup-content", ".quick-settings",
                         ".notification-banner:active",
                         "#dashtodockContainer.bottom.shrink.fixed #dash .dash-background",
                         ".workspace-switcher", ".osd-window", ".end-session-dialog"):
            rules = css.split(selector + " {", 1)[1].split("\n}", 1)[0]
            self.assertIn("border: none", rules, selector)
            self.assertNotIn("box-shadow: inset", rules, selector)

    def test_notification_headers_use_opaque_foreground_in_banner_and_calendar(self):
        css = (ROOT / "src/theme/gnome-shell/glass.css.in").read_text()
        for parent in ("#calendarArea .message", ".notification-banner"):
            for child in ("", " .message-source-icon",
                          " .message-header-content .message-source-title",
                          " .message-header-content .event-time"):
                selector = parent + " .message-header" + child
                self.assertIn(selector, css)
        rules = css.split(".notification-banner .message-header .message-header-content .event-time {", 1)[1].split("\n}", 1)[0]
        self.assertIn("color: ${fg} !important;", rules)
        self.assertIn("icon-shadow: none;", rules)

    def test_borderless_notifications_reset_yaru_negative_directional_padding(self):
        css = (ROOT / "src/theme/gnome-shell/glass.css.in").read_text()
        self.assertIn(".notification-banner:ltr,", css)
        self.assertIn(".notification-banner:rtl,", css)
        rules = css.split(".notification-banner:active {", 1)[1].split("\n}", 1)[0]
        self.assertIn("padding: 0;", rules)
        self.assertIn("border: none;", rules)


if __name__ == "__main__":
    unittest.main()
