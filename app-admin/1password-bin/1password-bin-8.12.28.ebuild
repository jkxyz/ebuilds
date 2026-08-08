# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2
# shellcheck shell=bash

EAPI=8

inherit desktop xdg

MY_PN="${PN%-bin}"

DESCRIPTION="Password Manager"
HOMEPAGE="https://1password.com"
SRC_URI="
	amd64? ( https://downloads.1password.com/linux/tar/stable/x86_64/${MY_PN}-${PV}.x64.tar.gz -> ${P}-amd64.tar.gz )
	arm64? ( https://downloads.1password.com/linux/tar/stable/aarch64/${MY_PN}-${PV}.arm64.tar.gz -> ${P}-arm64.tar.gz )"
S="${WORKDIR}"

LICENSE="all-rights-reserved"
SLOT="0"
KEYWORDS="amd64 arm64"
IUSE="cli policykit"
RDEPEND="
	acct-group/onepassword
	x11-misc/xdg-utils
	cli? ( app-admin/op-cli-bin )
	policykit? ( sys-auth/polkit )
"

RESTRICT="bindist mirror strip"

QA_PREBUILT="usr/bin/${MY_PN}"

src_prepare() {
	default
	xdg_environment_reset
}

src_install() {
	local archive_arch
	case ${ARCH} in
		amd64) archive_arch=x64 ;;
		arm64) archive_arch=arm64 ;;
		*) die "Unsupported architecture: ${ARCH}" ;;
	esac

	mkdir -p "${D}/opt/1Password/"
	cp -ar "${S}/${MY_PN}-${PV}.${archive_arch}/." "${D}/opt/1Password/" || die "Install failed!"

	# Fill in policy kit file with a list of (the first 10) human users of
	# the system.
	export POLICY_OWNERS
	POLICY_OWNERS="$(
		cut -d: -f1,3 /etc/passwd |
			grep -E ':[0-9]{4}$' |
			cut -d: -f1 |
			head -n 10 |
			sed 's/^/unix-user:/' |
			tr '\n' ' '
	)"

	mkdir -p "${D}/usr/share/polkit-1/actions/"
	eval "cat <<EOF
$(cat "${D}/opt/1Password/com.1password.1Password.policy.tpl")
EOF" >"${D}/usr/share/polkit-1/actions/com.1password.1Password.policy"
	chmod 644 "${D}/usr/share/polkit-1/actions/com.1password.1Password.policy"

	dosym -r /opt/1Password/${MY_PN} /usr/bin/${MY_PN}
	dosym -r /opt/1Password/op-ssh-sign /usr/bin/op-ssh-sign

	dosym -r /opt/1Password/resources/${MY_PN}.desktop "/usr/share/applications/${MY_PN}.desktop"
	newicon "${D}/opt/1Password/resources/icons/hicolor/512x512/apps/${MY_PN}.png" "${MY_PN}.png"

	dodoc "${D}/opt/1Password/resources/custom_allowed_browsers"
}

pkg_postinst() {
	# chrome-sandbox requires the setuid bit to be specifically set.
	# See https://github.com/electron/electron/issues/17972
	chmod 4755 /opt/1Password/chrome-sandbox

	# This gives no extra permissions to the binary. It only hardens it against environmental tampering.
	chgrp onepassword /opt/1Password/1Password-BrowserSupport
	chmod g+s /opt/1Password/1Password-BrowserSupport

	xdg_pkg_postinst
}

pkg_postrm() {
	xdg_icon_cache_update
	xdg_desktop_database_update
	xdg_mimeinfo_database_update
}
