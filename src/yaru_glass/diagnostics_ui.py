"""Asynchronous local diagnostic viewer; no appearance controls or uploads."""
import json
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

import diagnostics


class DiagnosticsWindow(Adw.Window):
    def __init__(self, parent):
        super().__init__(title="Yaru Glass Diagnostics", transient_for=parent, modal=False)
        self.set_default_size(700, 560)
        self.closed = False
        self.busy = False
        self.stored_verbose = False
        self.connect("close-request", self.on_close)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.append(Adw.HeaderBar())
        description = Gtk.Label(
            label="Local logs only. No automatic uploads. Reports exclude personal paths, "
                  "credentials and full settings. Review reports before sharing.",
            wrap=True, xalign=0, margin_start=16, margin_end=16)
        body.append(description)
        toolbar = Gtk.Box(spacing=8, margin_start=16, margin_end=16)
        self.level = Gtk.DropDown(model=Gtk.StringList.new(["All", "Info", "Warnings", "Errors"]))
        self.level.update_property([Gtk.AccessibleProperty.LABEL], ["Minimum log level"])
        toolbar.append(self.level)
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
        self.text.update_property([Gtk.AccessibleProperty.LABEL], ["Recent sanitized diagnostic records"])
        scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True,
                                    margin_start=16, margin_end=16, margin_bottom=16)
        scroll.set_child(self.text)
        body.append(scroll)
        self.set_content(body)
        self.level.connect("notify::selected", self.refresh)
        self.verbose_handler = self.verbose_switch.connect("notify::active", self.change_verbose)
        self.refresh()

    def on_close(self, *_args):
        self.closed = True
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
            self.text.get_buffer().set_text("\n".join(
                json.dumps(record, sort_keys=True) for record in data["records"]))
            self.verbose_switch.handler_block(self.verbose_handler)
            try:
                self.verbose_switch.set_active(verbose)
            finally:
                self.verbose_switch.handler_unblock(self.verbose_handler)
            self.status.set_label(f"{len(data['records'])} recent records. "
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
            self, "Save a diagnostic report?",
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
        if response != "save":
            return
        chooser = Gtk.FileChooserNative.new("Save sanitized diagnostic report", self,
                                             Gtk.FileChooserAction.SAVE, "Save", "Cancel")
        chooser.set_current_name("yaru-glass-diagnostics.json")
        chooser.connect("response", self.on_export_chosen)
        chooser.show()

    def on_export_chosen(self, chooser, response):
        file = chooser.get_file() if response == Gtk.ResponseType.ACCEPT else None
        chooser.destroy()
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
