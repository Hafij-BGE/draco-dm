"""Draw Draco's app icon (vector) and write the master picture the icon set is built from.

    python3 tools/make_app_icon.py && python3 tools/make_icons.py && python3 tools/make_ico.py

Writes data/draco-icon.svg (scalable master) and data/draco-source.png (1024 px, white margin so
make_icons.py can trim it like before)."""

import math
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def stars():
    out, seed = [], 11
    for _ in range(26):
        seed = (seed * 1103515245 + 12345) % 2 ** 31
        x = 70 + seed % 372
        seed = (seed * 1103515245 + 12345) % 2 ** 31
        y = 70 + seed % 372
        seed = (seed * 1103515245 + 12345) % 2 ** 31
        r = 0.8 + (seed % 100) / 60
        if (x - 256) ** 2 + (y - 262) ** 2 > 150 ** 2:
            out.append(f'<circle cx="{x}" cy="{y}" r="{r:.1f}" fill="#fff" opacity="{0.35 + (seed % 50) / 100:.2f}"/>')
    return "".join(out)


def sparkle(cx, cy, s, op):
    return (f'<path d="M{cx} {cy - s}C{cx + s * .12} {cy - s * .12} {cx + s * .12} {cy - s * .12} {cx + s} {cy}'
            f'C{cx + s * .12} {cy + s * .12} {cx + s * .12} {cy + s * .12} {cx} {cy + s}'
            f'C{cx - s * .12} {cy + s * .12} {cx - s * .12} {cy + s * .12} {cx - s} {cy}'
            f'C{cx - s * .12} {cy - s * .12} {cx - s * .12} {cy - s * .12} {cx} {cy - s}z" fill="#fff" opacity="{op}"/>')


def svg():
    tilt = -22
    ring_back = (f'<ellipse cx="256" cy="262" rx="190" ry="54" transform="rotate({tilt} 256 262)" fill="none" '
                 f'stroke="url(#ring)" stroke-width="20" opacity=".55"/>')
    ring_front = (f'<path d="M{256 - 190 * math.cos(math.radians(tilt)):.1f} {262 - 190 * math.sin(math.radians(tilt)):.1f}'
                  f' A190 54 {tilt} 0 0 {256 + 190 * math.cos(math.radians(tilt)):.1f} '
                  f'{262 + 190 * math.sin(math.radians(tilt)):.1f}" fill="none" stroke="url(#ring)" '
                  f'stroke-width="20" stroke-linecap="round"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
<defs>
  <linearGradient id="tile" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#1e1b6b"/><stop offset=".55" stop-color="#0f1340"/><stop offset="1" stop-color="#070a24"/>
  </linearGradient>
  <radialGradient id="neb1" cx=".2" cy=".18" r=".6"><stop offset="0" stop-color="#7c3aed" stop-opacity=".75"/>
    <stop offset="1" stop-color="#7c3aed" stop-opacity="0"/></radialGradient>
  <radialGradient id="neb2" cx=".88" cy=".9" r=".55"><stop offset="0" stop-color="#06b6d4" stop-opacity=".55"/>
    <stop offset="1" stop-color="#06b6d4" stop-opacity="0"/></radialGradient>
  <radialGradient id="planet" cx=".34" cy=".3" r=".8">
    <stop offset="0" stop-color="#c4f1ff"/><stop offset=".28" stop-color="#60a5fa"/>
    <stop offset=".62" stop-color="#6d28d9"/><stop offset="1" stop-color="#2e1065"/>
  </radialGradient>
  <linearGradient id="ring" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#f0abfc"/><stop offset=".5" stop-color="#a5f3fc"/><stop offset="1" stop-color="#c4b5fd"/>
  </linearGradient>
  <linearGradient id="arrow" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#dbeafe"/>
  </linearGradient>
  <radialGradient id="glow" cx=".5" cy=".5" r=".5"><stop offset=".55" stop-color="#8b5cf6" stop-opacity=".55"/>
    <stop offset="1" stop-color="#8b5cf6" stop-opacity="0"/></radialGradient>
  <clipPath id="clip"><rect x="16" y="16" width="480" height="480" rx="112"/></clipPath>
</defs>
<g clip-path="url(#clip)">
  <rect x="16" y="16" width="480" height="480" fill="url(#tile)"/>
  <rect x="16" y="16" width="480" height="480" fill="url(#neb1)"/>
  <rect x="16" y="16" width="480" height="480" fill="url(#neb2)"/>
  {stars()}
  {sparkle(120, 128, 16, .9)}{sparkle(400, 400, 11, .75)}{sparkle(408, 116, 8, .7)}
  <circle cx="256" cy="262" r="168" fill="url(#glow)"/>
  {ring_back}
  <circle cx="256" cy="262" r="124" fill="url(#planet)"/>
  <ellipse cx="214" cy="212" rx="58" ry="34" transform="rotate(-30 214 212)" fill="#fff" opacity=".22"/>
  <path d="M256 186v92" stroke="#ffffff" stroke-width="30" stroke-linecap="round"/>
  <path d="M212 248l44 44 44-44" fill="none" stroke="#ffffff" stroke-width="30" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M206 330h100" stroke="#e0e7ff" stroke-width="22" stroke-linecap="round" opacity=".9"/>
  {ring_front}
  <rect x="16" y="16" width="480" height="480" rx="112" fill="none" stroke="#ffffff" stroke-opacity=".14" stroke-width="4"/>
</g>
</svg>'''


def main():
    data = ROOT / "data"
    (data / "draco-icon.svg").write_text(svg())
    pb = GdkPixbuf.Pixbuf.new_from_file_at_size(str(data / "draco-icon.svg"), 960, 960)
    canvas = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 1024, 1024)
    canvas.fill(0xFFFFFFFF)
    pb.composite(canvas, 32, 32, 960, 960, 32, 32, 1, 1, GdkPixbuf.InterpType.HYPER, 255)
    canvas.savev(str(data / "draco-source.png"), "png", [], [])
    print("wrote data/draco-icon.svg and data/draco-source.png")


if __name__ == "__main__":
    main()
