#!/bin/sh
# Build dist/draco-dm_<version>_all.deb   (needs only dpkg-deb, no root)
set -e
SRC=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
VERSION=$(cd "$SRC" && python3 -c "import draco; print(draco.__version__)")
NAME=draco-dm_${VERSION}_all
PKG="$SRC/dist/build/$NAME"

rm -rf "$PKG"
sh "$SRC/packaging/linux/stage.sh" "$PKG" /usr
# Debian keeps licence text in the copyright file, and compresses docs.
rm -rf "$PKG/usr/share/licenses"
gzip -9n "$PKG/usr/share/doc/draco-dm/README.md"
cat > "$PKG/usr/share/doc/draco-dm/copyright" <<'COPY'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: draco-dm
Source: https://github.com/Hafij-BGE/draco-dm
Files: *
Copyright: 2026 Md Hafijur Rahman
License: GPL-3.0+
COPY

mkdir -p "$PKG/DEBIAN"
SIZE=$(du -sk "$PKG/usr" | cut -f1)
cat > "$PKG/DEBIAN/control" <<CTRL
Package: draco-dm
Version: $VERSION
Section: net
Priority: optional
Architecture: all
Installed-Size: $SIZE
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1
Recommends: ffmpeg, yt-dlp
Suggests: clamav
Maintainer: Md Hafijur Rahman <draco@localhost>
Homepage: https://github.com/Hafij-BGE/draco-dm
Description: fast multi-connection download manager
 Draco speeds up downloads by splitting files across up to 32 connections,
 resumes broken downloads, captures downloads and videos from the browser
 (Chrome, Brave, Edge, Firefox), downloads HLS streams, and runs queues on
 a schedule. Includes a site grabber, batch downloads and a speed limiter.
CTRL

mkdir -p "$SRC/dist"
dpkg-deb --root-owner-group -Zxz --build "$PKG" "$SRC/dist/$NAME.deb" >/dev/null
rm -rf "$SRC/dist/build"
echo "$SRC/dist/$NAME.deb"
