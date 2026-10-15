#!/bin/sh
# Build dist/draco_<version>_all.deb   (needs only dpkg-deb, no root)
set -e
SRC=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
VERSION=$(cd "$SRC" && python3 -c "import draco; print(draco.__version__)")
NAME=draco-dm_${VERSION}_all
PKG="$SRC/dist/build/$NAME"
APPID=io.github.draco.DracoDM

rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/usr/lib/draco" "$PKG/usr/bin" "$PKG/usr/share/applications" \
         "$PKG/usr/share/doc/draco"
cp -r "$SRC/draco" "$SRC/native_host" "$SRC/extension" "$PKG/usr/lib/draco/"
find "$PKG" -name __pycache__ -type d -prune -exec rm -rf {} +

cat > "$PKG/usr/bin/draco" <<'LAUNCH'
#!/bin/sh
export DRACO_LAUNCHER=/usr/bin/draco
PYTHONPATH="/usr/lib/draco${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m draco "$@"
LAUNCH
chmod 755 "$PKG/usr/bin/draco" "$PKG/usr/lib/draco/native_host/draco_host.py"

sed "s|^Exec=draco|Exec=/usr/bin/draco|" "$SRC/data/$APPID.desktop" > "$PKG/usr/share/applications/$APPID.desktop"
for s in 16 24 32 48 64 128 256 512; do
    install -Dm644 "$SRC/data/icons/$s.png" "$PKG/usr/share/icons/hicolor/${s}x${s}/apps/$APPID.png"
done
gzip -9n -c "$SRC/README.md" > "$PKG/usr/share/doc/draco/README.md.gz"
cat > "$PKG/usr/share/doc/draco/copyright" <<'COPY'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: draco
Files: *
Copyright: 2026 Md Hafijur Rahman
License: GPL-3.0+
Comment: Icon artwork is based on a photo supplied by the user.
COPY

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
Homepage: https://github.com/draco-dm
Description: fast multi-connection download manager
 Draco speeds up downloads by splitting files across up to 32 connections,
 resumes broken downloads, captures downloads and videos from the browser
 (Chrome, Brave, Edge, Firefox), downloads HLS streams, and runs queues on
 a schedule. Includes a site grabber, batch downloads and a speed limiter.
CTRL

cat > "$PKG/DEBIAN/postrm" <<'POSTRM'
#!/bin/sh
set -e
# Per-user browser registrations live in home folders; they are harmless once the
# app is gone, and are refreshed automatically if Draco is installed again.
exit 0
POSTRM
chmod 755 "$PKG/DEBIAN/postrm"

mkdir -p "$SRC/dist"
dpkg-deb --root-owner-group -Zxz --build "$PKG" "$SRC/dist/$NAME.deb"
rm -rf "$SRC/dist/build"
echo "Built $SRC/dist/$NAME.deb"
