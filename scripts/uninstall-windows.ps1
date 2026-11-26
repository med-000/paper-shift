$ErrorActionPreference = 'Stop'

$destination = Join-Path $env:LOCALAPPDATA 'Programs/PaperShift'
$pathMarker = Join-Path $destination '.path-added'
if (Test-Path $pathMarker) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @($userPath -split ';' | Where-Object { $_ -and $_ -ne $destination })
    [Environment]::SetEnvironmentVariable('Path', ($entries -join ';'), 'User')
    $currentEntries = @($env:Path -split ';' | Where-Object { $_ -and $_ -ne $destination })
    $env:Path = $currentEntries -join ';'
    Remove-Item -Force $pathMarker
}

Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $destination 'pshift.exe')
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $destination 'uninstall-windows.ps1')
if (Test-Path $destination) {
    Remove-Item -ErrorAction SilentlyContinue $destination
}
Write-Host 'PaperShiftを削除しました。'
