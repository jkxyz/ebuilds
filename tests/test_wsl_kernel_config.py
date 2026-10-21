from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class KernelDeploymentTests(unittest.TestCase):
    def test_deployment_guards(self):
        # Exercise the ebuild's config phase without invoking Windows or Portage.
        harness = r'''
inherit() { :; }
elog() { printf '%s\n' "$*"; }
ewarn() { printf '%s\n' "$*" >&2; }
dist-kernel_get_image_path() { printf '%s\n' arch/x86/boot/bzImage; }
env() {
    case "${@: -1}" in
        WSL_KERNEL_DIR) printf '%s\n' "$_test_destination"; [[ -n $_test_destination ]] ;;
        WSL_AUTO_UPDATE_CONFIG) printf '%s\n' "$_test_auto_update"; return "$_test_config_status" ;;
        *) return 2 ;;
    esac
}
command() { printf '%s\n' "$powershell_stub"; }
wslpath() { printf '%s\n' "$2"; }
PV=6.18.54.1 PN=wsl2-kernel P=wsl2-kernel-6.18.54.1
PF=$P CATEGORY=sys-kernel KV_FULL=6.18.54.1-microsoft-standard-WSL2
source "$1"
ROOT=$2 EROOT=$2 _test_destination=$3 powershell_stub=$4
_test_auto_update=$5 _test_config_status=$6
pkg_config
status=$?
printf 'CALLER_CWD=%s\n' "$PWD"
exit "$status"
'''
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            powershell = directory / "powershell.exe"
            powershell.write_text(
                "#!/bin/bash\nprintf '%s\\n' DEPLOYED \"$@\"\n"
                "printf 'POWERSHELL_CWD=%s\\n' \"$PWD\"\n"
            )
            powershell.chmod(0o755)
            destination_dir = directory / "Windows destination"
            destination_dir.mkdir()
            portage_dir = directory / "private build directory"
            portage_dir.mkdir()
            cases = [
                ("", str(destination_dir), "", 1, True, ""),  # EAPI 8 represents / as an empty string.
                ("", "", "true", 0, False, ""),
                ("/alternate-root", temporary, "true", 0, False, "EROOT='/alternate-root'"),
                ("", str(directory / "missing"), "true", 0, False, "WSL_KERNEL_DIR"),
                ("", "relative/path", "true", 0, False, "WSL_KERNEL_DIR"),
                ("", str(destination_dir), "true", 0, True, ""),
                ("", str(destination_dir), "false", 0, True, ""),
                ("", str(destination_dir), "yes", 0, True, "must be true or false"),
                ("", str(destination_dir), "true", 2, True, "Could not read WSL_AUTO_UPDATE_CONFIG"),
            ]
            ebuilds = list((ROOT / "sys-kernel/wsl2-kernel").glob("*.ebuild"))
            self.assertTrue(ebuilds, "No WSL kernel ebuilds found")
            for ebuild in ebuilds:
                for root, destination, auto, config_status, deploy, warning in cases:
                    with self.subTest(ebuild=ebuild.name, root=root, destination=destination, auto=auto, config_status=config_status):
                        result = subprocess.run(
                            ["bash", "-c", harness, "test", str(ebuild), root,
                             destination, str(powershell), auto, str(config_status)],
                            cwd=portage_dir, capture_output=True, text=True, check=False,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual("DEPLOYED" in result.stdout, deploy)
                        self.assertIn(f"CALLER_CWD={portage_dir}\n", result.stdout)
                        self.assertEqual(
                            "-UpdateConfig\n" in result.stdout,
                            deploy and auto == "true" and config_status == 0,
                        )
                        if deploy:
                            self.assertIn("-WindowStyle\nHidden\n", result.stdout)
                            self.assertIn(f"POWERSHELL_CWD={destination}\n", result.stdout)
                        if warning:
                            self.assertIn(warning, result.stderr)
                        else:
                            self.assertEqual(result.stderr, "")
