# Building Draco for Windows 11

The code runs on Windows, but the `.exe` has to be built on a Windows 11 PC, because GTK 4 must be bundled from Windows itself. It takes about 15 minutes the first time.

## One-time setup

1. Copy the whole `draco` folder to the Windows PC, for example to `C:\draco`.
2. Open **PowerShell** and install the two build tools:
   ```powershell
   winget install MSYS2.MSYS2 JRSoftware.InnoSetup
   ```

## Build

```powershell
cd C:\draco
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
```

The script:
1. Installs GTK 4, libadwaita, PyGObject and PyInstaller inside MSYS2.
2. Freezes the app into `dist\Draco\` (`Draco.exe` plus `draco-host.exe`, the browser helper).
3. Downloads `yt-dlp.exe` and `ffmpeg.exe` next to `Draco.exe`. They're needed for YouTube, HLS streams and subtitles.
4. Builds the installer **`dist\DracoSetup-1.4.0.exe`** with Inno Setup.

## What the installer does

- Installs for the current user to `%LOCALAPPDATA%\Programs\Draco`, so there's no administrator prompt.
- Adds Start-menu and (optionally) desktop shortcuts, plus an optional "start when I sign in" entry.
- Registers the browser helper for Chrome, Edge, Brave, Chromium, Opera, Vivaldi and Firefox. These are per-user registry keys under `HKCU\Software\…\NativeMessagingHosts`.
- Copies the browser extension to `Documents\Draco Browser Extension`. Load the `chrome` folder from there under `edge://extensions` / `chrome://extensions` → Developer mode → **Load unpacked**.
- The uninstaller removes the registry keys again.

## Where Draco keeps things on Windows

| What | Where |
|---|---|
| Settings | `%APPDATA%\Draco\settings.json` |
| Download list | `%LOCALAPPDATA%\Draco\downloads.json` |
| Downloads | your *Downloads* folder, in category sub-folders |

## Differences from Linux

- The app and its browser helper talk over a local `127.0.0.1` connection with a secret token, instead of a Unix socket.
- "Shut down / sleep / hibernate when the queue is done" use `shutdown /s`, `rundll32 powrprof.dll,SetSuspendState` and `shutdown /h`.
- "Open folder" opens Explorer with the file selected.
- The app isn't code-signed. Windows SmartScreen will say "Windows protected your PC" the first time: click **More info → Run anyway**. Signing needs a paid code-signing certificate.
