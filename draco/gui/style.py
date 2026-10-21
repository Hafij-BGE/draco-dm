"""Themes. Each theme is a small colour palette; one CSS template turns it into the whole look
(libadwaita named colours + Draco's toolbar, category tree, list and status bar).

Icons are plain SVG files in draco/icons/ named draco-*.svg. Replace any of them with
your own artwork (same file name) to change the look; no code changes needed.

Add a theme: copy an entry in THEMES, change the colours, restart Draco.
"""

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

ICON_DIR = Path(__file__).resolve().parent.parent / "icons"


def _light(**kw):
    base = dict(
        dark=False, font="", list_font="",
        window_bg="#f6f7f9", fg="#1c1c1c", view_bg="#ffffff", dim="#5e5c64",
        header_bg="#ebedf0", header_fg="#1c1c1c",
        menubar_bg="#f5f6f7", border="#c3ccd8",
        tool_top="#fdfeff", tool_mid="#eef3f9", tool_bottom="#dfe8f3", tool_border="#aebdd0", tool_fg="#1c1c1c",
        hover_top="#fffaf0", hover_bottom="#fde9b8", hover_border="#e3c06a",
        press_top="#fbe2a0", press_bottom="#f7d27a",
        pane_top="#f7f9fc", pane_bottom="#e3eaf3", pane_fg="#2a3a52",
        sel_bg="#cfe3fb", sel_fg="#000000", hover_row="#f2f7fd", row_line="#f0f2f5",
        colhead_top="#ffffff", colhead_bottom="#eef1f5",
        status_bg="#f0f1f3", accent="#1c71d8", accent_fg="#ffffff",
        ok="#1a7f37", err="#c01c28", active="#1a5fb4", radius="3px",
    )
    base.update(kw)
    return base


def _dark(**kw):
    base = dict(
        dark=True, font="", list_font="",
        window_bg="#1e1f22", fg="#e8e8ea", view_bg="#18191b", dim="#a0a0a8",
        header_bg="#25262a", header_fg="#e8e8ea",
        menubar_bg="#222326", border="#34363c",
        tool_top="#2d2f34", tool_mid="#27292d", tool_bottom="#222326", tool_border="#34363c", tool_fg="#e8e8ea",
        hover_top="#3a3d44", hover_bottom="#33363c", hover_border="#4b5059",
        press_top="#2a2c31", press_bottom="#25272b",
        pane_top="#26282c", pane_bottom="#222326", pane_fg="#d0d3da",
        sel_bg="#2b4a74", sel_fg="#ffffff", hover_row="#24272c", row_line="#222428",
        colhead_top="#26282c", colhead_bottom="#212226",
        status_bg="#1b1c1f", accent="#3584e4", accent_fg="#ffffff",
        ok="#57e389", err="#ff7b72", active="#78aeed", radius="3px",
    )
    base.update(kw)
    return base


THEMES = {
    "system": {"name": "Follow desktop (Adwaita)"},
    "classic": {"name": "Draco Classic", **_light()},
    # Retro desktop look: grey 3D toolbar, white grid, blue selection, compact font.
    "retro": {"name": "Retro Gray", **_light(
        font="'DejaVu Sans', 'Noto Sans', sans-serif", list_font="9pt",
        window_bg="#f0f0f0", header_bg="#ffffff", menubar_bg="#f0f0f0", border="#a0a0a0",
        tool_top="#fbfbfb", tool_mid="#f0f0f0", tool_bottom="#e3e3e3", tool_border="#a0a0a0",
        hover_top="#e5f3fb", hover_bottom="#cce8f7", hover_border="#7eb4ea",
        press_top="#cce4f7", press_bottom="#b5d6f1",
        pane_top="#f0f0f0", pane_bottom="#e1e1e1", pane_fg="#000000",
        sel_bg="#3399ff", sel_fg="#ffffff", hover_row="#e5f3fb", row_line="#ececec",
        colhead_top="#ffffff", colhead_bottom="#f0f0f0", status_bg="#f0f0f0",
        accent="#0078d7", ok="#007a00", err="#d00000", active="#0050b0", radius="0px")},
    "soft-light": {"name": "Soft Light", **_light(
        font="'Inter', 'Noto Sans', 'Cantarell', sans-serif",
        window_bg="#f3f3f3", header_bg="#f3f3f3", menubar_bg="#f9f9f9", border="#e5e5e5",
        tool_top="#f9f9f9", tool_mid="#f9f9f9", tool_bottom="#f3f3f3", tool_border="#e5e5e5",
        hover_top="#eaeaea", hover_bottom="#eaeaea", hover_border="#e0e0e0",
        press_top="#e0e0e0", press_bottom="#e0e0e0",
        pane_top="#f9f9f9", pane_bottom="#f3f3f3", pane_fg="#1b1b1b",
        sel_bg="#dbeafb", sel_fg="#000000", hover_row="#f5f5f5", row_line="#f3f3f3",
        colhead_top="#fbfbfb", colhead_bottom="#f9f9f9", status_bg="#f3f3f3",
        accent="#005fb8", radius="6px")},
    "galaxy": {"name": "Galaxy (dark violet)", **_dark(
        window_bg="#14121f", view_bg="#100e1a", header_bg="#1c1830", menubar_bg="#181528", border="#2e2850",
        tool_top="#2a2348", tool_mid="#211c3a", tool_bottom="#1a162e", tool_border="#3a3164",
        hover_top="#3d3270", hover_bottom="#322a5c", hover_border="#6a5acd",
        pane_top="#211c3a", pane_bottom="#1a162e", pane_fg="#d9d2ff",
        sel_bg="#4b3d8f", hover_row="#1d1933", row_line="#1a1730",
        colhead_top="#211c3a", colhead_bottom="#1a162e", status_bg="#120f1d",
        accent="#9b7bff", active="#b9a6ff")},
    "dark": {"name": "Dark", **_dark()},
    "midnight": {"name": "Midnight Blue", **_dark(
        window_bg="#0f1726", view_bg="#0c1320", header_bg="#14203a", menubar_bg="#111b30", border="#22314f",
        tool_top="#1b2a4a", tool_mid="#16233f", tool_bottom="#121d35", tool_border="#2a3b60",
        hover_top="#24406e", hover_bottom="#1e365d", hover_border="#3b6bb5",
        pane_top="#16233f", pane_bottom="#121d35", pane_fg="#cfe0ff",
        sel_bg="#1f4f8f", hover_row="#132038", row_line="#111c30",
        colhead_top="#16233f", colhead_bottom="#121d35", status_bg="#0d1422",
        accent="#4c9aff", active="#86b8ff")},
    "nightshade": {"name": "Nightshade", **_dark(
        window_bg="#282a36", fg="#f8f8f2", view_bg="#21222c", header_bg="#343746", menubar_bg="#2b2d3a",
        border="#44475a", tool_top="#3a3c4e", tool_mid="#343746", tool_bottom="#2d2f3d", tool_border="#44475a",
        hover_top="#4d5068", hover_bottom="#44475a", hover_border="#bd93f9",
        pane_top="#343746", pane_bottom="#2d2f3d", pane_fg="#f8f8f2",
        sel_bg="#44475a", hover_row="#2b2d3a", row_line="#262833",
        colhead_top="#343746", colhead_bottom="#2d2f3d", status_bg="#21222c",
        accent="#bd93f9", ok="#50fa7b", err="#ff5555", active="#8be9fd")},
    "arctic": {"name": "Arctic Frost", **_dark(
        window_bg="#2e3440", fg="#eceff4", view_bg="#2b303b", header_bg="#3b4252", menubar_bg="#323846",
        border="#434c5e", tool_top="#434c5e", tool_mid="#3b4252", tool_bottom="#353b49", tool_border="#4c566a",
        hover_top="#4c566a", hover_bottom="#434c5e", hover_border="#88c0d0",
        pane_top="#3b4252", pane_bottom="#353b49", pane_fg="#e5e9f0",
        sel_bg="#5e81ac", hover_row="#323846", row_line="#2f3542",
        colhead_top="#3b4252", colhead_bottom="#353b49", status_bg="#2b303b",
        accent="#88c0d0", accent_fg="#2e3440", ok="#a3be8c", err="#bf616a", active="#81a1c1")},
    "sand": {"name": "Sand Light", **_light(
        window_bg="#fdf6e3", fg="#586e75", view_bg="#fffbef", header_bg="#eee8d5", menubar_bg="#f5efdc",
        border="#d9d2bc", tool_top="#fdf6e3", tool_mid="#f3ecd8", tool_bottom="#eee8d5", tool_border="#d3cbb2",
        hover_top="#fff4cf", hover_bottom="#f7e7b0", hover_border="#b58900",
        pane_top="#f5efdc", pane_bottom="#eee8d5", pane_fg="#073642",
        sel_bg="#e6dcbc", sel_fg="#073642", hover_row="#f7f0dc", row_line="#f1ead6",
        colhead_top="#fdf6e3", colhead_bottom="#eee8d5", status_bg="#eee8d5",
        accent="#268bd2", ok="#859900", err="#dc322f", active="#268bd2")},
    "deep-teal": {"name": "Deep Teal", **_dark(
        window_bg="#002b36", fg="#93a1a1", view_bg="#00252f", header_bg="#073642", menubar_bg="#03303b",
        border="#0d4552", tool_top="#0a3f4c", tool_mid="#073642", tool_bottom="#04313c", tool_border="#14505e",
        hover_top="#145565", hover_bottom="#0f4a58", hover_border="#2aa198",
        pane_top="#073642", pane_bottom="#04313c", pane_fg="#eee8d5",
        sel_bg="#0f5566", hover_row="#03303b", row_line="#022d38",
        colhead_top="#073642", colhead_bottom="#04313c", status_bg="#00252f",
        accent="#268bd2", ok="#859900", err="#dc322f", active="#2aa198")},
    "forest": {"name": "Forest", **_light(
        window_bg="#f3f7f2", view_bg="#ffffff", header_bg="#e4eee2", menubar_bg="#eef4ec", border="#c5d6c1",
        tool_top="#fbfdfb", tool_mid="#edf5eb", tool_bottom="#dceadb", tool_border="#a9c4a4",
        hover_top="#f4fbe9", hover_bottom="#dff2c4", hover_border="#8fbf5a",
        pane_top="#f3f8f1", pane_bottom="#e1ecde", pane_fg="#24452a",
        sel_bg="#cde8c8", hover_row="#f1f8ef", row_line="#eef4ec",
        colhead_top="#ffffff", colhead_bottom="#edf3eb", status_bg="#ebf2e9",
        accent="#2f8f46", active="#2f7a3d")},
    "sunset": {"name": "Sunset", **_light(
        window_bg="#fdf5f0", view_bg="#fffdfb", header_bg="#fbe7dc", menubar_bg="#fcefe7", border="#ecc9b6",
        tool_top="#fffaf6", tool_mid="#fdeee4", tool_bottom="#f9dfd0", tool_border="#e6b499",
        hover_top="#fff1e4", hover_bottom="#ffd9b8", hover_border="#f08a4b",
        pane_top="#fdf1ea", pane_bottom="#f9e1d4", pane_fg="#6b2f14",
        sel_bg="#fcd3bd", hover_row="#fdf3ec", row_line="#f9ece4",
        colhead_top="#fffdfb", colhead_bottom="#fbeee6", status_bg="#fbeee6",
        accent="#e66100", active="#c64600")},
    "high-contrast": {"name": "High Contrast", **_dark(
        window_bg="#000000", fg="#ffffff", view_bg="#000000", dim="#ffffff", header_bg="#000000",
        menubar_bg="#000000", border="#ffffff", tool_top="#000000", tool_mid="#000000", tool_bottom="#000000",
        tool_border="#ffffff", hover_top="#1a1a1a", hover_bottom="#1a1a1a", hover_border="#ffff00",
        pane_top="#000000", pane_bottom="#000000", pane_fg="#ffffff",
        sel_bg="#ffff00", sel_fg="#000000", hover_row="#1a1a1a", row_line="#444444",
        colhead_top="#000000", colhead_bottom="#000000", status_bg="#000000",
        accent="#ffff00", accent_fg="#000000", ok="#00ff00", err="#ff4040", active="#00ffff", radius="0px")},
}

# ---------------------------------------------------------------- modern (dashboard) themes
# These switch the main window to the dashboard layout (stats header, rounded cards, progress
# column, details pane) and draw over a background picture from draco/art/.
ART_DIR = Path(__file__).resolve().parent.parent / "art"


def _modern(**kw):
    base = dict(
        dark=True, bg="bg-galaxy-explorer.jpg", base="#070a22", base2="#0b0f30",
        panel="rgba(12,16,48,0.80)", panel_solid="#0e1338", border="rgba(110,130,255,0.28)",
        fg="#e8ecff", dim="#9aa4d6", a1="#5a5cff", a2="#1fb8ff", accent="#5b7bff", accent_fg="#ffffff",
        tile="rgba(22,28,80,0.72)", tile_hover="rgba(52,64,160,0.85)", tile_border="rgba(120,140,255,0.32)",
        sel="rgba(78,96,255,0.34)", hover="rgba(90,110,255,0.12)", line="rgba(120,140,255,0.08)",
        p1="#7b5cff", p2="#20c4ff", ok1="#18c964", ok2="#7dff9a", ok="#36e07a", err="#ff5b7b",
        warn="#ffb020", active="#5aa8ff", glow="rgba(90,110,255,0.45)", trough="rgba(255,255,255,0.08)",
        radius="14px", pw="galaxy", pct="#ffffff", pct_shadow="0 1px 2px rgba(0,0,0,0.6)",
    )
    base.update(kw)
    return base


MODERN = {
    "galaxy-explorer": {"name": "Galaxy Explorer (dashboard)", **_modern()},
    "cosmic-minimal": {"name": "Cosmic Minimal (dashboard)", **_modern(
        bg="bg-cosmic-minimal.jpg", base="#060b1e", base2="#08102a", panel="rgba(9,15,38,0.92)",
        panel_solid="#0a1230", border="rgba(80,120,220,0.25)", a1="#2f6bff", a2="#2f9bff",
        tile="rgba(16,26,60,0.85)", tile_hover="rgba(36,60,130,0.9)", tile_border="rgba(80,120,220,0.3)",
        glow="rgba(47,107,255,0.35)")},
    "nebula-glow": {"name": "Nebula Glow (dashboard)", **_modern(
        bg="bg-nebula-glow.jpg", base="#180626", base2="#260a3a", panel="rgba(32,10,54,0.74)",
        panel_solid="#260a40", border="rgba(255,90,220,0.30)", fg="#fbeaff", dim="#c9a3dc",
        a1="#ff4fd8", a2="#8a5cff", accent="#d75cff", tile="rgba(60,16,90,0.70)",
        tile_hover="rgba(120,30,150,0.85)", tile_border="rgba(255,110,230,0.35)",
        sel="rgba(220,80,255,0.32)", hover="rgba(255,90,220,0.12)", line="rgba(255,120,230,0.08)",
        p1="#ff4fd8", p2="#8a5cff", glow="rgba(255,79,216,0.45)", active="#ff8ae8", pw="music")},
    "aurora-light": {"name": "Aurora Light (dashboard)", **_modern(
        dark=False, bg="bg-aurora-light.jpg", base="#eceeff", base2="#f6f4ff",
        panel="rgba(255,255,255,0.76)", panel_solid="#f8f8ff", border="rgba(140,140,220,0.35)",
        fg="#1d2140", dim="#6a6f95", a1="#6b5cff", a2="#3c8bff", accent="#5b5cff",
        tile="rgba(255,255,255,0.85)", tile_hover="rgba(230,232,255,0.95)", tile_border="rgba(140,140,220,0.40)",
        sel="rgba(108,92,255,0.18)", hover="rgba(108,92,255,0.08)", line="rgba(40,40,120,0.06)",
        p1="#7b5cff", p2="#3c8bff", ok="#13a456", err="#e0344f", active="#3c6bff",
        glow="rgba(108,92,255,0.25)", trough="rgba(40,40,120,0.10)", pw="compressed",
        pct="#1d2140", pct_shadow="0 0 3px rgba(255,255,255,0.9)")},
}

# Progress-window looks per download category in the dashboard themes.
PROGRESS_STYLES = {
    "galaxy": dict(dark=True, art="ill-galaxy.png", bg="bg-galaxy-explorer.jpg", base="#070b26",
                   panel="rgba(14,20,60,0.82)", border="rgba(90,140,255,0.40)", fg="#e8ecff", dim="#9aa4d6",
                   a1="#6b4dff", a2="#1fb8ff", tile="rgba(22,30,80,0.80)", seg_bg="#13204a",
                   seg_done="#2a8cff", seg_head="#ff8a1f", name="Galaxy Explorer"),
    "documents": dict(dark=True, art="ill-documents.png", bg="pw-documents.jpg", base="#05221b",
                      panel="rgba(6,40,32,0.84)", border="rgba(40,200,150,0.38)", fg="#e6fff6", dim="#8fcab5",
                      a1="#13b878", a2="#12d6c8", tile="rgba(10,60,46,0.85)", seg_bg="#0b3a2e",
                      seg_done="#16c98a", seg_head="#ffd54a", name="Starlight Forest"),
    "music": dict(dark=True, art="ill-music.png", bg="pw-music.jpg", base="#17072c",
                  panel="rgba(34,10,60,0.82)", border="rgba(255,80,200,0.38)", fg="#fdeaff", dim="#cf9fe0",
                  a1="#ff3d9a", a2="#9b4dff", tile="rgba(60,16,96,0.85)", seg_bg="#2c0f4a",
                  seg_done="#d24dff", seg_head="#ffd54a", name="Aurora Music"),
    "video": dict(dark=True, art="ill-video.png", bg="pw-video.jpg", base="#1a0d07",
                  panel="rgba(40,18,10,0.84)", border="rgba(255,140,50,0.40)", fg="#fff1e6", dim="#e0b090",
                  a1="#ff6a1a", a2="#ffc040", tile="rgba(70,32,14,0.85)", seg_bg="#3a1d0e",
                  seg_done="#ff8a1f", seg_head="#fff06a", name="Cinematic Horizon"),
    "compressed": dict(dark=False, art="ill-compressed.png", bg="pw-compressed.jpg", base="#eef0ff",
                       panel="rgba(255,255,255,0.84)", border="rgba(120,120,230,0.40)", fg="#1d2140",
                       dim="#6a6f95", a1="#5b4dff", a2="#7b8bff", tile="rgba(240,242,255,0.95)",
                       seg_bg="#dfe2fb", seg_done="#5b5cff", seg_head="#ff8a1f", name="Nebula Archive"),
}
CATEGORY_PROGRESS = {"Documents": "documents", "Music": "music", "Video": "video", "Compressed": "compressed"}


def is_modern(key):
    return key in MODERN


def progress_style(theme, category, chosen=None):
    """Which progress look a download gets (None = the plain classic window). `chosen` is the
    user's choice per category from Options (missing or "auto" = the built-in pick)."""
    if not is_modern(theme):
        return None
    pick = (chosen or {}).get(category or "General", "auto")
    if pick in PROGRESS_STYLES:
        return pick
    return CATEGORY_PROGRESS.get(category) or MODERN[theme]["pw"]


def seg_colors(pstyle):
    p = PROGRESS_STYLES.get(pstyle or "")
    return (p["seg_bg"], p["seg_done"], p["seg_head"]) if p else ("#e8edf3", "#3584e4", "#e66100")


# ---------------------------------------------------------------- icon styles
ICON_STYLES = [("auto", "Match theme"), ("color", "Colourful"), ("flat", "Flat"),
               ("mono", "Monochrome"), ("accent", "Accent colour")]
# Which icon style each theme uses when the choice is "Match theme".
THEME_ICONS = {"system": "mono", "classic": "color", "retro": "color", "soft-light": "flat", "galaxy": "accent",
               "dark": "mono", "midnight": "accent", "nightshade": "accent", "arctic": "accent",
               "sand": "flat", "deep-teal": "accent", "forest": "flat", "sunset": "flat",
               "high-contrast": "mono", "galaxy-explorer": "color", "cosmic-minimal": "color",
               "nebula-glow": "color", "aurora-light": "color"}
def current_theme(key):
    """A saved theme name, or Draco Classic if it no longer exists (themes were renamed in 1.4.4)."""
    return key if key in THEMES or key in MODERN else "classic"
# Line icons for the monochrome/accent styles (GTK recolours them to match the theme).
SYMBOLIC = {
    "add-url": "list-add-symbolic", "resume": "media-playback-start-symbolic",
    "stop": "media-playback-pause-symbolic", "stop-all": "media-playback-stop-symbolic",
    "delete": "user-trash-symbolic", "delete-completed": "edit-clear-all-symbolic",
    "options": "emblem-system-symbolic", "scheduler": "alarm-symbolic",
    "start-queue": "media-seek-forward-symbolic", "stop-queue": "process-stop-symbolic",
    "grabber": "system-search-symbolic", "batch": "view-list-bullet-symbolic",
    "folder": "folder-symbolic", "folder-all": "folder-download-symbolic",
    "cat-compressed": "package-x-generic-symbolic", "cat-documents": "x-office-document-symbolic",
    "cat-music": "audio-x-generic-symbolic", "cat-programs": "application-x-executable-symbolic",
    "cat-video": "video-x-generic-symbolic", "cat-general": "folder-symbolic",
    "unfinished": "content-loading-symbolic", "finished": "emblem-ok-symbolic",
    "queues": "view-list-ordered-symbolic", "queue": "view-list-symbolic",
}
# Semantic tint in the accent style: go = success colour, danger = error colour, rest = accent.
ICON_ROLE = {"resume": "go", "start-queue": "go", "stop-all": "danger", "delete": "danger",
             "delete-completed": "danger", "stop-queue": "danger"}


def resolve_icon_style(theme, choice):
    if choice and choice != "auto":
        return choice
    return THEME_ICONS.get(theme, "color")


def icon_name(base, style):
    if style == "color":
        return f"draco-{base}"
    if style == "flat":
        return f"draco-flat-{base}"
    return SYMBOLIC.get(base, "image-missing-symbolic")


TEMPLATE = """
@define-color window_bg_color {window_bg};
@define-color window_fg_color {fg};
@define-color view_bg_color {view_bg};
@define-color view_fg_color {fg};
@define-color headerbar_bg_color {header_bg};
@define-color headerbar_fg_color {header_fg};
@define-color headerbar_backdrop_color {header_bg};
@define-color popover_bg_color {view_bg};
@define-color popover_fg_color {fg};
@define-color dialog_bg_color {window_bg};
@define-color dialog_fg_color {fg};
@define-color card_bg_color {view_bg};
@define-color card_fg_color {fg};
@define-color accent_bg_color {accent};
@define-color accent_fg_color {accent_fg};
@define-color accent_color {accent};
@define-color sidebar_bg_color {view_bg};
@define-color sidebar_fg_color {fg};

window, .background {{ {font_rule} }}
.draco-menubar {{ background: {menubar_bg}; color: {fg}; border-bottom: 1px solid {border}; padding: 0 2px; }}
.draco-menubar item {{ padding: 3px 9px; }}

.draco-toolbar {{
  background: linear-gradient(to bottom, {tool_top} 0%, {tool_mid} 55%, {tool_bottom} 100%);
  border-bottom: 1px solid {tool_border}; padding: 3px 6px 2px 6px;
}}
.draco-toolbar button.tool {{
  min-width: 62px; padding: 3px 4px; border-radius: {radius};
  background: none; box-shadow: none; border: 1px solid transparent; color: {tool_fg};
}}
.draco-toolbar button.tool:hover {{
  background: linear-gradient(to bottom, {hover_top}, {hover_bottom}); border: 1px solid {hover_border};
}}
.draco-toolbar button.tool:active {{ background: linear-gradient(to bottom, {press_top}, {press_bottom}); }}
.draco-toolbar button.tool:disabled {{ opacity: 0.45; }}
.draco-toolbar button.tool label {{ font-size: 9pt; }}
.draco-toolbar separator {{ background: {tool_border}; margin: 6px 5px; min-width: 1px; }}

.draco-sidebar {{ background: {view_bg}; border-right: 1px solid {border}; }}
.draco-pane-title {{
  background: linear-gradient(to bottom, {pane_top}, {pane_bottom}); border-bottom: 1px solid {border};
  padding: 4px 8px; font-weight: bold; color: {pane_fg};
}}
.draco-sidebar list {{ background: {view_bg}; color: {fg}; }}
.draco-sidebar row {{ padding: 1px 2px; border-radius: {radius}; min-height: 22px; }}
.draco-sidebar row button {{ min-height: 16px; min-width: 16px; padding: 0; margin: 0; }}
.draco-sidebar row:selected {{ background: {sel_bg}; color: {sel_fg}; }}
.draco-sidebar row:hover:not(:selected) {{ background: {hover_row}; }}

columnview.draco-list {{ background: {view_bg}; color: {fg}; {list_font_rule} }}
columnview.draco-list > header > button {{
  background: linear-gradient(to bottom, {colhead_top}, {colhead_bottom});
  border-right: 1px solid {border}; border-bottom: 1px solid {border};
  padding: 3px 6px; font-weight: normal; color: {fg}; border-radius: 0;
}}
columnview.draco-list > listview > row {{ border-bottom: 1px solid {row_line}; }}
columnview.draco-list > listview > row > cell {{ padding: 1px 6px; }}
columnview.draco-list > listview > row:selected {{ background: {sel_bg}; color: {sel_fg}; }}
columnview.draco-list > listview > row:selected label {{ color: {sel_fg}; }}
columnview.draco-list > listview > row:hover:not(:selected) {{ background: {hover_row}; }}
.draco-status-complete {{ color: {ok}; }}
.draco-status-error {{ color: {err}; }}
.draco-status-active {{ color: {active}; font-weight: bold; }}

.draco-statusbar {{ background: {status_bg}; color: {fg}; border-top: 1px solid {border}; padding: 2px 8px; }}

.draco-dialog-head {{ font-size: 11pt; font-weight: bold; }}
.draco-field-title {{ color: {dim}; }}
.draco-segbar {{ border: 1px solid {border}; }}
.draco-conn-table label {{ font-family: monospace; font-size: 9pt; }}
.draco-conn-table .head {{ font-weight: bold; font-family: sans-serif; }}
notebook.draco-tabs > header {{ background: {pane_bottom}; }}

.draco-icons-mono image.draco-icon {{ color: {tool_fg}; }}
.draco-icons-mono .draco-sidebar image.draco-icon {{ color: {fg}; }}
.draco-icons-accent image.draco-icon {{ color: {accent}; }}
.draco-icons-accent image.draco-icon.go {{ color: {ok}; }}
.draco-icons-accent image.draco-icon.danger {{ color: {err}; }}
"""

MODERN_TEMPLATE = """
@define-color window_bg_color {base};
@define-color window_fg_color {fg};
@define-color view_bg_color {panel_solid};
@define-color view_fg_color {fg};
@define-color headerbar_bg_color {base};
@define-color headerbar_fg_color {fg};
@define-color headerbar_backdrop_color {base};
@define-color popover_bg_color {panel_solid};
@define-color popover_fg_color {fg};
@define-color dialog_bg_color {base2};
@define-color dialog_fg_color {fg};
@define-color card_bg_color {panel_solid};
@define-color card_fg_color {fg};
@define-color accent_bg_color {accent};
@define-color accent_fg_color {accent_fg};
@define-color accent_color {accent};
@define-color sidebar_bg_color {panel_solid};
@define-color sidebar_fg_color {fg};

window.background {{ background: linear-gradient(160deg, {base} 0%, {base2} 100%); color: {fg}; }}
window.dm-window {{
  background-color: {base}; background-image: url("{bg_url}");
  background-size: cover; background-position: center top; background-repeat: no-repeat;
}}
.dm-header {{ padding: 10px 14px 6px 14px; }}
.dm-brand-title {{ font-size: 21pt; font-weight: 800; color: {fg}; }}
.dm-brand-sub {{ font-size: 12pt; color: {fg}; }}
.dm-brand-tag {{ font-size: 9pt; color: {a2}; }}
.dm-tiles {{ margin-top: 4px; }}
button.dm-tile {{
  min-width: 74px; min-height: 66px; padding: 4px 6px; border-radius: 12px; color: {fg};
  background: {tile}; border: 1px solid {tile_border}; box-shadow: 0 2px 8px rgba(0,0,0,0.25);
}}
button.dm-tile:hover {{ background: {tile_hover}; box-shadow: 0 0 14px {glow}; }}
button.dm-tile:disabled > box {{ opacity: 0.4; }}
button.dm-tile label {{ font-size: 9.5pt; }}
button.dm-tile.primary {{
  background: linear-gradient(135deg, {a1}, {a2}); color: #ffffff; border-color: transparent;
  box-shadow: 0 0 18px {glow};
}}
button.dm-icon-btn {{
  min-width: 38px; min-height: 38px; border-radius: 10px; background: {tile}; border: 1px solid {tile_border};
}}
button.dm-icon-btn:hover {{ background: {tile_hover}; }}
.dm-card {{
  background: {panel}; border: 1px solid {border}; border-radius: {radius};
  box-shadow: 0 4px 22px rgba(0,0,0,0.30);
}}
.dm-stat-title {{ color: {dim}; font-size: 9.5pt; }}
.dm-stat-value {{ font-size: 18pt; font-weight: 800; color: {fg}; }}
.dm-ring-label {{ font-size: 9pt; color: {dim}; }}
.dm-stat-big {{ font-size: 24pt; }}
.dm-ring-num {{ font-size: 13pt; font-weight: 800; color: {fg}; }}

.dm-side {{ padding: 8px; }}
.dm-side list {{ background: none; color: {fg}; }}
.dm-side row {{ border-radius: 10px; padding: 6px 8px; margin: 1px 0; }}
.dm-side row:hover:not(:selected) {{ background: {hover}; }}
.dm-side row:selected {{ background: linear-gradient(90deg, {a1}, {a2}); color: #ffffff; box-shadow: 0 0 12px {glow}; }}
.dm-side row:selected label {{ color: #ffffff; }}
.dm-side-head {{ color: {dim}; font-weight: bold; font-size: 9.5pt; margin: 10px 8px 2px 8px; }}
.dm-badge {{
  background: {tile}; border: 1px solid {tile_border}; border-radius: 9px; padding: 0 8px;
  font-size: 9pt; min-width: 18px;
}}
.dm-side row:selected .dm-badge {{ background: rgba(255,255,255,0.22); border-color: transparent; }}

.dm-tabs togglebutton {{
  border-radius: 10px; padding: 5px 14px; background: {tile}; border: 1px solid {tile_border}; color: {fg};
}}
.dm-tabs togglebutton:checked {{
  background: linear-gradient(135deg, {a1}, {a2}); color: #ffffff; border-color: transparent;
  box-shadow: 0 0 12px {glow};
}}
.dm-search, .dm-search > text {{ background: {tile}; border-radius: 10px; color: {fg}; }}

columnview.dm-list {{ background: none; color: {fg}; }}
columnview.dm-list > header > button {{
  background: none; border: none; border-bottom: 1px solid {border}; color: {dim};
  padding: 6px 8px; font-weight: normal; box-shadow: none;
}}
columnview.dm-list > listview {{ background: none; }}
columnview.dm-list > listview > row {{ border-bottom: 1px solid {line}; min-height: 34px; }}
columnview.dm-list > listview > row > cell {{ padding: 2px 8px; }}
columnview.dm-list > listview > row:hover:not(:selected) {{ background: {hover}; }}
columnview.dm-list > listview > row:selected {{ background: {sel}; color: {fg}; }}

progressbar.dm-progress > trough {{ background: {trough}; border-radius: 8px; min-height: 16px; border: none; }}
progressbar.dm-progress > trough > progress {{
  background: linear-gradient(90deg, {p1}, {p2}); border-radius: 8px; min-height: 16px; border: none;
}}
progressbar.dm-progress.done > trough > progress {{ background: linear-gradient(90deg, {ok1}, {ok2}); }}
progressbar.dm-progress.failed > trough > progress {{ background: {err}; }}
.dm-pct {{ font-size: 8.5pt; font-weight: bold; color: {pct}; text-shadow: {pct_shadow}; }}
.draco-status-complete {{ color: {ok}; }}
.draco-status-error {{ color: {err}; }}
.draco-status-active {{ color: {active}; font-weight: bold; }}

.dm-status {{ padding: 8px 14px; margin: 0 12px 10px 12px; }}
.dm-status-sep {{ background: {border}; min-width: 1px; margin: 4px 6px; }}
.dm-dot {{ min-width: 12px; min-height: 12px; border-radius: 6px; background: {ok}; }}
switch:checked {{ background: linear-gradient(90deg, {a1}, {a2}); }}

.dm-details notebook > header {{ background: none; border: none; }}
.dm-details notebook > header tab {{ border-radius: 10px 10px 0 0; padding: 4px 8px; }}
.dm-details notebook > header tab:checked {{ background: linear-gradient(135deg, {a1}, {a2}); color: #ffffff; }}
.dm-big-pct {{ font-size: 26pt; font-weight: 800; color: {fg}; }}
.dm-details .pw-card {{ background: rgba(0,0,0,0.12); border: 1px solid {border}; border-radius: 12px; }}
.dm-details .pw-pad {{ padding: 10px; }}
.dm-details .pw-pct {{ color: {a2}; font-weight: bold; }}
.dm-details .draco-dialog-head {{ color: {a2}; }}
.dm-details button.pw-main {{ background: linear-gradient(135deg, {a1}, {a2}); color: #ffffff; }}

.draco-dialog-head {{ font-size: 11pt; font-weight: bold; }}
.draco-field-title {{ color: {dim}; }}
.draco-conn-table label {{ font-family: monospace; font-size: 9pt; }}
.draco-conn-table .head {{ font-weight: bold; font-family: sans-serif; }}
popover.menu contents, popover > contents {{ background: {panel_solid}; color: {fg}; }}
button.suggested-action {{ background: linear-gradient(135deg, {a1}, {a2}); color: #ffffff; }}
{progress_css}
"""

PROGRESS_TEMPLATE = """
window.pw-{key} {{
  background-color: {base}; background-image: url("{bg_url}"); background-size: cover; color: {fg};
}}
window.pw-{key} headerbar {{ background: none; box-shadow: none; color: {fg}; }}
window.pw-{key} .pw-title {{ font-size: 13pt; font-weight: bold; color: {fg}; }}
window.pw-{key} .pw-pct {{ color: {a2}; font-weight: bold; }}
window.pw-{key} notebook, window.pw-{key} notebook > stack {{ background: none; }}
window.pw-{key} notebook > header {{ background: none; border: none; }}
window.pw-{key} notebook > header tab {{
  background: {tile}; border: 1px solid {border}; border-radius: 10px; margin: 0 3px 6px 0; padding: 6px 12px;
  color: {fg};
}}
window.pw-{key} notebook > header tab:checked {{ background: linear-gradient(135deg, {a1}, {a2}); color: #ffffff; }}
window.pw-{key} .pw-card {{ background: {panel}; border: 1px solid {border}; border-radius: 14px; }}
window.pw-{key} .pw-pad {{ padding: 10px; }}
window.pw-{key} .draco-dialog-head {{ color: {a2}; font-size: 13pt; }}
window.pw-{key} .draco-field-title {{ color: {dim}; }}
window.pw-{key} progressbar.dm-progress > trough > progress {{ background: linear-gradient(90deg, {a1}, {a2}); }}
window.pw-{key} button {{ background: {tile}; border: 1px solid {border}; border-radius: 10px; color: {fg}; }}
window.pw-{key} button.pw-main {{ background: linear-gradient(135deg, {a1}, {a2}); color: #ffffff; border-color: transparent; }}
window.pw-{key} .draco-segbar {{ border: 1px solid {border}; border-radius: 6px; }}
"""

_provider = None
_current = "classic"


def current_palette():
    """Colours of the active dashboard theme (None for the classic themes)."""
    return MODERN.get(_current)


def theme_names():
    return [(key, t["name"]) for key, t in THEMES.items()] + [(key, t["name"]) for key, t in MODERN.items()]


def _art_url(name):
    return (ART_DIR / name).as_uri()


def progress_css():
    out = []
    for key, pal in PROGRESS_STYLES.items():
        out.append(PROGRESS_TEMPLATE.format(key=key, bg_url=_art_url(pal["bg"]), **pal))
    return "".join(out)


def css_for(key):
    if key in MODERN:
        vals = dict(MODERN[key])
        vals["bg_url"] = _art_url(vals["bg"])
        vals["progress_css"] = progress_css()
        return MODERN_TEMPLATE.format(**vals)
    t = THEMES.get(key)
    if not t or key == "system":
        return ""
    vals = dict(t)
    vals["font_rule"] = f"font-family: {t['font']};" if t.get("font") else ""
    vals["list_font_rule"] = f"font-size: {t['list_font']};" if t.get("list_font") else ""
    return TEMPLATE.format(**vals)


def apply_theme(key):
    """Switch the whole app to a theme (works while running)."""
    global _provider, _current
    _current = key
    display = Gdk.Display.get_default()
    t = MODERN.get(key) or THEMES.get(key) or THEMES["classic"]
    sm = Adw.StyleManager.get_default()
    if key == "system":
        sm.set_color_scheme(Adw.ColorScheme.DEFAULT)
    else:
        sm.set_color_scheme(Adw.ColorScheme.FORCE_DARK if t.get("dark") else Adw.ColorScheme.FORCE_LIGHT)
    if _provider is None:
        _provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, _provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _provider.load_from_string(css_for(key if key in THEMES or key in MODERN else "classic"))


def setup(theme="classic"):
    display = Gdk.Display.get_default()
    Gtk.IconTheme.get_for_display(display).add_search_path(str(ICON_DIR))
    Gtk.Window.set_default_icon_name("io.github.draco.DracoDM")
    apply_theme(theme)
