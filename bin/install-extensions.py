#!/usr/bin/env python3
"""Install exact, approved GNOME Shell extension releases without replacing installs.

usage: install-extensions.py STATE_FILE UUID [UUID ...]
       install-extensions.py --validate-only UUID [UUID ...]
New user-owned installs are recorded in STATE_FILE for uninstall.sh.
"""
import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src/yaru_glass"))
from extension_compatibility import (  # noqa: E402
    UBUNTU_RELEASES,
    USER_EXTENSIONS,
    ExtensionCompatibilityError,
    installed_extension_path,
    read_installed_metadata,
    release_for,
    running_shell_version,
    validate_extension_metadata,
    validate_extension_schemas,
    validate_installed_extension,
    validate_ubuntu_extension,
)
import diagnostics
import companion_extension

EGO = "https://extensions.gnome.org"
REQUIRED_EXTENSIONS = {
    "user-theme@gnome-shell-extensions.gcampax.github.com",
    "blur-my-shell@aunetx",
}


def release_url(uuid: str, shell_version: str) -> str:
    release = release_for(uuid, shell_version)
    return (
        f"{EGO}/download-extension/{uuid}.shell-extension.zip"
        f"?version_tag={release['version_tag']}"
    )


def fetch_release(uuid: str, shell_version: str) -> bytes:
    request = urllib.request.Request(
        release_url(uuid, shell_version),
        headers={"User-Agent": "yaru-glass-installer"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        contents = response.read()
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as package:
            metadata = json.loads(package.read("metadata.json"))
            if not isinstance(metadata, dict):
                raise ExtensionCompatibilityError(
                    f"{uuid}: downloaded metadata is not an object"
                )
            validate_extension_metadata(uuid, metadata, shell_version)
            schema_id = metadata.get("settings-schema")
            if not isinstance(schema_id, str) or not schema_id:
                raise ExtensionCompatibilityError(
                    f"{uuid}: exact release does not declare its settings schema"
                )
            schemas = {
                name: package.read(name)
                for name in package.namelist()
                if name.startswith("schemas/") and name.endswith(".gschema.xml")
            }
            validate_extension_schemas(uuid, metadata, schemas)
    except (KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        raise ExtensionCompatibilityError(
            f"{uuid}: downloaded release archive is malformed: {error}"
        ) from error
    return contents


def validate_existing(uuid: str, shell_version: str) -> bool:
    if installed_extension_path(uuid) is None:
        return False
    validate_installed_extension(uuid, shell_version)
    _extension_path, metadata = read_installed_metadata(uuid)
    print(f"  ✓ {uuid} v{metadata['version']} (exact installed release)")
    return True


def validate_ubuntu_installs(shell_version: str) -> None:
    for uuid in UBUNTU_RELEASES[shell_version]["packages"]:
        extension_path = validate_ubuntu_extension(uuid, shell_version)
        if extension_path is None:
            print(f"  ! {uuid}: Ubuntu extension unavailable; optional integration remains skipped")
        else:
            print(f"  ✓ {uuid} (Ubuntu distro package release)")


def prepare_extensions(
    uuids: list[str], shell_version: str, *, validate_only: bool = False,
) -> dict[str, bytes | None]:
    """Validate all present extensions and fetch all needed archives before install."""
    validate_ubuntu_installs(shell_version)
    prepared: dict[str, bytes | None] = {}
    for uuid in uuids:
        if uuid == companion_extension.UUID:
            existing = companion_extension.installed(shell_version)
            if existing is None and not validate_only:
                companion_extension.validate_tree(companion_extension.SOURCE, shell_version)
            prepared[uuid] = None
            continue
        release_for(uuid, shell_version)
        if validate_existing(uuid, shell_version):
            prepared[uuid] = None
            continue
        if validate_only:
            print(f"  ! {uuid}: not installed; validation-only mode leaves it skipped")
            prepared[uuid] = None
            continue
        try:
            prepared[uuid] = fetch_release(uuid, shell_version)
        except (OSError, urllib.error.URLError) as error:
            if uuid in REQUIRED_EXTENSIONS:
                raise ExtensionCompatibilityError(
                    f"{uuid}: its exact GNOME Shell {shell_version} release is unavailable "
                    f"({error}); retry when online or use --no-extensions"
                ) from error
            print(
                f"  ! {uuid}: exact GNOME Shell {shell_version} release unavailable "
                f"({error}); optional integration remains skipped"
            )
            prepared[uuid] = None
    return prepared


def install_prepared(uuid: str, contents: bytes, shell_version: str, state: Path) -> None:
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache_dir = cache_home / "yaru-glass/extensions"
    cache_dir.mkdir(parents=True, exist_ok=True)
    release = release_for(uuid, shell_version)
    archive = cache_dir / f"{uuid.replace('@', '_')}-{release['version_tag']}.zip"
    archive.write_bytes(contents)
    try:
        subprocess.run(["gnome-extensions", "install", str(archive)], check=True)
    finally:
        archive.unlink(missing_ok=True)

    state.parent.mkdir(parents=True, exist_ok=True)
    with state.open("a", encoding="utf-8") as state_file:
        state_file.write(uuid + "\n")
    extension_path = validate_installed_extension(uuid, shell_version)
    _extension_path, metadata = read_installed_metadata(uuid)
    if extension_path != USER_EXTENSIONS / uuid:
        raise ExtensionCompatibilityError(
            f"{uuid}: new install did not land in the user extension directory"
        )
    schema_dir = extension_path / "schemas"
    if schema_dir.is_dir() and any(schema_dir.glob("*.gschema.xml")):
        if not (schema_dir / "gschemas.compiled").exists():
            subprocess.run(["glib-compile-schemas", str(schema_dir)], check=True)
    print(f"  + {uuid} v{metadata['version']} installed for GNOME Shell {shell_version}")


@diagnostics.traced("extensions", "install")
def main() -> None:
    arguments = sys.argv[1:]
    validate_only = bool(arguments and arguments[0] == "--validate-only")
    if validate_only:
        if len(arguments) < 2:
            sys.exit(__doc__)
        state = None
        uuids = arguments[1:]
    else:
        if len(arguments) < 2:
            sys.exit(__doc__)
        state = Path(arguments[0])
        uuids = arguments[1:]

    try:
        shell_version = running_shell_version()
        prepared = prepare_extensions(uuids, shell_version, validate_only=validate_only)
        if state is not None:
            if companion_extension.UUID in uuids:
                companion_extension.install(shell_version, state)
            for uuid, contents in prepared.items():
                if contents is not None:
                    install_prepared(uuid, contents, shell_version, state)
    except ExtensionCompatibilityError as error:
        diagnostics.event("extensions", "compatibility", "failure", level="ERROR", error=error)
        sys.exit(f"Extension compatibility error: {error}")


if __name__ == "__main__":
    main()
