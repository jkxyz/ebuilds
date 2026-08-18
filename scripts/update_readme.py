#!/usr/bin/env python3
"""Render the package catalogue embedded in README.md."""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

try:
    from .bump_packages import ebuilds, keywords
except ImportError:  # pragma: no cover - used when run as a script
    from bump_packages import ebuilds, keywords


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
START_MARKER = "<!-- BEGIN GENERATED PACKAGE CATALOGUE -->"
END_MARKER = "<!-- END GENERATED PACKAGE CATALOGUE -->"
ASSIGNMENT_PATTERN = r'^\s*{name}\s*=\s*"([^"]*)"'
GLOBAL_USE_DESCRIPTIONS = {
    "X": "Install desktop icons and AppIndicator integration.",
    "selinux": "Install the corresponding SELinux policy.",
    "test": "Build and run the upstream test suite.",
}


class CatalogueError(RuntimeError):
    """The package catalogue could not be rendered safely."""


@dataclass(frozen=True)
class Release:
    version: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class UseFlag:
    name: str
    description: str | None


@dataclass(frozen=True)
class Package:
    atom: str
    description: str
    releases: tuple[Release, ...]
    use_flags: tuple[UseFlag, ...]


def normalize_text(parts) -> str:
    return " ".join("".join(parts).split())


def assignment(contents: str, name: str) -> str | None:
    match = re.search(
        ASSIGNMENT_PATTERN.format(name=re.escape(name)), contents, re.MULTILINE
    )
    return match.group(1).strip() if match is not None else None


def metadata(package_directory: Path) -> tuple[str | None, dict[str, str]]:
    path = package_directory / "metadata.xml"
    if not path.is_file():
        return None, {}
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as error:
        raise CatalogueError(f"cannot parse {path}: {error}") from error

    longdescription = root.find("longdescription")
    description = (
        normalize_text(longdescription.itertext())
        if longdescription is not None
        else None
    )
    flag_descriptions = {
        flag.attrib["name"]: normalize_text(flag.itertext())
        for flag in root.findall("./use/flag")
        if flag.attrib.get("name")
    }
    return description, flag_descriptions


def package(atom: str, root: Path = REPOSITORY_ROOT) -> Package:
    package_directory = root / atom
    release_entries = ebuilds(atom, root)
    if not release_entries:
        raise CatalogueError(f"no ebuilds found for {atom}")

    description, flag_descriptions = metadata(package_directory)
    iuse: set[str] = set()
    releases: list[Release] = []
    for entry in release_entries:
        contents = entry.path.read_text(encoding="utf-8")
        if description is None:
            description = assignment(contents, "DESCRIPTION")
        for value in (assignment(contents, "IUSE") or "").split():
            flag = value.lstrip("+-")
            if flag:
                iuse.add(flag)
        releases.append(
            Release(
                entry.version,
                tuple(
                    sorted(
                        value
                        for value in keywords(entry.path, required=False)
                        if not value.startswith("-")
                    )
                ),
            )
        )

    if not description:
        raise CatalogueError(f"cannot determine a description for {atom}")
    use_flags = tuple(
        UseFlag(name, flag_descriptions.get(name) or GLOBAL_USE_DESCRIPTIONS.get(name))
        for name in sorted(iuse, key=str.casefold)
    )
    return Package(atom, description, tuple(releases), use_flags)


def discover(root: Path = REPOSITORY_ROOT) -> list[Package]:
    packages: list[Package] = []
    for ebuild in sorted(root.glob("*/*/*.ebuild")):
        package_directory = ebuild.parent
        atom = f"{package_directory.parent.name}/{package_directory.name}"
        if packages and packages[-1].atom == atom:
            continue
        packages.append(package(atom, root))
    return packages


def render_package(entry: Package) -> str:
    versions: list[str] = []
    for release in entry.releases:
        line = f"`{release.version}`"
        if release.keywords:
            line += " (" + ", ".join(f"`{value}`" for value in release.keywords) + ")"
        versions.append(line)
    lines = [
        f"### `{entry.atom}`",
        "",
        entry.description,
        "",
        "**Versions:** " + "; ".join(versions),
    ]
    if not entry.use_flags:
        lines.extend(["", "**USE flags:** none"])
    else:
        lines.extend(["", "**USE flags**", ""])
        for flag in entry.use_flags:
            line = f"- `{flag.name}`"
            if flag.description:
                line += f" — {flag.description}"
            lines.append(line)
    return "\n".join(lines)


def render(root: Path = REPOSITORY_ROOT) -> str:
    return "\n\n".join(render_package(entry) for entry in discover(root))


def updated_readme(contents: str, root: Path = REPOSITORY_ROOT) -> str:
    start = contents.find(START_MARKER)
    end = contents.find(END_MARKER)
    if start < 0 or end < 0 or end < start:
        raise CatalogueError("README.md does not contain the catalogue markers")
    start += len(START_MARKER)
    return f"{contents[:start]}\n\n{render(root)}\n\n{contents[end:]}"


def update(
    root: Path = REPOSITORY_ROOT,
    readme: Path | None = None,
    *,
    check: bool = False,
) -> bool:
    path = readme or root / "README.md"
    contents = path.read_text(encoding="utf-8")
    result = updated_readme(contents, root)
    changed = result != contents
    if changed and not check:
        path.write_text(result, encoding="utf-8")
    return changed


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments not in ([], ["--check"]):
        print("usage: update_readme.py [--check]", file=sys.stderr)
        return 2
    try:
        changed = update(check=bool(arguments))
    except (CatalogueError, OSError, ValueError) as error:
        print(f"update_readme.py: {error}", file=sys.stderr)
        return 1
    if arguments and changed:
        print("update_readme.py: README.md package catalogue is stale", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
