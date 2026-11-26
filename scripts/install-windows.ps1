$ErrorActionPreference = 'Stop'

$binary = Join-Path $PSScriptRoot 'pshift.exe'
if (-not (Test-Path $binary)) {
    throw '配布アーカイブを展開してから実行してください。'
}

$destination = Join-Path $env:LOCALAPPDATA 'Programs/PaperShift'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -Force $binary (Join-Path $destination 'pshift.exe')

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$entries = @($userPath -split ';' | Where-Object { $_ })
if ($entries -notcontains $destination) {
    [Environment]::SetEnvironmentVariable('Path', (@($entries) + $destination) -join ';', 'User')
}

$currentEntries = @($env:Path -split ';' | Where-Object { $_ })
if ($currentEntries -notcontains $destination) {
    $env:Path = (@($currentEntries) + $destination) -join ';'
}

Write-Host "インストールしました: $(Join-Path $destination 'pshift.exe')"
Write-Host 'ユーザーのPATHに設定しました。pshift --helpで確認してください。'
