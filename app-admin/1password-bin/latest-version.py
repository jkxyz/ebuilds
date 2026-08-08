#!/usr/bin/env python3
"""Print the newest stable 1Password desktop version from the APT index."""

from __future__ import annotations

import gzip
import re
import sys
from typing import Iterable
from urllib.request import Request, urlopen


PACKAGES_URL = (
    "https://downloads.1password.com/linux/debian/amd64/"
    "dists/stable/main/binary-amd64/Packages.gz"
)
USER_AGENT = "jkxyz-ebuilds-version-probe/1"
PACKAGE_NAME = "1password"
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+\Z")
PRERELEASE_PATTERN = re.compile(r"(?:^|[-_.~])(alpha|beta|dev|nightly|pre|rc)(?:[-_.~\d]|$)", re.IGNORECASE)


def fetch(url: str = PACKAGES_URL) -> bytes:
    """Fetch the compressed APT package index."""

    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        return response.read()


def parse_version(value: str) -> tuple[int, ...]:
    """Validate and compare normalized Gentoo versions as integer tuples."""

    if VERSION_PATTERN.fullmatch(value) is None:
        raise ValueError(f"unsupported stable 1Password version: {value!r}")
    return tuple(int(part) for part in value.split("."))


def normalize_debian_version(value: str) -> str:
    """Remove a Debian epoch and package revision from an upstream version."""

    normalized = value.strip()
    if not normalized:
        raise ValueError("empty Debian version")
    if PRERELEASE_PATTERN.search(normalized):
        raise ValueError(f"prerelease 1Password version: {value!r}")

    # Debian's epoch is separated from the upstream version by the last (and
    # normally only) colon.  The package revision follows the final hyphen and
    # starts with a digit for the releases published by 1Password.
    if ":" in normalized:
        normalized = normalized.split(":", 1)[1]
    upstream, separator, revision = normalized.rpartition("-")
    if separator and revision and revision[0].isdigit():
        normalized = upstream

    parse_version(normalized)
    return normalized


def _stanzas(package_index: str) -> Iterable[dict[str, str]]:
    for stanza in re.split(r"\n\s*\n", package_index):
        fields: dict[str, str] = {}
        for line in stanza.splitlines():
            if not line or line[0].isspace() or ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key] = value.strip()
        if fields:
            yield fields


def parse_packages(package_index: str) -> str:
    """Return the newest stable release represented by an APT index."""

    matching_package = False
    versions: list[str] = []
    for fields in _stanzas(package_index):
        if fields.get("Package") != PACKAGE_NAME:
            continue
        matching_package = True
        try:
            versions.append(normalize_debian_version(fields.get("Version", "")))
        except ValueError:
            # Beta/nightly/prerelease entries are not valid normalized Gentoo
            # PVs.  They are intentionally ignored when a stable entry is
            # present, but an index containing only such entries still fails
            # below as a missing stable release.
            continue

    if not matching_package:
        raise RuntimeError(f"{PACKAGE_NAME} was not found in the stable APT index")
    if not versions:
        raise RuntimeError("the stable APT index contained no stable 1Password release")
    return max(versions, key=parse_version)


def latest_stable_version(package_index: str | None = None) -> str:
    """Fetch and parse the stable APT index unless fixture text is supplied."""

    if package_index is None:
        package_index = gzip.decompress(fetch()).decode("utf-8")
    return parse_packages(package_index)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print("latest-version.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(latest_stable_version())
    except Exception as error:  # noqa: BLE001 - a probe must turn all failures into exit status
        print(f"latest-version.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
