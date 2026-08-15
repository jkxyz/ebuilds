#!/usr/bin/env python3
"""Print the newest stable KDE Gear release containing Dolphin Plugins."""

from __future__ import annotations

from html.parser import HTMLParser
import re
import sys
from urllib.request import Request, urlopen


RELEASES_URL = "https://download.kde.org/stable/release-service/"
USER_AGENT = "jkxyz-ebuilds-version-probe/1"
VERSION_PATTERN = re.compile(r"(?:\A|/)(\d{2}\.\d{2}\.\d+)/?\Z")


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() != "a":
            return
        for name, value in attrs:
            if name.casefold() == "href" and value is not None:
                self.targets.append(value)


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def version_key(value: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def links(index: str) -> list[str]:
    parser = LinkParser()
    parser.feed(index)
    return parser.targets


def parse_releases(index: str) -> str:
    versions = {
        match.group(1)
        for target in links(index)
        if (match := VERSION_PATTERN.search(target)) is not None
    }
    if not versions:
        raise RuntimeError("no stable KDE Gear releases were found")
    return max(versions, key=version_key)


def require_artifact(index: str, version: str) -> None:
    expected = f"dolphin-plugins-{version}.tar.xz"
    if not any(target.rsplit("/", 1)[-1] == expected for target in links(index)):
        raise RuntimeError(f"KDE Gear {version} is missing {expected}")


def latest_stable_version(
    releases_index: str | None = None,
    artifact_index: str | None = None,
) -> str:
    if releases_index is None:
        releases_index = fetch(RELEASES_URL)
    version = parse_releases(releases_index)

    if artifact_index is None:
        artifact_index = fetch(f"{RELEASES_URL}{version}/src/")
    require_artifact(artifact_index, version)
    return version


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print("dolphin-plugins-dropbox.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(latest_stable_version())
    except Exception as error:  # noqa: BLE001 - probes report failures by exit status
        print(f"dolphin-plugins-dropbox.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
