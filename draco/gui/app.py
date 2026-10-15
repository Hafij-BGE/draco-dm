"""Adw.Application: glue between manager, IPC/browser requests and windows."""

import os
import subprocess
import threading
import urllib.parse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .. import APP_ID, APP_NAME, AUTHOR, __version__  # noqa: E402
from ..config import Settings  # noqa: E402
from ..engine import DownloadError, probe, sanitize_filename  # noqa: E402
from ..ipc import IpcServer  # noqa: E402
from ..manager import Manager  # noqa: E402
from ..media import is_hls  # noqa: E402
from .. import osdeps  # noqa: E402
from . import style, util  # noqa: E402
from .dialogs import (AddUrlDialog, BatchDialog, CompleteDialog, CountdownDialog, FileInfoDialog,  # noqa: E402
                      GrabberDialog, LinkPickerDialog, PropertiesDialog, RefreshAddressDialog)
from .prefs import PrefsDialog  # noqa: E402
from .progress import ProgressWindow  # noqa: E402
from .scheduler import SchedulerDialog  # noqa: E402
from .window import MainWindow  # noqa: E402


class DracoApp(Adw.Application):
    def __init__(self, start_hidden=False, initial=None):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.start_hidden = start_hidden
        self.initial = initial or []
        self.window = None
        self.progress_windows = {}
        self.refresh_target = None
        self._clip_seen = set()
        self._progress_seen = set()

    # ---------------------------------------------------------- lifecycle
    def do_startup(self):
        Adw.Application.do_startup(self)
        self.settings = Settings()
        theme = self.settings.get("theme") or ("classic" if self.settings.get("classic_look", True) else "system")
        theme = style.current_theme(theme)
        if theme != self.settings.get("theme"):
            self.settings["theme"] = theme
            self.settings.save()
        style.setup(theme)
        self.manager = Manager(self.settings)
        self.manager.listeners.append(self._on_event)
        self.ipc = IpcServer(lambda msg: self._dispatch(msg))
        self.ipc.start()
        threading.Thread(target=self._register_browsers, daemon=True).start()
        from ..bridge import Bridge
        from ..native import CHROME_EXTENSION_ID
        self.bridge = Bridge(self.settings, self._dispatch, self._ask_pair, CHROME_EXTENSION_ID, __version__)
        self.bridge.start()
        for name, cb in (("quit", lambda *_: self._quit()), ("about", lambda *_: self._about()),
                         ("show", lambda *_: self.show_main()),
                         ("browser-integration", lambda *_: self._browser_help())):
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", cb)
            self.add_action(a)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("win.add-url", ["<Control>n"])
        self.set_accels_for_action("win.prefs", ["<Control>comma"])
        GLib.timeout_add_seconds(15, self._sched_tick)
        self.hold()  # stay alive while the window is hidden

    def _ask_pair(self, origin):
        """Called on a bridge thread: ask the user (on the main loop) whether to pair a browser."""
        done = threading.Event()
        answer = [False]

        def show():
            self.show_main()
            browser = "Firefox" if origin.startswith("moz-extension://") else "Brave / Chrome / Opera / Edge"
            d = Adw.AlertDialog(
                heading="Connect a browser to Draco?",
                body=f"The Draco extension in {browser} wants to send downloads to Draco.\n\n"
                     "Allow only if you just clicked “Connect to Draco” in the extension.")
            d.add_response("deny", "Don't Allow")
            d.add_response("allow", "Allow")
            d.set_response_appearance("allow", Adw.ResponseAppearance.SUGGESTED)
            d.set_default_response("deny")
            d.set_close_response("deny")
            from .. import native
            auto = Gtk.CheckButton(label="Start Draco automatically at login (so the browser can always reach it)",
                                   active=True)
            if native.autostart_enabled():
                auto.set_visible(False)
            d.set_extra_child(auto)

            def resp(dlg, r):
                answer[0] = r == "allow"
                if answer[0] and auto.get_visible() and auto.get_active():
                    from ..__main__ import _launch_cmd
                    native.set_autostart(True, _launch_cmd())
                done.set()

            d.connect("response", resp)
            d.present(self.window)
            return False

        GLib.idle_add(show)
        done.wait(120)
        return answer[0]

    def set_theme(self, key):
        style.apply_theme(key)
        self.settings["theme"] = key
        self.settings.save()
        if self.window:
            a = self.window.lookup_action("theme")
            if a and a.get_state().get_string() != key:
                a.set_state(GLib.Variant.new_string(key))
            self.window.apply_icons()

    def _register_browsers(self):
        from pathlib import Path
        from .. import native
        from ..__main__ import _launch_cmd
        try:
            native.ensure_registered(_launch_cmd(), Path(__file__).resolve().parent.parent.parent)
        except OSError as e:
            print("browser registration failed:", e)

    def do_activate(self):
        if not self.window:
            self.window = MainWindow(self)
            self._setup_clipboard()
            self.window.connect("notify::is-active",
                                lambda w, _p: w.is_active() and self.clear_notifications())
            GLib.idle_add(self._clear_old_notifications)
        if not self.start_hidden:
            self.window.present()
        self.start_hidden = False
        for msg in self.initial:
            self._dispatch_main(msg)
        self.initial = []

    def do_shutdown(self):
        self.bridge.stop()
        self.manager.shutdown()
        self.ipc.stop()
        Adw.Application.do_shutdown(self)

    def _quit(self):
        if getattr(self, "_quitting", False):
            return
        self._quitting = True
        for w in list(self.get_windows()):
            w.destroy()
        self.release()
        self.quit()

    def show_main(self):
        if not self.window:
            self.activate()
        self.window.set_visible(True)
        self.window.present()

    # ---------------------------------------------------------- IPC
    def _dispatch(self, msg):
        """Runs on an IPC thread. Hand work to the main loop and answer quickly."""
        cmd = msg.get("cmd")
        if cmd == "ping":
            return {"ok": True, "version": __version__}
        if cmd == "status":
            return {"ok": True, "items": len(self.manager.items), "active": len(self.manager.tasks)}
        if cmd == "add" and msg.get("verify"):
            # A capture from the browser: check now (on this IPC thread) that Draco can really fetch
            # the link. If the server refuses a second request (POST forms, one-time links such as
            # Google Drive), say no so the browser simply carries on with its own download.
            verdict = self._verify_capture(msg)
            if not verdict.get("ok"):
                return verdict
        GLib.idle_add(self._dispatch_main, msg)
        return {"ok": True}

    def _verify_capture(self, msg):
        url = (msg.get("url") or "").strip()
        if not util.looks_like_url(url) or is_hls(url):
            return {"ok": True}
        item = {"url": url, "referer": msg.get("referer", ""), "cookies": msg.get("cookies", ""),
                "user_agent": msg.get("user_agent", ""), "headers": msg.get("headers") or {}}
        real = self.settings

        class _Quick:            # the user's settings, but give up after 8 s (the browser is waiting)
            def __getitem__(self, k):
                return 8 if k == "timeout" else real[k]

            def login_for(self, u):
                return real.login_for(u)

        try:
            info = probe(item, _Quick())
        except DownloadError as e:
            return {"ok": False, "error": f"Draco cannot fetch this link ({e}); left to the browser"}
        if 0 <= info["size"] < 1024 and (info["content_type"] or "").startswith("text/html"):
            return {"ok": False, "error": "The link returns a web page, not the file; left to the browser"}
        msg["_probe"] = info
        return {"ok": True}

    def _dispatch_main(self, msg):
        cmd = msg.get("cmd")
        if cmd == "show":
            self.show_main()
        elif cmd == "add":
            self.request_download(msg)
        elif cmd == "links":
            self.show_links(msg.get("urls", []), msg.get("title") or "Download links",
                            referer=msg.get("referer", ""), cookies=msg.get("cookies", ""),
                            user_agent=msg.get("user_agent", ""))
        elif cmd == "grab":
            self.show_grabber(msg.get("url", ""))
        return False

    # ---------------------------------------------------------- downloads
    def request_download(self, req):
        """Entry point for new downloads from any source (dialog, browser, clipboard, CLI)."""
        url = (req.get("url") or "").strip()
        if not util.looks_like_url(url):
            return
        if self.refresh_target and self.refresh_target in self.manager.items and req.get("source") == "browser":
            target, self.refresh_target = self.refresh_target, None
            self.manager.refresh_address(target, url, referer=req.get("referer"), cookies=req.get("cookies"))
            if self.window:
                self.window.toast("Download address refreshed")
            return
        kind = req.get("kind") if req.get("kind") in ("http", "hls", "ffmpeg", "ytdlp") else None
        if not kind and is_hls(url, req.get("content_type", "")):
            kind = "hls"
        item = self.manager.new_item(url, filename=req.get("filename", ""), referer=req.get("referer", ""),
                                     cookies=req.get("cookies", ""), headers=req.get("headers"),
                                     description=req.get("description", ""), kind=kind,
                                     user_agent=req.get("user_agent", ""))
        for k in ("auth_user", "auth_password"):
            if req.get(k):
                item[k] = req[k]
        if req.get("size"):
            try:
                item["size"] = int(req["size"])
            except (TypeError, ValueError):
                pass
        if item["kind"] == "ytdlp":
            from ..media import YTDLP, valid_quality, ytdlp_info
            item["ytdlp_quality"] = str(req.get("quality")) if valid_quality(req.get("quality")) else "best"
            item["subs"] = bool(req.get("subs"))
            if isinstance(req.get("sub_lang"), str):
                item["sub_lang"] = req["sub_lang"][:3]
            host = urllib.parse.urlparse(url).netloc.removeprefix("www.") or "video"
            if is_hls(url):
                # A raw stream address has no useful title of its own: name it after the page.
                title = sanitize_filename((req.get("description") or req.get("title") or f"{host} video")[:150])
                if not YTDLP:
                    item["kind"] = "hls"
                    item["filename"] = sanitize_filename(title + ".mp4")
                    self._file_info(item, None, req)
                    return
                item["ytdlp_template"] = title.replace("%", "%%") + ".%(ext)s"
                item["filename"] = sanitize_filename(title + (".mp3" if item["ytdlp_quality"] == "audio" else ".mp4"))
                if req.get("silent"):
                    self._file_info(item, None, req)
                    return
            if req.get("silent"):  # quick capture: start now, yt-dlp fills in the title
                ext = {"audio": ".mp3", "subs": ".srt"}.get(item["ytdlp_quality"], ".mp4")
                item["filename"] = sanitize_filename(f"{host} video{ext}")
                self._file_info(item, None, req)
                return

            if self.settings["start_immediately"]:
                item["filename"] = item.get("filename") or sanitize_filename(f"{host} video.mp4")
                self._file_info(item, None, req)
                return
            item["filename"] = item.get("filename") or sanitize_filename(f"{host} video.mp4")
            item["_loading"] = True
            dialog = self._open_file_info(item)

            def yt_worker():
                info, err = None, None
                try:
                    info = ytdlp_info(url, item.get("cookies", ""), item.get("referer", ""))
                except DownloadError as e:
                    err = str(e)
                GLib.idle_add(dialog.set_ytdlp_info, info, err)

            threading.Thread(target=yt_worker, daemon=True).start()
            return
        if item["kind"] != "http":
            self._file_info(item, None, req)
            return
        if req.get("_probe"):   # already checked while the browser was waiting
            info = req["_probe"]
            item.update(size=info["size"], resumable=info["resumable"], probed=True,
                        final_url=info["final_url"], content_type=info["content_type"])
            if not item["filename"]:
                item["filename"] = info["filename"]
            item["category"] = self.settings.category_for(item["filename"])
            item["save_dir"] = str(self.settings.folder_for(item["category"]))
            self._file_info(item, None, req)
            return

        def worker():
            err = None
            try:
                info = probe(item, self.settings)
                item.update(size=info["size"], resumable=info["resumable"], probed=True,
                            final_url=info["final_url"], content_type=info["content_type"])
                if is_hls(info["final_url"], info["content_type"]):
                    item["kind"] = "hls"
                if not item["filename"]:
                    item["filename"] = info["filename"]
                cat = "Video" if item["kind"] == "hls" else self.settings.category_for(item["filename"])
                item["category"] = cat
                item["save_dir"] = str(self.settings.folder_for(cat))
            except DownloadError as e:
                err = str(e)
            GLib.idle_add(self._file_info, item, err, req)

        threading.Thread(target=worker, daemon=True).start()

    def _file_info(self, item, err, req):
        if not item.get("filename"):
            item["filename"] = util_name(item["url"], item.get("kind"))
        if (self.settings["start_immediately"] or req.get("silent")) and not err:
            self.manager.add(item, start=True)
            if self.settings["show_progress_dialog"] and not req.get("silent"):
                self.show_progress(item)
        else:
            self._open_file_info(item, err)
        return False

    def _open_file_info(self, item, err=None):
        """At most one 'Download File Info' window per link: bring the existing one forward."""
        dialogs = getattr(self, "_info_dialogs", None)
        if dialogs is None:
            dialogs = self._info_dialogs = {}
        key = item["url"]
        d = dialogs.get(key)
        if d is not None and d.get_visible():
            d.present()
            return d
        d = FileInfoDialog(self, item, err)
        dialogs[key] = d
        d.connect("close-request", lambda *_: (dialogs.pop(key, None), False)[1])
        return d

    # ---------------------------------------------------------- windows
    def show_add_url(self, url=""):
        AddUrlDialog(self, url)

    def show_progress(self, item):
        self._progress_seen.add(item["id"])
        w = self.progress_windows.get(item["id"])
        if not w:
            w = ProgressWindow(self, item)
            self.progress_windows[item["id"]] = w
        w.present()

    def show_prefs(self):
        PrefsDialog(self).present(self.window)

    def show_scheduler(self):
        SchedulerDialog(self)

    def show_grabber(self, url=""):
        GrabberDialog(self, url)

    def show_batch(self, pattern=""):
        BatchDialog(self, pattern)

    def show_links(self, urls, title, referer="", cookies="", user_agent=""):
        LinkPickerDialog(self, urls, title, referer, cookies, user_agent)

    def show_properties(self, item):
        PropertiesDialog(self, item)

    def show_refresh_address(self, item):
        RefreshAddressDialog(self, item)

    def refresh_sidebar(self):
        if self.window:
            self.window._populate_sidebar()

    # ---------------------------------------------------------- events
    def _on_event(self, event, payload):
        if event in ("finished", "queue_done", "scanned"):
            GLib.idle_add(self._on_event_main, event, payload)

    def _on_event_main(self, event, payload):
        if event == "finished" and payload["status"] == "complete":
            it = payload
            if self.settings["notify"]:
                self._notify_grouped("done", it["filename"])
            if self.settings["sound"]:
                util.play_complete_sound()
            od = it.get("on_done") or {}
            path = util.file_path(it)
            if od.get("open"):
                util.open_path(path)
            if od.get("folder"):
                util.open_folder(path)
            if od.get("shutdown"):
                CountdownDialog(self, "Shutting down", lambda: subprocess.Popen(osdeps.power_command("shutdown")))
            elif od.get("exit"):
                CountdownDialog(self, "Closing Draco", self._quit, seconds=10)
            elif (self.settings["show_complete_dialog"] and it["id"] in self._progress_seen
                  and not od.get("open")):
                CompleteDialog(self, it)
        elif event == "finished" and payload["status"] == "error" and self.settings["notify"]:
            self._notify_grouped("failed", f"{payload.get('filename') or payload['url']}: {payload.get('error', '')}")
        elif event == "queue_done":
            self._after_queue(payload or {})
        elif event == "scanned" and payload.get("scan", "").startswith("flagged"):
            n = Gio.Notification.new("Virus scanner flagged a download")
            n.set_body(f"{payload['filename']}: {payload['scan']}")
            n.set_priority(Gio.NotificationPriority.URGENT)
            self.send_notification(f"scan-{payload['id']}", n)
        return False

    # ---------------------------------------------------------- notifications
    # One notification per kind that updates itself ("3 downloads complete"), instead of one per file.
    # They are cleared as soon as the Draco window is looked at, so the dock badge never piles up.
    _NOTE_IDS = ("done", "failed", "queue-done", "background")

    def _notify_grouped(self, kind, line):
        pending = self.__dict__.setdefault("_pending_notes", {"done": [], "failed": []})
        if self.window and self.window.is_active():
            return  # the user is looking at the list already
        pending[kind].append(line)
        lines = pending[kind]
        if kind == "done":
            title = "Download complete" if len(lines) == 1 else f"{len(lines)} downloads complete"
        else:
            title = "Download failed" if len(lines) == 1 else f"{len(lines)} downloads failed"
        n = Gio.Notification.new(title)
        n.set_body("\n".join(lines[-3:]) + (f"\n…and {len(lines) - 3} more" if len(lines) > 3 else ""))
        n.set_default_action("app.show")
        self.send_notification(kind, n)

    def clear_notifications(self, *_):
        for nid in self._NOTE_IDS:
            self.withdraw_notification(nid)
        self.__dict__["_pending_notes"] = {"done": [], "failed": []}

    def _clear_old_notifications(self):
        """Older versions posted one notification per download; withdraw any that are still listed."""
        self.clear_notifications()
        for item_id in list(self.manager.items):
            for prefix in ("done-", "err-"):
                self.withdraw_notification(prefix + item_id)
        return False

    def _after_queue(self, conf):
        action = conf.get("schedule", {}).get("after", "none")
        if self.settings["notify"]:
            n = Gio.Notification.new(f"{conf.get('name', 'Queue')} finished")
            self.send_notification("queue-done", n)
        commands = {a: osdeps.power_command(a) for a in ("suspend", "hibernate", "shutdown")}
        labels = {"suspend": "Suspending", "hibernate": "Hibernating", "shutdown": "Shutting down",
                  "exit": "Closing Draco"}
        if action in commands:
            CountdownDialog(self, labels[action], lambda: subprocess.Popen(commands[action]))
        elif action == "exit":
            CountdownDialog(self, labels[action], self._quit, seconds=10)

    def _sched_tick(self):
        self.manager.scheduler_tick()
        return True

    # ---------------------------------------------------------- clipboard
    def _setup_clipboard(self):
        clip = self.window.get_display().get_clipboard()
        clip.connect("changed", self._clip_changed)

    def _clip_changed(self, clip):
        if not self.settings["clipboard_monitor"] or clip.is_local():
            return
        clip.read_text_async(None, self._clip_read)

    def _clip_read(self, clip, res):
        try:
            text = (clip.read_text_finish(res) or "").strip()
        except GLib.Error:
            return
        if not util.looks_like_url(text) or text in self._clip_seen:
            return
        self._clip_seen.add(text)
        from ..grabber import _ext
        ext = _ext(text).lstrip(".")
        if ext in self.settings["capture_exts"].split() or ext == "m3u8":
            self.request_download({"url": text})

    # ---------------------------------------------------------- misc
    def notify_text(self, title, body, quit_button=False):
        n = Gio.Notification.new(title)
        n.set_body(body)
        if quit_button:
            n.add_button("Show Draco", "app.show")
            n.add_button("Quit Draco", "app.quit")
        self.send_notification("background", n)

    def _about(self):
        d = Adw.AboutDialog(application_name=APP_NAME, version=__version__, application_icon="io.github.draco.DracoDM",
                            comments="Free multi-connection download manager for Linux.\n"
                                     "No accounts, no subscription, no trial.",
                            license_type=Gtk.License.GPL_3_0, developer_name=AUTHOR,
                            developers=[AUTHOR], designers=[AUTHOR],
                            copyright=f"© 2026 {AUTHOR}")
        d.add_credit_section("Created by", [AUTHOR])
        d.present(self.window)

    def _browser_help(self):
        from ..native import integration_status
        d = Adw.AlertDialog(heading="Browser integration", body=integration_status())
        d.add_response("ok", "OK")
        d.present(self.window)


def util_name(url, kind):
    import urllib.parse
    from ..engine import sanitize_filename
    base = urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] or "download"
    if kind in ("hls", "ffmpeg"):
        base = os.path.splitext(base)[0] + ".mp4"
    return sanitize_filename(base)
