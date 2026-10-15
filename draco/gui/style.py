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

# ---------------------------------------------------------------- icon styles
ICON_STYLES = [("auto", "Match theme"), ("color", "Colourful"), ("flat", "Flat"),
               ("mono", "Monochrome"), ("accent", "Accent colour")]
# Which icon style each theme uses when the choice is "Match theme".
THEME_ICONS = {"system": "mono", "classic": "color", "retro": "color", "soft-light": "flat", "galaxy": "accent",
               "dark": "mono", "midnight": "accent", "nightshade": "accent", "arctic": "accent",
               "sand": "flat", "deep-teal": "accent", "forest": "flat", "sunset": "flat",
               "high-contrast": "mono"}
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

_provider = None


def theme_names():
    return [(key, t["name"]) for key, t in THEMES.items()]


def css_for(key):
    t = THEMES.get(key)
    if not t or key == "system":
        return ""
    vals = dict(t)
    vals["font_rule"] = f"font-family: {t['font']};" if t.get("font") else ""
    vals["list_font_rule"] = f"font-size: {t['list_font']};" if t.get("list_font") else ""
    return TEMPLATE.format(**vals)


def apply_theme(key):
    """Switch the whole app to a theme (works while running)."""
    global _provider
    display = Gdk.Display.get_default()
    t = THEMES.get(key) or THEMES["classic"]
    sm = Adw.StyleManager.get_default()
    if key == "system":
        sm.set_color_scheme(Adw.ColorScheme.DEFAULT)
    else:
        sm.set_color_scheme(Adw.ColorScheme.FORCE_DARK if t.get("dark") else Adw.ColorScheme.FORCE_LIGHT)
    if _provider is None:
        _provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, _provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _provider.load_from_string(css_for(key if key in THEMES else "classic"))


def setup(theme="classic"):
    display = Gdk.Display.get_default()
    Gtk.IconTheme.get_for_display(display).add_search_path(str(ICON_DIR))
    Gtk.Window.set_default_icon_name("io.github.draco.DracoDM")
    apply_theme(theme)
