"""Install native-messaging host manifests for Chromium-family browsers and Firefox."""

import json
import os
import shutil
from pathlib import Path

from . import osdeps
from .config import DATA_DIR

HOST_NAME = "io.github.draco"
CHROME_EXTENSION_ID = "majhnibnfcmhjemhkkddkojdbpedmmep"
FIREFOX_EXTENSION_ID = "draco@draco.github.io"

HOME = Path.home()
CHROMIUM_DIRS = [
    ".config/google-chrome", ".config/google-chrome-beta", ".config/google-chrome-unstable",
    ".config/chromium", ".config/BraveSoftware/Brave-Browser", ".config/BraveSoftware/Brave-Browser-Beta",
    ".config/microsoft-edge", ".config/microsoft-edge-beta", ".config/microsoft-edge-dev",
    ".config/vivaldi", ".config/opera", ".config/yandex-browser",
    "snap/chromium/common/chromium",
    ".var/app/com.google.Chrome/config/google-chrome", ".var/app/org.chromium.Chromium/config/chromium",
    ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser",
    ".var/app/com.microsoft.Edge/config/microsoft-edge",
]
FIREFOX_DIRS = [".mozilla", "snap/firefox/common/.mozilla", ".var/app/org.mozilla.firefox/.mozilla",
                ".librewolf", ".waterfox"]


def host_script_path():
    return DATA_DIR / "draco_host.py"


# Windows: browsers find native hosts through these registry keys (per user, no admin needed).
WIN_CHROMIUM_KEYS = [r"Software\Google\Chrome\NativeMessagingHosts", r"Software\Chromium\NativeMessagingHosts",
                     r"Software\Microsoft\Edge\NativeMessagingHosts",
                     r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts"]
WIN_FIREFOX_KEY = r"Software\Mozilla\NativeMessagingHosts"


def _launch_list(launch_cmd):
    if isinstance(launch_cmd, (list, tuple)):
        return list(launch_cmd)
    import shlex
    return shlex.split(launch_cmd)


def _windows_host_program(launch, source_host):
    """The program a Windows browser starts: draco-host.exe in a built app, else a .bat wrapper."""
    if osdeps.FROZEN:
        return osdeps.app_dir() / "draco-host.exe"
    script = host_script_path()
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(Path(source_host).read_text().replace("@LAUNCH@", json.dumps(launch)))
    bat = DATA_DIR / "draco_host.bat"
    import sys
    bat.write_text(f'@echo off\r\n"{sys.executable}" -u "{script}" %*\r\n')
    return bat


def install(launch_cmd, source_host=None):
    """Install the host program and register it with every browser found. Returns where."""
    launch = _launch_list(launch_cmd)
    source_host = Path(source_host or Path(__file__).resolve().parent.parent / "native_host" / "draco_host.py")
    done = []
    if osdeps.IS_WIN:
        import winreg
        program = _windows_host_program(launch, source_host)
        base = {"name": HOST_NAME, "description": "Draco Download Manager", "path": str(program), "type": "stdio"}
        chrome_manifest = DATA_DIR / f"{HOST_NAME}.chrome.json"
        firefox_manifest = DATA_DIR / f"{HOST_NAME}.firefox.json"
        chrome_manifest.write_text(json.dumps(dict(base, allowed_origins=[f"chrome-extension://{CHROME_EXTENSION_ID}/"]), indent=2))
        firefox_manifest.write_text(json.dumps(dict(base, allowed_extensions=[FIREFOX_EXTENSION_ID]), indent=2))
        for key, manifest in [(k, chrome_manifest) for k in WIN_CHROMIUM_KEYS] + [(WIN_FIREFOX_KEY, firefox_manifest)]:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{key}\\{HOST_NAME}") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, str(manifest))
            done.append("HKCU\\" + key)
        return done
    dest = host_script_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(source_host.read_text().replace("@LAUNCH@", json.dumps(launch)))
    dest.chmod(0o755)
    base = {"name": HOST_NAME, "description": "Draco Download Manager", "path": str(dest), "type": "stdio"}
    for d in CHROMIUM_DIRS:
        root = HOME / d
        if root.is_dir():
            target = root / "NativeMessagingHosts" / f"{HOST_NAME}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(dict(base, allowed_origins=[f"chrome-extension://{CHROME_EXTENSION_ID}/"]), indent=2))
            done.append(str(target))
    for d in FIREFOX_DIRS:
        root = HOME / d
        if root.is_dir():
            target = root / "native-messaging-hosts" / f"{HOST_NAME}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(dict(base, allowed_extensions=[FIREFOX_EXTENSION_ID]), indent=2))
            done.append(str(target))
    return done


def uninstall():
    removed = []
    if osdeps.IS_WIN:
        import winreg
        for key in WIN_CHROMIUM_KEYS + [WIN_FIREFOX_KEY]:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{key}\\{HOST_NAME}")
                removed.append("HKCU\\" + key)
            except OSError:
                pass
        return removed
    for d in CHROMIUM_DIRS:
        p = HOME / d / "NativeMessagingHosts" / f"{HOST_NAME}.json"
        if p.exists():
            p.unlink()
            removed.append(str(p))
    for d in FIREFOX_DIRS:
        p = HOME / d / "native-messaging-hosts" / f"{HOST_NAME}.json"
        if p.exists():
            p.unlink()
            removed.append(str(p))
    if host_script_path().exists():
        host_script_path().unlink()
    return removed


def _windows_registered():
    import winreg
    found = []
    for key in WIN_CHROMIUM_KEYS + [WIN_FIREFOX_KEY]:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{key}\\{HOST_NAME}"):
                found.append(key.split("\\")[-2])
        except OSError:
            pass
    return found


def integration_status():
    found = _windows_registered() if osdeps.IS_WIN else []
    for d in ([] if osdeps.IS_WIN else CHROMIUM_DIRS):
        if (HOME / d / "NativeMessagingHosts" / f"{HOST_NAME}.json").exists():
            found.append(d.split("/")[-1])
    for d in ([] if osdeps.IS_WIN else FIREFOX_DIRS):
        if (HOME / d / "native-messaging-hosts" / f"{HOST_NAME}.json").exists():
            found.append("Firefox" if "mozilla" in d else d)
    ext_dir = DATA_DIR / "extension"
    lines = []
    if found:
        lines.append("Native host registered for: " + ", ".join(found) + ".")
    else:
        lines.append("Native host not registered yet. Run:  draco --install-browser")
    vis = visible_extension_dir()
    lines.append("")
    lines.append("Load the extension once (folder: " + str(vis) + "):")
    lines.append("• Brave / Chrome / Opera / Edge: open the browser's extensions page (brave://extensions, "
                 "opera://extensions …), turn on Developer mode, click “Load unpacked” and choose the "
                 "“chrome” folder.")
    lines.append("• Firefox: about:debugging → This Firefox → “Load Temporary Add-on” → firefox/manifest.json")
    lines.append("")
    lines.append("Snap or Flatpak browsers: click the Draco button in the browser toolbar, then "
                 "“Connect to Draco”, and press Allow here.")
    return "\n".join(lines)


def install_extension_files(src_dir):
    """Copy the extension into the data dir and build the Firefox variant."""
    src = Path(src_dir)
    out = DATA_DIR / "extension"
    if out.exists():
        shutil.rmtree(out)
    chrome = out / "chrome"
    shutil.copytree(src / "chrome", chrome)
    firefox = out / "firefox"
    shutil.copytree(src / "chrome", firefox)
    man = json.loads((firefox / "manifest.json").read_text())
    man.pop("key", None)
    bg = man.pop("background")
    man["background"] = {"scripts": [bg["service_worker"]]}
    man["browser_specific_settings"] = {"gecko": {"id": FIREFOX_EXTENSION_ID, "strict_min_version": "115.0"}}
    (firefox / "manifest.json").write_text(json.dumps(man, indent=2))
    # Snap/Flatpak browsers can't open hidden folders in their file picker: keep a visible copy.
    visible = visible_extension_dir()
    try:
        if visible.exists():
            shutil.rmtree(visible)
        shutil.copytree(out, visible)
        (visible / "README.txt").write_text(
            "Draco browser extension.\n\n"
            "Brave / Chrome / Opera / Edge: open the extensions page, turn on Developer mode,\n"
            "click 'Load unpacked' and choose the 'chrome' folder here.\n"
            "Firefox: about:debugging -> This Firefox -> Load Temporary Add-on -> firefox/manifest.json\n")
    except OSError:
        pass
    return out


def visible_extension_dir():
    return osdeps.documents_dir() / "Draco Browser Extension"


def _digest(folder):
    import hashlib
    h = hashlib.sha256()
    try:
        for f in sorted(Path(folder).rglob("*")):
            if f.is_file():
                h.update(f.relative_to(folder).as_posix().encode())
                h.update(f.read_bytes())
    except OSError:
        return None
    return h.hexdigest()


def ensure_registered(launch_cmd, src_root):
    """Register this user's browsers on app start when missing or pointing at another install
    (e.g. right after installing the .deb). Cheap when everything is already in place."""
    src_root = Path(src_root)
    if osdeps.IS_WIN:
        needed = len(_windows_registered()) < len(WIN_CHROMIUM_KEYS) + 1
    else:
        host = host_script_path()
        needed = not host.exists() or json.dumps(_launch_list(launch_cmd)) not in host.read_text()
    if not needed and not osdeps.IS_WIN:
        for d in CHROMIUM_DIRS:
            if (HOME / d).is_dir() and not (HOME / d / "NativeMessagingHosts" / f"{HOST_NAME}.json").exists():
                needed = True
        for d in FIREFOX_DIRS:
            if (HOME / d).is_dir() and not (HOME / d / "native-messaging-hosts" / f"{HOST_NAME}.json").exists():
                needed = True
    same = _digest(DATA_DIR / "extension" / "chrome") == _digest(src_root / "extension" / "chrome")
    if not same or \
            not (visible_extension_dir() / "chrome" / "manifest.json").exists():
        needed = True
    if needed:
        install_extension_files(src_root / "extension")
        install(launch_cmd, src_root / "native_host" / "draco_host.py")
    return needed


def autostart_enabled():
    return osdeps.autostart_enabled()


def set_autostart(on, launch_cmd):
    """Start Draco hidden at login (so sandboxed browsers can always reach it)."""
    launch = _launch_list(launch_cmd)
    if osdeps.IS_WIN:
        import subprocess
        line = subprocess.list2cmdline(launch)
    else:
        import shlex
        line = shlex.join(launch)
    osdeps.set_autostart(on, line)
