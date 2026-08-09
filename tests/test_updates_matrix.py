from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts import updates_matrix


def make_ebuild(directory: Path, package: str, version: str) -> None:
    (directory / f"{package}-{version}.ebuild").write_text(
        'EAPI=8\nDESCRIPTION="fixture"\nKEYWORDS="~amd64"\n', encoding="utf-8"
    )


class UpdatesMatrixTests(unittest.TestCase):
    def test_discovery_is_opt_in_and_sorted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            fixture = root / "app-test" / "fixture-bin"
            fixture.mkdir(parents=True)
            (fixture / "latest_version.py").write_text("print('1.0.0')\n", encoding="utf-8")
            make_ebuild(fixture, "fixture-bin", "1.0.0")

            another = root / "app-test" / "another"
            another.mkdir()
            (another / "latest_version.py").write_text("print('1.0.0')\n", encoding="utf-8")
            make_ebuild(another, "another", "1.0.0")

            without_ebuild = root / "app-test" / "no-ebuild"
            without_ebuild.mkdir()
            (without_ebuild / "latest_version.py").write_text("", encoding="utf-8")

            self.assertEqual(
                updates_matrix.discover(root),
                [
                    {"atom": "app-test/another", "slug": "app-test-another"},
                    {"atom": "app-test/fixture-bin", "slug": "app-test-fixture-bin"},
                ],
            )
            self.assertEqual(
                updates_matrix.matrix_json(root),
                '{"has_updates":false,"matrix":{"include":[]}}',
            )

    def test_matrix_contains_only_newer_releases(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            current = root / "app-test" / "current"
            current.mkdir(parents=True)
            (current / "latest_version.py").write_text("print('2.0.0')\n", encoding="utf-8")
            make_ebuild(current, "current", "2.0.0-r1")

            outdated = root / "app-test" / "outdated"
            outdated.mkdir()
            (outdated / "latest_version.py").write_text("print('1.2.0')\n", encoding="utf-8")
            make_ebuild(outdated, "outdated", "1.1.0")

            self.assertEqual(
                updates_matrix.updates(root),
                [
                    {
                        "atom": "app-test/outdated",
                        "slug": "app-test-outdated",
                        "version": "1.2.0",
                    }
                ],
            )
            self.assertEqual(
                updates_matrix.matrix_json(root),
                '{"has_updates":true,"matrix":{"include":[{"atom":"app-test/outdated","slug":"app-test-outdated","version":"1.2.0"}]}}',
            )

    def test_older_probe_version_fails_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "app-test" / "fixture-bin"
            package.mkdir(parents=True)
            (package / "latest_version.py").write_text("print('1.1.0')\n", encoding="utf-8")
            make_ebuild(package, "fixture-bin", "1.2.0")

            with self.assertRaisesRegex(updates_matrix.BumpError, "older than local version"):
                updates_matrix.matrix_json(root)

    def test_probe_must_print_exactly_one_line(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "app-test" / "fixture-bin"
            package.mkdir(parents=True)
            (package / "latest_version.py").write_text(
                "print('1.1.0')\nprint('unexpected')\n", encoding="utf-8"
            )
            make_ebuild(package, "fixture-bin", "1.0.0")

            with self.assertRaisesRegex(updates_matrix.BumpError, "invalid output"):
                updates_matrix.matrix_json(root)

    def test_failed_probe_fails_discovery_with_its_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "app-test" / "fixture-bin"
            package.mkdir(parents=True)
            (package / "latest_version.py").write_text(
                "import sys\nprint('upstream unavailable', file=sys.stderr)\nraise SystemExit(1)\n",
                encoding="utf-8",
            )
            make_ebuild(package, "fixture-bin", "1.0.0")

            with self.assertRaisesRegex(updates_matrix.BumpError, "upstream unavailable"):
                updates_matrix.matrix_json(root)

    def test_main_rejects_arguments(self):
        original = updates_matrix.sys.argv
        try:
            updates_matrix.sys.argv = ["updates_matrix.py", "--format", "github-matrix"]
            self.assertEqual(updates_matrix.main(), 2)
        finally:
            updates_matrix.sys.argv = original


if __name__ == "__main__":
    unittest.main()
