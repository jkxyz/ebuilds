from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import prepare_updates


class PrepareUpdatesTests(unittest.TestCase):
    def test_load_updates_validates_slug_and_duplicate_items(self):
        valid = json.dumps(
            {
                "matrix": {
                    "include": [
                        {
                            "atom": "app-test/fixture-bin",
                            "slug": "app-test-fixture-bin",
                            "version": "2.0.0",
                        }
                    ]
                }
            }
        )
        self.assertEqual(
            prepare_updates.load_updates(valid),
            [
                prepare_updates.Update(
                    "app-test/fixture-bin", "app-test-fixture-bin", "2.0.0"
                )
            ],
        )

        invalid = valid.replace("app-test-fixture-bin", "unexpected")
        with self.assertRaisesRegex(prepare_updates.PrepareError, "unexpected slug"):
            prepare_updates.load_updates(invalid)

        duplicate = json.loads(valid)
        duplicate["matrix"]["include"] *= 2
        with self.assertRaisesRegex(
            prepare_updates.PrepareError, "duplicate update slug"
        ):
            prepare_updates.load_updates(json.dumps(duplicate))

    def test_prepare_writes_patch_and_matrix_metadata(self):
        commands: list[list[str]] = []

        def runner(command, **kwargs):
            commands.append(command)
            if command[:2] == ["git", "clone"]:
                Path(command[-1]).mkdir()
            elif command[:2] == ["docker", "run"]:
                mount = command[
                    command.index("--volume", command.index("--volume") + 1) + 1
                ]
                release = Path(mount.removesuffix(":/prepared")) / "release"
                release.write_text(
                    "updated=true\nprevious_version=1.0.0\nversion=2.0.0\nebuild=fixture-bin-2.0.0.ebuild\n",
                    encoding="utf-8",
                )
            elif command[:2] == ["git", "diff"]:
                return subprocess.CompletedProcess(
                    command, 0, "diff --git a/file b/file\n", ""
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        updates = json.dumps(
            {
                "matrix": {
                    "include": [
                        {
                            "atom": "app-test/fixture-bin",
                            "slug": "app-test-fixture-bin",
                            "version": "2.0.0",
                        }
                    ]
                }
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            result = prepare_updates.prepare(
                updates,
                root=Path(temporary),
                output=output,
                tools_image="tools:latest",
                repository_container="gentoo-repository",
                runner=runner,
            )

            self.assertEqual(
                result,
                {
                    "has_prepared": True,
                    "has_failures": False,
                    "matrix": {
                        "include": [
                            {
                                "atom": "app-test/fixture-bin",
                                "slug": "app-test-fixture-bin",
                                "previous_version": "1.0.0",
                                "version": "2.0.0",
                                "patch": "app-test-fixture-bin.patch",
                            }
                        ]
                    },
                    "failures": [],
                },
            )
            self.assertEqual(
                (output / "app-test-fixture-bin.patch").read_text(encoding="utf-8"),
                "diff --git a/file b/file\n",
            )

        docker = next(
            command for command in commands if command[:2] == ["docker", "run"]
        )
        self.assertIn("gentoo-repository:ro", docker)
        self.assertIn("ATOM=app-test/fixture-bin", docker)
        self.assertIn("VERSION=2.0.0", docker)
        self.assertIn(f"HOST_UID={os.getuid()}", docker)
        self.assertIn(f"HOST_GID={os.getgid()}", docker)
        self.assertIn("trap cleanup EXIT", prepare_updates.CONTAINER_SCRIPT)

    def test_prepare_retains_success_when_another_package_fails(self):
        def runner(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                Path(command[-1]).mkdir()
            elif command[:2] == ["docker", "run"]:
                if "ATOM=app-test/broken" in command:
                    raise subprocess.CalledProcessError(1, command)
                mount = command[
                    command.index("--volume", command.index("--volume") + 1) + 1
                ]
                release = Path(mount.removesuffix(":/prepared")) / "release"
                release.write_text(
                    "updated=true\nprevious_version=1.0.0\nversion=2.0.0\nebuild=working-2.0.0.ebuild\n",
                    encoding="utf-8",
                )
            elif command[:2] == ["git", "diff"]:
                return subprocess.CompletedProcess(command, 0, "patch\n", "")
            return subprocess.CompletedProcess(command, 0, "", "")

        entries = [
            {"atom": "app-test/broken", "slug": "app-test-broken", "version": "2.0.0"},
            {
                "atom": "app-test/working",
                "slug": "app-test-working",
                "version": "2.0.0",
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            result = prepare_updates.prepare(
                json.dumps({"matrix": {"include": entries}}),
                root=Path(temporary),
                output=Path(temporary) / "output",
                tools_image="tools:latest",
                repository_container="gentoo-repository",
                runner=runner,
            )

        self.assertTrue(result["has_prepared"])
        self.assertTrue(result["has_failures"])
        self.assertEqual(result["matrix"]["include"][0]["atom"], "app-test/working")
        self.assertEqual(
            result["failures"],
            [{"atom": "app-test/broken", "message": "command exited 1: docker run"}],
        )

    def test_run_update_creates_patch_that_applies_to_a_clean_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            origin = temporary_path / "origin"
            package = origin / "app-test" / "fixture-bin"
            package.mkdir(parents=True)
            (package / "fixture-bin-1.0.0.ebuild").write_text(
                'EAPI=8\nKEYWORDS="~amd64"\n', encoding="utf-8"
            )
            (origin / "README.md").write_text("old catalogue\n", encoding="utf-8")
            subprocess.run(
                ["git", "init", "-b", "main", origin], check=True, capture_output=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    origin,
                    "config",
                    "user.email",
                    "tests@example.invalid",
                ],
                check=True,
            )
            subprocess.run(
                ["git", "-C", origin, "config", "user.name", "Tests"], check=True
            )
            subprocess.run(["git", "-C", origin, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", origin, "commit", "-m", "fixture"],
                check=True,
                capture_output=True,
            )
            root = temporary_path / "source"
            subprocess.run(
                ["git", "clone", "--depth=1", origin.as_uri(), root],
                check=True,
                capture_output=True,
            )

            def runner(command, **kwargs):
                if command[:2] != ["docker", "run"]:
                    check = kwargs.pop("check")
                    return subprocess.run(command, check=check, **kwargs)
                repository_mount = command[command.index("--volume") + 1]
                repository = Path(repository_mount.removesuffix(":/work"))
                result_mount = command[
                    command.index("--volume", command.index("--volume") + 1) + 1
                ]
                result = Path(result_mount.removesuffix(":/prepared"))
                generated = (
                    repository / "app-test" / "fixture-bin" / "fixture-bin-2.0.0.ebuild"
                )
                generated.write_text('EAPI=8\nKEYWORDS="~amd64"\n', encoding="utf-8")
                (repository / "README.md").write_text(
                    "new catalogue\n", encoding="utf-8"
                )
                (result / "release").write_text(
                    "updated=true\nprevious_version=1.0.0\nversion=2.0.0\nebuild=fixture-bin-2.0.0.ebuild\n",
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 0, "", "")

            output = temporary_path / "output"
            item = prepare_updates.run_update(
                prepare_updates.Update(
                    "app-test/fixture-bin", "app-test-fixture-bin", "2.0.0"
                ),
                root=root,
                output=output,
                tools_image="tools:latest",
                repository_container="gentoo-repository",
                runner=runner,
            )
            checkout = temporary_path / "checkout"
            subprocess.run(
                ["git", "clone", "--local", root, checkout],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", checkout, "apply", output / item["patch"]], check=True
            )

            self.assertTrue(
                (
                    checkout / "app-test" / "fixture-bin" / "fixture-bin-2.0.0.ebuild"
                ).is_file()
            )
            self.assertEqual(
                (checkout / "README.md").read_text(encoding="utf-8"), "new catalogue\n"
            )


if __name__ == "__main__":
    unittest.main()
