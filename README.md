# jkxyz/ebuilds

A small [Gentoo](https://www.gentoo.org/) Portage overlay maintained by [jkxyz](https://github.com/jkxyz). It packages the 1Password, ChatGPT, and Nextcloud desktop clients, the 1Password CLI, and the Helium browser for amd64 and arm64.

## Packages

Versions marked `~amd64` or `~arm64` use Gentoo testing keywords; versions marked `amd64` or `arm64` are stable. The overlay does not enable any USE flags by default.

| Package | Purpose | Available versions | USE flags |
| --- | --- | --- | --- |
| `app-admin/1password-bin` | 1Password desktop client | `8.12.28` (`amd64`, `arm64`)<br>`8.12.32` (`~amd64`, `~arm64`) | `cli` — install `app-admin/op-cli-bin`<br>`policykit` — pull in `sys-auth/polkit` for desktop authentication |
| `app-admin/op-cli-bin` | 1Password command-line client | `2.38.1` (`~amd64`, `~arm64`) | None |
| `app-misc/chatgpt-bin` | ChatGPT desktop application | `26.803.81509-r1` (`~amd64`, `~arm64`) | None |
| `net-misc/nextcloud-client` | Nextcloud desktop sync client | `34.0.1` (`~amd64`, `~arm64`) | `dolphin` — build the Dolphin extension<br>`nautilus` — build the Nautilus extension<br>`test` — build and run the test suite<br>`webengine` — enable the legacy Flow1 login |
| `www-client/helium-bin` | Chromium-based Helium browser | `0.15.4.1` (`~amd64`, `~arm64`) | `qt6` — enable the bundled Qt 6 theme integration shim<br>`selinux` — install the Chromium SELinux policy |
| `acct-group/onepassword` | System group required by the 1Password desktop client | `0` (installed automatically) | None |

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

Use `~arm64` on arm64. Then install any package from the table with Portage, for example:

```bash
emerge --ask app-misc/chatgpt-bin
```

1Password and ChatGPT are proprietary. Accept their licenses only for the packages you intend to install, for example in `/etc/portage/package.license/proprietary-apps`:

```text
app-admin/1password-bin all-rights-reserved
app-admin/op-cli-bin all-rights-reserved
app-misc/chatgpt-bin all-rights-reserved
```

## Maintenance

The `Update packages` workflow checks tracked packages daily and opens a pull request when it finds a new stable upstream release. A package opts into these checks by providing an executable `CATEGORY/PACKAGE/latest_version.py` probe that prints the latest stable Portage version. Discovery and version comparison run directly on the Ubuntu runner; the Gentoo tools container starts only when an ebuild needs an update.

For a manual update, run the package's probe, bump the ebuild, regenerate its Manifest, run the Gentoo CI checks, and inspect the complete diff:

```bash
CATEGORY/PACKAGE/latest_version.py
scripts/bump_packages.py CATEGORY/PACKAGE VERSION
pkgdev manifest CATEGORY/PACKAGE
pkgcheck scan --exit GentooCI --cache-dir /tmp/pkgcheck CATEGORY/PACKAGE
git diff --check
git diff
```

`scripts/bump_packages.py` creates a testing-keyworded ebuild from the newest existing version. The tools used by CI are defined in `.github/gentoo-tools/Containerfile` when a matching local environment is needed.

When adding, bumping, stabilizing, or removing an ebuild, update the package table above if its versions, keywords, or USE flags changed.

### Stabilizing a release

Stabilize an architecture only after installing and testing the testing-keyworded ebuild on that architecture, including the relevant USE-flag combinations. Replace the testing keyword with a stable keyword, regenerate the Manifest, rerun QA, and inspect the diff:

```bash
ekeyword amd64 CATEGORY/PACKAGE/PACKAGE-VERSION.ebuild
pkgdev manifest CATEGORY/PACKAGE
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

This is an unofficial community overlay and is not affiliated with or endorsed by OpenAI, Helium, Nextcloud, 1Password, or the Gentoo project.

## License

The overlay's own files are licensed under the [GNU General Public License v2.0](LICENSE). This does not change the upstream licenses of packaged software; ChatGPT and 1Password remain proprietary software.
