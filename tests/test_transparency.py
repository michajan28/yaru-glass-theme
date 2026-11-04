import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/yaru_glass"))
import theme_settings as settings
import managed_glass

spec = importlib.util.spec_from_file_location("theme_build", ROOT / "scripts/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def setUpModule():
    state = tempfile.TemporaryDirectory(prefix="yaru-transparency-state-")
    unittest.addModuleCleanup(state.cleanup)
    environment = patch.dict(os.environ, {"XDG_STATE_HOME": state.name})
    environment.start()
    unittest.addModuleCleanup(environment.stop)


class SettingsTests(unittest.TestCase):
    def test_app_appearance_is_opt_in_and_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app-appearance.json"
            shell = Path(directory) / "settings.json"
            settings.save_settings({"transparency": 15, "glass_mode": "crystal"}, shell)
            original = shell.read_bytes()
            self.assertEqual(settings.load_app_appearance(path), {"enabled": False, "transparency": 25})
            for enabled in (False, True):
                for level in (0, 25, 50):
                    value = {"enabled": enabled, "transparency": level}
                    settings.save_app_appearance(value, path)
                    self.assertEqual(settings.load_app_appearance(path), value)
            self.assertEqual(shell.read_bytes(), original)
            before = path.read_bytes()
            with patch.object(Path, "replace", side_effect=OSError("read only")):
                with self.assertRaises(OSError):
                    settings.save_app_appearance({"enabled": False, "transparency": 0}, path)
            self.assertEqual(path.read_bytes(), before)

    def test_invalid_app_appearance_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.json"
            for value in ("{", "[]", "{}", '{"enabled": 1, "transparency": 25}',
                          '{"enabled": true, "transparency": 51}',
                          '{"enabled": true, "transparency": false}'):
                path.write_text(value)
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Invalid app appearance"):
                    settings.load_app_appearance(path)

    def test_missing_config_defaults_to_25(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(settings.load_transparency(Path(directory) / "absent.json"), 25)

    def test_round_trip_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config" / "settings.json"
            for value in (0, 25, 50):
                settings.save_transparency(value, path)
                self.assertEqual(settings.load_transparency(path), value)
            for value in (-1, 51, True, 25.0, "25", None):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    settings.save_transparency(value, path)
            self.assertEqual(settings.load_transparency(path), 50)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_invalid_config_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            for content in ("{", "[]", "{}", '{"transparency": true}', '{"transparency": 99}'):
                path.write_text(content)
                with self.subTest(content=content), self.assertRaisesRegex(ValueError, "Invalid settings"):
                    settings.load_transparency(path)
            with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
                with self.assertRaises(PermissionError):
                    settings.load_transparency(path)

    def test_atomic_write_failure_preserves_previous_setting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            settings.save_transparency(25, path)
            with patch.object(Path, "replace", side_effect=OSError("read only")):
                with self.assertRaises(OSError):
                    settings.save_transparency(50, path)
            self.assertEqual(json.loads(path.read_text()), {"transparency": 25, "glass_mode": "frost",
                                                           "solid": False, "readability_boost": False,
                                                           "background_blur": True})
            self.assertEqual(list(path.parent.iterdir()), [path])


class BuildTests(unittest.TestCase):
    def setUp(self):
        active = patch.object(build, "project_theme_active", return_value=False)
        active.start()
        self.addCleanup(active.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        themes = patch.object(build, "THEMES_DIR", Path(directory.name) / "themes")
        themes.start()
        self.addCleanup(themes.stop)

    def test_exact_scaling_and_preserved_colors(self):
        for variant in build.VARIANTS:
            original = variant["shell"].copy()
            for value in (0, 25, 50):
                colors = settings.shell_colors(original, value)
                for key, color in original.items():
                    match = re.fullmatch(r"rgba\((.*),\s*([\d.]+)\)", color)
                    if key in settings.SURFACE_TOKENS and match:
                        alpha = float(colors[key].rsplit(",", 1)[1].rstrip(")"))
                        expected = float(match.group(2)) * (1 - value / 100)
                        if key in {"panel_bg", "menu_bg", "dialog_bg", "notification_bg"}:
                            floor = .70 if variant["dark"] else .58
                            expected = floor + (1 - floor) * expected
                        self.assertAlmostEqual(alpha, expected)
                    else:
                        self.assertEqual(colors[key], color)
                self.assertEqual(variant["shell"], original)
                self.assertEqual(settings.shell_colors(original, value), colors)
        light = settings.shell_colors(build.VARIANTS[0]["shell"], 25)
        dark = settings.shell_colors(build.VARIANTS[1]["shell"], 25)
        self.assertEqual(light["panel_bg"], "rgba(246, 246, 248, 0.7753)")
        self.assertEqual(dark["panel_bg"], "rgba(28, 28, 30, 0.80125)")
        self.assertEqual(light["entry_focus"], "#ffffff")

    def test_native_st_notification_banner_layout_and_shadow(self):
        typelib = next(iter(sorted(Path("/usr/lib/gnome-shell").glob("St-*.typelib"))), None)
        mutter = typelib and Path("/usr/lib/x86_64-linux-gnu") / f"mutter-{typelib.stem.split('-')[1]}"
        if not typelib or not mutter.is_dir() or not shutil.which("gjs") or not shutil.which("dbus-run-session"):
            self.skipTest("GNOME Shell St/Mutter typelibs, gjs and dbus-run-session are required")
        with tempfile.TemporaryDirectory(prefix="yaru-st-") as directory:
            directory = Path(directory)
            libraries = f"/usr/lib/gnome-shell:{mutter}"
            # Headless Mutter must not register names on, or draw into, the live session.
            environment = {key: value for key, value in os.environ.items() if key not in {
                "DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY", "DISPLAY"}}
            environment.update({"GI_TYPELIB_PATH": libraries, "LD_LIBRARY_PATH": libraries,
                                "XDG_RUNTIME_DIR": str(directory)})
            for solid in (False, True):
                paths = []
                for variant in build.VARIANTS:
                    for mode in ("frost", "crystal"):
                        output = directory / f"{variant['name']}-{mode}-{solid}"
                        build.build_shell(variant, output, 50, glass_mode=mode, solid=solid)
                        paths.append(str(output / "gnome-shell/gnome-shell.css"))
                command = ["dbus-run-session", "--", "gjs", str(ROOT / "tests/check_notification_layout.js")]
                result = subprocess.run(command + (["--solid"] if solid else []) + paths,
                                        env=environment, capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_shell_only_preserves_assets_and_calendar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "system" / "Yaru-blue"
            base.mkdir(parents=True)
            (base / "gnome-shell.css").write_text("/* base #0073E5 */")
            (base / "check.svg").write_text('<svg fill="#0073E5"/>')
            output = root / "output"
            variant = build.VARIANTS[0]
            with patch.object(build, "SYS_SHELL", base.parent):
                build.build_shell(variant, output, 25)
                asset = output / "gnome-shell" / "check.svg"
                before = asset.stat()
                gtk = output / "gtk-3.0" / "gtk.css"
                gtk.parent.mkdir()
                gtk.write_text("unchanged GTK")
                for value, expected_alpha in ((0, "0.8404"), (25, "0.7753"), (50, "0.7102")):
                    build.build_shell(variant, output, value, css_only=True)
                    css = (output / "gnome-shell" / "gnome-shell.css").read_text()
                    self.assertIn(f"rgba(246, 246, 248, {expected_alpha})", css)
                    self.assertIn("#calendarArea .calendar .calendar-day.calendar-today", css)
                    self.assertIn("background-color: #007AFF !important;", css)
                    self.assertNotIn("${", css)
                self.assertEqual(asset.stat().st_mtime_ns, before.st_mtime_ns)
                self.assertEqual(gtk.read_text(), "unchanged GTK")
                with self.assertRaisesRegex(FileNotFoundError, "install.sh"):
                    build.build_shell(variant, root / "missing", 25, css_only=True)

    def test_shell_build_uses_modern_yaru_fallback_for_both_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for variant in build.VARIANTS:
                name = "Yaru-dark" if variant["dark"] else "Yaru"
                base = root / "system" / name
                base.mkdir(parents=True)
                (base / "gnome-shell.css").write_text(
                    "/* modern base */\n.test { color: -st-accent-fg-color; "
                    "background-color: st-mix(-st-accent-color, white, 20%); }\n")
                (base / "check.svg").write_text('<svg fill="#0073E5"/>')
                output = root / variant["name"]
                with patch.object(build, "SYS_SHELL", base.parent):
                    build.build_shell(variant, output, 25)
                    build.build_shell(variant, output, 50, css_only=True)
                css = (output / "gnome-shell/gnome-shell.css").read_text()
                self.assertIn(f"st-mix({variant['shell']['accent']}, white, 20%)", css)
                self.assertIn("color: #ffffff;", css)
                self.assertIn("background-color: rgba(246, 246, 248, 0.7102) !important;"
                              if not variant["dark"] else
                              "background-color: rgba(28, 28, 30, 0.7675) !important;", css)
                self.assertNotIn("-st-accent-", css)
                self.assertIn(variant["shell"]["accent"],
                              (output / "gnome-shell/check.svg").read_text())

    def test_shell_build_prefers_legacy_colored_base_when_both_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("Yaru-blue", "Yaru"):
                base = root / name
                base.mkdir()
                (base / "gnome-shell.css").write_text(f"/* {name} */")
            with patch.object(build, "SYS_SHELL", root):
                build.build_shell(build.VARIANTS[0], root / "output", 25)
            css = (root / "output/gnome-shell/gnome-shell.css").read_text()
            self.assertIn("/* Yaru-blue */", css)
            self.assertNotIn("/* Yaru */", css)

    def test_missing_shell_bases_report_both_expected_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(build, "SYS_SHELL", root):
                with self.assertRaisesRegex(FileNotFoundError, "Yaru-blue.*Yaru"):
                    build.build_shell(build.VARIANTS[0], root / "output", 25)
            self.assertFalse((root / "output").exists())

    def test_reload_inactive_theme_is_not_activated(self):
        with patch.object(build.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "'Other'\n")) as run:
            build.reload_shell_theme()
            self.assertEqual(run.call_count, 1)

    def test_reload_restores_theme_and_reports_errors(self):
        current = "'Yaru-Glass'"
        read = subprocess.CompletedProcess([], 0, current)
        with patch.object(build.subprocess, "run", side_effect=[
            read, subprocess.CalledProcessError(1, ["dconf"]), subprocess.CompletedProcess([], 0),
        ]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                build.reload_shell_theme()
            self.assertEqual(run.call_args.args[0][-1], current)

    def test_failed_build_does_not_save_or_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(build, "CONFIG_DIR", Path(directory)), \
                 patch.object(sys, "argv", ["build.py", "--shell-only", "--transparency", "30", "--save-setting"]), \
                 patch.object(build, "build_shell", side_effect=OSError("build failed")), \
                 patch.object(build, "save_settings") as save, \
                 patch.object(build, "reload_shell_theme") as reload:
                with self.assertRaisesRegex(RuntimeError, "build failed"):
                    build.main()
                save.assert_not_called()
                reload.assert_called_once()

    def test_full_build_uses_saved_setting(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(build, "CONFIG_DIR", Path(directory)), \
                 patch.object(build, "THEMES_DIR", Path(directory) / "themes"), \
                 patch.object(sys, "argv", ["build.py"]), \
                 patch.object(build, "load_settings", return_value={"transparency": 40, "glass_mode": "crystal"}), \
                 patch.object(build, "build_index"), patch.object(build, "build_gtk"), \
                 patch.object(build, "build_shell") as shell, \
                 patch.object(build, "reload_shell_theme"):
                build.main()
                self.assertEqual(shell.call_count, 2)
                self.assertTrue(all(call.args[2] == 40 for call in shell.call_args_list))
                self.assertTrue(all(call.kwargs["glass_mode"] == "crystal" for call in shell.call_args_list))

    def test_reload_failure_does_not_save(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(build, "CONFIG_DIR", Path(directory)), \
                 patch.object(sys, "argv", ["build.py", "--shell-only", "--transparency", "30", "--save-setting"]), \
                 patch.object(build, "build_shell"), \
                 patch.object(build, "save_settings") as save, \
                 patch.object(build, "reload_shell_theme", side_effect=OSError("reload failed")):
                with self.assertRaisesRegex(RuntimeError, "reload failed"):
                    build.main()
                save.assert_not_called()

    def test_failed_save_restores_css_and_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [build.THEMES_DIR / variant["name"] / "gnome-shell/gnome-shell.css"
                     for variant in build.VARIANTS]
            for path in paths:
                path.parent.mkdir(parents=True)
                path.write_text("old working CSS")

            def write_new(variant, output, *_args, **_kwargs):
                (output / "gnome-shell/gnome-shell.css").write_text("new CSS")

            with patch.object(build, "CONFIG_DIR", root), \
                 patch.object(sys, "argv", ["build.py", "--shell-only", "--transparency", "30",
                                           "--glass-mode", "crystal", "--save-setting"]), \
                 patch.object(build, "project_theme_active", return_value=True), \
                 patch.object(managed_glass, "verify_capabilities"), \
                 patch.object(managed_glass, "read_key", return_value="'before'"), \
                 patch.object(managed_glass, "pipelines", return_value={"existing": {}}), \
                 patch.object(managed_glass, "apply") as apply, \
                 patch.object(managed_glass, "restore_snapshot") as restore, \
                 patch.object(build, "build_shell", side_effect=write_new), \
                 patch.object(build, "reload_shell_theme"), \
                 patch.object(build, "save_settings", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(RuntimeError, "Previous appearance restored"):
                    build.main()
                apply.assert_called_once_with("crystal", True, False)
                restore.assert_called_once()
                for path in paths:
                    self.assertEqual(path.read_text(), "old working CSS")


if __name__ == "__main__":
    unittest.main()
