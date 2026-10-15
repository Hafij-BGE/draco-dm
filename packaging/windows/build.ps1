# Build DracoSetup.exe on Windows 11.  Run in PowerShell from the project folder:
#     powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
# Needs: MSYS2 (https://www.msys2.org, default C:\msys64) and Inno Setup 6 (https://jrsoftware.org).
# Both can be installed with:  winget install MSYS2.MSYS2 JRSoftware.InnoSetup

$ErrorActionPreference = "Stop"
$root  = Resolve-Path "$PSScriptRoot\..\.."
$msys  = "C:\msys64"
$bash  = "$msys\usr\bin\bash.exe"
$iscc  = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"

if (-not (Test-Path $bash)) { throw "MSYS2 not found at $msys. Install it: winget install MSYS2.MSYS2" }
if (-not (Test-Path $iscc)) { throw "Inno Setup 6 not found. Install it: winget install JRSoftware.InnoSetup" }

# 1. GTK 4, libadwaita, PyGObject and PyInstaller inside MSYS2's UCRT64 environment
$env:MSYSTEM = "UCRT64"            # login shells then put /ucrt64/bin (python, gtk) first on PATH
$unix = ($root -replace '\\', '/') -replace '^([A-Za-z]):', '/$1'
& $bash -lc "pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-python-gobject mingw-w64-ucrt-x86_64-gtk4 mingw-w64-ucrt-x86_64-libadwaita mingw-w64-ucrt-x86_64-python-pip mingw-w64-ucrt-x86_64-python-cairo"
& $bash -lc "cd '$unix' && python -m pip install --break-system-packages --upgrade pyinstaller pyinstaller-hooks-contrib"

# 2. Freeze the app: dist\Draco\Draco.exe + draco-host.exe
& $bash -lc "cd '$unix' && python -m PyInstaller --noconfirm --distpath dist --workpath build/pyinstaller packaging/windows/draco.spec"

# 3. Bundle yt-dlp and ffmpeg next to Draco.exe (optional but recommended: YouTube, HLS, subtitles)
$tools = "$root\dist\Draco"
if (-not (Test-Path "$tools\yt-dlp.exe")) {
    Invoke-WebRequest "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" -OutFile "$tools\yt-dlp.exe"
}
if (-not (Test-Path "$tools\ffmpeg.exe")) {
    $zip = "$env:TEMP\ffmpeg-release.zip"
    Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip
    Expand-Archive $zip "$env:TEMP\ffmpeg-release" -Force
    Copy-Item (Get-ChildItem "$env:TEMP\ffmpeg-release" -Recurse -Filter ffmpeg.exe | Select-Object -First 1).FullName $tools
}

# 4. Installer: dist\DracoSetup-<version>.exe
& $iscc "$root\packaging\windows\installer.iss"
Write-Host "`nDone: $(Get-ChildItem "$root\dist\DracoSetup-*.exe" | Select-Object -Last 1)"
