"""Scheduler: manage queues, their timetable, and the files inside them."""

import re

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from . import util  # noqa: E402
from .dialogs import Dialog  # noqa: E402

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
AFTER = [("none", "Do nothing"), ("exit", "Exit Draco"), ("suspend", "Suspend computer"),
         ("hibernate", "Hibernate computer"), ("shutdown", "Shut down computer")]
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class SchedulerDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Scheduler", 860, 620)
        self.manager = app.manager
        self.settings = app.settings
        self.current = None

        paned = Gtk.Paned(position=200, vexpand=True)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.qlist = Gtk.ListBox()
        self.qlist.add_css_class("navigation-sidebar")
        self.qlist.connect("row-selected", self._on_select)
        left.append(Gtk.ScrolledWindow(child=self.qlist, vexpand=True))
        lb = Gtk.Box(spacing=4)
        add = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="New queue")
        add.connect("clicked", lambda *_: self._new_queue())
        rem = Gtk.Button(icon_name="list-remove-symbolic", tooltip_text="Delete queue")
        rem.connect("clicked", lambda *_: self._delete_queue())
        lb.append(add)
        lb.append(rem)
        left.append(lb)
        paned.set_start_child(left)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_start=12)
        stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcher(stack=stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        right.append(switcher)
        right.append(stack)
        paned.set_end_child(right)
        self.body.append(paned)

        # --- schedule page
        page = Adw.PreferencesPage()
        grp = Adw.PreferencesGroup(title="Timetable")
        self.enabled = Adw.SwitchRow(title="Start this queue on a schedule")
        self.start_t = Adw.EntryRow(title="Start time (HH:MM, 24h)")
        self.stop_t = Adw.EntryRow(title="Stop time (HH:MM, optional)")
        self.once = Adw.ComboRow(title="Repeat", model=Gtk.StringList.new(["Every selected day", "Only once"]))
        days_row = Adw.ActionRow(title="Days")
        days_box = Gtk.Box(spacing=2, valign=Gtk.Align.CENTER)
        days_box.add_css_class("linked")
        self.day_btns = []
        for d in DAYS:
            b = Gtk.ToggleButton(label=d)
            self.day_btns.append(b)
            days_box.append(b)
        days_row.add_suffix(days_box)
        for w in (self.enabled, self.start_t, self.stop_t, self.once, days_row):
            grp.add(w)
        page.add(grp)
        grp2 = Adw.PreferencesGroup(title="Behaviour")
        self.max_active = Adw.SpinRow.new_with_range(1, 20, 1)
        self.max_active.set_title("Download at the same time")
        self.retry = Adw.SwitchRow(title="Retry files that failed")
        self.after = Adw.ComboRow(title="When done", model=Gtk.StringList.new([a[1] for a in AFTER]))
        for w in (self.max_active, self.retry, self.after):
            grp2.add(w)
        page.add(grp2)
        stack.add_titled_with_icon(page, "schedule", "Schedule", "alarm-symbolic")

        # --- files page
        files = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.flist = Gtk.ListBox()
        self.flist.add_css_class("boxed-list")
        files.append(Gtk.ScrolledWindow(child=self.flist, vexpand=True, min_content_height=300))
        fb = Gtk.Box(spacing=6)
        for icon, tip, cb in (("go-up-symbolic", "Move up", lambda: self._move(-1)),
                              ("go-down-symbolic", "Move down", lambda: self._move(1)),
                              ("list-remove-symbolic", "Remove from queue", self._remove_file)):
            b = Gtk.Button(icon_name=icon, tooltip_text=tip)
            b.connect("clicked", lambda _b, f=cb: f())
            fb.append(b)
        files.append(fb)
        stack.add_titled_with_icon(files, "files", "Files in queue", "view-list-symbolic")

        self.button("Close", self._close)
        self.button("Stop", lambda: (self._apply(), self.manager.stop_queue(self.current)))
        self.button("Start Now", lambda: (self._apply(), self.manager.start_queue(self.current)))
        self.button("Apply", self._apply, suggested=True)
        self._fill_queues()
        self.finish()

    # -- queues list
    def _fill_queues(self, select=None):
        self.qlist.remove_all()
        first = None
        for q in self.settings["queues"]:
            row = Gtk.ListBoxRow(child=util.label(q["name"]))
            row.qname = q["name"]
            self.qlist.append(row)
            if first is None or q["name"] == select:
                first = row
        if first:
            self.qlist.select_row(first)

    def _on_select(self, lb, row):
        if row is None:
            return
        if self.current:
            self._apply(quiet=True)
        self.current = row.qname
        q = self.manager.queue_conf(self.current)
        s = q.setdefault("schedule", {})
        self.enabled.set_active(s.get("enabled", False))
        self.start_t.set_text(s.get("start", ""))
        self.stop_t.set_text(s.get("stop", ""))
        self.once.set_selected(1 if s.get("once") else 0)
        days = s.get("days", list(range(7)))
        for i, b in enumerate(self.day_btns):
            b.set_active(i in days)
        self.max_active.set_value(q.get("max_active", 1))
        self.retry.set_active(s.get("retry_failed", True))
        keys = [a[0] for a in AFTER]
        self.after.set_selected(keys.index(s.get("after", "none")) if s.get("after", "none") in keys else 0)
        self._fill_files()

    def _fill_files(self):
        self.flist.remove_all()
        for it in self.manager.queue_items(self.current):
            row = Gtk.ListBoxRow(child=util.label(f"{it.get('filename') or it['url']}   —   {util.status_text(it)}",
                                                  css=[]))
            row.item_id = it["id"]
            row.get_child().set_margin_start(8)
            row.get_child().set_margin_top(4)
            row.get_child().set_margin_bottom(4)
            self.flist.append(row)

    def _apply(self, quiet=False):
        if not self.current:
            return
        q = self.manager.queue_conf(self.current)
        start, stop = self.start_t.get_text().strip(), self.stop_t.get_text().strip()
        ok = True
        for row, val in ((self.start_t, start), (self.stop_t, stop)):
            if val and not TIME_RE.match(val):
                row.add_css_class("error")
                ok = False
            else:
                row.remove_css_class("error")
        if not ok:
            return
        q["max_active"] = int(self.max_active.get_value())
        q["schedule"] = {
            "enabled": self.enabled.get_active() and bool(start),
            "start": start, "stop": stop,
            "days": [i for i, b in enumerate(self.day_btns) if b.get_active()],
            "once": self.once.get_selected() == 1,
            "after": AFTER[self.after.get_selected()][0],
            "retry_failed": self.retry.get_active(),
        }
        self.settings.save()
        if not quiet and self.app.window:
            self.app.window.toast(f"Saved “{self.current}”")

    def _close(self):
        self._apply(quiet=True)
        self.close()

    def _new_queue(self):
        names = self.manager.queue_names()
        n = 1
        while f"Queue {n}" in names:
            n += 1
        name = f"Queue {n}"
        self.settings["queues"].append({"name": name, "max_active": 2, "schedule": {
            "enabled": False, "start": "", "stop": "", "days": list(range(7)), "once": False,
            "after": "none", "retry_failed": True}})
        self.settings.save()
        self._fill_queues(select=name)
        self.app.refresh_sidebar()

    def _delete_queue(self):
        if not self.current or self.current == self.manager.queue_names()[0]:
            return  # the main queue always exists
        self.manager.stop_queue(self.current)
        self.manager.set_queue([i["id"] for i in self.manager.queue_items(self.current)], "")
        self.settings["queues"] = [q for q in self.settings["queues"] if q["name"] != self.current]
        self.settings.save()
        self.current = None
        self._fill_queues()
        self.app.refresh_sidebar()

    def _selected_file(self):
        row = self.flist.get_selected_row()
        return row.item_id if row else None

    def _move(self, delta):
        item_id = self._selected_file()
        if item_id:
            self.manager.move_in_queue(item_id, delta)
            self._fill_files()
            for row in list(self._rows()):
                if row.item_id == item_id:
                    self.flist.select_row(row)

    def _rows(self):
        r = self.flist.get_first_child()
        while r:
            yield r
            r = r.get_next_sibling()

    def _remove_file(self):
        item_id = self._selected_file()
        if item_id:
            self.manager.set_queue([item_id], "")
            self._fill_files()
