import contextlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/yaru_glass"))
import diagnostics as logs


def writer(index, max_bytes=logs.MAX_BYTES):
    logs.MAX_BYTES = max_bytes
    for _ in range(25):
        logs.event("worker", "apply", "success", count=index)


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"XDG_STATE_HOME": self.temp.name,
                                     "YARU_GLASS_OPERATION_ID": ""})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(patch.stopall)
        patch.object(logs, "_warned", False).start()

    def test_default_private_bounded_allowlisted_records(self):
        logs.event("worker", "apply", "success", password="secret", path="/home/private/image",
                   extension=[], mode="frost", transparency=35)
        record = logs.read_records()["records"][0]
        self.assertEqual(record["fields"], {"mode": "frost", "transparency": 35})
        self.assertEqual(record["schema"], 1)
        self.assertEqual(logs.directory().stat().st_mode & 0o777, 0o700)
        for path in logs.directory().iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("secret", json.dumps(record))

    def test_error_records_never_include_message_or_source(self):
        try:
            raise ValueError("password=secret /home/alice/private.jpg")
        except ValueError as exc:
            logs.event("worker", "apply", "failure", level="ERROR", error=exc)
        record = logs.read_records()["records"][0]
        self.assertEqual(record["error"], {"type": "ValueError", "frames": []})
        self.assertNotIn("alice", json.dumps(record))
        self.assertNotIn("secret", json.dumps(record))

    def test_operation_correlates_nested_calls_and_propagates_error(self):
        with self.assertRaises(ValueError):
            with logs.operation("settings", "apply"):
                with logs.operation("worker", "apply"):
                    raise ValueError("private")
        records = logs.read_records()["records"]
        self.assertEqual(len({record["operation"] for record in records}), 1)
        self.assertEqual([r["phase"] for r in records], ["start", "start", "failure", "failure"])
        self.assertEqual(records[-1]["level"], "ERROR")

    def test_operation_honors_inherited_identifier(self):
        with patch.dict(os.environ, {"YARU_GLASS_OPERATION_ID": "a" * 32}):
            with logs.operation("worker", "apply"):
                logs.event("glass", "repair", "requested")
        self.assertEqual({r["operation"] for r in logs.read_records()["records"]}, {"a" * 32})

    def test_verbose_is_independent_and_reversible(self):
        logs.event("sync", "apply", "start", level="DEBUG")
        self.assertEqual(logs.read_records()["records"], [])
        logs.set_verbose(True)
        logs.event("sync", "apply", "start", level="DEBUG")
        self.assertTrue(logs.verbose())
        self.assertEqual(len(logs.read_records()["records"]), 2)
        logs.set_verbose(False)
        self.assertFalse(logs.verbose())

    def test_rotation_concurrent_writers_and_retention(self):
        with patch.object(logs, "MAX_BYTES", 4096):
            processes = [multiprocessing.get_context("spawn").Process(
                target=writer, args=(i, 4096)) for i in range(4)]
            for process in processes:
                process.start()
            for process in processes:
                process.join(20)
                self.assertEqual(process.exitcode, 0)
            data = logs.read_records(2000)
            self.assertEqual(data["invalid_records"], 0)
            self.assertGreater(len(data["records"]), 0)
            self.assertLessEqual(len(list(logs.directory().glob("events.jsonl*"))), 5)
            for path in logs.directory().glob("events.jsonl*"):
                self.assertLessEqual(path.stat().st_size, 4096)

    def test_concurrent_append_without_rotation_loses_no_records(self):
        processes = [multiprocessing.get_context("spawn").Process(
            target=writer, args=(i,)) for i in range(3)]
        for process in processes:
            process.start()
        for process in processes:
            process.join(20)
            self.assertEqual(process.exitcode, 0)
        data = logs.read_records(2000)
        self.assertEqual(len(data["records"]), 75)
        self.assertEqual(data["invalid_records"], 0)

    def test_unavailable_storage_warns_once_and_never_breaks_action(self):
        output = io.StringIO()
        with patch.object(logs, "_prepare", side_effect=PermissionError("private path")), \
                contextlib.redirect_stderr(output):
            with logs.operation("worker", "apply"):
                pass
        self.assertEqual(output.getvalue().count("storage unavailable"), 1)
        self.assertNotIn("private path", output.getvalue())

    def test_disk_full_does_not_change_operation_success(self):
        with patch.object(logs, "_open", side_effect=OSError(28, "secret")), \
                contextlib.redirect_stderr(io.StringIO()) as output:
            with logs.operation("worker", "apply"):
                result = 42
        self.assertEqual(result, 42)
        self.assertIn("storage unavailable", output.getvalue())

    def test_unknown_events_and_unsafe_read_bounds_are_rejected(self):
        with self.assertRaises(ValueError):
            logs.event("private data", "apply", "success")
        for limit in (0, 2001, -1):
            with self.assertRaises(ValueError):
                logs.read_records(limit)

    def test_storage_symlinks_and_hardlinks_are_not_followed(self):
        target = Path(self.temp.name) / "private"
        target.write_text("unchanged")
        logs.directory().symlink_to(target)
        with self.assertRaises((OSError, ValueError)):
            logs.read_records()
        logs.directory().unlink()
        logs.directory().mkdir()
        (logs.directory() / "events.jsonl").symlink_to(target)
        with self.assertRaises(OSError):
            logs.read_records()
        self.assertEqual(target.read_text(), "unchanged")
        (logs.directory() / "events.jsonl").unlink()
        os.link(target, logs.directory() / "events.jsonl")
        with self.assertRaises(OSError):
            logs.read_records()

    def test_malformed_records_are_counted_not_displayed(self):
        logs.event("worker", "apply", "success")
        record = logs.read_records()["records"][0]
        record["extra"] = "private data"
        with (logs.directory() / "events.jsonl").open("a") as stream:
            stream.write("private data\n" + json.dumps(record) + "\n")
        data = logs.read_records()
        self.assertEqual(data["invalid_records"], 2)
        self.assertEqual(len(data["records"]), 1)
        self.assertNotIn("private data", json.dumps(data))

    def test_export_resanitizes_fields_and_refuses_overwrite(self):
        logs.event("worker", "apply", "success")
        active = logs.directory() / "events.jsonl"
        record = json.loads(active.read_text())
        record["fields"]["message"] = "token=secret"
        active.write_text(json.dumps(record) + "\n")
        destination = Path(self.temp.name) / "report.json"
        with patch.object(logs, "report", return_value={"records": logs.read_records()["records"]}):
            logs.export_report(destination)
            with self.assertRaises(FileExistsError):
                logs.export_report(destination)
        self.assertNotIn("secret", destination.read_text())
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_invalid_unicode_nested_and_unhashable_records_are_omitted(self):
        logs.event("worker", "apply", "success")
        original = logs.read_records()["records"][0]
        invalid = []
        for key in ("component", "action", "phase", "level"):
            record = {**original, key: []}
            invalid.append(json.dumps(record).encode())
        invalid.extend((json.dumps({**original, "schema": True}).encode(),
                        b"\xff", b"[" * 1500 + b"]" * 1500))
        with (logs.directory() / "events.jsonl").open("ab") as stream:
            stream.write(b"\n".join(invalid) + b"\n")
        data = logs.read_records()
        self.assertEqual(data["invalid_records"], len(invalid))
        self.assertEqual(len(data["records"]), 1)

    def test_purge_only_known_files_leaves_user_files_and_coordination_inode(self):
        logs.set_verbose(True)
        user = logs.directory() / "user-report.json"
        user.write_text("mine")
        inode = (logs.directory() / "diagnostics.lock").stat().st_ino
        logs.purge()
        self.assertTrue(user.exists())
        self.assertFalse((logs.directory() / "events.jsonl").exists())
        self.assertFalse((logs.directory() / "diagnostics.json").exists())
        self.assertEqual((logs.directory() / "diagnostics.lock").stat().st_ino, inode)

    def test_cli_json_output_filters_and_invalid_record_warning(self):
        logs.event("worker", "apply", "failure", level="ERROR")
        logs.event("sync", "activate", "success")
        result = subprocess.run(
            ["/usr/bin/python3", str(ROOT / "bin/yaru-glass-logs"), "show", "--level", "ERROR"],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertEqual(json.loads(result.stdout)["level"], "ERROR")

    def test_cli_unavailable_storage_returns_failure_without_private_error(self):
        with patch.object(logs, "_prepare", side_effect=PermissionError("/home/private")):
            with contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(logs.main(["show"]), 1)
        self.assertNotIn("/home/private", output.getvalue())

    def test_follow_prints_new_record_once_and_stops_cleanly(self):
        logs.event("worker", "apply", "success")
        rounds = 0

        def advance(_seconds):
            nonlocal rounds
            rounds += 1
            if rounds == 1:
                logs.event("sync", "activate", "success")
            elif rounds == 3:
                raise KeyboardInterrupt

        with patch.object(logs.time, "sleep", side_effect=advance), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(logs.main(["follow"]), 0)
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([r["component"] for r in records], ["worker", "sync"])

    def test_report_contains_safe_metadata_not_arbitrary_extension_fields(self):
        from gi.repository import Gio
        import managed_glass
        with patch.object(Gio, "bus_get_sync"), \
                patch.object(managed_glass, "running_shell_major", return_value="46"), \
                patch.object(managed_glass, "running_extension_info",
                             return_value={"state": 1.0, "version": 77,
                                           "path": "/home/alice/private", "error": "secret"}), \
                patch.object(managed_glass, "validate_running_extension"):
            result = logs.report()
        text = json.dumps(result)
        self.assertNotIn("alice", text)
        self.assertNotIn("secret", text)
        self.assertEqual(result["gnome_shell"], "46")
        self.assertEqual(result["extensions"]["blur-my-shell@aunetx"]["version"], 77)
        self.assertEqual(result["extensions"]["blur-my-shell@aunetx"]["state"], 1)

    def test_export_failure_removes_partial_output(self):
        destination = Path(self.temp.name) / "report.json"
        with patch.object(logs, "report", return_value={}), \
                patch.object(logs.os, "fdopen", side_effect=OSError(28, "disk full")):
            with self.assertRaises(OSError):
                logs.export_report(destination)
        self.assertFalse(destination.exists())

    def test_busy_storage_times_out_instead_of_blocking_actions(self):
        import time
        with logs._locked():
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                logs.read_records()
            self.assertLess(time.monotonic() - started, 1)
            with contextlib.redirect_stderr(io.StringIO()) as output:
                logs.event("settings", "apply", "requested")
        self.assertIn("storage unavailable", output.getvalue())

    def test_follow_survives_rotation_without_duplicates(self):
        rounds = 0

        def advance(_seconds):
            nonlocal rounds
            rounds += 1
            if rounds == 5:
                raise KeyboardInterrupt
            logs.event("worker", "apply", "success", count=rounds)

        with patch.object(logs, "MAX_BYTES", 512), \
                patch.object(logs.time, "sleep", side_effect=advance), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            logs.event("worker", "apply", "success", count=0)
            self.assertEqual(logs.main(["follow"]), 0)
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([r["fields"]["count"] for r in records], list(range(5)))
        self.assertTrue((logs.directory() / "events.jsonl.1").exists())


if __name__ == "__main__":
    unittest.main()
