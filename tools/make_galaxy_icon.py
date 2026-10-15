"""Turn the galaxy photo into Draco's icon artwork.

    python3 tools/make_galaxy_icon.py [--no-arrow]
    python3 tools/make_icons.py            # then build all icon sizes from it

Reads data/galaxy-photo.png, writes data/draco-source.png (1024 px, transparent corners).
"""

import math
import sys
from pathlib import Path

import cairo

ROOT = Path(__file__).resolve().parent.parent
SIZE = 1024
RADIUS = 0.225 * SIZE        # rounded-square corner radius
MARGIN = 0.03 * SIZE


def squircle(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def arrow(cr, cx, cy, s):
    """Download arrow (stem + head) and landing bar, centred on cx, cy, height ~ s."""
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.set_line_width(s * 0.16)
    cr.move_to(cx, cy - s * 0.48)
    cr.line_to(cx, cy + s * 0.18)
    cr.move_to(cx - s * 0.30, cy - s * 0.10)
    cr.line_to(cx, cy + s * 0.22)
    cr.line_to(cx + s * 0.30, cy - s * 0.10)
    cr.stroke()
    cr.set_line_width(s * 0.11)
    cr.move_to(cx - s * 0.32, cy + s * 0.50)
    cr.line_to(cx + s * 0.32, cy + s * 0.50)
    cr.stroke()


def main():
    with_arrow = "--no-arrow" not in sys.argv
    photo = cairo.ImageSurface.create_from_png(str(ROOT / "data" / "galaxy-photo.png"))
    pw, ph = photo.get_width(), photo.get_height()

    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, SIZE, SIZE)
    cr = cairo.Context(out)
    box = SIZE - 2 * MARGIN

    # 1. Clip to a rounded square and paint the photo, centred on the galaxy core, slightly zoomed.
    squircle(cr, MARGIN, MARGIN, box, box, RADIUS)
    cr.save()
    cr.clip()
    side = min(pw, ph) * 0.80                       # crop a bit tighter than the short edge
    core_x, core_y = pw * 0.503, ph * 0.533         # bright nucleus position in the photo
    scale = box / side
    cr.translate(MARGIN, MARGIN)
    cr.scale(scale, scale)
    cr.translate(-(core_x - side / 2), -(core_y - side / 2))
    cr.set_source_surface(photo, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_BEST)
    cr.paint()
    cr.restore()

    # 2. Vignette: darken the edges so the spiral pops and the shape reads at small sizes.
    cr.save()
    squircle(cr, MARGIN, MARGIN, box, box, RADIUS)
    cr.clip()
    g = cairo.RadialGradient(SIZE / 2, SIZE / 2, box * 0.22, SIZE / 2, SIZE / 2, box * 0.75)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(0.6, 0.02, 0.02, 0.08, 0.08)
    g.add_color_stop_rgba(1, 0.02, 0.02, 0.10, 0.45)
    cr.set_source(g)
    cr.paint()
    # top sheen
    sheen = cairo.LinearGradient(0, MARGIN, 0, SIZE / 2)
    sheen.add_color_stop_rgba(0, 1, 1, 1, 0.14)
    sheen.add_color_stop_rgba(1, 1, 1, 1, 0)
    cr.set_source(sheen)
    cr.paint()

    # 3. Download arrow over the core, with a soft shadow.
    if with_arrow:
        cx, cy, s = SIZE / 2, SIZE * 0.50, SIZE * 0.36
        for i, a in enumerate((0.10, 0.08, 0.06, 0.04)):
            cr.save()
            cr.translate(0, 6 + i * 4)
            cr.set_source_rgba(0.03, 0.02, 0.10, a * 2.2)
            arrow(cr, cx, cy, s * (1 + i * 0.012))
            cr.restore()
        cr.set_source_rgba(1, 1, 1, 0.97)
        arrow(cr, cx, cy, s)
    cr.restore()

    # 4. Thin light rim and a dark outer edge.
    squircle(cr, MARGIN + 3, MARGIN + 3, box - 6, box - 6, RADIUS - 3)
    cr.set_source_rgba(1, 1, 1, 0.22)
    cr.set_line_width(6)
    cr.stroke()
    squircle(cr, MARGIN, MARGIN, box, box, RADIUS)
    cr.set_source_rgba(0.02, 0.02, 0.08, 0.6)
    cr.set_line_width(3)
    cr.stroke()

    target = ROOT / "data" / "draco-source.png"
    out.write_to_png(str(target))
    print("wrote", target)


if __name__ == "__main__":
    main()
