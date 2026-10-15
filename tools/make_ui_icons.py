"""Generate Draco's own full-colour toolbar/sidebar icons (original artwork) as SVG.

    python3 tools/make_ui_icons.py draco/icons
"""

import sys
from pathlib import Path

DEFS = """<defs>
<linearGradient id="blue" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#62a0ea"/><stop offset="1" stop-color="#1a5fb4"/></linearGradient>
<linearGradient id="green" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8ff0a4"/><stop offset="1" stop-color="#26a269"/></linearGradient>
<linearGradient id="red" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f66151"/><stop offset="1" stop-color="#a51d2d"/></linearGradient>
<linearGradient id="orange" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffbe6f"/><stop offset="1" stop-color="#e66100"/></linearGradient>
<linearGradient id="gray" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#deddda"/><stop offset="1" stop-color="#77767b"/></linearGradient>
<linearGradient id="folder" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe16b"/><stop offset="1" stop-color="#f5c211"/></linearGradient>
<linearGradient id="folderback" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6d32d"/><stop offset="1" stop-color="#c88800"/></linearGradient>
<linearGradient id="paper" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#deddda"/></linearGradient>
<linearGradient id="purple" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#dc8add"/><stop offset="1" stop-color="#813d9c"/></linearGradient>
</defs>"""

STROKE = 'stroke="#00000040" stroke-width="1"'


def svg(body, size=32):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 32 32">'
            f'{DEFS}{body}</svg>\n')


def disc(fill):
    return f'<circle cx="16" cy="16" r="13.5" fill="url(#{fill})" {STROKE}/>' \
           '<ellipse cx="16" cy="9" rx="9" ry="4.5" fill="#ffffff" opacity="0.28"/>'


def folder(badge=""):
    return ('<path d="M3 8.5a1.5 1.5 0 0 1 1.5-1.5h7l2.5 2.5h13.5a1.5 1.5 0 0 1 1.5 1.5v14.5a1.5 1.5 0 0 1-1.5 1.5h-23'
            'a1.5 1.5 0 0 1-1.5-1.5z" fill="url(#folderback)" stroke="#9c6e00" stroke-width="0.8"/>'
            '<path d="M3 13h26v12.5a1.5 1.5 0 0 1-1.5 1.5h-23a1.5 1.5 0 0 1-1.5-1.5z" fill="url(#folder)" '
            'stroke="#9c6e00" stroke-width="0.8"/>' + badge)


def badge(color, glyph):
    return (f'<circle cx="23" cy="22" r="7" fill="url(#{color})" stroke="#ffffff" stroke-width="1.5"/>'
            f'<g fill="#ffffff" stroke="#ffffff">{glyph}</g>')


ICONS = {
    # ---------------- toolbar
    "draco-add-url": disc("blue") + '<path d="M14 8h4v6h6v4h-6v6h-4v-6H8v-4h6z" fill="#fff"/>',
    "draco-resume": disc("green") + '<path d="M12 8.5v15l12-7.5z" fill="#fff"/>',
    "draco-stop": disc("orange") + '<rect x="10.5" y="9" width="4" height="14" rx="1" fill="#fff"/>'
                                  '<rect x="17.5" y="9" width="4" height="14" rx="1" fill="#fff"/>',
    "draco-stop-all": disc("red") + '<rect x="10" y="10" width="12" height="12" rx="1.5" fill="#fff"/>',
    "draco-delete": ('<path d="M8 10h16l-1.5 17a2 2 0 0 1-2 1.8h-9a2 2 0 0 1-2-1.8z" fill="url(#red)" '
                    'stroke="#7a1520" stroke-width="0.8"/>'
                    '<rect x="6" y="6.5" width="20" height="3.5" rx="1.2" fill="url(#gray)" stroke="#5e5c64" stroke-width="0.8"/>'
                    '<rect x="13" y="4" width="6" height="3" rx="1" fill="none" stroke="#5e5c64" stroke-width="1.2"/>'
                    '<path d="M12.5 13v12M16 13v12M19.5 13v12" stroke="#ffffff" stroke-opacity="0.7" stroke-width="1.4"/>'),
    "draco-delete-completed": ('<path d="M5 10h14l-1.3 15a2 2 0 0 1-2 1.8h-7.4a2 2 0 0 1-2-1.8z" fill="url(#red)" '
                              'stroke="#7a1520" stroke-width="0.8"/>'
                              '<rect x="3.5" y="6.5" width="17" height="3.5" rx="1.2" fill="url(#gray)" stroke="#5e5c64" stroke-width="0.8"/>'
                              '<circle cx="23" cy="21" r="7.5" fill="url(#green)" stroke="#fff" stroke-width="1.5"/>'
                              '<path d="M19.5 21l2.5 2.5 4.5-5" fill="none" stroke="#fff" stroke-width="2.2" '
                              'stroke-linecap="round" stroke-linejoin="round"/>'),
    "draco-options": (''.join(f'<rect x="13.4" y="2.5" width="5.2" height="6" rx="1" fill="url(#gray)" '
                               f'stroke="#5e5c64" stroke-width="0.7" transform="rotate({a} 16 16)"/>'
                               for a in range(0, 360, 45))
                     + '<circle cx="16" cy="16" r="10" fill="url(#gray)" stroke="#5e5c64" stroke-width="0.8"/>'
                       '<circle cx="16" cy="16" r="4.2" fill="#f6f5f4" stroke="#5e5c64" stroke-width="0.8"/>'),
    "draco-scheduler": ('<circle cx="16" cy="17" r="12" fill="url(#blue)" stroke="#0b3d7a" stroke-width="0.8"/>'
                       '<circle cx="16" cy="17" r="9.3" fill="#ffffff"/>'
                       + "".join(f'<rect x="15.4" y="8.5" width="1.2" height="2.2" fill="#3d3846" '
                                 f'transform="rotate({a} 16 17)"/>' for a in range(0, 360, 30))
                       + '<path d="M16 11v6.5l4.5 3" fill="none" stroke="#c01c28" stroke-width="2" stroke-linecap="round"/>'
                         '<rect x="5" y="2" width="6" height="4" rx="1.5" fill="url(#gray)" transform="rotate(-30 8 4)"/>'
                         '<rect x="21" y="2" width="6" height="4" rx="1.5" fill="url(#gray)" transform="rotate(30 24 4)"/>'),
    "draco-start-queue": disc("green") + '<path d="M8 9.5v13l8-6.5zM16 9.5v13l8-6.5z" fill="#fff"/>',
    "draco-stop-queue": disc("red") + '<path d="M10.5 10.5l11 11M21.5 10.5l-11 11" stroke="#fff" '
                                     'stroke-width="3.6" stroke-linecap="round"/>',
    "draco-grabber": ('<circle cx="13" cy="13" r="10" fill="url(#blue)" stroke="#0b3d7a" stroke-width="0.8"/>'
                     '<path d="M3 13h20M13 3c-4 4-4 16 0 20M13 3c4 4 4 16 0 20M5 8h16M5 18h16" fill="none" '
                     'stroke="#ffffff" stroke-opacity="0.7" stroke-width="1"/>'
                     '<path d="M20 20l8 8" stroke="#3d3846" stroke-width="4.5" stroke-linecap="round"/>'
                     '<circle cx="13" cy="13" r="10" fill="none" stroke="#3d3846" stroke-width="2.4"/>'),
    "draco-batch": ('<rect x="10" y="3" width="17" height="20" rx="1.5" fill="url(#paper)" stroke="#77767b" stroke-width="0.8"/>'
                   '<rect x="7" y="6" width="17" height="20" rx="1.5" fill="url(#paper)" stroke="#77767b" stroke-width="0.8"/>'
                   '<rect x="4" y="9" width="17" height="20" rx="1.5" fill="url(#paper)" stroke="#77767b" stroke-width="0.8"/>'
                   '<path d="M7 14h11M7 18h11M7 22h8" stroke="#62a0ea" stroke-width="1.6"/>'
                   '<circle cx="24" cy="24" r="6.5" fill="url(#blue)" stroke="#fff" stroke-width="1.4"/>'
                   '<path d="M24 20.5v6M21 24l3 3 3-3" fill="none" stroke="#fff" stroke-width="1.8" '
                   'stroke-linecap="round" stroke-linejoin="round"/>'),
    # ---------------- sidebar
    "draco-folder": folder(),
    "draco-folder-all": folder(badge("blue", '<path d="M23 17.5v7M20 21.5l3 3 3-3" fill="none" stroke-width="1.8" '
                                            'stroke-linecap="round" stroke-linejoin="round"/>')),
    "draco-cat-compressed": folder(badge("orange", '<rect x="20" y="18.5" width="6" height="7" rx="0.8" fill="none" '
                                                  'stroke-width="1.4"/><path d="M23 18.5v3" stroke-width="1.4"/>')),
    "draco-cat-documents": folder(badge("blue", '<path d="M20.5 18.5h5M20.5 21.5h5M20.5 24.5h3.5" stroke-width="1.4"/>')),
    "draco-cat-music": folder(badge("purple", '<circle cx="21.5" cy="24" r="1.8" stroke="none"/>'
                                             '<path d="M23 24v-6.5l3-1" fill="none" stroke-width="1.4"/>')),
    "draco-cat-programs": folder(badge("gray", '<rect x="19.5" y="18.5" width="7" height="6" rx="0.8" fill="none" '
                                              'stroke-width="1.3"/><path d="M19.5 20.3h7" stroke-width="1.3"/>')),
    "draco-cat-video": folder(badge("red", '<path d="M21.5 18.5v7l5-3.5z" stroke="none"/>')),
    "draco-cat-general": folder(),
    "draco-unfinished": folder(badge("orange", '<path d="M23 18v4.5l2.5 1.5" fill="none" stroke-width="1.6" '
                                              'stroke-linecap="round"/>')),
    "draco-finished": folder(badge("green", '<path d="M20 22l2 2 4-4.5" fill="none" stroke-width="1.8" '
                                           'stroke-linecap="round" stroke-linejoin="round"/>')),
    "draco-queues": folder(badge("blue", '<path d="M20 19h6M20 22h6M20 25h6" stroke-width="1.4"/>')),
    "draco-queue": ('<rect x="4" y="5" width="24" height="22" rx="2" fill="url(#paper)" stroke="#77767b" stroke-width="0.8"/>'
                   '<circle cx="9" cy="11" r="1.8" fill="#26a269"/><circle cx="9" cy="16" r="1.8" fill="#26a269"/>'
                   '<circle cx="9" cy="21" r="1.8" fill="#9a9996"/>'
                   '<path d="M13 11h11M13 16h11M13 21h11" stroke="#5e5c64" stroke-width="1.6"/>'),
}

# "Flat" style: same pictures, solid colours, no gloss.
FLAT = {"blue": "#3584e4", "green": "#2ec27e", "red": "#e01b24", "orange": "#ff7800", "gray": "#9a9996",
        "folder": "#f8d34a", "folderback": "#e5a50a", "paper": "#ffffff", "purple": "#9141ac"}


def flat(body):
    import re
    body = re.sub(r'<ellipse [^>]*opacity="0\.28"/>', "", body)          # remove the shine
    return re.sub(r'url\(#(\w+)\)', lambda m: FLAT.get(m.group(1), "#888888"), body)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, body in ICONS.items():
        (out / f"{name}.svg").write_text(svg(body))
        (out / f"{name.replace('draco-', 'draco-flat-')}.svg").write_text(svg(flat(body)))
    print(2 * len(ICONS), "icons written to", out)
