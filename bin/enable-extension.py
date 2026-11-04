#!/usr/bin/env python3
"""Request one serialized GNOME Shell extension enable update.

usage: enable-extension.py UUID [UUID ...]
Exit 0 when all requested extensions become active, 2 when the request was
accepted but a relogin may be needed, and 1 for validation or activation errors.
"""
import sys
import time
from pathlib import Path
from typing import Iterable

from gi.repository import Gio, GLib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src/yaru_glass"))
from extension_compatibility import (  # noqa: E402
    UBUNTU_RELEASES,
    ExtensionCompatibilityError,
    running_shell_version,
    validate_installed_extension,
    validate_ubuntu_extension,
)
import diagnostics

EXTENSIONS_IFACE = "org.gnome.Shell.Extensions"
EXTENSIONS_PATH = "/org/gnome/Shell/Extensions"
ACTIVE = 1
ERROR = 3
OUT_OF_DATE = 4
WAIT_SECONDS = 5.0
POLL_SECONDS = 0.25


def validate_requested(uuids: Iterable[str], shell_version: str) -> list[str]:
    validated = []
    for uuid in dict.fromkeys(uuids):
        if uuid in UBUNTU_RELEASES.get(shell_version, {}).get("packages", {}):
            if validate_ubuntu_extension(uuid, shell_version) is None:
                raise ExtensionCompatibilityError(f"{uuid}: Ubuntu extension is not installed")
        else:
            validate_installed_extension(uuid, shell_version)
        validated.append(uuid)
    if not validated:
        raise ExtensionCompatibilityError("no installed extensions were selected")
    return validated


def request_enable(settings, uuids: Iterable[str]) -> None:
    """Make one enabled-extensions update for the whole validated batch."""
    uuids = list(dict.fromkeys(uuids))
    enabled = list(settings.get_strv("enabled-extensions"))
    disabled = list(settings.get_strv("disabled-extensions"))
    desired_enabled = list(dict.fromkeys([*enabled, *uuids]))
    desired_disabled = [uuid for uuid in disabled if uuid not in uuids]

    if desired_disabled != disabled:
        if not settings.set_strv("disabled-extensions", desired_disabled):
            raise ExtensionCompatibilityError("could not update disabled-extensions")
    if desired_enabled != enabled:
        if not settings.set_strv("enabled-extensions", desired_enabled):
            raise ExtensionCompatibilityError("could not request extension activation")

    # Let the Shell see the final extension list before re-enabling user extensions.
    if settings.get_boolean("disable-user-extensions"):
        if not settings.set_boolean("disable-user-extensions", False):
            raise ExtensionCompatibilityError("could not enable user extensions")
    Gio.Settings.sync()

    if list(settings.get_strv("enabled-extensions")) != desired_enabled:
        raise ExtensionCompatibilityError("GNOME did not retain the requested enabled-extensions list")
    if list(settings.get_strv("disabled-extensions")) != desired_disabled:
        raise ExtensionCompatibilityError("GNOME did not retain the requested disabled-extensions list")
    if settings.get_boolean("disable-user-extensions"):
        raise ExtensionCompatibilityError("GNOME user extensions remain globally disabled")


def _unpack(value):
    return value.unpack() if hasattr(value, "unpack") else value


def extension_info(connection, uuid: str) -> dict:
    result = connection.call_sync(
        EXTENSIONS_IFACE,
        EXTENSIONS_PATH,
        EXTENSIONS_IFACE,
        "GetExtensionInfo",
        GLib.Variant("(s)", (uuid,)),
        GLib.VariantType("(a{sv})"),
        Gio.DBusCallFlags.NONE,
        1000,
        None,
    ).unpack()[0]
    return {key: _unpack(value) for key, value in result.items()}


def wait_for_activation(
    uuids: Iterable[str], *, timeout: float = WAIT_SECONDS, interval: float = POLL_SECONDS,
    connection=None,
) -> tuple[list[str], list[str]]:
    """Return active and pending UUIDs; fail promptly for reported Shell errors."""
    if connection is None:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    requested = list(uuids)
    deadline = time.monotonic() + timeout
    pending = requested
    while pending and time.monotonic() < deadline:
        still_pending = []
        for uuid in pending:
            try:
                info = extension_info(connection, uuid)
            except GLib.Error:
                still_pending.append(uuid)
                continue
            state = info.get("state")
            if state == ACTIVE:
                continue
            if state in (ERROR, OUT_OF_DATE):
                detail = info.get("error") or info.get("error-message") or f"state {state}"
                raise ExtensionCompatibilityError(f"{uuid}: GNOME Shell activation failed: {detail}")
            still_pending.append(uuid)
        pending = still_pending
        if pending and time.monotonic() < deadline:
            time.sleep(min(interval, max(0, deadline - time.monotonic())))
    active = [uuid for uuid in requested if uuid not in pending]
    return active, pending


def main() -> int:
    diagnostics.event("extensions", "activate", "requested")
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1
    try:
        shell_version = running_shell_version()
        uuids = validate_requested(sys.argv[1:], shell_version)
        settings = Gio.Settings.new("org.gnome.shell")
        request_enable(settings, uuids)
        active, pending = wait_for_activation(uuids)
    except (ExtensionCompatibilityError, GLib.Error) as error:
        diagnostics.event("extensions", "activate", "failure", level="ERROR", error=error)
        print(f"Extension activation error: {error}", file=sys.stderr)
        return 1

    for uuid in active:
        diagnostics.event("extensions", "activate", "confirmed", extension=uuid)
        print(f"    {uuid}: active")
    if pending:
        diagnostics.event("extensions", "activate", "pending", level="WARNING", count=len(pending))
        print(
            "    Activation request was accepted, but these extensions are not yet active: "
            + ", ".join(pending)
            + ". Log out/in to retry activation.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
