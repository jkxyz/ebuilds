# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

CHROMIUM_LANGS="af am ar bg bn ca cs da de el en-GB en-US es-419 es
	et fa fi fil fr gu he hi hr hu id it ja kn ko lt lv ml mr ms nb nl
	pl pt-BR pt-PT ro ru sk sl sr sv sw ta te th tr uk ur vi zh-CN zh-TW"

inherit chromium-2 desktop pax-utils xdg

DESCRIPTION="Private, fast, and honest web browser based on Chromium"
HOMEPAGE="https://helium.computer/"
BASE_URI="https://github.com/imputnet/helium-linux/releases/download/${PV}"
SRC_URI="
	amd64? (
		${BASE_URI}/helium-${PV}-x86_64_linux.tar.xz
			-> ${P}-amd64.tar.xz
	)
	arm64? (
		${BASE_URI}/helium-${PV}-arm64_linux.tar.xz
			-> ${P}-arm64.tar.xz
	)"

case ${ARCH} in
	amd64) HELIUM_ARCH=x86_64 ;;
	arm64) HELIUM_ARCH=arm64 ;;
esac
S="${WORKDIR}/helium-${PV}-${HELIUM_ARCH}_linux"

LICENSE="GPL-3 BSD"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
IUSE="qt6 selinux"
REQUIRED_USE="elibc_glibc"

RDEPEND="
	>=app-accessibility/at-spi2-core-2.46.0:2
	app-misc/ca-certificates
	dev-libs/expat
	dev-libs/glib:2
	dev-libs/nspr
	>=dev-libs/nss-3.26
	media-fonts/liberation-fonts
	media-libs/alsa-lib
	media-libs/mesa[gbm(+)]
	net-misc/curl
	net-print/cups
	sys-apps/dbus
	elibc_glibc? ( sys-libs/glibc )
	sys-libs/libcap
	x11-libs/cairo
	x11-libs/gdk-pixbuf:2
	|| (
		gui-libs/gtk:4[X]
		x11-libs/gtk+:3[X]
	)
	x11-libs/libdrm
	x11-libs/libX11
	x11-libs/libxcb
	x11-libs/libXcomposite
	x11-libs/libXdamage
	x11-libs/libXext
	x11-libs/libXfixes
	x11-libs/libXrandr
	x11-libs/libXScrnSaver
	x11-libs/libxkbcommon
	x11-libs/libxshmfence
	x11-libs/pango
	x11-misc/xdg-utils
	qt6? ( dev-qt/qtbase:6[gui,widgets] )
	selinux? ( sec-policy/selinux-chromium )
"

RESTRICT="bindist mirror strip"

QA_PREBUILT="opt/helium/*"

pkg_setup() {
	chromium_suid_sandbox_check_kernel_config
}

src_prepare() {
	default

	pushd locales >/dev/null || die
	rm -f -- *.info || die
	chromium_remove_language_paks
	popd >/dev/null || die

	rm -f libqt5_shim.so || die
	if ! use qt6; then
		rm -f libqt6_shim.so || die
	fi
}

src_install() {
	dodir /opt/helium
	cp -a . "${ED}/opt/helium/" || die

	newicon -s 256 product_logo_256.png helium.png
	domenu helium.desktop
	dosym -r /opt/helium/helium-wrapper /usr/bin/helium

	pax-mark m "${ED}/opt/helium/helium"
}
