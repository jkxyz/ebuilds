#!/usr/bin/env python3
"""Print the version behind Dropbox's stable x86_64 Linux download."""

from __future__ import annotations

import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DOWNLOAD_URL = "https://www.dropbox.com/download?plat=lnx.x86_64"
USER_AGENT = "jkxyz-ebuilds-version-probe/1"
ARTIFACT_HOSTS = {
    "clientupdates.dropboxstatic.com",
    "edge.dropboxstatic.com",
}
ARTIFACT_PATTERN = re.compile(
    r"/dbx-releng/client/dropbox-lnx\.x86_64-(\d+(?:\.\d+)+)\.tar\.gz\Z"
)


def fetch_final_url(url: str = DOWNLOAD_URL) -> str:
    """Follow Dropbox's stable download redirect without reading the archive."""

    request = Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
    with urlopen(request, timeout=120) as response:
        return response.geturl()


def parse_artifact_url(url: str) -> str:
    """Validate a Dropbox CDN artifact URL and return its Portage version."""

    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ARTIFACT_HOSTS:
        raise RuntimeError(f"unsupported Dropbox download host: {url!r}")
    if parsed.query or parsed.fragment:
        raise RuntimeError(f"unexpected Dropbox artifact URL suffix: {url!r}")

    match = ARTIFACT_PATTERN.fullmatch(parsed.path)
    if match is None:
        raise RuntimeError(f"unsupported Dropbox Linux artifact: {url!r}")
    return match.group(1)


def latest_stable_version(final_url: str | None = None) -> str:
    if final_url is None:
        final_url = fetch_final_url()
    return parse_artifact_url(final_url)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print("dropbox.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(latest_stable_version())
    except Exception as error:  # noqa: BLE001 - probes report failures by exit status
        print(f"dropbox.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
