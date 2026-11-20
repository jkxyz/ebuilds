#!/usr/bin/env python3
"""Print the highest stable Nextcloud Desktop version from GitHub."""

from __future__ import annotations

from itertools import count
import json
import os
import re
import sys
from urllib.request import Request, urlopen


RELEASE_URL = "https://api.github.com/repos/nextcloud/desktop/releases"
PAGE_SIZE = 100
USER_AGENT = "jkxyz-ebuilds-version-probe/1"
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+\Z")


def fetch_page(page: int) -> list[dict]:
    """Fetch one page of GitHub releases."""

    request = Request(
        f"{RELEASE_URL}?per_page={PAGE_SIZE}&page={page}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    if request.type == "https" and request.host == "api.github.com":
        if token := os.environ.get("GITHUB_TOKEN"):
            request.add_unredirected_header("Authorization", f"Bearer {token}")
    with urlopen(request, timeout=120) as response:
        releases = json.load(response)

    if not isinstance(releases, list) or not all(
        isinstance(release, dict) for release in releases
    ):
        raise RuntimeError("the GitHub release response is not a list of releases")
    return releases


def latest_stable_version() -> str:
    versions = []
    for page in count(1):
        releases = fetch_page(page)
        for release in releases:
            if release.get("draft") or release.get("prerelease"):
                continue
            tag = release.get("tag_name")
            if not isinstance(tag, str):
                continue
            version = tag.removeprefix("v")
            if VERSION_PATTERN.fullmatch(version):
                versions.append(version)
        if len(releases) < PAGE_SIZE:
            break

    if not versions:
        raise RuntimeError("no stable Nextcloud Desktop releases with numeric versions")
    return max(versions, key=lambda version: tuple(map(int, version.split("."))))


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
