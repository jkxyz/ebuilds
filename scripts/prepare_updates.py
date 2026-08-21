#!/usr/bin/env python3
"""Prepare isolated package update patches with the Gentoo tools container."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

try:
    from .bump_packages import validate_atom, validate_version
except ImportError:  # pragma: no cover - used when run as a script
    from bump_packages import validate_atom, validate_version


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
Runner = Callable[..., subprocess.CompletedProcess[str]]
CONTAINER_SCRIPT = """\
git config --global --add safe.directory /work
scripts/bump_packages.py "$ATOM" "$VERSION" > /prepared/release
updated=$(sed -n 's/^updated=//p' /prepared/release)
ebuild=$(sed -n 's/^ebuild=//p' /prepared/release)
if [[ "$updated" == "true" ]]; then
    pkgcheck scan --exit GentooCI --cache-dir /tmp/pkgcheck "${ATOM}/${ebuild}"
    python scripts/update_readme.py
fi
"""


class PrepareError(RuntimeError):
    """An update could not be prepared safely."""


@dataclass(frozen=True)
class Update:
    atom: str
    slug: str
    version: str


def load_updates(value: str) -> list[Update]:
    """Validate and return the discovered update matrix."""

    try:
        document = json.loads(value)
        entries = document["matrix"]["include"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise PrepareError(
            "updates JSON does not contain a matrix.include list"
        ) from error
    if not isinstance(entries, list):
        raise PrepareError("updates JSON matrix.include is not a list")

    updates: list[Update] = []
    slugs: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise PrepareError("updates JSON contains a non-object matrix item")
        try:
            atom = entry["atom"]
            slug = entry["slug"]
            version = entry["version"]
        except KeyError as error:
            raise PrepareError(f"matrix item is missing {error.args[0]}") from error
        if not all(isinstance(item, str) for item in (atom, slug, version)):
            raise PrepareError("matrix item fields must be strings")
        validate_atom(atom)
        validate_version(version)
        if slug != atom.replace("/", "-"):
            raise PrepareError(f"unexpected slug {slug!r} for {atom}")
        if slug in slugs:
            raise PrepareError(f"duplicate update slug: {slug}")
        slugs.add(slug)
        updates.append(Update(atom, slug, version))
    return updates


def read_release(path: Path, update: Update) -> dict[str, str]:
    """Read the stable key/value output produced by bump_packages.py."""

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if not separator or key in values:
            raise PrepareError(f"invalid release output for {update.atom}")
        values[key] = value
    expected = {"updated", "previous_version", "version", "ebuild"}
    if set(values) != expected:
        raise PrepareError(f"incomplete release output for {update.atom}")
    if values["updated"] not in {"true", "false"}:
        raise PrepareError(f"invalid updated value for {update.atom}")
    validate_version(values["previous_version"])
    if values["version"] != update.version:
        raise PrepareError(f"prepared version changed for {update.atom}")
    package = update.atom.split("/", 1)[1]
    if (
        Path(values["ebuild"]).name != values["ebuild"]
        or not values["ebuild"].startswith(f"{package}-")
        or not values["ebuild"].endswith(".ebuild")
    ):
        raise PrepareError(f"invalid ebuild name for {update.atom}")
    return values


def run_update(
    update: Update,
    *,
    root: Path,
    output: Path,
    tools_image: str,
    repository_container: str,
    runner: Runner,
) -> dict[str, str] | None:
    """Prepare one update in a disposable local Git clone."""

    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"prepare-{update.slug}-") as temporary:
        temporary_path = Path(temporary)
        worktree = temporary_path / "repository"
        release = temporary_path / "release"
        runner(
            [
                "git",
                "clone",
                "--no-hardlinks",
                "--local",
                "--no-tags",
                str(root),
                str(worktree),
            ],
            cwd=root,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        runner(
            [
                "docker",
                "run",
                "--rm",
                "--volumes-from",
                f"{repository_container}:ro",
                "--volume",
                f"{worktree}:/work",
                "--volume",
                f"{temporary_path}:/prepared",
                "--workdir",
                "/work",
                "--env",
                f"ATOM={update.atom}",
                "--env",
                f"VERSION={update.version}",
                tools_image,
                "bash",
                "-euo",
                "pipefail",
                "-c",
                CONTAINER_SCRIPT,
            ],
            cwd=root,
            check=True,
            stdout=sys.stderr,
            stderr=sys.stderr,
            text=True,
        )
        values = read_release(release, update)
        if values["updated"] == "false":
            return None

        runner(
            ["git", "add", "--intent-to-add", "--", update.atom, "README.md"],
            cwd=worktree,
            check=True,
            stdout=subprocess.DEVNULL,
            text=True,
        )
        completed = runner(
            [
                "git",
                "diff",
                "--binary",
                "--full-index",
                "HEAD",
                "--",
                update.atom,
                "README.md",
            ],
            cwd=worktree,
            check=True,
            capture_output=True,
            text=True,
        )
        if not completed.stdout:
            raise PrepareError(f"prepared update has no diff for {update.atom}")
        patch = f"{update.slug}.patch"
        (output / patch).write_text(completed.stdout, encoding="utf-8")
        return {
            "atom": update.atom,
            "slug": update.slug,
            "previous_version": values["previous_version"],
            "version": values["version"],
            "patch": patch,
        }


def error_message(error: Exception) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        parts = [str(part) for part in error.cmd]
        if parts[:2] == ["docker", "run"]:
            parts = parts[:2]
        command = shlex.join(parts)
        return f"command exited {error.returncode}: {command}"
    return str(error)


def prepare(
    updates_json: str,
    *,
    root: Path = REPOSITORY_ROOT,
    output: Path,
    tools_image: str,
    repository_container: str,
    runner: Runner = subprocess.run,
) -> dict[str, object]:
    """Prepare every update, retaining successes when another package fails."""

    output.mkdir(parents=True, exist_ok=True)
    prepared: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    for update in load_updates(updates_json):
        print(f"Preparing {update.atom} {update.version}", file=sys.stderr)
        try:
            item = run_update(
                update,
                root=root,
                output=output,
                tools_image=tools_image,
                repository_container=repository_container,
                runner=runner,
            )
            if item is not None:
                prepared.append(item)
        except (OSError, PrepareError, ValueError, subprocess.SubprocessError) as error:
            failures.append({"atom": update.atom, "message": error_message(error)})
    return {
        "has_prepared": bool(prepared),
        "has_failures": bool(failures),
        "matrix": {"include": prepared},
        "failures": failures,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--updates-json", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tools-image", required=True)
    parser.add_argument("--repository-container", required=True)
    arguments = parser.parse_args(argv)
    try:
        result = prepare(
            arguments.updates_json,
            output=arguments.output,
            tools_image=arguments.tools_image,
            repository_container=arguments.repository_container,
        )
    except (OSError, PrepareError, ValueError) as error:
        print(f"prepare_updates.py: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
