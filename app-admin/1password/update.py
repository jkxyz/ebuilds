#!/usr/bin/env python3
"""Check for and bump stable 1Password releases."""

from __future__ import annotations

import argparse
import gzip
import os
from pathlib import Path
import re
import subprocess
from typing import Sequence
import urllib.request


PACKAGE_NAME = "1password"
PACKAGE_DIRECTORY = Path(__file__).resolve().parent
PACKAGES_URL = (
    "https://downloads.1password.com/linux/debian/amd64/"
    "dists/stable/main/binary-amd64/Packages.gz"
)
USER_AGENT = "jkxyz-ebuilds-updater/2"
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+")
EBUILD_PATTERN = re.compile(r"1password-(\d+(?:\.\d+)+)\.ebuild")
KEYWORDS_PATTERN = re.compile(r'^KEYWORDS="([^"]*)"$', re.MULTILINE)
ARCHITECTURES = ("amd64", "arm64")


def fetch(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=120)


def parse_version(value: str) -> tuple[int, ...]:
    if not VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"unsupported 1Password version: {value!r}")
    return tuple(int(part) for part in value.split("."))


def latest_stable_version() -> str:
    with fetch(PACKAGES_URL) as response:
        package_index = gzip.decompress(response.read()).decode("utf-8")

    versions = []
    for stanza in package_index.split("\n\n"):
        fields = {}
        for line in stanza.splitlines():
            if not line or line[0].isspace() or ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key] = value.strip()
        if fields.get("Package") != PACKAGE_NAME:
            continue

        version = fields.get("Version", "").split(":", 1)[-1]
        version = re.sub(r"-\d+$", "", version)
        parse_version(version)
        versions.append(version)

    if not versions:
        raise RuntimeError("1password was not found in the stable APT index")
    return max(versions, key=parse_version)


def ebuilds(package_directory: Path = PACKAGE_DIRECTORY) -> list[tuple[Path, str]]:
    releases = []
    for path in package_directory.glob(f"{PACKAGE_NAME}-*.ebuild"):
        match = EBUILD_PATTERN.fullmatch(path.name)
        if match is None:
            raise RuntimeError(f"cannot parse ebuild version from {path.name}")
        version = match.group(1)
        parse_version(version)
        releases.append((path, version))
    if not releases:
        raise RuntimeError("no 1Password ebuilds were found")
    return sorted(releases, key=lambda release: parse_version(release[1]))


def keywords(path: Path) -> set[str]:
    match = KEYWORDS_PATTERN.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError(f"cannot read KEYWORDS from {path.name}")
    return set(match.group(1).split())


def testing_only(path: Path) -> bool:
    values = keywords(path)
    testing_arches = {value[1:] for value in values if value.startswith("~")}
    stable_arches = values.intersection(ARCHITECTURES)
    return bool(testing_arches) and not stable_arches


def github_output(name: str, value: str) -> None:
    print(f"{name}={value}")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def check() -> bool:
    current = ebuilds()[-1][1]
    latest = latest_stable_version()
    print(f"Latest overlay version: {current}")
    print(f"Latest stable version:  {latest}")

    if parse_version(latest) < parse_version(current):
        raise RuntimeError(
            f"stable repository version {latest} is older than local version {current}"
        )

    updated = latest != current
    github_output("updated", str(updated).lower())
    github_output("previous_version", current)
    github_output("version", latest)
    return updated


def regenerate_manifest(
    package_directory: Path = PACKAGE_DIRECTORY,
    runner=subprocess.run,
) -> None:
    runner(["pkgdev", "manifest"], cwd=package_directory, check=True)


def bump(
    version: str,
    package_directory: Path = PACKAGE_DIRECTORY,
    runner=subprocess.run,
) -> Path:
    parse_version(version)
    releases = ebuilds(package_directory)
    source, current = releases[-1]
    if parse_version(version) <= parse_version(current):
        raise RuntimeError(
            f"new version {version} must be newer than local version {current}"
        )

    destination = package_directory / f"{PACKAGE_NAME}-{version}.ebuild"
    if destination.exists():
        raise RuntimeError(f"destination ebuild already exists: {destination.name}")

    runner(
        ["pkgbump", "--no-diff", source.name, version],
        cwd=package_directory,
        check=True,
    )
    (package_directory / ".pkgbump-pv").unlink(missing_ok=True)
    if not destination.is_file():
        raise RuntimeError(f"pkgbump did not create {destination.name}")

    new_keywords = keywords(destination)
    expected_keywords = {f"~{architecture}" for architecture in ARCHITECTURES}
    if new_keywords != expected_keywords:
        raise RuntimeError(
            f"{destination.name} has unexpected KEYWORDS: "
            + " ".join(sorted(new_keywords))
        )

    for path, old_version in releases:
        if parse_version(old_version) < parse_version(version) and testing_only(path):
            print(f"Removing superseded testing ebuild {path.name}")
            path.unlink()

    regenerate_manifest(package_directory, runner)
    return destination


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="check the stable APT repository")
    bump_parser = subparsers.add_parser("bump", help="bump to a new version")
    bump_parser.add_argument("version")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "check":
            check()
        else:
            destination = bump(arguments.version)
            print(f"Created {destination.name}")
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
