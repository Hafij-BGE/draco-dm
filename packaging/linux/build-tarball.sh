#!/bin/sh
# Build dist/draco-dm-<version>-linux.tar.gz: the app plus install.sh, for any distro.
# Unpack, then run ./install.sh (per-user, no root). Needs Python 3 + GTK 4 + libadwaita from the distro.
set -e
SRC=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
VERSION=$(cd "$SRC" && python3 -c "import draco; print(draco.__version__)")
NAME=draco-dm-$VERSION
OUT="$SRC/dist/build/$NAME"
rm -rf "$OUT"
mkdir -p "$OUT"
cp -r "$SRC/draco" "$SRC/native_host" "$SRC/extension" "$SRC/bin" "$SRC/data" \
      "$SRC/install.sh" "$SRC/README.md" "$SRC/LICENSE" "$SRC/THIRD_PARTY_NOTICES.md" "$OUT/"
rm -f "$OUT/data/galaxy-photo.png" "$OUT/data/draco-source.png" "$OUT/bin/draco-app.pyw"
find "$OUT" -name __pycache__ -type d -prune -exec rm -rf {} +
mkdir -p "$SRC/dist"
tar -C "$SRC/dist/build" --owner=0 --group=0 -czf "$SRC/dist/$NAME-linux.tar.gz" "$NAME"
rm -rf "$SRC/dist/build"
echo "$SRC/dist/$NAME-linux.tar.gz"
