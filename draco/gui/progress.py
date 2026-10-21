"""Download progress: the full view (download status / speed limiter / options on completion /
connections) and the window that shows it. The same view is embedded in the main window's details
pane when Options → General → "Show download progress" is set to "Inside Draco"."""

import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from . import style, util  # noqa: E402
from .util import fmt_eta, fmt_size, fmt_speed  # noqa: E402
from .widgets import SegmentMap, Sparkline  # noqa: E402,F401  (SegmentMap: kept importable from here)

STATUS_LINE = {
    "connecting": "Connecting…", "downloading": "Receiving data…", "merging": "Joining segments…",
    "paused": "Paused", "stopped": "Stopped", "queued": "Waiting in queue", "complete": "Download complete",
}


class ProgressView(Gtk.Box):
    """Everything about one download. `pstyle` picks a dashboard look (None = classic);
    `embedded` = shown inside the main window, so it stays when the download completes."""

    def __init__(self, app, item, pstyle=None, embedded=False, on_close=None, design=""):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.app = app
        self.item = item
        self.manager = app.manager
        self.pstyle = pstyle
        self.embedded = embedded
        self.on_close = on_close or (lambda: None)
        self._last = {}            # segment index -> (bytes, time) for per-connection speed
        item.setdefault("on_done", {})
        self.design = design
        if design == "browser":
            self._build_browser()
            self.update()
            return

        nb = Gtk.Notebook()
        nb.add_css_class("draco-tabs")
        nb.append_page(self._status_page(), Gtk.Label(label="Download status"))
        nb.append_page(self._limiter_page(), Gtk.Label(label="Speed Limiter"))
        nb.append_page(self._options_page(), Gtk.Label(label="Options on completion"))
        self.append(nb)

        btns = Gtk.Box(spacing=8)
        self.details_btn = Gtk.Button(label="Show details >>")
        self.details_btn.connect("clicked", self._toggle_details)
        btns.append(self.details_btn)
        btns.append(Gtk.Box(hexpand=True))
        self.pause_btn = Gtk.Button(label="Pause", width_request=96)
        self.pause_btn.add_css_class("pw-main")
        self.pause_btn.connect("clicked", self._toggle_pause)
        btns.append(self.pause_btn)
        cancel = Gtk.Button(label="Close" if embedded else "Cancel", width_request=90)
        cancel.connect("clicked", self._cancel)
        btns.append(cancel)
        self.append(btns)

        self.details = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        dbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=4)
        if pstyle:
            dbox.add_css_class("pw-card")
            dbox.add_css_class("pw-pad")
        dbox.append(util.label("Start positions and download progress by connections", css=["draco-field-title"]))
        self.map = SegmentMap(item, pstyle)
        self.map.add_css_class("draco-segbar")
        dbox.append(self.map)
        self.conn_grid = Gtk.Grid(column_spacing=18, row_spacing=2)
        self.conn_grid.add_css_class("draco-conn-table")
        heads = ("N.", "Downloaded", "Info") + (("Progress", "Speed") if pstyle else ())
        for col, title in enumerate(heads):
            self.conn_grid.attach(util.label(title, css=["head"]), col, 0, 1, 1)
        self.conn_rows = []
        dbox.append(Gtk.ScrolledWindow(child=self.conn_grid, min_content_height=90 if embedded else 150,
                                       max_content_height=200 if embedded else 260,
                                       propagate_natural_height=True))
        self.details.set_child(dbox)
        self.append(self.details)
        if embedded or app.settings.get("progress_details", False):
            self._toggle_details()
        self.update()

    # -- Galaxy Explorer details-pane layout -----------------------------------
    def _build_browser(self):
        """File header, big percentage, Pause/Stop/Close, Info / Speed Limiter / Options /
        Connections tabs, and the connection map with per-connection progress below."""
        from gi.repository import Pango
        it = self.item
        head = Gtk.Box(spacing=14, margin_top=6)
        self.file_icon = Gtk.Image(gicon=util.icon_for_file(it.get("filename") or "x.bin"), pixel_size=52)
        head.append(self.file_icon)
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True, valign=Gtk.Align.CENTER)
        self.name_lbl = util.label("", css=["dm-detail-name"])
        self.name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        words.append(self.name_lbl)
        self.url_lbl = util.label(it["url"], css=["dim-label"])
        words.append(self.url_lbl)
        head.append(words)
        copy = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text="Copy address", valign=Gtk.Align.CENTER)
        copy.add_css_class("flat")
        copy.connect("clicked", lambda *_: self.get_clipboard().set(self.item["url"]))
        head.append(copy)
        self.append(head)

        row = Gtk.Box(spacing=18, margin_top=6)
        self.big_pct = util.label("0%", css=["dm-big-pct"], ellipsize=False)
        self.big_pct.set_valign(Gtk.Align.CENTER)
        row.append(self.big_pct)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True, valign=Gtk.Align.CENTER)
        self.status_lbl = util.label("", css=["dm-detail-status"])
        col.append(self.status_lbl)
        self.bar = Gtk.ProgressBar(hexpand=True)
        self.bar.add_css_class("dm-progress")
        col.append(self.bar)
        summary = Gtk.Box(homogeneous=True)
        self.sum_done = util.label("", ellipsize=False)
        self.sum_rate = util.label("", xalign=0.6, ellipsize=False)
        self.sum_eta = util.label("", xalign=1, ellipsize=False)
        for w in (self.sum_done, self.sum_rate, self.sum_eta):
            w.add_css_class("dm-detail-sum")
            summary.append(w)
        col.append(summary)
        row.append(col)
        self.append(row)

        btns = Gtk.Box(spacing=10, margin_top=6)
        self.pause_btn = Gtk.Button(label="Pause", width_request=118)
        self.pause_btn.add_css_class("pw-main")
        self.pause_btn.connect("clicked", self._toggle_pause)
        stop = Gtk.Button(label="Stop", width_request=118)
        stop.connect("clicked", lambda *_: self.manager.pause(self.item["id"]))
        close = Gtk.Button(label="Close", width_request=118, tooltip_text="Close this tab (the download continues)")
        close.connect("clicked", self._cancel)
        for b in (self.pause_btn, stop, close):
            btns.append(b)
        self.append(btns)

        nb = Gtk.Notebook(margin_top=8)
        nb.add_css_class("dm-inner-tabs")
        info = Gtk.Box(spacing=14, margin_top=10, margin_bottom=6, margin_start=8, margin_end=8)
        grid = Gtk.Grid(column_spacing=22, row_spacing=5, valign=Gtk.Align.CENTER)
        self.fields = {}
        for r, (key, title) in enumerate([("size", "File size"), ("done", "Downloaded"), ("rate", "Transfer rate"),
                                          ("eta", "Time left"), ("resume", "Resume capability")]):
            grid.attach(util.label(title, css=["draco-field-title"], ellipsize=False), 0, r, 1, 1)
            v = util.label(ellipsize=False)
            grid.attach(v, 1, r, 1, 1)
            self.fields[key] = v
        info.append(grid)
        speed = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        speed.add_css_class("pw-card")
        speed.add_css_class("pw-pad")
        top = Gtk.Box()
        top.append(util.label("Speed", css=["dm-ring-title"], ellipsize=False))
        top.append(Gtk.Box(hexpand=True))
        self.graph_value = util.label("", css=["pw-pct"], ellipsize=False)
        top.append(self.graph_value)
        speed.append(top)
        self.graph = Sparkline(height=86)
        speed.append(self.graph)
        info.append(speed)
        nb.append_page(info, Gtk.Label(label="Info"))
        nb.append_page(self._limiter_page(), Gtk.Label(label="Speed Limiter"))
        nb.append_page(self._options_page(), Gtk.Label(label="Options on completion"))
        conn_info = Gtk.Grid(column_spacing=22, row_spacing=5, margin_top=10, margin_start=8)
        self.conn_stats = {}
        for r, (key, title) in enumerate([("using", "Connections in use"), ("parts", "Parts finished"),
                                          ("avg", "Average per connection"), ("limit", "Connections allowed")]):
            conn_info.attach(util.label(title, css=["draco-field-title"], ellipsize=False), 0, r, 1, 1)
            v = util.label(ellipsize=False)
            conn_info.attach(v, 1, r, 1, 1)
            self.conn_stats[key] = v
        self.conn_tab = Gtk.Label(label="Connections")
        nb.append_page(conn_info, self.conn_tab)
        self.append(nb)

        conns = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=8, vexpand=True)
        conns.add_css_class("pw-card")
        conns.add_css_class("pw-pad")
        conns.append(util.label("Start positions and download progress by connections", css=["dm-ring-title"]))
        self.map = SegmentMap(it, self.pstyle)
        self.map.add_css_class("draco-segbar")
        conns.append(self.map)
        self.conn_grid = Gtk.Grid(column_spacing=18, row_spacing=3)
        self.conn_grid.add_css_class("draco-conn-table")
        for c, title in enumerate(("N.", "Downloaded", "Info", "Progress", "Speed")):
            self.conn_grid.attach(util.label(title, css=["head"]), c, 0, 1, 1)
        self.conn_rows = []
        conns.append(Gtk.ScrolledWindow(child=self.conn_grid, vexpand=True, min_content_height=150))
        self.append(conns)
        self.pct_lbl = Gtk.Label()                       # classic window only
        self.details = Gtk.Revealer(reveal_child=True)    # connections always shown here
        self.pstyle = self.pstyle or "galaxy"             # per-connection progress bars + speed

    # -- pages -----------------------------------------------------------
    def _status_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_start=10, margin_end=10,
                      margin_top=10, margin_bottom=10)
        if self.pstyle:
            box.add_css_class("pw-card")
            box.add_css_class("pw-pad")
        self.url_lbl = util.label(self.item["url"], selectable=True)
        box.append(self.url_lbl)
        self.status_lbl = util.label("", css=["draco-dialog-head"])
        box.append(self.status_lbl)
        mid = Gtk.Box(spacing=12)
        grid = Gtk.Grid(column_spacing=24, row_spacing=3, hexpand=True)
        self.fields = {}
        for row, (key, title) in enumerate([("size", "File size"), ("done", "Downloaded"),
                                            ("rate", "Transfer rate"), ("eta", "Time left"),
                                            ("resume", "Resume capability")]):
            grid.attach(util.label(title, css=["draco-field-title"], ellipsize=False), 0, row, 1, 1)
            v = util.label(ellipsize=False)
            v.set_hexpand(True)
            grid.attach(v, 1, row, 1, 1)
            self.fields[key] = v
        mid.append(grid)
        self.graph = None
        if self.pstyle:
            art = style.ART_DIR / style.PROGRESS_STYLES[self.pstyle]["art"]
            if art.exists():
                pic = Gtk.Picture.new_for_filename(str(art))
                pic.set_content_fit(Gtk.ContentFit.CONTAIN)
                pic.set_size_request(170, 110)
                mid.append(pic)
        box.append(mid)
        bar_row = Gtk.Box(spacing=10, margin_top=6)
        self.bar = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER)
        self.bar.add_css_class("dm-progress")
        self.bar.set_size_request(-1, 18)
        bar_row.append(self.bar)
        self.pct_lbl = util.label("", css=["pw-pct"])
        if self.pstyle:
            bar_row.append(self.pct_lbl)
        box.append(bar_row)
        if self.pstyle and self.embedded:
            self.graph = Sparkline(height=36)
            box.append(util.label("Speed", css=["draco-field-title"]))
            box.append(self.graph)
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
        if not self.embedded:
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
        if not self.embedded:
            self.manager.pause(self.item["id"])
        self.on_close()

    # -- refresh ------------------------------------------------------------
    def update(self):
        """Refresh from the download; returns False once the view should go away."""
        it = self.item
        if it["id"] not in self.manager.items:
            return False
        task = self.manager.task(it["id"])
        frac = util.fraction(it)
        size = it.get("size", -1)
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
        self.pct_lbl.set_text(f"{frac * 100:.0f}%")
        if self.design == "browser":
            name = it.get("filename") or it["url"].rsplit("/", 1)[-1]
            if self.name_lbl.get_text() != name:
                self.name_lbl.set_text(name)
                self.file_icon.set_from_gicon(util.icon_for_file(name))
            self.big_pct.set_text(f"{frac * 100:.0f}%")
            self.sum_done.set_text(fmt_size(it.get("downloaded", 0)) + (f" / {fmt_size(size)}" if size > 0 else ""))
            self.sum_rate.set_text(fmt_speed(it.get("speed")) if st == "downloading" else "")
            self.sum_eta.set_text(fmt_eta(util.eta(it)) or "")
            self.graph_value.set_text(fmt_speed(it.get("speed")) if st == "downloading" else "")
            segs = it.get("segments") or []
            open_ = [sg for sg in segs if sg["e"] < 0 or sg["p"] < sg["e"]]
            self.conn_tab.set_text(f"Connections ({len(segs)})" if segs else "Connections")
            using = len(open_) if task else 0
            self.conn_stats["using"].set_text(str(using))
            self.conn_stats["parts"].set_text(f"{len(segs) - len(open_)} of {len(segs)}" if segs else "—")
            self.conn_stats["avg"].set_text(fmt_speed((it.get("speed") or 0) / using) if using else "—")
            self.conn_stats["limit"].set_text(str(it.get("connections") or self.app.settings["connections"]))
        for c, on in (("done", st == "complete"), ("failed", st == "error")):
            (self.bar.add_css_class if on else self.bar.remove_css_class)(c)
        if self.graph is not None:
            self.graph.push(it.get("speed", 0) if st == "downloading" else 0)
        self.pause_btn.set_label("Pause" if task else "Resume")
        self.pause_btn.set_sensitive(st != "complete")
        if self.embedded and self.design != "browser":
            has_conns = bool(it.get("segments") or it.get("seg_total"))
            self.details.set_visible(has_conns)
            self.details_btn.set_visible(has_conns)
        if self.details.get_reveal_child():
            self.map.queue_draw()
            self._update_connections(task)
        return not (st == "complete" and not self.embedded)

    def title(self):
        it = self.item
        return f"{util.fraction(it) * 100:.0f}% {it.get('filename') or ''}"

    def _update_connections(self, task):
        it = self.item
        segs = sorted(it.get("segments") or [], key=lambda s: s["s"])
        now = time.monotonic()
        rows = []
        for i, sg in enumerate(segs):
            total = (sg["e"] - sg["s"]) if sg["e"] >= 0 else -1
            got = sg["p"] - sg["s"]
            if total >= 0 and got >= total:
                info = "Finished"
            elif task:
                info = "Receiving data…"
            else:
                info = "Paused"
            prev = self._last.get(i)
            speed = (got - prev[0]) / max(1e-3, now - prev[1]) if prev and task and info != "Finished" else 0
            self._last[i] = (got, now)
            rows.append((fmt_size(got), info, (got / total) if total > 0 else 0.0, fmt_speed(speed) if speed > 0 else ""))
        if it.get("seg_total"):
            done = it.get("seg_done", 0)
            rows = [(f"{done} / {it['seg_total']} segments", "HLS stream", done / max(1, it["seg_total"]), "")]
        while len(self.conn_rows) < len(rows):
            r = len(self.conn_rows) + 1
            cells = [util.label(str(r)), util.label(xalign=1), util.label()]
            if self.pstyle:
                bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER, width_request=110)
                bar.add_css_class("dm-progress")
                cells += [bar, util.label(xalign=1)]
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
                if self.pstyle:
                    cells[3].set_fraction(rows[i][2])
                    cells[4].set_text(rows[i][3])


class ProgressWindow(Adw.Window):
    def __init__(self, app, item):
        pstyle = style.progress_style(app.settings.get("theme"), item.get("category"),
                                      app.settings.get("progress_styles"))
        super().__init__(title=item.get("filename") or "download", default_width=640 if pstyle else 580,
                         resizable=False, application=app)
        self.app = app
        self.item = item
        tv = Adw.ToolbarView()
        header = Adw.HeaderBar()
        if pstyle:
            self.add_css_class(f"pw-{pstyle}")
            head = Gtk.Box(spacing=10)
            head.append(Gtk.Image(icon_name="io.github.draco.DracoDM", pixel_size=30))
            self.title_lbl = util.label("", css=["pw-title"])
            head.append(self.title_lbl)
            header.set_title_widget(head)
        else:
            self.title_lbl = None
        tv.add_top_bar(header)
        self.view = ProgressView(app, item, pstyle, on_close=self.close)
        self.view.set_margin_start(12)
        self.view.set_margin_end(12)
        self.view.set_margin_top(4)
        self.view.set_margin_bottom(12)
        tv.set_content(self.view)
        self.set_content(tv)
        self._timer = GLib.timeout_add(500, self._update)
        self.connect("close-request", self._on_close)
        self._update()

    def _update(self):
        alive = self.view.update()
        title = self.view.title()
        self.set_title(title)
        if self.title_lbl:
            self.title_lbl.set_text(title)
        if not alive:
            self.close()
            return False
        return True

    def _on_close(self, *_):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        self.app.progress_windows.pop(self.item["id"], None)
        return False
