from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts import packages_matrix


def make_ebuild(directory: Path, package: str, version: str) -> None:
    (directory / f"{package}-{version}.ebuild").write_text(
        'EAPI=8\nDESCRIPTION="fixture"\nKEYWORDS="~amd64"\n', encoding="utf-8"
    )


class PackagesMatrixTests(unittest.TestCase):
    def test_discovery_is_opt_in_and_sorted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            probes = root / "scripts" / "latest_versions" / "app-test"
            probes.mkdir(parents=True)

            fixture = root / "app-test" / "fixture-bin"
            fixture.mkdir(parents=True)
            (probes / "fixture-bin.py").write_text("print('1.0.0')\n", encoding="utf-8")
            make_ebuild(fixture, "fixture-bin", "1.0.0")

            another = root / "app-test" / "another"
            another.mkdir()
            (probes / "another.py").write_text("print('1.0.0')\n", encoding="utf-8")
            make_ebuild(another, "another", "1.0.0")

            without_ebuild = root / "app-test" / "no-ebuild"
            without_ebuild.mkdir()
            (probes / "no-ebuild.py").write_text("", encoding="utf-8")
            (root / "scripts" / "latest_versions" / "unrelated.py").write_text(
                "", encoding="utf-8"
            )

            self.assertEqual(
                packages_matrix.discover(root),
                [
                    {"atom": "app-test/another", "slug": "app-test-another"},
                    {"atom": "app-test/fixture-bin", "slug": "app-test-fixture-bin"},
                ],
            )
            self.assertEqual(
                packages_matrix.matrix_json(root),
                '{"include":[{"atom":"app-test/another","slug":"app-test-another"},{"atom":"app-test/fixture-bin","slug":"app-test-fixture-bin"}]}',
            )

    def test_main_rejects_arguments(self):
        original = packages_matrix.sys.argv
        try:
            packages_matrix.sys.argv = ["packages_matrix.py", "--format", "github-matrix"]
            self.assertEqual(packages_matrix.main(), 2)
        finally:
            packages_matrix.sys.argv = original


if __name__ == "__main__":
    unittest.main()
