# Copyright 2026 Josh Kingsley
# Distributed under the terms of the GNU General Public License v2
param(
    [string]$Script = (Join-Path $PSScriptRoot '../sys-kernel/wsl2-kernel/files/deploy.ps1')
)
$ErrorActionPreference = 'Stop'
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('wsl-kernel-test-' + [Guid]::NewGuid().ToString('N'))
$held = $null
$legacy = $null

function Assert($Condition, $Message) {
    if (-not $Condition) { throw $Message }
}
function Deploy($Kernel, $Modules, [bool]$Update = $false, [int]$Expected = 0) {
    $process = New-Object Diagnostics.Process
    $process.StartInfo.FileName = Join-Path $PSHOME 'powershell.exe'
    $arguments = @('-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden',
        '-ExecutionPolicy', 'Bypass', '-File', $Script, '-Kernel', $Kernel,
        '-Modules', $Modules, '-Destination', $destination, '-Release', 'test-1',
        '-ConfigPath', $config)
    if ($Update) { $arguments += '-UpdateConfig' }
    $process.StartInfo.Arguments = ($arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.Start() | Out-Null
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $code = $process.ExitCode
    $output = $stdout.Result + $stderr.Result
    $process.Dispose()
    if ($code -ne $Expected) {
        throw "Deployment exited $code (expected $Expected): $output"
    }
    return $output
}
function Release-Path {
    $kh = (Get-FileHash -LiteralPath $kernel).Hash.Substring(0, 12)
    $mh = (Get-FileHash -LiteralPath $modules).Hash.Substring(0, 12)
    return Join-Path $destination "releases/test-1-$kh-$mh"
}
function Config-Text($Target) {
    return '[wsl2]' + "`r`n" + 'kernel=' + (Join-Path $Target 'kernel').Replace('\', '\\') +
        "`r`n" + 'kernelModules=' + (Join-Path $Target 'modules.vhdx').Replace('\', '\\') + "`r`n"
}
function Backup-Count {
    return @(Get-ChildItem -LiteralPath $testRoot -Filter '.wslconfig.wsl-kernel-backup-*').Count
}
try {
    $destination = Join-Path $testRoot "WSL [test] with 'quotes' and `$dollars"
    [IO.Directory]::CreateDirectory($destination) | Out-Null
    $kernel = Join-Path $testRoot 'kernel'
    $modules = Join-Path $testRoot 'modules.vhdx'
    $config = Join-Path $testRoot '.wslconfig'
    $utf8 = [Text.UTF8Encoding]::new($false, $true)
    [IO.File]::WriteAllText($kernel, 'kernel A')
    [IO.File]::WriteAllText($modules, 'modules A')
    $original = "# caf$([char]0xe9)`n[wsl2]`nmemory=8GB`n  kernel =old`nkernelModules=old`n# keep me`n[experimental]`nsparseVhd=true`n"
    [IO.File]::WriteAllText($config, $original, $utf8)
    $originalHash = (Get-FileHash -LiteralPath $config).Hash
    $output = Deploy $kernel $modules
    $first = Release-Path
    Assert ($output.Contains(('kernel=' + (Join-Path $first 'kernel').Replace('\', '\\')))) 'Manual paths were not printed'
    Assert ((Get-FileHash -LiteralPath $config).Hash -eq $originalHash) 'Manual mode changed configuration'
    Assert ((Backup-Count) -eq 0) 'Manual mode made a backup'
    Assert (-not (Test-Path -LiteralPath (Join-Path $destination 'default'))) 'Deployment created a junction'
    Assert ([IO.File]::ReadAllText((Join-Path $first 'kernel')) -eq 'kernel A') 'Initial copy failed'

    $output = Deploy $kernel $modules $true
    $expected = $original.Replace('kernel =old', 'kernel =' + (Join-Path $first 'kernel').Replace('\', '\\')).Replace(
        'kernelModules=old', 'kernelModules=' + (Join-Path $first 'modules.vhdx').Replace('\', '\\'))
    Assert ([IO.File]::ReadAllText($config) -ceq $expected) 'Unrelated text or line endings changed'
    Assert ([IO.File]::ReadAllBytes($config)[0] -eq 35) 'Added a UTF-8 BOM'
    $backups = @(Get-ChildItem -LiteralPath $testRoot -Filter '.wslconfig.wsl-kernel-backup-*')
    Assert ($backups.Count -eq 1) 'Missing configuration backup'
    Assert ((Get-FileHash -LiteralPath $backups[0].FullName).Hash -eq $originalHash) 'Backup differs from original'
    $output = Deploy $kernel $modules $true
    Assert ((Backup-Count) -eq 1) 'Idempotent retry made another backup'
    Assert (@(Get-ChildItem -LiteralPath (Join-Path $destination 'releases')).Count -eq 1) 'Retry duplicated release'

    # A legacy default junction is left alone; all new paths bypass it.
    $legacy = Join-Path $destination 'default'
    $oldRelease = Join-Path $testRoot 'old-release'
    [IO.Directory]::CreateDirectory($oldRelease) | Out-Null
    New-Item -ItemType Junction -Path $legacy -Value $oldRelease | Out-Null
    $held = [IO.File]::Open((Join-Path $first 'modules.vhdx'),
        [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
    [IO.File]::WriteAllText($kernel, 'kernel B')
    [IO.File]::WriteAllText($modules, 'modules B')
    $output = Deploy $kernel $modules $true
    $second = Release-Path
    Assert ([IO.File]::ReadAllText((Join-Path $second 'modules.vhdx')) -eq 'modules B') 'New pair missing'
    Assert ([IO.File]::ReadAllText((Join-Path $first 'kernel')) -eq 'kernel A') 'Old release changed'
    Assert ([IO.File]::ReadAllText($config).Contains($second.Replace('\', '\\'))) 'Configuration did not switch'
    Assert ((Get-Item -LiteralPath $legacy).Target[0] -eq $oldRelease) 'Legacy junction changed'
    $held.Dispose()
    $held = $null

    $before = (Get-FileHash -LiteralPath $config).Hash
    $output = Deploy $kernel (Join-Path $testRoot 'missing.vhdx') $true 1
    Assert ((Get-FileHash -LiteralPath $config).Hash -eq $before) 'Missing artifact changed config'
    [IO.File]::WriteAllText((Join-Path $second 'kernel'), 'modified')
    $output = Deploy $kernel $modules $true 1
    Assert ((Get-FileHash -LiteralPath $config).Hash -eq $before) 'Corrupt release changed config'

    # Rollback reuses the verified old pair. A locked config must stay intact.
    [IO.File]::WriteAllText($kernel, 'kernel A')
    [IO.File]::WriteAllText($modules, 'modules A')
    $held = [IO.File]::Open($config, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
    $output = Deploy $kernel $modules $true 1
    $held.Dispose()
    $held = $null
    Assert ((Get-FileHash -LiteralPath $config).Hash -eq $before) 'Locked config changed'
    $output = Deploy $kernel $modules $true
    Assert ([IO.File]::ReadAllText($config) -ceq $expected) 'Rollback failed'

    # Retain BOMs and CRLF, append missing sections/keys, and support a new file.
    foreach ($encoding in @([Text.UTF8Encoding]::new($true), [Text.Encoding]::Unicode)) {
        $text = "# preserved`r`n[wsl2]`r`nmemory=4GB`r`n"
        [IO.File]::WriteAllText($config, $text, $encoding)
        $output = Deploy $kernel $modules $true
        $actual = [IO.File]::ReadAllText($config)
        Assert ($actual.Contains("memory=4GB`r`n")) 'Missing-key update lost a setting'
        Assert ($actual.Contains('kernel=') -and $actual.Contains('kernelModules=')) 'Missing keys were not added'
        $bytes = [IO.File]::ReadAllBytes($config)
        $bom = $encoding.GetPreamble()
        Assert ([Convert]::ToBase64String($bytes, 0, $bom.Length) -eq [Convert]::ToBase64String($bom)) 'BOM changed'
        Assert (-not $actual.Replace("`r`n", '').Contains("`n")) 'CRLF changed'
    }
    [IO.File]::WriteAllText($config, "[experimental]`nsparseVhd=true", $utf8)
    $output = Deploy $kernel $modules $true
    Assert ([IO.File]::ReadAllText($config).StartsWith("[experimental]`nsparseVhd=true`n[wsl2]`n")) 'Missing section not appended'
    [IO.File]::WriteAllText($config, '[wsl2]', $utf8)
    $output = Deploy $kernel $modules $true
    Assert ([IO.File]::ReadAllText($config).Contains("[wsl2]`n")) 'Header without final newline failed'
    [IO.File]::Delete($config)
    $output = Deploy $kernel $modules
    Assert (-not [IO.File]::Exists($config)) 'Manual mode created configuration'
    $output = Deploy $kernel $modules $true
    Assert ([IO.File]::ReadAllText($config) -ceq (Config-Text $first)) 'New config contents differ'
    [IO.File]::WriteAllText($config, "[wsl2]`n[wsl2]`n", $utf8)
    $before = (Get-FileHash -LiteralPath $config).Hash
    $output = Deploy $kernel $modules $true 1
    Assert ((Get-FileHash -LiteralPath $config).Hash -eq $before) 'Ambiguous sections were changed'

    $destination = $legacy
    $output = Deploy $kernel $modules $false 1
    Assert ($output.Contains('direct Windows path')) 'Junction destination was not rejected'
    Write-Output 'PASS: manual/automatic configuration, backups, text/encoding preservation, locks, retry, rollback, and failure handling'
} finally {
    if ($null -ne $held) { $held.Dispose() }
    if ($null -ne $legacy -and (Test-Path -LiteralPath $legacy)) { [IO.Directory]::Delete($legacy) }
    if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}
