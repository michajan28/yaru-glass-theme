"""Verified stable GitHub releases and bounded, non-executing archive staging."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "michajan28/yaru-glass-theme"
API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_METADATA = 1024 * 1024
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_MEMBERS = 10000
TIMEOUT = 20
DEADLINE = 180
PAYLOAD = frozenset({"README.md", "CHANGELOG.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md", "VERSION",
                     ".github", "src", "scripts", "bin", "assets", "docs", "tests", "demo"})
REQUIRED = ("VERSION", "scripts/build.py", "scripts/uninstall.sh",
            "bin/yaru-glass-settings", "bin/yaru-glass-sync", "bin/yaru-glass-update",
            "src/yaru_glass/updates.py", "src/yaru_glass/update_transaction.py",
            "src/theme/gnome-shell/glass.css.in")


class UpdateError(RuntimeError):
    pass


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        raise UpdateError("Expected a stable MAJOR.MINOR.PATCH version.")
    return tuple(map(int, value.split(".")))


def read_version(root):
    value = (root / "VERSION").read_text().strip()
    version(value)
    return value


def checked_url(url):
    if not isinstance(url, str):
        raise UpdateError("Invalid GitHub download URL.")
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.username or parsed.password or
            parsed.port not in (None, 443) or parsed.fragment or
            parsed.hostname not in {"api.github.com", "github.com",
                                    "release-assets.githubusercontent.com",
                                    "objects.githubusercontent.com"}):
        raise UpdateError("Release URLs and redirects must use approved GitHub HTTPS hosts.")
    return url


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        checked_url(new_url)
        return super().redirect_request(request, fp, code, message, headers, new_url)


def download(url, limit, destination=None):
    checked_url(url)
    request = urllib.request.Request(url, headers={
        "User-Agent": "Yaru-Glass-Updater", "Accept": "application/vnd.github+json"
        if url == API else "application/octet-stream"})
    started = time.monotonic()
    try:
        with urllib.request.build_opener(Redirects()).open(request, timeout=TIMEOUT) as response:
            checked_url(response.geturl())
            length = response.headers.get("Content-Length")
            if length and (not length.isdecimal() or int(length) > limit):
                raise UpdateError("Release response exceeds its size limit.")
            content = bytearray()
            size = 0
            stream = destination.open("xb") if destination else None
            try:
                while True:
                    chunk = response.read1(64 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit or time.monotonic() - started > DEADLINE:
                        raise UpdateError("Release download exceeded its size or time limit.")
                    if stream:
                        stream.write(chunk)
                    else:
                        content.extend(chunk)
            finally:
                if stream:
                    stream.close()
            if length and size != int(length):
                raise UpdateError("Incomplete release download; retry.")
            return bytes(content)
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"GitHub returned HTTP {exc.code}. Check connectivity or rate limits and retry.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise UpdateError("GitHub is unavailable or TLS verification failed. Check connectivity and retry.") from exc


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    archive_url: str
    checksum_url: str
    digest: str | None
    size: int

    @property
    def filename(self):
        return f"yaru-glass-theme-{self.version}.tar.gz"


def latest():
    try:
        data = json.loads(download(API, MAX_METADATA))
        if not isinstance(data, dict) or data.get("draft") is not False or data.get("prerelease") is not False:
            raise UpdateError("GitHub did not return a published stable release.")
        tag = data["tag_name"]
        if not isinstance(tag, str) or not tag.startswith("v"):
            raise UpdateError("Invalid release tag.")
        text = tag[1:]
        version(text)
        release_url = f"https://github.com/{REPOSITORY}/releases/tag/{tag}"
        if data.get("html_url") != release_url:
            raise UpdateError("Release metadata points to a different repository.")
        name = f"yaru-glass-theme-{text}.tar.gz"
        assets = data["assets"]
        if not isinstance(assets, list):
            raise UpdateError("Invalid release assets.")
        selected = []
        for filename in (name, name + ".sha256"):
            matches = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == filename]
            if len(matches) != 1:
                raise UpdateError(f"Release requires exactly one {filename} asset.")
            asset = matches[0]
            expected = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{filename}"
            if asset.get("browser_download_url") != expected:
                raise UpdateError("Unexpected release asset URL.")
            size = asset["size"]
            if type(size) is not int or not 0 < size <= (MAX_ARCHIVE if filename == name else 4096):
                raise UpdateError("Invalid release asset size.")
            selected.append(asset)
        digest = selected[0].get("digest")
        if digest is not None and (not isinstance(digest, str) or
                                   not re.fullmatch(r"sha256:[a-f0-9]{64}", digest)):
            raise UpdateError("Invalid GitHub asset digest.")
        return Release(text, release_url, selected[0]["browser_download_url"],
                       selected[1]["browser_download_url"], digest, selected[0]["size"])
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise UpdateError("Malformed GitHub release metadata.") from exc


def check(installed):
    release = latest()
    return release, {"status": "available" if version(release.version) > version(installed) else "up-to-date",
                     "installed_version": installed, "available_version": release.version,
                     "release_url": release.url}


def verify(archive, checksum, expected_version, digest=None):
    filename = f"yaru-glass-theme-{expected_version}.tar.gz"
    version(expected_version)
    if archive.stat().st_size > MAX_ARCHIVE or checksum.stat().st_size > 4096:
        raise UpdateError("Release archive or checksum exceeds its size limit.")
    try:
        text = checksum.read_text("ascii")
    except (UnicodeError, OSError) as exc:
        raise UpdateError("Cannot read the release checksum.") from exc
    match = re.fullmatch(r"([a-fA-F0-9]{64}) [ *]" + re.escape(filename) + r"\n?", text)
    if not match:
        raise UpdateError("Checksum must name exactly the selected release archive.")
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != match[1].lower() or (digest is not None and digest != "sha256:" + actual):
        raise UpdateError("Release checksum mismatch. No installed files were changed.")


def extract(archive, target, expected_version):
    """Validate all members first, then write only regular files to a new directory."""
    root = f"yaru-glass-theme-{expected_version}"
    version(expected_version)
    try:
        with tarfile.open(archive, "r:gz") as package:
            members, names, expanded = [], set(), 0
            for member in package:
                parts = PurePosixPath(member.name).parts
                if (len(members) >= MAX_MEMBERS or not parts or parts[0] != root or
                        member.name.startswith("/") or "\\" in member.name or
                        any(part in {"..", ".", ""} for part in member.name.rstrip("/").split("/")) or
                        not (member.isdir() or member.isfile()) or
                        (len(parts) == 1 and not member.isdir()) or
                        member.name.rstrip("/") in names):
                    raise UpdateError("Unsafe or ambiguous release archive entry.")
                if len(parts) > 1 and parts[1] not in PAYLOAD:
                    raise UpdateError("Unexpected release payload path.")
                if any(part in {"backup", "state", ".git", "__pycache__"} for part in parts[1:]):
                    raise UpdateError("Release archive contains non-distributable state.")
                expanded += member.size
                if member.size < 0 or expanded > MAX_EXPANDED:
                    raise UpdateError("Expanded release archive is too large.")
                names.add(member.name.rstrip("/"))
                members.append(member)
            files = {member.name: member for member in members if member.isfile()}
            for name in names:
                if any(str(parent) in files for parent in PurePosixPath(name).parents):
                    raise UpdateError("Archive files cannot also be parent directories.")
            if any(f"{root}/{name}" not in files for name in REQUIRED):
                raise UpdateError("Release archive is missing required updater payload.")
            if files[f"{root}/VERSION"].size > 128:
                raise UpdateError("Invalid archive VERSION.")
            content = package.extractfile(files[f"{root}/VERSION"]).read(128)
            if content.decode("ascii").strip() != expected_version:
                raise UpdateError("Archive VERSION does not match the release.")
            target.mkdir(mode=0o700)
            for member in members:
                parts = PurePosixPath(member.name).parts[1:]
                if not parts:
                    continue
                out = target.joinpath(*parts)
                if member.isdir():
                    out.mkdir(parents=True, exist_ok=True)
                else:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with package.extractfile(member) as source, out.open("xb") as dest:
                        while chunk := source.read(64 * 1024):
                            dest.write(chunk)
                    out.chmod(0o755 if parts[0] in {"bin", "scripts"} and member.mode & 0o111 else 0o644)
    except (tarfile.TarError, UnicodeError, EOFError) as exc:
        raise UpdateError("Invalid release archive.") from exc


def fetch(release, workspace):
    archive = workspace / release.filename
    checksum = workspace / (release.filename + ".sha256")
    download(release.archive_url, MAX_ARCHIVE, archive)
    if archive.stat().st_size != release.size:
        raise UpdateError("Archive size does not match release metadata.")
    download(release.checksum_url, 4096, checksum)
    verify(archive, checksum, release.version, release.digest)
    payload = workspace / "payload"
    extract(archive, payload, release.version)
    return payload
