$ErrorActionPreference = 'Stop'

$baseUrl = $env:PAPERSHIFT_RELEASE_BASE_URL
if (-not $baseUrl) {
    throw '公開URLはまだありません。リリース公開後にPAPERSHIFT_RELEASE_BASE_URLを設定してください。'
}

$arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
$archive = "pshift-windows-$arch.zip"
$temporary = Join-Path ([IO.Path]::GetTempPath()) ("pshift-install-" + [IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $zip = Join-Path $temporary $archive
    Invoke-WebRequest -Uri ($baseUrl.TrimEnd('/') + '/' + $archive) -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $temporary

    $binary = Join-Path $temporary 'pshift.exe'
    if (-not (Test-Path $binary)) { throw '配布アーカイブにpshift.exeがありません。' }
    $destination = Join-Path $env:LOCALAPPDATA 'Programs/PaperShift'
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    Copy-Item -Force $binary (Join-Path $destination 'pshift.exe')
    Copy-Item -Force (Join-Path $temporary 'uninstall-windows.ps1') (Join-Path $destination 'uninstall-windows.ps1')

    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @($userPath -split ';' | Where-Object { $_ })
    if ($entries -notcontains $destination) {
        [Environment]::SetEnvironmentVariable('Path', (@($entries) + $destination) -join ';', 'User')
        New-Item -ItemType File -Force -Path (Join-Path $destination '.path-added') | Out-Null
    }
    $currentEntries = @($env:Path -split ';' | Where-Object { $_ })
    if ($currentEntries -notcontains $destination) {
        $env:Path = (@($currentEntries) + $destination) -join ';'
    }
    Write-Host "インストールしました: $(Join-Path $destination 'pshift.exe')"
    Write-Host 'PATHを設定しました。pshift --helpで確認してください。'
}
finally {
    Remove-Item -Recurse -Force $temporary
}
