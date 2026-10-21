"""Live planet in the details pane of the picture themes.

It shows the selected download's real state (scene_model.py) in five stages: Initializing,
Downloading, High speed, Finalizing and Completed, plus Paused and Error. It is drawn with GTK's
render nodes (GPU when available) at up to 30 frames a second, stops while the pane is hidden or
the window is minimised, and is a still picture with Reduce motion. In light themes the scene
fades into the white pane, in dark themes into the dark one.
Pictures: tools/make_scene_art.py (scene-planet.jpg, scene-nebula-a/b.png)."""

import math
import random
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, GLib, Graphene, Gsk, Gtk  # noqa: E402

from . import style  # noqa: E402
from .scene_model import SceneMotion, scene_state  # noqa: E402
from .widgets import HAS_PATHS  # noqa: E402

FPS = 30                        # while a download moves
CALM_FPS = 15                   # nothing selected, paused, completed, error
OVERLAP = 70                    # the planet's area reaches this far up behind the tab's content
MIN_FREE = 40                   # less free room than this below the content: draw nothing


def geometry(w, h, top):
    """Planet centre and radius: low in the pane, under the content that ends at `top`."""
    top0 = max(0.0, top - OVERLAP)
    avail = h - top0
    R = max(24.0, min(avail / 2.75, w * 0.19, 96.0))
    return w / 2, top0 + avail / 2, R, top0
STATIC_T = 40.0                 # moment shown as the still picture
FRAMES, COLS, FRAME = 96, 12, 200
HAS_MASK = hasattr(Gtk.Snapshot, "push_mask")


# ------------------------------------------------------------------ drawing helpers
def _rgba(c, a=1.0):
    col = Gdk.RGBA()
    col.red, col.green, col.blue, col.alpha = c[0], c[1], c[2], max(0.0, min(1.0, a))
    return col


def _stop(offset, c, a):
    s = Gsk.ColorStop()
    s.offset, s.color = offset, _rgba(c, a)
    return s


def _pt(x, y):
    return Graphene.Point().init(x, y)


def _rect(x, y, w, h):
    return Graphene.Rect().init(x, y, max(0.0, w), max(0.0, h))


def _mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def glow(snap, x, y, r, c, a, core=0.0):
    """Soft round dot (or glow) of radius r; `core` = solid part as a share of the radius."""
    if r <= 0.2 or a <= 0.003:
        return
    stops = [_stop(0, c, a)] + ([_stop(core, c, a)] if core > 0 else []) + [_stop(1, c, 0)]
    snap.append_radial_gradient(_rect(x - r, y - r, 2 * r, 2 * r), _pt(x, y), r, r, 0, 1, stops)


def streak(snap, x, y, angle, length, width, c, a):
    """Speed line / comet: bright head at (x, y), tail behind it."""
    if a <= 0.003:
        return
    snap.save()
    snap.translate(_pt(x, y))
    snap.rotate(math.degrees(angle))
    snap.append_linear_gradient(_rect(-length, -width / 2, length, width), _pt(-length, 0), _pt(0, 0),
                                [_stop(0, c, 0), _stop(1, c, a)])
    snap.restore()
    glow(snap, x, y, width * 1.8, c, a, 0.3)


def ellipse_half(cx, cy, rx, ry, rot, top):
    """Path of the far (top=True) or near half of a tilted ellipse."""
    b = Gsk.PathBuilder.new()
    c, s = math.cos(rot), math.sin(rot)

    def p(a):
        x, y = math.cos(a) * rx, math.sin(a) * ry
        return cx + x * c - y * s, cy + x * s + y * c

    a0, a1 = (math.pi, 2 * math.pi) if top else (0, math.pi)
    b.move_to(*p(a0))
    b.svg_arc_to(rx, ry, math.degrees(rot), False, True, *p(a1))
    return b.to_path()


class _Art:
    """Pictures load on a worker thread; the scene draws without them until they are there."""
    textures = {}
    _loading = set()
    _lock = threading.Lock()

    @classmethod
    def get(cls, name, on_ready):
        if name in cls.textures:
            return cls.textures[name]
        with cls._lock:
            if name in cls._loading:
                return None
            cls._loading.add(name)

        def work():
            tex = None
            try:
                tex = Gdk.Texture.new_from_filename(str(style.ART_DIR / name))
            except Exception as e:  # a missing picture only means a plainer scene
                print(f"draco: scene art {name}: {e}", file=sys.stderr)
            GLib.idle_add(lambda: (cls.textures.__setitem__(name, tex), on_ready(), False)[2])

        threading.Thread(target=work, daemon=True).start()
        return None


# ------------------------------------------------------------------ the planet
class Planet:
    RINGS = (1.55, 1.78, 2.02)          # orbital ring sizes (x planet radius)
    TILT = math.radians(-11)

    def __init__(self, redraw):
        self.redraw = redraw
        rng = self.rng = random.Random(9)
        self.stars = [(rng.random(), rng.random(), 0.8 + rng.random() * 1.6, rng.random() * 6.3,
                       0.6 + rng.random() * 2.2) for _ in range(70)]
        self.rocks = []
        for k in range(7):
            pts = [(math.cos(a) * (0.7 + rng.random() * 0.45), math.sin(a) * (0.7 + rng.random() * 0.45))
                   for a in (i / 8 * 2 * math.pi for i in range(8))]
            side = k % 2
            self.rocks.append({"x": (0.06 + rng.random() * 0.22) if side == 0 else (0.72 + rng.random() * 0.22),
                               "y": 0.12 + rng.random() * 0.8, "r": 4 + rng.random() * 9, "pts": pts,
                               "spin": rng.uniform(-0.4, 0.4), "drift": rng.uniform(-0.006, 0.006),
                               "a": rng.random() * 6.3})
        self.orbit = [(k % 3, rng.random() * 6.3, 0.5 + rng.random() * 0.7) for k in range(30)]
        self.inflow = []                # [angle, radius (x R), speed]
        self.streaks = []               # [x, y, angle, length, life]
        self.flashes = []               # [angle, life] where a particle merged into the planet
        self.gather = [(rng.random() * 6.3, 1.2 + rng.random() * 1.6, rng.random()) for _ in range(26)]
        self.turn = 0.0
        self.spin = 0.0
        self.top0 = 0.0
        self._field = None
        self._twinkle = []
        self._field_key = None

    # -------------------------------------------------- motion
    def step(self, dt, m, w, h):
        rng = self.rng
        slow = 1 - 0.7 * m.hold
        self.turn += dt / 0.55 * slow
        self.spin += dt * 4.0
        for r in self.rocks:
            r["a"] += dt * r["spin"]
            r["y"] = (r["y"] + dt * r["drift"]) % 1.0
        self.orbit = [(k, a + dt * s * (0.35 + 0.9 * m.active + 0.8 * m.speedy) * slow, s) for k, a, s in self.orbit]
        rate = m.flow * (10 + 16 * m.speedy + 24 * m.tight)
        if len(self.inflow) < 60 and rng.random() < rate * dt:
            self.inflow.append([rng.random() * 6.3, 2.3 + rng.random() * 0.4, 0.6 + rng.random() * 0.6])
        keep = []
        for p in self.inflow:
            p[1] -= dt * (0.45 + 0.6 * m.active + 1.4 * m.tight) * p[2]
            p[0] += dt * (0.9 + 1.2 * m.tight) / max(p[1], 0.4)
            if p[1] > 1.02:
                keep.append(p)
            elif m.tight > 0.2 and len(self.flashes) < 20:
                self.flashes.append([p[0], 1.0])
        self.inflow = keep
        self.flashes = [[a, life - dt * 2.2] for a, life in self.flashes if life - dt * 2.2 > 0]
        srate = m.flow * (0.5 + 7 * m.speedy + 1.5 * m.tight)
        if len(self.streaks) < 16 and rng.random() < srate * dt:
            ang = math.radians(rng.uniform(20, 38))             # top-left to bottom-right
            self.streaks.append([rng.uniform(-0.3, 0.7) * w, self.top0 - 10.0, ang, rng.uniform(30, 80), 1.0])
        keep = []
        for s in self.streaks:
            v = 260 + 260 * m.speedy
            s[0] += math.cos(s[2]) * v * dt
            s[1] += math.sin(s[2]) * v * dt
            if s[0] < w + 100 and s[1] < h + 100:
                keep.append(s)
        self.streaks = keep

    # -------------------------------------------------- layers
    def sky(self, snap, w, h, t, m, light, cx, cy, top0):
        """Everything behind the planet, faded at the edges so it blends into the pane (and into
        the details above it)."""
        ring, gl, tint = m.colors
        vr = max(h - cy, 40.0) * 1.05
        if HAS_MASK:
            snap.push_mask(Gsk.MaskMode.ALPHA)
            snap.append_radial_gradient(_rect(0, 0, w, h), _pt(cx, cy), w * 0.56, vr, 0, 1,
                                        [_stop(0, (1, 1, 1), 1), _stop(0.62, (1, 1, 1), 0.95), _stop(1, (1, 1, 1), 0)])
            snap.pop()
        if light:
            base0, base1 = _mix((0.93, 0.92, 1.0), tint, 0.22), _mix((0.98, 0.98, 1.0), tint, 0.10)
            base0 = _mix(base0, (1.0, 0.86, 0.70), 0.35 * m.tight)
        else:
            base0, base1 = _mix((0.03, 0.04, 0.13), tint, 0.30), (0.02, 0.03, 0.10)
            base0 = _mix(base0, (0.35, 0.12, 0.05), 0.45 * m.tight)
            base0 = _mix(base0, (0.24, 0.22, 0.52), 0.35 * m.calm)
        snap.append_radial_gradient(_rect(0, 0, w, h), _pt(cx, cy), w * 0.6, vr * 1.1, 0, 1,
                                    [_stop(0, base0, 1), _stop(1, base1, 1)])
        for name, off, a, y in (("scene-nebula-a.png", t * 6, 0.55, 0.0), ("scene-nebula-b.png", -t * 4 + 300, 0.5, 0.1)):
            tex = _Art.get(name, self.redraw)
            if tex:
                th = h * 1.3
                tw = tex.get_width() * th / tex.get_height()
                x = -(off % tw)
                snap.push_opacity(a * (0.55 if light else 1.0) * (0.75 + 0.35 * m.speedy))
                while x < w:
                    snap.append_texture(tex, _rect(x, h * y - h * 0.15, tw + 0.5, th))
                    x += tw
                snap.pop()
        # colour of the stage spreading around the planet
        glow(snap, cx, cy, min(w, 2 * vr) * (0.55 + 0.15 * m.speedy + 0.1 * m.tight), gl,
             (0.18 if light else 0.32) + 0.18 * m.speedy + 0.3 * m.tight + 0.1 * m.calm)
        if self._field_key != (w, h, light):          # stars: built once per size, in groups
            star = (0.45, 0.5, 0.9) if light else (1, 1, 1)
            fs = Gtk.Snapshot()
            rng = random.Random(w * 7 + h)
            for _ in range(int(w * h / 700)):
                glow(fs, rng.random() * w, rng.random() * h, 0.7 + rng.random() * 0.9, star,
                     (0.15 if light else 0.25) + rng.random() * 0.45, 0.35)
            groups = [Gtk.Snapshot() for _ in range(3)]
            for k, (x, y, r, ph, f) in enumerate(self.stars):
                glow(groups[k % 3], x * w, y * h, r * 1.3, star, 0.9, 0.3)
            self._field = fs.to_node()
            self._twinkle = [g.to_node() for g in groups]
            self._field_key = (w, h, light)
        if self._field:
            snap.append_node(self._field)
        for k, node in enumerate(self._twinkle):     # each group fades in and out at its own pace
            if node:
                snap.push_opacity((0.2 + 0.8 * (0.5 + 0.5 * math.sin(t * (0.9 + 0.7 * k) + k * 2.1)))
                                  * (0.7 + 0.3 * m.calm))
                snap.append_node(node)
                snap.pop()
        for s in self.streaks:
            streak(snap, s[0], s[1], s[2], s[3], 1.6, _mix(ring, (1, 1, 1), 0.3 if not light else 0), 0.85)
        self.asteroids(snap, w, h, light, top0)
        if m.alarm > 0.01:                       # error: a restrained red glow, faded like the sky
            glow(snap, cx, cy, max(w, 2 * vr) * 0.6, (0.92, 0.25, 0.3), (0.22 if light else 0.32) * m.alarm)
        if HAS_MASK:
            snap.pop()

    def asteroids(self, snap, w, h, light, top0):
        body = (0.62, 0.64, 0.78) if light else (0.13, 0.14, 0.24)
        lit = (0.85, 0.86, 0.95) if light else (0.42, 0.44, 0.62)
        for r in self.rocks:
            x, y, s = r["x"] * w, top0 + r["y"] * (h - top0), r["r"]
            if not HAS_PATHS:
                glow(snap, x, y, s, body, 0.9, 0.7)
                continue
            if "path" not in r:
                b = Gsk.PathBuilder.new()
                for i, (px, py) in enumerate(r["pts"]):
                    (b.move_to if i == 0 else b.line_to)(px * s, py * s)
                b.close()
                r["path"] = b.to_path()
            snap.save()
            snap.translate(_pt(x, y))
            snap.rotate(math.degrees(r["a"]))
            snap.push_fill(r["path"], Gsk.FillRule.WINDING)
            snap.append_radial_gradient(_rect(-s * 1.3, -s * 1.3, s * 2.6, s * 2.6), _pt(-s * 0.4, -s * 0.45),
                                        s * 1.4, s * 1.4, 0, 1, [_stop(0, lit, 1), _stop(1, body, 1)])
            snap.pop()
            snap.restore()

    def rings(self, snap, cx, cy, R, m, light, far):
        if not HAS_PATHS:
            return
        ring = m.colors[0]
        bright = (0.35 + 0.35 * m.active + 0.3 * m.speedy + 0.35 * m.tight + 0.15 * m.calm) * (1 - 0.5 * m.hold)
        if light:                               # deeper colour and stronger line on the pale sky
            ring = _mix(ring, (0.3, 0.25, 0.75), 0.35)
            bright = min(1.0, bright * 1.5)
        for k, size in enumerate(self.RINGS):
            rx = R * (size - (size - 1.18 - k * 0.07) * 0.55 * m.tight)    # finalizing: rings pull in
            ry = rx * 0.24
            path = ellipse_half(cx, cy, rx, ry, self.TILT, far)
            a = bright * (0.55 if far else 1.0) * (1.0 - 0.18 * k)
            snap.append_stroke(path, Gsk.Stroke.new(6 + 4 * m.speedy), _rgba(ring, 0.10 * a))
            snap.append_stroke(path, Gsk.Stroke.new(1.6 + 0.8 * m.speedy),
                               _rgba(ring if light else _mix(ring, (1, 1, 1), 0.35), 0.85 * a))
        # data particles riding the rings
        c, s = math.cos(self.TILT), math.sin(self.TILT)
        pa = (0.25 * (1 - m.calm) + 0.75 * m.active + 0.3 * m.speedy) * (1 - 0.8 * m.hold) * (1 - m.alarm)
        for k, ang, sp in self.orbit:
            if (math.sin(ang) < 0) != far:
                continue
            rx = R * (self.RINGS[k] - (self.RINGS[k] - 1.18 - k * 0.07) * 0.55 * m.tight)
            x, y = math.cos(ang) * rx, math.sin(ang) * rx * 0.24
            glow(snap, cx + x * c - y * s, cy + x * s + y * c, 2.0 + sp, _mix(ring, (1, 1, 1), 0.5), pa, 0.35)

    def planet(self, snap, cx, cy, R, t, m, light):
        ring, gl, tint = m.colors
        halo = 0.30 + 0.25 * m.speedy + 0.45 * m.tight + 0.25 * m.calm
        snap.append_radial_gradient(_rect(cx - R * 1.4, cy - R * 1.4, R * 2.8, R * 2.8), _pt(cx, cy), R * 1.35, R * 1.35,
                                    0, 1, [_stop(0.70, gl, halo), _stop(1, gl, 0)])
        ball = Gsk.RoundedRect()
        ball.init_from_rect(_rect(cx - R + 0.4, cy - R + 0.4, 2 * R - 0.8, 2 * R - 0.8), R)
        snap.push_rounded_clip(ball)
        tex = _Art.get("scene-planet.jpg", self.redraw)
        if tex:
            i0, f = int(self.turn) % FRAMES, self.turn - math.floor(self.turn)
            k = 2 * R / FRAME
            for i, a in ((i0, 1.0), ((i0 + 1) % FRAMES, f)):
                if a > 0.01:
                    ox, oy = (i % COLS) * FRAME * k, (i // COLS) * FRAME * k
                    snap.push_opacity(a)
                    snap.append_texture(tex, _rect(cx - R - ox, cy - R - oy, tex.get_width() * k, tex.get_height() * k))
                    snap.pop()
        else:
            snap.append_radial_gradient(_rect(cx - R, cy - R, 2 * R, 2 * R), _pt(cx - R * 0.4, cy - R * 0.4), R * 1.5,
                                        R * 1.5, 0, 1, [_stop(0, (0.3, 0.45, 0.85), 1), _stop(1, (0.04, 0.06, 0.2), 1)])
        # deep-space look: darker while initializing, tinted by the stage
        snap.append_color(_rgba((0.02, 0.03, 0.12), 0.22 + 0.5 * (1 - m.wake)), _rect(cx - R, cy - R, 2 * R, 2 * R))
        snap.append_color(_rgba(tint, 0.12 + 0.14 * m.tight), _rect(cx - R, cy - R, 2 * R, 2 * R))
        # rim light in the stage colour, a warm wash when finalizing, a soft glow when done
        snap.append_radial_gradient(_rect(cx - R, cy - R, 2 * R, 2 * R), _pt(cx, cy), R, R, 0, 1,
                                    [_stop(0.84, gl, 0), _stop(1, _mix(gl, (1, 1, 1), 0.25), 0.42 + 0.3 * m.tight)])
        if m.calm > 0.01:
            glow(snap, cx - R * 0.3, cy - R * 0.35, R * 1.2, (0.85, 0.88, 1.0), 0.28 * m.calm)
        snap.pop()
        for a, life in self.flashes:            # particles merging into the planet
            glow(snap, cx + math.cos(a) * R, cy + math.sin(a) * R * 0.9, 4 + 6 * (1 - life), (1, 0.85, 0.5), life * 0.9)

    def inflow_particles(self, snap, cx, cy, R, m, light):
        ring = _mix(m.colors[0], (1, 1, 1), 0.45)
        for a, r, s in self.inflow:
            x, y = cx + math.cos(a) * r * R, cy + math.sin(a) * r * R * 0.55
            fade = min(1.0, (r - 1.0) * 2.5) * min(1.0, (2.6 - r) * 2)
            glow(snap, x, y, 2.6 + s, ring, fade * m.active, 0.3)

    def gathering(self, snap, cx, cy, R, t, m):
        """Initializing: specks drifting in and settling on the rings."""
        a_all = (1 - m.wake) * 1.2 * (1 - m.hold)
        if a_all <= 0.02:
            return
        for ang, dist, ph in self.gather:
            d = 1.25 + (dist - 1.25) * (0.5 + 0.5 * math.cos(t * 0.35 + ph * 6.3))
            glow(snap, cx + math.cos(ang + t * 0.1) * d * R, cy + math.sin(ang + t * 0.1) * d * R * 0.5,
                 1.6, (0.75, 0.8, 1.0), a_all * 0.7, 0.35)

    def progress(self, snap, cx, cy, r, m, light):
        st = m.state
        if st.stage == "idle" or not HAS_PATHS:
            return
        track = Gsk.PathBuilder.new()
        track.add_circle(_pt(cx, cy), r)
        snap.append_stroke(track.to_path(), Gsk.Stroke.new(4), _rgba((0.3, 0.3, 0.6) if light else (1, 1, 1), 0.16))
        frac = m.arc if st.fraction >= 0 else 0.0
        ring = m.colors[0]
        if frac > 0.002:
            end = -math.pi / 2 + min(frac, 0.9999) * 2 * math.pi
            ex, ey = cx + math.cos(end) * r, cy + math.sin(end) * r
            b = Gsk.PathBuilder.new()
            b.move_to(cx, cy - r)
            b.svg_arc_to(r, r, 0, frac > 0.5, True, ex, ey)
            stroke = Gsk.Stroke.new(5)
            stroke.set_line_cap(Gsk.LineCap.ROUND)
            path = b.to_path()
            snap.append_stroke(path, Gsk.Stroke.new(12), _rgba(ring, 0.18))
            snap.push_stroke(path, stroke)
            snap.append_linear_gradient(_rect(cx - r - 6, cy - r - 6, 2 * r + 12, 2 * r + 12), _pt(cx - r, cy - r),
                                        _pt(cx + r, cy + r), [_stop(0, (1, 1, 1), 1), _stop(1, _mix(ring, (1, 1, 1), 0.3), 1)])
            snap.pop()
            glow(snap, ex, ey, 9, _mix(ring, (1, 1, 1), 0.4), 0.9, 0.2)
        if st.stage not in ("completed", "error"):    # amber start mark, as in the design
            glow(snap, cx, cy - r, 7, (1.0, 0.7, 0.25), 0.95, 0.35)

    def center_mark(self, snap, cx, cy, R, t, m, light):
        """Spinner while initializing, a check when completed (the text is a GTK label)."""
        stage = m.state.stage
        if stage == "initializing":
            for k in range(10):
                a = k / 10 * 2 * math.pi + self.spin
                glow(snap, cx + math.cos(a) * R * 0.17, cy - R * 0.2 + math.sin(a) * R * 0.17, 2.6,
                     (0.55, 0.8, 1.0), 0.25 + 0.75 * (k / 10), 0.5)
        elif stage == "completed" and HAS_PATHS:
            rr = R * 0.2
            y = cy - R * 0.22
            disc = Gsk.PathBuilder.new()
            disc.add_circle(_pt(cx, y), rr)
            snap.append_fill(disc.to_path(), Gsk.FillRule.WINDING, _rgba((1, 1, 1), 0.96 * m.calm))
            chk = Gsk.PathBuilder.new()
            chk.move_to(cx - rr * 0.45, y + rr * 0.02)
            chk.line_to(cx - rr * 0.1, y + rr * 0.36)
            chk.line_to(cx + rr * 0.5, y - rr * 0.32)
            st = Gsk.Stroke.new(max(2.5, rr * 0.22))
            st.set_line_cap(Gsk.LineCap.ROUND)
            st.set_line_join(Gsk.LineJoin.ROUND)
            snap.append_stroke(chk.to_path(), st, _rgba((0.13, 0.75, 0.38), m.calm))

    def draw(self, snap, w, h, t, m, light, geo):
        cx, cy, R, top0 = geo
        self.top0 = top0
        self.sky(snap, w, h, t, m, light, cx, cy, top0)
        self.rings(snap, cx, cy, R, m, light, True)
        self.gathering(snap, cx, cy, R, t, m)
        self.planet(snap, cx, cy, R, t, m, light)
        self.inflow_particles(snap, cx, cy, R, m, light)
        self.rings(snap, cx, cy, R, m, light, False)
        self.progress(snap, cx, cy, R * 1.24, m, light)
        self.center_mark(snap, cx, cy, R, t, m, light)


# ------------------------------------------------------------------ the widget
def reduced_motion(settings):
    gs = Gtk.Settings.get_default()
    return bool(settings.get("reduce_motion")) or (gs is not None and not gs.props.gtk_enable_animations)


class _Area(Gtk.Widget):
    def __init__(self, owner):
        super().__init__(hexpand=True, vexpand=True)
        self.owner = owner
        self._size = None

    def do_size_allocate(self, width, height, baseline):
        if (width, height) != self._size:       # labels move outside the layout pass
            self._size = (width, height)
            GLib.idle_add(lambda: (self.owner._place(), False)[1])

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        if w > 2 and h - self.owner.top >= MIN_FREE:
            self.owner.paint(snap, w, h)


class PlanetScene(Gtk.Overlay):
    """The planet with the percentage and state in its middle, for the selected download."""

    def __init__(self, app):
        super().__init__(vexpand=True, hexpand=True)
        self.app = app
        self.add_css_class("ps-scene")
        self.motion = SceneMotion()
        self.item = None
        self.t = STATIC_T
        self._last = None
        self._tick_id = 0
        self._failed = False
        self.planet = Planet(self._redraw)
        self.area = _Area(self)
        self.set_child(self.area)
        self.top = 0                            # where the tab's content ends (set by the details pane)
        self._geo = None
        self._gliding = False
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, halign=Gtk.Align.CENTER,
                      valign=Gtk.Align.START)
        box.set_can_target(False)
        self.big = Gtk.Label()
        self.big.add_css_class("ps-big")
        self.small = Gtk.Label()
        self.small.add_css_class("ps-small")
        box.append(self.big)
        box.append(self.small)
        self.add_overlay(box)
        self.text = box
        self.area.connect("map", lambda *_: self._sync_ticking())
        self.area.connect("unmap", lambda *_: self._stop())
        self.reload_settings()

    def _redraw(self):
        self.area.queue_draw()

    def set_top(self, top):
        """The details pane tells where its content ends; the planet goes below (and behind) it.
        Changes of a few pixels are ignored so the planet never shakes."""
        if abs(top - self.top) > 4:
            self.top = top
            self._place()
            self.area.queue_draw()

    def _geometry(self, w, h):
        """Planet place and size, gliding to a new spot instead of jumping (and ignoring tiny
        size changes of the pane)."""
        target = geometry(w, h, self.top)
        g = self._geo
        if g is None or not self._tick_id or max(abs(a - b) for a, b in zip(g, target)) > 120:
            self._geo = target
        elif max(abs(a - b) for a, b in zip(g, target)) > 4 or self._gliding:
            self._gliding = True
            self._geo = tuple(a + (b - a) * 0.2 for a, b in zip(g, target))
            if max(abs(a - b) for a, b in zip(self._geo, target)) < 0.5:
                self._geo, self._gliding = target, False
        return self._geo

    def _place(self):
        w, h = self.area.get_width(), self.area.get_height()
        if w < 2 or h < 2:
            return
        if self._geo is None or not self._tick_id:
            self._geometry(w, h)
        cx, cy, R, _ = self._geo
        self.text.set_visible(R >= 40 and h - self.top >= MIN_FREE)
        self._labels(R)
        # the labels' own heights (the box's measure would include the margin set here)
        nat = sum(lb.measure(Gtk.Orientation.VERTICAL, -1)[1] for lb in (self.big, self.small) if lb.get_visible())
        self.text.set_margin_top(max(0, int(cy - nat / 2)))

    def reload_settings(self):
        self.set_visible(bool(self.app.settings.get("details_animation", True)))
        self._sync_ticking()

    # -------------------------------------------------- state
    def set_item(self, item):
        """Called by the details pane on every update with the selected download (or None)."""
        self.item = item
        self.motion.set_state(scene_state(item))
        if not self._tick_id:
            self.motion.settle()
            self.area.queue_draw()
        self._labels()

    def _labels(self, R=None):
        st = self.motion.state
        stage = st.stage
        light = not style.is_dark()
        for c, on in (("ps-light", light), ("ps-dark", not light)):
            (self.add_css_class if on else self.remove_css_class)(c)
        show_pct = stage not in ("idle", "initializing", "completed") and st.fraction >= 0
        self.big.set_text(f"{st.fraction * 100:.0f}%" if show_pct else "")
        self.big.set_visible(show_pct)
        self.small.set_text(st.label)
        # spinner / check are drawn above the text
        if R is None:
            R = (self._geo or geometry(self.area.get_width(), self.area.get_height(), self.top))[2]
        self.small.set_margin_top(int(R * 0.3) if stage in ("initializing", "completed") else 0)
        name = (self.item or {}).get("filename") or ""
        self.area.update_property([Gtk.AccessibleProperty.LABEL],
                                  [f"{st.label} {self.big.get_text()} {name}".strip()])

    # -------------------------------------------------- frames
    def _sync_ticking(self):
        animate = self.get_visible() and self.area.get_mapped() and not reduced_motion(self.app.settings)
        if animate and not self._tick_id:
            self._last = None
            self._tick_id = self.area.add_tick_callback(self._tick)
        elif not animate:
            self._stop()
            self.t = STATIC_T
            self.motion.settle()
            self.area.queue_draw()

    def _stop(self):
        if self._tick_id:
            self.area.remove_tick_callback(self._tick_id)
            self._tick_id = 0

    def _tick(self, widget, clock):
        now = clock.get_frame_time() / 1e6
        if self._last is None:
            self._last = now
            return GLib.SOURCE_CONTINUE
        busy = self.motion.state.stage in ("initializing", "downloading", "highspeed", "finalizing") \
            or self.motion.active > 0.02
        if now - self._last < 1 / (FPS if busy else CALM_FPS) - 0.004:
            return GLib.SOURCE_CONTINUE
        root = widget.get_root()
        if root is not None and hasattr(root, "is_suspended") and root.is_suspended():
            self._last = now                    # minimised: skip work, don't jump when it comes back
            return GLib.SOURCE_CONTINUE
        dt = min(0.1, now - self._last)
        self._last = now
        if widget.get_height() - self.top < MIN_FREE:   # nothing shown: no work
            return GLib.SOURCE_CONTINUE
        self.t += dt
        stage = self.motion.state.stage
        self.motion.update(dt)
        try:
            self.planet.step(dt, self.motion, widget.get_width(), widget.get_height())
        except Exception as e:
            self._fail(e)
        if self.motion.state.stage != stage or self._gliding:
            self._place()
        widget.queue_draw()
        return GLib.SOURCE_CONTINUE


    def _fail(self, e):
        if not self._failed:
            print(f"draco: planet animation stopped: {e}", file=sys.stderr)
        self._failed = True
        self._stop()

    def paint(self, snap, w, h):
        if self._failed:                        # never let a drawing bug reach the downloads
            return
        try:
            inner = Gtk.Snapshot()
            self.planet.draw(inner, w, h, self.t, self.motion, not style.is_dark(), self._geometry(w, h))
            node = inner.to_node()
        except Exception as e:
            self._fail(e)
            node = None
        if node:
            snap.append_node(node)
