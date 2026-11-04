"""Run real lifecycle scripts only in a copied tree, private HOME and private bus."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.geteuid() == 0, "Lifecycle scripts require a normal user")
class LifecycleTests(unittest.TestCase):
    def test_install_upgrade_uninstall_and_purge_preserve_ownership(self):
        with tempfile.TemporaryDirectory(prefix="yaru-lifecycle-") as directory:
            temporary = Path(directory)
            home = temporary / "home"
            home.mkdir()
            runtime = temporary / "runtime"
            runtime.mkdir(mode=0o700)
            project = temporary / "project"
            project.mkdir()
            for name in ("README.md", "CHANGELOG.md", "AGENTS.md", "VERSION",
                         ".github", "src", "scripts", "bin", "assets", "docs", "tests"):
                source, target = ROOT / name, project / name
                if source.is_dir():
                    shutil.copytree(source, target,
                                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                else:
                    shutil.copy2(source, target)
            stub_bin = temporary / "stub-bin"
            stub_bin.mkdir()
            stubs = {
                "systemctl": 'printf "%s\\n" "$*" >> "$HOME/systemctl-calls"\n'
                             'case "$*" in *is-active*) echo active;; esac\n',
                "fc-cache": "exit 0\n",
                "fc-match": "echo 'Isolated font fixture'\n",
                "gnome-extensions": 'printf "%s\\n" "$*" >> "$HOME/extension-calls"\nexit 1\n',
            }
            for name, body in stubs.items():
                path = stub_bin / name
                path.write_text("#!/bin/sh\n" + body)
                path.chmod(0o755)
            environment = {
                "HOME": str(home), "USER": os.environ.get("USER", "yarutest"),
                "PATH": f"{stub_bin}:/usr/bin:/bin", "LANG": "C.UTF-8",
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_DATA_HOME": str(home / ".local/share"),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "XDG_RUNTIME_DIR": str(runtime),
                "XDG_DATA_DIRS": "/usr/local/share:/usr/share",
            }
            result = subprocess.run(
                ["dbus-run-session", "--", "/usr/bin/python3", str(project / "tests/test_lifecycle.py"),
                 "--fixture", str(project)],
                cwd=temporary, env=environment, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS: isolated install/upgrade/uninstall/purge", result.stdout)


def run_fixture(project):
    from gi.repository import Gio, GLib

    home = Path.home()
    if not (home.parent.name.startswith("yaru-lifecycle-") and home.name == "home"):
        raise RuntimeError("Lifecycle fixture requires its own temporary HOME")
    project = Path(project).resolve()
    if project.parent != home.parent or project.name != "project":
        raise RuntimeError("Lifecycle fixture requires a sibling copied project")
    sys.path.insert(0, str(project / "src/yaru_glass"))
    import managed_glass
    import wallpapers
    import diagnostics

    def run(*args, expected_status=0):
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        if result.returncode != expected_status:
            raise AssertionError(f"{args}: {result.stdout}\n{result.stderr}")
        return result.stdout

    def check(condition, message):
        if not condition:
            raise AssertionError(message)

    def dconf(*args):
        return run("dconf", *args).strip()

    interface = Gio.Settings.new("org.gnome.desktop.interface")
    interface.set_string("gtk-theme", "Yaru")
    interface.set_string("font-name", "Fixture Font 11")
    Gio.Settings.sync()
    original_gtk = home / ".config/gtk-4.0/gtk.css"
    original_gtk.parent.mkdir(parents=True)
    original_gtk.write_text("/* original isolated user CSS */\n")
    original_css = original_gtk.read_bytes()
    # Legacy extension records must remain restorable after integration retirement.
    dconf("write", "/org/gnome/shell/extensions/search-light/fixture", "'original'")
    dconf("write", "/org/gnome/shell/extensions/blur-my-shell/panel/blur", "true")
    dconf("write", "/org/gnome/shell/extensions/blur-my-shell/pipelines",
          "{'unrelated_pipeline': {'name': <'Keep this pipeline'>}}")
    dest = home / ".local/share/yaru-glass"
    installer = project / "scripts/install.sh"
    args = ("--no-apt", "--no-extensions", "--theme-only", "--yes")
    output = run("bash", str(installer), *args, expected_status=1)
    check("Blur my Shell must be enabled" in output,
          "Private session should report unavailable managed integration")
    check("✔ Yaru Glass installed" not in output,
          "Unavailable integration was reported as a complete installation")
    check((home / ".local/bin/yaru-glass-logs").is_symlink(), "Diagnostic launcher missing")
    first_logs = diagnostics.read_records(2000)["records"]
    first_install = [r for r in first_logs if r["component"] == "install"]
    check(first_install[0]["phase"] == "start" and first_install[-1]["phase"] == "failure",
          "Installer exit was not logged truthfully")
    operation = first_install[0]["operation"]
    check({r["operation"] for r in first_install} == {operation},
          "Install stage correlation was lost")
    check(any(r["component"] == "worker" and r["operation"] == operation for r in first_logs),
          "Installer did not propagate operation to worker")
    check(original_gtk.is_symlink(), "Installed GTK4 overrides not linked")
    backup = dest / "backup/original"
    original_keys = (backup / "keys.tsv").read_bytes()
    check(b"Fixture Font 11" in original_keys, "First-install settings not backed up")
    config = home / ".config/yaru-glass"
    config.mkdir(exist_ok=True)
    preferences = {
        "settings.json": {"transparency": 37, "glass_mode": "crystal",
                          "solid": False, "readability_boost": True},
        "app-appearance.json": {"enabled": True, "transparency": 19},
        "files-appearance.json": {"enabled": False, "transparency": 41},
    }
    for name, data in preferences.items():
        (config / name).write_text(json.dumps(data, indent=2) + "\n")
    preference_bytes = {name: (config / name).read_bytes() for name in preferences}
    (backup / "search-light.ini").write_text("[/]\nfixture='original'\n")
    stale_profile = dest / "assets/profiles/search-light.ini"
    stale_profile.write_text("[/]\nfixture='retired'\n")
    extensions = home / ".local/share/gnome-shell/extensions"
    owned = extensions / "owned-fixture@example"
    unrelated = extensions / "unrelated-fixture@example"
    for directory in (owned, unrelated):
        directory.mkdir(parents=True)
        (directory / "marker").write_text("fixture\n")
    state = dest / "state/installed-extensions.txt"
    state.parent.mkdir()
    state.write_text("owned-fixture@example\nsearch-light@icedman.github.com\n")
    # The private bus has no running Shell/extensions. Build against real system
    # resources with a non-project theme; managed-effect restoration is tested below.
    interface.set_string("gtk-theme", "Yaru")
    Gio.Settings.sync()
    output = run("bash", str(installer), *args, expected_status=1)
    check("Blur my Shell must be enabled" in output,
          "Private session should report unavailable managed integration on upgrade")
    check("keeping the original backup" in output, "Upgrade replaced original backup")
    check((backup / "keys.tsv").read_bytes() == original_keys, "Backup bytes changed")
    check(not stale_profile.exists(), "Retired profile survived upgrade")
    check((backup / "search-light.ini").exists(), "Legacy restoration record lost")
    check(state.read_text().endswith("search-light@icedman.github.com\n"), "Ownership state lost")
    for name, expected in preference_bytes.items():
        check((config / name).read_bytes() == expected, f"Upgrade changed {name}")
    check(any(r["operation"] == operation for r in diagnostics.read_records(2000)["records"]),
          "Upgrade deleted earlier diagnostic records")
    exported = home / "my-diagnostic-report.json"
    diagnostics.export_report(exported)
    # A minimal private schema allows the real restore path without loading an
    # extension or depending on the host user's extension installation.
    schemas = extensions / managed_glass.UUID / "schemas"
    schemas.mkdir(parents=True)
    (schemas / "fixture.gschema.xml").write_text(
        '<schemalist><schema id="org.gnome.shell.extensions.blur-my-shell" '
        'path="/org/gnome/shell/extensions/blur-my-shell/">'
        '<key name="pipelines" type="a{sa{sv}}"><default>{}</default></key>'
        '</schema></schemalist>')
    run("glib-compile-schemas", str(schemas))
    managed_glass.write_pipelines({
        "pipeline_yaru_glass_crystal_panel": {"name": "owned"},
        "unrelated_pipeline": {"name": "Keep this pipeline"},
    })
    original_effects = {key: None for key in managed_glass.desired_keys("crystal")}
    original_effects["panel/blur"] = "true"
    managed_glass.BACKUP.write_text(json.dumps({"keys": original_effects, "pipelines": {}}))
    managed_glass.write_key("panel/blur", "false")
    background = Gio.Settings.new("org.gnome.desktop.background")
    background.set_string("picture-uri", "file:///fixture-managed-light.png")
    background.set_string("picture-uri-dark", "file:///fixture-external-dark.png")
    Gio.Settings.sync()
    wallpapers.BACKUP.write_text(json.dumps({
        "picture-uri": {"original": "'file:///fixture-original-light.png'",
                        "last": "file:///fixture-managed-light.png"},
        "picture-uri-dark": {"original": "'file:///fixture-original-dark.png'",
                             "last": "file:///fixture-managed-dark.png"},
    }))
    dconf("write", "/org/gnome/shell/extensions/search-light/fixture", "'changed'")
    run("bash", str(dest / "scripts/uninstall.sh"))
    check(dest.exists() and state.exists(), "Normal uninstall deleted installed files/state")
    check((diagnostics.directory() / "events.jsonl").exists(), "Normal uninstall deleted diagnostics")
    check(any(r["component"] == "uninstall" and r["phase"] == "success"
              for r in diagnostics.read_records(2000)["records"]),
          "Normal uninstall outcome missing")
    check(owned.exists() and unrelated.exists(), "Normal uninstall removed extensions")
    check(original_gtk.read_bytes() == original_css and not original_gtk.is_symlink(),
          "Original GTK4 CSS not restored")
    check(dconf("read", "/org/gnome/desktop/interface/gtk-theme") == "'Yaru'",
          "Original theme not restored")
    check(dconf("read", "/org/gnome/desktop/interface/font-name") == "'Fixture Font 11'",
          "Original font not restored")
    check(dconf("read", "/org/gnome/shell/extensions/search-light/fixture") == "'original'",
          "Legacy Search Light profile not restored")
    check(managed_glass.read_key("panel/blur") == "true", "Original blur flag not restored")
    check(managed_glass.pipelines() == {"unrelated_pipeline": {"name": "Keep this pipeline"}},
          "Managed pipelines not removed or unrelated pipeline lost")
    check(dconf("read", "/org/gnome/desktop/background/picture-uri") ==
          "'file:///fixture-original-light.png'",
          "Owned wallpaper not restored")
    check(dconf("read", "/org/gnome/desktop/background/picture-uri-dark") ==
          "'file:///fixture-external-dark.png'",
          "External wallpaper choice overwritten")
    for name, expected in preference_bytes.items():
        check((config / name).read_bytes() == expected, f"Uninstall deleted/changed {name}")
    check(not managed_glass.BACKUP.exists() and not wallpapers.BACKUP.exists(),
          "Restoration records were not cleared")
    run("bash", str(dest / "scripts/uninstall.sh"), "--purge", "--remove-extensions")
    check(not dest.exists(), "Purge retained installed payload")
    check(exported.exists(), "Purge deleted user-exported diagnostic report")
    check({p.name for p in diagnostics.directory().iterdir()} == {"diagnostics.lock"},
          "Purge retained diagnostics beyond the coordination inode")
    for name in ("Yaru-Glass", "Yaru-Glass-dark"):
        check(not (home / ".local/share/themes" / name).exists(), "Purge retained generated theme")
    check(not owned.exists() and unrelated.exists(), "Extension ownership boundary violated")
    for relative in (".local/share/fonts/Inter", ".local/bin/yaru-glass-sync",
                     ".local/bin/yaru-glass-settings",
                     ".local/bin/yaru-glass-logs",
                     ".local/share/applications/org.yaru.glass.Settings.desktop",
                     ".config/systemd/user/yaru-glass-sync.service"):
        path = home / relative
        check(not path.exists() and not path.is_symlink(), f"Purge retained {relative}")
    for name in preferences:
        check(not (config / name).exists(), f"Purge retained {name}")
    check(original_gtk.read_bytes() == original_css, "Purge deleted original GTK4 CSS")
    retained = list((home / ".local/share").glob("yaru-glass-backup-*"))
    check(len(retained) == 1, "Purge did not retain one original-backup copy")
    check((retained[0] / "original/keys.tsv").read_bytes() == original_keys,
          "Purge changed original backup bytes")
    check(project.exists(), "Lifecycle validation deleted copied source checkout")
    calls = (home / "systemctl-calls").read_text()
    check("--user disable --now yaru-glass-sync.service" in calls, "Uninstall did not stop sync")
    print("PASS: isolated install/upgrade/uninstall/purge; preferences, backups, "
          "managed effects, conditional wallpapers and extension ownership verified")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fixture":
        run_fixture(sys.argv[2])
    else:
        unittest.main()
