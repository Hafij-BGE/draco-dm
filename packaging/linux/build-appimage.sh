#!/bin/sh
# Build dist/Draco-<version>-x86_64.AppImage: one portable file with Draco, yt-dlp and a static ffmpeg.
# It uses the system's Python 3 + GTK 4 + libadwaita (standard on GNOME/Ubuntu 23.10+/Fedora 39+);
# if they're missing it says how to install them. Downloads tools into build-cache/ the first time.
set -e
SRC=$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)
VERSION=$(cd "$SRC" && python3 -c "import draco; print(draco.__version__)")
APPID=io.github.draco.DracoDM
CACHE="$SRC/build-cache"
APPDIR="$SRC/dist/build/Draco.AppDir"
sh "$SRC/packaging/linux/fetch-tools.sh"

rm -rf "$APPDIR"
sh "$SRC/packaging/linux/stage.sh" "$APPDIR" /usr
install -m755 "$CACHE/yt-dlp" "$APPDIR/usr/bin/yt-dlp"
install -m755 "$CACHE/ffmpeg" "$APPDIR/usr/bin/ffmpeg"

cp "$APPDIR/usr/share/applications/$APPID.desktop" "$APPDIR/$APPID.desktop"
sed -i "s|^Exec=.*|Exec=draco %U|" "$APPDIR/$APPID.desktop"
cp "$SRC/data/icons/256.png" "$APPDIR/$APPID.png"
ln -sf "$APPID.png" "$APPDIR/.DirIcon"

cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE=$(dirname "$(readlink -f "$0")")
export PATH="$HERE/usr/bin:$PATH"                    # bundled yt-dlp + ffmpeg
export DRACO_LAUNCHER="${APPIMAGE:-$HERE/AppRun}"     # browser helper / autostart start this file
if ! python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1"); from gi.repository import Adw' 2>/dev/null; then
    msg="Draco needs Python 3 with GTK 4 and libadwaita.

Ubuntu / Debian:  sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
Fedora:           sudo dnf install python3-gobject gtk4 libadwaita
Arch / Manjaro:   sudo pacman -S python-gobject gtk4 libadwaita
openSUSE:         sudo zypper install python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1

Or use the Flatpak version of Draco, which needs nothing extra."
    echo "$msg" >&2
    { command -v zenity >/dev/null && zenity --error --title="Draco Download Manager" --text="$msg"; } ||
    { command -v kdialog >/dev/null && kdialog --error "$msg"; } ||
    { command -v notify-send >/dev/null && notify-send "Draco Download Manager" "$msg"; } || true
    exit 1
fi
exec python3 "$HERE/usr/lib/draco/draco_launch.py" "$@"
RUN
chmod 755 "$APPDIR/AppRun"

OUT="$SRC/dist/Draco-$VERSION-x86_64.AppImage"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$CACHE/appimagetool" --no-appstream "$APPDIR" "$OUT" >/dev/null 2>&1 ||
    ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$CACHE/appimagetool" --no-appstream "$APPDIR" "$OUT"
rm -rf "$SRC/dist/build"
echo "$OUT"
