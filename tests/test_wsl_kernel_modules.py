from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = os.environ.get("WSL_KERNEL_SOURCE")
TOOLS = ("patch", "mke2fs", "qemu-img", "debugfs")


@unittest.skipUnless(SOURCE and all(shutil.which(tool) for tool in TOOLS),
                     "requires WSL_KERNEL_SOURCE and the module image build tools")
class ModulesImageTests(unittest.TestCase):
    def test_flat_and_nested_layouts_share_module_data(self):
        def run(*args, **kwargs):
            return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "Microsoft/scripts/gen_artifacts_vhdx.sh"
            script.parent.mkdir(parents=True)
            shutil.copyfile(Path(SOURCE) / "Microsoft/scripts/gen_artifacts_vhdx.sh", script)
            run("patch", "-p1", "-i", str(ROOT / "sys-kernel/wsl2-kernel/files/wsl-modules-layout.patch"), cwd=root)
            release = "test-kernel"
            modules = root / "input/lib/modules" / release
            (modules / "kernel/net").mkdir(parents=True)
            (modules / "kernel/net/test.ko").write_text("module fixture\n")
            (modules / "modules.dep").write_text("kernel/net/test.ko:\n")
            (modules / "build").symlink_to("/nonexistent-build-tree")
            headers = root / "headers"
            (headers / "include").mkdir(parents=True)
            (headers / "include/test.h").write_text("header fixture\n")
            perf = root / "perf"
            perf.mkdir()
            image = root / "modules.vhdx"
            run("bash", str(script), str(root / "input"), str(headers), str(perf), release, str(image))
            raw = root / "modules.img"
            run("qemu-img", "convert", "-f", "vhdx", "-O", "raw", str(image), str(raw))

            def inspect(command):
                return run("debugfs", "-R", command, str(raw))

            # WSL 2.7.13 mounts /; newer WSL selects /<release>/modules.
            for prefix in ("", f"/{release}/modules"):
                self.assertEqual(inspect(f"cat {prefix}/modules.dep"), "kernel/net/test.ko:\n")
                self.assertEqual(inspect(f"cat {prefix}/kernel/net/test.ko"), "module fixture\n")
                self.assertNotIn("build", inspect(f"ls -p {prefix or '/'}"))
            flat = inspect("stat /kernel/net/test.ko")
            nested = inspect(f"stat /{release}/modules/kernel/net/test.ko")
            self.assertEqual(re.search(r"Inode: (\d+)", flat).group(1),
                             re.search(r"Inode: (\d+)", nested).group(1))
            self.assertEqual(inspect(f"cat /{release}/linux-headers/include/test.h"), "header fixture\n")
