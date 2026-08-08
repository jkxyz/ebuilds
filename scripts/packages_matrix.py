#!/usr/bin/env python3
"""Print the release-tracked packages as a GitHub Actions matrix."""

from __future__ import annotations

import json
from pathlib import Path
import sys

try:
    from .bump_packages import BumpError, ebuilds
except ImportError:  # pragma: no cover - used when run as a script
    from bump_packages import BumpError, ebuilds


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def discover(root: Path = REPOSITORY_ROOT) -> list[dict[str, str]]:
    """Discover packages opted into automation by an atom-mirrored probe."""

    packages: list[dict[str, str]] = []
    probes_root = root / "scripts" / "latest_versions"
    for probe in sorted(probes_root.glob("*/*.py")):
        if not probe.is_file():
            continue
        relative = probe.relative_to(probes_root)
        if len(relative.parts) != 2:
            continue
        category, filename = relative.parts
        package = Path(filename).stem
        package_path = root / category / package
        if not list(package_path.glob(f"{package}-*.ebuild")):
            continue
        # Parsing the ebuild names here makes an accidentally malformed package
        # fail discovery instead of silently producing an unusable matrix item.
        ebuilds(f"{category}/{package}", root)
        atom = f"{category}/{package}"
        packages.append({"atom": atom, "slug": atom.replace("/", "-")})
    return sorted(packages, key=lambda item: item["atom"])


def matrix_json(root: Path = REPOSITORY_ROOT) -> str:
    return json.dumps({"include": discover(root)}, separators=(",", ":"), sort_keys=True)


def main() -> int:
    if len(sys.argv) != 1:
        print("packages_matrix.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(matrix_json())
    except (BumpError, OSError, ValueError) as error:
        print(f"packages_matrix.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
