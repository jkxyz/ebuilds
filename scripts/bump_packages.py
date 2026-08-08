#!/usr/bin/env python3
"""Bump one package from an explicitly supplied Portage version."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cmp_to_key
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable, Iterable, Sequence

try:
    from portage.versions import vercmp, ververify
except ImportError:  # pragma: no cover - the Gentoo tools image always has Portage
    _FALLBACK_VERSION = re.compile(r"\d+(?:\.\d+)*(?:[-_+].*)?\Z")

    def ververify(version: str) -> bool:
        return _FALLBACK_VERSION.fullmatch(version) is not None

    def vercmp(left: str, right: str) -> int:
        def key(value: str) -> tuple[tuple[int, ...], str]:
            match = re.match(r"(\d+(?:\.\d+)*)(.*)\Z", value)
            if match is None:
                raise ValueError(f"invalid Portage version: {value!r}")
            return tuple(int(part) for part in match.group(1).split(".")), match.group(2)

        return (key(left) > key(right)) - (key(left) < key(right))


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
KEYWORDS_PATTERN = re.compile(r"^\s*KEYWORDS\s*=\s*\"([^\"]*)\"", re.MULTILINE)
EBUILD_SUFFIX = ".ebuild"


class BumpError(RuntimeError):
    """A package bump could not be completed safely."""


@dataclass(frozen=True)
class Ebuild:
    path: Path
    version: str


@dataclass(frozen=True)
class BumpResult:
    atom: str
    previous_version: str
    version: str
    updated: bool
    ebuild: str


Runner = Callable[..., subprocess.CompletedProcess[str]]


def compare_versions(left: str, right: str) -> int:
    """Compare two validated Portage versions."""

    result = vercmp(left, right)
    if result is None:
        raise BumpError(f"Portage could not compare versions {left!r} and {right!r}")
    return int(result)


def without_revision(version: str) -> str:
    """Return the upstream version portion of a Portage version."""

    return re.sub(r"-r\d+\Z", "", version)


def validate_version(value: str) -> str:
    if not value or not ververify(value):
        raise BumpError(f"invalid Portage version: {value!r}")
    return value


def validate_atom(atom: str) -> tuple[str, str]:
    parts = atom.split("/")
    if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
        raise BumpError(f"invalid package atom: {atom!r}")
    return parts[0], parts[1]


def package_directory(atom: str, root: Path = REPOSITORY_ROOT) -> Path:
    category, package = validate_atom(atom)
    directory = root / category / package
    if not directory.is_dir():
        raise BumpError(f"package directory does not exist: {atom}")
    return directory


def _ebuilds_in(directory: Path) -> list[Ebuild]:
    package = directory.name
    prefix = f"{package}-"
    releases: list[Ebuild] = []
    for path in directory.iterdir():
        if not path.is_file() or path.suffix != EBUILD_SUFFIX or not path.name.startswith(prefix):
            continue
        version = path.name[len(prefix) : -len(EBUILD_SUFFIX)]
        if not ververify(version):
            raise BumpError(f"cannot parse Portage version from {path.name}")
        releases.append(Ebuild(path=path, version=version))
    if not releases:
        raise BumpError(f"no matching ebuilds found in {directory}")

    def compare(left: Ebuild, right: Ebuild) -> int:
        result = compare_versions(left.version, right.version)
        return result if result else (left.path.name > right.path.name) - (left.path.name < right.path.name)

    return sorted(releases, key=cmp_to_key(compare))


def ebuilds(atom: str, root: Path = REPOSITORY_ROOT) -> list[Ebuild]:
    return _ebuilds_in(package_directory(atom, root))


def is_live_version(version: str) -> bool:
    return version == "9999" or version.startswith(("9999-", "9999_", "9999+"))


def non_live_ebuilds(releases: Iterable[Ebuild]) -> list[Ebuild]:
    result = [release for release in releases if not is_live_version(release.version)]
    if not result:
        raise BumpError("package has no non-live ebuild")
    return result


def highest(releases: Iterable[Ebuild]) -> Ebuild:
    entries = list(releases)
    if not entries:
        raise BumpError("package has no ebuilds")
    return max(entries, key=cmp_to_key(lambda left, right: compare_versions(left.version, right.version)))


def keywords(path: Path, *, required: bool = True) -> set[str]:
    match = KEYWORDS_PATTERN.search(path.read_text(encoding="utf-8"))
    if match is None:
        if not required:
            return set()
        raise BumpError(f"cannot read KEYWORDS from {path.name}")
    return set(match.group(1).split())


def stable_keywords(values: Iterable[str]) -> set[str]:
    """Return stable architecture keywords, excluding the unstable wildcard."""

    return {
        value
        for value in values
        if value and not value.startswith(("~", "-")) and value != "**"
    }


def testing_only(values: Iterable[str]) -> bool:
    values = set(values)
    return bool({value for value in values if value.startswith("~")}) and not stable_keywords(values)


def _remove_marker(directory: Path) -> None:
    marker = directory / ".pkgbump-pv"
    try:
        marker.unlink()
    except FileNotFoundError:
        pass


def _run_tool(runner: Runner, command: list[str], directory: Path) -> None:
    arguments = {"cwd": directory, "check": True}
    if runner is subprocess.run:
        # The command's own result is the only stdout this script should emit;
        # callers may redirect it directly to a key/value output file.
        arguments["stdout"] = subprocess.DEVNULL
    runner(command, **arguments)


def check_bump(
    atom: str,
    version: str,
    *,
    root: Path = REPOSITORY_ROOT,
) -> BumpResult:
    """Determine whether ``atom`` needs ``version`` without changing files."""

    requested = validate_version(version)
    current = highest(non_live_ebuilds(ebuilds(atom, root)))
    comparison = compare_versions(requested, current.version)
    if comparison < 0 and compare_versions(requested, without_revision(current.version)) == 0:
        comparison = 0
    if comparison < 0:
        raise BumpError(
            f"requested version {requested} is older than local version {current.version} for {atom}"
        )

    directory = package_directory(atom, root)
    return BumpResult(
        atom=atom,
        previous_version=current.version,
        version=requested,
        updated=comparison > 0,
        ebuild=(
            f"{directory.name}-{requested}{EBUILD_SUFFIX}"
            if comparison > 0
            else current.path.name
        ),
    )


def bump(
    atom: str,
    version: str,
    *,
    root: Path = REPOSITORY_ROOT,
    runner: Runner | None = None,
) -> BumpResult:
    """Bump ``atom`` to ``version`` without contacting an upstream service."""

    if runner is None:
        runner = subprocess.run

    result = check_bump(atom, version, root=root)
    if not result.updated:
        return result

    requested = result.version
    releases = ebuilds(atom, root)
    current = highest(non_live_ebuilds(releases))

    directory = package_directory(atom, root)
    destination = directory / result.ebuild
    if destination.exists():
        raise BumpError(f"destination ebuild already exists: {destination.name}")

    try:
        _run_tool(runner, ["pkgbump", "--no-diff", current.path.name, requested], directory)
    finally:
        _remove_marker(directory)

    if not destination.is_file():
        raise BumpError(f"pkgbump did not create {destination.name}")

    generated_keywords = keywords(destination)
    if not any(value.startswith("~") for value in generated_keywords):
        raise BumpError(f"{destination.name} has no testing keyword")
    generated_stable = stable_keywords(generated_keywords)
    if generated_stable:
        raise BumpError(
            f"{destination.name} has stable keywords: {', '.join(sorted(generated_stable))}"
        )

    for release in releases:
        if is_live_version(release.version) or compare_versions(release.version, requested) >= 0:
            continue
        if testing_only(keywords(release.path, required=False)):
            release.path.unlink()

    return BumpResult(
        atom=atom,
        previous_version=result.previous_version,
        version=requested,
        updated=True,
        ebuild=destination.name,
    )


def print_result(result: BumpResult) -> None:
    """Print stable key/value output suitable for shell consumers."""

    print(f"updated={str(result.updated).lower()}")
    print(f"previous_version={result.previous_version}")
    print(f"version={result.version}")
    print(f"ebuild={result.ebuild}")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2 or any(argument.startswith("-") for argument in arguments):
        print("usage: bump_packages.py ATOM VERSION", file=sys.stderr)
        return 2
    try:
        print_result(bump(arguments[0], arguments[1]))
    except (BumpError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"bump_packages.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
