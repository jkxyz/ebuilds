#!/usr/bin/env python3
"""Print pending package updates as a GitHub Actions matrix."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Callable

try:
    from .bump_packages import BumpError, check_bump, ebuilds
except ImportError:  # pragma: no cover - used when run as a script
    from bump_packages import BumpError, check_bump, ebuilds


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ProbeRunner = Callable[[Path], str]


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


def run_probe(probe: Path, root: Path = REPOSITORY_ROOT) -> str:
    """Run one version probe and return its single-line result."""

    completed = subprocess.run(
        [sys.executable, str(probe)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or f"exit status {completed.returncode}"
        raise BumpError(f"version probe failed for {probe.relative_to(root)}: {detail}")
    lines = completed.stdout.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise BumpError(f"version probe returned invalid output for {probe.relative_to(root)}")
    return lines[0].strip()


def updates(
    root: Path = REPOSITORY_ROOT,
    probe_runner: ProbeRunner | None = None,
) -> list[dict[str, str]]:
    """Return tracked packages whose probes report a newer release."""

    if probe_runner is None:
        probe_runner = lambda probe: run_probe(probe, root)

    result: list[dict[str, str]] = []
    probes_root = root / "scripts" / "latest_versions"
    for package in discover(root):
        probe = probes_root / f"{package['atom']}.py"
        status = check_bump(package["atom"], probe_runner(probe), root=root)
        if status.updated:
            result.append({**package, "version": status.version})
    return result


def matrix_json(
    root: Path = REPOSITORY_ROOT,
    probe_runner: ProbeRunner | None = None,
) -> str:
    packages = updates(root, probe_runner)
    result = {"has_updates": bool(packages), "matrix": {"include": packages}}
    return json.dumps(result, separators=(",", ":"), sort_keys=True)


def main() -> int:
    if len(sys.argv) != 1:
        print("updates_matrix.py accepts no arguments", file=sys.stderr)
        return 2
    try:
        print(matrix_json())
    except (BumpError, OSError, ValueError) as error:
        print(f"updates_matrix.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
