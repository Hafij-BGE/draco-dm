#!/bin/sh
# Install Draco Download Manager for the current user (no root needed).
#   ./install.sh               install / update
#   ./install.sh --autostart   also start Draco hidden at login (for scheduled queues)
#   ./install.sh --uninstall   remove everything except your settings and download list
set -e
SRC=$(dirname "$(readlink -f "$0")")
APPDIR="$HOME/.local/share/draco/app"
BIN="$HOME/.local/bin/draco"
DESKTOP="$HOME/.local/share/applications/io.github.draco.DracoDM.desktop"
ICONS="$HOME/.local/share/icons/hicolor"
ICON_NAME="io.github.draco.DracoDM.png"
AUTOSTART="$HOME/.config/autostart/io.github.draco.DracoDM.desktop"

if [ "$1" = "--uninstall" ]; then
    pkill -f "^python3 -m draco( |$)" 2>/dev/null || true
    [ -x "$BIN" ] && "$BIN" --uninstall-browser || true
    rm -rf "$APPDIR" "$HOME/.local/share/draco/extension"
    rm -f "$BIN" "$DESKTOP" "$AUTOSTART"
    for s in 16 24 32 48 64 128 256 512; do rm -f "$ICONS/${s}x${s}/apps/$ICON_NAME"; done
    gtk-update-icon-cache -q -f -t "$ICONS" 2>/dev/null || rm -f "$ICONS/icon-theme.cache"
    echo "Draco removed. Settings: ~/.config/draco  Download list: ~/.local/share/draco"
    exit 0
fi

# Remove the previous "Hawk" install. Its settings and download list are migrated on first start.
if [ -e "$HOME/.local/bin/hawkdm" ] || [ -d "$HOME/.local/share/hawkdm/app" ]; then
    pkill -f "^python3 -m hawkdm( |$)" 2>/dev/null || true
    rm -rf "$HOME/.local/share/hawkdm/app" "$HOME/.local/share/hawkdm/extension"
    rm -f "$HOME/.local/bin/hawkdm" "$HOME/.local/share/hawkdm/hawkdm_host.py" \
          "$HOME/.local/share/applications/io.github.hawkdm.HawkDM.desktop" \
          "$HOME/.local/share/icons/hicolor/scalable/apps/io.github.hawkdm.HawkDM.svg" \
          "$HOME/.config/autostart/io.github.hawkdm.HawkDM.desktop"
    for d in "$HOME/.config" "$HOME/.mozilla" "$HOME/snap" "$HOME/.var" "$HOME/.librewolf" "$HOME/.waterfox"; do
        [ -d "$d" ] && find "$d" -maxdepth 7 -name io.github.hawkdm.json -path "*ative*" -delete 2>/dev/null
    done
    gtk-update-icon-cache -q -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || rm -f "$HOME/.local/share/icons/hicolor/icon-theme.cache"
    echo "Removed the old Hawk install."
fi

# Remove the previous "Spectra" install (same app under its old name).
if [ -e "$HOME/.local/bin/spectra" ] || [ -d "$HOME/.local/share/spectra/app" ]; then
    pkill -f "^python3 -m spectra( |$)" 2>/dev/null || true
    rm -rf "$HOME/.local/share/spectra/app" "$HOME/.local/share/spectra/extension"
    rm -f "$HOME/.local/bin/spectra" "$HOME/.local/share/spectra/spectra_host.py" \
          "$HOME/.local/share/applications/io.github.spectra.SpectraDM.desktop" \
          "$HOME/.config/autostart/io.github.spectra.SpectraDM.desktop"
    for s in 16 24 32 48 64 128 256 512; do
        rm -f "$HOME/.local/share/icons/hicolor/${s}x${s}/apps/io.github.spectra.SpectraDM.png"
    done
    for d in "$HOME/.config" "$HOME/.mozilla" "$HOME/snap" "$HOME/.var" "$HOME/.librewolf" "$HOME/.waterfox"; do
        [ -d "$d" ] && find "$d" -maxdepth 7 -name io.github.spectra.json -path "*ative*" -delete 2>/dev/null
    done
    gtk-update-icon-cache -q -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || rm -f "$HOME/.local/share/icons/hicolor/icon-theme.cache"
    echo "Removed the old Spectra install."
fi

python3 -c 'import gi; gi.require_version("Gtk","4.0"); gi.require_version("Adw","1")' 2>/dev/null || {
    echo "Missing GTK4/libadwaita Python bindings. Install them with:"
    echo "  sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1      (Debian/Ubuntu)"
    echo "  sudo dnf install python3-gobject gtk4 libadwaita              (Fedora)"
    echo "  sudo pacman -S python-gobject gtk4 libadwaita                 (Arch)"
    exit 1
}

rm -rf "$APPDIR"
mkdir -p "$APPDIR" "$(dirname "$BIN")" "$(dirname "$DESKTOP")"
cp -r "$SRC/draco" "$SRC/native_host" "$SRC/extension" "$APPDIR/"
find "$APPDIR" -name __pycache__ -type d -exec rm -rf {} +

cat > "$BIN" <<LAUNCH
#!/bin/sh
PYTHONPATH="$APPDIR\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m draco "\$@"
LAUNCH
chmod +x "$BIN"

cp "$SRC/data/io.github.draco.DracoDM.desktop" "$DESKTOP"
sed -i "s|^Exec=draco|Exec=$BIN|" "$DESKTOP"
rm -f "$ICONS/scalable/apps/io.github.draco.DracoDM.svg"
for s in 16 24 32 48 64 128 256 512; do
    mkdir -p "$ICONS/${s}x${s}/apps"
    cp "$SRC/data/icons/$s.png" "$ICONS/${s}x${s}/apps/$ICON_NAME"
done
gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
update-desktop-database -q "$HOME/.local/share/applications" 2>/dev/null || true

if [ "$1" = "--autostart" ]; then
    mkdir -p "$(dirname "$AUTOSTART")"
    sed "s|^Exec=.*|Exec=$BIN --background|" "$DESKTOP" > "$AUTOSTART"
    echo "Autostart enabled."
fi

DRACO_LAUNCHER="$BIN" "$BIN" --install-browser
command -v yt-dlp >/dev/null || printf "\nOptional: install yt-dlp for media pages on supported sites:  pipx install yt-dlp\n"
command -v ffmpeg >/dev/null || printf "Optional: install ffmpeg for encrypted/live streams:  sudo apt install ffmpeg\n"
printf "\nDone. Start Draco from your app menu or run: draco\n"
