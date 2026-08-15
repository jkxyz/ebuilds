# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

PYTHON_COMPAT=( python3_{11..15} )

inherit python-r1 shell-completion

DESCRIPTION="Command-line interface for the Dropbox desktop client"
HOMEPAGE="https://github.com/dropbox/nautilus-dropbox"
SRC_URI="https://linux.dropboxstatic.com/packages/nautilus-dropbox-${PV}.tar.bz2"
S="${WORKDIR}/nautilus-dropbox-${PV}"

LICENSE="GPL-3"
SLOT="0"
KEYWORDS="~amd64"
REQUIRED_USE="${PYTHON_REQUIRED_USE}"

RDEPEND="
	${PYTHON_DEPS}
	>=net-misc/dropbox-264.4.3421
"
BDEPEND="${PYTHON_DEPS}"

src_prepare() {
	default

	# Always control the Portage-owned daemon. In particular, do not let
	# `dropbox start -i` install a second copy under ~/.dropbox-dist.
	sed -i \
		-e "s|^DROPBOX_DIST_PATH = .*|DROPBOX_DIST_PATH = \"${EPREFIX}/opt/dropbox\"|" \
		-e "s|^DROPBOXD_PATH = .*|DROPBOXD_PATH = \"${EPREFIX}/opt/dropbox/dropboxd\"|" \
		-e 's/^    should_install = .*/    should_install = False/' \
		-e 's/Run \\"dropbox start -i\\" to install the daemon/Install net-misc\/dropbox to provide the daemon/' \
		dropbox.in || die
}

build_cli() {
	"${EPYTHON}" build_dropbox.py "${PV}" \
		"${EPREFIX}/usr/share/applications" \
		< dropbox.in > dropbox || die
}

src_configure() {
	:
}

src_compile() {
	python_foreach_impl build_cli
}

src_install() {
	newbin dropbox ${PN}
	python_replicate_script "${ED}/usr/bin/${PN}"

	# Keep Gentoo's unambiguous name while also supporting Dropbox's documented
	# `dropbox COMMAND` spelling. /usr/bin takes precedence over /opt/bin.
	dosym ${PN} /usr/bin/dropbox
	newbashcomp "${FILESDIR}"/${PN}-completion ${PN}
	newbashcomp "${FILESDIR}"/${PN}-completion dropbox
}
