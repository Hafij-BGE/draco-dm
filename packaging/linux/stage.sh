#!/bin/sh
# Lay out Draco's files under ROOT/PREFIX. Shared by every Linux package format.
#   stage.sh ROOT [PREFIX]        PREFIX defaults to /usr (Flatpak uses /app)
set -e
ROOT=$1
PREFIX=${2:-/usr}
[ -n "$ROOT" ] || { echo "usage: stage.sh ROOT [PREFIX]" >&2; exit 2; }
SRC=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
APPID=io.github.draco.DracoDM
D="$ROOT$PREFIX"

mkdir -p "$D/lib/draco" "$D/bin" "$D/share/applications" "$D/share/metainfo" "$D/share/doc/draco-dm" \
         "$D/share/licenses/draco-dm"
cp -r "$SRC/draco" "$SRC/native_host" "$SRC/extension" "$D/lib/draco/"
find "$D/lib/draco" -name __pycache__ -type d -prune -exec rm -rf {} +

# Run a script (not "python3 -m draco"): a script's own folder comes first on sys.path, so a
# "draco" folder in the current directory can never shadow the installed app.
cat > "$D/lib/draco/draco_launch.py" <<'PY'
import sys
from draco.__main__ import main
sys.exit(main())
PY
cat > "$D/bin/draco" <<LAUNCH
#!/bin/sh
export DRACO_LAUNCHER="\${DRACO_LAUNCHER:-$PREFIX/bin/draco}"
exec python3 "$PREFIX/lib/draco/draco_launch.py" "\$@"
LAUNCH
chmod 755 "$D/bin/draco" "$D/lib/draco/native_host/draco_host.py"

sed "s|^Exec=draco|Exec=$PREFIX/bin/draco|" "$SRC/data/$APPID.desktop" > "$D/share/applications/$APPID.desktop"
install -m644 "$SRC/data/$APPID.metainfo.xml" "$D/share/metainfo/$APPID.metainfo.xml"
for s in 16 24 32 48 64 128 256 512; do
    install -Dm644 "$SRC/data/icons/$s.png" "$D/share/icons/hicolor/${s}x${s}/apps/$APPID.png"
done
install -m644 "$SRC/README.md" "$D/share/doc/draco-dm/README.md"
install -m644 "$SRC/LICENSE" "$D/share/licenses/draco-dm/LICENSE"
# Third-party notices (ffmpeg is GPL-3.0; source links inside). Also next to the README for
# formats that drop share/licenses (the .deb keeps share/doc).
install -m644 "$SRC/THIRD_PARTY_NOTICES.md" "$D/share/licenses/draco-dm/THIRD_PARTY_NOTICES.md"
install -m644 "$SRC/THIRD_PARTY_NOTICES.md" "$D/share/doc/draco-dm/THIRD_PARTY_NOTICES.md"
