# jkxyz/ebuilds

A [Gentoo](https://www.gentoo.org/) Portage overlay for packages maintained by [jkxyz](https://github.com/jkxyz). It currently provides the 1Password desktop application for amd64 and arm64 systems.

## Installation

Install `app-eselect/eselect-repository` if it is not already available, then add and synchronize the overlay as root:

```bash
eselect repository add jkxyz-ebuilds git https://github.com/jkxyz/ebuilds.git
emaint sync -r jkxyz-ebuilds
```

1Password is proprietary software. Accept its license for this package in the `package.license` configuration (for example, `/etc/portage/package.license/1password`):

```text
app-admin/1password all-rights-reserved
```

Install the application with Portage:

```bash
emerge --ask app-admin/1password
```

New upstream releases enter the overlay with testing keywords for both supported architectures. If the newest version has not been stabilized yet, accept its keyword explicitly in `/etc/portage/package.accept_keywords/1password`:

```text
app-admin/1password ~amd64
```

Use `~arm64` instead on arm64. The previous stable ebuild remains available while either architecture still needs it, and amd64 and arm64 may be stabilized independently after testing.

## USE flags

- `cli` — install Gentoo's `app-admin/op-cli-bin` command-line client.
- `policykit` — pull in `sys-auth/polkit` for polkit integration.

Both flags are disabled by default.

## Maintenance

A dedicated GitHub Actions workflow publishes the pinned Gentoo tools image to `ghcr.io/jkxyz/ebuilds-gentoo-tools` whenever its Containerfile changes. The update and stabilization jobs declare that package as their job container, so the release check and every package-changing or QA command run inside the same controlled Python and Gentoo environment.

A scheduled workflow checks 1Password's official stable APT repository every day. When a release is newer than every ebuild in the overlay, it uses `pkgbump` to create a `~amd64 ~arm64` ebuild, regenerates the Manifest with `pkgdev`, runs `pkgcheck`, and opens a signed pull request. Stabilization is a separate manual workflow so promotion happens only after real package testing.

Build the same OCI-compatible tools image locally with rootless Podman:

```bash
podman build -f .github/gentoo-tools/Containerfile -t gentoo-tools .
```

Run the release check through the tools image:

```bash
podman run --rm -v "$PWD:/var/db/repos/jkxyz-ebuilds:ro" -w /var/db/repos/jkxyz-ebuilds gentoo-tools python app-admin/1password/update.py check
```

Run version bumps, stabilization, and QA from the repository root through the tools image:

```bash
podman run --rm -v "$PWD:/var/db/repos/jkxyz-ebuilds" -w /var/db/repos/jkxyz-ebuilds gentoo-tools python app-admin/1password/update.py bump VERSION
podman run --rm -v "$PWD:/var/db/repos/jkxyz-ebuilds" -w /var/db/repos/jkxyz-ebuilds gentoo-tools python app-admin/1password/stabilize.py VERSION --arch amd64 --arch arm64
podman run --rm -v "$PWD:/var/db/repos/jkxyz-ebuilds" -w /var/db/repos/jkxyz-ebuilds gentoo-tools pkgcheck scan --exit GentooCI,-NonsolvableDeps --cache-dir /tmp/pkgcheck app-admin/1password
```

Omit either stabilization `--arch` argument when promoting only one architecture. The stabilization script regenerates the Manifest and removes an older stable ebuild only after the selected version fully supersedes its stable architecture coverage.

The QA gate uses pkgcheck's Gentoo CI failure set except for `NonsolvableDeps`: the optional `cli` flag intentionally depends on Gentoo's testing-only `app-admin/op-cli-bin`, so stable users who enable that flag must also accept the CLI package's testing keyword.

## Provenance

The `app-admin/1password` ebuild is based on [jaredallard/overlay](https://github.com/jaredallard/overlay/tree/main/app-admin/1password). This is an unofficial community overlay and is not affiliated with or endorsed by 1Password or the Gentoo project.

## License

The overlay's own files are licensed under the [GNU General Public License version 2.0](LICENSE). This does not change the upstream licenses of packaged software; 1Password remains proprietary software.
