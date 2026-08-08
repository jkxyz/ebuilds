# jkxyz/ebuilds

A [Gentoo](https://www.gentoo.org/) Portage overlay for packages maintained by [jkxyz](https://github.com/jkxyz). It provides the 1Password desktop application and command-line client for amd64 and arm64 systems.

## Installation

Install `app-eselect/eselect-repository` if it is not already available, then add and synchronize the overlay as root:

```bash
eselect repository add jkxyz-ebuilds git https://github.com/jkxyz/ebuilds.git
emaint sync -r jkxyz-ebuilds
```

1Password is proprietary software. Accept its license for the packages you intend to install in the `package.license` configuration (for example, `/etc/portage/package.license/1password-bin`):

```text
app-admin/1password-bin all-rights-reserved
app-admin/op-cli-bin all-rights-reserved
```

Install the desktop application with Portage:

```bash
emerge --ask app-admin/1password-bin
```

New upstream releases enter the overlay with testing keywords for both supported architectures. If the newest desktop version has not been stabilized yet, accept its keyword explicitly in `/etc/portage/package.accept_keywords/1password-bin`:

```text
app-admin/1password-bin ~amd64
```

Use `~arm64` instead on arm64. The CLI package is also testing-only until it has been tested and promoted for an architecture:

```text
app-admin/op-cli-bin ~amd64
```

The previous stable desktop ebuild remains available while either architecture still needs it, and amd64 and arm64 may be stabilized independently after testing.

## USE flags

- `cli` — install the overlay's `app-admin/op-cli-bin` command-line client.
- `policykit` — pull in `sys-auth/polkit` for polkit integration.

Both flags are disabled by default.

## Maintenance

The `latest-version.py` file in a package directory is the complete opt-in for release automation. It must print one stable Portage version, perform no workspace writes, and report failures on stderr. Packages without upstream releases, such as `acct-group/onepassword`, intentionally have no probe and are excluded from discovery.

The repository-wide bump program accepts only an atom and an explicit version; it does not contact upstream services or write GitHub workflow output files. The workflow composes the package matrix, package-local probe, and bump program at its shell boundary.

The scheduled and manual `Update packages` workflow discovers every opted-in package, runs one independent matrix job per atom, and opens one signed, non-draft pull request per outdated package. It uses the pinned Gentoo tools image from `ghcr.io/jkxyz/ebuilds-gentoo-tools` and limits each pull request to its package directory.

Build the same OCI-compatible tools image locally with rootless Podman:

```bash
podman build -f .github/gentoo-tools/Containerfile -t gentoo-tools .
```

Run the package-local release probes without changing the working tree:

```bash
app-admin/1password-bin/latest-version.py
app-admin/op-cli-bin/latest-version.py
```

Run a release bump and package QA from the repository root through the tools image:

```bash
podman run --rm -v "$PWD:/var/db/repos/jkxyz-ebuilds" -w /var/db/repos/jkxyz-ebuilds gentoo-tools scripts/bump_packages.py app-admin/1password-bin VERSION
podman run --rm -v "$PWD:/var/db/repos/jkxyz-ebuilds" -w /var/db/repos/jkxyz-ebuilds gentoo-tools scripts/bump_packages.py app-admin/op-cli-bin VERSION
podman run --rm -v "$PWD:/var/db/repos/jkxyz-ebuilds" -w /var/db/repos/jkxyz-ebuilds gentoo-tools pkgcheck scan --exit GentooCI,-NonsolvableDeps --cache-dir /tmp/pkgcheck app-admin/1password-bin
podman run --rm -v "$PWD:/var/db/repos/jkxyz-ebuilds" -w /var/db/repos/jkxyz-ebuilds gentoo-tools pkgcheck scan --exit GentooCI,-NonsolvableDeps --cache-dir /tmp/pkgcheck .
```

For manual stabilization, test the testing ebuild first, then run `ekeyword ARCH... PACKAGE-VERSION.ebuild`, regenerate its Manifest with `pkgdev manifest`, run `pkgcheck`, inspect the complete diff, and commit normally. When stable users are expected to enable `cli`, stabilize `app-admin/op-cli-bin` for an architecture before stabilizing `app-admin/1password-bin` on that architecture. Remove an older stable ebuild manually only after the replacement has stable keyword coverage for every architecture carried by the old version.

The initial full-overlay scan may use `GentooCI,-NonsolvableDeps`: stable `app-admin/1password-bin-8.12.28` can optionally depend on testing-only `app-admin/op-cli-bin`. The update workflow scans only the newly generated testing ebuild with the full `GentooCI` set.

## Provenance

The `app-admin/1password-bin` ebuild is based on [jaredallard/overlay](https://github.com/jaredallard/overlay). The CLI package follows [Gentoo's historical `op-cli-bin` ebuild](https://github.com/gentoo/gentoo/blob/master/app-admin/op-cli-bin/op-cli-bin-2.23.0.ebuild) and uses 1Password's official release artifacts. This is an unofficial community overlay and is not affiliated with or endorsed by 1Password or the Gentoo project.

## License

The overlay's own files are licensed under the [GNU General Public License v2.0](LICENSE). This does not change the upstream licenses of packaged software; 1Password remains proprietary software.
