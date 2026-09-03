# jkxyz/ebuilds

A small [Gentoo](https://www.gentoo.org/) Portage overlay maintained by [jkxyz](https://github.com/jkxyz). It packages the 1Password, ChatGPT, Dropbox, and Nextcloud desktop clients, their related command-line or desktop integrations, and the Helium browser.

## Packages

Versions marked `~amd64` or `~arm64` use Gentoo testing keywords; versions marked `amd64` or `arm64` are stable. The overlay does not enable any USE flags by default.

The catalogue below is generated from the ebuilds and their `metadata.xml` files by `scripts/update_readme.py`.

<!-- BEGIN GENERATED PACKAGE CATALOGUE -->

### `acct-group/onepassword`

Group for the 1Password password manager

**Versions:** `0`

**USE flags:** none

### `app-admin/1password-bin`

The official 1Password desktop password manager for Linux.

**Versions:** `8.12.28` (`amd64`, `arm64`); `8.12.34` (`~amd64`, `~arm64`)

**USE flags**

- `cli` — Install the 1Password command-line client via app-admin/op-cli-bin
- `policykit` — Install polkit integration for desktop authentication.

### `app-admin/op-cli-bin`

The official 1Password command-line client for Linux.

**Versions:** `2.39.0` (`~amd64`, `~arm64`)

**USE flags:** none

### `app-misc/chatgpt-bin`

ChatGPT is OpenAI's desktop application for Chat, Work, and Codex. It can work with local projects, files, and development tools.

**Versions:** `26.831.21537` (`~amd64`, `~arm64`)

**USE flags:** none

### `kde-apps/dolphin-plugins-dropbox`

The Dropbox version-control plugin from KDE's Dolphin Plugins release. It adds Dropbox file status overlays and context actions to Dolphin.

**Versions:** `26.08.0` (`~amd64`)

**USE flags:** none

### `net-misc/dropbox`

The official proprietary Dropbox desktop client for synchronizing files with the Dropbox service. Dropbox supports Linux on amd64 only.

**Versions:** `268.4.4124` (`~amd64`)

**USE flags**

- `selinux` — Install the corresponding SELinux policy.
- `X` — Install desktop icons and AppIndicator integration.

### `net-misc/dropbox-cli`

The GPL-licensed command-line frontend from nautilus-dropbox, configured to control the system copy installed by net-misc/dropbox.

**Versions:** `2026.05.06` (`~amd64`)

**USE flags:** none

### `net-misc/nextcloud-client`

Desktop Syncing Client for Nextcloud

**Versions:** `34.0.3` (`~amd64`, `~arm64`)

**USE flags**

- `dolphin` — Install the kde-apps/dolphin extension
- `nautilus` — Install the gnome-base/nautilus extension
- `test` — Build and run the upstream test suite.
- `webengine` — Enable old Flow1 login using dev-qt/qtwebengine

### `www-client/helium-bin`

Helium is a privacy-focused Chromium-based web browser with integrated content blocking and a minimal user interface.

**Versions:** `0.16.3.1` (`~amd64`, `~arm64`)

**USE flags**

- `qt6` — Enable the bundled Qt 6 theme integration shim.
- `selinux` — Install the corresponding SELinux policy.

<!-- END GENERATED PACKAGE CATALOGUE -->

## Installation

Install `app-eselect/eselect-repository` if necessary, then add and synchronize the overlay as root:

```bash
eselect repository add jkxyz-ebuilds git https://github.com/jkxyz/ebuilds.git
emaint sync -r jkxyz-ebuilds
```

For a testing-keyworded package, accept the keyword that matches the system architecture in a file under `/etc/portage/package.accept_keywords/`:

```text
app-misc/chatgpt-bin ~amd64
```

Use `~arm64` on arm64. Then install any package from the catalogue with Portage, for example:

```bash
emerge --ask app-misc/chatgpt-bin
```

1Password and ChatGPT are proprietary. Accept their licenses only for the packages you intend to install, for example in `/etc/portage/package.license/proprietary-apps`:

```text
app-admin/1password-bin all-rights-reserved
app-admin/op-cli-bin all-rights-reserved
app-misc/chatgpt-bin all-rights-reserved
net-misc/dropbox dropbox
```

Install `kde-apps/dolphin-plugins-dropbox` to pull in the Dropbox client and CLI together with Dolphin integration. The CLI is available as both `dropbox-cli` and the upstream-compatible `dropbox` command.

## Maintenance

The `Update packages` workflow checks tracked packages daily and opens a pull request when it finds a new stable upstream release. A package opts into these checks by providing an executable `CATEGORY/PACKAGE/latest_version.py` probe that prints the latest stable Portage version. Discovery and version comparison run directly on the Ubuntu runner; the Gentoo tools container starts only when an ebuild needs an update.

For a manual update, run the package's probe, bump the ebuild, regenerate its Manifest, run the Gentoo CI checks, and inspect the complete diff:

```bash
CATEGORY/PACKAGE/latest_version.py
scripts/bump_packages.py CATEGORY/PACKAGE VERSION
pkgdev manifest CATEGORY/PACKAGE
scripts/update_readme.py
pkgcheck scan --exit GentooCI --cache-dir /tmp/pkgcheck CATEGORY/PACKAGE
git diff --check
git diff
```

`scripts/bump_packages.py` creates a testing-keyworded ebuild from the newest existing version. The tools used by CI are defined in `tools/Containerfile` when a matching local environment is needed.

When adding, bumping, stabilizing, or removing an ebuild, regenerate the package catalogue. The automated update workflow does this after every successful package bump.

### Stabilizing a release

Stabilize an architecture only after installing and testing the testing-keyworded ebuild on that architecture, including the relevant USE-flag combinations. Replace the testing keyword with a stable keyword, regenerate the Manifest, rerun QA, and inspect the diff:

```bash
ekeyword amd64 CATEGORY/PACKAGE/PACKAGE-VERSION.ebuild
pkgdev manifest CATEGORY/PACKAGE
scripts/update_readme.py
pkgcheck scan --exit GentooCI --cache-dir /tmp/pkgcheck CATEGORY/PACKAGE
git diff --check
git diff
```

Use `arm64` when stabilizing arm64. For `app-admin/1password-bin`, first ensure that `app-admin/op-cli-bin` has a tested stable version on the same architecture so the desktop package remains installable with `USE=cli`; stabilize the CLI first when necessary.

Keep an older stable ebuild until its replacement is stable on every architecture keyworded by the old version. After removing the old ebuild, regenerate the Manifest and run QA again.

## Provenance

- `net-misc/nextcloud-client` is based on [Gentoo's official 33.0.5 ebuild](https://gitweb.gentoo.org/repo/gentoo.git/tree/net-misc/nextcloud-client/nextcloud-client-33.0.5.ebuild).
- `app-admin/1password-bin` is based on [jaredallard/overlay](https://github.com/jaredallard/overlay).
- `app-admin/op-cli-bin` follows [Gentoo's historical ebuild](https://github.com/gentoo/gentoo/blob/master/app-admin/op-cli-bin/op-cli-bin-2.23.0.ebuild) and uses 1Password's official release artifacts.
- `app-misc/chatgpt-bin` and `www-client/helium-bin` use their upstream architecture-specific Linux packages.
- `net-misc/dropbox` follows Gentoo's official binary-daemon packaging while using Dropbox's stable Linux download redirect for update discovery. `net-misc/dropbox-cli` is generated from Dropbox's versioned nautilus-dropbox source release, and `kde-apps/dolphin-plugins-dropbox` follows Gentoo's split KDE Gear package.

This is an unofficial community overlay and is not affiliated with or endorsed by OpenAI, Dropbox, Helium, Nextcloud, 1Password, KDE, or the Gentoo project.

## License

The overlay's own files are licensed under the [GNU General Public License v2.0](LICENSE). This does not change the upstream licenses of packaged software; ChatGPT, Dropbox, and 1Password remain proprietary software.
