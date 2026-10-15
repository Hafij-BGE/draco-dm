#!/bin/sh
# Build dist/draco-dm-<version>-1-any.pkg.tar.zst on Arch Linux (makepkg, run as a normal user).
set -e
SRC=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
VERSION=$(cd "$SRC" && python3 -c "import draco; print(draco.__version__)")
WORK="$SRC/dist/build/arch"
rm -rf "$WORK"
mkdir -p "$WORK"
sed "s/^pkgver=.*/pkgver=$VERSION/" "$SRC/packaging/linux/arch/PKGBUILD" > "$WORK/PKGBUILD"
cd "$WORK"
DRACO_SRC="$SRC" PKGDEST="$SRC/dist" makepkg --nodeps --force --noconfirm >/dev/null
rm -rf "$SRC/dist/build"
ls "$SRC"/dist/draco-dm-"$VERSION"-1-any.pkg.tar.zst
