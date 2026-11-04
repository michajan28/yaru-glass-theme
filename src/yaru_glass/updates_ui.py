"""Native, asynchronous controls for the shared updater CLI."""
import json
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

import diagnostics
import updates


class UpdatesWindow(Adw.Window):
    def __init__(self, parent, root):
        super().__init__(title="Yaru Glass Updates", transient_for=parent, modal=False,
                         destroy_with_parent=True)
        self.parent = parent
        self.root = root
        self.process = None
        self.installing = False
        self.closed = False
        self.available = None
        self.connect("close-request", self.on_close)
        self.set_default_size(440, 400)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.append(Adw.HeaderBar())
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                          margin_start=20, margin_end=20, margin_bottom=20)
        self.version_label = Gtk.Label(xalign=0, wrap=True)
        try:
            installed = updates.read_version(Path.home() / ".local/share/yaru-glass")
            self.version_label.set_label(f"Installed version: {installed}")
        except (OSError, RuntimeError) as exc:
            self.version_label.set_label(f"Installed version unavailable: {exc}")
        content.append(self.version_label)
        content.append(Gtk.Label(
            label="Manually check stable public GitHub releases for this account. "
                  "No login required. Preferences, wallpapers and extensions are preserved.",
            wrap=True, xalign=0))
        self.status = Gtk.Label(label="No check performed.", xalign=0, wrap=True, selectable=True)
        content.append(self.status)
        self.release_link = Gtk.LinkButton.new_with_label(
            f"https://github.com/{updates.REPOSITORY}/releases", "Release notes")
        self.release_link.set_halign(Gtk.Align.START)
        content.append(self.release_link)
        self.check_button = Gtk.Button(label="Check for updates")
        self.check_button.connect("clicked", self.check)
        content.append(self.check_button)
        self.install_button = Gtk.Button(label="Install update…", sensitive=False)
        self.install_button.connect("clicked", self.confirm_install)
        content.append(self.install_button)
        self.finish_button = Gtk.Button(label="Close Settings to finish", visible=False)
        self.finish_button.connect("clicked", self.finish)
        content.append(self.finish_button)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(content)
        body.append(scroll)
        self.set_content(body)

    def on_close(self, *_args):
        if self.installing:
            self.status.set_label("Please wait for installation or recovery to finish.")
            return True
        self.closed = True
        return False

    def check(self, *_args):
        self.available = None
        self.start(["check", "--json"], False)

    def parent_busy(self):
        return (self.parent.process is not None or self.parent.requested is not None or
                self.parent.timeout_id or not self.parent.files_restart.get_sensitive() or
                getattr(self.parent, "update_installed", False))

    def confirm_install(self, *_args):
        if self.process is not None or self.available is None:
            return
        if self.parent_busy():
            self.error("Finish pending appearance changes or Files restart before installing.")
            return
        dialog = Adw.MessageDialog.new(
            self, f"Install Yaru Glass {self.available}?",
            "The verified app and theme files will be replaced for this account. "
            "Your customization and original backup stay unchanged. "
            "Settings must be closed and reopened afterward. Files will not restart automatically.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("install", "Install update")
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self.on_confirmed, self.available)
        dialog.present()

    def on_confirmed(self, _dialog, response, selected):
        if response != "install":
            return
        if self.parent_busy():
            self.error("Another appearance operation started. Finish it and retry.")
            return
        self.start(["install", "--yes", "--json", "--target", selected], True)

    def start(self, arguments, installing):
        if self.process is not None:
            return
        self.installing = installing
        self.parent.update_installing = installing
        if installing:
            self.parent.pages.set_sensitive(False)
        self.check_button.set_sensitive(False)
        self.install_button.set_sensitive(False)
        self.status.remove_css_class("error")
        self.status.set_label("Downloading, verifying and installing… Please wait."
                              if installing else "Checking GitHub releases…")
        try:
            operation = diagnostics.new_operation()
            self.process = Gio.Subprocess.new(
                ["/usr/bin/env", f"YARU_GLASS_OPERATION_ID={operation}", "/usr/bin/python3",
                 str(self.root / "bin/yaru-glass-update"), *arguments],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
            self.process.communicate_utf8_async(None, None, self.completed, None)
        except GLib.Error as exc:
            self.reset_busy()
            self.error(f"Could not start the updater: {exc}")

    def reset_busy(self):
        was_installing = self.installing
        self.process = None
        self.installing = False
        self.parent.update_installing = False
        if was_installing and not getattr(self.parent, "update_installed", False):
            self.parent.pages.set_sensitive(True)
        self.check_button.set_sensitive(True)
        self.install_button.set_sensitive(self.available is not None)

    def completed(self, process, result, _data):
        was_installing = self.installing
        self.reset_busy()
        if self.closed:
            return
        try:
            _ok, stdout, stderr = process.communicate_utf8_finish(result)
            data = json.loads(stdout)
            if not isinstance(data, dict) or not isinstance(data.get("status"), str):
                raise ValueError("Invalid updater response")
            if not process.get_successful():
                if was_installing and data.get("recovery_required") is True:
                    self.parent.update_installed = True
                    self.parent.pages.set_sensitive(False)
                    self.finish_button.set_visible(True)
                self.error(data.get("message") or stderr.strip() or "Update failed; inspect Diagnostics.")
                return
            status = data["status"]
            if status in {"available", "up-to-date"}:
                for key in ("installed_version", "available_version"):
                    updates.version(data[key])
                expected_url = (f"https://github.com/{updates.REPOSITORY}/releases/tag/"
                                f"v{data['available_version']}")
                if data["release_url"] != expected_url:
                    raise ValueError("Unexpected release URL")
                self.version_label.set_label(f"Installed version: {data['installed_version']}")
                self.available = data["available_version"] if status == "available" else None
                self.release_link.set_uri(expected_url)
                self.status.set_label(f"Version {self.available} is available." if self.available
                                      else "You are up to date; no newer stable release is available.")
                self.install_button.set_sensitive(self.available is not None)
            elif status == "installed" and was_installing:
                updates.version(data["installed_version"])
                if (data.get("settings_relaunch_required") is not True or
                        type(data.get("shell_reload_requested")) is not bool or
                        type(data.get("files_restart_required")) is not bool):
                    raise ValueError("Incomplete installation result")
                self.parent.update_installed = True
                self.parent.pages.set_sensitive(False)
                self.available = None
                self.install_button.set_sensitive(False)
                self.check_button.set_sensitive(False)
                self.finish_button.set_visible(True)
                self.version_label.set_label(f"Installed version: {data['installed_version']}")
                self.status.set_label(
                    "Update installed. Close Settings and reopen it from the application launcher. "
                    + ("Shell reload requested. " if data["shell_reload_requested"] else
                       "Inactive project theme was not activated. ")
                    + "Restart Files yourself when convenient; it has not been restarted.")
            else:
                raise ValueError("Unexpected updater result")
        except (GLib.Error, ValueError, KeyError, TypeError, RuntimeError) as exc:
            self.available = None
            self.install_button.set_sensitive(False)
            if was_installing:
                # An invalid response cannot prove that the old payload is still installed.
                self.parent.update_installed = True
                self.parent.pages.set_sensitive(False)
                self.finish_button.set_visible(True)
            self.error(f"Updater result unavailable; reopen Settings and inspect Diagnostics. {exc}")

    def error(self, message):
        diagnostics.event("updater", "protocol", "failure", level="ERROR")
        self.status.add_css_class("error")
        self.status.set_label(message)

    def finish(self, *_args):
        if not self.installing:
            self.close()
            self.parent.close()
