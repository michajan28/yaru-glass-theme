import runpy
import json
import os
import copy
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/yaru_glass"))

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, GLib, Gtk
    UI_AVAILABLE = Gtk.init_check()
except (ImportError, ValueError):
    UI_AVAILABLE = False


class FakeProcess:
    def __init__(self, successful=True, error=""):
        self.successful = successful
        self.error = error

    def communicate_utf8_async(self, _input, _cancellable, callback, target):
        self.callback = callback
        self.target = target
        self.stdout = ""
        if target is not None:
            snapshot = copy.deepcopy(callback.__self__.snapshot())
            for section, fields in target.items():
                snapshot[section].update(fields)
            self.stdout = json.dumps(snapshot)

    def communicate_utf8_finish(self, _result):
        return True, self.stdout, self.error

    def get_successful(self):
        return self.successful

    def finish(self):
        self.callback(self, None, self.target)


@unittest.skipUnless(UI_AVAILABLE, "GTK 4/libadwaita and a display are required")
class SettingsUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = runpy.run_path(str(ROOT / "bin/yaru-glass-settings"), run_name="settings_test")
        Adw.init()
        cls.app = cls.ui["SettingsApplication"]()
        cls.app.set_application_id("org.yaru.glass.Settings.Test")
        cls.app.register(None)

    def setUp(self):
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        diagnostic_env = patch.dict(os.environ, {"XDG_STATE_HOME": state.name})
        diagnostic_env.start()
        self.addCleanup(diagnostic_env.stop)
        files_load = patch.object(self.ui["files_appearance"], "load",
                                  return_value={"enabled": False, "transparency": 25})
        files_load.start()
        self.addCleanup(files_load.stop)
        with patch.dict(self.ui["SettingsWindow"].__init__.__globals__, {
            "load_settings": lambda: {"transparency": 25, "glass_mode": "frost"},
            "load_app_appearance": lambda: {"enabled": False, "transparency": 25},
        }):
            self.window = self.ui["SettingsWindow"](self.app)

    def tearDown(self):
        self.cancel_timeout()
        if not self.window.get_realized():
            self.window.realize()
        self.window.destroy()

    def test_files_description_does_not_exclude_verified_nautilus_50(self):
        body = self.window.page_bodies["applications"]
        child = body.get_first_child()
        groups = []
        while child:
            if isinstance(child, Adw.PreferencesGroup):
                groups.append(child)
            child = child.get_next_sibling()
        files_group = next(group for group in groups
                           if group.get_title() == "Files transparency (experimental)")
        self.assertIn("Nautilus sidebar and headerbars", files_group.get_description())
        self.assertNotIn("46 only", files_group.get_description())

    def cancel_timeout(self):
        if self.window.timeout_id:
            GLib.source_remove(self.window.timeout_id)
            self.window.timeout_id = 0

    def diagnostics_window(self):
        from diagnostics_ui import DiagnosticsPage
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        env = patch.dict(os.environ, {"XDG_STATE_HOME": directory.name})
        env.start()
        self.addCleanup(env.stop)
        window = DiagnosticsPage(self.window)
        self.addCleanup(window.on_close)
        self.wait_diagnostics(window)
        return window

    def updates_window(self):
        from updates_ui import UpdatesPage
        with patch("updates.read_version", return_value="2.2.4"):
            window = UpdatesPage(self.window, ROOT)
        self.addCleanup(window.on_close)
        return window

    def updater_result(self, window, result, installing=False, successful=True):
        process = FakeProcess(successful=successful)
        window.process = process
        window.installing = installing
        window.parent.update_installing = installing
        process.stdout = json.dumps(result)
        window.completed(process, None, None)

    def test_updates_navigation_opens_manual_controls_without_network(self):
        from updates_ui import UpdatesPage
        with patch.object(UpdatesPage, "start") as start:
            self.window.open_updates()
            window = self.window.updates_page
            self.assertIs(window.get_root(), self.window)
            self.assertEqual(self.window.pages.get_visible_child_name(), "updates")
            self.assertTrue(window.check_button.get_sensitive())
            self.assertFalse(window.install_button.get_sensitive())
            start.assert_not_called()
            window.check_button.emit("clicked")
            start.assert_called_once_with(["check", "--json"], False)

    def test_updates_check_uses_async_cli_and_accepts_only_expected_release_link(self):
        from updates_ui import Gio
        window = self.updates_window()
        process = FakeProcess()
        with patch.object(Gio.Subprocess, "new", return_value=process) as start:
            window.check()
        arguments, flags = start.call_args.args
        self.assertIn("check", arguments)
        self.assertIn("--json", arguments)
        self.assertIs(window.process, process)
        self.assertFalse(window.check_button.get_sensitive())
        process.stdout = json.dumps({
            "status": "available", "installed_version": "2.2.4", "available_version": "2.3.0",
            "release_url": "https://github.com/michajan28/yaru-glass-theme/releases/tag/v2.3.0"})
        process.finish()
        self.assertTrue(window.install_button.get_sensitive())
        self.assertEqual(window.available, "2.3.0")
        self.updater_result(window, {
            "status": "available", "installed_version": "2.2.4", "available_version": "2.3.0",
            "release_url": "https://example.com/untrusted"})
        self.assertIn("unavailable", window.status.get_label())
        self.assertTrue(window.status.has_css_class("error"))

    def test_updates_busy_cancel_and_parent_close_gates(self):
        window = self.updates_window()
        window.available = "2.3.0"
        with patch.object(window, "start") as start:
            window.on_confirmed(None, "cancel", "2.3.0")
            start.assert_not_called()
            self.window.requested = {"shell": {"transparency": 13}}
            window.on_confirmed(None, "install", "2.3.0")
            start.assert_not_called()
            self.window.requested = None
            window.on_confirmed(None, "install", "2.3.0")
            start.assert_called_once_with(
                ["install", "--yes", "--json", "--target", "2.3.0"], True)
        window.installing = True
        self.window.update_installing = True
        self.assertTrue(window.on_close())
        self.assertTrue(self.window.on_close(self.window))
        self.window.queue_patch({"shell": {"transparency": 12}})
        self.assertIsNone(self.window.requested)
        self.window.update_installing = False
        window.installing = False

    def test_updates_success_requires_reopening_and_never_restarts_files(self):
        window = self.updates_window()
        self.updater_result(window, {
            "status": "installed", "installed_version": "2.3.0",
            "settings_relaunch_required": True, "shell_reload_requested": False,
            "files_restart_required": True}, installing=True)
        self.assertTrue(self.window.update_installed)
        self.assertFalse(self.window.page_bodies["shell"].get_sensitive())
        self.assertTrue(self.window.pages.get_sensitive())
        self.assertTrue(window.finish_button.get_visible())
        self.assertIn("Inactive project theme was not activated", window.status.get_label())
        self.assertIn("has not been restarted", window.status.get_label())

    def test_updates_failure_and_unavailable_result_are_truthful(self):
        window = self.updates_window()
        self.updater_result(window, {"status": "error", "message": "offline",
                                    "recovery_required": False}, successful=False)
        self.assertEqual(window.status.get_label(), "offline")
        self.assertTrue(window.check_button.get_sensitive())
        self.updater_result(window, {"status": "error", "message": "Rollback incomplete",
                                    "recovery_required": True}, installing=True, successful=False)
        self.assertFalse(self.window.page_bodies["shell"].get_sensitive())
        self.assertTrue(window.finish_button.get_visible())
        self.updater_result(window, {"status": "installed"}, installing=True)
        self.assertIn("unavailable", window.status.get_label())
        self.assertFalse(self.window.page_bodies["shell"].get_sensitive())

    def test_external_app_update_disables_stale_appearance_controls(self):
        window = self.window
        window.loaded_version = "a different installed version"
        window.queue_patch({"shell": {"transparency": 13}})
        self.assertTrue(window.update_installed)
        self.assertIsNone(window.requested)
        self.assertFalse(window.page_bodies["shell"].get_sensitive())

    def wait_diagnostics(self, window):
        deadline = time.monotonic() + 10
        context = GLib.MainContext.default()
        while window.busy and time.monotonic() < deadline:
            while context.pending():
                context.iteration(False)
            time.sleep(.01)
        self.assertFalse(window.busy, "Diagnostic worker failed to complete")

    def test_diagnostics_has_visible_labeled_navigation_button_that_opens_viewer(self):
        from diagnostics_ui import DiagnosticsPage
        window = self.window
        context = GLib.MainContext.default()
        for size in ((900, 700), (740, 650), (360, 420)):
            window.set_default_size(*size)
            window.present()
            for _ in range(12):
                while context.pending():
                    context.iteration(False)
                time.sleep(.025)
            model = window.pages.get_pages()
            self.assertEqual([model.get_item(i).get_title() for i in range(model.get_n_items())],
                             ["Shell", "Applications", "Wallpapers", "Diagnostics", "Updates"])
            if size[0] >= 740:
                self.assertTrue(window.navigation.get_mapped())
                self.assertLessEqual(window.navigation.get_width(), window.get_width())
            else:
                self.assertTrue(window.compact_navigation.get_mapped())
            window.open_diagnostics()
            self.wait_diagnostics(window.diagnostics_page)
            self.assertIsInstance(window.diagnostics_page, DiagnosticsPage)
            self.assertIs(window.diagnostics_page.get_root(), window)
            self.assertEqual(window.pages.get_visible_child_name(), "diagnostics")
            window.compact_navigation.set_selected(4)
            self.assertEqual(window.pages.get_visible_child_name(), "updates")
            self.assertIs(window.updates_page.get_root(), window)
            self.assertLessEqual(window.get_width(), size[0])

    def test_diagnostics_reads_filters_and_toggles_without_appearance_changes(self):
        import diagnostics
        window = self.diagnostics_window()
        before = copy.deepcopy(self.window.snapshot())
        diagnostics.event("worker", "apply", "failure", level="ERROR")
        diagnostics.event("sync", "activate", "success")
        window.level.set_selected(3)
        self.wait_diagnostics(window)
        buffer = window.text.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        self.assertIn("[ERROR]", text)
        self.assertIn("Worker / Apply - Failed", text)
        self.assertNotIn("Sync /", text)
        self.assertNotIn('{"action":', text)
        window.verbose_switch.set_active(True)
        self.wait_diagnostics(window)
        self.assertTrue(diagnostics.verbose())
        self.assertEqual(self.window.snapshot(), before)
        self.assertIsNone(self.window.process)

    def test_diagnostics_storage_failure_is_visible_not_an_empty_success(self):
        import diagnostics
        window = self.diagnostics_window()
        with patch.object(diagnostics, "read_records", side_effect=PermissionError("private")):
            window.refresh()
            self.wait_diagnostics(window)
        self.assertIn("unavailable", window.status.get_label())
        self.assertNotIn("private", window.status.get_label())
        self.assertTrue(window.status.has_css_class("error"))

    def test_diagnostics_formats_details_and_errors_without_changing_json_export(self):
        from diagnostics_ui import format_record
        record = {"timestamp": "2026-11-04T13:34:36+00:00", "level": "ERROR",
                  "component": "updater", "action": "install", "phase": "failure",
                  "fields": {"duration_ms": 125, "reload_requested": False},
                  "error": {"type": "PermissionError", "errno": "EACCES",
                            "frames": [{"file": "updates.py", "line": 42}]},
                  "operation": "a" * 32, "version": "2.2.4", "pid": 42}
        before = copy.deepcopy(record)
        summary, details = format_record(record)
        self.assertIn("[ERROR]", summary)
        self.assertIn("Updater / Install - Failed", summary)
        self.assertIn("Duration ms: 125", details)
        self.assertIn("Reload requested: No", details)
        self.assertIn("Error: PermissionError", details)
        self.assertIn("System error: EACCES", details)
        self.assertIn("At: updates.py:42", details)
        self.assertIn("Operation: " + "a" * 32, details)
        self.assertEqual(record, before)

    def test_diagnostics_export_requires_explicit_choice_and_surfaces_failure(self):
        import diagnostics
        from unittest.mock import Mock
        from gi.repository import Gio
        window = self.diagnostics_window()
        chooser = Mock()
        with patch.object(diagnostics, "export_report") as export:
            window.on_export_chosen(chooser, Gtk.ResponseType.CANCEL)
            export.assert_not_called()
        destination = Path(os.environ["XDG_STATE_HOME"]) / "report.json"
        chooser.get_file.return_value = Gio.File.new_for_path(str(destination))
        with patch.object(diagnostics, "report", return_value={"schema": 1, "records": []}):
            window.on_export_chosen(chooser, Gtk.ResponseType.ACCEPT)
            self.wait_diagnostics(window)
        self.assertEqual(json.loads(destination.read_text())["schema"], 1)
        self.assertIn("saved locally", window.status.get_label())
        window.on_export_chosen(chooser, Gtk.ResponseType.ACCEPT)
        self.wait_diagnostics(window)
        self.assertIn("no success is confirmed", window.status.get_label())
        self.assertTrue(window.status.has_css_class("error"))

    def test_diagnostics_async_worker_does_not_block_gtk(self):
        import threading
        window = self.diagnostics_window()
        gate = threading.Event()
        self.addCleanup(gate.set)
        complete = []
        window.run_job(lambda: gate.wait(5), complete.append)
        self.assertTrue(window.busy)
        self.assertFalse(window.refresh_button.get_sensitive())
        self.assertFalse(complete)
        gate.set()
        self.wait_diagnostics(window)
        self.assertEqual(complete, [True])
        self.assertTrue(window.refresh_button.get_sensitive())

    def test_diagnostics_failed_verbose_toggle_restores_last_confirmed_value(self):
        import diagnostics
        window = self.diagnostics_window()
        with patch.object(diagnostics, "set_verbose", side_effect=PermissionError("private")):
            window.verbose_switch.set_active(True)
            self.wait_diagnostics(window)
        self.assertFalse(window.verbose_switch.get_active())
        self.assertTrue(window.status.has_css_class("error"))

    def test_worker_correlates_request_and_result_without_logging_payload(self):
        import diagnostics
        process = FakeProcess()
        with patch.object(self.ui["Gio"].Subprocess, "new", return_value=process) as launch:
            self.window.queue_patch({"app": {"enabled": True}})
            self.apply_now()
            operation = self.window.worker_operation
            self.assertIn(f"YARU_GLASS_OPERATION_ID={operation}", launch.call_args.args[0])
            self.assertEqual(json.loads(launch.call_args.args[0][-1]), {"app": {"enabled": True}})
            process.finish()
        records = [r for r in diagnostics.read_records()["records"] if r["action"] == "apply"]
        self.assertEqual([r["phase"] for r in records], ["requested", "success"])
        self.assertEqual({r["operation"] for r in records}, {operation})

    def apply_now(self):
        self.cancel_timeout()
        self.window.apply_pending()

    def finish_pending(self, successful=True, error=""):
        process = FakeProcess(successful, error)
        with patch.object(self.ui["Gio"].Subprocess, "new", return_value=process):
            self.apply_now()
            process.finish()

    def test_pages_group_controls_and_status_without_saving_or_building(self):
        window = self.window
        self.assertEqual(window.pages.get_visible_child_name(), "shell")
        for name, controls in (
            ("shell", (window.mode, window.scale, window.status, window.retry)),
            ("applications", (window.app_switch, window.app_status, window.files_switch,
                              window.files_status, window.files_restart)),
            ("wallpapers", (*window.wallpaper_previews.values(), window.wallpaper_status)),
        ):
            page = window.page_bodies[name]
            for control in controls:
                self.assertTrue(control.is_ancestor(page), (name, control))
            scroll = window.pages.get_child_by_name(name)
            self.assertIsInstance(scroll, Gtk.ScrolledWindow)
            self.assertEqual(scroll.props.hscrollbar_policy, Gtk.PolicyType.NEVER)
        with patch.object(self.ui["Gio"].Subprocess, "new") as launch, \
             patch.object(self.ui["files_appearance"], "save") as save:
            for name in ("applications", "wallpapers", "shell"):
                window.pages.set_visible_child_name(name)
            launch.assert_not_called()
            save.assert_not_called()
        self.assertIsNone(window.requested)
        self.assertEqual(window.timeout_id, 0)

    def test_errors_navigate_to_the_relevant_page(self):
        window = self.window
        with patch("sys.stderr"):
            window.show_app_error("app failure")
            self.assertEqual(window.pages.get_visible_child_name(), "applications")
            window.pages.set_visible_child_name("wallpapers")
            window.show_files_error("Files failure")
            self.assertEqual(window.pages.get_visible_child_name(), "applications")
            window.show_error("Shell failure")
            self.assertEqual(window.pages.get_visible_child_name(), "shell")

    def test_files_save_and_restart_status_are_distinct(self):
        window = self.window
        with patch.object(self.ui["files_appearance"], "save"):
            window.set_files_preset(None, True, 25)
            self.finish_pending()
        self.assertIn("restart required", window.files_status.get_label())
        with patch.object(window, "integration_state", return_value=(True, True)):
            window.finish_files_restart()
        self.assertEqual(window.files_status.get_label(), "Files restarted with the saved appearance.")
        with patch.object(window, "integration_state", return_value=(False, False)):
            window.finish_files_restart()
        self.assertIn("inactive", window.files_status.get_label())

    def test_pages_render_at_default_size_and_keep_transparent_background(self):
        from gtk_rendering import snapshot_widget
        window = self.window
        window.app_appearance = {"enabled": True, "transparency": 50}
        window.update_app_style()
        paintable = Gtk.WidgetPaintable.new(window)
        window.present()
        context = GLib.MainContext.default()
        for name in ("shell", "applications", "wallpapers"):
            window.pages.set_visible_child_name(name)
            for _ in range(12):
                while context.pending():
                    context.iteration(False)
                time.sleep(.025)
            self.assertLessEqual(window.get_width(), 740)
            self.assertEqual(window.get_height(), 650)
            page = window.pages.get_child_by_name(name)
            self.assertTrue(page.get_mapped())
            self.assertLessEqual(window.page_bodies[name].get_width(), page.get_width())
            texture = snapshot_widget(window, paintable)
            image = self.ui["Gdk"].pixbuf_get_from_texture(texture)
            alpha = image.get_pixels()[150 * image.get_rowstride() + 12 * image.get_n_channels() + 3]
            self.assertLess(alpha, 255, name)

    def test_settings_pages_fit_small_window_and_scroll_vertically(self):
        window = self.window
        window.set_default_size(360, 420)
        window.present()
        context = GLib.MainContext.default()
        for _ in range(12):
            while context.pending():
                context.iteration(False)
            time.sleep(.025)
        self.assertTrue(window.compact_navigation.get_visible())
        window.compact_navigation.set_selected(1)
        self.assertEqual(window.pages.get_visible_child_name(), "applications")
        for name in ("shell", "applications", "wallpapers"):
            window.pages.set_visible_child_name(name)
            for _ in range(12):
                while context.pending():
                    context.iteration(False)
                time.sleep(.025)
            page = window.pages.get_child_by_name(name)
            self.assertIsInstance(page, Gtk.ScrolledWindow)
            self.assertLessEqual(window.get_width(), 380)
            self.assertLessEqual(window.get_height(), 420)
            self.assertLessEqual(window.page_bodies[name].get_width(), page.get_width())
            self.assertGreater(window.page_bodies[name].get_height(), page.get_height())
            self.assertTrue(window.compact_navigation.get_visible())
            self.assertFalse(window.navigation.get_visible())
            horizontal, vertical = page.get_policy()
            self.assertEqual(horizontal, Gtk.PolicyType.NEVER)
            self.assertEqual(vertical, Gtk.PolicyType.AUTOMATIC)

    def test_scale_and_debounce(self):
        window = self.window
        self.assertEqual(window.scale.get_value(), 25)
        self.assertEqual(window.scale.get_adjustment().get_lower(), 0)
        self.assertEqual(window.scale.get_adjustment().get_upper(), 50)
        with patch.object(self.ui["Gio"].Subprocess, "new") as launch:
            window.scale.set_value(10)
            window.scale.set_value(30)
            window.scale.set_value(40)
            self.assertEqual(window.requested, {"shell": {"transparency": 40}})
            self.assertEqual(window.percent.get_label(), "40%")
            launch.assert_not_called()
        self.assertNotEqual(window.timeout_id, 0)

    def test_app_transparency_is_opt_in_scoped_and_does_not_build_shell(self):
        window = self.window
        self.assertFalse(window.has_css_class("yaru-settings-glass"))
        self.assertFalse(window.app_scale.get_sensitive())
        with patch.object(self.ui["Gio"].Subprocess, "new") as build:
            window.app_switch.set_active(True)
            window.app_scale.set_value(50)
            build.assert_not_called()
        self.finish_pending()
        self.assertTrue(window.has_css_class("yaru-settings-glass"))
        self.assertEqual(window.app_appearance, {"enabled": True, "transparency": 50})
        self.assertIsNone(window.requested)
        self.assertEqual(window.timeout_id, 0)
        self.assertEqual(window.get_opacity(), 1)
        css = window.app_css.to_string()
        self.assertIn("window.yaru-settings-glass", css)
        self.assertIn("@view_bg_color", css)
        self.assertNotRegex(css, r"window\.yaru-settings-glass\s*\{[^}]*\bopacity:")
        self.assertEqual(window.scale.get_value(), 25)
        window.app_switch.set_active(False)
        self.finish_pending()
        self.assertFalse(window.has_css_class("yaru-settings-glass"))

    def test_files_controls_save_independently_without_restarting_apps(self):
        window = self.window
        self.assertFalse(window.files_switch.get_active())
        self.assertFalse(window.files_scale.get_sensitive())
        with patch.object(self.ui["files_appearance"], "save") as save, \
             patch.object(self.ui["Gio"].Subprocess, "new") as process:
            window.files_switch.set_active(True)
            window.files_scale.set_value(40)
            self.assertEqual(window.requested, {"files": {"enabled": True, "transparency": 40}})
            save.assert_not_called()
            process.assert_not_called()
        self.finish_pending()
        self.assertTrue(window.files_scale.get_sensitive())
        self.assertIn("quit and reopen Files", window.files_status.get_label())
        self.assertIsNone(window.requested)
        self.assertFalse(window.app_switch.get_active())
        self.assertEqual(window.scale.get_value(), 25)

    def test_files_save_error_and_retry_are_visible(self):
        window = self.window
        with patch("sys.stderr"):
            window.files_switch.set_active(True)
            self.finish_pending(False, "read only")
        self.assertIn("read only", window.files_status.get_label())
        self.assertTrue(window.files_retry.get_visible())
        window.on_files_appearance_changed()
        self.finish_pending()
        self.assertFalse(window.files_retry.get_visible())

    def test_files_presets_save_once_and_reset_is_independent(self):
        window = self.window
        for enabled, level in ((False, 0), (True, 10), (True, 25), (True, 50), (False, 25)):
            window.set_files_preset(None, enabled, level)
            self.assertEqual(window.requested, {"files": {"enabled": enabled, "transparency": level}})
            self.finish_pending()
            expected = round(self.ui["files_appearance"].opacity(
                {"enabled": enabled, "transparency": level}, "frost") * 100)
            self.assertIn(f"{expected}% opaque", window.files_opacity.get_label())
            self.assertEqual(window.scale.get_value(), 25)
            self.assertFalse(window.app_switch.get_active())

    def test_restart_cancel_never_quits_files(self):
        with patch.object(self.ui["Gio"].Subprocess, "new") as launch:
            self.window.on_files_restart_confirmed(None, "cancel")
            launch.assert_not_called()

    def test_restart_confirmation_defaults_to_cancel(self):
        from unittest.mock import Mock
        dialog = Mock()
        with patch.object(self.ui["Adw"], "MessageDialog", return_value=dialog) as create:
            self.window.confirm_files_restart(None)
        dialog.set_default_response.assert_called_once_with("cancel")
        dialog.set_close_response.assert_called_once_with("cancel")
        self.assertIn("file operations", create.call_args.kwargs["body"])
        dialog.present.assert_called_once()

    def test_restart_waits_for_exit_then_opens_home(self):
        from unittest.mock import Mock
        process = FakeProcess()
        window = self.window
        with patch.object(self.ui["Gio"].Subprocess, "new", return_value=process) as launch, \
             patch.object(self.ui["Gio"], "bus_watch_name", return_value=77) as watch, \
             patch.object(self.ui["Gio"], "bus_unwatch_name") as unwatch:
            window.on_files_restart_confirmed(None, "restart")
            launch.assert_called_once_with(["nautilus", "--quit"],
                                          self.ui["Gio"].SubprocessFlags.STDOUT_PIPE |
                                          self.ui["Gio"].SubprocessFlags.STDERR_PIPE)
            self.assertTrue(window.on_close(window))
            process.finish()
            watch.assert_called_once()
            connection = Mock()
            window.on_files_vanished(connection, "org.gnome.Nautilus")
            unwatch.assert_called_once_with(77)
            self.assertEqual(connection.call.call_args.args[3], "Open")
            self.assertIn(Path.home().as_uri(), str(connection.call.call_args.args[4]))
            window.on_files_opened(connection, None)
            self.assertTrue(window.files_restart.get_sensitive())
            self.assertIn("restarted", window.files_status.get_label())

    def test_nonzero_quit_checks_actual_files_exit(self):
        from unittest.mock import Mock
        process = Mock()
        process.communicate_utf8_finish.return_value = (True, "", "quit returned nonzero")
        process.get_successful.return_value = False
        connection = Mock()
        window = self.window
        with patch.object(self.ui["Gio"], "bus_get_sync", return_value=connection):
            window.on_files_quit(process, None)
        self.assertEqual(connection.call.call_args.args[3], "NameHasOwner")
        self.assertEqual(connection.call.call_args.args[-2], window.on_files_quit_checked)
        self.assertEqual(connection.call.call_args.args[-1], "quit returned nonzero")
        with patch.object(window, "on_files_vanished") as vanished, patch("sys.stderr") as log:
            connection.call_finish.return_value = GLib.Variant("(b)", (False,))
            window.on_files_quit_checked(connection, None, "quit returned nonzero")
            vanished.assert_called_once_with(connection, "org.gnome.Nautilus")
            self.assertTrue(log.write.called)

    def test_nonzero_quit_does_not_reopen_running_or_unverified_files(self):
        from unittest.mock import Mock
        connection = Mock()
        window = self.window
        with patch.object(window, "on_files_vanished") as vanished, patch("sys.stderr"):
            connection.call_finish.return_value = GLib.Variant("(b)", (True,))
            window.on_files_quit_checked(connection, None, "still running")
            self.assertIn("still running", window.files_status.get_label())
            connection.call_finish.side_effect = GLib.Error("bus failed")
            window.on_files_quit_checked(connection, None, "quit failed")
            self.assertIn("Could not verify Files exit", window.files_status.get_label())
            self.assertIn("bus failed", window.files_status.get_label())
            vanished.assert_not_called()

    def test_restart_failure_and_timeout_are_visible(self):
        window = self.window
        with patch.object(self.ui["Gio"].Subprocess, "new", side_effect=GLib.Error("missing")), \
             patch("sys.stderr"):
            window.on_files_restart_confirmed(None, "restart")
        self.assertTrue(window.files_restart.get_sensitive())
        self.assertIn("missing", window.files_status.get_label())
        with patch("sys.stderr"):
            window.files_restart_expired()
        self.assertIn("not force-killed", window.files_status.get_label())

    def test_app_save_failure_keeps_previous_appearance_and_retry_works(self):
        window = self.window
        with patch("sys.stderr"):
            window.app_switch.set_active(True)
            self.finish_pending(False, "read only")
        self.assertFalse(window.has_css_class("yaru-settings-glass"))
        self.assertFalse(window.app_appearance["enabled"])
        self.assertIn("read only", window.app_status.get_label())
        self.assertTrue(window.app_retry.get_visible())
        window.on_app_appearance_changed()
        self.finish_pending()
        self.assertTrue(window.has_css_class("yaru-settings-glass"))
        self.assertFalse(window.app_retry.get_visible())

    def test_app_css_parses_for_both_modes_schemes_and_slider_limits(self):
        window = self.window
        errors = []
        window.app_css.connect("parsing-error", lambda provider, section, error: errors.append(str(error)))
        with patch.object(window.style_manager, "get_dark") as get_dark:
            for dark in (False, True):
                get_dark.return_value = dark
                for mode in ("frost", "crystal"):
                    window.applied_glass_mode = mode
                    for level in (0, 25, 50):
                        window.app_appearance = {"enabled": True, "transparency": level}
                        window.update_app_style()
                        self.assertTrue(window.has_css_class("yaru-settings-glass"))
        self.assertEqual(errors, [])

    def test_transparent_settings_descriptions_have_full_foreground_contrast(self):
        window = self.window
        manager = window.style_manager
        original = manager.get_color_scheme()
        context = GLib.MainContext.default()
        window.app_appearance = {"enabled": True, "transparency": 50}
        window.applied_glass_mode = "crystal"
        window.present()

        def labels(widget):
            if isinstance(widget, Gtk.Label):
                yield widget
            child = widget.get_first_child()
            while child:
                yield from labels(child)
                child = child.get_next_sibling()

        def luminance(rgb):
            return sum(weight * (v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4)
                       for v, weight in zip(rgb, (.2126, .7152, .0722)))

        try:
            for scheme, floor, boost in (
                (scheme, floor, boost) for scheme, floor in
                ((Adw.ColorScheme.FORCE_LIGHT, .70), (Adw.ColorScheme.FORCE_DARK, .80))
                for boost in (False, True)
            ):
                window.shell_settings["readability_boost"] = boost
                manager.set_color_scheme(scheme)
                window.update_app_style()
                for _ in range(12):
                    while context.pending():
                        context.iteration(False)
                    time.sleep(.025)
                foreground = window.get_style_context().get_color()
                matched = 0
                for label in labels(window):
                    if not (label.has_css_class("dim-label") or label.has_css_class("subtitle")):
                        continue
                    matched += 1
                    self.assertEqual(label.get_opacity(), 1)
                    color = label.get_style_context().get_color()
                    for component in ("red", "green", "blue", "alpha"):
                        self.assertAlmostEqual(getattr(color, component), getattr(foreground, component), places=3)
                    dark = scheme == Adw.ColorScheme.FORCE_DARK
                    base = .12 if dark else .98
                    for backdrop in (0, 1):
                        alpha = floor + (1 - floor) / 2 if boost else floor
                        background = base * alpha + backdrop * (1 - alpha)
                        a, b = sorted((luminance((color.red, color.green, color.blue)),
                                       luminance((background,) * 3)))
                        self.assertGreaterEqual((b + .05) / (a + .05), 4.5)
                self.assertGreater(matched, 3)
        finally:
            manager.set_color_scheme(original)

    def test_disabled_percentage_labels_keep_full_foreground(self):
        window = self.window
        manager = window.style_manager
        original = manager.get_color_scheme()
        context = GLib.MainContext.default()
        try:
            for scheme in (Adw.ColorScheme.FORCE_LIGHT, Adw.ColorScheme.FORCE_DARK):
                manager.set_color_scheme(scheme)
                window.update_app_style()
                window.present()
                for _ in range(12):
                    while context.pending():
                        context.iteration(False)
                    time.sleep(.025)
                self.assertFalse(window.app_scale.get_sensitive())
                self.assertTrue(window.app_percent.get_sensitive())
                color = window.app_percent.get_style_context().get_color()
                foreground = window.get_style_context().get_color()
                for component in ("red", "green", "blue", "alpha"):
                    self.assertAlmostEqual(getattr(color, component), getattr(foreground, component), places=3)
        finally:
            manager.set_color_scheme(original)

    def test_rendered_app_background_is_transparent_but_controls_are_solid(self):
        from gtk_rendering import snapshot_widget
        window = self.window
        manager = window.style_manager
        original = manager.get_color_scheme()
        context = GLib.MainContext.default()
        paintable = Gtk.WidgetPaintable.new(window)
        window.present()
        try:
            for scheme, floor, boost in (
                (scheme, floor, boost) for scheme, floor in
                ((Adw.ColorScheme.FORCE_LIGHT, .70), (Adw.ColorScheme.FORCE_DARK, .80))
                for boost in (False, True)
            ):
                window.shell_settings["readability_boost"] = boost
                manager.set_color_scheme(scheme)
                for mode in ("frost", "crystal"):
                    window.applied_glass_mode = mode
                    for enabled, level in ((False, 50), (True, 0), (True, 25), (True, 50)):
                        window.app_appearance = {"enabled": enabled, "transparency": level}
                        window.update_app_style()
                        for _ in range(12):
                            while context.pending():
                                context.iteration(False)
                            time.sleep(.025)
                        texture = snapshot_widget(window, paintable)
                        image = self.ui["Gdk"].pixbuf_get_from_texture(texture)
                        pixels = image.get_pixels()
                        stride, channels = image.get_rowstride(), image.get_n_channels()
                        alpha = pixels[150 * stride + 12 * channels + 3]
                        expected = 1 - (1 - floor) * level / 50 * (1 if mode == "crystal" else .7)
                        if boost:
                            expected += (1 - expected) / 2
                        if not enabled:
                            expected = 1
                        self.assertAlmostEqual(alpha / 255, expected, delta=.01,
                                               msg=(scheme, mode, enabled, level, alpha))
                        ok, bounds = window.preset.compute_bounds(window)
                        self.assertTrue(ok)
                        x, y = int(bounds.get_x() + 10), int(bounds.get_y() + 10)
                        self.assertLess(y, image.get_height())
                        self.assertEqual(pixels[y * stride + x * channels + 3], 255)
                        self.assertEqual(window.get_opacity(), 1)
        finally:
            manager.set_color_scheme(original)

    def test_builds_are_serialized_and_latest_value_wins(self):
        first, last = FakeProcess(), FakeProcess()
        with patch.object(self.ui["Gio"].Subprocess, "new", side_effect=[first, last]) as launch:
            self.window.scale.set_value(10)
            self.apply_now()
            self.assertEqual(json.loads(launch.call_args.args[0][-1]), {"shell": {"transparency": 10}})
            self.window.scale.set_value(20)
            self.window.scale.set_value(45)
            self.apply_now()
            self.assertEqual(launch.call_count, 1)
            first.finish()
            self.assertEqual(launch.call_count, 2)
            self.assertEqual(json.loads(launch.call_args.args[0][-1]), {"shell": {"transparency": 45}})
            last.finish()
            self.assertEqual(self.window.shell_settings["transparency"], 45)
            self.assertIsNone(self.window.process)

    def test_close_flushes_pending_and_waits(self):
        process = FakeProcess()
        with patch.object(self.ui["Gio"].Subprocess, "new", return_value=process), \
             patch.object(self.window, "close") as close:
            self.window.scale.set_value(35)
            self.assertTrue(self.window.on_close(self.window))
            self.assertFalse(self.window.scale.get_sensitive())
            close.assert_not_called()
            process.finish()
            close.assert_called_once()
            self.assertFalse(self.window.on_close(self.window))

    def test_new_movement_keeps_its_debounce_when_build_finishes(self):
        first, last = FakeProcess(), FakeProcess()
        with patch.object(self.ui["Gio"].Subprocess, "new", side_effect=[first, last]) as launch:
            self.window.scale.set_value(10)
            self.apply_now()
            self.window.scale.set_value(45)
            first.finish()
            self.assertEqual(launch.call_count, 1)
            self.assertNotEqual(self.window.timeout_id, 0)
            self.apply_now()
            self.assertEqual(launch.call_count, 2)
            last.finish()
            self.assertEqual(self.window.shell_settings["transparency"], 45)

    def test_build_error_is_visible_and_does_not_close(self):
        process = FakeProcess(False, "Cannot write stylesheet")
        with patch.object(self.ui["Gio"].Subprocess, "new", return_value=process), \
             patch.object(self.window, "close") as close:
            self.window.scale.set_value(35)
            self.window.on_close(self.window)
            with patch("sys.stderr"):
                process.finish()
            self.assertIn("Cannot write stylesheet", self.window.status.get_label())
            self.assertTrue(self.window.retry.get_visible())
            self.assertTrue(self.window.scale.get_sensitive())
            self.assertFalse(self.window.closing)
            close.assert_not_called()

    def test_reset_applies_even_at_default(self):
        with patch.object(self.window, "confirm_action", side_effect=lambda heading, body, action: action()):
            self.window.on_reset(None)
        self.assertEqual(self.window.requested, {"shell": {"transparency": 25, "glass_mode": "frost",
                                                         "solid": False, "background_blur": True}})
        self.assertNotEqual(self.window.timeout_id, 0)

    def test_preset_cancel_and_confirmation_are_side_effect_free_until_apply(self):
        from unittest.mock import Mock
        dialog = Mock()
        self.window.preset.set_selected(2)
        with patch.object(self.ui["Adw"], "MessageDialog", return_value=dialog) as create, \
             patch.object(self.ui["Gio"].Subprocess, "new") as launch:
            self.window.confirm_preset(None)
            callback = dialog.connect.call_args.args[1]
            callback(dialog, "cancel")
            self.assertIsNone(self.window.requested)
            launch.assert_not_called()
            dialog.set_default_response.assert_called_with("cancel")
            self.assertIn("Disabled → Enabled", create.call_args.kwargs["body"])
            self.assertIn("Glass style: Frost → Crystal", create.call_args.kwargs["body"])
            self.assertIn("Transparency level: 25% → 50%", create.call_args.kwargs["body"])
            self.assertIn("wallpapers stay unchanged", create.call_args.kwargs["body"])
            callback(dialog, "apply")
        self.assertEqual(self.window.requested, self.ui["preset_values"]("Clear Crystal"))
        self.finish_pending()
        self.assertIn("Clear Crystal", self.window.overview.get_label())
        self.assertTrue(self.window.app_appearance["enabled"])
        self.assertTrue(self.window.files_saved["enabled"])

    def test_solid_and_boost_preserve_independent_controls(self):
        self.window.scale.set_value(17)
        self.window.solid_switch.set_active(True)
        self.window.boost_switch.set_active(True)
        self.finish_pending()
        self.assertFalse(self.window.scale.get_sensitive())
        self.assertEqual(self.window.scale.get_value(), 17)
        self.assertFalse(self.window.app_appearance["enabled"])
        self.assertFalse(self.window.files_saved["enabled"])
        self.assertTrue(self.window.shell_settings["readability_boost"])
        self.assertIn("Custom", self.window.overview.get_label())

    def test_blur_switch_preserves_other_sections_and_saved_preference(self):
        self.assertTrue(self.window.blur_switch.get_active())
        self.window.blur_switch.set_active(False)
        self.assertEqual(self.window.requested, {"shell": {"background_blur": False}})
        self.finish_pending()
        self.assertFalse(self.window.shell_settings["background_blur"])
        self.assertFalse(self.window.app_appearance["enabled"])
        self.assertFalse(self.window.files_saved["enabled"])
        self.window.solid_switch.set_active(True)
        self.window.blur_switch.set_active(True)
        self.finish_pending()
        self.assertTrue(self.window.shell_settings["background_blur"])
        self.assertIn("suppressed by Solid", self.window.overview.get_label())
        self.window.solid_switch.set_active(False)
        self.finish_pending()
        self.assertTrue(self.window.blur_switch.get_active())

    def test_reset_confirmation_shows_readable_before_after_values(self):
        from unittest.mock import Mock
        self.window.shell_settings["transparency"] = 10
        self.window.shell_settings["glass_mode"] = "crystal"
        dialog = Mock()
        with patch.object(self.ui["Adw"], "MessageDialog", return_value=dialog) as create:
            self.window.confirm_reset("Shell", {
                "shell": {"transparency": 25, "glass_mode": "frost", "solid": False}})
        self.assertEqual(create.call_args.kwargs["heading"], "Reset Shell?")
        body = create.call_args.kwargs["body"]
        self.assertIn("Shell\n", body)
        self.assertIn("Transparency level: 10% → 25%", body)
        self.assertIn("Glass style: Crystal → Frost", body)
        self.assertIn("Solid backgrounds: Off → Off", body)
        self.assertIn("Only the listed settings will be reset.", body)
        self.assertNotIn("{", body)
        dialog.set_default_response.assert_called_once_with("cancel")

    def test_repair_confirmation_does_not_present_fallback_as_current_value(self):
        from unittest.mock import Mock
        self.window.invalid_sections.add("shell")
        dialog = Mock()
        with patch.object(self.ui["Adw"], "MessageDialog", return_value=dialog) as create:
            self.window.confirm_reset("invalid preferences", {
                "shell": {"transparency": 25, "glass_mode": "frost"}})
        self.assertEqual(create.call_args.kwargs["heading"], "Repair invalid preferences?")
        body = create.call_args.kwargs["body"]
        self.assertIn("Invalid or unavailable → 25%", body)
        self.assertIn("Only invalid settings in the listed sections will be replaced with defaults.", body)

    def test_reset_and_wallpaper_restore_require_confirmation(self):
        from unittest.mock import Mock
        dialog = Mock()
        with patch.object(self.ui["Adw"], "MessageDialog", return_value=dialog):
            self.window.on_reset(None)
            self.assertIsNone(self.window.requested)
            dialog.connect.call_args.args[1](dialog, "cancel")
            self.assertIsNone(self.window.requested)
        with patch.object(self.ui["Adw"], "MessageDialog", return_value=Mock()), \
             patch.object(self.ui["wallpapers"], "restore_slot") as restore:
            self.window.confirm_wallpaper_restore(None, "picture-uri")
            restore.assert_not_called()

    def test_reset_app_leaves_shell_files_and_boost_unchanged(self):
        self.window.shell_settings["readability_boost"] = True
        before_shell = self.window.shell_settings.copy()
        before_files = self.window.files_saved.copy()
        with patch.object(self.window, "confirm_action", side_effect=lambda heading, body, action: action()):
            self.window.confirm_reset("Settings app", {"app": {"enabled": False, "transparency": 25}})
        self.finish_pending()
        self.assertEqual(self.window.shell_settings, before_shell)
        self.assertEqual(self.window.files_saved, before_files)

    def test_later_files_change_invalidates_restart_status(self):
        self.window.finish_files_restart()
        self.assertTrue(self.window.files_live_confirmed)
        self.window.on_theme_changed()
        self.assertFalse(self.window.files_live_confirmed)
        self.assertIn("unknown", self.window.files_status.get_label())
        self.window.finish_files_restart()
        self.window.files_switch.set_active(True)
        self.finish_pending()
        self.assertFalse(self.window.files_live_confirmed)
        self.assertIn("restart required", self.window.files_status.get_label())
        self.assertIn("unknown", self.window.overview.get_label())

    def test_invalid_worker_output_never_claims_applied(self):
        process = FakeProcess()
        self.window.app_switch.set_active(True)
        with patch.object(self.ui["Gio"].Subprocess, "new", return_value=process), patch("sys.stderr"):
            self.apply_now()
            process.stdout = "not valid JSON"
            process.finish()
        self.assertIn("uncertain", self.window.status.get_label())
        self.assertFalse(self.window.app_appearance["enabled"])

    def test_failed_coordinated_preset_retries_the_complete_operation(self):
        target = self.ui["preset_values"]("Clear Crystal")
        self.window.queue_patch(target)
        with patch("sys.stderr"):
            self.finish_pending(False, "disk full")
        self.assertEqual(self.window.pages.get_visible_child_name(), "shell")
        self.assertFalse(self.window.app_appearance["enabled"])
        self.window.app_retry.emit("clicked")
        self.assertEqual(self.window.requested, target)
        self.finish_pending()
        self.assertIn("Clear Crystal", self.window.overview.get_label())

    def test_multiple_invalid_preferences_offer_explicit_complete_repair(self):
        from unittest.mock import Mock
        globals_ = self.ui["SettingsWindow"].__init__.__globals__
        with patch.dict(globals_, {"load_settings": Mock(side_effect=ValueError("invalid Shell")),
                                   "load_app_appearance": Mock(side_effect=ValueError("invalid app"))}), \
             patch.object(self.ui["files_appearance"], "load", side_effect=ValueError("invalid Files")), \
             patch("sys.stderr"):
            broken = self.ui["SettingsWindow"](self.app)
        try:
            self.assertEqual(broken.invalid_sections, {"shell", "app", "files"})
            self.assertTrue(broken.repair.get_visible())
            self.assertIn("not saved", broken.overview.get_label())
            self.assertIn("Saved preset: Unknown", broken.overview.get_label())
            with patch.object(broken, "confirm_action") as confirmation:
                broken.confirm_repair(None)
                self.assertIsNone(broken.requested)
                confirmation.call_args.args[2]()
            self.assertEqual(set(broken.requested), {"shell", "app", "files"})
            self.assertEqual(set(broken.requested["shell"]),
                             {"transparency", "glass_mode", "solid", "readability_boost", "background_blur"})
        finally:
            if broken.timeout_id:
                GLib.source_remove(broken.timeout_id)
            broken.destroy()

    def test_launch_failure_is_reported(self):
        with patch.object(self.ui["Gio"].Subprocess, "new", side_effect=GLib.Error("Cannot start builder")), \
             patch("sys.stderr"):
            self.window.scale.set_value(35)
            self.apply_now()
        self.assertIsNone(self.window.process)
        self.assertIn("Cannot start builder", self.window.status.get_label())
        self.assertTrue(self.window.retry.get_visible())

    def test_mixed_style_and_slider_changes_share_latest_snapshot(self):
        first, last = FakeProcess(), FakeProcess()
        with patch.object(self.ui["Gio"].Subprocess, "new", side_effect=[first, last]) as launch:
            self.window.scale.set_value(10)
            self.apply_now()
            self.window.mode.set_selected(1)
            self.window.scale.set_value(40)
            self.apply_now()
            first.finish()
            self.assertEqual(launch.call_count, 2)
            command = launch.call_args.args[0]
            self.assertEqual(json.loads(command[-1]), {"shell": {"glass_mode": "crystal", "transparency": 40}})
            last.finish()
            self.assertEqual(self.window.shell_settings["glass_mode"], "crystal")
            self.assertEqual(self.window.shell_settings["transparency"], 40)

    def test_cancel_wallpaper_chooser_changes_nothing(self):
        from unittest.mock import Mock
        chooser = Mock()
        with patch.object(self.ui["wallpapers"], "set_wallpaper") as setter:
            self.window.on_wallpaper_chosen(chooser, Gtk.ResponseType.CANCEL, "picture-uri")
            setter.assert_not_called()
            chooser.destroy.assert_called_once()

    def test_wallpaper_previews_are_independent_scaled_and_refreshable(self):
        from unittest.mock import Mock
        pixbuf = self.ui["GdkPixbuf"].Pixbuf
        colorspace = self.ui["GdkPixbuf"].Colorspace.RGB
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("light.png", "dark.png")]
            for path, color in zip(paths, (0xff0000ff, 0x0000ffff)):
                image = pixbuf.new(colorspace, False, 8, 640, 320)
                image.fill(color)
                image.savev(str(path), "png", [], [])
            values = dict(zip(self.ui["wallpapers"].KEYS, (path.as_uri() for path in paths)))
            self.window.background = Mock()
            self.window.background.get_string.side_effect = values.__getitem__
            self.window.refresh_wallpapers()
            for key, color in zip(values, ((255, 0, 0), (0, 0, 255))):
                image = self.ui["Gdk"].pixbuf_get_from_texture(self.window.wallpaper_previews[key].get_paintable())
                self.assertEqual((image.get_width(), image.get_height()), (128, 64))
                self.assertEqual(tuple(image.get_pixels()[:3]), color)
                self.assertFalse(self.window.wallpaper_preview_errors[key].get_visible())
            values["picture-uri"] = paths[1].as_uri()
            self.window.refresh_wallpapers()
            image = self.ui["Gdk"].pixbuf_get_from_texture(self.window.wallpaper_previews["picture-uri"].get_paintable())
            self.assertEqual(tuple(image.get_pixels()[:3]),
                             (0, 0, 255))

    def test_missing_wallpaper_clears_thumbnail_and_reports_error(self):
        from unittest.mock import Mock
        self.window.background = Mock()
        self.window.background.get_string.return_value = "file:///nonexistent/yaru-preview-test.png"
        with patch("sys.stderr"):
            self.window.refresh_wallpapers()
        for key in self.ui["wallpapers"].KEYS:
            self.assertIsNone(self.window.wallpaper_previews[key].get_paintable())
            self.assertTrue(self.window.wallpaper_preview_errors[key].get_visible())
            self.assertIn("Preview unavailable", self.window.wallpaper_preview_errors[key].get_label())

    def test_empty_wallpaper_has_placeholder_without_error(self):
        from unittest.mock import Mock
        self.window.background = Mock()
        self.window.background.get_string.return_value = ""
        self.window.refresh_wallpapers()
        for key in self.ui["wallpapers"].KEYS:
            self.assertIsNone(self.window.wallpaper_previews[key].get_paintable())
            self.assertFalse(self.window.wallpaper_preview_errors[key].get_visible())
            self.assertEqual(self.window.wallpaper_labels[key].get_label(), "No image selected")


if __name__ == "__main__":
    unittest.main()
