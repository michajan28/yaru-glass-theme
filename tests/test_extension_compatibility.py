import io
import json
import os
import runpy
import sys
import subprocess
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/yaru_glass"))

import extension_compatibility as compatibility


def setUpModule():
    state = tempfile.TemporaryDirectory(prefix="yaru-extension-state-")
    unittest.addModuleCleanup(state.cleanup)
    environment = patch.dict(os.environ, {"XDG_STATE_HOME": state.name})
    environment.start()
    unittest.addModuleCleanup(environment.stop)


def schema_xml(schema_id, keys):
    key_nodes = "".join(f'<key name="{key}" type="s"/>' for key in sorted(keys))
    return f'<schemalist><schema id="{schema_id}">{key_nodes}</schema></schemalist>'


class ExtensionCompatibilityTests(unittest.TestCase):
    def test_exact_release_candidates_are_pinned_per_shell(self):
        self.assertEqual(
            compatibility.RELEASES["46"]["blur-my-shell@aunetx"],
            {"version": 77, "version_tag": "77413"},
        )
        self.assertEqual(
            compatibility.RELEASES["50"]["user-theme@gnome-shell-extensions.gcampax.github.com"],
            {"version": 79, "version_tag": "75092"},
        )
        self.assertNotIn("logomenu@aryan_k", compatibility.RELEASES["50"])
        self.assertEqual(compatibility.UBUNTU_RELEASES["50"]["packages"][
            "ubuntu-dock@ubuntu.com"
        ], ("gnome-shell-ubuntu-extensions", "50.26.04.8ubuntu"))

    def test_policy_uuid_enumeration_is_complete_and_excludes_gnome50_logo_menu(self):
        self.assertEqual(
            compatibility.policy_extension_uuids("46"),
            (
                "user-theme@gnome-shell-extensions.gcampax.github.com",
                "blur-my-shell@aunetx",
                "just-perfection-desktop@just-perfection",
                "auto-theme-switcher@amritashan.github.io",
                "logomenu@aryan_k",
                "ubuntu-dock@ubuntu.com",
                "ubuntu-appindicators@ubuntu.com",
            ),
        )
        self.assertEqual(
            compatibility.policy_extension_uuids("50"),
            (
                "user-theme@gnome-shell-extensions.gcampax.github.com",
                "blur-my-shell@aunetx",
                "just-perfection-desktop@just-perfection",
                "auto-theme-switcher@amritashan.github.io",
                "ubuntu-dock@ubuntu.com",
                "ubuntu-appindicators@ubuntu.com",
            ),
        )
        with self.assertRaisesRegex(
            compatibility.ExtensionCompatibilityError, "no exact Yaru Glass extension policy",
        ):
            compatibility.policy_extension_uuids("49")

    def test_metadata_requires_exact_uuid_version_and_shell(self):
        metadata = {
            "uuid": "blur-my-shell@aunetx",
            "version": 77,
            "shell-version": ["46", "47", "48", "49", "50", "51"],
        }
        compatibility.validate_extension_metadata(
            "blur-my-shell@aunetx", metadata, "46",
        )
        for field, value, message in (
            ("uuid", "other@example", "UUID"),
            ("version", 76, "exact version 77"),
            ("shell-version", ["50"], "does not declare GNOME Shell 46"),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(
                compatibility.ExtensionCompatibilityError, message,
            ):
                compatibility.validate_extension_metadata(
                    "blur-my-shell@aunetx", {**metadata, field: value}, "46",
                )

    def test_running_extension_api_checks_version_and_active_state(self):
        compatibility.validate_running_extension(
            "blur-my-shell@aunetx",
            {"uuid": "blur-my-shell@aunetx", "version": 77, "state": 1},
            "50",
        )
        with self.assertRaisesRegex(compatibility.ExtensionCompatibilityError, "version 77"):
            compatibility.validate_running_extension(
                "blur-my-shell@aunetx", {"version": 76}, "50",
            )
        with self.assertRaisesRegex(compatibility.ExtensionCompatibilityError, "not active"):
            compatibility.validate_running_extension(
                "blur-my-shell@aunetx", {"version": 77, "state": 2}, "50",
            )
        with self.assertRaisesRegex(compatibility.ExtensionCompatibilityError, "Logo Menu"):
            compatibility.validate_running_extension(
                "logomenu@aryan_k", {"version": 45}, "50",
            )

    def test_ubuntu_extension_requires_exact_distro_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extension = root / "system" / "ubuntu-dock@ubuntu.com"
            extension.mkdir(parents=True)
            (extension / "metadata.json").write_text(json.dumps({
                "uuid": "ubuntu-dock@ubuntu.com",
                "version": 105,
                "shell-version": ["45", "46", "47", "48", "49", "50"],
            }))
            result = subprocess.CompletedProcess(
                ["dpkg-query"], 0, "50.26.04.8ubuntu", "",
            )
            with patch.object(compatibility, "USER_EXTENSIONS", root / "user"), \
                 patch.object(compatibility, "SYSTEM_EXTENSIONS", root / "system"), \
                 patch.object(compatibility.subprocess, "run", return_value=result):
                self.assertEqual(
                    compatibility.validate_ubuntu_extension("ubuntu-dock@ubuntu.com", "50"),
                    extension,
                )
            result.stdout = "50.26.04.7ubuntu"
            with patch.object(compatibility, "USER_EXTENSIONS", root / "user"), \
                 patch.object(compatibility, "SYSTEM_EXTENSIONS", root / "system"), \
                 patch.object(compatibility.subprocess, "run", return_value=result):
                with self.assertRaisesRegex(
                    compatibility.ExtensionCompatibilityError, "exact package version",
                ):
                    compatibility.validate_ubuntu_extension("ubuntu-dock@ubuntu.com", "50")

    def test_running_ubuntu_extensions_use_exact_package_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system_extensions = root / "system"
            for uuid, version in (
                ("ubuntu-dock@ubuntu.com", 105),
                ("ubuntu-appindicators@ubuntu.com", None),
            ):
                extension = system_extensions / uuid
                extension.mkdir(parents=True)
                metadata = {
                    "uuid": uuid,
                    "shell-version": ["45", "46", "47", "48", "49", "50"],
                }
                if version is not None:
                    metadata["version"] = version
                (extension / "metadata.json").write_text(json.dumps(metadata))

            package = subprocess.CompletedProcess(
                ["dpkg-query"], 0, "50.26.04.8ubuntu", "",
            )
            with patch.object(compatibility, "USER_EXTENSIONS", root / "user"), \
                 patch.object(compatibility, "SYSTEM_EXTENSIONS", system_extensions), \
                 patch.object(compatibility.subprocess, "run", return_value=package):
                compatibility.validate_running_extension(
                    "ubuntu-dock@ubuntu.com",
                    {"uuid": "ubuntu-dock@ubuntu.com", "version": 105, "state": 1},
                    "50",
                )
                compatibility.validate_running_extension(
                    "ubuntu-appindicators@ubuntu.com",
                    {"uuid": "ubuntu-appindicators@ubuntu.com", "state": 1},
                    "50",
                )
                with self.assertRaisesRegex(
                    compatibility.ExtensionCompatibilityError, "Ubuntu policy requires 105",
                ):
                    compatibility.validate_running_extension(
                        "ubuntu-dock@ubuntu.com",
                        {"version": 104, "state": 1},
                        "50",
                    )
                with self.assertRaisesRegex(
                    compatibility.ExtensionCompatibilityError, "Ubuntu policy requires None",
                ):
                    compatibility.validate_running_extension(
                        "ubuntu-appindicators@ubuntu.com",
                        {"version": 1, "state": 1},
                        "50",
                    )
                with self.assertRaisesRegex(
                    compatibility.ExtensionCompatibilityError, "not active",
                ):
                    compatibility.validate_running_extension(
                        "ubuntu-appindicators@ubuntu.com",
                        {"state": 2},
                        "50",
                    )

    def test_exact_archive_url_and_metadata_are_checked(self):
        installer = runpy.run_path(str(ROOT / "bin/install-extensions.py"), run_name="installer_test")
        self.assertEqual(
            installer["release_url"]("blur-my-shell@aunetx", "46"),
            "https://extensions.gnome.org/download-extension/"
            "blur-my-shell@aunetx.shell-extension.zip?version_tag=77413",
        )
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("metadata.json", json.dumps({
                "uuid": "blur-my-shell@aunetx",
                "version": 77,
                "shell-version": ["46", "50"],
                "settings-schema": "org.gnome.shell.extensions.blur-my-shell",
            }))
            for schema_id, keys in compatibility.REQUIRED_SCHEMA_KEYS[
                "blur-my-shell@aunetx"
            ].items():
                package.writestr(
                    f"schemas/{schema_id}.gschema.xml", schema_xml(schema_id, keys),
                )
        archive.seek(0)
        with patch.object(installer["urllib"].request, "urlopen", return_value=archive) as urlopen:
            installer["fetch_release"]("blur-my-shell@aunetx", "46")
        self.assertIn("version_tag=77413", urlopen.call_args.args[0].full_url)

        incomplete = io.BytesIO()
        with zipfile.ZipFile(incomplete, "w") as package:
            package.writestr("metadata.json", json.dumps({
                "uuid": "blur-my-shell@aunetx",
                "version": 77,
                "shell-version": ["46"],
                "settings-schema": "org.gnome.shell.extensions.blur-my-shell",
            }))
            package.writestr(
                "schemas/root.gschema.xml",
                schema_xml("org.gnome.shell.extensions.blur-my-shell", set()),
            )
        incomplete.seek(0)
        with patch.object(installer["urllib"].request, "urlopen", return_value=incomplete):
            with self.assertRaisesRegex(
                compatibility.ExtensionCompatibilityError, "lacks required integration keys",
            ):
                installer["fetch_release"]("blur-my-shell@aunetx", "46")

    def test_mismatched_existing_extension_fails_before_download(self):
        installer = runpy.run_path(str(ROOT / "bin/install-extensions.py"), run_name="installer_test")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extension = root / "user" / "blur-my-shell@aunetx"
            extension.mkdir(parents=True)
            (extension / "metadata.json").write_text(json.dumps({
                "uuid": "blur-my-shell@aunetx",
                "version": 76,
                "shell-version": ["46", "50"],
            }))
            with patch.object(compatibility, "USER_EXTENSIONS", root / "user"), \
                 patch.object(compatibility, "SYSTEM_EXTENSIONS", root / "system"), \
                 patch.dict(installer["prepare_extensions"].__globals__, {
                     "validate_ubuntu_installs": lambda _version: None,
                     "fetch_release": Mock(),
                 }):
                fetch = installer["prepare_extensions"].__globals__["fetch_release"]
                with self.assertRaisesRegex(
                    compatibility.ExtensionCompatibilityError, "exact version 77",
                ):
                    installer["prepare_extensions"](["blur-my-shell@aunetx"], "46")
                fetch.assert_not_called()

    def test_unavailable_optional_release_is_explicitly_skipped(self):
        installer = runpy.run_path(str(ROOT / "bin/install-extensions.py"), run_name="installer_test")
        with patch.dict(installer["prepare_extensions"].__globals__, {
             "validate_ubuntu_installs": lambda _version: None,
             "installed_extension_path": lambda _uuid: None,
             "fetch_release": Mock(side_effect=urllib.error.URLError("offline")),
        }), \
             patch("builtins.print") as report:
            result = installer["prepare_extensions"](
                ["just-perfection-desktop@just-perfection"], "46",
            )
        self.assertIsNone(result["just-perfection-desktop@just-perfection"])
        self.assertIn("optional integration remains skipped", report.call_args.args[0])

    def test_install_uses_no_force_and_records_user_owned_install(self):
        installer = runpy.run_path(str(ROOT / "bin/install-extensions.py"), run_name="installer_test")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user_extensions = root / "user"
            with patch.dict(installer["install_prepared"].__globals__, {
                 "USER_EXTENSIONS": user_extensions,
                 "SYSTEM_EXTENSIONS": root / "system",
            }), \
                 patch.object(compatibility, "USER_EXTENSIONS", user_extensions), \
                 patch.object(compatibility, "SYSTEM_EXTENSIONS", root / "system"), \
                 patch.dict("os.environ", {"XDG_CACHE_HOME": str(root / "cache")}):
                def install(command, check):
                    if command[0] == "gnome-extensions":
                        extension = user_extensions / "blur-my-shell@aunetx"
                        (extension / "schemas").mkdir(parents=True)
                        (extension / "metadata.json").write_text(json.dumps({
                            "uuid": "blur-my-shell@aunetx",
                            "version": 77,
                            "shell-version": ["46", "50"],
                            "settings-schema": "org.gnome.shell.extensions.blur-my-shell",
                        }))
                        for schema_id, keys in compatibility.REQUIRED_SCHEMA_KEYS[
                            "blur-my-shell@aunetx"
                        ].items():
                            (extension / "schemas" / f"{schema_id}.gschema.xml").write_text(
                                schema_xml(schema_id, keys),
                            )

                state = root / "state" / "installed.txt"
                with patch.object(installer["subprocess"], "run", side_effect=install) as command:
                    installer["install_prepared"](
                        "blur-my-shell@aunetx", b"archive", "46", state,
                    )
            self.assertNotIn("--force", command.call_args_list[0].args[0])
            self.assertEqual(state.read_text(), "blur-my-shell@aunetx\n")
            self.assertFalse((root / "cache/yaru-glass/extensions").exists() and
                             any((root / "cache/yaru-glass/extensions").iterdir()))

    def test_installer_options_keep_extension_mutations_scoped(self):
        installer = (ROOT / "scripts/install.sh").read_text()
        self.assertIn("--no-extensions) DO_EXT=0 ;;", installer)
        self.assertIn("--theme-only) DO_PROFILE=0 DO_EXT=0 ;;", installer)
        self.assertIn('if [[ $DO_EXT -eq 1 ]]; then', installer)
        self.assertNotIn("dconf write \"$EXT_PATH/auto-theme-switcher/", installer)


if __name__ == "__main__":
    unittest.main()
