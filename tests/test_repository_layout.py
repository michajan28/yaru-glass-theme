import os
import runpy
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def setUpModule():
    state = tempfile.TemporaryDirectory(prefix="yaru-layout-state-")
    unittest.addModuleCleanup(state.cleanup)
    environment = patch.dict(os.environ, {"XDG_STATE_HOME": state.name})
    environment.start()
    unittest.addModuleCleanup(environment.stop)


class RepositoryLayoutTests(unittest.TestCase):
    def test_project_identity_is_consistent(self):
        for relative in ("src/yaru_glass/theme_settings.py",
                         "src/theme/gtk-3.0/glass.css",
                         "src/theme/gnome-shell/glass.css.in",
                         "bin/yaru-glass-settings", "bin/yaru-glass-sync"):
            self.assertTrue((ROOT / relative).is_file(), relative)
        installer = (ROOT / "scripts/install.sh").read_text()
        for identifier in ("Yaru Glass Settings", "Yaru-Glass", "Yaru-Glass-dark",
                           "yaru-glass-sync.service", "org.yaru.glass.Settings.desktop"):
            self.assertIn(identifier, installer)
        settings = runpy.run_path(str(ROOT / "src/yaru_glass/theme_settings.py"))
        self.assertEqual(settings["CONFIG_DIR"].name, "yaru-glass")

    @unittest.skipIf(os.geteuid() == 0, "Installer preflight rejects root")
    def test_installer_omits_logo_menu_only_on_gnome_50(self):
        installer = (ROOT / "scripts/install.sh").read_text()
        preflight = installer.split("# ---------------------------------------------------------------- packages", 1)[0]
        profiles = installer.split('  for f in "$DEST"/assets/profiles/*.ini; do', 1)[1]
        profiles = 'for f in "$DEST"/assets/profiles/*.ini; do' + profiles.split("  done", 1)[0] + "done\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "src").mkdir()
            (root / "bin").mkdir()
            shutil.copytree(ROOT / "src/yaru_glass", root / "src/yaru_glass")
            shutil.copy2(ROOT / "bin/yaru-glass-logs", root / "bin/yaru-glass-logs")
            shutil.copy2(ROOT / "VERSION", root / "VERSION")
            home = root / "home"
            for uuid in ("logomenu@aryan_k", "just-perfection-desktop@just-perfection"):
                metadata = home / ".local/share/gnome-shell/extensions" / uuid / "metadata.json"
                metadata.parent.mkdir(parents=True)
                metadata.write_text("{}")
            stub = root / "gnome-shell"
            dconf = root / "dconf"
            dconf.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n")
            dconf.chmod(0o755)
            for name in ("Logo-menu", "just-perfection"):
                path = root / "assets/profiles" / f"{name}.ini"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("[/]\\n")
            for version in ("46", "50"):
                with self.subTest(version=version):
                    stub.write_text(f"#!/bin/sh\necho 'GNOME Shell {version}'\n")
                    stub.chmod(0o755)
                    script = root / "scripts/preflight.sh"
                    script.write_text(preflight + '\nprintf "EXTENSION:%s\\n" "${EXTENSIONS[@]}"\n'
                                      f'DEST="{root}"\n' + profiles)
                    result = subprocess.run(
                        ["bash", str(script), "--no-apt", "--yes"],
                        env={**os.environ, "PATH": f"{root}:/usr/bin:/bin", "HOME": str(home),
                             "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent"},
                        check=True, capture_output=True, text=True,
                    )
                    self.assertEqual("EXTENSION:logomenu@aryan_k" in result.stdout, version == "46")
                    self.assertEqual("load /org/gnome/shell/extensions/Logo-menu/" in result.stdout,
                                     version == "46")
                    self.assertIn("load /org/gnome/shell/extensions/just-perfection/", result.stdout)

    def test_extension_installer_uses_exact_release_tags(self):
        helper = runpy.run_path(str(ROOT / "bin/install-extensions.py"), run_name="extension_test")
        self.assertIn("version_tag=61748", helper["release_url"](
            "user-theme@gnome-shell-extensions.gcampax.github.com", "46",
        ))
        self.assertIn("version_tag=75092", helper["release_url"](
            "user-theme@gnome-shell-extensions.gcampax.github.com", "50",
        ))
        with self.assertRaisesRegex(ValueError, "no exact Yaru Glass release"):
            helper["release_url"]("user-theme@gnome-shell-extensions.gcampax.github.com", "47")

    def test_search_light_is_not_installed_exported_or_synchronized(self):
        installer = (ROOT / "scripts/install.sh").read_text()
        sync = (ROOT / "bin/yaru-glass-sync").read_text()
        exporter = (ROOT / "scripts/export-profile.py").read_text()
        self.assertNotIn("search-light@icedman.github.com", installer)
        self.assertNotIn("search-light", sync)
        self.assertNotIn("search-light", exporter)
        self.assertFalse((ROOT / "assets/profiles/search-light.ini").exists())
        self.assertNotIn("imagemagick", installer)
        self.assertNotIn("gsettings set org.gnome.desktop.wm.keybindings", installer)
        self.assertIn('rm -f "$DEST/assets/profiles/search-light.ini"', installer)
        self.assertNotIn('rm -f "$ORIG/', installer)

    def test_package_is_self_contained_and_excludes_local_files(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            project = temporary / "project"
            project.mkdir()
            for name in ("README.md", "CHANGELOG.md", "AGENTS.md", "VERSION", ".github/skills",
                         "src", "scripts", "bin", "assets", "docs", "demo", "tests"):
                source = ROOT / name
                target = project / name
                if source.is_dir():
                    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
                else:
                    shutil.copy2(source, target)
            for name in (".git", "dist", "backup", "state", "src/__pycache__", "docs/.git"):
                target = project / name
                target.mkdir(parents=True, exist_ok=True)
                (target / "private-marker").write_text("must not ship")
            (project / "src/stale.pyc").write_bytes(b"not source")
            stub_bin = temporary / "stub-bin"
            stub_bin.mkdir()
            dconf = stub_bin / "dconf"
            dconf.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$DCONF_LOG\"\nprintf '[/]\\nfixture=true\\n'\n")
            dconf.chmod(0o755)
            home = temporary / "home"
            home.mkdir()
            environment = {
                **os.environ,
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_DATA_HOME": str(home / ".local/share"),
                "PATH": f"{stub_bin}:/usr/bin:/bin",
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
                "DCONF_LOG": str(temporary / "dconf.log"),
            }
            version = (project / "VERSION").read_text().strip()
            package_name = f"yaru-glass-theme-{version}"
            for curated, output in ((True, temporary / "curated-output"),
                                    (False, None), (False, temporary / "custom-output")):
                with self.subTest(output=output):
                    profiles_before = {path.name: path.read_bytes()
                                       for path in (project / "assets/profiles").glob("*.ini")}
                    command = ["bash", str(project / "scripts/make-package.sh")]
                    if curated:
                        command.append("--curated-profiles")
                    if output is not None:
                        command.append(str(output))
                    subprocess.run(command, cwd=temporary, env=environment, check=True,
                                   capture_output=True, text=True)
                    output_dir = output or project / "dist/releases"
                    archive = output_dir / f"{package_name}.tar.gz"
                    if curated:
                        self.assertFalse((temporary / "dconf.log").exists())
                        self.assertEqual(profiles_before, {path.name: path.read_bytes()
                                         for path in (project / "assets/profiles").glob("*.ini")})
                    original_archive = archive.read_bytes()
                    rejected = subprocess.run(command, cwd=temporary, env=environment,
                                              capture_output=True, text=True)
                    self.assertNotEqual(rejected.returncode, 0)
                    self.assertIn("Refusing to overwrite", rejected.stderr)
                    self.assertEqual(archive.read_bytes(), original_archive)
                    subprocess.run(["sha256sum", "-c", f"{archive.name}.sha256"],
                                   cwd=output_dir, check=True, capture_output=True, text=True)
                    with tarfile.open(archive) as package:
                        names = package.getnames()
                        for name in names:
                            parts = Path(name).parts
                            self.assertFalse(set(parts) & {".git", "dist", "backup", "state", "__pycache__"})
                            self.assertFalse(name.endswith((".pyc", ".pyo")))
                        for name in ("CHANGELOG.md", "AGENTS.md", ".github/skills/yaru-release/SKILL.md",
                                     "scripts/install.sh", "scripts/uninstall.sh", "scripts/build.py",
                                     "bin/yaru-glass-settings", "bin/yaru-glass-sync", "bin/yaru-glass-logs",
                                     "src/yaru_glass/diagnostics.py", "src/yaru_glass/diagnostics_ui.py",
                                     "src/yaru_glass/theme_settings.py", "src/theme/gnome-shell/glass.css.in",
                                     "assets/fonts/Inter/InterVariable.ttf", "assets/fonts/Inter/LICENSE.txt",
                                     "assets/profiles/blur-my-shell.ini", "docs/MANUAL.md",
                                     "demo/index.html", "demo/desktop-view.html",
                                     "demo/login-view.html",
                                     "demo/demo-assets/desktop/desktop.js",
                                     "demo/demo-assets/lockscreen/alpine.jpg"):
                            self.assertIn(f"{package_name}/{name}", names)
                        self.assertTrue(package.getmember(f"{package_name}/scripts/install.sh").mode & 0o111)
                        self.assertTrue(package.getmember(f"{package_name}/bin/yaru-glass-logs").mode & 0o111)
                        if curated:
                            for name, content in profiles_before.items():
                                self.assertEqual(package.extractfile(
                                    f"{package_name}/assets/profiles/{name}").read(), content)
                        unpacked = temporary / ("curated-unpacked" if curated else
                                                "custom-unpacked" if output else "default-unpacked")
                        package.extractall(unpacked, filter="data")
                    subprocess.run(["/usr/bin/python3", str(unpacked / package_name / "scripts/build.py"),
                                    "--help"], cwd=temporary, env=environment, check=True,
                                   capture_output=True, text=True)
                    subprocess.run(["/usr/bin/python3", str(unpacked / package_name / "bin/yaru-glass-logs"),
                                    "--help"], cwd=temporary, env=environment, check=True,
                                   capture_output=True, text=True)

    def test_native_dock_uses_dominant_color_dashes_without_css_dot_override(self):
        profile = (ROOT / "assets/profiles/dash-to-dock.ini").read_text()
        self.assertIn("running-indicator-style='DASHES'", profile)
        self.assertIn("running-indicator-dominant-color=true", profile)
        self.assertIn("custom-theme-customize-running-dots=false", profile)
        template = (ROOT / "src/theme/gnome-shell/glass.css.in").read_text()
        self.assertNotIn(".app-grid-running-dot", template)

    def test_app_grid_tiles_have_clear_interaction_states(self):
        template = (ROOT / "src/theme/gnome-shell/glass.css.in").read_text()
        self.assertIn(".overview-tile:hover", template)
        self.assertIn(".overview-tile:focus", template)
        self.assertIn("box-shadow: inset 0 0 0 2px ${accent};", template)
        self.assertIn(".overview-tile:active", template)
        self.assertIn(".overview-icon.overview-icon-with-label > StBoxLayout", template)

    @unittest.skipIf(os.geteuid() == 0, "The uninstaller rejects root before checking its source path")
    def test_purge_refuses_to_delete_the_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            scripts = temporary / "checkout/scripts"
            scripts.mkdir(parents=True)
            uninstaller = scripts / "uninstall.sh"
            shutil.copy2(ROOT / "scripts/uninstall.sh", uninstaller)
            result = subprocess.run(["bash", str(uninstaller), "--purge"],
                                    env={**os.environ, "HOME": str(temporary / "home")},
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not the source checkout", result.stdout)
            self.assertTrue(uninstaller.exists())


if __name__ == "__main__":
    unittest.main()
