"""Dialogs: add URL, file info, completion, links picker, batch, grabber, properties."""

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from .. import batch as batchmod  # noqa: E402
from ..grabber import SiteGrabber  # noqa: E402
from ..media import YTDLP  # noqa: E402
from . import util  # noqa: E402
from .util import fmt_size, fmt_time  # noqa: E402


class Dialog(Adw.Window):
    def __init__(self, app, title, width=540, height=-1):
        super().__init__(title=title, default_width=width, default_height=height, application=app)
        self.app = app
        # Attach to the main window only while the user is in it: GNOME hides a dialog together with a
        # minimised parent, so a download caught from the browser would wait unseen behind Draco.
        parent = app.window if app.window and app.window.get_visible() and app.window.is_active() else None
        if parent:
            self.set_transient_for(parent)
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                            margin_start=18, margin_end=18, margin_top=6, margin_bottom=18)
        tv.set_content(self.body)
        self.set_content(tv)
        self.buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin_top=6)
        sc = Gtk.ShortcutController()
        sc.add_shortcut(Gtk.Shortcut(trigger=Gtk.ShortcutTrigger.parse_string("Escape"),
                                     action=Gtk.CallbackAction.new(lambda *_: self.close() or True)))
        self.add_controller(sc)

    def button(self, text, cb, suggested=False, destructive=False):
        b = Gtk.Button(label=text)
        if suggested:
            b.add_css_class("suggested-action")
        if destructive:
            b.add_css_class("destructive-action")
        b.connect("clicked", lambda *_: cb())
        self.buttons.append(b)
        return b

    def finish(self):
        self.body.append(self.buttons)
        self.present()


def _grid_row(grid, row, title, widget):
    grid.attach(util.label(title, css=["dim-label"], ellipsize=False), 0, row, 1, 1)
    widget.set_hexpand(True)
    grid.attach(widget, 1, row, 1, 1)


# --------------------------------------------------------------------------
class AddUrlDialog(Dialog):
    def __init__(self, app, url=""):
        super().__init__(app, "Enter New Address to Download", 560)
        self.entry = Gtk.Entry(text=url, placeholder_text="https://…", activates_default=True)
        self.entry.connect("activate", lambda *_: self._ok())
        self.body.append(util.label("Address"))
        self.body.append(self.entry)
        self.auth = Gtk.Expander(label="Use authorization")
        g = Gtk.Grid(column_spacing=10, row_spacing=6, margin_top=6)
        self.user = Gtk.Entry()
        self.pw = Gtk.PasswordEntry(show_peek_icon=True)
        _grid_row(g, 0, "Login", self.user)
        _grid_row(g, 1, "Password", self.pw)
        self.auth.set_child(g)
        self.body.append(self.auth)
        self.button("Cancel", self.close)
        self.button("OK", self._ok, suggested=True)
        self.finish()
        if not url:
            self.get_clipboard().read_text_async(None, self._clip)

    def _clip(self, cb, res):
        try:
            text = cb.read_text_finish(res)
        except GLib.Error:
            return
        if util.looks_like_url(text) and not self.entry.get_text():
            self.entry.set_text(text.strip())
            self.entry.select_region(0, -1)

    def _ok(self):
        url = self.entry.get_text().strip()
        if not util.looks_like_url(url):
            self.entry.add_css_class("error")
            return
        req = {"url": url}
        if self.auth.get_expanded() and self.user.get_text():
            req["auth_user"] = self.user.get_text()
            req["auth_password"] = self.pw.get_text()
        self.close()
        self.app.request_download(req)


# --------------------------------------------------------------------------
class FileInfoDialog(Dialog):
    """'Download File Info': choose category, file name, folder; start now or later."""

    def __init__(self, app, item, error=None):
        super().__init__(app, "Download File Info", 600)
        self.item = item
        s = app.settings
        self.cats = [c["name"] for c in s["categories"]] + ["General"]

        g = Gtk.Grid(column_spacing=12, row_spacing=8)
        self.url = Gtk.Entry(text=item["url"])
        _grid_row(g, 0, "URL", self.url)
        self.cat = Gtk.DropDown.new_from_strings(self.cats)
        self.cat.set_selected(self.cats.index(item["category"]) if item["category"] in self.cats else len(self.cats) - 1)
        self.cat.connect("notify::selected", self._on_cat)
        _grid_row(g, 1, "Category", self.cat)

        path_box = Gtk.Box(spacing=6)
        planned = item.get("planned_dir") or item["save_dir"]     # an early download sits in the temp folder
        self.path = Gtk.Entry(text=str(Path(planned) / (item["filename"] or "download")), hexpand=True)
        browse = Gtk.Button(icon_name="document-open-symbolic", tooltip_text="Choose location")
        browse.connect("clicked", self._browse)
        path_box.append(self.path)
        path_box.append(browse)
        _grid_row(g, 2, "Save As", path_box)
        fixed = s.get("fixed_folder")
        self.where = util.label("", xalign=0, wrap=True, css=["dim-label"])
        where_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        where_box.append(self.where)
        # one click back to the folder of the last download (shown when it isn't the folder above)
        self.last_dir = s.get("last_save_dir") or ""
        self.last = Gtk.Button(halign=Gtk.Align.START, tooltip_text="Save this download in the same folder as the last one")
        self.last.add_css_class("flat")
        last_box = Gtk.Box(spacing=6)
        last_box.append(Gtk.Image(icon_name="document-open-recent-symbolic"))
        self.last_label = util.label("", xalign=0, ellipsize=True)
        last_box.append(self.last_label)
        self.last.set_child(last_box)
        self.last.connect("clicked", self._use_last)
        where_box.append(self.last)
        # Options → Start downloading while choosing the folder: show how far it already is
        # temp downloading: progress, Stop, and "don't start early" (always / for this file type)
        self.early_box = Gtk.Box(spacing=6, visible=False)
        self.early_bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER, width_request=80, hexpand=False)
        self.early_box.append(self.early_bar)
        self.early = util.label("", xalign=0, css=["accent"], ellipsize=False)
        self.early.set_hexpand(True)
        self.early_box.append(self.early)
        stop = Gtk.Button(label="Stop", tooltip_text="Stop temp downloading for this file")
        stop.add_css_class("flat")
        stop.connect("clicked", lambda *_: self._stop_early())
        self.early_box.append(stop)
        ext = Path(item.get("filename") or "").suffix.lower().lstrip(".")
        pop = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for label, never in (("Don't start early", "all"), (f"Not for .{ext} files", ext) if ext else (None, None)):
            if label:
                b = Gtk.Button(label=label)
                b.add_css_class("flat")
                b.connect("clicked", lambda _b, n=never: self._stop_early(n))
                pop.append(b)
        more = Gtk.MenuButton(icon_name="view-more-symbolic", tooltip_text="Temp downloading options",
                              popover=Gtk.Popover(child=pop))
        more.add_css_class("flat")
        self.early_more = more
        self.early_box.append(more)
        where_box.append(self.early_box)
        g.attach(where_box, 1, 3, 1, 1)
        self._confirmed = False
        self._early_timer = 0
        if item.get("early"):
            self._show_early()
            self._early_timer = GLib.timeout_add(500, self._show_early)
        self.connect("close-request", self._on_close)
        self.always = Gtk.CheckButton(label="Always save downloads to this folder from now on",
                                      active=bool(fixed) and Path(fixed).expanduser() == Path(planned))
        self.always.set_tooltip_text("Every new download goes to this folder until you reset it "
                                     "(here or in Options → Save To)")
        always_row = Gtk.Box(spacing=8)
        always_row.append(self.always)
        self.reset = Gtk.Button(label="Reset to default", valign=Gtk.Align.CENTER,
                                tooltip_text="Stop using one folder for everything: downloads go to the "
                                             "default (category) folders again")
        self.reset.add_css_class("flat")
        self.reset.connect("clicked", self._reset_folder)
        always_row.append(self.reset)
        g.attach(always_row, 1, 4, 1, 1)
        self.remember = Gtk.CheckButton(label="Remember this folder for the category")
        g.attach(self.remember, 1, 5, 1, 1)
        self.always.connect("toggled", lambda *_: self._show_where())
        self.path.connect("changed", lambda *_: self._show_where())
        self._show_where()
        self.desc = Gtk.Entry(text=item.get("description", ""))
        _grid_row(g, 6, "Description", self.desc)
        size = fmt_size(item.get("size", -1))
        info = size
        if item.get("kind") == "ytdlp":
            info = "Video page — downloaded with yt-dlp"
        elif item.get("kind") == "hls":
            info = "Streaming video (HLS) — joined into one file"
        elif item.get("probed"):
            info += "   ·   resume " + ("supported" if item.get("resumable") else "NOT supported")
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.START,
                       margin_start=8, width_request=110)
        side.append(Gtk.Image(gicon=util.icon_for_file(item["filename"] or "x.bin"), pixel_size=64))
        self.side_info = util.label(info, xalign=0.5, wrap=True)
        side.append(self.side_info)
        top = Gtk.Box(spacing=12)
        g.set_hexpand(True)
        top.append(g)
        top.append(side)
        self.body.append(top)

        self.quality = None
        self.q_values = []
        if item.get("kind") == "ytdlp":
            row = Gtk.Box(spacing=12)
            row.append(util.label("Quality", css=["dim-label"]))
            self.quality = Gtk.DropDown(model=Gtk.StringList(), hexpand=True)
            self.quality.connect("notify::selected", self._on_quality)
            row.append(self.quality)
            self.q_spinner = Gtk.Spinner(spinning=bool(item.get("_loading")), visible=bool(item.get("_loading")))
            row.append(self.q_spinner)
            self.body.append(row)
            self.subs_check = Gtk.CheckButton(label="Download subtitles too (added to the video + saved as .srt)",
                                              active=bool(item.get("subs")))
            self.body.append(self.subs_check)
            self._fill_qualities()
        self.ytdlp = None
        if YTDLP and item.get("kind") == "http":
            self.ytdlp = Gtk.CheckButton(label="Treat as video page and download with yt-dlp")
            self.body.append(self.ytdlp)
        if error:
            err = util.label(f"Could not query the server: {error}", wrap=True, css=["error"])
            self.body.append(err)

        self.queue = Gtk.DropDown.new_from_strings(app.manager.queue_names())
        later_box = Gtk.Box(spacing=0)
        later_box.add_css_class("linked")
        self.buttons.append(later_box)
        later = Gtk.Button(label="Download Later")
        later.connect("clicked", lambda *_: self._go(False))
        later_box.append(later)
        later_box.append(self.queue)
        b = self.button("Start Download", lambda: self._go(True), suggested=True)
        self.button("Cancel", self.close)
        self.set_default_widget(b)
        self.finish()
        b.grab_focus()

    # -- yt-dlp details -----------------------------------------------------
    def _fill_qualities(self):
        it = self.item
        info = it.get("ytdlp_info") or {}
        sizes = info.get("sizes") or {}
        heights = [h for h in info.get("heights") or it.get("ytdlp_heights") or [] if h >= 144]
        cur = str(it.get("ytdlp_quality") or "best")
        if cur.isdigit() and int(cur) not in heights:
            heights = sorted(set(heights) | {int(cur)}, reverse=True)

        def with_size(text, key):
            return f"{text}   —   ~{fmt_size(sizes[key])}" if sizes.get(key) else text

        best = f"Best available ({heights[0]}p)" if heights else "Best available"
        self.q_values = ["best"] + [str(h) for h in heights] + ["audio", "subs"]
        labels = ([with_size(best, "best")] + [with_size(f"{h}p", str(h)) for h in heights]
                  + [with_size("Audio only (MP3)", "audio"), "Subtitles only (.srt)"])
        self._filling = True
        self.quality.set_model(Gtk.StringList.new(labels))
        self.quality.set_selected(self.q_values.index(cur) if cur in self.q_values else 0)
        self._filling = False
        self._on_quality()

    def _on_quality(self, *_):
        if getattr(self, "_filling", False) or not self.q_values:
            return
        it = self.item
        info = it.get("ytdlp_info") or {}
        q = self.q_values[self.quality.get_selected()]
        size = (info.get("sizes") or {}).get(q)
        lines = []
        if it.get("_loading"):
            lines.append("Reading video details…")
        lines.append({"audio": "Audio (MP3)", "subs": "Subtitles"}.get(q, "Video"))
        if size and q != "subs":
            lines.append(f"~{fmt_size(size)}")
        if info.get("duration"):
            d = int(info["duration"])
            lines.append(f"{d // 3600}:{d % 3600 // 60:02d}:{d % 60:02d}" if d >= 3600 else f"{d // 60}:{d % 60:02d}")
        if info.get("uploader"):
            lines.append(info["uploader"])
        self.side_info.set_text("\n".join(lines))
        self.subs_check.set_sensitive(q not in ("subs", "audio"))
        # keep the file name's extension in step with the choice
        p = Path(self.path.get_text())
        ext = {"audio": ".mp3", "subs": ".srt"}.get(q, ".mp4")
        if p.suffix.lower() in (".mp4", ".mp3", ".srt", ".mkv", ".webm") and p.suffix.lower() != ext:
            self.path.set_text(str(p.with_suffix(ext)))

    def set_ytdlp_info(self, info, error=None):
        """Called when yt-dlp has read the page (the dialog is already open)."""
        it = self.item
        it["_loading"] = False
        self.q_spinner.stop()
        self.q_spinner.set_visible(False)
        if info:
            it["ytdlp_info"] = info
            it["ytdlp_heights"] = info["heights"]
            if not it.get("ytdlp_template"):   # page title names the file (HLS streams keep the tab title)
                p = Path(self.path.get_text())
                self.path.set_text(str(p.with_name(util_sanitize(info["title"] + p.suffix))))
            if not self.desc.get_text() and info.get("uploader"):
                self.desc.set_text(info["uploader"])
        self._fill_qualities()
        if error:
            self.body.insert_child_after(util.label(f"Could not read video details: {error}", wrap=True,
                                                    css=["error"]), self.subs_check)
        return False

    def _show_where(self):
        """Say plainly which folder the file goes to, so it can be checked before starting."""
        folder = Path(self.path.get_text()).expanduser().parent
        note = f"Will be saved in:  {folder}"
        if self.always.get_active():
            note += "\nAll new downloads will go to this folder until you reset it."
        self.where.set_text(note)
        self.remember.set_sensitive(not self.always.get_active())
        self.reset.set_visible(bool(self.app.settings.get("fixed_folder")) or self.always.get_active())
        last = Path(self.last_dir).expanduser() if self.last_dir else None
        show = bool(last) and last != folder and last.is_dir()
        self.last.set_visible(show)
        if show:
            home = str(Path.home())
            text = str(last)
            self.last_label.set_text("Last saved to:  " + ("~" + text[len(home):] if text.startswith(home) else text))

    def _show_early(self):
        it = self.item
        if not it.get("early") or it["id"] not in self.app.manager.items:
            self.early_box.set_visible(False)
            self._early_timer = 0
            return False
        size, done = it.get("size", -1), it.get("downloaded", 0)
        frac = 1.0 if it.get("early_done") else (done / size if size and size > 0 else 0.0)
        self.early_bar.set_fraction(min(1.0, frac))
        if it.get("early_done"):
            text = "Done"
        elif it.get("status") == "error":
            text = "Failed · retries on Start"
        else:
            speed = util.fmt_speed(it.get("speed")) if it.get("status") == "downloading" else ""
            text = (f"{frac * 100:.0f}% · " if size and size > 0 else "") + fmt_size(done) + (f" · {speed}" if speed else "")
        self.early.set_text(text)
        self.early_box.set_visible(True)
        return True

    def _stop_early(self, never=None):
        """Stop temp downloading for this file; `never` = "all" or a file type to switch it off for."""
        s, it = self.app.settings, self.item
        self.early_more.popdown()
        if never == "all":
            s["early_download"] = False
        elif never:
            exts = s.get("early_skip_exts", "").split()
            if never not in exts:
                s["early_skip_exts"] = " ".join(exts + [never])
        if never:
            s.save()
        if it.get("early") and it["id"] in self.app.manager.items:
            self.app.manager.discard_early(it["id"])
        # back to a normal download that starts when confirmed
        it.update(early=False, save_dir=it.pop("planned_dir", it["save_dir"]), status="stopped", downloaded=0,
                  segments=[], speed=0, error="")
        it.pop("early_done", None)
        self.early_box.set_visible(False)

    def _on_close(self, *_):
        if self._early_timer:
            GLib.source_remove(self._early_timer)
            self._early_timer = 0
        if not self._confirmed and self.item.get("early"):
            # cancelled or closed without confirming: stop the early copy and delete it
            threading.Thread(target=self.app.manager.discard_early, args=(self.item["id"],), daemon=True).start()
        return False

    def _use_last(self, *_):
        name = Path(self.path.get_text()).name or (self.item.get("filename") or "download")
        self.path.set_text(str(Path(self.last_dir).expanduser() / name))

    def _reset_folder(self, *_):
        """Back to the default folders: forget the fixed folder now and show the category's folder."""
        s = self.app.settings
        if s.get("fixed_folder"):
            s["fixed_folder"] = ""
            s.save()
        self.always.set_active(False)
        self._on_cat()
        self._show_where()
        self.where.set_text(self.where.get_text() + "\nReset: downloads go to the default folders again.")

    def _on_cat(self, *_):
        cat = self.cats[self.cat.get_selected()]
        name = Path(self.path.get_text()).name
        self.path.set_text(str(self.app.settings.folder_for(cat) / name))

    def _browse(self, *_):
        p = Path(self.path.get_text())
        dlg = Gtk.FileDialog(title="Save As", initial_name=p.name)
        if p.parent.is_dir():
            dlg.set_initial_folder(Gio_file(p.parent))

        def done(d, res):
            try:
                f = d.save_finish(res)
            except GLib.Error:
                return
            self.path.set_text(f.get_path())

        dlg.save(self, None, done)

    def _go(self, start):
        it, s = self.item, self.app.settings
        p = Path(self.path.get_text()).expanduser()
        cat = self.cats[self.cat.get_selected()]
        if s.get("last_save_dir") != str(p.parent):
            s["last_save_dir"] = str(p.parent)
            s.save()
        if self.always.get_active():
            s["fixed_folder"] = str(p.parent)
            s.save()
        elif s.get("fixed_folder") and Path(s["fixed_folder"]).expanduser() == p.parent:
            s["fixed_folder"] = ""     # unticked for the fixed folder itself: back to the default folders
            s.save()
        if self.remember.get_active() and not self.always.get_active():
            for c in s["categories"]:
                if c["name"] == cat:
                    c["folder"] = str(p.parent)
            s.save()
        m = self.app.manager
        url = self.url.get_text().strip()
        early = bool(it.get("early")) and it["id"] in m.items
        if early and (url != it["url"] or (self.ytdlp and self.ytdlp.get_active())):
            m.discard_early(it["id"])          # another link or a video page now: start over properly
            it.update(early=False, status="stopped", downloaded=0, segments=[], speed=0)
            it.pop("planned_dir", None)
            it.pop("early_done", None)
            early = False
        if early:
            # already downloading into the temp folder (this is the same item the task uses, so its
            # folder and name stay as they are): only say where the file goes
            it.update(category=cat, description=self.desc.get_text())
            it.pop("planned_dir", None)
            queue = "" if start else m.queue_names()[self.queue.get_selected()]
            self._confirmed = True
            self.close()
            m.confirm_early(it["id"], p.parent, util_sanitize(p.name), start, queue)
            if start and s["show_progress_dialog"]:
                self.app.show_progress(it)
            return
        it.update(url=url, filename=util_sanitize(p.name), save_dir=str(p.parent),
                  category=cat, description=self.desc.get_text())
        if self.ytdlp and self.ytdlp.get_active():
            it["kind"] = "ytdlp"
            it["filename"] = ""
        if self.quality is not None:
            it["ytdlp_quality"] = self.q_values[self.quality.get_selected()]
            it["subs"] = self.subs_check.get_active() and it["ytdlp_quality"] not in ("audio", "subs")
            it.pop("_loading", None)
            stem = Path(it["filename"]).stem or "video"
            it["ytdlp_template"] = stem.replace("%", "%%") + ".%(ext)s"
        queue = "" if start else m.queue_names()[self.queue.get_selected()]
        self._confirmed = True
        self.close()
        self.app.manager.add(it, start=start, queue=queue)
        if start and s["show_progress_dialog"]:
            self.app.show_progress(it)


def Gio_file(path):
    from gi.repository import Gio
    return Gio.File.new_for_path(str(path))


def util_sanitize(name):
    from ..engine import sanitize_filename
    return sanitize_filename(name)


# --------------------------------------------------------------------------
class CompleteDialog(Dialog):
    def __init__(self, app, item):
        super().__init__(app, "Download complete", 560)
        path = util.file_path(item)
        head = Gtk.Box(spacing=12)
        head.append(Gtk.Image(gicon=util.icon_for_file(item["filename"]), pixel_size=48))
        head.append(util.label("Download complete", css=["draco-dialog-head"]))
        self.body.append(head)
        g = Gtk.Grid(column_spacing=12, row_spacing=6)
        _grid_row(g, 0, "Address", util.label(item["url"], selectable=True))
        _grid_row(g, 1, "Saved to", util.label(str(path), selectable=True))
        _grid_row(g, 2, "Size", util.label(fmt_size(item.get("size", -1))))
        if item.get("scan"):
            _grid_row(g, 3, "Virus scan", util.label(item["scan"]))
        self.body.append(g)
        self.dont = Gtk.CheckButton(label="Don't show this dialog again")
        self.body.append(self.dont)
        self.button("Open", lambda: (util.open_path(path), self._close()), suggested=True)
        self.button("Open with…", lambda: (Gtk.FileLauncher(file=Gio_file(path), always_ask=True)
                                           .launch(self, None, None), self._close()))
        self.button("Open folder", lambda: (util.open_folder(path), self._close()))
        self.button("Close", self._close)
        self.finish()

    def _close(self):
        if self.dont.get_active():
            self.app.settings["show_complete_dialog"] = False
            self.app.settings.save()
        self.close()


# --------------------------------------------------------------------------
class LinkList(Gtk.Box):
    """Filterable checklist of URLs."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, vexpand=True)
        top = Gtk.Box(spacing=6)
        self.filter = Gtk.SearchEntry(placeholder_text="Filter (text or .ext)", hexpand=True)
        self.filter.connect("search-changed", lambda *_: self.listbox.invalidate_filter())
        top.append(self.filter)
        for text, val in (("All", True), ("None", False)):
            b = Gtk.Button(label=text)
            b.connect("clicked", lambda _b, v=val: self.check_visible(v))
            top.append(b)
        self.append(top)
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.listbox.add_css_class("boxed-list")
        self.listbox.set_filter_func(self._filter)
        sw = Gtk.ScrolledWindow(child=self.listbox, vexpand=True, min_content_height=260)
        self.append(sw)
        self.count = util.label("0 links", css=["dim-label"])
        self.append(self.count)
        self.rows = []

    def add(self, url, checked=True):
        cb = Gtk.CheckButton(active=checked)
        cb.connect("toggled", lambda *_: self._update_count())
        box = Gtk.Box(spacing=8, margin_start=6, margin_end=6, margin_top=2, margin_bottom=2)
        box.append(cb)
        box.append(util.label(url))
        row = Gtk.ListBoxRow(child=box)
        row.url, row.check = url, cb
        self.listbox.append(row)
        self.rows.append(row)
        self._update_count()

    def clear(self):
        self.listbox.remove_all()
        self.rows = []
        self._update_count()

    def _filter(self, row):
        t = self.filter.get_text().strip().lower()
        return not t or t in row.url.lower()

    def check_visible(self, value):
        for r in self.rows:
            if self._filter(r):
                r.check.set_active(value)

    def selected(self):
        return [r.url for r in self.rows if r.check.get_active() and self._filter(r)]

    def _update_count(self):
        self.count.set_text(f"{len(self.selected())} of {len(self.rows)} links selected")


def _queue_picker(app):
    return Gtk.DropDown.new_from_strings(app.manager.queue_names())


def add_links(app, urls, queue, start, referer="", cookies="", user_agent=""):
    m = app.manager
    for url in urls:
        it = m.new_item(url, referer=referer, cookies=cookies, user_agent=user_agent)
        it["auto_category"] = True
        m.add(it, queue=queue)
    if start and urls:
        m.start_queue(queue)
    if app.window:
        app.window.toast(f"Added {len(urls)} download(s) to {queue}")


class LinkPickerDialog(Dialog):
    def __init__(self, app, urls, title="Select links to download", referer="", cookies="", user_agent=""):
        super().__init__(app, title, 720, 560)
        self.referer, self.cookies, self.ua = referer, cookies, user_agent
        self.links = LinkList()
        for u in dict.fromkeys(urls):
            self.links.add(u, checked=_is_file_link(u, app.settings))
        self.body.append(self.links)
        self.queue = _queue_picker(app)
        self.buttons.append(util.label("Queue:"))
        self.buttons.append(self.queue)
        self.button("Cancel", self.close)
        self.button("Add to Queue", lambda: self._go(False))
        self.button("Download Now", lambda: self._go(True), suggested=True)
        self.finish()

    def _go(self, start):
        q = self.app.manager.queue_names()[self.queue.get_selected()]
        add_links(self.app, self.links.selected(), q, start, self.referer, self.cookies, self.ua)
        self.close()


def _is_file_link(url, settings):
    from ..grabber import _ext
    e = _ext(url).lstrip(".")
    return e in settings["capture_exts"].split()


# --------------------------------------------------------------------------
class BatchDialog(Dialog):
    def __init__(self, app, pattern=""):
        super().__init__(app, "Add Batch Download", 680, 600)
        self.body.append(util.label(
            "Use [from-to] ranges, e.g. https://site.com/img[001-150].jpg or /part[a-f].rar.\n"
            "Or put a single * in the address and fill in the range below.", wrap=True, css=["dim-label"]))
        self.pattern = Gtk.Entry(placeholder_text="https://example.com/file[01-20].zip")
        self.pattern.connect("changed", lambda *_: self._preview())
        self.body.append(self.pattern)
        row = Gtk.Box(spacing=8)
        self.wfrom = Gtk.Entry(text="1", width_chars=5)
        self.wto = Gtk.Entry(text="10", width_chars=5)
        self.width = Gtk.SpinButton.new_with_range(0, 10, 1)
        self.letters = Gtk.CheckButton(label="letters")
        for w in (self.wfrom, self.wto, self.width):
            w.connect("changed" if isinstance(w, Gtk.Entry) else "value-changed", lambda *_: self._preview())
        self.letters.connect("toggled", lambda *_: self._preview())
        for lbl, w in (("* from", self.wfrom), ("to", self.wto), ("digits", self.width)):
            row.append(util.label(lbl))
            row.append(w)
        row.append(self.letters)
        self.body.append(row)
        self.links = LinkList()
        self.body.append(self.links)
        self.queue = _queue_picker(app)
        self.buttons.append(util.label("Queue:"))
        self.buttons.append(self.queue)
        self.button("Cancel", self.close)
        self.button("Add to Queue", lambda: self._go(False))
        self.button("Download Now", lambda: self._go(True), suggested=True)
        self.finish()
        if pattern:
            self.pattern.set_text(pattern)

    def _preview(self):
        text = self.pattern.get_text().strip()
        self.links.clear()
        self.pattern.remove_css_class("error")
        if not text:
            return
        try:
            if "*" in text:
                urls = batchmod.expand_wildcard(text, self.wfrom.get_text() or "1", self.wto.get_text() or "1",
                                                int(self.width.get_value()), self.letters.get_active())
            else:
                urls = batchmod.expand_pattern(text)
        except (ValueError, TypeError):
            self.pattern.add_css_class("error")
            return
        for u in urls[:2000]:
            self.links.add(u)

    def _go(self, start):
        q = self.app.manager.queue_names()[self.queue.get_selected()]
        add_links(self.app, self.links.selected(), q, start)
        self.close()


# --------------------------------------------------------------------------
class GrabberDialog(Dialog):
    def __init__(self, app, url=""):
        super().__init__(app, "Site Grabber", 760, 640)
        self.grabber = None
        g = Gtk.Grid(column_spacing=12, row_spacing=8)
        self.url = Gtk.Entry(text=url, placeholder_text="Start page, e.g. https://example.com/files/")
        _grid_row(g, 0, "Start page", self.url)
        self.exts = Gtk.Entry(text=app.settings["capture_exts"])
        _grid_row(g, 1, "File types", self.exts)
        opts = Gtk.Box(spacing=10)
        self.depth = Gtk.SpinButton.new_with_range(0, 6, 1)
        self.depth.set_value(1)
        self.max_pages = Gtk.SpinButton.new_with_range(1, 5000, 50)
        self.max_pages.set_value(200)
        self.same = Gtk.CheckButton(label="Stay on this site", active=True)
        self.under = Gtk.CheckButton(label="Stay under start folder")
        opts.append(util.label("Depth"))
        opts.append(self.depth)
        opts.append(util.label("Max pages"))
        opts.append(self.max_pages)
        opts.append(self.same)
        opts.append(self.under)
        _grid_row(g, 2, "Explore", opts)
        self.body.append(g)
        bar = Gtk.Box(spacing=8)
        self.go_btn = Gtk.Button(label="Start Exploring")
        self.go_btn.add_css_class("suggested-action")
        self.go_btn.connect("clicked", lambda *_: self._toggle())
        self.status = util.label("", css=["dim-label"])
        self.spinner = Gtk.Spinner()
        bar.append(self.go_btn)
        bar.append(self.spinner)
        bar.append(self.status)
        self.body.append(bar)
        self.links = LinkList()
        self.body.append(self.links)
        self.queue = _queue_picker(app)
        self.buttons.append(util.label("Queue:"))
        self.buttons.append(self.queue)
        self.button("Close", self.close)
        self.button("Add to Queue", lambda: self._go(False))
        self.button("Download Selected", lambda: self._go(True), suggested=True)
        self.connect("close-request", lambda *_: self.grabber and self.grabber.stop() and False)
        self.finish()

    def _toggle(self):
        if self.grabber:
            self.grabber.stop()
            return
        url = self.url.get_text().strip()
        if not util.looks_like_url(url):
            self.url.add_css_class("error")
            return
        self.url.remove_css_class("error")
        self.links.clear()
        self.grabber = SiteGrabber(
            self.app.settings, url, depth=int(self.depth.get_value()),
            exts=self.exts.get_text().split(), same_site=self.same.get_active(),
            stay_under_path=self.under.get_active(), max_pages=int(self.max_pages.get_value()),
            on_found=lambda u: GLib.idle_add(self.links.add, u),
            on_progress=lambda p, f, cur: GLib.idle_add(self.status.set_text,
                                                        f"{p} pages scanned, {f} files found  {cur[-60:]}"),
            on_done=lambda: GLib.idle_add(self._done))
        self.go_btn.set_label("Stop")
        self.spinner.start()
        self.grabber.start()

    def _done(self):
        self.grabber = None
        self.go_btn.set_label("Start Exploring")
        self.spinner.stop()

    def _go(self, start):
        q = self.app.manager.queue_names()[self.queue.get_selected()]
        add_links(self.app, self.links.selected(), q, start, referer=self.url.get_text().strip())
        self.close()


# --------------------------------------------------------------------------
class PropertiesDialog(Dialog):
    def __init__(self, app, item):
        super().__init__(app, "Properties", 600)
        self.item = item
        g = Gtk.Grid(column_spacing=12, row_spacing=6)
        rows = [
            ("File", str(util.file_path(item)) if item.get("filename") else "(not known yet)"),
            ("Address", item["url"]),
            ("Final address", item.get("final_url") or ""),
            ("Referer", item.get("referer") or ""),
            ("Type", item.get("kind", "http") + (f" · {item['content_type']}" if item.get("content_type") else "")),
            ("Size", fmt_size(item.get("size", -1))),
            ("Status", util.status_text(item)),
            ("Added", fmt_time(item.get("added"))),
            ("Finished", fmt_time(item.get("finished"))),
            ("Virus scan", item.get("scan") or ""),
        ]
        r = 0
        for title, val in rows:
            if val:
                _grid_row(g, r, title, util.label(val, selectable=True))
                r += 1
        self.desc = Gtk.Entry(text=item.get("description", ""))
        _grid_row(g, r, "Description", self.desc)
        self.conns = Gtk.SpinButton.new_with_range(1, 32, 1)
        self.conns.set_value(item.get("connections") or app.settings["connections"])
        _grid_row(g, r + 1, "Connections", self.conns)
        self.body.append(g)
        self.button("Close", self.close)
        self.button("Save", self._save, suggested=True)
        self.finish()

    def _save(self):
        self.item["description"] = self.desc.get_text()
        self.item["connections"] = int(self.conns.get_value())
        self.app.manager.emit("changed", self.item)
        self.close()


class RefreshAddressDialog(Dialog):
    def __init__(self, app, item):
        super().__init__(app, "Refresh Download Address", 600)
        self.item = item
        self.body.append(util.label(
            "The link for this file has expired or stopped working. Paste a fresh link for the same file "
            "and Draco keeps everything already downloaded.\n\nOr click “Wait for browser”, then click the "
            "download link again in your browser — Draco will catch it and use it here.",
            wrap=True))
        self.body.append(util.label(f"File: {item.get('filename') or item['url']}", css=["dim-label"]))
        self.entry = Gtk.Entry(placeholder_text="New address")
        self.body.append(self.entry)
        self.button("Cancel", self.close)
        self.button("Wait for Browser", self._wait)
        self.button("Apply", self._apply, suggested=True)
        self.finish()

    def _wait(self):
        self.app.refresh_target = self.item["id"]
        if self.app.window:
            self.app.window.toast("Now click the download link again in your browser")
        self.close()

    def _apply(self):
        url = self.entry.get_text().strip()
        if not util.looks_like_url(url):
            self.entry.add_css_class("error")
            return
        self.app.manager.refresh_address(self.item["id"], url)
        self.close()


class CountdownDialog(Dialog):
    """Gives the user a chance to cancel shutdown/suspend after a queue finishes."""

    def __init__(self, app, action_label, callback, seconds=60):
        super().__init__(app, "Queue finished", 420)
        self.callback, self.left, self.action_label = callback, seconds, action_label
        self.lbl = util.label("", wrap=True)
        self.body.append(self.lbl)
        self.button("Cancel", self._cancel, suggested=True)
        self.button("Do It Now", self._fire, destructive=True)
        self._timer = GLib.timeout_add_seconds(1, self._tick)
        self._tick()
        self.finish()

    def _tick(self):
        self.lbl.set_text(f"All downloads in the queue are finished.\n{self.action_label} in {self.left} seconds.")
        self.left -= 1
        if self.left < 0:
            self._timer = None  # this source ends by returning False
            self._fire()
            return False
        return True

    def _cancel(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        self.close()

    def _fire(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        self.close()
        self.callback()
