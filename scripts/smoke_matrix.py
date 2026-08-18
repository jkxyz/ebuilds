#!/usr/bin/env python3
"""Select updated ebuild packages for smoke-test matrix jobs."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

try:
    from .bump_packages import BumpError, ebuilds, highest, non_live_ebuilds
except ImportError:  # pragma: no cover - used when run as a script
    from bump_packages import BumpError, ebuilds, highest, non_live_ebuilds


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ZERO_REVISION = re.compile(r"0+")
GIT_REVISION = re.compile(r"[0-9a-fA-F]{40,64}")
SMOKE_USE = {
    "app-admin/1password-bin": "-cli -policykit",
    "net-misc/dropbox": "X -selinux",
    "net-misc/nextcloud-client": "-dolphin -nautilus -test -webengine",
    "www-client/helium-bin": "qt6 -selinux",
}
SMOKE_PROFILE = {
    "kde-apps/dolphin-plugins-dropbox": (
        "default/linux/amd64/23.0/desktop/plasma"
    ),
}


def is_package_change(parts: tuple[str, ...]) -> bool:
    if len(parts) < 3:
        return False
    return parts[2].endswith(".ebuild") or parts[2] == "Manifest" or parts[2] == "files"


def changed_packages(paths: Iterable[str], root: Path = REPOSITORY_ROOT) -> list[str]:
    atoms: set[str] = set()
    for value in paths:
        parts = Path(value).parts
        if not is_package_change(parts):
            continue
        atom = f"{parts[0]}/{parts[1]}"
        package_directory = root / atom
        if package_directory.is_dir() and list(
            package_directory.glob(f"{parts[1]}-*.ebuild")
        ):
            atoms.add(atom)
    return sorted(atoms)


def all_packages(root: Path = REPOSITORY_ROOT) -> list[str]:
    return sorted(
        {
            f"{path.parent.parent.name}/{path.parent.name}"
            for path in root.glob("*/*/*.ebuild")
        }
    )


def changed_paths(
    before: str,
    after: str,
    root: Path = REPOSITORY_ROOT,
    runner=subprocess.run,
) -> list[str]:
    if not GIT_REVISION.fullmatch(before) or not GIT_REVISION.fullmatch(after):
        raise BumpError("invalid Git revision supplied for smoke-test discovery")
    if ZERO_REVISION.fullmatch(before):
        return [str(path.relative_to(root)) for path in root.glob("*/*/*.ebuild")]
    completed = runner(
        ["git", "diff", "--name-only", before, after],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.splitlines()


def matrix(atoms: Iterable[str], root: Path = REPOSITORY_ROOT) -> dict[str, object]:
    include: list[dict[str, str]] = []
    for atom in sorted(set(atoms)):
        release = highest(non_live_ebuilds(ebuilds(atom, root)))
        profile = SMOKE_PROFILE.get(atom, "")
        include.append(
            {
                "atom": atom,
                "profile": profile,
                "slug": atom.replace("/", "-"),
                "use": SMOKE_USE.get(atom, ""),
                "version": release.version,
            }
        )
    return {"has_packages": bool(include), "matrix": {"include": include}}


def matrix_json(atoms: Iterable[str], root: Path = REPOSITORY_ROOT) -> str:
    return json.dumps(matrix(atoms, root), separators=(",", ":"), sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments == ["--all"]:
            atoms = all_packages()
        elif len(arguments) == 2 and not any(
            value.startswith("-") for value in arguments
        ):
            atoms = changed_packages(changed_paths(arguments[0], arguments[1]))
        else:
            print("usage: smoke_matrix.py --all | BEFORE AFTER", file=sys.stderr)
            return 2
        print(matrix_json(atoms))
    except (BumpError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"smoke_matrix.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
