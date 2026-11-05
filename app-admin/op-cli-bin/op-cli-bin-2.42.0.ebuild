# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="Official 1Password command-line client"
HOMEPAGE="https://developer.1password.com/docs/cli/"
SRC_URI="
	amd64? ( https://cache.agilebits.com/dist/1P/op2/pkg/v${PV}/op_linux_amd64_v${PV}.zip -> ${P}-amd64.zip )
	arm64? ( https://cache.agilebits.com/dist/1P/op2/pkg/v${PV}/op_linux_arm64_v${PV}.zip -> ${P}-arm64.zip )"
S="${WORKDIR}"

LICENSE="all-rights-reserved"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
BDEPEND="app-arch/unzip"

RESTRICT="bindist mirror"
QA_PREBUILT="usr/bin/op"

src_install() {
	dobin op
}
