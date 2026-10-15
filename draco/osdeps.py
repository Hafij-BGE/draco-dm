"""Small OS differences in one place (Linux and Windows 11)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

IS_WIN = os.name == "nt"
FROZEN = getattr(sys, "frozen", False)          # running from a PyInstaller build


def app_dir():
    """Folder of the installed program (bundled tools such as ffmpeg.exe / yt-dlp.exe live here)."""
    if FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def which(name):
    """Find a helper tool: next to the program first (Windows bundle), then on PATH."""
    if IS_WIN:
        local = app_dir() / f"{name}.exe"
        if local.exists():
            return str(local)
    return shutil.which(name)


def popen_kwargs():
    """Keep console tools (yt-dlp, ffmpeg) from flashing a console window on Windows."""
    if IS_WIN:
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}


# ---------------------------------------------------------------- folders
def _xdg_user_dir(kind, fallback):
    try:
        out = os.popen(f"xdg-user-dir {kind} 2>/dev/null").read().strip()
        if out and out != str(Path.home()):
            return Path(out)
    except OSError:
        pass
    return Path.home() / fallback


def _win_known_folder(guid, fallback):
    """SHGetKnownFolderPath, so a moved Downloads/Documents folder is respected."""
    try:
        import ctypes
        from ctypes import wintypes
        import uuid

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]

        u = uuid.UUID(guid)
        g = GUID(u.time_low, u.time_mid, u.time_hi_version, (wintypes.BYTE * 8).from_buffer_copy(u.bytes[8:]))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)) == 0:
            path = Path(out.value)
            ctypes.windll.ole32.CoTaskMemFree(out)
            return path
    except Exception:
        pass
    return Path.home() / fallback


def downloads_dir():
    if IS_WIN:
        return _win_known_folder("374DE290-123F-4565-9164-39C4925E467B", "Downloads")
    return _xdg_user_dir("DOWNLOAD", "Downloads")


def documents_dir():
    if IS_WIN:
        return _win_known_folder("FDD39AD0-238F-46AF-ADB4-6C85480369C7", "Documents")
    return _xdg_user_dir("DOCUMENTS", "Documents")


def config_dir():
    if IS_WIN:
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming") / "Draco"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "draco"


def data_dir():
    if IS_WIN:
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "Draco"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "draco"


def runtime_dir():
    if IS_WIN:
        return data_dir() / "run"
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/draco-{os.getuid()}")


# ---------------------------------------------------------------- desktop actions
def open_file(path):
    path = str(path)
    if IS_WIN:
        os.startfile(path)  # noqa: S606 - opening the user's own downloaded file is the point
    else:
        from gi.repository import Gio
        Gio.AppInfo.launch_default_for_uri(Path(path).as_uri(), None)


def reveal(path):
    """Open the folder with the file selected."""
    path = Path(path)
    if IS_WIN:
        if path.exists():
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            os.startfile(str(path.parent))  # noqa: S606
        return
    try:
        from gi.repository import Gio, GLib
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync("org.freedesktop.FileManager1", "/org/freedesktop/FileManager1",
                      "org.freedesktop.FileManager1", "ShowItems",
                      GLib.Variant("(ass)", ([path.as_uri()], "")), None,
                      Gio.DBusCallFlags.NONE, 2000, None)
        return
    except Exception:
        pass
    open_file(path.parent)


def play_complete_sound():
    if IS_WIN:
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
        return
    if shutil.which("canberra-gtk-play"):
        subprocess.Popen(["canberra-gtk-play", "-i", "complete", "-d", "Draco Download Manager"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif shutil.which("paplay") and Path("/usr/share/sounds/freedesktop/stereo/complete.oga").exists():
        subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def power_command(action):
    """Command for 'when the queue is done': suspend | hibernate | shutdown."""
    if IS_WIN:
        return {"suspend": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                "hibernate": ["shutdown", "/h"],
                "shutdown": ["shutdown", "/s", "/t", "0"]}.get(action)
    return {"suspend": ["systemctl", "suspend"], "hibernate": ["systemctl", "hibernate"],
            "shutdown": ["systemctl", "poweroff"]}.get(action)


# ---------------------------------------------------------------- start at login
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart" / \
    "io.github.draco.DracoDM.desktop"


def autostart_enabled():
    if IS_WIN:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
                winreg.QueryValueEx(k, "Draco")
                return True
        except OSError:
            return False
    return _AUTOSTART_FILE.exists()


def set_autostart(on, launch_cmd):
    if IS_WIN:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            if on:
                winreg.SetValueEx(k, "Draco", 0, winreg.REG_SZ, f"{launch_cmd} --background")
            else:
                try:
                    winreg.DeleteValue(k, "Draco")
                except OSError:
                    pass
        return
    if on:
        _AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
        _AUTOSTART_FILE.write_text(
            "[Desktop Entry]\nType=Application\nName=Draco Download Manager\n"
            f"Exec={launch_cmd} --background\nIcon=io.github.draco.DracoDM\n"
            "X-GNOME-Autostart-enabled=true\nNoDisplay=true\nTerminal=false\n")
    elif _AUTOSTART_FILE.exists():
        _AUTOSTART_FILE.unlink()
