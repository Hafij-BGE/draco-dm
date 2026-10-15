#!/bin/sh
# Build dist/draco-dm-<version>-1.noarch.rpm   (needs rpmbuild: Fedora "rpm-build", Ubuntu "rpm")
set -e
SRC=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
VERSION=$(cd "$SRC" && python3 -c "import draco; print(draco.__version__)")
TOP="$SRC/dist/build/rpm"
rm -rf "$TOP"
mkdir -p "$TOP"
rpmbuild -bb --quiet \
    --define "_topdir $TOP" --define "draco_version $VERSION" --define "draco_src $SRC" \
    --define "dist %{nil}" --define "_build_id_links none" \
    "$SRC/packaging/linux/draco-dm.spec"
mkdir -p "$SRC/dist"
cp "$TOP"/RPMS/noarch/draco-dm-"$VERSION"-1.noarch.rpm "$SRC/dist/"
rm -rf "$SRC/dist/build"
echo "$SRC/dist/draco-dm-$VERSION-1.noarch.rpm"
