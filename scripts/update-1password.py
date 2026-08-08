#!/usr/bin/env python3
"""Update app-admin/1password from the official stable APT repository."""

from __future__ import annotations

import gzip
import hashlib
import os
from pathlib import Path
import re
import tempfile
import urllib.request


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRECTORY = REPOSITORY_ROOT / "app-admin" / "1password"
PACKAGES_URL = (
    "https://downloads.1password.com/linux/debian/amd64/"
    "dists/stable/main/binary-amd64/Packages.gz"
)
USER_AGENT = "jkxyz-ebuilds-updater/1"
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+")
ARCHITECTURES = {
    "amd64": "x86_64/1password-{version}.x64.tar.gz",
    "arm64": "aarch64/1password-{version}.arm64.tar.gz",
}


def fetch(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=120)


def parse_version(value: str) -> tuple[int, ...]:
    if not VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"unsupported 1Password version: {value!r}")
    return tuple(int(part) for part in value.split("."))


def latest_stable_version() -> str:
    with fetch(PACKAGES_URL) as response:
        package_index = gzip.decompress(response.read()).decode("utf-8")

    versions = []
    for stanza in package_index.split("\n\n"):
        fields = {}
        for line in stanza.splitlines():
            if not line or line[0].isspace() or ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key] = value.strip()
        if fields.get("Package") != "1password":
            continue

        version = fields.get("Version", "").split(":", 1)[-1]
        # Debian revisions are packaging metadata, not part of the upstream
        # version used in the stable tarball URL.
        version = re.sub(r"-\d+$", "", version)
        versions.append(version)

    if not versions:
        raise RuntimeError("1password was not found in the stable APT index")
    return max(versions, key=parse_version)


def current_ebuild() -> tuple[Path, str]:
    ebuilds = sorted(PACKAGE_DIRECTORY.glob("1password-*.ebuild"))
    if len(ebuilds) != 1:
        raise RuntimeError(
            f"expected exactly one 1Password ebuild, found {len(ebuilds)}"
        )

    match = re.fullmatch(r"1password-(\d+(?:\.\d+)+)\.ebuild", ebuilds[0].name)
    if match is None:
        raise RuntimeError(f"cannot parse ebuild version from {ebuilds[0].name}")
    return ebuilds[0], match.group(1)


def artifact_metadata(url: str, destination: Path) -> tuple[int, str, str]:
    blake2b = hashlib.blake2b()
    sha512 = hashlib.sha512()
    size = 0

    with fetch(url) as response, destination.open("wb") as artifact:
        while chunk := response.read(1024 * 1024):
            artifact.write(chunk)
            size += len(chunk)
            blake2b.update(chunk)
            sha512.update(chunk)

    return size, blake2b.hexdigest(), sha512.hexdigest()


def github_output(name: str, value: str) -> None:
    print(f"{name}={value}")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def main() -> None:
    ebuild, current = current_ebuild()
    latest = latest_stable_version()
    print(f"Installed ebuild version: {current}")
    print(f"Latest stable version:   {latest}")

    if parse_version(latest) < parse_version(current):
        raise RuntimeError(
            f"stable repository version {latest} is older than local version {current}"
        )
    if latest == current:
        github_output("updated", "false")
        github_output("version", current)
        return

    manifest_lines = []
    with tempfile.TemporaryDirectory(prefix="1password-update-") as temporary:
        temporary_directory = Path(temporary)
        for architecture, relative_url in ARCHITECTURES.items():
            url = (
                "https://downloads.1password.com/linux/tar/stable/"
                + relative_url.format(version=latest)
            )
            filename = f"1password-{latest}-{architecture}.tar.gz"
            print(f"Downloading {url}")
            size, blake2b, sha512 = artifact_metadata(
                url, temporary_directory / filename
            )
            manifest_lines.append(
                f"DIST {filename} {size} BLAKE2B {blake2b} SHA512 {sha512}"
            )

    new_ebuild = PACKAGE_DIRECTORY / f"1password-{latest}.ebuild"
    ebuild.rename(new_ebuild)

    manifest = PACKAGE_DIRECTORY / "Manifest"
    temporary_manifest = manifest.with_suffix(".tmp")
    temporary_manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    temporary_manifest.replace(manifest)

    github_output("updated", "true")
    github_output("previous_version", current)
    github_output("version", latest)


if __name__ == "__main__":
    main()
