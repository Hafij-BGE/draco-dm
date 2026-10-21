#!/bin/sh
# Download the helper tools bundled into the AppImage and Flatpak (once) into build-cache/.
set -e
SRC=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
CACHE="$SRC/build-cache"
mkdir -p "$CACHE"
fetch() { [ -s "$CACHE/$2" ] || curl -fsSL --retry 3 -o "$CACHE/$2" "$1"; }
fetch https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage appimagetool
fetch https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp yt-dlp
chmod +x "$CACHE/appimagetool" "$CACHE/yt-dlp"
# Static ffmpeg: johnvansickle.com first, the GitHub-hosted BtbN build when that site is down.
if [ ! -s "$CACHE/ffmpeg" ]; then
    TMP=$(mktemp -d)
    if curl -fsSL --connect-timeout 20 --max-time 600 --retry 2 -o "$TMP/f.tar.xz" \
            https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz; then
        tar -xJf "$TMP/f.tar.xz" -C "$TMP" --wildcards '*/ffmpeg'
    else
        echo "johnvansickle.com unreachable; using the BtbN ffmpeg build from GitHub"
        curl -fsSL --retry 3 -o "$TMP/f.tar.xz" \
            https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
        tar -xJf "$TMP/f.tar.xz" -C "$TMP" --wildcards '*/bin/ffmpeg'
    fi
    find "$TMP" -type f -name ffmpeg -exec mv {} "$CACHE/ffmpeg" \;
    chmod +x "$CACHE/ffmpeg"
    rm -rf "$TMP"
fi
