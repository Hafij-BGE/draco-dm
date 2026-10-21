"""Main window: toolbar, category/queue sidebar and the download list."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk  # noqa: E402

from .. import APP_NAME  # noqa: E402
from ..manager import ACTIVE  # noqa: E402
from . import style, util  # noqa: E402
from .modern import ModernLayout  # noqa: E402
from .util import fmt_eta, fmt_size, fmt_speed, fmt_time  # noqa: E402


class DownloadObj(GObject.Object):
    __gtype_name__ = "DracoDownloadObj"

    name = GObject.Property(type=str, default="")
    size_text = GObject.Property(type=str, default="")
    status_text = GObject.Property(type=str, default="")
    fraction = GObject.Property(type=float, default=0.0)
    eta_text = GObject.Property(type=str, default="")
    speed_text = GObject.Property(type=str, default="")
    last_try_text = GObject.Property(type=str, default="")
    description = GObject.Property(type=str, default="")
    queue_text = GObject.Property(type=str, default="")
    icon = GObject.Property(type=Gio.Icon)

    def __init__(self, item):
        super().__init__()
        self.item = item
        self.id = item["id"]
        self._icon_for = None
        self.refresh()

    def _put(self, prop, value):
        if self.get_property(prop) != value:
            self.set_property(prop, value)

    def refresh(self):
        it = self.item
        name = it.get("filename") or it["url"].rsplit("/", 1)[-1] or it["url"]
        self._put("name", name)
        if self._icon_for != name:
            self._icon_for = name
            self.set_property("icon", util.icon_for_file(name))
        self._put("size_text", fmt_size(it.get("size", -1)) if it.get("size", -1) > 0 else "")
        self._put("status_text", util.status_text(it))
        self._put("fraction", util.fraction(it))
        self._put("eta_text", fmt_eta(util.eta(it)))
        self._put("speed_text", fmt_speed(it.get("speed")) if it.get("status") == "downloading" else "")
        self._put("last_try_text", fmt_time(it.get("finished") or it.get("last_try") or it.get("added")))
        self._put("description", it.get("description", ""))
        self._put("queue_text", it.get("queue", ""))


def _cmp(a, b):
    return Gtk.Ordering.SMALLER if a < b else (Gtk.Ordering.LARGER if a > b else Gtk.Ordering.EQUAL)


class MainWindow(ModernLayout, Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.app = app
        self.manager = app.manager
        self.set_default_size(1240, 680)
        self.set_icon_name("io.github.draco.DracoDM")
        self.objs = {}
        self.store = Gio.ListStore(item_type=DownloadObj)
        self.filter_key = ("all", None)
        self.tab_key = "all"
        self.layout = None

        self._build_actions()
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)
        self.apply_layout()

        for it in self.manager.items.values():
            self._add_obj(it)

        drop = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)

        self._changed = set()
        self.manager.listeners.append(self._on_manager_event)
        GLib.timeout_add(500, self._tick)
        self.connect("close-request", self._on_close)
        self._update_actions()

    # ------------------------------------------------------------------ UI
    def apply_layout(self):
        """Classic menu-bar layout, or the dashboard for the dashboard themes. Rebuilt on theme change."""
        theme = self.app.settings.get("theme")
        want = "modern" if style.is_modern(theme) else "classic"
        # dashboard themes differ in extras (Cosmic Dashboard), so a switch between them rebuilds too
        if want == self.layout and (want == "classic" or theme == getattr(self, "_layout_theme", None)):
            return
        self.layout = want
        self._layout_theme = theme
        self.browser = False
        self.detail_views = []
        self.cosmic = None
        if want == "modern":
            self.add_css_class("dm-window")
            content = self._build_modern()
            if self.get_default_size()[0] < 1500:
                self.set_default_size(1600, 900)
        else:
            self.remove_css_class("dm-window")
            content = self._build_classic()
        self.toast_overlay.set_child(content)
        self.side_pane.set_visible(self.app.settings.get("show_categories", True))
        self.toolbar.set_visible(self.app.settings.get("show_toolbar", True))
        self.apply_icons()
        self._update_actions()

    def _build_classic(self):
        view = Adw.ToolbarView(top_bar_style=Adw.ToolbarStyle.FLAT)
        header = Adw.HeaderBar(title_widget=Adw.WindowTitle(title=APP_NAME))
        palette = Gio.Menu()
        themes = Gio.Menu()
        for key, name in style.theme_names():
            themes.append(name, f"win.theme::{key}")
        palette.append_section("Theme", themes)
        icon_styles = Gio.Menu()
        for key, name in style.ICON_STYLES:
            icon_styles.append(name, f"win.icon-style::{key}")
        palette.append_section("Icon style", icon_styles)
        header.pack_end(Gtk.MenuButton(icon_name="applications-graphics-symbolic", menu_model=palette,
                                       tooltip_text="Theme and icon style"))
        view.add_top_bar(header)
        view.add_top_bar(self._build_menubar())
        self.toolbar = self._build_toolbar()
        view.add_top_bar(self.toolbar)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, position=215,
                               shrink_start_child=False, resize_start_child=False)
        self.side_pane = self._build_sidebar()
        self.paned.set_start_child(self.side_pane)
        self.paned.set_end_child(self._build_list())
        view.set_content(self.paned)
        view.add_bottom_bar(self._build_statusbar())
        return view

    def _build_menubar(self):
        bar = Gtk.PopoverMenuBar.new_from_model(self._build_menu_model())
        bar.add_css_class("draco-menubar")
        return bar

    def _build_menu_model(self):
        root = Gio.Menu()

        def sub(label, *sections):
            menu = Gio.Menu()
            for sec in sections:
                s = Gio.Menu()
                for text, action in sec:
                    s.append(text, action)
                menu.append_section(None, s)
            root.append_submenu(label, menu)

        sub("_Tasks",
            [("Add New Download…", "win.add-url"), ("Add Batch Download…", "win.batch"),
             ("Add Batch Download from Clipboard", "win.batch-clipboard")],
            [("Run Site Grabber…", "win.grabber")],
            [("Import Links from Text File…", "win.import"), ("Export Download List…", "win.export")],
            [("Exit", "app.quit")])
        sub("_File",
            [("Open", "win.open"), ("Open With…", "win.open-with"), ("Open Folder", "win.open-folder")],
            [("Redownload", "win.redownload"), ("Refresh Download Address…", "win.refresh-address"),
             ("Copy Address", "win.copy-url")],
            [("Properties", "win.properties"), ("Remove", "win.delete")])
        sub("_Downloads",
            [("Resume", "win.resume"), ("Stop", "win.pause"), ("Stop All", "win.stop-all")],
            [("Delete", "win.delete"), ("Delete All Completed", "win.delete-completed")],
            [("Speed Limiter", "win.speed-limiter")],
            [("Scheduler…", "win.scheduler"), ("Start Queue", "win.start-queue"), ("Stop Queue", "win.stop-queue")],
            [("Options…", "win.prefs")])
        themes = Gio.Menu()
        for key, name in style.theme_names():
            themes.append(name, f"win.theme::{key}")
        view = Gio.Menu()
        s1 = Gio.Menu()
        s1.append("Categories", "win.show-categories")
        s1.append("Toolbar", "win.show-toolbar")
        view.append_section(None, s1)
        icons_menu = Gio.Menu()
        for key, name in style.ICON_STYLES:
            icons_menu.append(name, f"win.icon-style::{key}")
        s2 = Gio.Menu()
        s2.append_submenu("Theme", themes)
        s2.append_submenu("Icon Style", icons_menu)
        view.append_section(None, s2)
        s3 = Gio.Menu()
        s3.append("Show Download Progress", "win.progress")
        view.append_section(None, s3)
        root.append_submenu("_View", view)
        sub("_Help",
            [("Browser Integration…", "app.browser-integration")],
            [("About Draco Download Manager", "app.about")])
        return root

    def _build_toolbar(self):
        self._tool_icons = []
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        bar.add_css_class("draco-toolbar")
        buttons = [
            ("Add URL", "draco-add-url", "win.add-url"),
            ("Resume", "draco-resume", "win.resume"),
            ("Stop", "draco-stop", "win.pause"),
            ("Stop All", "draco-stop-all", "win.stop-all"),
            ("Delete", "draco-delete", "win.delete"),
            ("Delete Completed", "draco-delete-completed", "win.delete-completed"),
            None,
            ("Options", "draco-options", "win.prefs"),
            ("Scheduler", "draco-scheduler", "win.scheduler"),
            ("Start Queue", "draco-start-queue", "win.start-queue"),
            ("Stop Queue", "draco-stop-queue", "win.stop-queue"),
            None,
            ("Grabber", "draco-grabber", "win.grabber"),
            ("Batch", "draco-batch", "win.batch"),
        ]
        for spec in buttons:
            if spec is None:
                bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
                continue
            text, icon, action = spec
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            img = Gtk.Image(icon_name=icon, pixel_size=32)
            self._tool_icons.append((img, icon.removeprefix("draco-")))
            box.append(img)
            box.append(Gtk.Label(label=text))
            b = Gtk.Button(child=box, action_name=action, tooltip_text=text)
            b.add_css_class("tool")
            bar.append(b)
        bar.append(Gtk.Box(hexpand=True))
        self.search = Gtk.SearchEntry(placeholder_text="Find download", width_chars=18,
                                      valign=Gtk.Align.CENTER, margin_end=4)
        self.search.connect("search-changed", lambda *_: self._refilter())
        bar.append(self.search)
        return bar

    def _build_sidebar(self):
        pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        pane.add_css_class("draco-sidebar")
        head = Gtk.Box()
        head.add_css_class("draco-pane-title")
        head.append(Gtk.Label(label="Categories", xalign=0, hexpand=True))
        close = Gtk.Button(icon_name="window-close-symbolic", tooltip_text="Hide categories",
                           action_name="win.show-categories")
        close.add_css_class("flat")
        close.add_css_class("circular")
        close.set_size_request(18, 18)
        head.append(close)
        pane.append(head)
        self.sidebar = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.sidebar.connect("row-selected", self._on_sidebar)
        self._populate_sidebar()
        pane.append(Gtk.ScrolledWindow(child=self.sidebar, vexpand=True,
                                       hscrollbar_policy=Gtk.PolicyType.NEVER))
        pane.set_size_request(185, -1)
        return pane

    def _populate_sidebar(self):
        self.sidebar.remove_all()
        self._tree_children = {}
        self._side_icons = []

        def row(text, icon, key, depth=0, parent=None, expandable=False):
            box = Gtk.Box(spacing=5, margin_start=2 + depth * 22)
            exp = Gtk.Button(icon_name="pan-down-symbolic", valign=Gtk.Align.CENTER)
            exp.add_css_class("flat")
            exp.set_size_request(16, 16)
            if expandable:
                exp.connect("clicked", lambda b, k=key: self._toggle_branch(k, b))
            else:  # invisible placeholder keeps the columns aligned
                exp.set_opacity(0)
                exp.set_can_target(False)
                exp.set_can_focus(False)
            box.append(exp)
            img = Gtk.Image(icon_name=icon, pixel_size=20)
            self._side_icons.append((img, icon.removeprefix("draco-")))
            box.append(img)
            box.append(Gtk.Label(label=text, xalign=0, hexpand=True))
            r = Gtk.ListBoxRow(child=box)
            r.key = key
            self.sidebar.append(r)
            if parent is not None:
                self._tree_children.setdefault(parent, []).append(r)
            return r

        def cat_icon(name):
            n = f"draco-cat-{name.lower()}"
            return n if (style.ICON_DIR / f"{n}.svg").exists() else "draco-folder"

        first = row("All Downloads", "draco-folder-all", ("all", None), expandable=True)
        for cat in self.app.settings["categories"]:
            row(cat["name"], cat_icon(cat["name"]), ("cat", cat["name"]), 1, ("all", None))
        row("General", "draco-cat-general", ("cat", "General"), 1, ("all", None))
        row("Unfinished", "draco-unfinished", ("unfinished", None))
        row("Finished", "draco-finished", ("finished", None))
        queues_key = ("queues", None)
        row("Queues", "draco-queues", queues_key, expandable=True)
        for q in self.manager.queue_names():
            row(q, "draco-queue", ("queue", q), 1, queues_key)
        self.sidebar.select_row(first)
        if hasattr(self, "_tool_icons"):
            self.apply_icons()

    def apply_icons(self):
        """Restyle toolbar + category icons for the current theme / icon-style choice."""
        s = self.app.settings
        icon_style = style.resolve_icon_style(s.get("theme") or "classic", s.get("icon_style", "auto"))
        for key, _ in style.ICON_STYLES:
            self.remove_css_class(f"draco-icons-{key}")
        self.add_css_class(f"draco-icons-{icon_style}")
        line = icon_style in ("mono", "accent")
        side = (22, 18) if self.layout == "modern" else (20, 16)
        tool = (30, 26) if self.layout == "modern" else (32, 26)
        for icons, big, small in ((self._tool_icons, *tool), (getattr(self, "_side_icons", []), *side)):
            for img, base in icons:
                img.set_from_icon_name(style.icon_name(base, icon_style))
                img.set_pixel_size(small if line else big)
                img.add_css_class("draco-icon")
                for role in ("go", "danger"):
                    img.remove_css_class(role)
                if style.ICON_ROLE.get(base):
                    img.add_css_class(style.ICON_ROLE[base])

    def _toggle_branch(self, key, button):
        kids = self._tree_children.get(key, [])
        show = not (kids and kids[0].get_visible())
        for r in kids:
            r.set_visible(show)
        button.set_icon_name("pan-down-symbolic" if show else "pan-end-symbolic")

    def _build_list(self):
        self.filter = Gtk.CustomFilter.new(self._filter_func)
        filtered = Gtk.FilterListModel(model=self.store, filter=self.filter)
        self.cv = Gtk.ColumnView(show_row_separators=False, show_column_separators=True,
                                 reorderable=True, hexpand=True, vexpand=True)
        self.cv.add_css_class("draco-list")
        sorted_model = Gtk.SortListModel(model=filtered, sorter=self.cv.get_sorter())
        self.selection = Gtk.MultiSelection(model=sorted_model)
        self.selection.connect("selection-changed", lambda *_: self._update_actions())
        self.selection.connect("items-changed", lambda *_: self._update_actions())
        self.cv.set_model(self.selection)
        self.cv.connect("activate", self._on_activate)

        it = lambda o: o.item  # noqa: E731
        self._add_column("File Name", self._name_factory(), expand=True,
                         key=lambda o: o.name.lower())
        self._add_column("Q", self._queue_factory(), key=lambda o: o.queue_text, width=34)
        self._add_column("Size", self._text_factory("size_text", xalign=1), key=lambda o: it(o).get("size", -1), width=90)
        self._add_column("Status", self._status_factory(), key=lambda o: o.fraction, width=120)
        self._add_column("Time left", self._text_factory("eta_text", xalign=1), key=lambda o: util.eta(it(o)) or 0, width=80)
        self._add_column("Transfer rate", self._text_factory("speed_text", xalign=1), key=lambda o: it(o).get("speed", 0), width=100)
        self._add_column("Last Try Date", self._text_factory("last_try_text"),
                         key=lambda o: it(o).get("finished") or it(o).get("last_try") or it(o).get("added") or 0, width=120)
        self._add_column("Description", self._text_factory("description"), key=lambda o: o.description, width=160)

        click = Gtk.GestureClick(button=3)
        click.connect("pressed", self._on_right_click)
        self.cv.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.cv.add_controller(keys)
        return Gtk.ScrolledWindow(child=self.cv)

    def _add_column(self, title, factory, key, expand=False, width=-1):
        col = Gtk.ColumnViewColumn(title=title, factory=factory, expand=expand, resizable=True)
        if width > 0:
            col.set_fixed_width(width)
        col.set_sorter(Gtk.CustomSorter.new(lambda a, b, _: _cmp(key(a), key(b)), None))
        self.cv.append_column(col)

    def _text_factory(self, prop, xalign=0):
        f = Gtk.SignalListItemFactory()
        f.connect("setup", lambda f, li: li.set_child(util.label(xalign=xalign)))

        def bind(f, li):
            li._b = li.get_item().bind_property(prop, li.get_child(), "label",
                                                GObject.BindingFlags.SYNC_CREATE)

        f.connect("bind", bind)
        f.connect("unbind", lambda f, li: li._b.unbind())
        return f

    def _name_factory(self, icon_size=16, end_ellipsis=False):
        f = Gtk.SignalListItemFactory()

        def setup(f, li):
            box = Gtk.Box(spacing=6)
            box.append(Gtk.Image(pixel_size=icon_size))
            lb = util.label()
            if end_ellipsis:
                from gi.repository import Pango
                lb.set_ellipsize(Pango.EllipsizeMode.END)
            box.append(lb)
            li.set_child(box)

        def bind(f, li):
            obj, box = li.get_item(), li.get_child()
            li._b = [obj.bind_property("icon", box.get_first_child(), "gicon", GObject.BindingFlags.SYNC_CREATE),
                     obj.bind_property("name", box.get_last_child(), "label", GObject.BindingFlags.SYNC_CREATE),
                     obj.bind_property("name", box, "tooltip-text", GObject.BindingFlags.SYNC_CREATE)]

        f.connect("setup", setup)
        f.connect("bind", bind)
        f.connect("unbind", lambda f, li: [b.unbind() for b in li._b])
        return f

    def _queue_factory(self):
        f = Gtk.SignalListItemFactory()
        f.connect("setup", lambda f, li: li.set_child(Gtk.Image(icon_name="draco-queue", pixel_size=14)))

        def bind(f, li):
            obj, img = li.get_item(), li.get_child()

            def upd(*_):
                img.set_visible(bool(obj.queue_text))
                img.set_tooltip_text(obj.queue_text)

            li._h = obj.connect("notify::queue-text", upd)
            upd()

        f.connect("bind", bind)
        f.connect("unbind", lambda f, li: li.get_item().disconnect(li._h))
        return f

    def _status_factory(self):
        f = Gtk.SignalListItemFactory()
        f.connect("setup", lambda f, li: li.set_child(util.label()))
        classes = {"complete": "draco-status-complete", "error": "draco-status-error",
                   "downloading": "draco-status-active", "connecting": "draco-status-active",
                   "merging": "draco-status-active"}

        def bind(f, li):
            obj, lb = li.get_item(), li.get_child()

            def upd(*_):
                lb.set_text(obj.status_text)
                lb.set_tooltip_text(obj.status_text)
                for c in set(classes.values()):
                    lb.remove_css_class(c)
                c = classes.get(obj.item.get("status"))
                if c:
                    lb.add_css_class(c)

            li._h = obj.connect("notify::status-text", upd)
            upd()

        f.connect("bind", bind)
        f.connect("unbind", lambda f, li: li.get_item().disconnect(li._h))
        return f

    def _build_statusbar(self):
        bar = Gtk.Box(spacing=12)
        bar.add_css_class("draco-statusbar")
        self.status_label = Gtk.Label(xalign=0, hexpand=True)
        bar.append(self.status_label)
        self.limit_toggle = Gtk.CheckButton(label="Speed limiter")
        self.limit_spin = Gtk.SpinButton.new_with_range(16, 1024 * 1024, 64)
        lim = self.app.settings["speed_limit_kbps"]
        self.limit_spin.set_value(lim or 512)
        self.limit_toggle.set_active(bool(lim))
        self.limit_toggle.connect("toggled", self._apply_limit)
        self.limit_spin.connect("value-changed", self._apply_limit)
        bar.append(self.limit_toggle)
        bar.append(self.limit_spin)
        bar.append(Gtk.Label(label="KB/s"))
        return bar

    def _apply_limit(self, *_):
        kbps = int(self.limit_spin.get_value()) if self.limit_toggle.get_active() else 0
        self.app.settings["speed_limit_kbps"] = kbps
        self.app.settings.save()
        self.manager.global_limiter.set_rate(kbps * 1024)
        a = self.lookup_action("speed-limiter")
        if a and a.get_state().get_boolean() != bool(kbps):
            a.set_state(GLib.Variant.new_boolean(bool(kbps)))

    def _update_actions(self):
        if not hasattr(self, "selection"):
            return
        sel = self.selected()
        has = bool(sel)
        done = any(i["status"] == "complete" for i in sel)
        for name in ("resume", "pause", "delete", "open-folder", "redownload", "refresh-address",
                     "properties", "progress", "copy-url", "remove-queue", "move-queue"):
            a = self.lookup_action(name)
            if a:
                a.set_enabled(has)
        for name in ("open", "open-with"):
            a = self.lookup_action(name)
            if a:
                a.set_enabled(done)

    # ---------------------------------------------------------- actions
    def _build_actions(self):
        def add(name, cb, param=None):
            a = Gio.SimpleAction.new(name, param)
            a.connect("activate", cb)
            self.add_action(a)

        add("add-url", lambda *_: self.app.show_add_url())
        add("resume", lambda *_: self._each(self._start_one))
        add("pause", lambda *_: self._each(lambda it: self.manager.pause(it["id"])))
        add("stop-all", lambda *_: self.manager.stop_all())
        add("delete", lambda *_: self._confirm_delete(self.selected()))
        add("delete-completed", lambda *_: self._confirm_delete(
            [i for i in self.manager.items.values() if i["status"] == "complete"], completed=True))
        add("prefs", lambda *_: self.app.show_prefs())
        add("scheduler", lambda *_: self.app.show_scheduler())
        add("start-queue", lambda *_: self.manager.start_queue(self._current_queue()))
        add("stop-queue", lambda *_: self.manager.stop_queue(self._current_queue()))
        add("grabber", lambda *_: self.app.show_grabber())
        add("batch", lambda *_: self.app.show_batch())
        add("import", lambda *_: self._import_links())
        add("export", lambda *_: self._export_links())
        add("open", lambda *_: self._each(lambda it: util.open_path(util.file_path(it))
                                          if it["status"] == "complete" else None))
        add("open-folder", lambda *_: self._each(lambda it: util.open_folder(util.file_path(it))))
        add("redownload", lambda *_: self._each(self._redownload))
        add("refresh-address", lambda *_: self._each(lambda it: self.app.show_refresh_address(it)))
        add("properties", lambda *_: self._each(lambda it: self.app.show_properties(it)))
        add("progress", lambda *_: self._each(lambda it: self.app.show_progress(it)))
        add("copy-url", lambda *_: self.get_clipboard().set("\n".join(i["url"] for i in self.selected())))
        add("remove-queue", lambda *_: self.manager.set_queue([i["id"] for i in self.selected()], ""))
        add("move-queue", lambda a, p: self.manager.set_queue([i["id"] for i in self.selected()], p.get_string()),
            GLib.VariantType.new("s"))
        add("open-with", lambda *_: self._each(self._open_with))
        add("batch-clipboard", lambda *_: self.get_clipboard().read_text_async(None, self._batch_clip))

        def toggle(name, initial, cb):
            a = Gio.SimpleAction.new_stateful(name, None, GLib.Variant.new_boolean(initial))

            def change(action, value):
                action.set_state(value)
                cb(value.get_boolean())

            a.connect("change-state", change)
            self.add_action(a)

        theme = Gio.SimpleAction.new_stateful("theme", GLib.VariantType.new("s"),
                                              GLib.Variant.new_string(self.app.settings.get("theme") or "classic"))

        def set_theme(action, value):
            action.set_state(value)
            self.app.set_theme(value.get_string())

        theme.connect("change-state", set_theme)
        self.add_action(theme)
        icon_style = Gio.SimpleAction.new_stateful("icon-style", GLib.VariantType.new("s"),
                                                   GLib.Variant.new_string(self.app.settings.get("icon_style", "auto")))

        def set_icon_style(action, value):
            action.set_state(value)
            self.app.settings["icon_style"] = value.get_string()
            self.app.settings.save()
            self.apply_icons()

        icon_style.connect("change-state", set_icon_style)
        self.add_action(icon_style)

        toggle("speed-limiter", bool(self.app.settings["speed_limit_kbps"]),
               lambda on: self.limit_toggle.get_active() != on and self.limit_toggle.set_active(on))
        toggle("show-categories", self.app.settings.get("show_categories", True),
               lambda on: self._set_view("show_categories", self.side_pane, on))
        toggle("show-toolbar", self.app.settings.get("show_toolbar", True),
               lambda on: self._set_view("show_toolbar", self.toolbar, on))

    def _set_view(self, key, widget, on):
        widget.set_visible(on)
        self.app.settings[key] = on
        self.app.settings.save()

    def _open_with(self, it):
        if it["status"] != "complete":
            return
        launcher = Gtk.FileLauncher(file=Gio.File.new_for_path(str(util.file_path(it))), always_ask=True)
        launcher.launch(self, None, None)

    def _batch_clip(self, cb, res):
        try:
            text = (cb.read_text_finish(res) or "").strip()
        except GLib.Error:
            text = ""
        self.app.show_batch(text if util.looks_like_url(text) else "")

    def _start_one(self, it):
        if it["status"] == "complete":
            return
        if self.manager.start(it["id"]) and self.app.settings["show_progress_dialog"]:
            self.app.show_progress(it)

    def _redownload(self, it):
        self.manager.reset(it["id"])
        self._start_one(it)

    def _each(self, fn):
        for it in self.selected():
            fn(it)

    def selected(self):
        out = []
        bits = self.selection.get_selection()
        model = self.selection
        for i in range(bits.get_size()):
            obj = model.get_item(bits.get_nth(i))
            if obj:
                out.append(obj.item)
        return out

    def _current_queue(self):
        if self.filter_key[0] == "queue":
            return self.filter_key[1]
        for it in self.selected():
            if it.get("queue"):
                return it["queue"]
        return self.manager.queue_names()[0]

    def _confirm_delete(self, items, completed=False):
        if not items:
            return
        d = Adw.AlertDialog(heading=f"Delete {len(items)} download(s)?",
                            body="Removes them from the list. Unfinished partial data is always discarded.")
        check = Gtk.CheckButton(label="Also delete the downloaded files from disk")
        d.set_extra_child(check)
        d.add_response("cancel", "Cancel")
        d.add_response("delete", "Delete")
        d.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_resp(dlg, resp):
            if resp == "delete":
                self.manager.remove([i["id"] for i in items], delete_files=check.get_active())

        d.connect("response", on_resp)
        d.present(self)

    def _on_right_click(self, gesture, n, x, y):
        menu = Gio.Menu()
        s1 = Gio.Menu()
        s1.append("Open", "win.open")
        s1.append("Open Folder", "win.open-folder")
        s1.append("Show Progress", "win.progress")
        menu.append_section(None, s1)
        s2 = Gio.Menu()
        s2.append("Resume", "win.resume")
        s2.append("Stop", "win.pause")
        s2.append("Redownload", "win.redownload")
        s2.append("Refresh Download Address…", "win.refresh-address")
        menu.append_section(None, s2)
        qmenu = Gio.Menu()
        for q in self.manager.queue_names():
            qmenu.append(q, f"win.move-queue('{q}')")
        s3 = Gio.Menu()
        s3.append_submenu("Move to Queue", qmenu)
        s3.append("Remove from Queue", "win.remove-queue")
        menu.append_section(None, s3)
        s4 = Gio.Menu()
        s4.append("Copy Address", "win.copy-url")
        s4.append("Properties", "win.properties")
        s4.append("Delete", "win.delete")
        menu.append_section(None, s4)
        pop = Gtk.PopoverMenu(menu_model=menu, has_arrow=False)
        pop.set_parent(self.cv)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        pop.set_pointing_to(rect)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        pop.popup()

    def _on_key(self, ctrl, keyval, keycode, state):
        if keyval == Gdk.KEY_Delete:
            self._confirm_delete(self.selected())
            return True
        if keyval == Gdk.KEY_v and state & Gdk.ModifierType.CONTROL_MASK:
            self.get_clipboard().read_text_async(None, self._paste_done)
            return True
        return False

    def _paste_done(self, cb, res):
        try:
            text = cb.read_text_finish(res)
        except GLib.Error:
            return
        urls = [l.strip() for l in (text or "").splitlines() if util.looks_like_url(l)]
        if len(urls) == 1:
            self.app.request_download({"url": urls[0]})
        elif urls:
            self.app.show_links(urls, "Pasted links")

    def _on_activate(self, cv, pos):
        obj = self.selection.get_item(pos)
        if not obj:
            return
        it = obj.item
        if it["status"] == "complete":
            util.open_path(util.file_path(it))
        elif not self.open_detail(it, pin=True):
            self.app.show_progress(it)

    def _on_drop(self, target, value, x, y):
        urls = [l.strip() for l in (value or "").splitlines() if util.looks_like_url(l)]
        if len(urls) == 1:
            self.app.request_download({"url": urls[0]})
        elif urls:
            self.app.show_links(urls, "Dropped links")
        return bool(urls)

    def _import_links(self):
        dlg = Gtk.FileDialog(title="Import links from text file")

        def done(d, res):
            try:
                f = d.open_finish(res)
            except GLib.Error:
                return
            ok, data, _ = f.load_contents(None)
            urls = [l.strip() for l in data.decode("utf-8", "replace").splitlines() if util.looks_like_url(l)]
            if urls:
                self.app.show_links(urls, "Imported links")

        dlg.open(self, None, done)

    def _export_links(self):
        dlg = Gtk.FileDialog(title="Export download list", initial_name="downloads.txt")

        def done(d, res):
            try:
                f = d.save_finish(res)
            except GLib.Error:
                return
            text = "\n".join(i["url"] for i in self.manager.items.values()) + "\n"
            f.replace_contents(text.encode(), None, False, Gio.FileCreateFlags.NONE, None)
            self.toast("Exported %d links" % len(self.manager.items))

        dlg.save(self, None, done)

    # -------------------------------------------------------- filtering
    def _on_sidebar(self, box, row):
        if row is None or not hasattr(row, "key"):
            return
        self.filter_key = row.key
        self._refilter()

    def _refilter(self):
        if hasattr(self, "filter"):  # sidebar is built before the list
            self.filter.changed(Gtk.FilterChange.DIFFERENT)

    def _filter_func(self, obj):
        it = obj.item
        text = self.search.get_text().strip().lower() if hasattr(self, "search") else ""
        if text and text not in (it.get("filename") or "").lower() and text not in it["url"].lower():
            return False
        if self.layout == "modern" and self.tab_key != "all":
            if self.tab_key == "completed" and it["status"] != "complete":
                return False
            if self.tab_key == "downloading" and it["status"] not in ACTIVE:
                return False
        kind, val = self.filter_key
        if kind == "cat":
            return it.get("category") == val
        if kind == "unfinished":
            return it["status"] != "complete"
        if kind == "downloading":
            return it["status"] in ACTIVE
        if kind == "finished":
            return it["status"] == "complete"
        if kind == "queue":
            return it.get("queue") == val
        return True

    # -------------------------------------------------- manager events
    def _add_obj(self, it):
        obj = DownloadObj(it)
        self.objs[it["id"]] = obj
        self.store.append(obj)

    def _on_manager_event(self, event, payload):
        if event == "changed":
            self._changed.add(payload["id"])
        else:
            GLib.idle_add(self._handle_event, event, payload)

    def _handle_event(self, event, payload):
        if getattr(self, "cosmic", None) is not None and self.layout == "modern" and isinstance(payload, dict):
            self.cosmic.note(event, payload)
        if event == "added" and payload["id"] not in self.objs:
            self._add_obj(payload)
        elif event == "removed":
            obj = self.objs.pop(payload["id"], None)
            if obj:
                ok, pos = self.store.find(obj)
                if ok:
                    self.store.remove(pos)
        elif event in ("finished", "reordered", "queue"):
            for obj in self.objs.values():
                obj.refresh()
            self._refilter()
        return False

    def _tick(self):
        changed, self._changed = self._changed, set()
        for item_id in changed:
            obj = self.objs.get(item_id)
            if obj:
                obj.refresh()
        if self.layout == "modern":
            self._modern_tick()
            self.manager.save_if_dirty()
            return True
        active = [i for i in self.manager.items.values() if i["status"] in ACTIVE]
        speed = sum(i.get("speed", 0) or 0 for i in active)
        running = [q for q, r in self.manager.queue_running.items() if r]
        txt = f"{len(active)} active   ↓ {fmt_speed(speed) or '0 B/s'}   {len(self.manager.items)} total"
        if running:
            txt += "   Running: " + ", ".join(running)
        self.status_label.set_text(txt)
        self.manager.save_if_dirty()
        return True

    def toast(self, text):
        self.toast_overlay.add_toast(Adw.Toast(title=text, timeout=3))

    def _on_close(self, *_):
        if self.manager.tasks or self.app.settings.get("background_on_close", True):
            # Keep running hidden: no window means no taskbar/dock entry, but browser downloads are
            # still caught instantly and progress windows still appear. Open Draco again to show it.
            self.set_visible(False)
            if not getattr(self.app, "_told_background", False):   # say it once per session
                self.app._told_background = True
                body = ("Downloads continue in the background." if self.manager.tasks else
                        "Draco keeps running to catch browser downloads.")
                self.app.notify_text("Draco is running in the background",
                                     body + (" Click the Draco icon in the top bar to show it again or quit."
                                             if self.app.tray else " Open Draco from the app menu to show it again."),
                                     quit_button=True)
            return True
        # Nothing downloading: really exit (the app holds itself alive, so closing the window alone isn't enough).
        self.app._quit()
        return True
