#!/bin/sh
# Download the helper tools bundled into the AppImage and Flatpak (once) into build-cache/.
set -e
SRC=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
CACHE="$SRC/build-cache"
mkdir -p "$CACHE"
fetch() { [ -s "$CACHE/$2" ] || curl -fsSL --retry 3 -o "$CACHE/$2" "$1"; }
fetch https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage appimagetool
fetch https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp yt-dlp
fetch https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz ffmpeg-static.tar.xz
chmod +x "$CACHE/appimagetool" "$CACHE/yt-dlp"
if [ ! -s "$CACHE/ffmpeg" ]; then
    tar -xJf "$CACHE/ffmpeg-static.tar.xz" -C "$CACHE" --wildcards '*/ffmpeg'
    mv "$CACHE"/ffmpeg-*-static/ffmpeg "$CACHE/ffmpeg"
    rm -rf "$CACHE"/ffmpeg-*-static
fi
