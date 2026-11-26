$ErrorActionPreference = 'Stop'

if (-not $IsWindows -and $env:OS -ne 'Windows_NT') {
    throw 'Windowsで実行してください。'
}

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    uv run --with pyinstaller pyinstaller --noconfirm --clean --onefile --name pshift --copy-metadata paper-shift src/__main__.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstallerのビルドに失敗しました。' }

    $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
    $archive = Join-Path $root "dist/pshift-windows-$arch.zip"
    Compress-Archive -Force -Path @(
        (Join-Path $root 'dist/pshift.exe'),
        (Join-Path $PSScriptRoot 'install-windows.ps1'),
        (Join-Path $PSScriptRoot 'uninstall-windows.ps1')
    ) -DestinationPath $archive
    Write-Host "作成しました: $archive"
}
finally {
    Pop-Location
}
