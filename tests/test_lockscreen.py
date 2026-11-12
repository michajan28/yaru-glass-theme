"""Independent extension packaging, preferences and native allocation checks."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src/gnome-shell-extension"
sys.path.insert(0, str(ROOT / "src/yaru_glass"))
import companion_extension as companion
from extension_compatibility import ExtensionCompatibilityError


class LockScreenTests(unittest.TestCase):
    def test_metadata_keeps_gdm_out_of_scope(self):
        metadata = companion.validate_tree(EXTENSION)
        self.assertEqual(metadata["session-modes"], ["user", "unlock-dialog"])
        self.assertEqual(metadata["shell-version"], ["46", "50"])

    def test_independent_zip_and_preferences_without_theme_app(self):
        if not shutil.which("gnome-extensions") or not shutil.which("gjs"):
            self.skipTest("GNOME extension tooling and GJS are required")
        with tempfile.TemporaryDirectory(prefix="yaru-independent-") as directory:
            temporary = Path(directory)
            archive = companion.build(temporary)
            companion.validate_archive(archive)
            with self.assertRaisesRegex(ExtensionCompatibilityError, "overwrite"):
                companion.build(temporary)
            extension = temporary / "extension"
            with zipfile.ZipFile(archive) as package:
                package.extractall(extension)
            self.assertTrue((extension / "prefs.js").is_file())
            self.assertFalse((extension / "src/yaru_glass").exists())
            schemas = extension / "schemas"
            subprocess.run(["glib-compile-schemas", "--strict", str(schemas)], check=True,
                           capture_output=True, text=True)
            result = subprocess.run(
                ["gjs", "-m", str(ROOT / "tests/check_lockscreen_preferences.js"),
                 str(extension), str(temporary)],
                env={**os.environ, "GSETTINGS_SCHEMA_DIR": str(schemas),
                     "GSETTINGS_BACKEND": "memory"},
                capture_output=True, text=True, timeout=40)
            if any(message in result.stderr.lower()
                   for message in ("cannot open display", "failed to open display")):
                self.skipTest("GTK display required for Preferences")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-4000:])
            self.assertIn("PASS: independent Preferences", result.stdout)

    def test_installer_retains_compatible_copy_and_rejects_collisions(self):
        with tempfile.TemporaryDirectory(prefix="yaru-companion-") as directory:
            home = Path(directory)
            target = home / ".local/share/gnome-shell/extensions" / companion.UUID
            with patch.object(Path, "home", return_value=home):
                target.parent.mkdir(parents=True)
                target.symlink_to(EXTENSION, target_is_directory=True)
                with self.assertRaisesRegex(ExtensionCompatibilityError, "symlink"):
                    companion.installed("50")
                target.unlink()
                shutil.copytree(EXTENSION, target)
                subprocess.run(["glib-compile-schemas", "--strict", str(target / "schemas")],
                               check=True, capture_output=True, text=True)
                with patch.object(companion, "build") as build:
                    companion.install("50", home / "ownership")
                    build.assert_not_called()
                self.assertFalse((home / "ownership").exists())
                compiled = target / "schemas/gschemas.compiled"
                saved = home / "compiled"
                compiled.rename(saved)
                compiled.symlink_to(saved)
                with self.assertRaisesRegex(ExtensionCompatibilityError, "symlink"):
                    companion.installed("50")
                compiled.unlink()
                saved.rename(compiled)
                path = target / "metadata.json"
                value = json.loads(path.read_text())
                value["uuid"] = "unrelated@fixture"
                path.write_text(json.dumps(value))
                with self.assertRaisesRegex(ExtensionCompatibilityError, "incompatible"):
                    companion.install("50", home / "ownership")
                self.assertEqual(json.loads(path.read_text())["uuid"], "unrelated@fixture")

    def test_normal_extension_helper_installs_local_companion_without_enabling(self):
        with tempfile.TemporaryDirectory(prefix="yaru-companion-install-") as directory:
            home = Path(directory)
            script = f"""
import os, runpy, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, {str(ROOT / "src/yaru_glass")!r})
import companion_extension as companion
from gi.repository import Gio
shell = Gio.Settings.new("org.gnome.shell")
shell.set_strv("enabled-extensions", ["keep@fixture"])
shell.set_boolean("disable-user-extensions", True)
Gio.Settings.sync()
state = Path.home() / "installed-extensions.txt"
ui = runpy.run_path({str(ROOT / "bin/install-extensions.py")!r}, run_name="installer_test")
sys.argv = ["install-extensions.py", str(state), companion.UUID]
with patch.dict(ui["main"].__wrapped__.__globals__, {{
    "running_shell_version": lambda: "50",
    "validate_ubuntu_installs": lambda shell: None,
    "fetch_release": lambda *args: (_ for _ in ()).throw(AssertionError("Remote fetch")),
}}):
    ui["main"]()
assert state.read_text() == companion.UUID + "\\n"
assert shell.get_strv("enabled-extensions") == ["keep@fixture"]
assert shell.get_boolean("disable-user-extensions")
root = companion.installed("50")
source = Gio.SettingsSchemaSource.new_from_directory(str(root / "schemas"),
    Gio.SettingsSchemaSource.get_default(), False)
value = Gio.Settings.new_full(source.lookup(companion.SCHEMA, False), None, None)
assert not value.get_boolean("enabled")
before = (root / "prefs.js").read_bytes()
with patch.object(companion, "build", side_effect=AssertionError("Replaced existing copy")):
    companion.install("50", state)
assert state.read_text() == companion.UUID + "\\n"
assert (root / "prefs.js").read_bytes() == before
"""
            result = subprocess.run(
                ["dbus-run-session", "--", "/usr/bin/python3", "-c", script],
                env={**os.environ, "HOME": str(home), "XDG_DATA_HOME": str(home / ".local/share"),
                     "XDG_CONFIG_HOME": str(home / "config"), "XDG_STATE_HOME": str(home / "state"),
                     "XDG_CACHE_HOME": str(home / "cache"), "GSETTINGS_BACKEND": "memory"},
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-4000:])

    def test_native_clock_layout_preserves_authentication_allocation(self):
        typelib = next(iter(sorted(Path("/usr/lib/gnome-shell").glob("St-*.typelib"))), None)
        mutter = typelib and Path("/usr/lib/x86_64-linux-gnu") / f"mutter-{typelib.stem.split('-')[1]}"
        if not typelib or not mutter.is_dir() or not shutil.which("gjs"):
            self.skipTest("GNOME Shell St/Mutter and GJS required")
        with tempfile.TemporaryDirectory(prefix="yaru-lock-layout-") as directory:
            libraries = f"/usr/lib/gnome-shell:{mutter}"
            environment = {key: value for key, value in os.environ.items()
                           if key not in {"DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY", "DISPLAY"}}
            environment.update({"GI_TYPELIB_PATH": libraries, "LD_LIBRARY_PATH": libraries,
                                "XDG_RUNTIME_DIR": directory})
            result = subprocess.run(
                ["dbus-run-session", "--", "gjs", "-m",
                 str(ROOT / "tests/check_lockscreen_layout.js"), str(EXTENSION / "stylesheet.css")],
                env=environment, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-4000:])
            self.assertIn("36 native lock-screen layout cases passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
