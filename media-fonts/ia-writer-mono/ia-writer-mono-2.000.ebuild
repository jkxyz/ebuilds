# Copyright 1999-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit font

# Upstream publishes no releases. The static fonts, version 2.000, have not
# changed since 2018, so pin a snapshot of the repository.
COMMIT="c6588670c71e9ac628acc27b72cde4bf12726b7f"

DESCRIPTION="Monospaced typeface from iA Writer, based on IBM Plex Mono"
HOMEPAGE="https://github.com/iaolo/iA-Fonts"
SRC_URI="https://github.com/iaolo/iA-Fonts/archive/${COMMIT}.tar.gz -> ${P}.gh.tar.gz"
S="${WORKDIR}/iA-Fonts-${COMMIT}"

LICENSE="OFL-1.1"
SLOT="0"
KEYWORDS="~amd64 ~arm64"

DOCS=( "iA Writer Mono/Readme.md" )

FONT_S="${S}/iA Writer Mono/Static"
FONT_SUFFIX="ttf"
