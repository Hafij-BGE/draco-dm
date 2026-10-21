"""Layout of the light picture themes (Sky Light, Rose Sunset): brand header with square buttons,
a row of white tool tiles, coloured sidebar, download list with a details pane on the right and a
status bar with speed limiter and drive space. Downloads also get a standalone progress window
whose colours and picture follow the file kind (see BrightProgressWindow)."""

import shutil
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

from .. import APP_ID  # noqa: E402
from ..manager import ACTIVE  # noqa: E402
from . import bright_style, style, util  # noqa: E402
from .util import fmt_eta, fmt_size, fmt_speed  # noqa: E402
from .widgets import Ring, SegmentMap, Sparkline  # noqa: E402

LIMITS = [64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384]


def _lbl(text="", css=None, xalign=0, ellipsize=False, **kw):
    lb = util.label(text, xalign=xalign, css=css, ellipsize=ellipsize)
    for k, v in kw.items():
        lb.set_property(k.replace("_", "-"), v)
    return lb


def _sq(icon, tip, action=None, toggle=False, css="bw-sq"):
    b = (Gtk.ToggleButton if toggle else Gtk.Button)(icon_name=icon, tooltip_text=tip)
    if action:
        b.set_action_name(action)
    b.add_css_class(css)
    b.set_valign(Gtk.Align.CENTER)
    return b


def _tabs(titles, css, on_pick):
    box = Gtk.Box(spacing=4)
    box.add_css_class(css)
    group, buttons = None, {}
    for key, title in titles:
        b = Gtk.ToggleButton(label=title, active=group is None)
        if group:
            b.set_group(group)
        group = group or b
        b.connect("toggled", lambda btn, k=key: btn.get_active() and on_pick(k))
        buttons[key] = b
        box.append(b)
    return box, buttons


def _limiter_box(item, manager):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=12, margin_start=6)
    check = Gtk.CheckButton(label="Use speed limiter for this download", active=bool(item.get("speed_limit_kbps")))
    row = Gtk.Box(spacing=8)
    row.append(_lbl("Maximum download speed"))
    spin = Gtk.SpinButton.new_with_range(8, 1024 * 1024, 32)
    spin.set_value(item.get("speed_limit_kbps") or 256)
    row.append(spin)
    row.append(_lbl("KB/s"))

    def apply(*_):
        kbps = int(spin.get_value()) if check.get_active() else 0
        task = manager.task(item["id"])
        if task:
            task.set_speed_limit(kbps)
        else:
            item["speed_limit_kbps"] = kbps

    check.connect("toggled", apply)
    spin.connect("value-changed", apply)
    box.append(check)
    box.append(row)
    return box


def _options_box(app, item):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=12, margin_start=6)
    od = item.setdefault("on_done", {})
    c = Gtk.CheckButton(label="Show download complete dialog", active=app.settings["show_complete_dialog"])
    c.connect("toggled", lambda b: (app.settings.__setitem__("show_complete_dialog", b.get_active()),
                                    app.settings.save()))
    box.append(c)
    for key, text in (("open", "Open the file when done"), ("folder", "Open the folder when done"),
                      ("exit", "Exit Draco when done"), ("shutdown", "Turn off the computer when done")):
        b = Gtk.CheckButton(label=text, active=bool(od.get(key)))
        b.connect("toggled", lambda btn, k=key: od.__setitem__(k, btn.get_active()))
        box.append(b)
    return box


def _preview_box(item):
    """Picture of a finished image file; otherwise a short note and an Open button."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12, valign=Gtk.Align.START)
    path = util.file_path(item)
    kind = bright_style.kind_of(item)
    if item.get("status") == "complete" and kind == "image" and path.exists():
        pic = Gtk.Picture.new_for_filename(str(path))
        pic.set_content_fit(Gtk.ContentFit.CONTAIN)
        pic.set_size_request(-1, 180)
        box.append(pic)
    else:
        msg = ("Preview is available when the download has finished." if item.get("status") != "complete"
               else "No preview for this file type.")
        box.append(_lbl(msg, css=["bw-key"], wrap=True))
    if item.get("status") == "complete":
        b = Gtk.Button(label="Open file", halign=Gtk.Align.START)
        b.connect("clicked", lambda *_: util.open_path(path))
        box.append(b)
    return box


class BrightDetails(Gtk.Box):
    """Right-hand pane of the main window: Details / Speed limiter / Options on completion / Preview."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.app = window.app
        self.manager = window.manager
        self.item = None
        tabs, self.tab_buttons = _tabs((("details", "Details"), ("limiter", "Speed limiter"),
                                        ("options", "Options on completion"), ("preview", "Preview")),
                                       "bw-ptabs", self._pick)
        self.append(tabs)
        self.stack = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.append(self.stack)
        self.empty = _lbl("Select a download to see its details.", css=["bw-key"], xalign=0.5)
        self.empty.set_vexpand(True)
        self.stack.add_named(self.empty, "empty")
        self.stack.add_named(self._details(), "details")
        self.extra = {}
        self.stack.set_visible_child_name("empty")

    def _details(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_start=14, margin_end=14,
                      margin_top=14, margin_bottom=10)
        head = Gtk.Box(spacing=12)
        self.icon = Gtk.Image(pixel_size=54)
        head.append(self.icon)
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True, valign=Gtk.Align.CENTER)
        self.name = _lbl(css=["bw-detail-name"])
        self.name.set_ellipsize(Pango.EllipsizeMode.END)
        self.url = _lbl(css=["bw-url"])
        self.url.set_ellipsize(Pango.EllipsizeMode.END)
        words.append(self.name)
        words.append(self.url)
        head.append(words)
        copy = _sq("edit-copy-symbolic", "Copy address", css="bw-flat")
        copy.connect("clicked", lambda *_: self.item and self.get_clipboard().set(self.item["url"]))
        head.append(copy)
        box.append(head)

        row = Gtk.Box(spacing=16)
        pal = style.current_palette() or {}
        self.ring = Ring("active", size=78, width=6,
                         colors=(pal.get("a2", "#3b9cff"), pal.get("a1", "#2563eb"), pal.get("ring_track", "#e3e9f7")))
        self.ring.label.add_css_class("bw-ring-num")
        row.append(self.ring)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7, hexpand=True, valign=Gtk.Align.CENTER)
        self.state = _lbl(css=["bw-state"])
        col.append(self.state)
        self.bar = Gtk.ProgressBar()
        self.bar.add_css_class("bw-bar")
        self.bar.add_css_class("bw-thin")
        col.append(self.bar)
        nums = Gtk.Box(homogeneous=True)
        self.n_done, self.n_rate, self.n_eta = _lbl(css=["bw-small"]), _lbl(css=["bw-small"], xalign=0.5), \
            _lbl(css=["bw-small"], xalign=1)
        for w in (self.n_done, self.n_rate, self.n_eta):
            nums.append(w)
        col.append(nums)
        row.append(col)
        box.append(row)

        btns = Gtk.Box(spacing=10)
        self.pause = Gtk.Button(width_request=150)
        self.pause.add_css_class("bw-pause")
        self.pause.connect("clicked", self._toggle)
        cancel = Gtk.Button(width_request=150)
        cancel.add_css_class("bw-cancel")
        cb = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        cb.append(Gtk.Image(icon_name="draco-m-stop-queue", pixel_size=16))
        cb.append(Gtk.Label(label="Cancel"))
        cancel.set_child(cb)
        cancel.connect("clicked", lambda *_: self.item and self.manager.pause(self.item["id"]))
        btns.append(self.pause)
        btns.append(cancel)
        box.append(btns)
        sep = Gtk.Separator()
        sep.add_css_class("bw-sep")
        box.append(sep)

        info = Gtk.Box(spacing=14)
        grid = Gtk.Grid(column_spacing=22, row_spacing=8, valign=Gtk.Align.START)
        self.vals = {}
        for r, (key, title) in enumerate((("size", "File size"), ("done", "Downloaded"), ("rate", "Transfer rate"),
                                          ("eta", "Time left"), ("resume", "Resume capability"))):
            grid.attach(_lbl(title, css=["bw-key"]), 0, r, 1, 1)
            v = _lbl(css=["bw-val"])
            grid.attach(v, 1, r, 1, 1)
            self.vals[key] = v
        info.append(grid)
        sp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        top = Gtk.Box()
        top.append(_lbl("Speed", css=["bw-key"]))
        top.append(Gtk.Box(hexpand=True))
        self.speed = _lbl(css=["bw-speed-val"])
        top.append(self.speed)
        sp.append(top)
        self.graph = Sparkline(height=110)
        sp.append(self.graph)
        info.append(sp)
        box.append(info)
        return box

    def _pick(self, key):
        if not self.item:
            return
        if key == "details":
            self.stack.set_visible_child_name("details")
            return
        old = self.stack.get_child_by_name(key)
        if old:
            self.stack.remove(old)
        page = {"limiter": lambda: _limiter_box(self.item, self.manager),
                "options": lambda: _options_box(self.app, self.item),
                "preview": lambda: _preview_box(self.item)}[key]()
        page.set_margin_start(14)
        self.stack.add_named(page, key)
        self.stack.set_visible_child_name(key)

    def _toggle(self, *_):
        if not self.item:
            return
        if self.manager.task(self.item["id"]):
            self.manager.pause(self.item["id"])
        else:
            self.manager.start(self.item["id"])

    def show(self, item):
        if item is not self.item:
            self.item = item
            self.graph.values = [0.0] * len(self.graph.values)
            self.tab_buttons["details"].set_active(True)
            self.stack.set_visible_child_name("details")
        self.update()

    def update(self):
        it = self.item
        if not it or it["id"] not in self.manager.items:
            self.item = None
            self.stack.set_visible_child_name("empty")
            return
        task = self.manager.task(it["id"])
        frac = util.fraction(it)
        size = it.get("size", -1)
        st = it.get("status", "stopped")
        name = it.get("filename") or it["url"].rsplit("/", 1)[-1]
        self.icon.set_from_icon_name(bright_style.file_icon(it))
        self.name.set_text(name)
        self.url.set_text(it["url"])
        self.ring.set_value(f"{frac * 100:.0f}%", frac)
        self.state.set_text({"downloading": "Downloading…", "connecting": "Connecting…", "merging": "Joining…",
                             "complete": "Download complete", "error": "Error: " + (it.get("error") or "")}
                            .get(st, st.capitalize()))
        self.bar.set_fraction(frac)
        self.n_done.set_text(fmt_size(it.get("downloaded", 0)) + (f" / {fmt_size(size)}" if size > 0 else ""))
        self.n_rate.set_text(fmt_speed(it.get("speed")) if st == "downloading" else "")
        eta = fmt_eta(util.eta(it))
        self.n_eta.set_text(f"{eta} left" if eta else "")
        self.vals["size"].set_text(fmt_size(size))
        self.vals["done"].set_text(fmt_size(it.get("downloaded", 0)) + (f" ({frac * 100:.2f} %)" if size > 0 else ""))
        self.vals["rate"].set_text(fmt_speed(it.get("speed")) or "—")
        self.vals["eta"].set_text(eta or "—")
        resumable = it.get("resumable") or it.get("kind") in ("hls", "ytdlp")
        self.vals["resume"].set_text("Yes" if resumable else "No")
        for c in ("bw-val", "bw-yes"):
            self.vals["resume"].remove_css_class(c)
        self.vals["resume"].add_css_class("bw-yes" if resumable else "bw-val")
        self.speed.set_text(fmt_speed(it.get("speed")) if st == "downloading" else "")
        self.graph.push(it.get("speed", 0) if st == "downloading" else 0)
        pb = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        pb.append(Gtk.Image(icon_name="media-playback-pause-symbolic" if task else "media-playback-start-symbolic"))
        pb.append(Gtk.Label(label="Pause" if task else "Resume"))
        self.pause.set_child(pb)
        self.pause.set_sensitive(st != "complete")


class BrightLayout:
    """Mixed into MainWindow next to ModernLayout."""

    def _build_bright(self):
        self.bright = True
        self.browser = False
        self.cosmic_btn = None
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.add_css_class("bw-root")
        root.append(self._bright_header())
        body = Gtk.Box(spacing=12, vexpand=True)
        self.side_pane = self._bright_sidebar()
        body.append(self.side_pane)
        body.append(self._bright_center())
        root.append(body)
        root.append(self._bright_status())
        self._drive_t = 0
        return root

    # ------------------------------------------------------------- header
    def _bright_header(self):
        handle = Gtk.WindowHandle()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=16)
        handle.set_child(outer)
        top = Gtk.Box(spacing=12)
        logo = Gtk.Image(gicon=style.app_icon(), pixel_size=66)
        logo.add_css_class("bw-logo")
        top.append(logo)
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        words.append(_lbl("Draco", css=["bw-brand-title"]))
        words.append(_lbl("Download Manager", css=["bw-brand-sub"]))
        words.append(_lbl("Explore Downloads · Beyond Limits", css=["bw-brand-tag"]))
        top.append(words)
        right = Gtk.Box(spacing=8, valign=Gtk.Align.START)
        right.append(_sq("emblem-system-symbolic", "Options", "win.prefs"))
        right.append(_sq("alarm-symbolic", "Scheduler", "win.scheduler"))
        pal = Gtk.MenuButton(icon_name="applications-graphics-symbolic", tooltip_text="Theme",
                             menu_model=self._theme_menu(), valign=Gtk.Align.CENTER)
        pal.add_css_class("bw-sq")
        right.append(pal)
        tools = Gio.Menu()
        for text, action in (("Run Site Grabber…", "win.grabber"), ("Add Batch Download…", "win.batch"),
                             ("Import Links from Text File…", "win.import"), ("Export Download List…", "win.export"),
                             ("Browser Integration…", "app.browser-integration")):
            tools.append(text, action)
        grid = Gtk.MenuButton(icon_name="view-app-grid-symbolic", tooltip_text="Tools", menu_model=tools,
                              valign=Gtk.Align.CENTER)
        grid.add_css_class("bw-sq")
        right.append(grid)
        menu = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Menu", menu_model=self._menu_model(),
                              valign=Gtk.Align.CENTER)
        menu.add_css_class("bw-flat")
        right.append(menu)
        right.append(Gtk.WindowControls(side=Gtk.PackType.END))
        top.append(right)
        outer.append(top)

        self._tool_icons = []
        tiles = Gtk.Box(spacing=8, margin_start=166, margin_bottom=2)
        for text, icon, action, primary in (
                ("Add URL", "list-add-symbolic", "win.add-url", True), ("Resume", "draco-m-resume", "win.resume", False),
                ("Stop", "draco-m-stop", "win.pause", False), ("Stop All", "draco-m-stop-all", "win.stop-all", False),
                ("Delete", "draco-m-delete", "win.delete", False),
                ("Delete Completed", "draco-m-delete-completed", "win.delete-completed", False),
                ("Options", "draco-m-options", "win.prefs", False),
                ("Scheduler", "draco-m-scheduler", "win.scheduler", False), ("Grabber", "draco-m-grabber", "win.grabber", False),
                ("Batch", "draco-m-batch", "win.batch", False)):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.append(Gtk.Image(icon_name=icon, pixel_size=26 if primary else 24))
            box.append(Gtk.Label(label=text))
            b = Gtk.Button(child=box, action_name=action, tooltip_text=text)
            b.add_css_class("bw-tile")
            if primary:
                b.add_css_class("primary")
            tiles.append(b)
        self.toolbar = tiles
        outer.append(tiles)
        return handle

    # ------------------------------------------------------------- sidebar
    def _bright_sidebar(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, width_request=230)
        card.add_css_class("bw-card")
        card.add_css_class("bw-side")
        self.sidebar = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, margin_top=8, margin_bottom=8)
        self.sidebar.connect("row-selected", self._on_sidebar)
        self._badges = {}
        self._side_icons = []

        def row(text, icon, key, size=26, queue=False):
            box = Gtk.Box(spacing=12)
            box.append(Gtk.Image(icon_name=icon, pixel_size=size))
            box.append(Gtk.Label(label=text, xalign=0, hexpand=True))
            n = Gtk.Label(label="0")
            n.add_css_class("bw-count")
            box.append(n)
            self._badges[key] = n
            r = Gtk.ListBoxRow(child=box)
            if queue:
                r.add_css_class("bw-queue")
            r.key = key
            self.sidebar.append(r)
            return r

        first = row("All Downloads", "draco-b-home", ("all", None))
        row("Downloading", "draco-b-folder-all", ("downloading", None))
        row("Completed", "draco-m-finished", ("finished", None))
        for cat in self.app.settings["categories"]:
            icon = f"draco-b-cat-{cat['name'].lower()}"
            row(cat["name"], icon if (style.ICON_DIR / f"{icon}.svg").exists() else "draco-b-folder", ("cat", cat["name"]))
        row("General", "draco-b-cat-general", ("cat", "General"))
        head = Gtk.ListBoxRow(child=_lbl("Queues", css=["bw-side-head"]), selectable=False, activatable=False)
        self.sidebar.append(head)
        for i, q in enumerate(self.manager.queue_names()):
            row(q, ("draco-m-queues", "draco-m-scheduler", "draco-m-unfinished")[i % 3], ("queue", q), size=20, queue=True)
        self.sidebar.select_row(first)
        card.append(Gtk.ScrolledWindow(child=self.sidebar, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER))
        return card

    # ------------------------------------------------------------- list + details
    def _bright_center(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True)
        card.add_css_class("bw-card")
        top = Gtk.Box(spacing=8, margin_start=10, margin_end=10, margin_top=10)
        tabs = Gtk.Box(spacing=4)
        tabs.add_css_class("bw-tabs")
        self.tab_buttons, self.tab_titles = {}, {"all": "All", "downloading": "Downloading", "completed": "Completed"}
        group = None
        for key, icon in (("all", "draco-f-document"), ("downloading", None), ("completed", "draco-m-finished")):
            b = Gtk.ToggleButton(active=group is None)
            inner = Gtk.Box(spacing=8)
            if icon:
                inner.append(Gtk.Image(icon_name=icon, pixel_size=18))
            lb = Gtk.Label(label=self.tab_titles[key])
            inner.append(lb)
            b.set_child(inner)
            b._label = lb
            if group:
                b.set_group(group)
            group = group or b
            b.connect("toggled", lambda btn, k=key: btn.get_active() and self._set_tab(k))
            self.tab_buttons[key] = b
            tabs.append(b)
        top.append(tabs)
        more = Gtk.MenuButton(icon_name="pan-down-symbolic", tooltip_text="Sort", valign=Gtk.Align.CENTER)
        more.add_css_class("bw-flat")
        sort = Gio.Menu()
        sort.append("Show unfinished", "win.show-unfinished")
        more.set_menu_model(self._menu_model())
        top.append(more)
        top.append(Gtk.Box(hexpand=True))
        self.search = Gtk.SearchEntry(placeholder_text="Search downloads…", width_chars=30)
        self.search.add_css_class("bw-search")
        self.search.connect("search-changed", lambda *_: self._refilter())
        self.search.connect("activate", lambda e: util.looks_like_url(e.get_text().strip()) and
                            (self.app.request_download({"url": e.get_text().strip()}), e.set_text("")))
        top.append(self.search)
        self.view_list = _sq("view-list-bullet-symbolic", "List only", toggle=True)
        self.view_side = _sq("view-grid-symbolic", "Show or hide the sidebar", toggle=True)
        self.view_pane = _sq("view-dual-symbolic", "Details pane", toggle=True)
        self.view_side.set_active(self.app.settings.get("show_categories", True))
        self.view_pane.set_active(self.app.settings.get("details_pane", True))
        self.view_list.set_active(not self.view_pane.get_active())
        self.view_list.connect("toggled", lambda b: b.get_active() and self.view_pane.set_active(False))
        self.view_pane.connect("toggled", lambda b: self._bright_pane(b.get_active()))
        self.view_side.connect("toggled", lambda b: self._set_view("show_categories", self.side_pane, b.get_active()))
        for b in (self.view_list, self.view_side, self.view_pane):
            top.append(b)
        card.append(top)

        body = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True, shrink_start_child=False,
                         shrink_end_child=False, resize_end_child=False, margin_start=6, margin_end=10,
                         margin_bottom=10)
        body.set_start_child(self._bright_list())
        self.bright_details = BrightDetails(self)
        self.bright_details.set_size_request(400, -1)
        self.details_revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_LEFT,
                                             reveal_child=self.view_pane.get_active())
        pane = Gtk.Box()
        pane.add_css_class("bw-card")
        pane.set_margin_start(8)
        pane.append(self.bright_details)
        self.details_revealer.set_child(pane)
        body.set_end_child(self.details_revealer)
        card.append(body)
        self.pane_btn = self.view_pane
        return card

    def _bright_pane(self, on):
        self.details_revealer.set_reveal_child(on)
        if self.view_list.get_active() == on:
            self.view_list.set_active(not on)
        self.app.settings["details_pane"] = on
        self.app.settings.save()

    def _bright_list(self):
        self.filter = Gtk.CustomFilter.new(self._filter_func)
        filtered = Gtk.FilterListModel(model=self.store, filter=self.filter)
        self.cv = Gtk.ColumnView(show_row_separators=False, show_column_separators=False, hexpand=True, vexpand=True)
        self.cv.add_css_class("bw-list")
        sorted_model = Gtk.SortListModel(model=filtered, sorter=self.cv.get_sorter())
        self.selection = Gtk.MultiSelection(model=sorted_model)
        self.selection.connect("selection-changed", self._bright_selection)
        self.selection.connect("items-changed", lambda *_: self._update_actions())
        self.cv.set_model(self.selection)
        self.cv.connect("activate", self._on_activate)
        it = lambda o: o.item  # noqa: E731
        self._add_column("#", self._bright_index(), key=lambda o: o.item.get("added") or 0, width=34)
        self._add_column("File Name", self._bright_name(), expand=True, key=lambda o: o.name.lower(), width=170)
        self._add_column("Size", self._text_factory("size_text"), key=lambda o: it(o).get("size", -1), width=84)
        self._add_column("Progress", self._bright_progress(), key=lambda o: o.fraction, width=104)
        self._add_column("Speed", self._text_factory("speed_text"), key=lambda o: it(o).get("speed", 0), width=78)
        self._add_column("Time left", self._text_factory("eta_text"), key=lambda o: util.eta(it(o)) or 0, width=70)
        click = Gtk.GestureClick(button=3)
        click.connect("pressed", self._on_right_click)
        self.cv.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.cv.add_controller(keys)
        return Gtk.ScrolledWindow(child=self.cv, vexpand=True)

    def _bright_index(self):
        f = Gtk.SignalListItemFactory()

        def setup(f, li):
            lb = _lbl(css=["bw-index"])
            li.set_child(lb)

        f.connect("setup", setup)
        f.connect("bind", lambda f, li: li.get_child().set_text(str(li.get_position() + 1)))
        return f

    def _bright_name(self):
        f = Gtk.SignalListItemFactory()

        def setup(f, li):
            box = Gtk.Box(spacing=10)
            box.append(Gtk.Image(pixel_size=24))
            lb = util.label()
            lb.set_ellipsize(Pango.EllipsizeMode.END)
            box.append(lb)
            li.set_child(box)

        def bind(f, li):
            obj, box = li.get_item(), li.get_child()
            img, lb = box.get_first_child(), box.get_last_child()

            def upd(*_):
                img.set_from_icon_name(bright_style.file_icon(obj.item))
                lb.set_text(obj.name)
                box.set_tooltip_text(obj.name)

            li._h = obj.connect("notify::name", upd)
            upd()

        f.connect("setup", setup)
        f.connect("bind", bind)
        f.connect("unbind", lambda f, li: li.get_item().disconnect(li._h))
        return f

    def _bright_progress(self):
        f = Gtk.SignalListItemFactory()

        def setup(f, li):
            ov = Gtk.Overlay()
            bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER, hexpand=True)
            bar.add_css_class("bw-bar")
            ov.set_child(bar)
            lb = Gtk.Label(halign=Gtk.Align.END, margin_end=8)
            lb.add_css_class("bw-pct")
            ov.add_overlay(lb)
            li.set_child(ov)

        def bind(f, li):
            obj, ov = li.get_item(), li.get_child()
            bar, lb = ov.get_child(), ov.get_last_child()

            def upd(*_):
                st = obj.item.get("status")
                bar.set_fraction(obj.fraction)
                lb.set_text(f"{obj.fraction * 100:.0f}%")
                for c, on in (("done", st == "complete"), ("failed", st == "error"),
                              ("hi", st != "complete" and obj.fraction >= 0.6)):
                    (bar.add_css_class if on else bar.remove_css_class)(c)

            li._h = [obj.connect("notify::fraction", upd), obj.connect("notify::status-text", upd)]
            upd()

        f.connect("setup", setup)
        f.connect("bind", bind)
        f.connect("unbind", lambda f, li: [li.get_item().disconnect(h) for h in li._h])
        return f

    def _bright_selection(self, *_):
        self._update_actions()
        sel = self.selected()
        if len(sel) == 1:
            self.bright_details.show(sel[0])

    def _bright_open(self, item, pin=False):
        """Show the download in the details pane; a double-click (pin) opens its own window."""
        if pin:
            return False
        self.bright_details.show(item)
        return True

    # ------------------------------------------------------------- status bar
    def _bright_status(self):
        bar = Gtk.Box(spacing=12)
        bar.add_css_class("bw-card")
        bar.add_css_class("bw-status")

        def vsep():
            s = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
            s.add_css_class("bw-vsep")
            bar.append(s)

        bar.append(Gtk.Image(icon_name="draco-m-pulse", pixel_size=30))
        bar.append(_lbl("Total speed:"))
        self.st_speed = _lbl("0 B/s", css=["bw-strong"])
        bar.append(self.st_speed)
        graph_pop = Gtk.Popover()
        self.st_graph = Sparkline(height=90)
        self.st_graph.set_size_request(320, -1)
        graph_pop.set_child(self.st_graph)
        more = Gtk.MenuButton(icon_name="pan-down-symbolic", popover=graph_pop, tooltip_text="Speed history")
        more.add_css_class("bw-flat")
        bar.append(more)
        self.st_active = _lbl("0", xalign=0.5)
        self.st_active.add_css_class("bw-badge")
        bar.append(self.st_active)
        bar.append(_lbl("Downloading"))
        done = Gtk.Image(icon_name="draco-m-finished", pixel_size=24)
        bar.append(done)
        self.st_done = _lbl("Completed")
        bar.append(self.st_done)
        self.st_total = _lbl("0", css=["bw-badge-plain"])
        bar.append(self.st_total)
        bar.append(_lbl("Total"))
        vsep()
        bar.append(_lbl("Speed limiter"))
        self.limit_toggle = Gtk.Switch(valign=Gtk.Align.CENTER)
        lim = self.app.settings["speed_limit_kbps"]
        self.limit_spin = Gtk.SpinButton.new_with_range(16, 1024 * 1024, 64)     # kept for the shared limiter code
        self.limit_spin.set_value(lim or 512)
        self.limit_toggle.set_active(bool(lim))
        self.limit_drop = Gtk.DropDown.new_from_strings([fmt_speed(k * 1024) for k in LIMITS])
        self.limit_drop.add_css_class("bw-drop")
        self.limit_drop.set_valign(Gtk.Align.CENTER)
        self._sync_drop()
        self.limit_drop.connect("notify::selected", lambda d, _p: self.limit_spin.set_value(LIMITS[d.get_selected()]))
        self.limit_spin.connect("value-changed", lambda *_: (self._sync_drop(), self._apply_limit()))
        self.limit_toggle.connect("notify::active", self._apply_limit)
        bar.append(self.limit_toggle)
        bar.append(self.limit_drop)
        vsep()
        drive = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True, valign=Gtk.Align.CENTER)
        self.drive_lbl = _lbl("Drive space: —", css=["bw-small"])
        drive.append(self.drive_lbl)
        self.drive_bar = Gtk.ProgressBar()
        self.drive_bar.add_css_class("bw-bar")
        self.drive_bar.add_css_class("bw-thin")
        drive.append(self.drive_bar)
        bar.append(drive)
        folder = _sq("folder-symbolic", "Open download folder", css="bw-flat")
        folder.connect("clicked", lambda *_: util.open_path(self.app.settings.base_dir()))
        bar.append(folder)
        bar.append(_sq("emblem-system-symbolic", "Options", "win.prefs", css="bw-flat"))
        chev = Gtk.MenuButton(icon_name="pan-down-symbolic", menu_model=self._menu_model(), tooltip_text="Menu")
        chev.add_css_class("bw-flat")
        bar.append(chev)
        self.status_label = Gtk.Label(visible=False)
        return bar

    def _sync_drop(self):
        v = int(self.limit_spin.get_value())
        best = min(range(len(LIMITS)), key=lambda i: abs(LIMITS[i] - v))
        if self.limit_drop.get_selected() != best:
            self.limit_drop.set_selected(best)

    # ------------------------------------------------------------- refresh
    def _bright_tick(self):
        items = list(self.manager.items.values())
        active = [i for i in items if i["status"] in ACTIVE]
        done = [i for i in items if i["status"] == "complete"]
        speed = sum(i.get("speed", 0) or 0 for i in active)
        self.st_speed.set_text(fmt_speed(speed) or "0 B/s")
        self.st_graph.push(speed)
        self.st_active.set_text(str(len(active)))
        self.st_done.set_text("Completed")
        self.st_done.set_tooltip_text(f"{len(done)} completed")
        self.st_total.set_text(str(len(items)))
        counts = {"all": len(items), "downloading": len(active), "completed": len(done)}
        for key, b in self.tab_buttons.items():
            b._label.set_text(f"{self.tab_titles[key]} ({counts[key]})")
        for (kind, val), badge in self._badges.items():
            n = {"all": len(items), "downloading": len(active), "finished": len(done)}.get(kind)
            if n is None:
                n = sum(1 for i in items if (i.get("category") if kind == "cat" else i.get("queue")) == val)
            badge.set_text(str(n))
        if self.bright_details.item is None:            # keep the pane on the selected download
            sel = self.selected()
            if len(sel) == 1:
                self.bright_details.show(sel[0])
        self.bright_details.update()
        now = time.monotonic()
        if now - self._drive_t > 5:
            self._drive_t = now
            try:
                where = self.app.settings.base_dir()
                while not where.exists() and where != where.parent:
                    where = where.parent
                du = shutil.disk_usage(where)
                self.drive_lbl.set_text(f"Drive space: {fmt_size(du.free)} free of {fmt_size(du.total)}")
                self.drive_bar.set_fraction(du.used / du.total if du.total else 0)
            except OSError:
                self.drive_lbl.set_text("Drive space: —")


# ===================================================================== standalone window
class BrightProgressWindow(Adw.Window):
    """Progress of one download in its own small window, coloured by file kind:
    Status / Connections / Log / Preview."""

    def __init__(self, app, item):
        super().__init__(title=item.get("filename") or "download", default_width=500, resizable=False,
                         application=app)
        self.app = app
        self.item = item
        self.manager = app.manager
        self.kind = bright_style.kind_of(item)
        self.add_css_class(f"pk-{self.kind}")
        self.log = []
        self._last_status = None
        k = bright_style.KINDS[self.kind]

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=14, margin_end=14,
                       margin_bottom=14)
        handle = Gtk.WindowHandle()
        head = Gtk.Box(spacing=12, margin_top=12)
        self.icon = Gtk.Image(icon_name=bright_style.file_icon(item), pixel_size=48)
        head.append(self.icon)
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True, valign=Gtk.Align.CENTER)
        self.name = _lbl(css=["pk-name"])
        self.name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.sizes = _lbl(css=["pk-size"])
        words.append(self.name)
        words.append(self.sizes)
        head.append(words)
        head.append(Gtk.WindowControls(side=Gtk.PackType.END, valign=Gtk.Align.START))
        handle.set_child(head)
        root.append(handle)

        tabs, self.tabs = _tabs((("status", "Status"), ("connections", "Connections"), ("log", "Log"),
                                 ("preview", "Preview")), "pk-tabs", self._pick)
        root.append(tabs)
        self.stack = Gtk.Stack(vhomogeneous=False, transition_type=Gtk.StackTransitionType.CROSSFADE)
        root.append(self.stack)

        # status page
        status = Gtk.Box(spacing=12)
        status.add_css_class("pk-card")
        art = bright_style.ART_DIR / f"pw2-ill-{self.kind}.png"
        pic = Gtk.Picture.new_for_filename(str(art))
        pic.set_content_fit(Gtk.ContentFit.CONTAIN)
        pic.set_size_request(122, 120)
        pic.set_margin_start(4)
        status.append(pic)
        grid = Gtk.Grid(column_spacing=16, row_spacing=6, valign=Gtk.Align.CENTER, margin_top=10, margin_bottom=10)
        self.vals = {}
        rows = (("type", "File type:"), ("source", "Source:"), ("save", "Save to:"), ("state", "Status:"),
                ("resume", "Resumable:"))
        for r, (key, title) in enumerate(rows):
            grid.attach(_lbl(title, css=["pk-key"]), 0, r, 1, 1)
            if key in ("source", "save"):
                cell = Gtk.Box(spacing=5)
                cell.append(Gtk.Image(icon_name="web-browser-symbolic" if key == "source" else "folder-symbolic",
                                      pixel_size=13))
                v = _lbl(css=["pk-val"])
                v.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                v.set_max_width_chars(26)
                cell.append(v)
                grid.attach(cell, 1, r, 1, 1)
            else:
                v = _lbl(css=["pk-yes" if key == "resume" else "pk-val"])
                grid.attach(v, 1, r, 1, 1)
            self.vals[key] = v
        status.append(grid)
        sp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True, margin_end=12, margin_top=10,
                     margin_bottom=10)
        self.speed = _lbl(css=["pk-speed"], xalign=1)
        sp.append(self.speed)
        self.graph = Sparkline(height=80)
        self.graph.colors = (k["a1"], k["a2"])
        sp.append(self.graph)
        status.append(sp)
        self.stack.add_named(status, "status")

        conns = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=10, margin_bottom=10,
                        margin_start=12, margin_end=12)
        wrap = Gtk.Box()
        wrap.add_css_class("pk-card")
        wrap.append(conns)
        conns.append(_lbl("Start positions and download progress by connections", css=["pk-key"]))
        self.map = SegmentMap(item)
        conns.append(self.map)
        self.conn_grid = Gtk.Grid(column_spacing=18, row_spacing=2)
        self.conn_grid.add_css_class("draco-conn-table")
        for c, title in enumerate(("N.", "Downloaded", "Info")):
            self.conn_grid.attach(_lbl(title, css=["head"]), c, 0, 1, 1)
        self.conn_rows = []
        conns.append(Gtk.ScrolledWindow(child=self.conn_grid, min_content_height=120, max_content_height=180,
                                        propagate_natural_height=True))
        self.stack.add_named(wrap, "connections")

        logw = Gtk.Box()
        logw.add_css_class("pk-card")
        self.log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, margin_top=10, margin_bottom=10,
                               margin_start=12, margin_end=12)
        self.log_box.add_css_class("pk-log")
        logw.append(Gtk.ScrolledWindow(child=self.log_box, min_content_height=140, hexpand=True,
                                       propagate_natural_height=True, max_content_height=200))
        self.stack.add_named(logw, "log")
        self.preview_wrap = Gtk.Box()
        self.preview_wrap.add_css_class("pk-card")
        self.stack.add_named(self.preview_wrap, "preview")

        prog = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        prog.add_css_class("pk-card")
        line = Gtk.Box(spacing=14, margin_start=14, margin_end=14, margin_top=12)
        self.pct = _lbl(css=["pk-pct"])
        self.pct.set_width_chars(4)
        line.append(self.pct)
        self.bar = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER)
        line.append(self.bar)
        prog.append(line)
        under = Gtk.Box(margin_start=14, margin_end=14, margin_bottom=10)
        under.append(Gtk.Box(width_request=60))
        self.done = _lbl(css=["pk-small"], xalign=0.5)
        self.done.set_hexpand(True)
        under.append(self.done)
        self.eta = _lbl(css=["pk-small"], xalign=1)
        under.append(self.eta)
        prog.append(under)

        btns = Gtk.Box(spacing=10, margin_start=14, margin_end=14, margin_bottom=12)
        self.pause = Gtk.Button()
        self.pause.add_css_class("pk-pause")
        self.pause.connect("clicked", self._toggle)
        btns.append(self.pause)
        cancel = Gtk.Button()
        cancel.add_css_class("pk-cancel")
        cb = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        cb.append(Gtk.Image(icon_name="draco-m-stop-queue", pixel_size=18))
        cb.append(Gtk.Label(label="Cancel"))
        cancel.set_child(cb)
        cancel.connect("clicked", self._cancel)
        btns.append(cancel)
        btns.append(Gtk.Box(hexpand=True))
        link = Gtk.Button(icon_name="draco-link-symbolic", tooltip_text="Copy address")
        link.connect("clicked", lambda *_: self.get_clipboard().set(self.item["url"]))
        folder = Gtk.Button(icon_name="folder-symbolic", tooltip_text="Open folder")
        folder.connect("clicked", lambda *_: util.open_folder(util.file_path(self.item)))
        gear = Gtk.MenuButton(icon_name="emblem-system-symbolic", tooltip_text="Speed limit and when done")
        pop = Gtk.Popover()
        pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=6, margin_end=6, margin_bottom=6)
        pbox.append(_limiter_box(item, self.manager))
        pbox.append(_options_box(app, item))
        pop.set_child(pbox)
        gear.set_popover(pop)
        for b in (link, folder, gear):
            b.add_css_class("pk-sq")
            btns.append(b)
        prog.append(btns)
        root.append(prog)
        self.set_content(root)
        self._timer = GLib.timeout_add(500, self._update)
        self.connect("close-request", self._on_close)
        self._note(f"Opened {item.get('filename') or item['url']}")
        self._update()

    def _note(self, text):
        self.log.append((time.strftime("%H:%M:%S"), text))
        self.log_box.append(_lbl(f"{self.log[-1][0]}  {text}", wrap=True))

    def _pick(self, key):
        if key == "preview":
            child = self.preview_wrap.get_first_child()
            if child:
                self.preview_wrap.remove(child)
            box = _preview_box(self.item)
            box.set_margin_start(12)
            box.set_margin_bottom(12)
            self.preview_wrap.append(box)
        self.stack.set_visible_child_name(key)

    def _toggle(self, *_):
        if self.manager.task(self.item["id"]):
            self.manager.pause(self.item["id"])
        else:
            self.manager.start(self.item["id"])

    def _cancel(self, *_):
        self.manager.pause(self.item["id"])
        self.close()

    def _update(self):
        it = self.item
        if it["id"] not in self.manager.items:
            self.close()
            return False
        task = self.manager.task(it["id"])
        st = it.get("status", "stopped")
        frac = util.fraction(it)
        size = it.get("size", -1)
        name = it.get("filename") or it["url"].rsplit("/", 1)[-1]
        self.set_title(f"{frac * 100:.0f}% {name}")
        self.name.set_text(name)
        self.icon.set_from_icon_name(bright_style.file_icon(it))
        got = fmt_size(it.get("downloaded", 0))
        self.sizes.set_text(f"{fmt_size(size)} ({got} / {fmt_size(size)})" if size > 0 else got)
        ext = name.rsplit(".", 1)[-1].upper() if "." in name else ""
        self.vals["type"].set_text(f"{bright_style.KINDS[self.kind]['title']}" + (f" ({ext})" if ext else ""))
        from urllib.parse import urlsplit
        self.vals["source"].set_text(urlsplit(it["url"]).hostname or it["url"])
        self.vals["save"].set_text(str(it.get("save_dir") or ""))
        state = {"downloading": "Downloading…", "connecting": "Connecting…", "merging": "Joining…",
                 "complete": "Complete", "error": "Error"}.get(st, st.capitalize())
        self.vals["state"].set_text(state)
        self.vals["resume"].set_text("Yes" if it.get("resumable") or it.get("kind") in ("hls", "ytdlp") else "No")
        self.speed.set_text(fmt_speed(it.get("speed")) if st == "downloading" else "")
        self.graph.push(it.get("speed", 0) if st == "downloading" else 0)
        self.pct.set_text(f"{frac * 100:.0f}%")
        self.bar.set_fraction(frac)
        self.done.set_text(f"{got} / {fmt_size(size)}" if size > 0 else got)
        eta = fmt_eta(util.eta(it))
        self.eta.set_text(f"{eta} left" if eta else ("Done" if st == "complete" else ""))
        pb = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        pb.append(Gtk.Image(icon_name="media-playback-pause-symbolic" if task else "media-playback-start-symbolic"))
        pb.append(Gtk.Label(label="Pause" if task else "Resume"))
        self.pause.set_child(pb)
        self.pause.set_sensitive(st != "complete")
        if st != self._last_status:
            self._last_status = st
            self._note(state + (f": {it.get('error')}" if st == "error" and it.get("error") else ""))
        if self.stack.get_visible_child_name() == "connections":
            self.map.queue_draw()
            self._conns(task)
        if st == "complete":
            GLib.timeout_add(1500, lambda: (self.close(), False)[1])
            return False
        return True

    def _conns(self, task):
        segs = sorted(self.item.get("segments") or [], key=lambda s: s["s"])
        rows = []
        for sg in segs:
            total = (sg["e"] - sg["s"]) if sg["e"] >= 0 else -1
            got = sg["p"] - sg["s"]
            rows.append((fmt_size(got), "Finished" if total >= 0 and got >= total else
                         ("Receiving data…" if task else "Paused")))
        while len(self.conn_rows) < len(rows):
            r = len(self.conn_rows) + 1
            cells = [_lbl(str(r)), _lbl(xalign=1), _lbl()]
            for c, w in enumerate(cells):
                self.conn_grid.attach(w, c, r, 1, 1)
            self.conn_rows.append(cells)
        for i, cells in enumerate(self.conn_rows):
            vis = i < len(rows)
            for w in cells:
                w.set_visible(vis)
            if vis:
                cells[1].set_text(rows[i][0])
                cells[2].set_text(rows[i][1])

    def _on_close(self, *_):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        self.app.progress_windows.pop(self.item["id"], None)
        return False


GObject.type_ensure(Gtk.WindowControls)
