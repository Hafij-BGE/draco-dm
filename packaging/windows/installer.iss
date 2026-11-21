; Inno Setup script: turns dist\Draco\ into DracoSetup-<version>.exe
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\windows\installer.iss
; Installs per user (no admin prompt) to %LOCALAPPDATA%\Programs\Draco.

#ifndef AppVersion
  #define AppVersion "1.9.2"
#endif

[Setup]
ChangesAssociations=yes
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
Name: "torrents"; Description: "Open .torrent files and magnet links with Draco"; GroupDescription: "Options:"
Name: "autostart"; Description: "Start Draco when I sign in (needed for scheduled queues)"; GroupDescription: "Options:"; Flags: unchecked

[Files]
Source: "..\..\dist\Draco\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Draco Download Manager"; Filename: "{app}\Draco.exe"
Name: "{autodesktop}\Draco Download Manager"; Filename: "{app}\Draco.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Draco"; ValueData: """{app}\Draco.exe"" --background"; Tasks: autostart; Flags: uninsdeletevalue
; Torrents: .torrent files and magnet: links (per user, removed on uninstall)
Root: HKCU; Subkey: "Software\Classes\DracoDM.torrent"; ValueType: string; ValueName: ""; ValueData: "Torrent file"; Tasks: torrents; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\DracoDM.torrent\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\Draco.exe,0"; Tasks: torrents
Root: HKCU; Subkey: "Software\Classes\DracoDM.torrent\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Draco.exe"" ""%1"""; Tasks: torrents
Root: HKCU; Subkey: "Software\Classes\.torrent"; ValueType: string; ValueName: ""; ValueData: "DracoDM.torrent"; Tasks: torrents; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.torrent\OpenWithProgids"; ValueType: string; ValueName: "DracoDM.torrent"; ValueData: ""; Tasks: torrents; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\magnet"; ValueType: string; ValueName: ""; ValueData: "URL:Magnet link"; Tasks: torrents; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\magnet"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""; Tasks: torrents
Root: HKCU; Subkey: "Software\Classes\magnet\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\Draco.exe,0"; Tasks: torrents
Root: HKCU; Subkey: "Software\Classes\magnet\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Draco.exe"" ""%1"""; Tasks: torrents

[Run]
; Registers the browser helper (per-user registry keys) and copies the extension to Documents.
Filename: "{app}\Draco.exe"; Parameters: "--install-browser"; Flags: runhidden waituntilterminated
Filename: "{app}\Draco.exe"; Description: "Start Draco Download Manager"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\Draco.exe"; Parameters: "--uninstall-browser"; Flags: runhidden waituntilterminated; RunOnceId: "UnregisterBrowsers"
