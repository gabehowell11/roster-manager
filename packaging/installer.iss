; Inno Setup script for RosterManagerSetup.exe. Build it with:
;     python packaging/build_installer.py
; which runs packaging/build.py first if needed and passes AppVersion from pyproject.toml.
;
; Installs for the current user only (no admin prompt) into
; %LOCALAPPDATA%\Programs\Roster Manager, adds a Start menu entry and a desktop icon,
; and registers an uninstaller in Settings > Apps. Rosters live in the user's app data
; folder, so upgrading or uninstalling never touches them.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "Roster Manager"
#define AppExe "RosterManager.exe"
; Must match APP_USER_MODEL_ID in src/rostermanager/__main__.py so the taskbar
; groups the running app with its pinned shortcut.
#define AppUserModelID "RosterManager.RosterManager"

[Setup]
; Never change AppId: Windows uses it to recognize upgrades of the same app.
AppId={{6D99A611-9021-4CB2-93E9-0CD60968A896}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Roster Manager contributors
AppPublisherURL=https://github.com/gabehowell11/roster-manager
AppSupportURL=https://github.com/gabehowell11/roster-manager/issues
AppComments=Not affiliated with or endorsed by the NFL.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
DisableReadyPage=yes
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
SetupIconFile=icon.ico
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
OutputDir=..\dist
OutputBaseFilename=RosterManagerSetup

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Shortcuts:"

[Files]
; The whole PyInstaller folder. Old files are removed first so an upgrade never
; mixes libraries from two versions.
Source: "..\dist\RosterManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "{#AppUserModelID}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "{#AppUserModelID}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Open {#AppName} now"; Flags: nowait postinstall skipifsilent
