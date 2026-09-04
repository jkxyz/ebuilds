# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit desktop linux-info optfeature pax-utils unpacker xdg

DESCRIPTION="End-to-end encrypted cloud storage desktop client"
HOMEPAGE="https://filen.io/products/desktop https://github.com/FilenCloudDienste/filen-desktop"
BASE_URI="https://github.com/FilenCloudDienste/filen-desktop/releases/download/v${PV}"
SRC_URI="
	amd64? ( ${BASE_URI}/Filen_linux_amd64.deb -> ${P}-amd64.deb )
	arm64? ( ${BASE_URI}/Filen_linux_arm64.deb -> ${P}-arm64.deb )
"
S="${WORKDIR}"

LICENSE="AGPL-3"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
REQUIRED_USE="elibc_glibc"

RDEPEND="
	app-accessibility/at-spi2-core:2
	app-crypt/libsecret
	dev-libs/expat
	dev-libs/glib:2
	dev-libs/nspr
	dev-libs/nss
	media-libs/alsa-lib
	media-libs/mesa[gbm(+)]
	net-print/cups
	sys-apps/dbus
	sys-apps/util-linux
	sys-fs/fuse:3
	elibc_glibc? ( sys-libs/glibc )
	virtual/udev
	x11-libs/cairo
	x11-libs/gdk-pixbuf:2
	x11-libs/gtk+:3[X,wayland]
	x11-libs/libdrm
	x11-libs/libnotify
	x11-libs/libX11
	x11-libs/libxcb
	x11-libs/libXcomposite
	x11-libs/libXdamage
	x11-libs/libXext
	x11-libs/libXfixes
	x11-libs/libXrandr
	x11-libs/libXScrnSaver
	x11-libs/libXtst
	x11-libs/libxkbcommon
	x11-libs/pango
	x11-misc/xdg-utils
"

RESTRICT="bindist mirror strip"

QA_PREBUILT="opt/Filen/*"
CONFIG_CHECK="~USER_NS"

src_unpack() {
	unpack_deb "${A}"
}

src_prepare() {
	default
	gunzip usr/share/doc/filen/changelog.gz || die
	sed -i -e 's|^Exec=/opt/Filen/Filen |Exec=filen |' \
		usr/share/applications/Filen.desktop || die

	local foreign_arch
	local unpacked="opt/Filen/resources/app.asar.unpacked"
	case ${ARCH} in
		amd64) foreign_arch=arm64 ;;
		arm64) foreign_arch=amd64 ;;
	esac
	rm "${unpacked}/bin/rclone/rclone-linux-${foreign_arch}" \
		|| die

	# Upstream bundles musl and glibc native modules in each package.
	rm -r "${unpacked}"/node_modules/@napi-rs/*-musl \
		|| die
	rm "${unpacked}"/node_modules/@msgpackr-extract/*/*.musl.node \
		|| die
}

src_install() {
	dodoc usr/share/doc/filen/changelog
	domenu usr/share/applications/Filen.desktop

	local size
	for size in 16 24 32 48 64 128 256 512 1024; do
		doicon -s "${size}" \
			"usr/share/icons/hicolor/${size}x${size}/apps/Filen.png"
	done

	dodir /opt/Filen
	cp -a opt/Filen/. "${ED}/opt/Filen/" || die
	dosym -r /opt/Filen/Filen /usr/bin/filen

	insinto /etc/apparmor.d
	newins opt/Filen/resources/apparmor-profile Filen

	pax-mark m \
		"${ED}/opt/Filen/Filen" \
		"${ED}/opt/Filen/chrome_crashpad_handler"
}

pkg_postinst() {
	xdg_pkg_postinst

	optfeature "AppIndicator-compatible tray icons" \
		dev-libs/libayatana-appindicator
	optfeature "emoji support" media-fonts/noto-emoji
}

pkg_postrm() {
	xdg_pkg_postrm
}
