"""Exact GNOME Shell extension releases accepted by Yaru Glass integrations."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Mapping
import xml.etree.ElementTree as ET


USER_EXTENSIONS = Path.home() / ".local/share/gnome-shell/extensions"
SYSTEM_EXTENSIONS = Path("/usr/share/gnome-shell/extensions")

# version_tag is the immutable release identifier used by extensions.gnome.org.
RELEASES = {
    "46": {
        "user-theme@gnome-shell-extensions.gcampax.github.com": {
            "version": 60, "version_tag": "61748",
        },
        "blur-my-shell@aunetx": {"version": 77, "version_tag": "77413"},
        "just-perfection-desktop@just-perfection": {
            "version": 37, "version_tag": "74466",
        },
        "auto-theme-switcher@amritashan.github.io": {
            "version": 11, "version_tag": "72675",
        },
        "logomenu@aryan_k": {"version": 41, "version_tag": "70010"},
    },
    "50": {
        "user-theme@gnome-shell-extensions.gcampax.github.com": {
            "version": 79, "version_tag": "75092",
        },
        "blur-my-shell@aunetx": {"version": 77, "version_tag": "77413"},
        "just-perfection-desktop@just-perfection": {
            "version": 37, "version_tag": "74466",
        },
        "auto-theme-switcher@amritashan.github.io": {
            "version": 11, "version_tag": "72675",
        },
    },
}

# Ubuntu publishes the Shell 50 dock and AppIndicators in one package; Noble
# still publishes separate packages. These are package archive versions, not
# upstream extension versions.
UBUNTU_RELEASES = {
    "46": {
        "packages": {
            "ubuntu-dock@ubuntu.com": ("gnome-shell-extension-ubuntu-dock", "90ubuntu3"),
            "ubuntu-appindicators@ubuntu.com": (
                "gnome-shell-extension-appindicator", "58-1ubuntu24.04.1",
            ),
        },
        "extension_versions": {
            "ubuntu-dock@ubuntu.com": 90,
            "ubuntu-appindicators@ubuntu.com": None,
        },
    },
    "50": {
        "packages": {
            "ubuntu-dock@ubuntu.com": ("gnome-shell-ubuntu-extensions", "50.26.04.8ubuntu"),
            "ubuntu-appindicators@ubuntu.com": (
                "gnome-shell-ubuntu-extensions", "50.26.04.8ubuntu",
            ),
        },
        "extension_versions": {
            "ubuntu-dock@ubuntu.com": 105,
            "ubuntu-appindicators@ubuntu.com": None,
        },
    },
}

ACTIVE_STATE = 1
REQUIRED_SCHEMA_KEYS = {
    "user-theme@gnome-shell-extensions.gcampax.github.com": {
        "org.gnome.shell.extensions.user-theme": {"name"},
    },
    "blur-my-shell@aunetx": {
        "org.gnome.shell.extensions.blur-my-shell": {"pipelines"},
        "org.gnome.shell.extensions.blur-my-shell.panel": {
            "blur", "static-blur", "override-background", "pipeline", "corner-radius",
        },
        "org.gnome.shell.extensions.blur-my-shell.popup": {
            "blur", "static-blur", "override-background", "pipeline", "corner-radius",
            "calendar-corner-radius", "dialog-corner-radius", "menu-corner-radius",
            "notification-corner-radius", "osd-corner-radius", "osd-window-corner-radius",
            "quick-settings-corner-radius", "rounded-corners",
        },
        "org.gnome.shell.extensions.blur-my-shell.dash-to-dock": {
            "blur", "static-blur", "override-background", "pipeline",
        },
    },
    "just-perfection-desktop@just-perfection": {
        "org.gnome.shell.extensions.just-perfection": {
            "clock-menu-position", "clock-menu-position-offset",
        },
    },
    "auto-theme-switcher@amritashan.github.io": {
        "org.gnome.shell.extensions.auto-theme-switcher": {"light-theme", "dark-theme"},
    },
    "logomenu@aryan_k": {
        "org.gnome.shell.extensions.logo-menu": {"menu-button-icon-size"},
    },
}


class ExtensionCompatibilityError(ValueError):
    """Raised when an installed or running extension violates the exact policy."""


def running_shell_version() -> str:
    result = subprocess.run(
        ["gnome-shell", "--version"], capture_output=True, text=True, check=False,
    )
    match = re.search(r"\b(\d+)\b", result.stdout)
    if not match:
        raise ExtensionCompatibilityError("could not detect GNOME Shell version")
    return match.group(1)


def policy_extension_uuids(shell_version: str) -> tuple[str, ...]:
    """Return all upstream and Ubuntu extension UUIDs governed by a Shell policy.

    The tuple is deterministic: EGO-managed releases first, then Ubuntu-owned
    package extensions. Logo Menu is absent from the GNOME 50 policy.
    """
    shell_version = str(shell_version)
    if shell_version not in RELEASES or shell_version not in UBUNTU_RELEASES:
        raise ExtensionCompatibilityError(
            f"no exact Yaru Glass extension policy exists for GNOME Shell {shell_version}"
        )
    return tuple(RELEASES[shell_version]) + tuple(
        UBUNTU_RELEASES[shell_version]["packages"]
    )


def release_for(uuid: str, shell_version: str) -> Mapping[str, object]:
    release = RELEASES.get(str(shell_version), {}).get(uuid)
    if release is None:
        if uuid == "logomenu@aryan_k" and str(shell_version) == "50":
            raise ExtensionCompatibilityError(
                "Logo Menu is intentionally omitted on GNOME Shell 50 until guest interaction is verified"
            )
        raise ExtensionCompatibilityError(
            f"no exact Yaru Glass release is approved for {uuid} on GNOME Shell {shell_version}"
        )
    return release


def validate_extension_metadata(
    uuid: str, metadata: Mapping[str, object], shell_version: str,
) -> None:
    """Validate extension.json metadata against the exact supported release."""
    release = release_for(uuid, shell_version)
    if metadata.get("uuid") != uuid:
        raise ExtensionCompatibilityError(
            f"{uuid}: extension metadata UUID is {metadata.get('uuid')!r}"
        )
    version = metadata.get("version")
    if isinstance(version, bool) or version != release["version"]:
        raise ExtensionCompatibilityError(
            f"{uuid}: found version {version!r}; GNOME Shell {shell_version} requires "
            f"exact version {release['version']}. Install that release manually; Yaru Glass "
            "will not replace or downgrade an existing extension."
        )
    shell_versions = metadata.get("shell-version")
    if not isinstance(shell_versions, list) or str(shell_version) not in shell_versions:
        raise ExtensionCompatibilityError(
            f"{uuid} v{version}: metadata does not declare GNOME Shell {shell_version}"
        )


def validate_extension_schemas(
    uuid: str, metadata: Mapping[str, object], schema_documents: Mapping[str, bytes],
) -> None:
    """Check declared and integration-required GSettings schemas/keys."""
    settings_schema = metadata.get("settings-schema")
    if not isinstance(settings_schema, str) or not settings_schema:
        raise ExtensionCompatibilityError(f"{uuid}: extension does not declare a settings schema")
    schemas: dict[str, set[str]] = {}
    try:
        for document in schema_documents.values():
            root = ET.fromstring(document)
            for schema in root.findall("schema"):
                schema_id = schema.attrib.get("id")
                if schema_id:
                    schemas[schema_id] = {
                        key.attrib["name"] for key in schema.findall("key")
                        if "name" in key.attrib
                    }
    except ET.ParseError as error:
        raise ExtensionCompatibilityError(f"{uuid}: invalid GSettings schema XML: {error}") from error
    if settings_schema not in schemas:
        raise ExtensionCompatibilityError(
            f"{uuid}: release is missing declared schema {settings_schema}"
        )
    requirements = REQUIRED_SCHEMA_KEYS.get(uuid, {})
    for schema_id, required_keys in requirements.items():
        missing = required_keys - schemas.get(schema_id, set())
        if missing:
            raise ExtensionCompatibilityError(
                f"{uuid}: schema {schema_id} lacks required integration keys "
                f"{', '.join(sorted(missing))}"
            )


def installed_extension_path(uuid: str) -> Path | None:
    """Return GNOME's overriding user copy, or its system copy, if present."""
    for extension_root in (USER_EXTENSIONS, SYSTEM_EXTENSIONS):
        metadata_path = extension_root / uuid / "metadata.json"
        if metadata_path.is_file():
            return metadata_path.parent
    return None


def read_installed_metadata(uuid: str) -> tuple[Path, dict[str, object]]:
    extension_path = installed_extension_path(uuid)
    if extension_path is None:
        raise ExtensionCompatibilityError(f"{uuid}: extension is not installed")
    metadata_path = extension_path / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExtensionCompatibilityError(
            f"{uuid}: cannot read extension metadata at {metadata_path}: {error}"
        ) from error
    if not isinstance(metadata, dict):
        raise ExtensionCompatibilityError(f"{uuid}: extension metadata is not an object")
    return extension_path, metadata


def validate_installed_extension(uuid: str, shell_version: str | None = None) -> Path:
    """Validate the installed copy that GNOME would load, without changing it."""
    shell_version = shell_version or running_shell_version()
    extension_path, metadata = read_installed_metadata(uuid)
    validate_extension_metadata(uuid, metadata, shell_version)
    schema_dir = extension_path / "schemas"
    if not schema_dir.is_dir():
        raise ExtensionCompatibilityError(f"{uuid}: installed GSettings schemas are missing")
    try:
        schema_documents = {
            schema_path.name: schema_path.read_bytes()
            for schema_path in schema_dir.glob("*.gschema.xml")
        }
    except OSError as error:
        raise ExtensionCompatibilityError(f"{uuid}: cannot read installed GSettings schemas: {error}") from error
    validate_extension_schemas(uuid, metadata, schema_documents)
    return extension_path


def validate_running_extension(
    uuid: str, info: Mapping[str, object], shell_version: str | None = None,
) -> None:
    """Validate a running extension info dict (for example a Shell D-Bus payload).

    The dict must contain its ``version`` and may contain ``uuid``, ``state``, or
    nested ``metadata`` fields. If state is supplied, only GNOME's active state
    (1) is accepted.
    """
    shell_version = shell_version or running_shell_version()
    if not isinstance(info, Mapping):
        raise ExtensionCompatibilityError(f"{uuid}: running extension info is not a mapping")
    runtime_uuid = info.get("uuid")
    if runtime_uuid is not None and runtime_uuid != uuid:
        raise ExtensionCompatibilityError(
            f"running extension UUID mismatch: expected {uuid}, received {runtime_uuid!r}"
        )
    state = info.get("state")
    if state is not None and state != ACTIVE_STATE:
        raise ExtensionCompatibilityError(f"{uuid}: extension is not active (state={state!r})")
    metadata = info.get("metadata")
    ubuntu_policy = UBUNTU_RELEASES.get(str(shell_version), {})
    if uuid in ubuntu_policy.get("packages", {}):
        extension_path = validate_ubuntu_extension(uuid, shell_version)
        if extension_path is None:
            raise ExtensionCompatibilityError(f"{uuid}: Ubuntu extension is not installed")
        expected_version = ubuntu_policy["extension_versions"][uuid]
        if isinstance(metadata, Mapping):
            if metadata.get("uuid") != uuid:
                raise ExtensionCompatibilityError(
                    f"{uuid}: running extension metadata UUID is {metadata.get('uuid')!r}"
                )
            shell_versions = metadata.get("shell-version")
            if not isinstance(shell_versions, list) or str(shell_version) not in shell_versions:
                raise ExtensionCompatibilityError(
                    f"{uuid}: running metadata does not declare GNOME Shell {shell_version}"
                )
            if metadata.get("version") != expected_version:
                raise ExtensionCompatibilityError(
                    f"{uuid}: running metadata version {metadata.get('version')!r}; "
                    f"Ubuntu policy requires {expected_version!r}"
                )
        version = info.get("version")
        if version != expected_version:
            raise ExtensionCompatibilityError(
                f"{uuid}: running version {version!r}; Ubuntu policy requires "
                f"{expected_version!r} from package "
                f"{ubuntu_policy['packages'][uuid][0]}="
                f"{ubuntu_policy['packages'][uuid][1]}"
            )
        return
    if isinstance(metadata, Mapping):
        validate_extension_metadata(uuid, metadata, shell_version)
        return
    version = info.get("version")
    release = release_for(uuid, shell_version)
    if isinstance(version, bool) or version != release["version"]:
        raise ExtensionCompatibilityError(
            f"{uuid}: running version {version!r}; GNOME Shell {shell_version} requires "
            f"exact version {release['version']}"
        )


def validate_ubuntu_extension(uuid: str, shell_version: str) -> Path | None:
    """Validate an Ubuntu-owned Dock/AppIndicator copy and its exact package."""
    policy = UBUNTU_RELEASES.get(str(shell_version))
    if policy is None or uuid not in policy["packages"]:
        raise ExtensionCompatibilityError(
            f"no Ubuntu package policy is approved for {uuid} on GNOME Shell {shell_version}"
        )
    user_metadata = USER_EXTENSIONS / uuid / "metadata.json"
    if user_metadata.is_file():
        raise ExtensionCompatibilityError(
            f"{uuid}: a user-owned copy overrides Ubuntu's distro extension; remove it "
            "yourself or disable this integration. Yaru Glass will not replace it."
        )
    system_metadata = SYSTEM_EXTENSIONS / uuid / "metadata.json"
    if not system_metadata.is_file():
        return None
    extension_path = system_metadata.parent
    try:
        metadata = json.loads(system_metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExtensionCompatibilityError(
            f"{uuid}: cannot read Ubuntu extension metadata: {error}"
        ) from error
    if not isinstance(metadata, dict) or metadata.get("uuid") != uuid:
        raise ExtensionCompatibilityError(f"{uuid}: invalid Ubuntu extension metadata")
    if str(shell_version) not in metadata.get("shell-version", []):
        raise ExtensionCompatibilityError(
            f"{uuid}: Ubuntu package metadata does not support GNOME Shell {shell_version}"
        )
    expected_extension_version = policy["extension_versions"][uuid]
    if expected_extension_version is not None and metadata.get("version") != expected_extension_version:
        raise ExtensionCompatibilityError(
            f"{uuid}: Ubuntu metadata version {metadata.get('version')!r}; expected "
            f"{expected_extension_version} for GNOME Shell {shell_version}"
        )
    package, expected_version = policy["packages"][uuid]
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Version}", package],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0 or result.stdout.strip() != expected_version:
        installed = result.stdout.strip() or "not owned by the expected Ubuntu package"
        raise ExtensionCompatibilityError(
            f"{uuid}: Ubuntu package {package} is {installed}; this integration requires "
            f"exact package version {expected_version}. Yaru Glass will not replace or downgrade it."
        )
    return extension_path


def validate_ubuntu_extensions(shell_version: str) -> dict[str, Path]:
    """Return present, exact Ubuntu extension paths; absent integrations are optional."""
    paths = {}
    for uuid in UBUNTU_RELEASES.get(str(shell_version), {}).get("packages", {}):
        path = validate_ubuntu_extension(uuid, shell_version)
        if path is not None:
            paths[uuid] = path
    return paths
