#!/usr/bin/env python3
"""Print the newest stable Filen desktop release with both Linux packages."""

from __future__ import annotations

import json
import re
import sys
from urllib.request import Request, urlopen


RELEASE_URL = (
    "https://api.github.com/repos/FilenCloudDienste/filen-desktop/releases/latest"
)
USER_AGENT = "jkxyz-ebuilds-version-probe/1"
VERSION_PATTERN = re.compile(r"v(\d+(?:\.\d+)+)\Z")


def fetch(url: str = RELEASE_URL) -> str:
    """Fetch GitHub's latest Filen desktop release response."""

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
    """Return a stable version when both supported Debian packages exist."""

    try:
        release = json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"could not parse the GitHub release response: {error}"
        ) from error

    if not isinstance(release, dict):
        raise RuntimeError("the GitHub release response is not an object")
    if release.get("draft") or release.get("prerelease"):
        raise RuntimeError("GitHub returned a draft or prerelease as the latest release")

    tag = release.get("tag_name")
    match = VERSION_PATTERN.fullmatch(tag) if isinstance(tag, str) else None
    if match is None:
        raise RuntimeError(f"unsupported stable Filen version: {tag!r}")
    version = match.group(1)

    assets = release.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("the GitHub release response has no asset list")
    names = {
        asset.get("name")
        for asset in assets
        if isinstance(asset, dict) and isinstance(asset.get("name"), str)
    }
    required = {"Filen_linux_amd64.deb", "Filen_linux_arm64.deb"}
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"the latest Filen release is missing: {', '.join(missing)}")
    return version


def latest_stable_version(payload: str | None = None) -> str:
    if payload is None:
        payload = fetch()
    return parse_release(payload)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print("filen-desktop-bin.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(latest_stable_version())
    except Exception as error:  # noqa: BLE001 - probes turn failures into exit status
        print(f"filen-desktop-bin.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
