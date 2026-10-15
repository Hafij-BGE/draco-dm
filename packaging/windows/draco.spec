# PyInstaller spec for Draco on Windows 11 (run from an MSYS2 UCRT64 shell, see BUILD-WINDOWS.md)
#   pyinstaller --noconfirm packaging/windows/draco.spec
# Produces dist/Draco/ containing Draco.exe (the app) and draco-host.exe (the browser helper).

import os
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent.parent      # noqa: F821  (SPECPATH is set by PyInstaller)

# Bundle only what Draco uses from GTK: GTK 4 + libadwaita, the Adwaita icon/theme, English.
GI_CONFIG = {"gi": {"module-versions": {"Gtk": "4.0", "Gdk": "4.0", "Adw": "1"},
                    "icons": ["Adwaita", "hicolor"], "themes": ["Adwaita"], "languages": ["en_US"]}}

datas = [
    (str(ROOT / "draco" / "icons"), "draco/icons"),          # toolbar/category icons + app icon
    (str(ROOT / "extension"), "extension"),                   # browser extension, copied out on first run
    (str(ROOT / "native_host"), "native_host"),
]

app = Analysis(  # noqa: F821
    [str(ROOT / "bin" / "draco-app.pyw")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=["gi.repository.Adw", "gi.repository.Gtk", "gi.repository.Gdk", "gi.repository.Graphene",
                   "gi.repository.GdkPixbuf", "gi.repository.Pango", "winreg", "winsound"],
    hooksconfig=GI_CONFIG,
    excludes=["tkinter", "unittest", "pydoc"],
)
host = Analysis(  # noqa: F821
    [str(ROOT / "native_host" / "draco_host.py")],
    pathex=[str(ROOT)],
    excludes=["tkinter", "unittest", "gi"],
)

app_exe = EXE(  # noqa: F821
    PYZ(app.pure),  # noqa: F821
    app.scripts, [], exclude_binaries=True,
    name="Draco", icon=str(ROOT / "data" / "draco.ico"),
    # GUI app: no console window. DRACO_CONSOLE=1 builds a console variant used by CI for --selftest,
    # so errors are printed instead of shown in a dialog nobody can click.
    console=os.environ.get("DRACO_CONSOLE") == "1",
    version=None,
)
host_exe = EXE(  # noqa: F821
    PYZ(host.pure),  # noqa: F821
    host.scripts, [], exclude_binaries=True,
    name="draco-host", icon=str(ROOT / "data" / "draco.ico"),
    console=True,                  # browsers talk to it over stdin/stdout
)

COLLECT(  # noqa: F821
    app_exe, app.binaries, app.datas,
    host_exe, host.binaries, host.datas,
    name="Draco",
)
