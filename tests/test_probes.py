from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
from io import StringIO
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_probe(relative_path: str, name: str):
    path = ROOT / relative_path
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class DesktopProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = load_probe(
            "app-admin/1password-bin/latest_version.py", "desktop_latest_version"
        )

    def test_normalizes_epoch_and_revision_and_selects_newest_stable(self):
        package_index = """
Package: unrelated
Version: 99.99.99

Package: 1password
Version: 1:8.12.28-1

Package: 1password
Version: 8.12.30

Package: 1password
Version: 8.12.31-beta.1-1
"""
        self.assertEqual(self.probe.parse_packages(package_index), "8.12.30")
        self.assertEqual(
            self.probe.normalize_debian_version("2:8.12.29-1"), "8.12.29"
        )

    def test_malformed_or_missing_release_fails(self):
        with self.assertRaises(RuntimeError):
            self.probe.parse_packages("Package: something-else\nVersion: 1.0.0\n")
        with self.assertRaises(RuntimeError):
            self.probe.parse_packages("Package: 1password\nVersion: 8.12.30-beta.1-1\n")
        with self.assertRaises(RuntimeError):
            self.probe.parse_packages("Package: 1password\nVersion: malformed\n")

    def test_main_prints_only_the_version(self):
        self.probe.latest_stable_version = lambda: "8.12.30"
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = self.probe.main([])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "8.12.30\n")
        self.assertEqual(stderr.getvalue(), "")


class ChatGPTProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = load_probe(
            "app-misc/chatgpt-bin/latest_version.py", "chatgpt_latest_version"
        )

    @staticmethod
    def package_index(architecture: str, version: str = "26.803.81509") -> str:
        return f"""Package: chatgpt
Version: {version}
Architecture: {architecture}
Filename: pool/main/c/chatgpt/chatgpt_{version}_{architecture}.deb

"""

    def test_selects_newest_stable_release_with_expected_artifact(self):
        package_index = (
            self.package_index("amd64", "26.803.81508")
            + self.package_index("amd64", "26.803.81509")
        )
        self.assertEqual(
            self.probe.parse_packages(package_index, "amd64"), "26.803.81509"
        )

    def test_rejects_wrong_architecture_and_malformed_artifact(self):
        with self.assertRaises(RuntimeError):
            self.probe.parse_packages(self.package_index("arm64"), "amd64")
        malformed = self.package_index("amd64").replace(
            "chatgpt_26.803.81509_amd64.deb", "chatgpt_latest_amd64.deb"
        )
        with self.assertRaises(RuntimeError):
            self.probe.parse_packages(malformed, "amd64")

    def test_requires_architecture_versions_to_match(self):
        with self.assertRaisesRegex(RuntimeError, "architecture versions do not match"):
            self.probe.latest_stable_version(
                {
                    "amd64": self.package_index("amd64", "26.803.81509"),
                    "arm64": self.package_index("arm64", "26.803.81508"),
                }
            )

    def test_main_prints_only_the_version(self):
        original = self.probe.latest_stable_version
        try:
            self.probe.latest_stable_version = lambda: "26.803.81509"
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = self.probe.main([])
        finally:
            self.probe.latest_stable_version = original
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "26.803.81509\n")
        self.assertEqual(stderr.getvalue(), "")


class CliProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = load_probe(
            "app-admin/op-cli-bin/latest_version.py", "cli_latest_version"
        )

    def test_selects_newest_stable_article_and_ignores_prereleases(self):
        feed = """
<html><body>
  <article class="beta"><h3>2.99.0-beta.1</h3></article>
  <article><h3>2.38.1 <span>(build 1)</span></h3></article>
  <article><h3>2.35.0</h3></article>
  <article><h3>2.38.2-beta.1</h3></article>
</body></html>
"""
        self.assertEqual(self.probe.parse_release_feed(feed), "2.38.1")

    def test_malformed_or_missing_release_fails(self):
        with self.assertRaises(RuntimeError):
            self.probe.parse_release_feed("<article><h3>not-a-version</h3></article>")
        with self.assertRaises(RuntimeError):
            self.probe.parse_release_feed(
                '<article class="beta"><h3>2.99.0-beta.1</h3></article>'
            )

    def test_main_prints_only_the_version(self):
        self.probe.latest_stable_version = lambda: "2.38.1"
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = self.probe.main([])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "2.38.1\n")
        self.assertEqual(stderr.getvalue(), "")


class NextcloudProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = load_probe(
            "net-misc/nextcloud-client/latest_version.py",
            "nextcloud_latest_version",
        )

    def test_parses_latest_stable_release(self):
        payload = '{"tag_name":"v34.0.1","draft":false,"prerelease":false}'
        self.assertEqual(self.probe.parse_release(payload), "34.0.1")

    def test_rejects_prereleases_and_malformed_versions(self):
        with self.assertRaises(RuntimeError):
            self.probe.parse_release(
                '{"tag_name":"v34.0.2-rc1","draft":false,"prerelease":true}'
            )
        with self.assertRaises(RuntimeError):
            self.probe.parse_release(
                '{"tag_name":"latest","draft":false,"prerelease":false}'
            )

    def test_main_prints_only_the_version(self):
        self.probe.latest_stable_version = lambda: "34.0.1"
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = self.probe.main([])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "34.0.1\n")
        self.assertEqual(stderr.getvalue(), "")


class HeliumProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = load_probe(
            "www-client/helium-bin/latest_version.py",
            "helium_latest_version",
        )

    @staticmethod
    def release(version: str = "0.15.3.1") -> str:
        return f"""{{
            "tag_name": "{version}",
            "draft": false,
            "prerelease": false,
            "assets": [
                {{"name": "helium-{version}-x86_64_linux.tar.xz"}},
                {{"name": "helium-{version}-arm64_linux.tar.xz"}}
            ]
        }}"""

    def test_parses_stable_release_with_both_tarballs(self):
        self.assertEqual(self.probe.parse_release(self.release()), "0.15.3.1")

    def test_rejects_prereleases_and_incomplete_assets(self):
        prerelease = self.release().replace('"prerelease": false', '"prerelease": true')
        with self.assertRaises(RuntimeError):
            self.probe.parse_release(prerelease)

        release = json.loads(self.release())
        release["assets"].pop()
        with self.assertRaisesRegex(RuntimeError, "arm64_linux.tar.xz"):
            self.probe.parse_release(json.dumps(release))

    def test_rejects_malformed_version(self):
        with self.assertRaisesRegex(RuntimeError, "unsupported stable Helium version"):
            self.probe.parse_release(self.release("latest"))

    def test_main_prints_only_the_version(self):
        self.probe.latest_stable_version = lambda: "0.15.3.1"
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = self.probe.main([])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "0.15.3.1\n")
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
