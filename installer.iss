; Inno Setup script for Operator.
; Build on Windows:  iscc installer.iss   (needs Inno Setup 6 + a built dist\Operator.exe)
; Produces:          Output\OperatorSetup.exe
;
; The API key is NOT collected here — Operator asks for it on first launch and
; stores it in Windows Credential Manager. This installer only lays down files.

#define AppName "Operator"
#define AppVersion "0.1.0"
#define AppPublisher "James King"
#define AppExe "Operator.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Per-user install needs no admin rights, matching the "no admin" constraint.
PrivilegesRequired=lowest
OutputBaseFilename=OperatorSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
; The built exe (PyInstaller onefile).
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
; Seed files placed alongside the exe. Operator copies these to config.toml /
; profile.toml on first run if they are missing. profile.toml itself is never shipped.
Source: "config.example.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "profile.example.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "playbooks\*"; DestDir: "{app}\playbooks"; Flags: ignoreversion recursesubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
; Offer to launch after install; first launch runs setup and prompts for the key.
Filename: "{app}\{#AppExe}"; Description: "Launch Operator (sets up your API key)"; Flags: nowait postinstall skipifsilent
