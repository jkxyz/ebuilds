#!/usr/bin/env python3
"""Print the newest stable Nextcloud Desktop release from GitHub."""

from __future__ import annotations

import json
import re
import sys
from urllib.request import Request, urlopen


RELEASE_URL = "https://api.github.com/repos/nextcloud/desktop/releases/latest"
USER_AGENT = "jkxyz-ebuilds-version-probe/1"
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+\Z")


def fetch(url: str = RELEASE_URL) -> str:
    """Fetch GitHub's latest-release response."""

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
    """Return the numeric version from a stable GitHub release response."""

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
    if not isinstance(tag, str):
        raise RuntimeError("the GitHub release response has no tag name")
    version = tag.removeprefix("v")
    if VERSION_PATTERN.fullmatch(version) is None:
        raise RuntimeError(f"unsupported stable Nextcloud Desktop version: {tag!r}")
    return version


def latest_stable_version(payload: str | None = None) -> str:
    if payload is None:
        payload = fetch()
    return parse_release(payload)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print("nextcloud-client.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(latest_stable_version())
    except Exception as error:  # noqa: BLE001 - probes turn failures into exit status
        print(f"nextcloud-client.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
