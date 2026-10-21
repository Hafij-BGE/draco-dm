"""Write the "Modern" icon set (draco/icons/draco-m-*.svg): clean gradient glyphs for the
dashboard themes. Run: python3 tools/make_modern_icons.py"""

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "draco" / "icons"


def grad(gid, c1, c2):
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>')


def svg(defs, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24">'
            f'<defs>{defs}<filter id="s" x="-20%" y="-20%" width="140%" height="140%">'
            '<feDropShadow dx="0" dy="0.6" stdDeviation="0.6" flood-color="#000" flood-opacity="0.35"/></filter></defs>'
            f'<g filter="url(#s)">{body}</g></svg>')


GREEN = ("#6ee7b7", "#10b981")
RED = ("#fb7185", "#e11d48")
BLUE = ("#93c5fd", "#2563eb")
VIOLET = ("#c4b5fd", "#7c3aed")
CYAN = ("#67e8f9", "#0891b2")
YELLOW = ("#fde68a", "#f59e0b")
PINK = ("#f9a8d4", "#db2777")
WHITE = ("#ffffff", "#e0e7ff")


def gear():
    teeth = "".join(f'<rect x="10.4" y="2.2" width="3.2" height="4.4" rx="1" transform="rotate({a} 12 12)"/>'
                    for a in range(0, 360, 45))
    return ('<mask id="h"><rect width="24" height="24" fill="#fff"/><circle cx="12" cy="12" r="3" fill="#000"/></mask>'
            f'<g fill="url(#g)" mask="url(#h)">{teeth}<circle cx="12" cy="12" r="7"/></g>')


ICONS = {
    # toolbar tiles
    "add-url": (("#7dd3fc", "#6366f1"), '<path d="M12 4.5v15M4.5 12h15" stroke="url(#g)" stroke-width="3" stroke-linecap="round"/>'),
    "resume": (GREEN, '<path d="M7.5 5.2v13.6c0 .8.9 1.3 1.6.9l10.6-6.8c.6-.4.6-1.4 0-1.8L9.1 4.3c-.7-.4-1.6.1-1.6.9z" '
                      'fill="url(#g)"/>'),
    "stop": (RED, '<rect x="5.5" y="5.5" width="13" height="13" rx="3.2" fill="url(#g)"/>'),
    "stop-all": (RED, '<rect x="5.5" y="4.5" width="4.6" height="15" rx="1.6" fill="url(#g)"/>'
                      '<rect x="13.9" y="4.5" width="4.6" height="15" rx="1.6" fill="url(#g)"/>'),
    "delete": (RED, '<path d="M4.5 6.5h15" stroke="url(#g)" stroke-width="2.2" stroke-linecap="round"/>'
                    '<path d="M9.5 6V4.6c0-.6.4-1 1-1h3c.6 0 1 .4 1 1V6" stroke="url(#g)" stroke-width="1.8" fill="none"/>'
                    '<path d="M6.3 8.5h11.4l-.9 10.6c-.1 1-.9 1.7-1.9 1.7H9.1c-1 0-1.8-.7-1.9-1.7z" fill="url(#g)"/>'
                    '<path d="M10.2 11.5v6M13.8 11.5v6" stroke="#fff" stroke-opacity=".7" stroke-width="1.3" '
                    'stroke-linecap="round"/>'),
    "delete-completed": (RED, '<path d="M6.3 8.5h11.4l-.9 10.6c-.1 1-.9 1.7-1.9 1.7H9.1c-1 0-1.8-.7-1.9-1.7z" fill="url(#g)"/>'
                              '<path d="M4.5 6.5h15" stroke="url(#g)" stroke-width="2.2" stroke-linecap="round"/>'
                              '<path d="M9.3 14.3l1.9 1.9 3.6-3.8" stroke="#fff" stroke-width="1.6" fill="none" '
                              'stroke-linecap="round" stroke-linejoin="round"/>'),
    "options": (BLUE, None),
    "scheduler": (VIOLET, '<circle cx="12" cy="13" r="7.6" fill="none" stroke="url(#g)" stroke-width="2.4"/>'
                          '<path d="M12 9v4.4l3 1.8" stroke="url(#g)" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
                          '<path d="M5 5.6l2.4-2M19 5.6l-2.4-2" stroke="url(#g)" stroke-width="2.2" stroke-linecap="round"/>'),
    "grabber": (CYAN, '<circle cx="12" cy="12" r="8.2" fill="none" stroke="url(#g)" stroke-width="2"/>'
                      '<ellipse cx="12" cy="12" rx="3.6" ry="8.2" fill="none" stroke="url(#g)" stroke-width="1.8"/>'
                      '<path d="M4 9.3h16M4 14.7h16" stroke="url(#g)" stroke-width="1.8"/>'),
    "batch": (VIOLET, '<path d="M12 3.5l8.5 4.3L12 12 3.5 7.8z" fill="url(#g)"/>'
                      '<path d="M4.3 11.6L12 15.4l7.7-3.8M4.3 15.4L12 19.2l7.7-3.8" stroke="url(#g)" stroke-width="2" '
                      'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'),
    "start-queue": (GREEN, '<path d="M4 6.2v11.6c0 .7.8 1.1 1.4.7L13 13v4.8c0 .7.8 1.1 1.4.7l7-5.8c.5-.4.5-1.1 0-1.4l-7-5.8'
                           'c-.6-.4-1.4 0-1.4.7V11L5.4 5.5C4.8 5.1 4 5.5 4 6.2z" fill="url(#g)"/>'),
    "stop-queue": (RED, '<circle cx="12" cy="12" r="8.5" fill="url(#g)"/>'
                        '<path d="M9 9l6 6M15 9l-6 6" stroke="#fff" stroke-width="2" stroke-linecap="round"/>'),
    "cosmic": (CYAN, '<circle cx="12" cy="12" r="5.6" fill="url(#g)"/>'
                     '<ellipse cx="12" cy="12" rx="10" ry="3.6" fill="none" stroke="url(#g)" stroke-width="1.6" '
                     'transform="rotate(-20 12 12)"/><circle cx="19.5" cy="5.5" r="1.3" fill="#fde68a"/>'
                     '<circle cx="4.5" cy="18.5" r="0.9" fill="#fff"/>'),
    "home": (BLUE, '<path d="M3.5 11.2L12 4l8.5 7.2" stroke="url(#g)" stroke-width="2.3" fill="none" '
                   'stroke-linecap="round" stroke-linejoin="round"/><path d="M6 10.5V19c0 .6.4 1 1 1h3.5v-5h3v5H17'
                   'c.6 0 1-.4 1-1v-8.5" fill="url(#g)"/>'),
    "pulse": (CYAN, '<path d="M2.5 12h4l2.2-5.5 4 11 2.6-7 1.6 1.5h4.6" stroke="url(#g)" stroke-width="2.2" '
                    'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'),
    "pie": (CYAN, '<path d="M11 3.2A8.8 8.8 0 1 0 20.8 13H11z" fill="url(#g)"/>'
                  '<path d="M13 1.5v9.5h9.5A9.5 9.5 0 0 0 13 1.5z" fill="url(#g)" opacity=".7"/>'),
    # sidebar
    "folder-all": (BLUE, '<path d="M12 3.5v9.5M8.2 9.4L12 13.2l3.8-3.8" stroke="url(#g)" stroke-width="2.4" fill="none" '
                         'stroke-linecap="round" stroke-linejoin="round"/>'
                         '<path d="M4 14.5v3.3c0 1.2 1 2.2 2.2 2.2h11.6c1.2 0 2.2-1 2.2-2.2v-3.3" stroke="url(#g)" '
                         'stroke-width="2.4" fill="none" stroke-linecap="round"/>'),
    "folder": (YELLOW, '<path d="M3.5 7c0-1.1.9-2 2-2h4.2l2 2h6.8c1.1 0 2 .9 2 2v8.5c0 1.1-.9 2-2 2h-13c-1.1 0-2-.9-2-2z" '
                       'fill="url(#g)"/>'),
    "cat-general": (YELLOW, '<path d="M3.5 7c0-1.1.9-2 2-2h4.2l2 2h6.8c1.1 0 2 .9 2 2v8.5c0 1.1-.9 2-2 2h-13c-1.1 0-2-.9-2-2z" '
                            'fill="url(#g)"/><path d="M3.5 10h17" stroke="#fff" stroke-opacity=".35" stroke-width="1"/>'),
    "cat-compressed": (YELLOW, '<rect x="5" y="3.5" width="14" height="17" rx="2.4" fill="url(#g)"/>'
                               '<path d="M12 3.5v2M12 6.5v2M12 9.5v2" stroke="#7c2d12" stroke-width="1.6"/>'
                               '<rect x="10.3" y="12" width="3.4" height="4.2" rx="1" fill="#7c2d12"/>'),
    "cat-documents": (BLUE, '<path d="M6.5 3.5h7.4l4.6 4.6v11.4c0 .6-.4 1-1 1h-11c-.6 0-1-.4-1-1v-15c0-.6.4-1 1-1z" '
                            'fill="url(#g)"/><path d="M13.9 3.5v4.6h4.6" fill="#dbeafe" fill-opacity=".7"/>'
                            '<path d="M8.5 11.5h7M8.5 14.5h7M8.5 17.2h4.5" stroke="#fff" stroke-width="1.4" '
                            'stroke-linecap="round"/>'),
    "cat-music": (PINK, '<path d="M9.5 16.5V6.2l10-2.2v10.2" stroke="url(#g)" stroke-width="2.2" fill="none" '
                        'stroke-linejoin="round"/><circle cx="7" cy="16.8" r="3" fill="url(#g)"/>'
                        '<circle cx="17" cy="14.5" r="3" fill="url(#g)"/>'),
    "cat-programs": (VIOLET, '<rect x="3.5" y="3.5" width="7.5" height="7.5" rx="2" fill="url(#g)"/>'
                             '<rect x="13" y="3.5" width="7.5" height="7.5" rx="2" fill="url(#g)" opacity=".75"/>'
                             '<rect x="3.5" y="13" width="7.5" height="7.5" rx="2" fill="url(#g)" opacity=".75"/>'
                             '<rect x="13" y="13" width="7.5" height="7.5" rx="2" fill="url(#g)"/>'),
    "cat-video": (VIOLET, '<rect x="3" y="5" width="18" height="14" rx="3.4" fill="url(#g)"/>'
                          '<path d="M10 9v6l5-3z" fill="#fff"/>'),
    "unfinished": (GREEN, '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" stroke="url(#g)" stroke-width="2.6" fill="none" '
                          'stroke-linecap="round"/><path d="M19.8 4.2v4.6h-4.6" stroke="url(#g)" stroke-width="2.4" '
                          'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'),
    "finished": (GREEN, '<circle cx="12" cy="12" r="9" fill="url(#g)"/>'
                        '<path d="M7.8 12.3l2.8 2.8 5.6-6" stroke="#fff" stroke-width="2.2" fill="none" '
                        'stroke-linecap="round" stroke-linejoin="round"/>'),
    "queues": (BLUE, '<path d="M9 6.5h11M9 12h11M9 17.5h11" stroke="url(#g)" stroke-width="2.4" stroke-linecap="round"/>'
                     '<circle cx="4.8" cy="6.5" r="1.6" fill="url(#g)"/><circle cx="4.8" cy="12" r="1.6" fill="url(#g)"/>'
                     '<circle cx="4.8" cy="17.5" r="1.6" fill="url(#g)"/>'),
    "queue": (CYAN, '<path d="M4 7h16M4 12h16M4 17h10" stroke="url(#g)" stroke-width="2.4" stroke-linecap="round"/>'
                    '<path d="M17 15l3 2-3 2z" fill="url(#g)"/>'),
}


def main():
    for name, ((c1, c2), body) in ICONS.items():
        body = gear() if name == "options" else body
        (OUT / f"draco-m-{name}.svg").write_text(svg(grad("g", c1, c2), body))
    print(f"wrote {len(ICONS)} icons to {OUT}")


if __name__ == "__main__":
    main()
