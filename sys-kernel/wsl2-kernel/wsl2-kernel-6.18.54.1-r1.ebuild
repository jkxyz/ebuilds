# Copyright 2020-2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

inherit kernel-build savedconfig

DESCRIPTION="Linux kernel built with Microsoft's WSL patches and defaults"
HOMEPAGE="https://github.com/microsoft/WSL2-Linux-Kernel/"
SRC_URI="https://github.com/microsoft/WSL2-Linux-Kernel/archive/refs/tags/linux-msft-wsl-${PV}.tar.gz -> WSL2-Linux-Kernel-${PV}.tar.gz"
S="${WORKDIR}/WSL2-Linux-Kernel-linux-msft-wsl-${PV}"

LICENSE="GPL-2"
KEYWORDS="~amd64 ~arm64"
IUSE="debug"

PATCHES=( "${FILESDIR}/wsl-modules-layout.patch" )

BDEPEND="
	app-emulation/qemu
	dev-libs/openssl
	dev-util/pahole
	net-misc/rsync
	sys-fs/e2fsprogs
"

pkg_pretend() {
	# WSL supplies its own initramfs and does not use /boot or a bootloader.
	:
}

pkg_setup() {
	kernel-build_pkg_setup
	# Deployment reads the current make.conf, including for binary installs.
	unset WSL_KERNEL_DIR WSL_AUTO_UPDATE_CONFIG
}

src_prepare() {
	default
	case ${ARCH} in
		amd64) cp Microsoft/config-wsl .config || die ;;
		arm64) cp Microsoft/config-wsl-arm64 .config || die ;;
		*) die "Unsupported architecture: ${ARCH}" ;;
	esac
	kernel-build_merge_configs
}

src_install() {
	# kernel-build_src_install consumes the source tree.
	cp Microsoft/scripts/gen_artifacts_vhdx.sh "${T}/" || die
	emake O="${WORKDIR}/build" "${MAKEARGS[@]}" \
		INSTALL_HDR_PATH="${T}/headers" headers_install
	mkdir "${T}/perf" || die
	kernel-build_src_install

	# perf is optional userspace tooling; install it with Gentoo if required.
	TMPDIR="${T}" bash "${T}/gen_artifacts_vhdx.sh" \
		"${ED}" "${T}/headers" "${T}/perf" "${KV_FULL}" \
		"${T}/modules.vhdx" || die "Could not create the WSL modules image"
	insinto "/usr/src/linux-${KV_FULL}"
	doins "${T}/modules.vhdx"

	insinto "/usr/share/${PN}/${P}"
	doins "${FILESDIR}/deploy.ps1"
	dodoc "${FILESDIR}/README.md"
}

wsl2_kernel_manual_instructions() {
	elog "To install manually, copy both artifacts shown above to a Windows directory."
	elog 'Set kernel= and kernelModules= under [wsl2] in %UserProfile%\.wslconfig.'
	elog "Use absolute Windows paths with doubled backslashes."
	elog "After configuring it, run wsl --shutdown from Windows, then start WSL again."
	elog "This stops all WSL distributions; save your work first."
	elog "Retry deployment without rebuilding: emerge --config =${CATEGORY}/${PF}"
}

wsl2_kernel_deploy() {
	local source_dir="${EROOT}/usr/src/linux-${KV_FULL}"
	local kernel="${source_dir}/$(dist-kernel_get_image_path)"
	local modules="${source_dir}/modules.vhdx"
	elog "Kernel: ${kernel}"
	elog "Modules image: ${modules}"

	# Do not reuse the build machine's saved environment when installing a binpkg.
	local destination status=0
	destination=$(env -u WSL_KERNEL_DIR portageq envvar WSL_KERNEL_DIR) || status=${?}
	# portageq returns 1 for an unset variable.
	if (( status > 1 )); then
		ewarn "Could not read WSL_KERNEL_DIR; automatic deployment skipped."
		wsl2_kernel_manual_instructions
		return
	fi
	if [[ -z ${destination} ]]; then
		elog "WSL_KERNEL_DIR is unset or empty; Windows deployment is disabled."
		wsl2_kernel_manual_instructions
		return
	fi
	# EAPI 7+ strips the trailing slash: the live system has EROOT="".
	if [[ -n ${EROOT} ]]; then
		ewarn "Automatic Windows deployment is unavailable for EROOT='${EROOT}'."
		wsl2_kernel_manual_instructions
		return
	fi
	if [[ ${destination} != /* || ! -d ${destination} ]]; then
		ewarn "WSL_KERNEL_DIR is not an existing absolute directory: ${destination}"
		wsl2_kernel_manual_instructions
		return
	fi
	local auto_update config_args=()
	status=0
	auto_update=$(env -u WSL_AUTO_UPDATE_CONFIG portageq envvar WSL_AUTO_UPDATE_CONFIG) || status=${?}
	if (( status > 1 )); then
		ewarn "Could not read WSL_AUTO_UPDATE_CONFIG; .wslconfig will not be changed."
	else
		case ${auto_update} in
			true) config_args+=( -UpdateConfig ) ;;
			false|"") ;;
			*) ewarn "WSL_AUTO_UPDATE_CONFIG must be true or false; .wslconfig will not be changed." ;;
		esac
	fi

	local powershell script_win kernel_win modules_win destination_win
	powershell=$(command -v powershell.exe)
	if [[ -z ${powershell} ]]; then
		# Portage normally removes the Windows directories from PATH.
		powershell=$(wslpath -u 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe')
	fi
	if [[ ! -x ${powershell} ]] ||
		! script_win=$(wslpath -w "${EROOT}/usr/share/${PN}/${P}/deploy.ps1") ||
		! kernel_win=$(wslpath -w "${kernel}") ||
		! modules_win=$(wslpath -w "${modules}") ||
		! destination_win=$(wslpath -w "${destination}"); then
		ewarn "Windows interoperability is unavailable; automatic deployment skipped."
		wsl2_kernel_manual_instructions
		return
	fi

	elog "WSL_KERNEL_DIR=${destination}"
	elog "Deploying the kernel and matching modules image to: ${destination_win}"
	elog "Both files will be verified in a versioned release directory."
	elog "Existing releases will be kept so a running WSL VM can continue using them."
	if (( ${#config_args[@]} )); then
		elog "WSL_AUTO_UPDATE_CONFIG=true: your Windows .wslconfig will be updated if needed after verification."
		elog "Only kernel and kernelModules under [wsl2] will be updated; other settings are preserved."
		elog "An existing configuration will be backed up beside it before changes are applied."
		elog "A missing configuration will be created; an unchanged one needs no new backup."
	else
		elog "WSL_AUTO_UPDATE_CONFIG=${auto_update:-<unset>}: automatic configuration is disabled."
		elog "Your .wslconfig will be left unchanged. Use the printed paths to configure it manually."
		elog "Set WSL_AUTO_UPDATE_CONFIG=true in make.conf to enable automatic configuration."
	fi
	elog "PowerShell will run hidden. This deployment does not restart WSL."

	# Capture Windows output so Portage retains it in elog, including on failure.
	# Windows interop cannot reliably launch from Portage's private working directory.
	local output line deploy_status=0
	output=$(
		exec 2>&1
		cd "${destination}" &&
			"${powershell}" -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass \
			-File "${script_win}" -Kernel "${kernel_win}" -Modules "${modules_win}" \
			-Destination "${destination_win}" -Release "${PF}" "${config_args[@]}"
	) || deploy_status=${?}
	while IFS= read -r line; do
		line=${line%$'\r'}
		[[ -n ${line} ]] || continue
		if (( deploy_status )); then
			ewarn "${line}"
		else
			elog "${line}"
		fi
	done <<< "${output}"
	if (( deploy_status )); then
		ewarn "Windows deployment failed (exit ${deploy_status}); see the details above."
		ewarn "The installed Gentoo artifacts remain available."
		wsl2_kernel_manual_instructions
	else
		elog "Retry deployment without rebuilding: emerge --config =${CATEGORY}/${PF}"
	fi
}

pkg_postinst() {
	savedconfig_pkg_postinst
	dist-kernel_update_src_symlink "${EROOT}/usr/src/linux" "${KV_FULL}"
	wsl2_kernel_deploy
}

pkg_config() {
	wsl2_kernel_deploy
}
