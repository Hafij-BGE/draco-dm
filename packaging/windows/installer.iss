; Inno Setup script: turns dist\Draco\ into DracoSetup-<version>.exe
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\windows\installer.iss
; Installs per user (no admin prompt) to %LOCALAPPDATA%\Programs\Draco.

#ifndef AppVersion
  #define AppVersion "1.6.1"
#endif

[Setup]
AppId={{6D1F2B8A-4C1E-4E0B-9C59-D7A0C0A0D2A1}
AppName=Draco Download Manager
AppVersion={#AppVersion}
AppPublisher=Md Hafijur Rahman
AppCopyright=© 2026 Md Hafijur Rahman
DefaultDirName={localappdata}\Programs\Draco
DefaultGroupName=Draco Download Manager
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=DracoSetup-{#AppVersion}
SetupIconFile=..\..\data\draco.ico
UninstallDisplayIcon={app}\Draco.exe
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
MinVersion=10.0.17763

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start Draco when I sign in (needed for scheduled queues)"; GroupDescription: "Options:"; Flags: unchecked

[Files]
Source: "..\..\dist\Draco\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Draco Download Manager"; Filename: "{app}\Draco.exe"
Name: "{autodesktop}\Draco Download Manager"; Filename: "{app}\Draco.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Draco"; ValueData: """{app}\Draco.exe"" --background"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
; Registers the browser helper (per-user registry keys) and copies the extension to Documents.
Filename: "{app}\Draco.exe"; Parameters: "--install-browser"; Flags: runhidden waituntilterminated
Filename: "{app}\Draco.exe"; Description: "Start Draco Download Manager"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\Draco.exe"; Parameters: "--uninstall-browser"; Flags: runhidden waituntilterminated; RunOnceId: "UnregisterBrowsers"
