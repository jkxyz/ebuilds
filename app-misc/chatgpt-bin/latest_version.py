#!/usr/bin/env python3
"""Print the newest stable ChatGPT desktop release for Linux."""

from __future__ import annotations

import gzip
import re
import sys
from urllib.request import Request, urlopen


PACKAGES_URLS = {
    "amd64": (
        "https://persistent.oaistatic.com/codex-app-prod/linux/deb/"
        "dists/stable/main/binary-amd64/Packages.gz"
    ),
    "arm64": (
        "https://persistent.oaistatic.com/codex-app-prod/linux/deb/"
        "dists/stable/main/binary-arm64/Packages.gz"
    ),
}
USER_AGENT = "jkxyz-ebuilds-version-probe/1"
PACKAGE_NAME = "chatgpt"
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+\Z")


def fetch(url: str) -> bytes:
    """Fetch one compressed OpenAI APT package index."""

    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        return response.read()


def parse_version(value: str) -> tuple[int, ...]:
    """Validate an upstream version and return a comparable tuple."""

    if VERSION_PATTERN.fullmatch(value) is None:
        raise ValueError(f"unsupported stable ChatGPT version: {value!r}")
    return tuple(int(part) for part in value.split("."))


def _stanzas(package_index: str):
    for stanza in re.split(r"\n\s*\n", package_index):
        fields: dict[str, str] = {}
        for line in stanza.splitlines():
            if not line or line[0].isspace() or ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key] = value.strip()
        if fields:
            yield fields


def parse_packages(package_index: str, architecture: str) -> str:
    """Return the newest stable release with the expected architecture artifact."""

    matching_package = False
    versions: list[str] = []
    for fields in _stanzas(package_index):
        if fields.get("Package") != PACKAGE_NAME:
            continue
        matching_package = True
        version = fields.get("Version", "")
        if fields.get("Architecture") != architecture:
            continue
        try:
            parse_version(version)
        except ValueError:
            continue
        expected_filename = (
            f"pool/main/c/chatgpt/chatgpt_{version}_{architecture}.deb"
        )
        if fields.get("Filename") != expected_filename:
            continue
        versions.append(version)

    if not matching_package:
        raise RuntimeError(f"{PACKAGE_NAME} was not found in the {architecture} APT index")
    if not versions:
        raise RuntimeError(
            f"the {architecture} APT index contained no usable stable release"
        )
    return max(versions, key=parse_version)


def latest_stable_version(package_indexes: dict[str, str] | None = None) -> str:
    """Fetch and compare both supported architecture indexes."""

    if package_indexes is None:
        package_indexes = {
            architecture: gzip.decompress(fetch(url)).decode("utf-8")
            for architecture, url in PACKAGES_URLS.items()
        }

    versions = {
        architecture: parse_packages(package_indexes[architecture], architecture)
        for architecture in PACKAGES_URLS
    }
    if len(set(versions.values())) != 1:
        details = ", ".join(
            f"{architecture}={version}"
            for architecture, version in sorted(versions.items())
        )
        raise RuntimeError(f"ChatGPT architecture versions do not match: {details}")
    return next(iter(versions.values()))


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print("chatgpt-bin.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(latest_stable_version())
    except Exception as error:  # noqa: BLE001 - probes turn failures into exit status
        print(f"chatgpt-bin.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
