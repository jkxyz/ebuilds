# WSL 2 kernel

Builds Microsoft's WSL kernel with its default configuration, plus a VHDX with
matching modules and UAPI headers. Gentoo's `kernel-build` eclass handles the
build, saved configuration, and installed sources for external modules.
Configuration fragments in `/etc/kernel/config.d/*.config` also apply.
Compiler tuning is not changed. Install `dev-util/perf` separately if needed.

## Optional Windows deployment

Create a directory on a Windows drive, then set this in
`/etc/portage/make.conf`:

```bash
WSL_KERNEL_DIR="/mnt/c/Users/josh.kingsley/WSL"
```

Leave the variable unset or empty to install only inside Gentoo and print
manual instructions. A missing directory or unavailable Windows interoperability
also leaves the Gentoo installation usable.

The installation reads the current Portage configuration for these settings,
including when installing a binary package. It copies and verifies the kernel
and modules image into `releases/<package-version>-<content-hashes>/` under the
destination. Rebuilding the same version with different contents creates a
separate directory. Completed releases are not overwritten or automatically
removed, so a running VM can keep its existing modules image open.

By default, deployment prints the exact `kernel=` and `kernelModules=` entries
to put under `[wsl2]` in `%UserProfile%\.wslconfig`. These point directly to the
versioned files, with doubled backslashes. No junction is created: Windows
can reject junctions in WSL boot paths as an untrusted mount point.

To update those two entries automatically, also set:

```bash
WSL_AUTO_UPDATE_CONFIG=true
```

Unset, empty, or `false` leaves `.wslconfig` unchanged. Other values warn and
leave it unchanged. The option requires `WSL_KERNEL_DIR` to be configured.
When enabled, the helper preserves other settings and sections, comments,
line endings, and the text encoding. Missing keys or the `[wsl2]` section are
added. Multiple `[wsl2]` sections are rejected as ambiguous.

The helper replaces `.wslconfig` only after verifying both artifacts. An
existing configuration is backed up beside it as
`.wslconfig.wsl-kernel-backup-<unique-id>`, and the backup path is printed.
A new configuration is created if needed. An unchanged configuration is not
rewritten or backed up again. A failed configuration update leaves the copied
artifacts available for manual selection or retry.

The helper uses Windows PowerShell 5.1 and the current Windows user's profile
and permissions. PowerShell runs with
`-WindowStyle Hidden -NoProfile -NonInteractive`; the execution policy override
applies only to that invocation. Use a direct directory on a local Windows
drive, normally NTFS, without junctions or symlinks in the path.

When ready, run `wsl --shutdown` from Windows, then start Gentoo and check
`uname -r`. This affects every WSL 2 distribution. The ebuild does not stop
WSL or configure a bootloader. Update the configuration while WSL is running,
then shut it down; avoid starting the VM concurrently with deployment.

To retry deployment or select an installed older package without rebuilding:

```bash
sudo emerge --config =sys-kernel/wsl2-kernel-6.18.54.1
```

Old release directories may be removed manually after they are no longer
selected or mounted. A `default` junction from an earlier helper is left
untouched and is no longer used. Replace any old `default` paths in
`.wslconfig` with the printed direct paths, or enable automatic configuration
and rerun deployment.

To recover from a kernel that cannot boot, remove the `kernel` and
`kernelModules` overrides from `.wslconfig` in Windows, run `wsl --shutdown`,
and launch Gentoo using Microsoft's bundled kernel.

## Test the local checkout

These commands use a temporary `PORTAGE_REPOSITORIES` definition. They do not
edit the synced repository or permanently register a development overlay.
Replace the checkout path if necessary.

```bash
cd /home/josh/src/gentoo/jkxyz-ebuilds
repos=$(printf '[DEFAULT]\nmain-repo = gentoo\n[gentoo]\nlocation = /var/db/repos/gentoo\n[jkxyz-ebuilds]\nlocation = %s\nmasters = gentoo\nauto-sync = no\n' "$PWD")
atom='=sys-kernel/wsl2-kernel-6.18.54.1::jkxyz-ebuilds'
```

Test the Windows helper with disposable dummy artifacts and a temporary
configuration first. This covers manual and automatic configuration, backups,
preservation of other settings, locks, retry, rollback, and failures. It does
not change your WSL boot configuration.

```bash
powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass \
  -File "$(wslpath -w "$PWD/tests/test_wsl_kernel_deploy.ps1")"
```

Inspect and install build dependencies through Portage. WSL supplies its own
initramfs, so the overlay masks the inherited `initramfs` flag for this package.
No manual USE override is needed. The inherited `installkernel` dependency is
retained, but its bootloader hooks are not run.

```bash
sudo env PORTAGE_REPOSITORIES="$repos" ACCEPT_KEYWORDS="~amd64" \
  emerge --ask --onlydeps "$atom"
```

Build and stage the package without merging it or copying anything to Windows:

```bash
sudo env PORTAGE_REPOSITORIES="$repos" ACCEPT_KEYWORDS="~amd64" \
  ebuild "$PWD/sys-kernel/wsl2-kernel/wsl2-kernel-6.18.54.1.ebuild" clean install
```

The resulting image is under Portage's build directory, normally
`/var/tmp/portage/sys-kernel/wsl2-kernel-6.18.54.1/image/usr/src/`.
Inspect its kernel and `modules.vhdx`. Then, when ready to test an installation:

```bash
sudo env PORTAGE_REPOSITORIES="$repos" ACCEPT_KEYWORDS="~amd64" \
  ebuild "$PWD/sys-kernel/wsl2-kernel/wsl2-kernel-6.18.54.1.ebuild" merge
```

`merge` uses the staged build and runs the optional Windows deployment.
Set `WSL_KERNEL_DIR` before this step if copying is desired, and optionally
`WSL_AUTO_UPDATE_CONFIG=true` to update `.wslconfig`. The custom kernel takes
effect after WSL restarts. Use `~arm64` on arm64.

### Retest the helper with an already installed kernel

The config phase uses the installed helper. To test a helper edit without
rebuilding the kernel, install the checkout's helper and rerun the local
config phase (using the `repos` definition above):

```bash
sudo install -m 0644 sys-kernel/wsl2-kernel/files/deploy.ps1 \
  /usr/share/wsl2-kernel/wsl2-kernel-6.18.54.1/deploy.ps1
sudo env PORTAGE_REPOSITORIES="$repos" ACCEPT_KEYWORDS="~amd64" \
  FEATURES=noauto \
  ebuild "$PWD/sys-kernel/wsl2-kernel/wsl2-kernel-6.18.54.1.ebuild" config
```

Set `WSL_AUTO_UPDATE_CONFIG=true` in `/etc/portage/make.conf` before this step
to test automatic configuration. Inspect the printed paths and backup before
restarting WSL from Windows. No new kernel build is needed to replace the
old junction-based selection.

After publishing and syncing the overlay, put
`sys-kernel/wsl2-kernel ~amd64` in `/etc/portage/package.accept_keywords/`.
Then use `emerge --ask sys-kernel/wsl2-kernel` normally. An existing
`-initramfs` entry in `/etc/portage/package.use/` may be removed; the overlay
already disables this unsupported feature.

## Automatic version updates

`latest_version.py` follows Microsoft's latest stable GitHub release and accepts
only tags in the `linux-msft-wsl-X.Y.Z.W` format. The existing update workflow
discovers the probe and opens version bump pull requests, including the source
Manifest. Drafts, prereleases, and unexpected tags are rejected.

## Provenance

Based on Phoenix591's GPL-2
[wsl2-kernel ebuild](https://github.com/Phoenix591/gentoo-overlay/tree/master/sys-kernel/wsl2-kernel).
The modules image uses Microsoft's `Microsoft/scripts/gen_artifacts_vhdx.sh`
from the same pinned kernel source release.
