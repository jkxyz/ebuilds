#!/usr/bin/env python3
"""Print the newest stable 1Password CLI version from its release feed."""

from __future__ import annotations

from html.parser import HTMLParser
import re
import sys
from urllib.request import Request, urlopen


RELEASE_FEED_URL = "https://app-updates.agilebits.com/product_history/CLI2"
USER_AGENT = "jkxyz-ebuilds-version-probe/1"
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+\Z")


def fetch(url: str = RELEASE_FEED_URL) -> str:
    """Fetch the official CLI release feed."""

    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def parse_version(value: str) -> tuple[int, ...]:
    if VERSION_PATTERN.fullmatch(value) is None:
        raise ValueError(f"unsupported stable CLI version: {value!r}")
    return tuple(int(part) for part in value.split("."))


class _ReleaseFeedParser(HTMLParser):
    """Collect numeric h3 release headings outside beta articles."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._article_depth = 0
        self._beta_article = False
        self._heading_depth = 0
        self._heading_text: list[str] = []
        self.versions: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "article":
            attributes = dict(attrs)
            classes = set((attributes.get("class") or "").split())
            self._article_depth += 1
            if self._article_depth == 1:
                self._beta_article = "beta" in classes
        elif tag == "h3" and self._article_depth:
            self._heading_depth += 1
            if self._heading_depth == 1:
                self._heading_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self._heading_depth:
            self._heading_depth -= 1
            if self._heading_depth == 0:
                heading = "".join(self._heading_text).strip()
                token = heading.split(None, 1)[0] if heading else ""
                if token and not self._beta_article:
                    candidate = token.removeprefix("v")
                    if VERSION_PATTERN.fullmatch(candidate):
                        self.versions.append(candidate)
                self._heading_text = []
        elif tag == "article" and self._article_depth:
            self._article_depth -= 1
            if self._article_depth == 0:
                self._beta_article = False

    def handle_data(self, data: str) -> None:
        if self._heading_depth:
            self._heading_text.append(data)


def parse_release_feed(feed: str) -> str:
    """Return the newest numeric release whose article is not marked beta."""

    parser = _ReleaseFeedParser()
    try:
        parser.feed(feed)
        parser.close()
    except Exception as error:
        raise RuntimeError(f"could not parse the CLI release feed: {error}") from error

    if not parser.versions:
        raise RuntimeError("the CLI release feed contained no stable numeric release")
    return max(parser.versions, key=parse_version)


def latest_stable_version(feed: str | None = None) -> str:
    if feed is None:
        feed = fetch()
    return parse_release_feed(feed)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print("op-cli-bin.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(latest_stable_version())
    except Exception as error:  # noqa: BLE001 - a probe must turn all failures into exit status
        print(f"op-cli-bin.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
