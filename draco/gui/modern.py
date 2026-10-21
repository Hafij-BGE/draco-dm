"""Dashboard layout of the main window, used by the dashboard themes (Galaxy Explorer, Cosmic
Minimal, Nebula Glow, Aurora Light): stats header, rounded cards, a progress column and a details
pane that shows the full progress of open downloads as tabs."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gio, GObject, Gtk  # noqa: E402

from .. import APP_ID  # noqa: E402
from ..manager import ACTIVE  # noqa: E402
from . import style, util  # noqa: E402
from .progress import ProgressView  # noqa: E402
from .util import fmt_speed  # noqa: E402
from .widgets import Ring, Sparkline  # noqa: E402

TILES = [
    ("Add URL", "draco-add-url", "win.add-url"), ("Resume", "draco-resume", "win.resume"),
    ("Stop", "draco-stop", "win.pause"), ("Stop All", "draco-stop-all", "win.stop-all"),
    ("Delete", "draco-delete", "win.delete"), ("Options", "draco-options", "win.prefs"),
    ("Scheduler", "draco-scheduler", "win.scheduler"), ("Grabber", "draco-grabber", "win.grabber"),
    ("Batch", "draco-batch", "win.batch"),
]
STATUS_ICON = {"complete": "draco-finished", "error": "dialog-error-symbolic",
               "downloading": "folder-download-symbolic", "connecting": "network-transmit-receive-symbolic",
               "merging": "emblem-synchronizing-symbolic", "paused": "media-playback-pause-symbolic"}


class ModernLayout:
    """Mixed into MainWindow; builds the dashboard and keeps its numbers up to date."""

    # ------------------------------------------------------------- build
    def _build_modern(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(self._modern_header())
        body = Gtk.Box(spacing=12, margin_start=12, margin_end=12, margin_bottom=10, vexpand=True)
        self.side_pane = self._modern_sidebar()
        body.append(self.side_pane)
        self.details_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True,
                                       shrink_end_child=False, resize_end_child=False)
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, hexpand=True)
        self.wide_stats = self._modern_wide_stats()
        main.append(self.wide_stats)
        main.append(self._modern_list())
        self.details_paned.set_start_child(main)
        self.details_paned.set_end_child(self._modern_details())
        body.append(self.details_paned)
        root.append(body)
        root.append(self._modern_statusbar())
        self._pane_mode(self.app.settings.get("details_pane", True))
        return root

    def _modern_wide_stats(self):
        """The stats row above the list, used while the details pane is closed."""
        row = Gtk.Box(spacing=12)
        speed = Gtk.Box(spacing=16, hexpand=True)
        speed.add_css_class("dm-card")
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, margin_start=18)
        col.append(util.label("Total Download Speed", css=["dm-stat-title"], ellipsize=False))
        self.wide_speed_value = util.label("0 B/s", css=["dm-stat-value", "dm-stat-big"], ellipsize=False)
        col.append(self.wide_speed_value)
        speed.append(col)
        self.wide_graph = Sparkline(height=74)
        self.wide_graph.set_margin_top(8)
        self.wide_graph.set_margin_bottom(8)
        self.wide_graph.set_margin_end(14)
        speed.append(self.wide_graph)
        row.append(speed)
        self.wide_rings = {}
        for key, title in (("active", "Active"), ("done", "Completed"), ("queue", "Queued")):
            card = Gtk.Box(spacing=12, width_request=180)
            card.add_css_class("dm-card")
            ring = Ring(key, size=58)
            ring.set_margin_start(14)
            ring.set_margin_top(10)
            ring.set_margin_bottom(10)
            self.wide_rings[key] = ring
            card.append(ring)
            card.append(util.label(title, css=["dm-stat-title"], ellipsize=False))
            row.append(card)
        return row

    def _pane_mode(self, pane_open):
        """Pane open: compact stats in the header. Pane closed: the wide stats row above the list."""
        self.header_stats.set_visible(pane_open)
        self.wide_stats.set_visible(not pane_open)

    def _modern_header(self):
        handle = Gtk.WindowHandle()
        header = Gtk.Box(spacing=14)
        header.add_css_class("dm-header")
        handle.set_child(header)

        brand = Gtk.Box(spacing=10, valign=Gtk.Align.START, width_request=262)
        brand.append(Gtk.Image(icon_name=APP_ID, pixel_size=64))
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        words.append(util.label("Draco", css=["dm-brand-title"], ellipsize=False))
        words.append(util.label("Download Manager", css=["dm-brand-sub"], ellipsize=False))
        words.append(util.label("Explore Downloads • Beyond Limits", css=["dm-brand-tag"], ellipsize=False))
        brand.append(words)
        header.append(brand)

        self._tool_icons = []
        tiles = Gtk.Box(spacing=8, valign=Gtk.Align.END, hexpand=True)
        tiles.add_css_class("dm-tiles")
        for i, (text, icon, action) in enumerate(TILES):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            img = Gtk.Image(icon_name=icon, pixel_size=30)
            self._tool_icons.append((img, icon.removeprefix("draco-")))
            box.append(img)
            box.append(Gtk.Label(label=text))
            b = Gtk.Button(child=box, action_name=action, tooltip_text=text)
            b.add_css_class("dm-tile")
            if i == 0:
                b.add_css_class("primary")
            tiles.append(b)
        self.toolbar = tiles
        header.append(tiles)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, width_request=360)
        top = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        for icon, tip, action in (("emblem-system-symbolic", "Options", "win.prefs"),
                                  ("alarm-symbolic", "Scheduler", "win.scheduler")):
            b = Gtk.Button(icon_name=icon, tooltip_text=tip, action_name=action)
            b.add_css_class("dm-icon-btn")
            top.append(b)
        palette = Gtk.MenuButton(icon_name="applications-graphics-symbolic", tooltip_text="Theme",
                                 menu_model=self._theme_menu())
        palette.add_css_class("dm-icon-btn")
        top.append(palette)
        self.pane_btn = Gtk.ToggleButton(icon_name="sidebar-show-right-symbolic", tooltip_text="Download details",
                                         active=self.app.settings.get("details_pane", True))
        self.pane_btn.add_css_class("dm-icon-btn")
        self.pane_btn.connect("toggled", lambda b: self._show_details(b.get_active()))
        top.append(self.pane_btn)
        menu = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Menu", menu_model=self._menu_model())
        menu.add_css_class("dm-icon-btn")
        top.append(menu)
        top.append(Gtk.WindowControls(side=Gtk.PackType.END))
        right.append(top)

        stats = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.header_stats = stats
        stats.add_css_class("dm-card")
        stats.set_margin_top(2)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_start=14, margin_end=14,
                        margin_top=10, margin_bottom=10)
        row = Gtk.Box(spacing=10)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        col.append(util.label("Total Download Speed", css=["dm-stat-title"], ellipsize=False))
        self.speed_value = util.label("0 B/s", css=["dm-stat-value"], ellipsize=False)
        col.append(self.speed_value)
        row.append(col)
        self.speed_graph = Sparkline(height=46)
        row.append(self.speed_graph)
        inner.append(row)
        rings = Gtk.Box(spacing=12, homogeneous=True)
        self.rings = {}
        for key, title in (("active", "Active"), ("done", "Completed"), ("queue", "Queued")):
            r = Gtk.Box(spacing=6)
            ring = Ring(key)
            self.rings[key] = ring
            r.append(ring)
            r.append(util.label(title, css=["dm-ring-label"], ellipsize=False))
            rings.append(r)
        inner.append(rings)
        stats.append(inner)
        right.append(stats)
        header.append(right)
        return handle

    def _modern_sidebar(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, width_request=250)
        card.add_css_class("dm-card")
        card.add_css_class("dm-side")
        self.sidebar = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.sidebar.connect("row-selected", self._on_sidebar)
        self._badges = {}
        self._side_icons = []

        def cat_icon(name):
            n = f"draco-cat-{name.lower()}"
            return n if (style.ICON_DIR / f"{n}.svg").exists() else "draco-folder"

        def row(text, icon, key):
            box = Gtk.Box(spacing=10)
            img = Gtk.Image(icon_name=icon, pixel_size=22)
            self._side_icons.append((img, icon.removeprefix("draco-")))
            box.append(img)
            box.append(Gtk.Label(label=text, xalign=0, hexpand=True))
            badge = Gtk.Label(label="0")
            badge.add_css_class("dm-badge")
            box.append(badge)
            self._badges[key] = badge
            r = Gtk.ListBoxRow(child=box)
            r.key = key
            self.sidebar.append(r)
            return r

        def head(text):
            r = Gtk.ListBoxRow(child=util.label(text, css=["dm-side-head"]), selectable=False, activatable=False)
            self.sidebar.append(r)

        first = row("All Downloads", "draco-folder-all", ("all", None))
        for cat in self.app.settings["categories"]:
            row(cat["name"], cat_icon(cat["name"]), ("cat", cat["name"]))
        row("General", "draco-cat-general", ("cat", "General"))
        head("Status")
        row("Unfinished", "draco-unfinished", ("unfinished", None))
        row("Finished", "draco-finished", ("finished", None))
        head("Queues")
        for q in self.manager.queue_names():
            row(q, "draco-queue", ("queue", q))
        self.sidebar.select_row(first)
        card.append(Gtk.ScrolledWindow(child=self.sidebar, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER))
        return card

    def _modern_list(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        card.add_css_class("dm-card")
        top = Gtk.Box(spacing=8, margin_start=10, margin_end=10, margin_top=10)
        tabs = Gtk.Box(spacing=6)
        tabs.add_css_class("dm-tabs")
        self.tab_buttons = {}
        group = None
        for key, title in (("all", "All Downloads"), ("downloading", "Downloading"), ("completed", "Completed")):
            b = Gtk.ToggleButton(label=title, active=(key == "all"))
            if group:
                b.set_group(group)
            group = group or b
            b.connect("toggled", lambda btn, k=key: btn.get_active() and self._set_tab(k))
            self.tab_buttons[key] = b
            tabs.append(b)
        top.append(tabs)
        top.append(Gtk.Box(hexpand=True))
        self.search = Gtk.SearchEntry(placeholder_text="Find download…", width_chars=22)
        self.search.add_css_class("dm-search")
        self.search.connect("search-changed", lambda *_: self._refilter())
        top.append(self.search)
        card.append(top)

        self.filter = Gtk.CustomFilter.new(self._filter_func)
        filtered = Gtk.FilterListModel(model=self.store, filter=self.filter)
        self.cv = Gtk.ColumnView(show_row_separators=False, show_column_separators=False, reorderable=True,
                                 hexpand=True, vexpand=True)
        self.cv.add_css_class("dm-list")
        sorted_model = Gtk.SortListModel(model=filtered, sorter=self.cv.get_sorter())
        self.selection = Gtk.MultiSelection(model=sorted_model)
        self.selection.connect("selection-changed", self._modern_selection_changed)
        self.selection.connect("items-changed", lambda *_: self._update_actions())
        self.cv.set_model(self.selection)
        self.cv.connect("activate", self._on_activate)
        it = lambda o: o.item  # noqa: E731
        self._add_column("File Name", self._name_factory(20, end_ellipsis=True), expand=True,
                         key=lambda o: o.name.lower(), width=210)
        self._add_column("Size", self._text_factory("size_text", xalign=1), key=lambda o: it(o).get("size", -1), width=92)
        self._add_column("Status", self._modern_status_factory(), key=lambda o: o.fraction, width=132)
        self._add_column("Progress", self._progress_factory(), key=lambda o: o.fraction, width=120)
        self._add_column("Time left", self._text_factory("eta_text", xalign=1), key=lambda o: util.eta(it(o)) or 0, width=72)
        self._add_column("Speed", self._text_factory("speed_text", xalign=1), key=lambda o: it(o).get("speed", 0), width=84)
        self._add_column("Last Try Date", self._text_factory("last_try_text"),
                         key=lambda o: it(o).get("finished") or it(o).get("last_try") or it(o).get("added") or 0, width=92)
        click = Gtk.GestureClick(button=3)
        click.connect("pressed", self._on_right_click)
        self.cv.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.cv.add_controller(keys)
        card.append(Gtk.ScrolledWindow(child=self.cv, vexpand=True, margin_start=4, margin_end=4, margin_bottom=6))
        return card

    def _modern_details(self):
        self.details_revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_LEFT,
                                             reveal_child=self.app.settings.get("details_pane", True))
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, width_request=460, margin_start=12)
        card.add_css_class("dm-card")
        card.add_css_class("dm-details")
        self.detail_tabs = Gtk.Notebook(scrollable=True, vexpand=True, margin_start=8, margin_end=8, margin_top=8)
        self.detail_tabs.set_show_border(False)
        self.detail_views = []          # [ProgressView, tab label, pinned]
        self.detail_empty = util.label("Select a download to see its progress here.", xalign=0.5,
                                       css=["dim-label"])
        self.detail_empty.set_vexpand(True)
        card.append(self.detail_empty)
        card.append(self.detail_tabs)
        self.detail_tabs.set_visible(False)
        self.details_revealer.set_child(card)
        return self.details_revealer

    def _modern_statusbar(self):
        bar = Gtk.Box(spacing=10)
        bar.add_css_class("dm-card")
        bar.add_css_class("dm-status")
        dot = Gtk.Box(valign=Gtk.Align.CENTER)
        dot.add_css_class("dm-dot")
        bar.append(dot)
        self.st_active = util.label("0 active")
        bar.append(self.st_active)
        for attr in ("st_done", "st_total"):
            sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
            sep.add_css_class("dm-status-sep")
            bar.append(sep)
            lb = util.label("")
            setattr(self, attr, lb)
            bar.append(lb)
        bar.append(Gtk.Box(hexpand=True))
        bar.append(Gtk.Image(icon_name="folder-download-symbolic"))
        self.st_speed = util.label("Total speed: 0 B/s")
        bar.append(self.st_speed)
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.add_css_class("dm-status-sep")
        bar.append(sep)
        bar.append(util.label("Speed limiter"))
        self.limit_toggle = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.limit_spin = Gtk.SpinButton.new_with_range(16, 1024 * 1024, 64)
        lim = self.app.settings["speed_limit_kbps"]
        self.limit_spin.set_value(lim or 512)
        self.limit_toggle.set_active(bool(lim))
        self.limit_toggle.connect("notify::active", self._apply_limit)
        self.limit_spin.connect("value-changed", self._apply_limit)
        bar.append(self.limit_toggle)
        bar.append(self.limit_spin)
        bar.append(util.label("KB/s"))
        self.status_label = Gtk.Label(visible=False)     # the classic layout's text line (unused here)
        return bar

    # ------------------------------------------------------------- menus
    def _theme_menu(self):
        palette = Gio.Menu()
        themes = Gio.Menu()
        for key, name in style.theme_names():
            themes.append(name, f"win.theme::{key}")
        palette.append_section("Theme", themes)
        return palette

    def _menu_model(self):
        """The classic menu bar, as one menu."""
        return self._build_menu_model()

    # ------------------------------------------------------------- factories
    def _modern_status_factory(self):
        f = Gtk.SignalListItemFactory()
        classes = {"complete": "draco-status-complete", "error": "draco-status-error",
                   "downloading": "draco-status-active", "connecting": "draco-status-active",
                   "merging": "draco-status-active"}

        def setup(f, li):
            box = Gtk.Box(spacing=6)
            box.append(Gtk.Image(pixel_size=14))
            box.append(util.label())
            li.set_child(box)

        def bind(f, li):
            obj, box = li.get_item(), li.get_child()
            img, lb = box.get_first_child(), box.get_last_child()

            def upd(*_):
                st = obj.item.get("status")
                lb.set_text("Error" if st == "error" else obj.status_text)
                box.set_tooltip_text(obj.item.get("error") if st == "error" else obj.status_text)
                img.set_from_icon_name(STATUS_ICON.get(st, "media-playback-pause-symbolic"))
                for w in (lb, img):
                    for c in set(classes.values()):
                        w.remove_css_class(c)
                    if classes.get(st):
                        w.add_css_class(classes[st])

            li._h = obj.connect("notify::status-text", upd)
            upd()

        f.connect("setup", setup)
        f.connect("bind", bind)
        f.connect("unbind", lambda f, li: li.get_item().disconnect(li._h))
        return f

    def _progress_factory(self):
        f = Gtk.SignalListItemFactory()

        def setup(f, li):
            ov = Gtk.Overlay()
            bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER, hexpand=True)
            bar.add_css_class("dm-progress")
            ov.set_child(bar)
            lb = Gtk.Label()
            lb.add_css_class("dm-pct")
            ov.add_overlay(lb)
            li.set_child(ov)

        def bind(f, li):
            obj, ov = li.get_item(), li.get_child()
            bar, lb = ov.get_child(), ov.get_last_child()

            def upd(*_):
                st = obj.item.get("status")
                bar.set_fraction(obj.fraction)
                lb.set_text(f"{obj.fraction * 100:.1f}%" if 0 < obj.fraction < 1 else f"{obj.fraction * 100:.0f}%")
                for c, on in (("done", st == "complete"), ("failed", st == "error")):
                    (bar.add_css_class if on else bar.remove_css_class)(c)

            li._h = [obj.connect("notify::fraction", upd), obj.connect("notify::status-text", upd)]
            upd()

        f.connect("setup", setup)
        f.connect("bind", bind)
        f.connect("unbind", lambda f, li: [li.get_item().disconnect(h) for h in li._h])
        return f

    # ------------------------------------------------------------- details pane
    def _show_details(self, on):
        self.details_revealer.set_reveal_child(on)
        self._pane_mode(on)
        self.app.settings["details_pane"] = on
        self.app.settings.save()

    def _modern_selection_changed(self, *_):
        self._update_actions()
        sel = self.selected()
        if len(sel) == 1:
            self.open_detail(sel[0])

    def open_detail(self, item, pin=False):
        """Show a download's full progress in the details pane (a pinned tab stays open)."""
        if self.layout != "modern":
            return False
        for i, entry in enumerate(self.detail_views):
            if entry[0].item is item:
                entry[2] = entry[2] or pin
                self.detail_tabs.set_current_page(i)
                self._reveal_details()
                return True
        pstyle = style.progress_style(self.app.settings.get("theme"), item.get("category"),
                                      self.app.settings.get("progress_styles"))
        view = ProgressView(self.app, item, pstyle, embedded=True)
        view.set_margin_top(6)
        view.set_margin_bottom(8)
        tab = Gtk.Box(spacing=6)
        name = util.label("", ellipsize=True)
        name.set_width_chars(14)
        name.set_max_width_chars(18)
        tab.append(name)
        close = Gtk.Button(icon_name="window-close-symbolic")
        close.add_css_class("flat")
        close.add_css_class("circular")
        tab.append(close)
        entry = [view, name, pin]
        view.on_close = lambda e=entry: self._close_detail(e)
        close.connect("clicked", lambda *_: self._close_detail(entry))
        cur = self.detail_tabs.get_current_page()
        if not pin and 0 <= cur < len(self.detail_views) and not self.detail_views[cur][2]:
            self._close_detail(self.detail_views[cur])        # replace the unpinned preview tab
            cur = min(cur, len(self.detail_views))
            pos = self.detail_tabs.insert_page(view, tab, cur)
            self.detail_views.insert(pos, entry)
        else:
            pos = self.detail_tabs.append_page(view, tab)
            self.detail_views.insert(pos, entry)
        self.detail_tabs.set_tab_reorderable(view, False)
        self.detail_tabs.set_current_page(pos)
        self._refresh_detail_titles()
        self.detail_tabs.set_visible(True)
        self.detail_empty.set_visible(False)
        if pin:
            self._reveal_details()
        return True

    def _reveal_details(self):
        if not self.details_revealer.get_reveal_child():
            self.pane_btn.set_active(True)

    def _close_detail(self, entry):
        if entry not in self.detail_views:
            return
        n = self.detail_tabs.page_num(entry[0])
        if n >= 0:
            self.detail_tabs.remove_page(n)
        self.detail_views.remove(entry)
        empty = not self.detail_views
        self.detail_tabs.set_visible(not empty)
        self.detail_empty.set_visible(empty)
        self._refresh_detail_titles()

    def _refresh_detail_titles(self):
        for i, (view, name, pin) in enumerate(self.detail_views):
            fn = view.item.get("filename") or view.item["url"].rsplit("/", 1)[-1]
            name.set_text(f"{i + 1}  {fn}")
            name.set_tooltip_text(fn)

    # ------------------------------------------------------------- refresh
    def _modern_tick(self):
        items = list(self.manager.items.values())
        active = [i for i in items if i["status"] in ACTIVE]
        done = [i for i in items if i["status"] == "complete"]
        queued = [i for i in items if i["status"] == "queued" or (i.get("queue") and i["status"] not in ("complete",)
                                                                 and i["status"] not in ACTIVE)]
        speed = sum(i.get("speed", 0) or 0 for i in active)
        total = max(1, len(items))
        self.speed_value.set_text(fmt_speed(speed) or "0 B/s")
        self.speed_graph.push(speed)
        self.wide_graph.push(speed)
        self.wide_speed_value.set_text(fmt_speed(speed) or "0 B/s")
        for rings in (self.rings, self.wide_rings):
            rings["active"].set_value(len(active), len(active) / total)
            rings["done"].set_value(len(done), len(done) / total)
            rings["queue"].set_value(len(queued), len(queued) / total)
        self.st_active.set_text(f"{len(active)} active")
        self.st_done.set_text(f"{len(done)} completed")
        self.st_total.set_text(f"{len(items)} total")
        self.st_speed.set_text(f"Total speed: {fmt_speed(speed) or '0 B/s'}")
        counts = {"all": len(items), "downloading": len(active), "completed": len(done)}
        for key, b in self.tab_buttons.items():
            title = {"all": "All Downloads", "downloading": "Downloading", "completed": "Completed"}[key]
            b.set_label(f"{title} ({counts[key]})")
        for key, badge in self._badges.items():
            kind, val = key
            if kind == "all":
                n = len(items)
            elif kind == "cat":
                n = sum(1 for i in items if i.get("category") == val)
            elif kind == "unfinished":
                n = len(items) - len(done)
            elif kind == "finished":
                n = len(done)
            else:
                n = sum(1 for i in items if i.get("queue") == val)
            badge.set_text(str(n))
        for entry in list(self.detail_views):
            if not entry[0].update():
                self._close_detail(entry)
        self._refresh_detail_titles()

    def _set_tab(self, key):
        self.tab_key = key
        self._refilter()


GObject.type_ensure(Gtk.WindowControls)
