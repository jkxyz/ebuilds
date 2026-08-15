#!/usr/bin/env python3
"""Print the newest versioned Dropbox Linux installer-source release."""

from __future__ import annotations

from datetime import date
from html.parser import HTMLParser
import re
import sys
from urllib.request import Request, urlopen


RELEASES_URL = "https://linux.dropbox.com/packages/"
USER_AGENT = "jkxyz-ebuilds-version-probe/1"
ARTIFACT_PATTERN = re.compile(
    r"(?:\A|/)nautilus-dropbox-(\d{4}\.\d{2}\.\d{2})\.tar\.bz2\Z"
)


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


def fetch(url: str = RELEASES_URL) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def version_key(value: str) -> date:
    try:
        return date.fromisoformat(value.replace(".", "-"))
    except ValueError as error:
        raise RuntimeError(f"invalid Dropbox CLI release date: {value!r}") from error


def parse_releases(index: str) -> str:
    parser = LinkParser()
    parser.feed(index)

    versions = {
        match.group(1)
        for target in parser.targets
        if (match := ARTIFACT_PATTERN.search(target)) is not None
    }
    if not versions:
        raise RuntimeError("no versioned Dropbox CLI source releases were found")
    for version in versions:
        version_key(version)
    return max(versions, key=version_key)


def latest_stable_version(index: str | None = None) -> str:
    if index is None:
        index = fetch()
    return parse_releases(index)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print("dropbox-cli.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(latest_stable_version())
    except Exception as error:  # noqa: BLE001 - probes report failures by exit status
        print(f"dropbox-cli.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
