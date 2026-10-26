# Third-party notices

Draco Download Manager is © 2026 Md. Hafijur Rahman and licensed under the
GNU General Public License v3.0 (see `LICENSE`). It uses and, in some packages,
bundles the following third-party software.

## ffmpeg (bundled in the Windows installer, AppImage and Flatpak)

- Project: FFmpeg, <https://ffmpeg.org>. Licence: **GNU General Public License v3.0**
  for the builds bundled with Draco (the full GPL-3.0 text is in `LICENSE` next to this
  file; Windows installs also carry `ffmpeg-LICENSE.txt` from the ffmpeg build).
- Draco runs ffmpeg as a separate program (`ffmpeg` / `ffmpeg.exe`); it is not linked into Draco.
- Where the bundled binaries come from, and where their **source code** is:
  - Linux (AppImage, Flatpak): static builds by John Van Sickle, <https://johnvansickle.com/ffmpeg/>
    (source tarballs are linked from that page), with the BtbN builds as a fallback,
    <https://github.com/BtbN/FFmpeg-Builds> (build scripts and sources at the same address).
  - Windows: "release essentials" builds by gyan.dev, <https://www.gyan.dev/ffmpeg/builds/>
    (source and build information: <https://github.com/GyanD/codexffmpeg>).
  - Upstream source code of every ffmpeg release: <https://ffmpeg.org/download.html>
    and <https://git.ffmpeg.org/ffmpeg.git>.
- The `.deb`, `.rpm` and Arch packages do not bundle ffmpeg; they use the one from your distribution.
- You may also write to the address in `README.md` / the project's GitHub issues page to
  ask for the source code of the ffmpeg build you received.

## yt-dlp (bundled in the Windows installer, AppImage and Flatpak)

- <https://github.com/yt-dlp/yt-dlp>, licence: The Unlicense (public domain).
- Used as a separate program to read media pages on the sites it supports.

## GTK 4, libadwaita, PyGObject, Python

- GTK 4 and libadwaita: LGPL-2.1-or-later, <https://gtk.org>, <https://gnome.pages.gitlab.gnome.org/libadwaita/>.
- PyGObject: LGPL-2.1-or-later, <https://pygobject.gnome.org>.
- Python: PSF License, <https://www.python.org>.
- These come from your distribution (or the GNOME runtime in the Flatpak). The Windows
  installer bundles them, built with MSYS2 (<https://www.msys2.org>), together with
  PyInstaller (GPL-2.0-or-later with the bootloader exception, <https://pyinstaller.org>).

## Disclaimer

Draco is a general-purpose download manager. Users are responsible for complying with the
terms of service and copyright of the content they download. Draco is not affiliated with
any website or with the projects listed above.
