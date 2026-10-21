"""Small drawn widgets for the dashboard themes: speed graph, stat rings, connection map."""

import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, Graphene, Gsk, Gtk  # noqa: E402

from . import style, util  # noqa: E402


HAS_PATHS = hasattr(Gsk, "PathBuilder")     # GTK 4.14+; older GTK just shows the numbers


def rgba(spec, alpha=None):
    c = Gdk.RGBA()
    c.parse(spec)
    if alpha is not None:
        c.alpha = alpha
    return c


def _point(x, y):
    return Graphene.Point().init(x, y)


def _stop(offset, color):
    s = Gsk.ColorStop()
    s.offset, s.color = offset, color
    return s


class Sparkline(Gtk.Widget):
    """Line graph of the last speed samples, filled with a fading gradient."""

    def __init__(self, height=48, samples=60):
        super().__init__(hexpand=True, height_request=height)
        self.values = [0.0] * samples

    def push(self, value):
        self.values = self.values[1:] + [max(0.0, float(value or 0))]
        self.queue_draw()

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        if w < 4 or h < 4 or not HAS_PATHS:
            return
        pal = dict(style.current_palette() or {})
        if getattr(self, "colors", None):
            pal["a1"], pal["a2"] = self.colors
        top = max(self.values) or 1.0
        n = len(self.values)
        pts = [(i / (n - 1) * w, h - 3 - (v / top) * (h - 8)) for i, v in enumerate(self.values)]
        line = Gsk.PathBuilder.new()
        line.move_to(*pts[0])
        for x, y in pts[1:]:
            line.line_to(x, y)
        fill = Gsk.PathBuilder.new()
        fill.move_to(0, h)
        for x, y in pts:
            fill.line_to(x, y)
        fill.line_to(w, h)
        fill.close()
        bounds = Graphene.Rect().init(0, 0, w, h)
        a1, a2 = rgba(pal.get("a1", "#5a5cff")), rgba(pal.get("a2", "#1fb8ff"))
        snap.push_fill(fill.to_path(), Gsk.FillRule.WINDING)
        snap.append_linear_gradient(bounds, _point(0, 0), _point(0, h),
                                    [_stop(0, rgba(pal.get("a2", "#1fb8ff"), 0.45)),
                                     _stop(1, rgba(pal.get("a1", "#5a5cff"), 0.0))])
        snap.pop()
        stroke = Gsk.Stroke.new(2.2)
        stroke.set_line_join(Gsk.LineJoin.ROUND)
        snap.push_stroke(line.to_path(), stroke)
        snap.append_linear_gradient(bounds, _point(0, 0), _point(w, 0), [_stop(0, a1), _stop(1, a2)])
        snap.pop()


class Ring(Gtk.Widget):
    """Circular counter: a coloured arc around a number."""

    def __init__(self, color_key, size=44, colors=None, width=4):
        super().__init__(width_request=size, height_request=size, valign=Gtk.Align.CENTER)
        self.color_key = color_key
        self.colors = colors          # (arc start, arc end, track) for the light themes
        self.width = width
        self.value, self.fraction = 0, 0.0
        self.label = Gtk.Label(label="0")
        self.label.add_css_class("dm-ring-num")
        self.label.set_parent(self)

    def set_value(self, value, fraction):
        if (value, fraction) != (self.value, self.fraction):
            self.value, self.fraction = value, fraction
            self.label.set_text(str(value))
            self.queue_draw()

    def do_size_allocate(self, width, height, baseline):
        self.label.allocate(width, height, baseline, None)

    def do_measure(self, orientation, for_size):
        return (self.get_size_request()[0], self.get_size_request()[0], -1, -1)

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        r = min(w, h) / 2 - self.width / 2 - 1
        cx, cy = w / 2, h / 2
        pal = style.current_palette() or {}
        color = {"active": "#c04bff", "done": pal.get("ok", "#36e07a"), "queue": pal.get("warn", "#ffb020")}
        if HAS_PATHS:
            track = Gsk.PathBuilder.new()
            track.add_circle(_point(cx, cy), r)
            snap.append_stroke(track.to_path(), Gsk.Stroke.new(self.width),
                               rgba(self.colors[2]) if self.colors else rgba(pal.get("fg", "#ffffff"), 0.12))
        frac = min(1.0, max(0.0, self.fraction))
        if frac > 0 and HAS_PATHS:
            arc = Gsk.PathBuilder.new()
            a0 = -math.pi / 2
            a1 = a0 + 2 * math.pi * min(frac, 0.9999)
            arc.move_to(cx + r * math.cos(a0), cy + r * math.sin(a0))
            arc.svg_arc_to(r, r, 0, frac > 0.5, True, cx + r * math.cos(a1), cy + r * math.sin(a1))
            st2 = Gsk.Stroke.new(self.width)
            st2.set_line_cap(Gsk.LineCap.ROUND)
            if self.colors:
                b = Graphene.Rect().init(0, 0, w, h)
                snap.push_stroke(arc.to_path(), st2)
                snap.append_linear_gradient(b, _point(0, 0), _point(w, h),
                                            [_stop(0, rgba(self.colors[0])), _stop(1, rgba(self.colors[1]))])
                snap.pop()
            else:
                snap.append_stroke(arc.to_path(), st2, rgba(color[self.color_key]))
        self.snapshot_child(self.label, snap)


class SegmentMap(Gtk.Widget):
    """Bar showing which byte ranges are downloaded and where each connection is."""

    def __init__(self, item, pstyle=None, colors=None):
        super().__init__(hexpand=True, height_request=20)
        self.item = item
        self.pstyle = pstyle
        self.colors = colors          # one colour per connection (light Classic window)

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        bg, done, head = (rgba(c) for c in style.seg_colors(self.pstyle))

        def rect(x, width, color):
            snap.append_color(color, Graphene.Rect().init(x, 0, max(0.0, width), h))

        rect(0, w, bg)
        it = self.item
        size = it.get("size", -1)
        segs = it.get("segments") or []
        if size and size > 0 and segs:
            for i, sg in enumerate(sorted(segs, key=lambda g: g["s"])):
                col = rgba(self.colors[i % len(self.colors)]) if self.colors else done
                rect(sg["s"] / size * w, (sg["p"] - sg["s"]) / size * w, col)
            for sg in segs:
                if sg["e"] >= 0 and sg["p"] < sg["e"]:
                    rect(sg["p"] / size * w, 2, head)
        else:
            rect(0, util.fraction(it) * w, done)
