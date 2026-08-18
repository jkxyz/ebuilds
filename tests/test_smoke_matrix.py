from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import smoke_matrix


def make_ebuild(root: Path, atom: str, version: str) -> None:
    directory = root / atom
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{directory.name}-{version}.ebuild").write_text(
        'EAPI=8\nDESCRIPTION="fixture"\nKEYWORDS="~amd64"\n',
        encoding="utf-8",
    )


class SmokeMatrixTests(unittest.TestCase):
    def test_selects_only_packages_with_build_relevant_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_ebuild(root, "app-test/changed", "1.0")
            make_ebuild(root, "app-test/files-changed", "2.0")
            make_ebuild(root, "app-test/metadata-only", "3.0")

            self.assertEqual(
                smoke_matrix.changed_packages(
                    [
                        "README.md",
                        "app-test/changed/changed-1.0.ebuild",
                        "app-test/changed/Manifest",
                        "app-test/files-changed/files/fix.patch",
                        "app-test/metadata-only/metadata.xml",
                        "deleted/package/package-1.ebuild",
                    ],
                    root,
                ),
                ["app-test/changed", "app-test/files-changed"],
            )

    def test_matrix_uses_the_latest_release_and_is_sorted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_ebuild(root, "net-misc/dropbox", "1.0")
            make_ebuild(root, "net-misc/dropbox", "1.2")
            make_ebuild(root, "app-test/another", "2.0")

            result = smoke_matrix.matrix(["net-misc/dropbox", "app-test/another"], root)

            self.assertTrue(result["has_packages"])
            self.assertEqual(
                result["matrix"]["include"],
                [
                    {
                        "atom": "app-test/another",
                        "profile": "",
                        "slug": "app-test-another",
                        "use": "",
                        "version": "2.0",
                    },
                    {
                        "atom": "net-misc/dropbox",
                        "profile": "",
                        "slug": "net-misc-dropbox",
                        "use": "X -selinux",
                        "version": "1.2",
                    },
                ],
            )

    def test_matrix_selects_a_plasma_profile_for_the_dolphin_plugin(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_ebuild(root, "kde-apps/dolphin-plugins-dropbox", "1.0")

            result = smoke_matrix.matrix(
                ["kde-apps/dolphin-plugins-dropbox"], root
            )

            self.assertEqual(
                result["matrix"]["include"][0]["profile"],
                "default/linux/amd64/23.0/desktop/plasma",
            )

    def test_zero_before_revision_selects_all_ebuild_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_ebuild(root, "app-test/fixture", "1.0")
            paths = smoke_matrix.changed_paths("0" * 40, "a" * 40, root)
            self.assertEqual(paths, ["app-test/fixture/fixture-1.0.ebuild"])

    def test_changed_paths_uses_the_requested_push_range(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(
                command, 0, "app-test/pkg/Manifest\n", ""
            )

        paths = smoke_matrix.changed_paths("a" * 40, "b" * 40, runner=runner)
        self.assertEqual(paths, ["app-test/pkg/Manifest"])
        self.assertEqual(
            calls[0][0], ["git", "diff", "--name-only", "a" * 40, "b" * 40]
        )


class CommandTests(unittest.TestCase):
    def test_rejects_invalid_arguments(self):
        self.assertEqual(smoke_matrix.main([]), 2)
        self.assertEqual(smoke_matrix.main(["--unknown"]), 2)


if __name__ == "__main__":
    unittest.main()
