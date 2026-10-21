#!/usr/bin/env python3
"""Print the newest stable Microsoft WSL kernel release from GitHub."""

from __future__ import annotations

import json
import re
import sys
from urllib.request import Request, urlopen


RELEASE_URL = "https://api.github.com/repos/microsoft/WSL2-Linux-Kernel/releases/latest"
USER_AGENT = "jkxyz-ebuilds-version-probe/1"
VERSION_PATTERN = re.compile(r"linux-msft-wsl-(\d+\.\d+\.\d+\.\d+)\Z")


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
    match = VERSION_PATTERN.fullmatch(tag) if isinstance(tag, str) else None
    if match is None:
        raise RuntimeError(f"unsupported stable Microsoft WSL kernel version: {tag!r}")
    return match.group(1)


def latest_stable_version(payload: str | None = None) -> str:
    if payload is None:
        payload = fetch()
    return parse_release(payload)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print("wsl2-kernel/latest_version.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(latest_stable_version())
    except Exception as error:  # noqa: BLE001 - probes turn failures into exit status
        print(f"wsl2-kernel/latest_version.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
