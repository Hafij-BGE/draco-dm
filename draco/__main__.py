"""Command line entry point.

    draco                      open the window (or bring the running one forward)
    draco URL [URL...]         download URL(s); hands them to the running instance if there is one
    draco --background         start without showing the window (used by the browser + autostart)
    draco --install-browser    register the browser native-messaging host and unpack the extension
    draco --uninstall-browser
    draco --status
"""

import argparse
import os
import sys
from pathlib import Path

from . import __version__, ipc


def _launch_cmd():
    """How to start Draco again (for the browser helper and start-at-login), as an argument list."""
    from . import osdeps
    exe = os.environ.get("DRACO_LAUNCHER")
    if exe:
        return [exe]
    if osdeps.IS_WIN:
        if osdeps.FROZEN:
            return [sys.executable]                     # ...\Draco\Draco.exe
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        return [str(pythonw if pythonw.exists() else sys.executable),
                str(Path(__file__).resolve().parent.parent / "bin" / "draco-app.pyw")]
    local = Path.home() / ".local/bin/draco"
    if local.exists():
        return [str(local)]
    return [str(Path(__file__).resolve().parent.parent / "bin" / "draco")]


def _selftest():
    """Check that a (frozen) install can load everything it needs. Prints a report, exit code 0 = OK."""
    import traceback
    from . import osdeps
    ok = True

    def check(name, fn):
        nonlocal ok
        try:
            detail = fn()
            print(f"  ok    {name}" + (f": {detail}" if detail else ""))
        except Exception:
            ok = False
            print(f"  FAIL  {name}")
            traceback.print_exc()

    print(f"Draco {__version__} selftest (frozen={osdeps.FROZEN}, app_dir={osdeps.app_dir()})")
    base = Path(__file__).resolve().parent.parent
    check("icons", lambda: f"{len(list((base / 'draco' / 'icons').glob('*.svg')))} svg")
    check("extension files", lambda: (base / "extension" / "chrome" / "manifest.json").stat().st_size and "present")
    check("native host script", lambda: (base / "native_host" / "draco_host.py").stat().st_size and "present")
    check("folders", lambda: f"config={osdeps.config_dir()} downloads={osdeps.downloads_dir()}")

    def gtk():
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        gi.require_version("Graphene", "1.0")
        from gi.repository import Adw, Gtk
        return f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}, " \
               f"libadwaita {Adw.get_major_version()}.{Adw.get_minor_version()}, display={Gtk.init_check()}"
    check("GTK 4 + libadwaita", gtk)
    check("themes", lambda: (__import__("draco.gui.style", fromlist=["x"]).css_for("retro") and "css ok"))
    check("GUI modules", lambda: __import__("draco.gui.app", fromlist=["x"]) and "import ok")
    check("yt-dlp", lambda: osdeps.which("yt-dlp") or "not found (optional)")
    check("ffmpeg", lambda: osdeps.which("ffmpeg") or "not found (optional)")
    print("SELFTEST OK" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="draco", description="Draco Download Manager")
    ap.add_argument("urls", nargs="*", help="addresses to download")
    ap.add_argument("--background", action="store_true", help="start hidden")
    ap.add_argument("--referer", default="")
    ap.add_argument("--now", action="store_true", help="start without the file info dialog")
    ap.add_argument("--install-browser", action="store_true")
    ap.add_argument("--uninstall-browser", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--version", action="version", version=f"draco {__version__}")
    ap.add_argument("--selftest", action="store_true", help="check the installation and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if args.install_browser:
        from . import native
        src = Path(__file__).resolve().parent.parent
        ext = native.install_extension_files(src / "extension")
        done = native.install(_launch_cmd(), src / "native_host" / "draco_host.py")
        print("Native host registered in:\n  " + ("\n  ".join(done) if done else "(no browser profiles found)"))
        print(f"\nExtension unpacked to {ext}")
        print(native.integration_status().split("\n", 2)[-1])
        return 0
    if args.uninstall_browser:
        from . import native
        for p in native.uninstall():
            print("removed", p)
        return 0

    msgs = [{"cmd": "add", "url": u, "referer": args.referer, "silent": args.now} for u in args.urls]
    if ipc.ping():
        if args.status:
            print(ipc.send({"cmd": "status"}))
            return 0
        for m in msgs:
            ipc.send(m)
        if not msgs and not args.background:
            ipc.send({"cmd": "show"})
        return 0
    if args.status:
        print("Draco is not running")
        return 1

    # Wayland/X11 match windows to the .desktop file (and its icon) by this name.
    from gi.repository import GLib
    from . import APP_ID, APP_NAME
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(APP_NAME)
    from .gui.app import DracoApp
    app = DracoApp(start_hidden=args.background, initial=msgs)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
