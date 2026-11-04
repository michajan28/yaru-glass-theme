import os
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def setUpModule():
    state = tempfile.TemporaryDirectory(prefix="yaru-extension-enable-state-")
    unittest.addModuleCleanup(state.cleanup)
    environment = patch.dict(os.environ, {"XDG_STATE_HOME": state.name})
    environment.start()
    unittest.addModuleCleanup(environment.stop)


class Variant:
    def __init__(self, _signature, value):
        self.value = value

    def unpack(self):
        return self.value


class FakeSettings:
    def __init__(self, enabled=(), disabled=(), globally_disabled=False):
        self.values = {
            "enabled-extensions": list(enabled),
            "disabled-extensions": list(disabled),
            "disable-user-extensions": globally_disabled,
        }
        self.writes = []

    def get_strv(self, key):
        return list(self.values[key])

    def get_boolean(self, key):
        return self.values[key]

    def set_strv(self, key, value):
        self.writes.append((key, list(value)))
        self.values[key] = list(value)
        return True

    def set_boolean(self, key, value):
        self.writes.append((key, value))
        self.values[key] = value
        return True


class ExtensionEnableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gio = types.SimpleNamespace(
            Settings=types.SimpleNamespace(sync=lambda: None),
            DBusCallFlags=types.SimpleNamespace(NONE=0),
            BusType=types.SimpleNamespace(SESSION=0),
            bus_get_sync=lambda *_args: None,
        )
        glib = types.SimpleNamespace(
            Error=type("FakeGLibError", (Exception,), {}),
            Variant=Variant,
            VariantType=lambda signature: signature,
        )
        repository = types.ModuleType("gi.repository")
        repository.Gio = gio
        repository.GLib = glib
        gi = types.ModuleType("gi")
        gi.repository = repository
        with patch.dict(sys.modules, {"gi": gi, "gi.repository": repository}):
            cls.helper = runpy.run_path(
                str(ROOT / "bin/enable-extension.py"), run_name="enable_extension_test",
            )
        cls.gio = gio
        cls.glib = glib

    def test_batch_enable_uses_one_enabled_list_update_and_preserves_unrelated_values(self):
        settings = FakeSettings(
            enabled=("existing@example",),
            disabled=("blur-my-shell@aunetx", "other@example"),
            globally_disabled=True,
        )
        self.helper["request_enable"](
            settings,
            ("blur-my-shell@aunetx", "logomenu@aryan_k", "blur-my-shell@aunetx"),
        )
        self.assertEqual(
            settings.writes,
            [
                ("disabled-extensions", ["other@example"]),
                ("enabled-extensions", [
                    "existing@example", "blur-my-shell@aunetx", "logomenu@aryan_k",
                ]),
                ("disable-user-extensions", False),
            ],
        )

    def test_activation_wait_reports_active_and_pending_separately(self):
        class Connection:
            def __init__(self, states):
                self.states = states
                self.calls = []

            def call_sync(self, *args):
                uuid = args[4].unpack()[0]
                self.calls.append(uuid)
                return Variant("(a{sv})", ({"state": Variant("u", self.states[uuid])},))

        connection = Connection({"active@example": 1})
        active, pending = self.helper["wait_for_activation"](
            ["active@example"], timeout=0.01, interval=0.001, connection=connection,
        )
        self.assertEqual(active, ["active@example"])
        self.assertEqual(pending, [])
        self.assertEqual(connection.calls, ["active@example"])

        connection = Connection({"pending@example": 2})
        active, pending = self.helper["wait_for_activation"](
            ["pending@example"], timeout=0, connection=connection,
        )
        self.assertEqual(active, [])
        self.assertEqual(pending, ["pending@example"])

    def test_shell_activation_error_is_not_mislabeled_as_relogin_pending(self):
        class Connection:
            def call_sync(self, *args):
                return Variant("(a{sv})", ({
                    "state": Variant("u", 3),
                    "error": Variant("s", "status role conflict"),
                },))

        with self.assertRaisesRegex(ValueError, "activation failed.*status role conflict"):
            self.helper["wait_for_activation"](
                ["broken@example"], timeout=0.1, connection=Connection(),
            )

    def test_installer_uses_only_one_enable_request_path(self):
        installer = (ROOT / "scripts/install.sh").read_text()
        self.assertNotIn("gnome-extensions enable", installer)
        self.assertEqual(installer.count('"$DEST/bin/enable-extension.py"'), 1)
        self.assertIn('if [[ $activation_status -eq 2 ]]; then', installer)
        self.assertIn("ACTIVATION_RELOGIN=1", installer)
        self.assertIn("after_count > before_count || ACTIVATION_RELOGIN", installer)


if __name__ == "__main__":
    unittest.main()
