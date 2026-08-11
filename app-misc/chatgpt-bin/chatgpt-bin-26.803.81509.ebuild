# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit desktop linux-info optfeature pax-utils unpacker xdg

DESCRIPTION="Official ChatGPT desktop application"
HOMEPAGE="https://openai.com/codex/ https://developers.openai.com/codex/app"
BASE_URI="https://persistent.oaistatic.com/codex-app-prod/linux/deb/pool/main/c/chatgpt"
SRC_URI="
	amd64? ( ${BASE_URI}/chatgpt_${PV}_amd64.deb -> ${P}-amd64.deb )
	arm64? ( ${BASE_URI}/chatgpt_${PV}_arm64.deb -> ${P}-arm64.deb )
"
S="${WORKDIR}"

LICENSE="all-rights-reserved"
SLOT="0"
KEYWORDS="~amd64 ~arm64"

RDEPEND="
	app-accessibility/at-spi2-core:2
	app-misc/ca-certificates
	dev-libs/expat
	dev-libs/glib:2
	dev-libs/libusb:1
	dev-libs/nspr
	dev-libs/nss
	dev-libs/openssl
	dev-vcs/git
	media-gfx/graphite2
	media-libs/fontconfig
	media-libs/alsa-lib
	media-libs/mesa[gbm(+)]
	net-print/cups
	sys-apps/dbus
	sys-devel/gcc
	sys-libs/glibc
	virtual/udev
	x11-libs/cairo
	x11-libs/gdk-pixbuf:2
	x11-libs/gtk+:3[X]
	x11-libs/libdrm
	x11-libs/libnotify
	x11-libs/libX11
	x11-libs/libxcb
	x11-libs/libXcomposite
	x11-libs/libXdamage
	x11-libs/libXext
	x11-libs/libXfixes
	x11-libs/libXrandr
	x11-libs/libxkbcommon
	x11-libs/libxshmfence
	x11-libs/pango
	x11-misc/xdg-utils
"

RESTRICT="bindist mirror strip"

QA_PREBUILT="usr/lib/chatgpt/*"
CONFIG_CHECK="~USER_NS"

src_unpack() {
	unpack_deb "${A}"
}

src_install() {
	dodoc usr/share/doc/chatgpt/copyright
	domenu usr/share/applications/chatgpt.desktop
	doicon usr/share/pixmaps/chatgpt.png

	dosym ../lib/chatgpt/codex-launcher /usr/bin/chatgpt
	cp -a "${S}"/usr/lib "${ED}"/usr/ || die

	insinto /etc/apparmor.d
	doins etc/apparmor.d/chatgpt

	pax-mark m \
		"${ED}"/usr/lib/chatgpt/ChatGPT \
		"${ED}"/usr/lib/chatgpt/browser_crashpad_handler
}

pkg_postinst() {
	xdg_pkg_postinst

	optfeature "secure credential storage" app-crypt/libsecret
	optfeature "emoji support" media-fonts/noto-emoji
	optfeature "PulseAudio support" media-libs/libpulse
}

pkg_postrm() {
	xdg_pkg_postrm
}
