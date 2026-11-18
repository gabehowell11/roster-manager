# Silently installs dist\RosterManagerSetup.exe for the current user, checks the
# installed app starts (--self-test) and the shortcuts exist, then uninstalls and
# checks it is gone. CI runs this; it also works on a dev machine (it uses a
# throwaway install folder, but does briefly add and remove the shortcuts).
$ErrorActionPreference = "Stop"

$setup = Join-Path $PSScriptRoot "..\dist\RosterManagerSetup.exe"
$dir = Join-Path $env:TEMP "RosterManagerInstallTest"
$exe = Join-Path $dir "RosterManager.exe"
$desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "Roster Manager.lnk"
$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Roster Manager.lnk"

function Run-And-Wait([string]$file, [string[]]$arguments) {
    $p = Start-Process -FilePath $file -ArgumentList $arguments -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "$file exited with $($p.ExitCode)" }
}

if (-not (Test-Path $setup)) { throw "missing $setup; run python packaging/build_installer.py" }
if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }

Write-Host "Installing to $dir"
Run-And-Wait $setup @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/DIR=`"$dir`"", "/TASKS=desktopicon")

if (-not (Test-Path $exe)) { throw "installed exe not found at $exe" }
if (-not (Test-Path $desktop)) { throw "desktop shortcut not found at $desktop" }
if (-not (Test-Path $startMenu)) { throw "Start menu shortcut not found at $startMenu" }

Write-Host "Self-testing the installed app"
Run-And-Wait $exe @("--self-test")

Write-Host "Uninstalling"
$uninstaller = Get-ChildItem $dir -Filter "unins*.exe" | Select-Object -First 1
if ($null -eq $uninstaller) { throw "uninstaller not found in $dir" }
Run-And-Wait $uninstaller.FullName @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")
Start-Sleep -Seconds 2  # the uninstaller finishes deleting itself after it exits

if (Test-Path $exe) { throw "exe still present after uninstall" }
if (Test-Path $desktop) { throw "desktop shortcut still present after uninstall" }
if (Test-Path $startMenu) { throw "Start menu shortcut still present after uninstall" }
Write-Host "Installer test passed"
