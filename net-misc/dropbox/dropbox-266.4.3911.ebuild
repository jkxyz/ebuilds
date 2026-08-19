# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit desktop pax-utils systemd xdg

DESCRIPTION="Official Dropbox desktop syncing client"
HOMEPAGE="https://www.dropbox.com/"
SRC_URI="https://clientupdates.dropboxstatic.com/dbx-releng/client/dropbox-lnx.x86_64-${PV}.tar.gz"

LICENSE="BSD-2 CC-BY-ND-3.0 FTL MIT LGPL-2 openssl dropbox"
SLOT="0"
KEYWORDS="-* ~amd64"
IUSE="selinux X"

RESTRICT="mirror strip"

QA_PREBUILT="opt/dropbox/.*"
QA_EXECSTACK="opt/dropbox/dropbox"

RDEPEND="
	X? (
		dev-libs/libayatana-appindicator
		x11-themes/hicolor-icon-theme
	)
	selinux? ( sec-policy/selinux-dropbox )
	app-arch/bzip2
	dev-libs/glib:2
	dev-libs/libffi:0/8
	media-libs/fontconfig
	media-libs/freetype
	net-misc/wget
	sys-libs/ncurses-compat:5
	virtual/opengl
	virtual/zlib:=
	x11-libs/libICE
	x11-libs/libSM
	x11-libs/libX11
	x11-libs/libXext
	x11-libs/libXrender
	x11-libs/libxcb
"

src_unpack() {
	unpack ${A}
	mkdir -p "${S}" || die
	mv "${WORKDIR}"/.dropbox-dist/* "${S}" || die
	mv "${S}"/dropbox-lnx.x86_64-${PV}/* "${S}" || die
	rmdir "${S}"/dropbox-lnx.x86_64-${PV} || die
	rmdir "${WORKDIR}"/.dropbox-dist || die
}

src_prepare() {
	default

	# Use the system copy declared in RDEPEND.
	rm -v libffi.so.8* || die

	if use X; then
		mv images/hicolor/16x16/status "${T}" || die
	else
		rm -r images || die
	fi

	pax-mark cm dropbox
	mv README ACKNOWLEDGEMENTS "${T}" || die
}

src_install() {
	local targetdir=/opt/dropbox

	insinto "${targetdir}"
	doins -r *
	fperms a+x "${targetdir}"/{dropbox,dropboxd}
	dosym "${targetdir}/dropboxd" /opt/bin/dropbox

	# Dropbox looks for this extension beside its bundled Python modules.
	dosym ../libdropbox_tprt.so "${targetdir}/python-pyext/libdropbox_tprt.so"

	if use X; then
		# The binary expects Ubuntu's library names in its own directory.
		dosym ../../usr/$(get_libdir)/libayatana-appindicator3.so.1 \
			"${targetdir}/libappindicator3.so.1"
		dosym libappindicator3.so.1 "${targetdir}/libappindicator3.so"

		doicon -s 16 -c status "${T}"/status/*
		newicon -s scalable \
			images/emblems/hicolor/64x64/emblems/emblem-dropbox-app.svg \
			dropbox.svg
	fi

	make_desktop_entry --eapi9 "${targetdir}/dropboxd" \
		--desktopid dropbox \
		--name "Dropbox" \
		--icon dropbox \
		--categories "Network;FileTransfer"

	newinitd "${FILESDIR}"/dropbox.initd dropbox
	newconfd "${FILESDIR}"/dropbox.conf dropbox
	systemd_newunit "${FILESDIR}"/dropbox_at.service dropbox@.service

	dodoc "${T}"/{README,ACKNOWLEDGEMENTS}
}

pkg_postinst() {
	xdg_pkg_postinst

	ewarn "Dropbox may try to update itself under ~/.dropbox-dist, outside"
	ewarn "Portage's control. To keep this installation package-managed, run"
	ewarn "the following command as each user who will run Dropbox:"
	ewarn
	ewarn "    install -dm0 ~/.dropbox-dist"
	ewarn
	ewarn "Remove that directory before uninstalling Dropbox or intentionally"
	ewarn "switching back to Dropbox-managed per-user updates."

	if has_version gnome-base/gnome-shell && \
		! has_version gnome-extra/gnome-shell-extension-appindicator; then
		einfo
		einfo "Install gnome-extra/gnome-shell-extension-appindicator for a"
		einfo "Dropbox tray icon in GNOME."
	fi
}
