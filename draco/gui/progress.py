"""Per-download progress window (download status / speed limiter / options on completion)."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gdk, GLib, Graphene, Gtk  # noqa: E402

from . import util  # noqa: E402
from .util import fmt_eta, fmt_size, fmt_speed  # noqa: E402

STATUS_LINE = {
    "connecting": "Connecting…", "downloading": "Receiving data…", "merging": "Joining segments…",
    "paused": "Paused", "stopped": "Stopped", "queued": "Waiting in queue", "complete": "Download complete",
}


class ProgressWindow(Adw.Window):
    def __init__(self, app, item):
        super().__init__(title=item.get("filename") or "download", default_width=580, resizable=False,
                         application=app)
        self.app = app
        self.item = item
        self.manager = app.manager
        item.setdefault("on_done", {})

        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                        margin_start=12, margin_end=12, margin_top=4, margin_bottom=12)
        tv.set_content(outer)
        self.set_content(tv)

        nb = Gtk.Notebook()
        nb.add_css_class("draco-tabs")
        nb.append_page(self._status_page(), Gtk.Label(label="Download status"))
        nb.append_page(self._limiter_page(), Gtk.Label(label="Speed Limiter"))
        nb.append_page(self._options_page(), Gtk.Label(label="Options on completion"))
        outer.append(nb)

        btns = Gtk.Box(spacing=8)
        self.details_btn = Gtk.Button(label="Show details >>")
        self.details_btn.connect("clicked", self._toggle_details)
        btns.append(self.details_btn)
        btns.append(Gtk.Box(hexpand=True))
        self.pause_btn = Gtk.Button(label="Pause", width_request=90)
        self.pause_btn.connect("clicked", self._toggle_pause)
        cancel = Gtk.Button(label="Cancel", width_request=90)
        cancel.connect("clicked", self._cancel)
        btns.append(self.pause_btn)
        btns.append(cancel)
        outer.append(btns)

        self.details = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        dbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=4)
        dbox.append(util.label("Start positions and download progress by connections", css=["draco-field-title"]))
        self.map = SegmentMap(item)
        self.map.add_css_class("draco-segbar")
        dbox.append(self.map)
        self.conn_grid = Gtk.Grid(column_spacing=18, row_spacing=1)
        self.conn_grid.add_css_class("draco-conn-table")
        for col, title in enumerate(("N.", "Downloaded", "Info")):
            lb = util.label(title, css=["head"])
            self.conn_grid.attach(lb, col, 0, 1, 1)
        self.conn_rows = []
        dbox.append(Gtk.ScrolledWindow(child=self.conn_grid, min_content_height=150, max_content_height=240,
                                       propagate_natural_height=True))
        self.details.set_child(dbox)
        outer.append(self.details)
        if app.settings.get("progress_details", False):
            self._toggle_details()

        self._timer = GLib.timeout_add(500, self._update)
        self.connect("close-request", self._on_close)
        self._update()

    # -- pages -----------------------------------------------------------
    def _status_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_start=10, margin_end=10,
                      margin_top=10, margin_bottom=10)
        self.url_lbl = util.label(self.item["url"], selectable=True)
        box.append(self.url_lbl)
        self.status_lbl = util.label("", css=["draco-dialog-head"])
        box.append(self.status_lbl)
        grid = Gtk.Grid(column_spacing=24, row_spacing=3)
        self.fields = {}
        for row, (key, title) in enumerate([("size", "File size"), ("done", "Downloaded"),
                                            ("rate", "Transfer rate"), ("eta", "Time left"),
                                            ("resume", "Resume capability")]):
            grid.attach(util.label(title, css=["draco-field-title"]), 0, row, 1, 1)
            v = util.label()
            v.set_hexpand(True)
            grid.attach(v, 1, row, 1, 1)
            self.fields[key] = v
        box.append(grid)
        self.bar = Gtk.ProgressBar(margin_top=6)
        self.bar.set_size_request(-1, 18)
        box.append(self.bar)
        return box

    def _limiter_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=10, margin_end=10,
                      margin_top=10, margin_bottom=10)
        self.limit_check = Gtk.CheckButton(label="Use speed limiter for this download",
                                           active=bool(self.item.get("speed_limit_kbps")))
        row = Gtk.Box(spacing=8)
        row.append(util.label("Maximum download speed"))
        self.limit_spin = Gtk.SpinButton.new_with_range(8, 1024 * 1024, 32)
        self.limit_spin.set_value(self.item.get("speed_limit_kbps") or 256)
        row.append(self.limit_spin)
        row.append(util.label("KB/s"))
        self.limit_check.connect("toggled", self._apply_limit)
        self.limit_spin.connect("value-changed", self._apply_limit)
        box.append(self.limit_check)
        box.append(row)
        box.append(util.label("The global limit is in the main window status bar.", css=["dim-label"]))
        return box

    def _options_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=10, margin_end=10,
                      margin_top=10, margin_bottom=10)
        od = self.item["on_done"]
        c = Gtk.CheckButton(label="Show download complete dialog", active=self.app.settings["show_complete_dialog"])
        c.connect("toggled", lambda b: (self.app.settings.__setitem__("show_complete_dialog", b.get_active()),
                                        self.app.settings.save()))
        box.append(c)
        for key, text in (("open", "Open the file when done"), ("folder", "Open the folder when done"),
                          ("exit", "Exit Draco when done"), ("shutdown", "Turn off the computer when done")):
            b = Gtk.CheckButton(label=text, active=bool(od.get(key)))
            b.connect("toggled", lambda btn, k=key: od.__setitem__(k, btn.get_active()))
            box.append(b)
        return box

    # -- actions ------------------------------------------------------------
    def _toggle_details(self, *_):
        show = not self.details.get_reveal_child()
        self.details.set_reveal_child(show)
        self.details_btn.set_label("<< Hide details" if show else "Show details >>")
        self.app.settings["progress_details"] = show

    def _apply_limit(self, *_):
        kbps = int(self.limit_spin.get_value()) if self.limit_check.get_active() else 0
        task = self.manager.task(self.item["id"])
        if task:
            task.set_speed_limit(kbps)
        else:
            self.item["speed_limit_kbps"] = kbps

    def _toggle_pause(self, *_):
        if self.manager.task(self.item["id"]):
            self.manager.pause(self.item["id"])
        else:
            self.manager.start(self.item["id"])

    def _cancel(self, *_):
        self.manager.pause(self.item["id"])
        self.close()

    def _on_close(self, *_):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        self.app.progress_windows.pop(self.item["id"], None)
        return False

    # -- refresh ------------------------------------------------------------
    def _update(self):
        it = self.item
        if it["id"] not in self.manager.items:
            self.close()
            return False
        task = self.manager.task(it["id"])
        frac = util.fraction(it)
        size = it.get("size", -1)
        self.set_title(f"{frac * 100:.0f}% {it.get('filename') or ''}")
        self.url_lbl.set_text(it["url"])
        st = it.get("status", "stopped")
        self.status_lbl.set_text("Error: " + it.get("error", "") if st == "error" else STATUS_LINE.get(st, st))
        f = self.fields
        f["size"].set_text(fmt_size(size))
        f["done"].set_text(fmt_size(it.get("downloaded", 0)) + (f" ( {frac * 100:.2f} % )" if size > 0 else ""))
        f["rate"].set_text(fmt_speed(it.get("speed")) or "—")
        f["eta"].set_text(fmt_eta(util.eta(it)) or "—")
        f["resume"].set_text("Yes" if it.get("resumable") or it.get("kind") in ("hls", "ytdlp") else
                             ("Unknown" if not it.get("probed") else "No"))
        self.bar.set_fraction(frac)
        self.pause_btn.set_label("Pause" if task else "Resume")
        self.pause_btn.set_sensitive(st != "complete")
        if self.details.get_reveal_child():
            self.map.queue_draw()
            self._update_connections(task)
        if st == "complete":
            self.close()
            return False
        return True

    def _update_connections(self, task):
        it = self.item
        segs = sorted(it.get("segments") or [], key=lambda s: s["s"])
        rows = []
        for sg in segs:
            total = (sg["e"] - sg["s"]) if sg["e"] >= 0 else -1
            got = sg["p"] - sg["s"]
            if total >= 0 and got >= total:
                info = "Finished"
            elif task:
                info = "Receiving data…"
            else:
                info = "Paused"
            rows.append((fmt_size(got), info))
        if it.get("seg_total"):
            rows = [(f"{it.get('seg_done', 0)} / {it['seg_total']} segments", "HLS stream")]
        while len(self.conn_rows) < len(rows):
            r = len(self.conn_rows) + 1
            cells = [util.label(str(r)), util.label(xalign=1), util.label()]
            for c, w in enumerate(cells):
                self.conn_grid.attach(w, c, r, 1, 1)
            self.conn_rows.append(cells)
        for i, cells in enumerate(self.conn_rows):
            visible = i < len(rows)
            for w in cells:
                w.set_visible(visible)
            if visible:
                cells[1].set_text(rows[i][0])
                cells[2].set_text(rows[i][1])


def _rgba(spec):
    c = Gdk.RGBA()
    c.parse(spec)
    return c


class SegmentMap(Gtk.Widget):
    """Bar showing which byte ranges are downloaded and where each connection is."""

    BG, DONE, HEAD = _rgba("#e8edf3"), _rgba("#3584e4"), _rgba("#e66100")

    def __init__(self, item):
        super().__init__(hexpand=True, height_request=20)
        self.item = item

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()

        def rect(x, width, color):
            snap.append_color(color, Graphene.Rect().init(x, 0, max(0.0, width), h))

        rect(0, w, self.BG)
        it = self.item
        size = it.get("size", -1)
        segs = it.get("segments") or []
        if size and size > 0 and segs:
            for sg in segs:
                rect(sg["s"] / size * w, (sg["p"] - sg["s"]) / size * w, self.DONE)
            for sg in segs:
                if sg["e"] >= 0 and sg["p"] < sg["e"]:
                    rect(sg["p"] / size * w, 2, self.HEAD)
        else:
            rect(0, util.fraction(it) * w, self.DONE)
