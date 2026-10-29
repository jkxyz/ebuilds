from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "app-emacs/ghostel" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load("ghostel_update", "update.py")
probe = load("ghostel_probe", "latest_version.py")


class GhostelUpdateTests(unittest.TestCase):
    def test_probe_accepts_stable_release_and_rejects_prerelease(self):
        self.assertEqual(probe.parse_release(json.dumps({"tag_name": "v0.59.0"})), "0.59.0")
        for release in ({"tag_name": "v0.60.0", "prerelease": True}, {"tag_name": "main"}):
            with self.assertRaises(RuntimeError):
                probe.parse_release(json.dumps(release))

    def test_collects_fetched_transitive_dependencies_and_skips_unused_lazy_ones(self):
        manifests = [
            {"dependencies": {"ghostty": {"hash": "ghostty-hash", "url": "https://github.com/ghostty-org/ghostty/archive/abc.tar.gz"}}},
            {"dependencies": {
                "selected": {"hash": "selected-hash", "url": "https://example.org/selected.tar.gz", "lazy": True},
                "unused": {"hash": "unused-hash", "url": "https://example.org/unused.tar.gz", "lazy": True},
                "local": {"path": "pkg/local"},
            }},
            {"dependencies": []},  # Zig serializes empty .{} as an empty tuple.
        ]
        self.assertEqual(hook.dependency_archives(manifests, {"ghostty-hash", "selected-hash"}), {
            "ghostty-abc.tar.gz": "https://github.com/ghostty-org/ghostty/archive/abc.tar.gz",
            "selected.tar.gz": "https://example.org/selected.tar.gz",
        })

    def test_rejects_missing_dependency_url_and_filename_collision(self):
        with self.assertRaisesRegex(RuntimeError, "no upstream URL"):
            hook.dependency_archives([], {"unknown-hash"})
        manifests = [{"dependencies": {
            "one": {"hash": "one", "url": "https://one.example/a.tar.gz"},
            "two": {"hash": "two", "url": "https://two.example/a.tar.gz"},
        }}]
        with self.assertRaisesRegex(RuntimeError, "conflicting dependency archive"):
            hook.dependency_archives(manifests, {"one", "two"})

    def test_rejects_non_archive_or_shell_syntax_in_upstream_url(self):
        for url in ("git+https://github.com/example/repo", "https://example.org/a.tar.gz?token=x", "https://example.org/$(id).tar.gz", "https://example.org/a.ebuild"):
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                hook.archive_name(url)

    def test_replaces_only_dependency_block_in_sorted_order(self):
        before = 'EAPI=8\ndeclare -A ZBS_DEPENDENCIES=(\n\t[old.tar.gz]="old"\n)\ninherit zig\n'
        archives = {"z.tar.gz": "https://example.org/z.tar.gz", "a.tar.gz": "https://example.org/a.tar.gz"}
        after = hook.replace_dependencies(before, archives)
        self.assertEqual(after, 'EAPI=8\ndeclare -A ZBS_DEPENDENCIES=(\n\t[a.tar.gz]="https://example.org/a.tar.gz"\n\t[z.tar.gz]="https://example.org/z.tar.gz"\n)\ninherit zig\n')
        self.assertEqual(hook.replace_dependencies(after, archives), after)
        for invalid in ("inherit zig\n", before + before):
            with self.assertRaisesRegex(RuntimeError, "exactly one"):
                hook.replace_dependencies(invalid, archives)


if __name__ == "__main__":
    unittest.main()
