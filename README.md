# jkxyz/ebuilds

A [Gentoo](https://www.gentoo.org/) Portage overlay for packages maintained by [jkxyz](https://github.com/jkxyz). It provides the ChatGPT, Nextcloud, and 1Password desktop clients, the Helium browser, and the 1Password command-line client for amd64 and arm64 systems.

## Installation

Install `app-eselect/eselect-repository` if it is not already available, then add and synchronize the overlay as root:

```bash
eselect repository add jkxyz-ebuilds git https://github.com/jkxyz/ebuilds.git
emaint sync -r jkxyz-ebuilds
```

1Password and ChatGPT are proprietary software. Accept their licenses for the packages you intend to install in the `package.license` configuration (for example, `/etc/portage/package.license/proprietary-apps`):

```text
app-admin/1password-bin all-rights-reserved
app-admin/op-cli-bin all-rights-reserved
app-misc/chatgpt-bin all-rights-reserved
```

Install the desktop application with Portage:

```bash
emerge --ask app-admin/1password-bin
```

Install the Nextcloud desktop client with Portage:

```bash
emerge --ask net-misc/nextcloud-client
```

ChatGPT for Linux is testing-only on both supported architectures. Accept `~amd64` or `~arm64` for `app-misc/chatgpt-bin`, then install it with Portage:

```bash
emerge --ask app-misc/chatgpt-bin
```

Helium is testing-only on both supported architectures. Accept `~amd64` or `~arm64` for `www-client/helium-bin`, then install it with Portage:

```bash
emerge --ask www-client/helium-bin
```

New upstream releases enter the overlay with testing keywords for both supported architectures. If the newest desktop version has not been stabilized yet, accept its keyword explicitly in `/etc/portage/package.accept_keywords/1password-bin`:

```text
app-admin/1password-bin ~amd64
```

Use `~arm64` instead on arm64. The CLI package is also testing-only until it has been tested and promoted for an architecture:

```text
app-admin/op-cli-bin ~amd64
```

The Nextcloud desktop client is testing-only on both supported architectures. Accept `~amd64` or `~arm64` for `net-misc/nextcloud-client` before installing it.

The previous stable desktop ebuild remains available while either architecture still needs it, and amd64 and arm64 may be stabilized independently after testing.

## USE flags

- `cli` — install the overlay's `app-admin/op-cli-bin` command-line client.
- `policykit` — pull in `sys-auth/polkit` for polkit integration.
- `dolphin` — install the Nextcloud Dolphin extension.
- `nautilus` — install the Nextcloud Nautilus extension.
- `webengine` — enable Nextcloud's legacy Flow1 login.
- `qt6` — enable Helium's bundled Qt 6 theme integration shim.

The overlay does not set defaults for these flags.

## Maintenance

The `Update packages` workflow checks tracked packages daily and opens a pull request when it finds a new stable release. An executable `CATEGORY/PACKAGE/latest_version.py` probe opts a package into these checks and prints its latest stable Portage version. Discovery and version comparison run directly on the Ubuntu runner; the Gentoo tools container starts only for packages that actually need an update.

Run the probes directly to check upstream versions:

```bash
app-admin/1password-bin/latest_version.py
app-admin/op-cli-bin/latest_version.py
app-misc/chatgpt-bin/latest_version.py
net-misc/nextcloud-client/latest_version.py
www-client/helium-bin/latest_version.py
```

For a manual bump, provide the atom and version from the repository root:

```bash
scripts/bump_packages.py app-admin/1password-bin VERSION
scripts/bump_packages.py app-admin/op-cli-bin VERSION
scripts/bump_packages.py app-misc/chatgpt-bin VERSION
scripts/bump_packages.py net-misc/nextcloud-client VERSION
scripts/bump_packages.py www-client/helium-bin VERSION
```

Regenerate the affected Manifest, run package QA, and inspect the complete diff before committing:

```bash
pkgdev manifest app-admin/1password-bin
pkgcheck scan --exit GentooCI --cache-dir /tmp/pkgcheck app-admin/1password-bin
pkgdev manifest app-misc/chatgpt-bin
pkgcheck scan --exit GentooCI --cache-dir /tmp/pkgcheck app-misc/chatgpt-bin
pkgdev manifest net-misc/nextcloud-client
pkgcheck scan --exit GentooCI --cache-dir /tmp/pkgcheck net-misc/nextcloud-client
pkgdev manifest www-client/helium-bin
pkgcheck scan --exit GentooCI --cache-dir /tmp/pkgcheck www-client/helium-bin
```

The tools used by CI are defined in `.github/gentoo-tools/Containerfile` if a matching local environment is needed.

### Stabilizing a release

Stabilize each architecture independently only after testing the testing-keyworded ebuild on that architecture.

1. Install and test the target `~amd64` or `~arm64` ebuild. Test the relevant USE flag combinations as well.
2. Before stabilizing `app-admin/1password-bin`, ensure `app-admin/op-cli-bin` already has a tested stable version for the same architecture. Stabilize the CLI first when necessary so the desktop package's `cli` dependency remains solvable.
3. Replace the testing keyword with the stable keyword using `ekeyword`. For example, to stabilize amd64:

```bash
ekeyword amd64 app-admin/op-cli-bin/op-cli-bin-VERSION.ebuild
ekeyword amd64 app-admin/1password-bin/1password-bin-VERSION.ebuild
```

Use `arm64` instead when stabilizing arm64, and omit the CLI command when a suitable CLI version is already stable for that architecture.

4. Regenerate the Manifests and run QA on both packages:

```bash
pkgdev manifest app-admin/op-cli-bin app-admin/1password-bin
pkgcheck scan --exit GentooCI --cache-dir /tmp/pkgcheck app-admin/op-cli-bin app-admin/1password-bin
```

5. Inspect the diff and commit the stabilization. Keep the older stable ebuild until the replacement is stable on every architecture keyworded by the old version; after removing it, regenerate the Manifest and run QA again.

## Provenance

The `net-misc/nextcloud-client` ebuild is based on [Gentoo's official 33.0.5 ebuild](https://gitweb.gentoo.org/repo/gentoo.git/tree/net-misc/nextcloud-client/nextcloud-client-33.0.5.ebuild). The `app-admin/1password-bin` ebuild is based on [jaredallard/overlay](https://github.com/jaredallard/overlay). The CLI package follows [Gentoo's historical `op-cli-bin` ebuild](https://github.com/gentoo/gentoo/blob/master/app-admin/op-cli-bin/op-cli-bin-2.23.0.ebuild) and uses 1Password's official release artifacts. ChatGPT and Helium use their upstream architecture-specific Linux packages. This is an unofficial community overlay and is not affiliated with or endorsed by OpenAI, Helium, Nextcloud, 1Password, or the Gentoo project.

## License

The overlay's own files are licensed under the [GNU General Public License v2.0](LICENSE). This does not change the upstream licenses of packaged software; ChatGPT and 1Password remain proprietary software.
