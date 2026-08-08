#!/usr/bin/env python3
"""Stabilize selected architectures for a 1Password release."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
from typing import Sequence


PACKAGE_NAME = "1password"
PACKAGE_DIRECTORY = Path(__file__).resolve().parent
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+")
EBUILD_PATTERN = re.compile(r"1password-(\d+(?:\.\d+)+)\.ebuild")
KEYWORDS_PATTERN = re.compile(r'^KEYWORDS="([^"]*)"$', re.MULTILINE)
ARCHITECTURES = ("amd64", "arm64")


def parse_version(value: str) -> tuple[int, ...]:
    if not VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"unsupported 1Password version: {value!r}")
    return tuple(int(part) for part in value.split("."))


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


def stable_architectures(path: Path) -> set[str]:
    return keywords(path).intersection(ARCHITECTURES)


def regenerate_manifest(
    package_directory: Path = PACKAGE_DIRECTORY,
    runner=subprocess.run,
) -> None:
    runner(["pkgdev", "manifest"], cwd=package_directory, check=True)


def stabilize(
    version: str,
    architectures: Sequence[str],
    package_directory: Path = PACKAGE_DIRECTORY,
    runner=subprocess.run,
) -> Path:
    parse_version(version)
    selected = list(dict.fromkeys(architectures))
    if not selected:
        raise ValueError("at least one architecture must be selected")
    unsupported = set(selected).difference(ARCHITECTURES)
    if unsupported:
        raise ValueError(
            "unsupported architecture: " + ", ".join(sorted(unsupported))
        )

    releases = ebuilds(package_directory)
    target = package_directory / f"{PACKAGE_NAME}-{version}.ebuild"
    if not target.is_file():
        raise RuntimeError(f"ebuild does not exist: {target.name}")

    current_keywords = keywords(target)
    missing = {
        architecture
        for architecture in selected
        if architecture not in current_keywords
        and f"~{architecture}" not in current_keywords
    }
    if missing:
        raise RuntimeError(
            f"{target.name} is not keyworded for: " + ", ".join(sorted(missing))
        )

    runner(["ekeyword", *selected, target.name], cwd=package_directory, check=True)
    stabilized = stable_architectures(target)
    if not set(selected).issubset(stabilized):
        raise RuntimeError(
            f"ekeyword did not stabilize: "
            + ", ".join(sorted(set(selected).difference(stabilized)))
        )

    for path, old_version in releases:
        if parse_version(old_version) >= parse_version(version):
            continue
        old_stable = stable_architectures(path)
        if old_stable and old_stable.issubset(stabilized):
            print(f"Removing superseded stable ebuild {path.name}")
            path.unlink()

    regenerate_manifest(package_directory, runner)
    return target


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument(
        "--arch",
        action="append",
        choices=ARCHITECTURES,
        required=True,
        dest="architectures",
        help="architecture to stabilize (repeat for multiple architectures)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser()
    arguments = parser.parse_args(argv)
    try:
        target = stabilize(arguments.version, arguments.architectures)
        print(
            f"Stabilized {target.name} for "
            + ", ".join(dict.fromkeys(arguments.architectures))
        )
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
