# jkxyz/ebuilds

A [Gentoo](https://www.gentoo.org/) Portage overlay for packages maintained by
[jkxyz](https://github.com/jkxyz). It currently provides the 1Password desktop
application for amd64 and arm64 systems.

## Installation

Install `app-eselect/eselect-repository` if it is not already available, then
add and synchronize the overlay as root:

```bash
eselect repository add jkxyz-ebuilds git https://github.com/jkxyz/ebuilds.git
emaint sync -r jkxyz-ebuilds
```

1Password is proprietary software. Accept its license for this package in the
`package.license` configuration (for example,
`/etc/portage/package.license/1password`):

```text
app-admin/1password all-rights-reserved
```

Install the application with Portage:

```bash
emerge --ask app-admin/1password
```

## USE flags

- `cli` — install Gentoo's `app-admin/op-cli-bin` command-line client.
- `policykit` — pull in `sys-auth/polkit` for polkit integration.

Both flags are disabled by default.

## Updates

A scheduled GitHub Actions workflow checks 1Password's official stable APT
repository every day. For each new release, it downloads the official amd64 and
arm64 tarballs, regenerates the Manifest hashes, and opens a version-bump pull
request.

## Provenance

The `app-admin/1password` ebuild is based on
[jaredallard/overlay](https://github.com/jaredallard/overlay/tree/main/app-admin/1password).
This is an unofficial community overlay and is not affiliated with or endorsed
by 1Password or the Gentoo project.

## License

The overlay's own files are licensed under the [GNU General Public License version 2.0](LICENSE). This does not change the upstream licenses of packaged software; 1Password remains proprietary software.
