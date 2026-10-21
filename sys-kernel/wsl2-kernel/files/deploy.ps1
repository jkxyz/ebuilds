# Copyright 2026 Josh Kingsley
# Distributed under the terms of the GNU General Public License v2

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Kernel,
    [Parameter(Mandatory = $true)][string]$Modules,
    [Parameter(Mandatory = $true)][string]$Destination,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9._+-]*$')][string]$Release,
    [switch]$UpdateConfig,
    [string]$ConfigPath = (Join-Path $env:USERPROFILE '.wslconfig')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-DirectPath([string]$Path) {
    # WSL can reject paths through user-created junctions with 0x800701c0.
    while ($Path) {
        $entry = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
        if ($null -ne $entry -and ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Use a direct Windows path, without junctions or symlinks: $Path"
        }
        $Path = [IO.Path]::GetDirectoryName($Path)
    }
}

function Set-KernelPaths([string]$Text, [string]$KernelPath, [string]$ModulesPath) {
    $newline = "`n"
    if ($Text.Contains("`r`n") -or $Text.Length -eq 0) { $newline = "`r`n" }
    $sections = [regex]::Matches($Text, '(?m)^[ \t]*\[([^\]\r\n]+)\][ \t]*(?:[;#][^\r\n]*)?(?:\r?\n|\z)')
    $wsl = @($sections | Where-Object { $_.Groups[1].Value.Trim() -ieq 'wsl2' })
    if ($wsl.Count -gt 1) { throw 'Multiple [wsl2] sections; resolve them before automatic configuration.' }
    if ($wsl.Count -eq 0) {
        if ($Text.Length -gt 0 -and -not $Text.EndsWith("`n")) { $Text += $newline }
        return $Text + '[wsl2]' + $newline + 'kernel=' + $KernelPath + $newline +
            'kernelModules=' + $ModulesPath + $newline
    }
    $start = $wsl[0].Index + $wsl[0].Length
    $end = $Text.Length
    foreach ($section in $sections) {
        if ($section.Index -ge $start) { $end = $section.Index; break }
    }
    $prefix = $Text.Substring(0, $start)
    if (-not $prefix.EndsWith("`n")) { $prefix += $newline }
    $body = $Text.Substring($start, $end - $start)
    foreach ($setting in @(@('kernel', $KernelPath), @('kernelModules', $ModulesPath))) {
        $pattern = [regex]::new('(?im)^([ \t]*' + $setting[0] + '[ \t]*=)[^\r\n]*')
        $value = $setting[1]
        if ($pattern.IsMatch($body)) {
            $body = $pattern.Replace($body, [Text.RegularExpressions.MatchEvaluator]{
                param($match)
                $match.Groups[1].Value + $value
            })
        } else {
            $body = $setting[0] + '=' + $value + $newline + $body
        }
    }
    return $prefix + $body + $Text.Substring($end)
}

function Update-KernelConfig([string]$KernelPath, [string]$ModulesPath) {
    $path = [IO.Path]::GetFullPath($ConfigPath)
    Assert-DirectPath $path
    $configLock = $null
    $temporary = $null
    try {
        $configLock = [IO.File]::Open(($path + '.wsl-kernel.lock'),
            [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        $exists = [IO.File]::Exists($path)
        $original = ''
        $encoding = [Text.UTF8Encoding]::new($false, $true)
        if ($exists) {
            $bytes = [IO.File]::ReadAllBytes($path)
            $reader = [IO.StreamReader]::new([IO.MemoryStream]::new($bytes, $false), $encoding, $true)
            try {
                $original = $reader.ReadToEnd()
                # Preserve the detected BOM; the default UTF-8 encoding has none.
                $encoding = $reader.CurrentEncoding
            } finally { $reader.Dispose() }
        }
        $updated = Set-KernelPaths $original $KernelPath $ModulesPath
        if ($exists -and $updated -ceq $original) {
            Write-Output "Configuration already selects this release: $path"
            Write-Output 'No configuration changes or new backup were needed.'
            return
        }
        $temporary = $path + '.tmp-' + [Guid]::NewGuid().ToString('N')
        [IO.File]::WriteAllText($temporary, $updated, $encoding)
        if ($exists) {
            # Avoid overwriting an edit made while the replacement was prepared.
            $current = [IO.File]::ReadAllBytes($path)
            if ([Convert]::ToBase64String($current) -cne [Convert]::ToBase64String($bytes)) {
                throw 'Configuration changed during deployment; retry the update.'
            }
            $backup = $path + '.wsl-kernel-backup-' + [Guid]::NewGuid().ToString('N')
            [IO.File]::Replace($temporary, $path, $backup)
            Write-Output "Previous configuration backed up to: $backup"
            Write-Output "Updated kernel and kernelModules under [wsl2] in: $path"
        } else {
            [IO.File]::Move($temporary, $path)
            Write-Output "Created configuration with this kernel and modules image: $path"
        }
        $temporary = $null
    } finally {
        if ($null -ne $temporary -and [IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
        if ($null -ne $configLock) { $configLock.Dispose() }
    }
}

$lock = $null
$staging = $null
try {
    if ($Destination -notmatch '^[a-zA-Z]:\\' -or
        -not (Test-Path -LiteralPath $Destination -PathType Container)) {
        throw 'Destination must be an existing directory on a local Windows drive.'
    }
    $Destination = [IO.Path]::GetFullPath($Destination)
    Assert-DirectPath $Destination
    $lock = [IO.File]::Open((Join-Path $Destination '.deploy.lock'),
        [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)

    foreach ($source in @($Kernel, $Modules)) {
        if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or
            (Get-Item -LiteralPath $source).Length -eq 0) {
            throw "Missing or empty artifact: $source"
        }
    }
    $kernelHash = (Get-FileHash -LiteralPath $Kernel -Algorithm SHA256).Hash
    $modulesHash = (Get-FileHash -LiteralPath $Modules -Algorithm SHA256).Hash
    $build = "$Release-$($kernelHash.Substring(0, 12))-$($modulesHash.Substring(0, 12))"
    $releases = Join-Path $Destination 'releases'
    Assert-DirectPath $releases
    [IO.Directory]::CreateDirectory($releases) | Out-Null
    $target = Join-Path $releases $build
    Assert-DirectPath (Join-Path $target 'kernel')
    Assert-DirectPath (Join-Path $target 'modules.vhdx')

    if (-not (Test-Path -LiteralPath $target)) {
        Write-Output 'Copying kernel and modules image into a new release directory.'
        $staging = Join-Path $releases ('.staging-' + [Guid]::NewGuid().ToString('N'))
        [IO.Directory]::CreateDirectory($staging) | Out-Null
        Copy-Item -LiteralPath $Kernel -Destination (Join-Path $staging 'kernel')
        Copy-Item -LiteralPath $Modules -Destination (Join-Path $staging 'modules.vhdx')
        if ((Get-FileHash -LiteralPath (Join-Path $staging 'kernel')).Hash -ne $kernelHash -or
            (Get-FileHash -LiteralPath (Join-Path $staging 'modules.vhdx')).Hash -ne $modulesHash) {
            throw 'Artifact verification failed; configuration has not been changed.'
        }
        [IO.Directory]::Move($staging, $target)
        $staging = $null
    } elseif ((Get-FileHash -LiteralPath (Join-Path $target 'kernel')).Hash -ne $kernelHash -or
              (Get-FileHash -LiteralPath (Join-Path $target 'modules.vhdx')).Hash -ne $modulesHash) {
        throw "Existing release is incomplete or modified: $target"
    } else {
        Write-Output 'Existing release matches both artifacts; reusing it without copying.'
    }

    $kernelPath = (Join-Path $target 'kernel').Replace('\', '\\')
    $modulesPath = (Join-Path $target 'modules.vhdx').Replace('\', '\\')
    Write-Output "Verified release ready: $target"
    if ($UpdateConfig) {
        Write-Output "Automatic configuration enabled. Applying these entries to: $ConfigPath"
    } else {
        Write-Output "Automatic configuration disabled. This file has not been changed: $ConfigPath"
        Write-Output 'Manually set these entries in that file, preserving any other settings:'
    }
    Write-Output '[wsl2]'
    Write-Output ('kernel=' + $kernelPath)
    Write-Output ('kernelModules=' + $modulesPath)
    if ($UpdateConfig) { Update-KernelConfig $kernelPath $modulesPath }
    if ($UpdateConfig) {
        Write-Output 'The configured kernel will be used the next time the WSL VM starts.'
    } else {
        Write-Output 'Finish the manual configuration before restarting WSL to use this release.'
    }
    Write-Output 'When ready, save your work and run wsl --shutdown from Windows, then start WSL again.'
    Write-Output 'This stops all WSL distributions. The custom kernel applies to all WSL 2 distributions.'
} catch {
    Write-Error -ErrorRecord $_ -ErrorAction Continue
    exit 1
} finally {
    if ($null -ne $staging -and (Test-Path -LiteralPath $staging)) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    if ($null -ne $lock) { $lock.Dispose() }
}
