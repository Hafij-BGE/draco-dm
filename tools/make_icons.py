"""Build Draco's app icon set from one source picture.

    python3 tools/make_icons.py [source.png]     (default: data/draco-source.png)

Removes the plain white background around the artwork (white inside the artwork is
kept), crops it square, and writes:
    data/draco.png                       512 px master
    data/icons/<size>.png                  16 … 512 px for the desktop icon theme
    extension/chrome/icons/<size>.png      16/32/48/128 px for the browser extension
    draco/icons/io.github.draco.DracoDM.png   used inside the app
"""

import sys
from collections import deque
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
THEME_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
EXT_SIZES = (16, 32, 48, 128)
WHITE_CUTOFF = 238      # how close to white a pixel must be to count as background


def load_rgba(path):
    pb = GdkPixbuf.Pixbuf.new_from_file(str(path))
    if not pb.get_has_alpha():
        pb = pb.add_alpha(False, 0, 0, 0)
    w, h, rs = pb.get_width(), pb.get_height(), pb.get_rowstride()
    raw = pb.get_pixels()
    px = bytearray(w * h * 4)
    for y in range(h):
        px[y * w * 4:(y + 1) * w * 4] = raw[y * rs:y * rs + w * 4]
    return w, h, px


def remove_background(w, h, px):
    """Flood-fill the white area touching the border, then soften the edge (colour-to-alpha)."""
    def whiteish(i):
        return min(px[i], px[i + 1], px[i + 2]) >= WHITE_CUTOFF

    bg = bytearray(w * h)
    q = deque()
    for x in range(w):
        q.extend(((x, 0), (x, h - 1)))
    for y in range(h):
        q.extend(((0, y), (w - 1, y)))
    while q:
        x, y = q.popleft()
        k = y * w + x
        if bg[k] or not whiteish(k * 4):
            continue
        bg[k] = 1
        if x > 0:
            q.append((x - 1, y))
        if x < w - 1:
            q.append((x + 1, y))
        if y > 0:
            q.append((x, y - 1))
        if y < h - 1:
            q.append((x, y + 1))
    # Edge ring: pixels within 3 px of the background get white "un-blended" into alpha.
    ring = bytearray(bg)
    for _ in range(3):
        nxt = bytearray(ring)
        for y in range(1, h - 1):
            row = y * w
            for x in range(1, w - 1):
                k = row + x
                if not ring[k] and (ring[k - 1] or ring[k + 1] or ring[k - w] or ring[k + w]):
                    nxt[k] = 1
        ring = nxt
    for k in range(w * h):
        i = k * 4
        if bg[k]:
            px[i + 3] = 0
        elif ring[k]:
            r, g, b = px[i], px[i + 1], px[i + 2]
            a = max(255 - r, 255 - g, 255 - b)
            if a == 0:
                px[i + 3] = 0
                continue
            for c in range(3):
                px[i + c] = max(0, min(255, round(255 - (255 - px[i + c]) * 255 / a)))
            px[i + 3] = a
    return px


def crop_square(w, h, px, margin_ratio=0.04):
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            if px[(y * w + x) * 4 + 3] > 8:
                xs.append(x)
                ys.append(y)
                break
        for x in range(w - 1, -1, -1):
            if px[(y * w + x) * 4 + 3] > 8:
                xs.append(x)
                break
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    side = max(x1 - x0, y1 - y0) + 1
    side = int(side * (1 + 2 * margin_ratio))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    out = bytearray(side * side * 4)
    ox, oy = cx - side // 2, cy - side // 2
    for y in range(side):
        sy = oy + y
        if 0 <= sy < h:
            for x in range(side):
                sx = ox + x
                if 0 <= sx < w:
                    si, di = (sy * w + sx) * 4, (y * side + x) * 4
                    out[di:di + 4] = px[si:si + 4]
    return side, out


def to_pixbuf(side, px):
    return GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(px)), GdkPixbuf.Colorspace.RGB,
                                           True, 8, side, side, side * 4)


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "draco-source.png"
    w, h, px = load_rgba(src)
    px = remove_background(w, h, px)
    side, sq = crop_square(w, h, px)
    master = to_pixbuf(side, sq)

    def save(size, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        master.scale_simple(size, size, GdkPixbuf.InterpType.HYPER).savev(str(path), "png", [], [])

    save(512, ROOT / "data" / "draco.png")
    for s in THEME_SIZES:
        save(s, ROOT / "data" / "icons" / f"{s}.png")
    for s in EXT_SIZES:
        save(s, ROOT / "extension" / "chrome" / "icons" / f"{s}.png")
    save(256, ROOT / "draco" / "icons" / "io.github.draco.DracoDM.png")
    print("icons written from", src)


if __name__ == "__main__":
    main()
