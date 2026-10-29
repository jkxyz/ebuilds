# Ghostel

The ebuild builds Ghostel and its native module from the same release. Emacs
must have `USE=dynamic-loading` enabled. Accept `~amd64` (or `~arm64`) for
`app-emacs/ghostel`, then install it with:

```sh
PORTAGE_SCHEDULING_POLICY=idle emerge --ask app-emacs/ghostel
```

## Choosing the compiler

Gentoo's Zig eclass accepts either `dev-lang/zig:0.16[llvm]` or
`dev-lang/zig-bin:0.16`. Ghostel 0.59.0 requires exactly Zig 0.16.0.
Source Zig uses LLVM, Clang, and LLD slot 21. The binary compiler includes
its toolchain; Ghostel is still compiled from source with either provider.

Portage normally reuses an installed provider. To choose the binary compiler
before installing Ghostel:

```sh
PORTAGE_SCHEDULING_POLICY=idle emerge --ask --oneshot dev-lang/zig-bin:0.16
PORTAGE_SCHEDULING_POLICY=idle emerge --ask app-emacs/ghostel
```

For source Zig, accept its testing keyword and install
`dev-lang/zig:0.16[llvm]` instead. A mask on the unwanted provider can enforce
a dependency policy. When both providers are installed, the Zig eclass prefers
source Zig regardless of `eselect zig`; `ZIG_EXE` in a package environment can
override that choice.

## Emacs configuration

Gentoo's site initialization adds Ghostel to `load-path`, selects the system
module directory, and advertises its version to `package.el` as a built-in
package. Existing `use-package` declarations, including `:ensure t` and MELPA's
`evil-ghostel`, can use it. Normal package upgrades leave built-ins alone.

After emerging Ghostel, remove its previous MELPA installation and restart
Emacs (including any daemon). Keep `evil-ghostel` installed through MELPA.
An existing user installation of Ghostel can otherwise shadow the system copy.
If a future extension requires a newer Ghostel, update the system package
before updating that extension.

Check the installation with `M-: (locate-library "ghostel")` and
`M-: (package-installed-p 'ghostel '(0 59 0))`.

## Updating

The daily update workflow checks stable Ghostel releases. The package's
`update.py` hook resolves upstream's pinned dependencies for amd64 and arm64 with glibc and musl,
refreshes `ZBS_DEPENDENCIES`, and lets the shared bump helper regenerate the
Manifest. Zig verifies upstream's package hashes; Portage records separate
archive checksums. The hook configures the build without compiling the module.

Manual bumps through `scripts/bump_packages.py app-emacs/ghostel VERSION` run
the same hook. The tools container supplies Zig 0.16.0; locally, install that
version of either compiler or set `ZIG_EXE` to its executable. To regenerate
an existing ebuild, run:

```sh
app-emacs/ghostel/update.py app-emacs/ghostel/ghostel-0.59.0.ebuild
pkgdev manifest app-emacs/ghostel
```

If upstream changes its required Zig version, the hook stops for review of
the compiler dependency, build options, and tools image. Regenerated updates
still need a build with `USE=test` before merging. Compilation uses Zig's
offline `--system` mode; a local Ghostty fork works around Zig 0.16's handling
of nested path dependencies in that mode.
