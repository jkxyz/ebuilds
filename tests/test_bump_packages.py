from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import bump_packages


def make_ebuild(directory: Path, package: str, version: str, keywords: str) -> Path:
    path = directory / f"{package}-{version}.ebuild"
    path.write_text(
        f'EAPI=8\nDESCRIPTION="fixture"\nKEYWORDS="{keywords}"\n',
        encoding="utf-8",
    )
    return path


class BumpFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.package = self.root / "app-test" / "fixture-bin"
        self.package.mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def add(self, version: str, keywords: str) -> Path:
        return make_ebuild(self.package, "fixture-bin", version, keywords)

    def fake_runner(self, calls, generated_keywords="~amd64 ~arm64"):
        def runner(command, cwd, check=True, **kwargs):
            calls.append((list(command), Path(cwd), kwargs))
            if command[0] == "pkgbump":
                source = Path(cwd) / command[2]
                version = command[3]
                destination = Path(cwd) / f"fixture-bin-{version}.ebuild"
                contents = source.read_text(encoding="utf-8")
                contents = contents.replace(
                    source.name.removesuffix(".ebuild"), destination.name.removesuffix(".ebuild")
                )
                contents = contents.replace(
                    'KEYWORDS="amd64 arm64"', f'KEYWORDS="{generated_keywords}"'
                ).replace(
                    'KEYWORDS="~amd64 ~arm64"', f'KEYWORDS="{generated_keywords}"'
                )
                destination.write_text(contents, encoding="utf-8")
                (Path(cwd) / ".pkgbump-pv").write_text("fixture", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        return runner


class BumpTests(BumpFixture):
    def test_current_version_is_a_noop(self):
        self.add("1.2.0", "~amd64 ~arm64")
        calls = []
        result = bump_packages.bump(
            "app-test/fixture-bin", "1.2.0", root=self.root, runner=self.fake_runner(calls)
        )
        self.assertFalse(result.updated)
        self.assertEqual(result.ebuild, "fixture-bin-1.2.0.ebuild")
        self.assertEqual(calls, [])

    def test_current_upstream_version_with_local_revision_is_a_noop(self):
        self.add("1.2.0-r1", "~amd64 ~arm64")
        calls = []
        result = bump_packages.bump(
            "app-test/fixture-bin", "1.2.0", root=self.root, runner=self.fake_runner(calls)
        )
        self.assertFalse(result.updated)
        self.assertEqual(result.previous_version, "1.2.0-r1")
        self.assertEqual(result.version, "1.2.0")
        self.assertEqual(result.ebuild, "fixture-bin-1.2.0-r1.ebuild")
        self.assertEqual(calls, [])

    def test_older_upstream_version_is_rejected_with_local_revision(self):
        self.add("1.2.0-r1", "~amd64 ~arm64")
        calls = []
        with self.assertRaisesRegex(bump_packages.BumpError, "older than local version"):
            bump_packages.bump(
                "app-test/fixture-bin", "1.1.0", root=self.root, runner=self.fake_runner(calls)
            )
        self.assertEqual(calls, [])

    def test_testing_source_is_removed_but_stable_and_live_are_preserved(self):
        stable = self.add("1.0.0", "amd64 arm64")
        testing = self.add("1.1.0", "~amd64 ~arm64")
        live = self.add("9999", "**")
        calls = []
        result = bump_packages.bump(
            "app-test/fixture-bin", "1.2.0", root=self.root, runner=self.fake_runner(calls)
        )
        self.assertTrue(result.updated)
        self.assertTrue(stable.exists())
        self.assertFalse(testing.exists())
        self.assertTrue(live.exists())
        self.assertTrue((self.package / result.ebuild).exists())
        self.assertFalse((self.package / ".pkgbump-pv").exists())
        self.assertEqual([call[0][0] for call in calls], ["pkgbump", "pkgdev"])
        self.assertEqual(calls[0][0], ["pkgbump", "--no-diff", testing.name, "1.2.0"])

    def test_stable_source_is_preserved(self):
        stable = self.add("1.0.0", "amd64 arm64")
        calls = []
        bump_packages.bump(
            "app-test/fixture-bin", "1.1.0", root=self.root, runner=self.fake_runner(calls)
        )
        self.assertTrue(stable.exists())

    def test_unkeyworded_source_is_preserved(self):
        source = self.add("0.9.0", "")
        source.write_text('EAPI=8\nDESCRIPTION="fixture"\n', encoding="utf-8")
        self.add("1.0.0", "~amd64")
        calls = []
        bump_packages.bump(
            "app-test/fixture-bin", "1.1.0", root=self.root, runner=self.fake_runner(calls)
        )
        self.assertTrue(source.exists())

    def test_generated_keywords_are_validated(self):
        self.add("1.0.0", "amd64")
        calls = []
        with self.assertRaises(bump_packages.BumpError):
            bump_packages.bump(
                "app-test/fixture-bin",
                "1.1.0",
                root=self.root,
                runner=self.fake_runner(calls, generated_keywords="amd64 ~arm64"),
            )
        self.assertEqual([call[0][0] for call in calls], ["pkgbump"])


class CommandTests(BumpFixture):
    def test_main_requires_exactly_atom_and_version(self):
        self.assertEqual(bump_packages.main([]), 2)
        self.assertEqual(bump_packages.main(["app-test/fixture-bin"]), 2)
        self.assertEqual(bump_packages.main(["--version", "1.2.0"]), 2)


if __name__ == "__main__":
    unittest.main()
