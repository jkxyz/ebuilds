# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

NEED_EMACS=28.1
ZIG_SLOT=0.16
ZIG_NEEDS_LLVM=1

# Pin the complete build dependency set for offline compilation.
declare -A ZBS_DEPENDENCIES=(
	[arocc-f97cdfc3779aec4b242299e2fc9a1c828c3547c6.tar.gz]="https://github.com/vancluever/arocc/archive/f97cdfc3779aec4b242299e2fc9a1c828c3547c6.tar.gz"
	[ghostty-a2e440396403385680008e456a741a7776091412.tar.gz]="https://github.com/ghostty-org/ghostty/archive/a2e440396403385680008e456a741a7776091412.tar.gz"
	[ghostty-themes-release-20261005-151109-31756e7.tgz]="https://deps.files.ghostty.org/ghostty-themes-release-20261005-151109-31756e7.tgz"
	[highway-66486a10623fa0d72fe91260f96c892e41aceb06.tar.gz]="https://deps.files.ghostty.org/highway-66486a10623fa0d72fe91260f96c892e41aceb06.tar.gz"
	[pixels-12207ff340169c7d40c570b4b6a97db614fe47e0d83b5801a932dcd44917424c8806.tar.gz]="https://deps.files.ghostty.org/pixels-12207ff340169c7d40c570b4b6a97db614fe47e0d83b5801a932dcd44917424c8806.tar.gz"
	[translate-c-4e879eb8aba615de112eabd1231ea6e01920cead.tar.gz]="https://codeberg.org/vancluever/translate-c/archive/4e879eb8aba615de112eabd1231ea6e01920cead.tar.gz"
	[uucode-9d55524551411b493cca41ca06363625d90aff1e.tar.gz]="https://github.com/jacobsandlund/uucode/archive/9d55524551411b493cca41ca06363625d90aff1e.tar.gz"
	[wuffs-7411f488fe2e2c205c3d3b3d28638b7356522930.tar.gz]="https://deps.files.ghostty.org/wuffs-7411f488fe2e2c205c3d3b3d28638b7356522930.tar.gz"
	[zlib-1220fed0c74e1019b3ee29edae2051788b080cd96e90d56836eea857b0b966742efb.tar.gz]="https://deps.files.ghostty.org/zlib-1220fed0c74e1019b3ee29edae2051788b080cd96e90d56836eea857b0b966742efb.tar.gz"
)

inherit elisp zig

DESCRIPTION="Emacs terminal emulator powered by libghostty"
HOMEPAGE="https://github.com/dakra/ghostel/"
SRC_URI="https://github.com/dakra/ghostel/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz
	${ZBS_DEPENDENCIES_SRC_URI}"

LICENSE="GPL-3+ MIT Apache-2.0 BSD ZLIB Unicode-3.0 CC0-1.0"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
IUSE="test"
RESTRICT="!test? ( test )"

RDEPEND="
	>=app-editors/emacs-${NEED_EMACS}:*[dynamic-loading]
	>=app-emacs/compat-30.1.0.1
"
BDEPEND="${RDEPEND}"

DOCS=( README.md CHANGELOG.md )
SITEFILE="50${PN}-gentoo.el"

pkg_setup() {
	elisp_pkg_setup
	zig_pkg_setup
	[[ ${ZIG_VER} == 0.16.0 ]] || die "Ghostel ${PV} requires exactly Zig 0.16.0"
}

src_prepare() {
	zig_src_prepare
	# Zig 0.16 loops on Ghostty's nested path dependencies in --system mode.
	# A local fork keeps those paths working while all downloads stay disabled.
	cp -a "${WORKDIR}/zig-pkg"/ghostty-* "${WORKDIR}/ghostty" || die
}

src_configure() {
	local my_zbs_args=(
		# Match upstream; ReleaseSafe translation fails on fortified glibc headers.
		--release=fast
		--prefix "${EPREFIX}/usr/$(get_libdir)/emacs/modules/${PN}"
		--fork=../ghostty
	)
	zig_src_configure
}

src_compile() {
	zig_src_compile
	cd lisp || die
	BYTECOMPFLAGS+=" -L ${BROOT}${SITELISP}/compat"
	elisp-compile *.el
	elisp-make-autoload-file "${PN}-autoloads.el" .
}

src_install() {
	zig_src_install
	elisp-install ${PN} lisp/*.el lisp/*.elc
	insinto "${SITEETC}/${PN}"
	doins -r etc
	# Ghostel locates resources relative to its Lisp directory.
	dosym -r "${SITEETC}/${PN}/etc" "${SITELISP}/${PN}/etc"
	sed "s/@VERSION@/${PV//./ }/g" "${FILESDIR}/${SITEFILE}" > "${T}/${SITEFILE}" || die
	elisp-site-file-install "${T}/${SITEFILE}"
}
