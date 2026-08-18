from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import update_readme


def make_package(
    root: Path,
    atom: str,
    versions: list[tuple[str, str]],
    *,
    iuse: str = "",
    metadata: str | None = None,
) -> Path:
    directory = root / atom
    directory.mkdir(parents=True)
    package = directory.name
    for version, keywords in versions:
        (directory / f"{package}-{version}.ebuild").write_text(
            "\n".join(
                [
                    "EAPI=8",
                    'DESCRIPTION="Fixture package"',
                    f'KEYWORDS="{keywords}"',
                    f'IUSE="{iuse}"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
    if metadata is not None:
        (directory / "metadata.xml").write_text(metadata, encoding="utf-8")
    return directory


class CatalogueTests(unittest.TestCase):
    def test_renders_versions_descriptions_and_use_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_package(
                root,
                "app-test/fixture",
                [("1.0", "amd64 arm64"), ("1.1", "-* ~amd64 ~arm64")],
                iuse="test feature",
                metadata="""<pkgmetadata>
                    <longdescription>A useful <pkg>fixture</pkg> package.</longdescription>
                    <use><flag name="feature">Enable the useful feature.</flag></use>
                </pkgmetadata>
                """,
            )

            rendered = update_readme.render(root)

            self.assertIn("### `app-test/fixture`", rendered)
            self.assertIn("A useful fixture package.", rendered)
            self.assertIn("`1.0` (`amd64`, `arm64`)", rendered)
            self.assertIn("`1.1` (`~amd64`, `~arm64`)", rendered)
            self.assertNotIn("`-*`", rendered)
            self.assertIn("- `feature` — Enable the useful feature.", rendered)
            self.assertIn("- `test` — Build and run the upstream test suite.", rendered)

    def test_updates_only_the_marked_catalogue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_package(root, "app-test/fixture", [("1.0", "~amd64")])
            readme = root / "README.md"
            readme.write_text(
                f"before\n{update_readme.START_MARKER}\nstale\n"
                f"{update_readme.END_MARKER}\nafter\n",
                encoding="utf-8",
            )

            self.assertTrue(update_readme.update(root, readme, check=True))
            self.assertEqual(readme.read_text(encoding="utf-8").count("stale"), 1)
            self.assertTrue(update_readme.update(root, readme))
            contents = readme.read_text(encoding="utf-8")
            self.assertIn("before", contents)
            self.assertIn("### `app-test/fixture`", contents)
            self.assertIn("after", contents)
            self.assertFalse(update_readme.update(root, readme, check=True))

    def test_repository_catalogue_is_current(self):
        self.assertFalse(update_readme.update(check=True))


class CommandTests(unittest.TestCase):
    def test_rejects_unknown_arguments(self):
        self.assertEqual(update_readme.main(["--write"]), 2)


if __name__ == "__main__":
    unittest.main()
