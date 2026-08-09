#!/usr/bin/env python3
"""Print the newest stable Helium Linux release with complete tarball assets."""

from __future__ import annotations

import json
import re
import sys
from urllib.request import Request, urlopen


RELEASE_URL = "https://api.github.com/repos/imputnet/helium-linux/releases/latest"
USER_AGENT = "jkxyz-ebuilds-version-probe/1"
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+\Z")


def fetch(url: str = RELEASE_URL) -> str:
    """Fetch GitHub's latest Helium Linux release response."""

    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def parse_release(payload: str) -> str:
    """Return the version of a stable release containing both Linux tarballs."""

    try:
        release = json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"could not parse the GitHub release response: {error}") from error

    if not isinstance(release, dict):
        raise RuntimeError("the GitHub release response is not an object")
    if release.get("draft") or release.get("prerelease"):
        raise RuntimeError("GitHub returned a draft or prerelease as the latest release")

    tag = release.get("tag_name")
    if not isinstance(tag, str) or VERSION_PATTERN.fullmatch(tag) is None:
        raise RuntimeError(f"unsupported stable Helium version: {tag!r}")

    assets = release.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("the GitHub release response has no asset list")
    names = {
        asset.get("name")
        for asset in assets
        if isinstance(asset, dict) and isinstance(asset.get("name"), str)
    }
    required = {
        f"helium-{tag}-x86_64_linux.tar.xz",
        f"helium-{tag}-arm64_linux.tar.xz",
    }
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"the latest Helium release is missing: {', '.join(missing)}")
    return tag


def latest_stable_version(payload: str | None = None) -> str:
    if payload is None:
        payload = fetch()
    return parse_release(payload)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print("helium-bin.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(latest_stable_version())
    except Exception as error:  # noqa: BLE001 - probes turn failures into exit status
        print(f"helium-bin.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
