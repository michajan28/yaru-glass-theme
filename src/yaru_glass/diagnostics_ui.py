"""Asynchronous local diagnostic viewer; no appearance controls or uploads."""
from datetime import datetime
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

import diagnostics


def format_record(record):
    timestamp = datetime.fromisoformat(record["timestamp"]).astimezone().isoformat(
        sep=" ", timespec="seconds")
    phase = {"start": "Started", "success": "Completed", "failure": "Failed",
             "requested": "Requested", "confirmed": "Confirmed", "pending": "Pending"}[record["phase"]]
    summary = (f"{timestamp}  [{record['level']}]\n"
               f"{record['component'].replace('_', ' ').title()} / "
               f"{record['action'].replace('_', ' ').title()} - {phase}\n")
    details = []
    for key, value in sorted(record["fields"].items()):
        if type(value) is bool:
            value = "Yes" if value else "No"
        details.append(f"{key.replace('_', ' ').capitalize()}: {value}")
    failure = record.get("error")
    if failure:
        details.append("Error: " + failure["type"])
        if "errno" in failure:
            details.append("System error: " + failure["errno"])
        details.extend(f"At: {frame['file']}:{frame['line']}" for frame in failure.get("frames", []))
    details.append(f"Operation: {record['operation']}")
    details.append(f"Version: {record['version']}  |  Process: {record['pid']}")
    return summary, "\n".join(details) + "\n\n"


class DiagnosticsPage(Gtk.Box):
    def __init__(self, parent):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                         margin_top=20, margin_bottom=20)
        self.parent = parent
        self.closed = False
        self.busy = False
        self.export_chooser = None
        self.stored_verbose = False
        body = self
        description = Gtk.Label(
            label="Local logs only. No automatic uploads. Reports exclude personal paths, "
                  "credentials and full settings. Review reports before sharing.",
            wrap=True, xalign=0, margin_start=16, margin_end=16)
        body.append(description)
        toolbar = Gtk.Box(spacing=8, margin_start=16, margin_end=16)
        self.level = Gtk.DropDown(model=Gtk.StringList.new(["All", "Info", "Warnings", "Errors"]))
        self.level.update_property([Gtk.AccessibleProperty.LABEL], ["Minimum log level"])
        body.append(self.level)
        self.level.set_margin_start(16)
        self.level.set_margin_end(16)
        self.level.set_halign(Gtk.Align.START)
        self.refresh_button = Gtk.Button(label="Refresh")
        self.refresh_button.connect("clicked", self.refresh)
        toolbar.append(self.refresh_button)
        self.copy_button = Gtk.Button(label="Copy")
        self.copy_button.connect("clicked", self.copy)
        toolbar.append(self.copy_button)
        self.save_button = Gtk.Button(label="Save report…")
        self.save_button.connect("clicked", self.confirm_export)
        toolbar.append(self.save_button)
        body.append(toolbar)
        self.verbose_switch = Adw.SwitchRow(title="Verbose diagnostics",
                                            subtitle="Additional safe events; no personal data")
        group = Adw.PreferencesGroup(margin_start=16, margin_end=16)
        group.add(self.verbose_switch)
        body.append(group)
        self.status = Gtk.Label(xalign=0, wrap=True, selectable=True,
                                margin_start=16, margin_end=16)
        body.append(self.status)
        self.text = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.text.set_left_margin(12)
        self.text.set_right_margin(12)
        self.text.set_top_margin(12)
        self.text.set_bottom_margin(12)
        self.text.set_pixels_above_lines(2)
        buffer = self.text.get_buffer()
        buffer.create_tag("summary", weight=700, pixels_above_lines=6)
        buffer.create_tag("details", scale=.9, left_margin=20)
        buffer.create_tag("error", weight=700, underline=1)
        self.text.update_property([Gtk.AccessibleProperty.LABEL], ["Recent sanitized diagnostic records"])
        scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True,
                                    margin_start=16, margin_end=16, margin_bottom=16)
        scroll.set_child(self.text)
        body.append(scroll)
        self.level.connect("notify::selected", self.refresh)
        self.verbose_handler = self.verbose_switch.connect("notify::active", self.change_verbose)
        self.refresh()

    def on_close(self, *_args):
        self.closed = True
        if self.export_chooser is not None:
            self.export_chooser.destroy()
            self.export_chooser = None
        return False

    def run_job(self, work, finished, action="read", failed=None):
        if self.busy:
            return
        self.busy = True
        for control in (self.refresh_button, self.copy_button, self.save_button,
                        self.verbose_switch, self.level):
            control.set_sensitive(False)
        self.status.set_label("Reading local diagnostics…")

        def complete(result, error):
            if self.closed:
                return GLib.SOURCE_REMOVE
            self.busy = False
            for control in (self.refresh_button, self.copy_button, self.save_button,
                            self.verbose_switch, self.level):
                control.set_sensitive(True)
            if error is not None:
                self.status.set_label(
                    f"Diagnostics unavailable ({type(error).__name__}). "
                    "Check local storage permissions or the report destination; no success is confirmed.")
                self.status.add_css_class("error")
                if failed is not None:
                    failed()
            else:
                self.status.remove_css_class("error")
                finished(result)
            return GLib.SOURCE_REMOVE

        def run():
            try:
                result = work()
            except (OSError, ValueError, GLib.Error) as exc:
                diagnostics.event("diagnostics", action, "failure", level="ERROR", error=exc)
                GLib.idle_add(complete, None, exc)
            else:
                GLib.idle_add(complete, result, None)

        threading.Thread(target=run, daemon=True).start()

    def refresh(self, *_args):
        level = diagnostics.LEVELS[self.level.get_selected()]

        def work():
            return diagnostics.read_records(200, level), diagnostics.verbose()

        def finished(result):
            data, verbose = result
            self.stored_verbose = verbose
            buffer = self.text.get_buffer()
            buffer.set_text("")
            for record in reversed(data["records"]):
                summary, details = format_record(record)
                tags = ("summary", "error") if record["level"] in {"ERROR", "WARNING"} else ("summary",)
                buffer.insert_with_tags_by_name(buffer.get_end_iter(), summary, *tags)
                buffer.insert_with_tags_by_name(buffer.get_end_iter(), details, "details")
            self.verbose_switch.handler_block(self.verbose_handler)
            try:
                self.verbose_switch.set_active(verbose)
            finally:
                self.verbose_switch.handler_unblock(self.verbose_handler)
            self.status.set_label(f"{len(data['records'])} recent events, newest first. "
                                  f"{data['invalid_records']} invalid records omitted.")

        self.run_job(work, finished)

    def copy(self, *_args):
        buffer = self.text.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        self.get_clipboard().set(text)
        self.status.set_label("Sanitized visible records copied. Review before sharing.")

    def change_verbose(self, *_args):
        enabled = self.verbose_switch.get_active()

        def finished(_result):
            self.stored_verbose = enabled
            self.status.set_label("Verbose diagnostics enabled." if enabled
                                  else "Verbose diagnostics disabled.")

        def failed():
            self.verbose_switch.handler_block(self.verbose_handler)
            try:
                self.verbose_switch.set_active(self.stored_verbose)
            finally:
                self.verbose_switch.handler_unblock(self.verbose_handler)

        self.run_job(lambda: diagnostics.set_verbose(enabled), finished,
                     action="verbose", failed=failed)

    def confirm_export(self, *_args):
        dialog = Adw.MessageDialog.new(
            self.parent, "Save a diagnostic report?",
            "Includes up to 1,000 sanitized recent events, project/GNOME version and known "
            "extension states. No credentials, personal paths, full preferences or journal "
            "dump. Choose a new file (existing files are never overwritten). "
            "Save locally and review before sharing. Nothing is uploaded.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Choose destination…")
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self.choose_export)
        dialog.present()

    def choose_export(self, _dialog, response):
        if response != "save" or self.closed or self.busy:
            return
        if self.export_chooser is not None:
            return
        chooser = Gtk.FileChooserNative.new("Save sanitized diagnostic report", self.parent,
                                             Gtk.FileChooserAction.SAVE, "Save", "Cancel")
        chooser.set_modal(True)
        chooser.set_current_name("yaru-glass-diagnostics.json")
        chooser.connect("response", self.on_export_chosen)
        self.export_chooser = chooser
        chooser.show()

    def on_export_chosen(self, chooser, response):
        file = chooser.get_file() if response == Gtk.ResponseType.ACCEPT else None
        chooser.destroy()
        self.export_chooser = None
        if self.closed:
            return
        if response != Gtk.ResponseType.ACCEPT:
            return
        path = file.get_path() if file else None
        if not path:
            self.status.set_label("Choose a local destination; no report was saved.")
            self.status.add_css_class("error")
            return
        self.run_job(lambda: diagnostics.export_report(path),
                     lambda _: self.status.set_label("Sanitized report saved locally. Review before sharing."),
                     action="export")
