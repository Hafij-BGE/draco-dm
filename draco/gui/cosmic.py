"""Cosmic Dashboard: an overview of all transfers for the Galaxy Explorer theme.

Active downloads orbit the Draco star as planets (colour = category, ring = progress); around
it sit the queues ("fleet"), categories, a speed trend, real-time alerts and telemetry.
"""

import math
import shutil
import time
from collections import deque

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Graphene, Gsk, Gtk  # noqa: E402

from ..manager import ACTIVE  # noqa: E402
from . import util  # noqa: E402
from .util import fmt_size, fmt_speed  # noqa: E402
from .widgets import HAS_PATHS, Sparkline, _point, _stop, rgba  # noqa: E402

CAT_COLORS = {"Compressed": ("#fde68a", "#f59e0b"), "Documents": ("#93c5fd", "#2563eb"),
              "Music": ("#f9a8d4", "#db2777"), "Programs": ("#c4b5fd", "#7c3aed"),
              "Video": ("#d8b4fe", "#9333ea"), "General": ("#a5f3fc", "#0891b2")}


def _cat_colors(cat):
    return CAT_COLORS.get(cat or "General", CAT_COLORS["General"])


class CosmicMap(Gtk.Widget):
    """Draco star in the middle, active downloads orbiting it, waiting ones on the outer ring."""

    def __init__(self):
        super().__init__(hexpand=True, vexpand=True, height_request=320)
        self.items = []
        self._t0 = time.monotonic()
        self._tick = None

    def set_items(self, items):
        self.items = items
        self.queue_draw()

    def start(self):
        if self._tick is None:
            self._tick = self.add_tick_callback(lambda *_: (self.queue_draw(), True)[1])

    def stop(self):
        if self._tick is not None:
            self.remove_tick_callback(self._tick)
            self._tick = None

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        if w < 50 or h < 50:
            return
        cx, cy = w / 2, h / 2
        rx, ry = w * 0.44, h * 0.42
        t = time.monotonic() - self._t0
        # orbits
        if HAS_PATHS:
            for k in (0.38, 0.68, 1.0):
                orbit = Gsk.PathBuilder.new()
                orbit.move_to(cx + rx * k, cy)
                for i in range(1, 73):
                    a = i / 72 * 2 * math.pi
                    orbit.line_to(cx + rx * k * math.cos(a), cy + ry * k * math.sin(a))
                snap.append_stroke(orbit.to_path(), Gsk.Stroke.new(1), rgba("#8ea2ff", 0.18))
        # the star
        glow = Graphene.Rect().init(cx - 70, cy - 70, 140, 140)
        snap.append_radial_gradient(glow, _point(cx, cy), 70, 70, 0, 1,
                                    [_stop(0, rgba("#fff7d6", 0.95)), _stop(0.18, rgba("#ffd27a", 0.8)),
                                     _stop(0.45, rgba("#9b6bff", 0.35)), _stop(1, rgba("#2a1d6b", 0.0))])
        lay = self.create_pango_layout("DRACO")
        tw, th = lay.get_pixel_size()
        snap.save()
        snap.translate(_point(cx - tw / 2, cy + 34))
        snap.append_layout(lay, rgba("#c9d2ff", 0.85))
        snap.restore()
        active = [i for i in self.items if i["status"] in ACTIVE]
        waiting = [i for i in self.items if i["status"] not in ACTIVE and i["status"] != "complete"][:10]
        if not active and not waiting:
            lay = self.create_pango_layout("No transfers in flight — add a download to launch one")
            tw, th = lay.get_pixel_size()
            snap.save()
            snap.translate(_point(cx - tw / 2, cy + ry * 0.38 + 26))
            snap.append_layout(lay, rgba("#9aa4d6"))
            snap.restore()
        for rank, (group, k, speed, size) in enumerate(((active, 0.68, 0.18, 15), (waiting, 1.0, 0.05, 9))):
            n = max(1, len(group))
            for i, it in enumerate(group):
                a = 2 * math.pi * i / n + t * speed * (1 if rank == 0 else -1) + rank
                px, py = cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)
                self._planet(snap, it, px, py, size, labelled=(rank == 0))

    def _planet(self, snap, it, x, y, r, labelled):
        c1, c2 = _cat_colors(it.get("category"))
        box = Graphene.Rect().init(x - r, y - r, 2 * r, 2 * r)
        stops = [_stop(0, rgba(c1)), _stop(0.75, rgba(c2)), _stop(1, rgba(c2))]
        if HAS_PATHS:
            disc = Gsk.PathBuilder.new()
            disc.add_circle(_point(x, y), r)
            snap.push_fill(disc.to_path(), Gsk.FillRule.WINDING)
            snap.append_radial_gradient(box, _point(x - r * 0.35, y - r * 0.35), r * 1.7, r * 1.7, 0, 1, stops)
            snap.pop()
        else:
            snap.append_color(rgba(c2), box)
        frac = util.fraction(it)
        if HAS_PATHS and frac > 0:
            ring = Gsk.PathBuilder.new()
            rr = r + 5
            a0 = -math.pi / 2
            a1 = a0 + 2 * math.pi * min(frac, 0.9999)
            ring.move_to(x + rr * math.cos(a0), y + rr * math.sin(a0))
            ring.svg_arc_to(rr, rr, 0, frac > 0.5, True, x + rr * math.cos(a1), y + rr * math.sin(a1))
            st = Gsk.Stroke.new(3)
            st.set_line_cap(Gsk.LineCap.ROUND)
            snap.append_stroke(ring.to_path(), st, rgba("#4fd1ff" if it["status"] != "error" else "#ff5b7b"))
        if labelled:
            name = it.get("filename") or "download"
            name = name if len(name) <= 26 else name[:23] + "…"
            text = f"{name}\n{frac * 100:.0f}%  ·  {fmt_speed(it.get('speed')) or '—'}"
            lay = self.create_pango_layout(text)
            tw, th = lay.get_pixel_size()
            snap.save()
            snap.translate(_point(x - tw / 2, y + r + 8))
            snap.append_layout(lay, rgba("#e8ecff"))
            snap.restore()


def _card(title, expand=False):
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, vexpand=expand)
    card.add_css_class("dm-card")
    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=14, margin_end=14,
                    margin_top=12, margin_bottom=12, vexpand=expand)
    inner.append(util.label(title.upper(), css=["dm-cosmic-title"], ellipsize=False))
    card.append(inner)
    return card, inner


class CosmicDashboard(Gtk.Box):
    def __init__(self, window):
        super().__init__(spacing=12, hexpand=True, vexpand=True)
        self.window = window
        self.manager = window.manager
        self.alerts = deque(maxlen=8)
        self.received = 0.0
        self._last = time.monotonic()

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, width_request=280, hexpand=False)
        card, self.fleet = _card("Fleet · queues")
        left.append(card)
        card, self.cats = _card("Categories", expand=True)
        left.append(card)
        self.append(left)

        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, hexpand=True)
        card, inner = _card("Transfer flow", expand=True)
        self.map = CosmicMap()
        inner.append(self.map)
        center.append(card)
        card, inner = _card("Speed trend")
        row = Gtk.Box(spacing=14)
        self.speed_lbl = util.label("0 B/s", css=["dm-stat-value"], ellipsize=False)
        row.append(self.speed_lbl)
        self.trend = Sparkline(height=70, samples=240)
        row.append(self.trend)
        inner.append(row)
        center.append(card)
        self.append(center)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, width_request=300, hexpand=False)
        card, inner = _card("Real-time alerts", expand=True)
        self.alert_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        inner.append(self.alert_box)
        right.append(card)
        card, self.telemetry = _card("Telemetry")
        self.tele = {}
        for key, title in (("conns", "Active connections"), ("received", "Received this session"),
                           ("rate", "Success rate"), ("disk", "Free disk space"), ("limit", "Speed limit")):
            r = Gtk.Box(spacing=8)
            r.append(util.label(title, css=["dm-ring-label"], ellipsize=False))
            r.append(Gtk.Box(hexpand=True))
            v = util.label("—", xalign=1, ellipsize=False)
            r.append(v)
            self.tele[key] = v
            self.telemetry.append(r)
        right.append(card)
        self.append(right)
        self._fleet_rows = {}
        self._cat_rows = {}
        self._render_alerts()

    # ------------------------------------------------------------------ events
    def note(self, event, item):
        name = item.get("filename") or item.get("url", "")
        if event == "added":
            self.alerts.appendleft(("folder-download-symbolic", f"Added {name}", time.time()))
        elif event == "finished" and item.get("status") == "complete":
            self.alerts.appendleft(("draco-m-finished", f"Completed {name}", time.time()))
        elif event == "finished" and item.get("status") == "error":
            self.alerts.appendleft(("dialog-error-symbolic", f"Failed {name}: {item.get('error', '')}", time.time()))
        else:
            return
        self._render_alerts()

    def _render_alerts(self):
        child = self.alert_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.alert_box.remove(child)
            child = nxt
        if not self.alerts:
            self.alert_box.append(util.label("All quiet. Finished and failed downloads show up here.",
                                             css=["dm-ring-label"], wrap=True))
            return
        for icon, text, when in self.alerts:
            r = Gtk.Box(spacing=8)
            r.append(Gtk.Image(icon_name=icon, pixel_size=16))
            lb = util.label(text)
            lb.set_hexpand(True)
            lb.set_tooltip_text(text)
            r.append(lb)
            r.append(util.label(time.strftime("%H:%M", time.localtime(when)), css=["dm-ring-label"], ellipsize=False))
            self.alert_box.append(r)

    # ------------------------------------------------------------------ refresh
    def update(self, speed):
        now = time.monotonic()
        self.received += speed * (now - self._last)
        self._last = now
        items = list(self.manager.items.values())
        self.map.set_items(items)
        self.trend.push(speed)
        self.speed_lbl.set_text(fmt_speed(speed) or "0 B/s")
        self._update_fleet(items)
        self._update_cats(items)
        done = sum(1 for i in items if i["status"] == "complete")
        failed = sum(1 for i in items if i["status"] == "error")
        conns = 0
        for task_id in list(self.manager.tasks):
            it = self.manager.items.get(task_id) or {}
            conns += sum(1 for sg in it.get("segments") or [] if sg["e"] < 0 or sg["p"] < sg["e"]) or 1
        self.tele["conns"].set_text(str(conns))
        self.tele["received"].set_text(fmt_size(int(self.received)))
        self.tele["rate"].set_text(f"{done * 100 // (done + failed)} %" if done + failed else "—")
        try:
            free = shutil.disk_usage(self.window.app.settings.base_dir()).free
            self.tele["disk"].set_text(fmt_size(free))
        except OSError:
            self.tele["disk"].set_text("—")
        lim = self.window.app.settings["speed_limit_kbps"]
        self.tele["limit"].set_text(f"{lim} KB/s" if lim else "Off")

    def _update_fleet(self, items):
        for name in self.manager.queue_names():
            if name not in self._fleet_rows:
                r = Gtk.Box(spacing=8)
                words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
                title = util.label(name, ellipsize=True)
                state = util.label("", css=["dm-ring-label"], ellipsize=False)
                words.append(title)
                words.append(state)
                r.append(Gtk.Image(icon_name="draco-m-queue", pixel_size=22))
                r.append(words)
                btn = Gtk.Button(valign=Gtk.Align.CENTER)
                btn.add_css_class("dm-icon-btn")
                btn.connect("clicked", lambda b, q=name: (self.manager.stop_queue(q) if self.manager.queue_running.get(q)
                                                          else self.manager.start_queue(q)))
                r.append(btn)
                self.fleet.append(r)
                self._fleet_rows[name] = (state, btn)
            state, btn = self._fleet_rows[name]
            q = [i for i in items if i.get("queue") == name]
            waiting = sum(1 for i in q if i["status"] != "complete")
            running = bool(self.manager.queue_running.get(name))
            state.set_text(f"{'Running' if running else 'Docked'} · {waiting} waiting · {len(q)} total")
            btn.set_icon_name("draco-m-stop-queue" if running else "draco-m-start-queue")
            btn.set_tooltip_text("Stop queue" if running else "Start queue")

    def _update_cats(self, items):
        names = [c["name"] for c in self.window.app.settings["categories"]] + ["General"]
        total = sum(max(0, i.get("size", 0) or 0) for i in items) or 1
        for name in names:
            if name not in self._cat_rows:
                r = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
                top = Gtk.Box(spacing=8)
                base = f"cat-{name.lower()}"
                top.append(Gtk.Image(icon_name=f"draco-m-{base}" if name.lower() in
                                     ("compressed", "documents", "music", "programs", "video", "general")
                                     else "draco-m-folder", pixel_size=18))
                top.append(util.label(name, ellipsize=False))
                top.append(Gtk.Box(hexpand=True))
                count = util.label("", css=["dm-ring-label"], ellipsize=False)
                top.append(count)
                r.append(top)
                bar = Gtk.ProgressBar()
                bar.add_css_class("dm-progress")
                bar.add_css_class("dm-thin")
                r.append(bar)
                self.cats.append(r)
                self._cat_rows[name] = (count, bar)
            count, bar = self._cat_rows[name]
            mine = [i for i in items if (i.get("category") or "General") == name]
            size = sum(max(0, i.get("size", 0) or 0) for i in mine)
            count.set_text(f"{len(mine)} · {fmt_size(size) if size else '0 B'}")
            bar.set_fraction(size / total)

    def set_active(self, on):
        (self.map.start if on else self.map.stop)()
