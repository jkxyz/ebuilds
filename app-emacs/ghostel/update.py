#!/usr/bin/env python3
"""Refresh Ghostel's distfiles from the dependencies selected by upstream's build."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ZIG_VERSION = "0.16.0"
TARGETS = (
    "x86_64-linux-gnu", "x86_64-linux-musl",
    "aarch64-linux-gnu", "aarch64-linux-musl",
)
DEPENDENCIES = re.compile(r"^declare -A ZBS_DEPENDENCIES=\(\n.*?^\)", re.M | re.S)
ZON_READER = '''\
const std = @import("std");
pub fn main(init: std.process.Init) !void {
    const manifests = .{ IMPORTS };
    const json = try std.json.Stringify.valueAlloc(init.arena.allocator(), manifests, .{});
    try std.Io.File.stdout().writeStreamingAll(init.io, json);
}
'''


def run_zig(zig: str, source: Path, *args: str) -> str:
    result = subprocess.run(
        [zig, *args],
        cwd=source,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def read_manifests(zig: str, source: Path, paths: list[Path]) -> list[dict]:
    # Let Zig parse ZON, including comments, enum names and escaped strings.
    imports = ", ".join(
        f"@import({json.dumps(path.relative_to(source).as_posix())})" for path in paths
    )
    reader = source / ".gentoo-manifests.zig"
    reader.write_text(ZON_READER.replace("IMPORTS", imports), encoding="utf-8")
    return json.loads(run_zig(zig, source, "run", reader.name))


def archive_name(url: str) -> str:
    if re.fullmatch(r"https://[A-Za-z0-9._~:/%+@=-]+", url) is None:
        raise RuntimeError(f"unsupported dependency URL: {url!r}")
    parsed = urlsplit(url)
    name = Path(parsed.path).name
    parts = parsed.path.strip("/").split("/")
    if parsed.hostname in {"github.com", "codeberg.org"} and len(parts) >= 4 and parts[2] == "archive":
        name = f"{parts[1]}-{name}"
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*\.(?:tar\.(?:gz|xz|zst|bz2)|tgz|zip)", name) is None:
        raise RuntimeError(f"unsupported dependency archive name: {name!r}")
    return name


def dependency_archives(manifests: list[dict], fetched: set[str]) -> dict[str, str]:
    archives: dict[str, str] = {}
    matched: set[str] = set()
    for manifest in manifests:
        for dependency in (manifest.get("dependencies") or {}).values():
            package_hash = dependency.get("hash")
            if package_hash not in fetched:
                continue
            url = dependency["url"]
            name = archive_name(url)
            if name in archives and archives[name] != url:
                raise RuntimeError(f"conflicting dependency archive: {name}")
            archives[name] = url
            matched.add(package_hash)
    if missing := fetched - matched:
        raise RuntimeError(f"no upstream URL found for fetched dependencies: {sorted(missing)}")
    if not archives:
        raise RuntimeError("upstream resolved no dependency archives")
    return archives


def replace_dependencies(contents: str, archives: dict[str, str]) -> str:
    block = "declare -A ZBS_DEPENDENCIES=(\n"
    block += "".join(f'\t[{name}]="{url}"\n' for name, url in sorted(archives.items()))
    block += ")"
    updated, count = DEPENDENCIES.subn(lambda _: block, contents)
    if count != 1:
        raise RuntimeError("expected exactly one ZBS_DEPENDENCIES block")
    return updated


def update(ebuild: Path) -> None:
    match = re.fullmatch(r"ghostel-(\d+\.\d+\.\d+)\.ebuild", ebuild.name)
    if match is None:
        raise RuntimeError(f"unsupported Ghostel ebuild: {ebuild.name}")
    version = match[1]
    contents = ebuild.read_text(encoding="utf-8")
    zig = (
        os.environ.get("ZIG_EXE")
        or shutil.which(f"zig-bin-{ZIG_VERSION}")
        or shutil.which(f"zig-{ZIG_VERSION}")
    )
    if not zig:
        raise RuntimeError(f"install Zig {ZIG_VERSION} or set ZIG_EXE")

    with tempfile.TemporaryDirectory(prefix="ghostel-update-") as temporary:
        work = Path(temporary)
        if run_zig(zig, work, "version").strip() != ZIG_VERSION:
            raise RuntimeError(f"the update hook requires Zig {ZIG_VERSION}")
        archive = work / "release.tar.gz"
        request = Request(
            f"https://github.com/dakra/ghostel/archive/refs/tags/v{version}.tar.gz",
            headers={"User-Agent": "jkxyz-ebuilds-ghostel-update/1"},
        )
        with urlopen(request, timeout=120) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        with tarfile.open(archive) as release:
            release.extractall(work, filter="data")
        source = work / f"ghostel-{version}"
        root_manifest = source / "build.zig.zon"
        manifest = read_manifests(zig, source, [root_manifest])[0]
        if manifest["version"] != version or manifest["minimum_zig_version"] != ZIG_VERSION:
            raise RuntimeError("upstream changed its version or required Zig; review the ebuild and update hook")
        # A clean package directory ensures cached or unrelated packages cannot
        # leak into the generated list. Zig checks upstream's hashes on fetch.
        if (source / "zig-pkg").exists():
            raise RuntimeError("unexpected bundled zig-pkg directory")
        for target in TARGETS:
            # --fetch alone skips lazy dependencies; --help configures the build
            # and resolves them without executing compilation or install steps.
            run_zig(zig, source, "build", "--help", "--release=fast", f"-Dtarget={target}")
        packages = source / "zig-pkg"
        fetched = {path.name for path in packages.iterdir() if path.is_dir()}
        paths = [root_manifest, *sorted(packages.rglob("build.zig.zon"))]
        archives = dependency_archives(read_manifests(zig, source, paths), fetched)
        ebuild.write_text(replace_dependencies(contents, archives), encoding="utf-8")
        print(f"Refreshed {len(archives)} Ghostel dependency archives", file=sys.stderr)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: update.py EBUILD", file=sys.stderr)
        return 2
    try:
        update(Path(sys.argv[1]).resolve())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"ghostel update: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
