"""Updater contracts and transactions use private files and mocked desktop/network IO."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/yaru_glass"))
import operation_lock
import updates
import update_transaction as transaction


def release_data(text="2.3.0"):
    name = f"yaru-glass-theme-{text}.tar.gz"
    return {"draft": False, "prerelease": False, "tag_name": "v" + text,
            "html_url": f"https://github.com/{updates.REPOSITORY}/releases/tag/v{text}",
            "assets": [{"name": filename, "size": size,
                        "browser_download_url": f"https://github.com/{updates.REPOSITORY}/releases/"
                                                f"download/v{text}/{filename}"}
                       for filename, size in ((name, 100), (name + ".sha256", 96))]}


class ReleaseTests(unittest.TestCase):
    def test_numeric_comparison_and_cli_shape(self):
        for installed, latest, status in (("2.2.4", "2.3.0", "available"),
                                           ("2.3.0", "2.3.0", "up-to-date"),
                                           ("2.10.0", "2.9.9", "up-to-date")):
            with self.subTest(installed=installed, latest=latest), patch.object(
                    updates, "download", return_value=json.dumps(release_data(latest)).encode()):
                _, result = updates.check(installed)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["installed_version"], installed)
                self.assertEqual(result["available_version"], latest)
        for value in ("dev", "v2.3.0", "2.3", "2.3.0-beta", "02.3.0", None):
            with self.subTest(value=value), self.assertRaises(updates.UpdateError):
                updates.version(value)

    def test_invalid_release_metadata_never_looks_up_to_date(self):
        cases = []
        for field, value in (("draft", True), ("prerelease", True), ("draft", None),
                             ("tag_name", "v2.3.0-rc1"), ("html_url", "https://example.com"),
                             ("assets", []), ("assets", None)):
            data = release_data()
            data[field] = value
            cases.append(data)
        for field, value in (("size", -1), ("size", updates.MAX_ARCHIVE + 1),
                             ("browser_download_url", "http://github.com/unsafe"),
                             ("digest", "sha256:bad")):
            data = release_data()
            data["assets"][0][field] = value
            cases.append(data)
        data = release_data()
        data["assets"].append(copy.deepcopy(data["assets"][0]))
        cases += [data, [], None, {"draft": False, "prerelease": False}]
        for data in cases:
            with self.subTest(data=data), patch.object(
                    updates, "download", return_value=json.dumps(data).encode()):
                with self.assertRaises(updates.UpdateError):
                    updates.check("2.2.4")
        with patch.object(updates, "download", side_effect=updates.UpdateError("offline")):
            with self.assertRaisesRegex(updates.UpdateError, "offline"):
                updates.check("2.2.4")

    def test_download_url_and_redirect_policy(self):
        for url in ("http://github.com/x", "https://example.com/x", "https://github.com.evil/x",
                    "https://user:password@github.com/x", "https://github.com:444/x",
                    "file:///tmp/archive"):
            with self.subTest(url=url), self.assertRaises(updates.UpdateError):
                updates.checked_url(url)
        self.assertEqual(updates.checked_url(updates.API), updates.API)
        for host in ("release-assets.githubusercontent.com", "objects.githubusercontent.com"):
            self.assertEqual(updates.checked_url(f"https://{host}/a"), f"https://{host}/a")
        with self.assertRaises(updates.UpdateError):
            updates.Redirects().redirect_request(None, None, 302, "", {}, "https://example.com")

    def test_network_limits_and_errors(self):
        class Response(io.BytesIO):
            headers = {}
            def geturl(self):
                return updates.API
        response = Response(b"12345")
        with patch("urllib.request.OpenerDirector.open", return_value=response):
            with self.assertRaisesRegex(updates.UpdateError, "size or time"):
                updates.download(updates.API, 4)
        response = Response(b"12345")
        response.headers = {"Content-Length": "10"}
        with patch("urllib.request.OpenerDirector.open", return_value=response):
            with self.assertRaisesRegex(updates.UpdateError, "Incomplete"):
                updates.download(updates.API, 100)
        import urllib.error
        for error in (urllib.error.URLError("offline"), TimeoutError(),
                      urllib.error.HTTPError(updates.API, 403, "rate limited", {}, None)):
            with patch("urllib.request.OpenerDirector.open", side_effect=error):
                with self.assertRaises(updates.UpdateError):
                    updates.download(updates.API, 100)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.archive = self.directory / "yaru-glass-theme-2.3.0.tar.gz"
        self.checksum = self.archive.with_name(self.archive.name + ".sha256")

    def archive_with(self, extra=(), missing=(), file_version="2.3.0"):
        root = "yaru-glass-theme-2.3.0/"
        with tarfile.open(self.archive, "w:gz") as package:
            for name in updates.REQUIRED:
                if name in missing:
                    continue
                content = (file_version if name == "VERSION" else "# fixture").encode()
                member = tarfile.TarInfo(root + name)
                member.size = len(content)
                member.mode = 0o755
                package.addfile(member, io.BytesIO(content))
            for name, kind in extra:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = "/etc/passwd" if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ""
                package.addfile(member)
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.checksum.write_text(f"{digest}  {self.archive.name}\n")
        return digest

    def test_valid_archive_and_checksum(self):
        digest = self.archive_with()
        updates.verify(self.archive, self.checksum, "2.3.0", "sha256:" + digest)
        destination = self.directory / "payload"
        updates.extract(self.archive, destination, "2.3.0")
        self.assertEqual((destination / "VERSION").read_text(), "2.3.0")
        self.assertTrue((destination / "bin/yaru-glass-update").stat().st_mode & 0o111)

    def test_contributor_documents_are_valid_payload_for_upgrade(self):
        root = "yaru-glass-theme-2.3.0/"
        self.archive_with([(root + name, tarfile.REGTYPE)
                           for name in ("CONTRIBUTING.md", "SECURITY.md")])
        legacy_payload = updates.PAYLOAD - {"CONTRIBUTING.md", "SECURITY.md"}
        destination = self.directory / "payload"
        with patch.object(updates, "PAYLOAD", legacy_payload):
            with self.assertRaisesRegex(updates.UpdateError, "Unexpected release payload path"):
                updates.extract(self.archive, destination, "2.3.0")
        self.assertFalse(destination.exists())
        updates.verify(self.archive, self.checksum, "2.3.0")
        updates.extract(self.archive, destination, "2.3.0")
        for name in ("CONTRIBUTING.md", "SECURITY.md"):
            self.assertTrue((destination / name).is_file())

    def test_checksum_filename_digest_and_archive_must_agree(self):
        self.archive_with()
        with self.assertRaisesRegex(updates.UpdateError, "checksum mismatch"):
            updates.verify(self.archive, self.checksum, "2.3.0", "sha256:" + "0" * 64)
        self.checksum.write_text("0" * 64 + "  other.tar.gz\n")
        with self.assertRaisesRegex(updates.UpdateError, "exactly"):
            updates.verify(self.archive, self.checksum, "2.3.0")
        self.checksum.write_text("0" * 64 + f"  {self.archive.name}\n")
        with self.assertRaisesRegex(updates.UpdateError, "checksum mismatch"):
            updates.verify(self.archive, self.checksum, "2.3.0")

    def test_unsafe_archives_rejected_before_destination_is_created(self):
        root = "yaru-glass-theme-2.3.0"
        for name, kind in ((root + "/../escape", tarfile.REGTYPE),
                           ("/absolute", tarfile.REGTYPE), ("other/VERSION", tarfile.REGTYPE),
                           (root + "/link", tarfile.SYMTYPE), (root + "/link", tarfile.LNKTYPE),
                           (root + "/device", tarfile.CHRTYPE), (root + "/fifo", tarfile.FIFOTYPE),
                           (root + "/VERSION", tarfile.REGTYPE),
                           (root + "/state/private", tarfile.REGTYPE),
                           (root + "/assets/../../escape", tarfile.REGTYPE)):
            with self.subTest(name=name, kind=kind):
                self.archive_with([(name, kind)])
                destination = self.directory / "payload"
                with self.assertRaises(updates.UpdateError):
                    updates.extract(self.archive, destination, "2.3.0")
                self.assertFalse(destination.exists())
        self.archive_with(file_version="2.4.0")
        with self.assertRaisesRegex(updates.UpdateError, "VERSION"):
            updates.extract(self.archive, self.directory / "payload", "2.3.0")
        self.archive_with(missing=("scripts/build.py",))
        with self.assertRaisesRegex(updates.UpdateError, "missing"):
            updates.extract(self.archive, self.directory / "payload", "2.3.0")

    def test_member_and_expansion_limits(self):
        self.archive_with()
        for name in ("MAX_MEMBERS", "MAX_EXPANDED"):
            with self.subTest(limit=name), patch.object(updates, name, 1):
                with self.assertRaises(updates.UpdateError):
                    updates.extract(self.archive, self.directory / "payload", "2.3.0")


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name) / "home"
        self.home.mkdir()
        self.home_patch = patch.object(Path, "home", return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)
        self.env = patch.dict(os.environ, {"HOME": str(self.home),
                              "XDG_CONFIG_HOME": str(self.home / ".config"),
                              "XDG_STATE_HOME": str(self.home / ".local/state")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.package = transaction.installed_root()
        self.package.mkdir(parents=True)
        (self.package / "VERSION").write_text("2.2.4\n")
        for name, content in (("backup/original/keys.tsv", b"original backup\n"),
                              ("state/installed-extensions.txt", b"owned@example\n"),
                              ("assets/profiles/custom.ini", b"keep custom profile\n"),
                              ("notes.txt", b"user-owned\n"), ("retired.py", b"retired\n")):
            path = self.package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.payload = self.home.parent / "payload"
        self.payload.mkdir()
        (self.payload / "VERSION").write_text("2.3.0\n")
        (self.payload / "assets/profiles").mkdir(parents=True)
        (self.payload / "assets/profiles/custom.ini").write_text("bundled replacement\n")
        self.config = self.home / ".config/yaru-glass"
        self.config.mkdir(parents=True)
        for name in ("settings.json", "app-appearance.json", "files-appearance.json",
                     "wallpapers.json", "glass-backup.json"):
            (self.config / name).write_bytes(b'{"fixture":true}\n')
        self.config_before = {path.name: path.read_bytes() for path in self.config.iterdir()}
        for label in ("light", "dark"):
            target = transaction.targets()[label]
            target.mkdir(parents=True)
            (target / "marker").write_text("old " + label)
        self.calls = []
        self.patches = [
            patch.object(transaction, "preflight"),
            patch.object(transaction, "service_active", return_value=True),
            patch.object(transaction, "capture_effects", return_value={
                "/org/gnome/shell/extensions/blur-my-shell/panel/blur": "'before'"}),
            patch.object(transaction, "run", side_effect=self.fake_run),
            patch.object(transaction, "generate", side_effect=self.fake_generate),
            patch.object(transaction, "reload_theme", return_value=True),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def fake_run(self, command, *args, **kwargs):
        self.calls.append(command)
        return ""

    def fake_generate(self, payload, output, fd):
        output.mkdir()
        for name in transaction.THEME_NAMES:
            (output / name).mkdir()
            (output / name / "marker").write_text("new " + name)

    def workspace(self):
        path = operation_lock.directory() / "transaction"
        path.mkdir()
        return path

    def assert_original(self):
        self.assertEqual((self.package / "VERSION").read_text(), "2.2.4\n")
        self.assertEqual((transaction.targets()["light"] / "marker").read_text(), "old light")
        self.assertFalse(os.path.lexists(transaction.targets()["launcher"]))
        for name, content in self.config_before.items():
            self.assertEqual((self.config / name).read_bytes(), content)

    def test_success_preserves_preferences_backups_profiles_and_other_account(self):
        other = self.home.parent / "other-account"
        other.mkdir()
        (other / "marker").write_text("untouched")
        workspace = self.workspace()
        result = transaction.install(self.payload, workspace, 99)
        self.assertEqual(result["status"], "installed")
        self.assertTrue(result["shell_reload_requested"])
        self.assertEqual((self.package / "VERSION").read_text(), "2.3.0\n")
        self.assertEqual((self.package / "backup/original/keys.tsv").read_bytes(), b"original backup\n")
        self.assertEqual((self.package / "state/installed-extensions.txt").read_bytes(), b"owned@example\n")
        self.assertEqual((self.package / "assets/profiles/custom.ini").read_bytes(), b"keep custom profile\n")
        for name, content in self.config_before.items():
            self.assertEqual((self.config / name).read_bytes(), content)
        self.assertEqual((other / "marker").read_text(), "untouched")
        self.assertTrue(transaction.targets()["launcher"].is_symlink())
        self.assertFalse(workspace.exists())
        self.assertIn(["systemctl", "--user", "start", transaction.SERVICE], self.calls)
        self.assertFalse(any("enable" in command or "apt-get" in command for command in self.calls))

    def test_precommit_generation_failure_leaves_everything_unchanged(self):
        with patch.object(transaction, "generate", side_effect=updates.UpdateError("generation failed")):
            with self.assertRaisesRegex(updates.UpdateError, "generation"):
                transaction.install(self.payload, self.workspace(), 99)
        self.assert_original()
        self.assertFalse(self.calls)

    def test_reload_failure_rolls_back_full_package_themes_and_runtime(self):
        with patch.object(transaction, "reload_theme", side_effect=[updates.UpdateError("reload failed"), True]):
            with self.assertRaisesRegex(updates.UpdateError, "previous version restored"):
                transaction.install(self.payload, self.workspace(), 99)
        self.assert_original()
        self.assertIn(["dconf", "write", "/org/gnome/shell/extensions/blur-my-shell/panel/blur",
                       "'before'"], self.calls)

    def test_service_restart_failure_rolls_back_and_restarts_old_service(self):
        count = 0
        def run(command, *args, **kwargs):
            nonlocal count
            self.calls.append(command)
            if "start" in command:
                count += 1
                if count == 1:
                    raise updates.UpdateError("service failed")
            return ""
        with patch.object(transaction, "run", side_effect=run):
            with self.assertRaisesRegex(updates.UpdateError, "previous version restored"):
                transaction.install(self.payload, self.workspace(), 99)
        self.assertEqual(count, 2)
        self.assert_original()

    def test_inactive_service_is_not_started_or_enabled(self):
        with patch.object(transaction, "service_active", return_value=False), patch.object(
                transaction, "reload_theme", return_value=False):
            result = transaction.install(self.payload, self.workspace(), 99)
        self.assertFalse(result["shell_reload_requested"])
        self.assertFalse(any("start" in command or "enable" in command for command in self.calls))

    def test_partial_replacement_failure_rolls_back_all_prior_renames(self):
        rename = Path.rename
        failed = False
        def fail_once(path, target):
            nonlocal failed
            if path.name == "new-light" and not failed:
                failed = True
                raise PermissionError("fixture replacement denied")
            return rename(path, target)
        with patch.object(Path, "rename", new=fail_once):
            with self.assertRaisesRegex(updates.UpdateError, "previous version restored"):
                transaction.install(self.payload, self.workspace(), 99)
        self.assertTrue(failed)
        self.assert_original()

    def test_insufficient_space_and_build_lock_contention_do_not_mutate_install(self):
        from collections import namedtuple
        usage = namedtuple("Usage", "total used free")(100, 99, 1)
        with patch.object(shutil, "disk_usage", return_value=usage):
            with self.assertRaisesRegex(updates.UpdateError, "free space"):
                transaction.install(self.payload, self.workspace(), 99)
        self.assert_original()
        self.assertFalse(self.calls)
        import fcntl
        with (self.config / "build.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(operation_lock.BusyError, "appearance"):
                transaction.install(self.payload, operation_lock.directory() / "transaction", 99)
        self.assert_original()

    def test_interruption_after_partial_commit_recovers_from_persistent_journal(self):
        rename = Path.rename
        def interrupt(path, target):
            if path.name == "new-dark":
                raise KeyboardInterrupt("fixture interruption")
            return rename(path, target)
        workspace = self.workspace()
        with patch.object(Path, "rename", new=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                transaction.install(self.payload, workspace, 99)
        self.assertTrue((workspace / "journal.json").exists())
        self.assertEqual((self.package / "VERSION").read_text(), "2.3.0\n")
        self.assertTrue(transaction.recover(workspace))
        self.assert_original()

    def test_malformed_recovery_records_fail_without_mutation(self):
        workspace = self.workspace()
        for value in ([], {"schema": 1, "entries": {}},
                      {"schema": 1, "entries": {}, "service_active": False,
                       "committed": False, "effects": {"bad": "value"}}):
            (workspace / "journal.json").write_text(json.dumps(value))
            with self.assertRaises(updates.UpdateError):
                transaction.recover(workspace)
            self.assert_original()
            self.assertFalse(self.calls)

    def test_failure_retains_recovery_then_retry_restores_original(self):
        workspace = self.workspace()
        with patch.object(transaction, "reload_theme", side_effect=updates.UpdateError("reload failed")):
            with self.assertRaisesRegex(updates.UpdateError, "Rollback incomplete"):
                transaction.install(self.payload, workspace, 99)
        self.assertTrue((workspace / "journal.json").exists())
        self.assertTrue(transaction.recover(workspace))
        self.assert_original()
        self.assertFalse(transaction.recover(workspace))

    def test_interruption_between_renames_is_recoverable(self):
        workspace = self.workspace()
        data = {"schema": 1, "entries": {"package": {"present": True}},
                "service_active": False, "effects": {}, "committed": False}
        transaction.journal_write(workspace, data)
        self.package.rename(workspace / "old-package")
        self.assertFalse(self.package.exists())
        self.assertTrue(transaction.recover(workspace))
        self.assert_original()

    def test_no_downgrades(self):
        (self.payload / "VERSION").write_text("2.2.4")
        with self.assertRaisesRegex(updates.UpdateError, "not newer"):
            transaction.install(self.payload, self.workspace(), 99)
        self.assert_original()

    def test_operation_locks_reject_conflicts_and_pending_recovery(self):
        with operation_lock.locked(exclusive=True):
            script = ("import sys; sys.path.insert(0,sys.argv[1]); "
                      "import operation_lock; "
                      "with_lock=operation_lock.locked(); with_lock.__enter__()")
            result = subprocess.run(["/usr/bin/python3", "-c", script,
                                     str(ROOT / "src/yaru_glass")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("busy", result.stderr)
        workspace = self.workspace()
        (workspace / "journal.json").write_text("{}")
        with self.assertRaisesRegex(operation_lock.BusyError, "recovery"):
            with operation_lock.locked():
                self.fail("Pending recovery must exclude mutations")


@unittest.skipIf(os.geteuid() == 0, "Updates require a normal desktop user")
class UpdaterLifecycleTests(unittest.TestCase):
    def test_verified_bootstrap_then_installed_cli_update(self):
        if not Path("/usr/share/themes/Yaru-blue/gtk-4.0/gtk.gresource").exists():
            self.skipTest("System Yaru resources are required for isolated staged generation")
        with tempfile.TemporaryDirectory(prefix="yaru-updater-") as directory:
            temporary = Path(directory)
            home = temporary / "home"
            home.mkdir()
            package = home / ".local/share/yaru-glass"
            package.mkdir(parents=True)
            for name in updates.PAYLOAD:
                source, target = ROOT / name, package / name
                if source.is_dir():
                    shutil.copytree(source, target, ignore=shutil.ignore_patterns(
                        "__pycache__", "*.pyc", ".git"))
                else:
                    shutil.copy2(source, target)
            (package / "VERSION").write_text("2.2.4\n")
            (package / "bin/yaru-glass-update").unlink()
            (package / "backup/original").mkdir(parents=True)
            (package / "backup/original/keys.tsv").write_text("first-install backup\n")
            (package / "state").mkdir()
            (package / "state/installed-extensions.txt").write_text("owned@example\n")
            (package / "assets/profiles/custom.ini").write_text("custom profile\n")
            (package / "bin/retired-command").write_text("must be removed")
            for name in transaction.THEME_NAMES:
                path = home / ".local/share/themes" / name
                path.mkdir(parents=True)
                (path / "old-marker").write_text("old theme")
            config = home / ".config/yaru-glass"
            config.mkdir(parents=True)
            for name, value in {
                "settings.json": {"transparency": 37, "glass_mode": "crystal",
                                  "readability_boost": True, "background_blur": False},
                "app-appearance.json": {"enabled": True, "transparency": 19},
                "files-appearance.json": {"enabled": False, "transparency": 41},
            }.items():
                (config / name).write_text(json.dumps(value) + "\n")
            before = {path.name: path.read_bytes() for path in config.iterdir()}
            stub = temporary / "stub-bin"
            stub.mkdir()
            (stub / "gnome-shell").write_text("#!/bin/sh\necho 'GNOME Shell 46.0'\n")
            (stub / "systemctl").write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$HOME/service-calls"\n'
                'case "$*" in *is-active*) echo inactive; exit 3;; esac\n')
            for path in stub.iterdir():
                path.chmod(0o755)
            environment = {
                "HOME": str(home), "PATH": f"{stub}:/usr/bin:/bin", "LANG": "C.UTF-8",
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_STATE_HOME": str(home / ".local/state"),
                "XDG_DATA_HOME": str(home / ".local/share"),
                "XDG_RUNTIME_DIR": str(temporary / "runtime"),
            }
            Path(environment["XDG_RUNTIME_DIR"]).mkdir(mode=0o700)

            def invoke(script, *arguments, extra_env=None):
                result = subprocess.run(
                    ["dbus-run-session", "--", "/usr/bin/python3", str(script), *arguments],
                    env={**environment, **(extra_env or {})}, capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return json.loads(result.stdout)

            archives = temporary / "archives"
            archives.mkdir()
            for text in ("2.3.0", "2.4.0"):
                release_root = temporary / ("release-" + text)
                release_root.mkdir()
                for name in updates.PAYLOAD:
                    source, target = ROOT / name, release_root / name
                    if source.is_dir():
                        shutil.copytree(source, target,
                                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
                    else:
                        shutil.copy2(source, target)
                (release_root / "VERSION").write_text(text + "\n")
                archive = archives / f"yaru-glass-theme-{text}.tar.gz"
                with tarfile.open(archive, "w:gz") as stream:
                    stream.add(release_root, arcname=f"yaru-glass-theme-{text}")
                checksum = archive.with_name(archive.name + ".sha256")
                checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest() +
                                    f"  {archive.name}\n")
                if text == "2.3.0":
                    extracted = temporary / "extracted"
                    updates.extract(archive, extracted, text)
                    result = invoke(extracted / "bin/yaru-glass-update", "install", "--bootstrap",
                                    "--archive", str(archive), "--checksum", str(checksum), "--yes", "--json")
                    self.assertEqual(result["installed_version"], text)
            data = release_data("2.4.0")
            data["assets"][0]["size"] = (archives / data["assets"][0]["name"]).stat().st_size
            (archives / "release.json").write_text(json.dumps(data))
            fixtures = temporary / "network-fixture"
            fixtures.mkdir()
            (fixtures / "sitecustomize.py").write_text(
                "import os, sys\nfrom pathlib import Path\n"
                "sys.path.insert(0,str(Path(os.environ['HOME'])/"
                "'.local/share/yaru-glass/src/yaru_glass'))\n"
                "import updates\n"
                "def download(url, limit, destination=None):\n"
                "    path=Path(os.environ['UPDATE_FIXTURE']) / "
                "('release.json' if url==updates.API else url.rsplit('/',1)[1])\n"
                "    data=path.read_bytes()\n"
                "    if len(data)>limit: raise updates.UpdateError('fixture exceeds limit')\n"
                "    if destination:\n"
                "        with destination.open('xb') as stream: stream.write(data)\n"
                "        return b''\n"
                "    return data\n"
                "updates.download=download\n")
            network_env = {"PYTHONPATH": str(fixtures), "UPDATE_FIXTURE": str(archives)}
            cli = package / "bin/yaru-glass-update"
            result = invoke(cli, "check", "--json", extra_env=network_env)
            self.assertEqual(result["status"], "available")
            result = invoke(cli, "install", "--yes", "--json", "--target", "2.4.0", extra_env=network_env)
            self.assertEqual(result["installed_version"], "2.4.0")
            self.assertFalse(result["shell_reload_requested"])
            for name, content in before.items():
                self.assertEqual((config / name).read_bytes(), content)
            self.assertEqual((package / "backup/original/keys.tsv").read_text(), "first-install backup\n")
            self.assertEqual((package / "state/installed-extensions.txt").read_text(), "owned@example\n")
            self.assertEqual((package / "assets/profiles/custom.ini").read_text(), "custom profile\n")
            self.assertFalse((package / "bin/retired-command").exists())
            self.assertTrue((home / ".local/bin/yaru-glass-update").is_symlink())
            for name in transaction.THEME_NAMES:
                self.assertTrue((home / ".local/share/themes" / name / "gnome-shell/gnome-shell.css").is_file())
            calls = (home / "service-calls").read_text()
            self.assertNotIn("--user start ", calls)
            self.assertNotIn("--user enable ", calls)


if __name__ == "__main__":
    unittest.main()
