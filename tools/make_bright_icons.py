"""Icons for the Sky Light / Rose Sunset themes: coloured file-type documents (draco-f-*.svg) and
filled tile icons for the sidebar (draco-b-*.svg). Run: python3 tools/make_bright_icons.py"""

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "draco" / "icons"
MODERN = runpy.run_path(str(ROOT / "tools" / "make_modern_icons.py"), run_name="icons")

DOC = "M6 2.2h8.2L19.8 7.8V20.2c0 .9-.7 1.6-1.6 1.6H6c-.9 0-1.6-.7-1.6-1.6V3.8c0-.9.7-1.6 1.6-1.6z"
FOLD = "M14.2 2.2v4c0 .9.7 1.6 1.6 1.6h4z"

# kind: (light, dark, label or glyph)
FILES = {
    "archive": ("#a78bfa", "#6d28d9", "ZIP"),
    "disc": ("#cbd5e1", "#64748b", "ISO"),
    "pdf": ("#f87171", "#dc2626", "PDF"),
    "document": ("#60a5fa", "#2563eb", "DOC"),
    "music": ("#f9a8d4", "#db2777", '<path d="M10.3 16.6V10l5.2-1.3v6.4" stroke="#fff" stroke-width="1.4" fill="none"/>'
                                    '<circle cx="9" cy="16.8" r="1.6" fill="#fff"/><circle cx="14.2" cy="15.3" r="1.6" fill="#fff"/>'),
    "video": ("#c084fc", "#7e22ce", '<path d="M10 11.2v6.2l5.2-3.1z" fill="#fff"/>'),
    "program": ("#7dd3fc", "#0284c7", '<rect x="8.2" y="11" width="3.2" height="3.2" rx=".6" fill="#fff"/>'
                                      '<rect x="12.4" y="11" width="3.2" height="3.2" rx=".6" fill="#fff"/>'
                                      '<rect x="8.2" y="15.2" width="3.2" height="3.2" rx=".6" fill="#fff"/>'
                                      '<rect x="12.4" y="15.2" width="3.2" height="3.2" rx=".6" fill="#fff"/>'),
    "image": ("#67e8f9", "#0891b2", '<path d="M8 18l3-3.6 2 2.2 1.6-1.8 2.4 3.2z" fill="#fff"/><circle cx="10.2" cy="11.8" r="1.1" fill="#fff"/>'),
    "sheet": ("#86efac", "#16a34a", "XLS"),
    "unknown": ("#cbd5e1", "#94a3b8", "?"),
    "live": ("#fda4af", "#e11d48", '<circle cx="12" cy="14.6" r="1.4" fill="#fff"/>'
                                   '<path d="M9.3 11.9a3.8 3.8 0 0 0 0 5.4M14.7 11.9a3.8 3.8 0 0 1 0 5.4" stroke="#fff" '
                                   'stroke-width="1.3" fill="none" stroke-linecap="round"/>'),
}

# sidebar tiles: name -> (light, dark, modern glyph to whiten)
TILES = {
    "home": ("#60a5fa", "#2563eb", "home"),
    "folder-all": ("#818cf8", "#4f46e5", "folder-all"),
    "cat-compressed": ("#fdba74", "#ea580c", "cat-compressed"),
    "cat-documents": ("#7dd3fc", "#0284c7", "cat-documents"),
    "cat-music": ("#f0abfc", "#c026d3", "cat-music"),
    "cat-programs": ("#a5b4fc", "#4f46e5", "cat-programs"),
    "cat-video": ("#c4b5fd", "#7c3aed", "cat-video"),
    "cat-general": ("#fcd34d", "#f59e0b", "cat-general"),
    "folder": ("#fcd34d", "#f59e0b", "folder"),
}


def file_icon(light, dark, mark):
    if mark.startswith("<"):
        inner = mark
    else:
        size = 5.4 if len(mark) > 1 else 8
        inner = (f'<text x="12.1" y="{17.6 if len(mark) > 1 else 18.4}" text-anchor="middle" '
                 f'font-family="Inter, Cantarell, sans-serif" font-weight="800" font-size="{size}" '
                 f'fill="#fff">{mark}</text>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24"><defs>'
            f'<linearGradient id="d" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{light}"/>'
            f'<stop offset="1" stop-color="{dark}"/></linearGradient></defs>'
            f'<path d="{DOC}" fill="url(#d)"/><path d="{FOLD}" fill="#fff" fill-opacity=".45"/>{inner}</svg>')


def tile_icon(light, dark, glyph):
    (_c1, _c2), body = MODERN["ICONS"][glyph]
    body = body or MODERN["gear"]()
    body = body.replace('"#fff"', f'"{dark}"').replace("#7c2d12", dark).replace("#dbeafe", light)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24"><defs>'
            f'<linearGradient id="t" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{light}"/>'
            f'<stop offset="1" stop-color="{dark}"/></linearGradient>'
            '<linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/>'
            '<stop offset="1" stop-color="#fff"/></linearGradient></defs>'
            '<rect x="1" y="1" width="22" height="22" rx="6" fill="url(#t)"/>'
            f'<g transform="translate(4.2 4.2) scale(.65)">{body}</g></svg>')


def main():
    for kind, (light, dark, mark) in FILES.items():
        (OUT / f"draco-f-{kind}.svg").write_text(file_icon(light, dark, mark))
    for name, (light, dark, glyph) in TILES.items():
        (OUT / f"draco-b-{name}.svg").write_text(tile_icon(light, dark, glyph))
    print(f"wrote {len(FILES)} file icons and {len(TILES)} tile icons")


if __name__ == "__main__":
    main()
