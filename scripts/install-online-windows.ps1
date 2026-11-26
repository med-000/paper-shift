$ErrorActionPreference = 'Stop'

$baseUrl = $env:PAPERSHIFT_RELEASE_BASE_URL
if (-not $baseUrl) {
    $baseUrl = 'https://github.com/med-000/paper-shift/releases/latest/download'
}

$arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
if ($arch -ne 'x64') { throw 'Windows x64のみ対応しています。' }
$archive = "pshift-windows-$arch.zip"
$temporary = Join-Path ([IO.Path]::GetTempPath()) ("pshift-install-" + [IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $zip = Join-Path $temporary $archive
    Invoke-WebRequest -Uri ($baseUrl.TrimEnd('/') + '/' + $archive) -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $temporary

    & (Join-Path $temporary 'install-windows.ps1')
}
finally {
    Remove-Item -Recurse -Force $temporary
}
