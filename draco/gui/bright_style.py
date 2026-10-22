"""Colours and stylesheet of the picture themes (Cosmic Sky, Sunrise, Galaxy Explorer Dark, …), plus
the per-file-kind looks of their standalone progress windows."""

from pathlib import Path

ART_DIR = Path(__file__).resolve().parent.parent / "art"


def _theme(**kw):
    base = dict(
        dark=False, bg="hd-cosmic-sky.jpg", base="#eef3fc", fg="#16213e", dim="#6b7894",
        card="rgba(255,255,255,0.84)", card_solid="#ffffff", border="rgba(190,205,235,0.70)",
        accent="#2f74f5", a1="#2563eb", a2="#3b9cff", accent_soft="#e4eeff", accent_line="#bcd3ff",
        p1="#3b82f6", p2="#60a5fa", hi1="#10b981", hi2="#34d399", trough="#e6edf9",
        ok="#16a34a", err="#ef4444", cancel_bg="#ffe6e9", tile="#ffffff", tile_border="rgba(205,215,240,0.9)",
        ring_track="#e3e9f7", graph1="#2563eb", graph2="#93c5fd",
        surface="#ffffff", sq_bg="rgba(255,255,255,0.85)", tile_bg="rgba(255,255,255,0.90)",
        shadow="rgba(60,80,140,0.08)", glow3="0 0 6px #ffffff, 0 0 12px #ffffff, 0 0 18px rgba(255,255,255,0.9)",
    )
    base.update(kw)
    return base


def _light(accent, a2, soft, line, base, art, p2=None, hi=("#10b981", "#34d399"), name=""):
    """A light theme from its accent colour and header picture."""
    return {"name": name, **_theme(
        bg=art, base=base, accent=accent, a1=accent, a2=a2, accent_soft=soft, accent_line=line,
        p1=accent, p2=p2 or a2, hi1=hi[0], hi2=hi[1], trough=soft, graph1=accent, graph2=a2,
        ring_track=soft)}


def _dark(accent, a2, base, art, hi=("#22d3ee", "#67e8f9"), name=""):
    """A dark theme from its accent colour and header picture."""
    return {"name": name, **_theme(
        dark=True, bg=art, base=base, fg="#e8ecfb", dim="#9aa4c4", accent=accent, a1=accent, a2=a2,
        accent_soft="rgba(255,255,255,0.08)", accent_line="rgba(255,255,255,0.18)",
        card="rgba(14,18,40,0.82)", card_solid="#12162c", border="rgba(150,160,230,0.20)",
        p1=accent, p2=a2, hi1=hi[0], hi2=hi[1], trough="rgba(255,255,255,0.08)", ok="#34d399",
        err="#f87171", cancel_bg="rgba(248,113,113,0.16)", tile="#1a1f3d", tile_border="rgba(160,170,240,0.22)",
        ring_track="rgba(255,255,255,0.10)", graph1=accent, graph2=a2, surface="#1a1f3d",
        sq_bg="rgba(26,31,61,0.85)", tile_bg="rgba(22,27,56,0.88)", shadow="rgba(0,0,0,0.35)",
        glow3="0 0 6px rgba(0,0,0,0.85), 0 0 12px rgba(0,0,0,0.6)")}


BRIGHT = {
    # header pictures cut from the theme concept images (tools/make_theme_art.py)
    "cosmic-sky": _light("#2563eb", "#3b9cff", "#e4eeff", "#bcd3ff", "#eef3fc", "hd-cosmic-sky.jpg", name="Cosmic Sky (Light)"),
    "starlight-forest": _light("#16a34a", "#22c55e", "#e2f5e7", "#bfe6c9", "#eff7f0", "hd-starlight-forest.jpg",
                               hi=("#0d9488", "#2dd4bf"), name="Starlight Forest (Light)"),
    "aurora": _light("#c026d3", "#e879f9", "#fbe8ff", "#f0c4f7", "#fbf1fd", "hd-aurora.jpg", name="Aurora (Light)"),
    "sunrise": _light("#ea580c", "#fb923c", "#ffedd5", "#fed7aa", "#fff6ee", "hd-sunrise.jpg",
                      hi=("#f59e0b", "#fcd34d"), name="Sunrise (Light)"),
    "ocean": _light("#0284c7", "#38bdf8", "#e0f2fe", "#bae6fd", "#eef8fd", "hd-ocean.jpg", name="Ocean (Light)"),
    "minimal": _light("#2563eb", "#60a5fa", "#e8efff", "#c7d7fb", "#f4f6fa", "hd-minimal.jpg", name="Minimal (Light)"),
    "lavender": _light("#7c3aed", "#a78bfa", "#ede9fe", "#ddd6fe", "#f6f3fe", "hd-lavender.jpg", name="Lavender (Light)"),
    "sandstone": _light("#c2410c", "#f59e0b", "#fdf1dc", "#f5dcae", "#fbf6ec", "hd-sandstone.jpg",
                        hi=("#d97706", "#fbbf24"), name="Sandstone (Light)"),
    "monochrome": _light("#334155", "#64748b", "#e8ecf1", "#cbd3dd", "#f3f5f8", "hd-monochrome.jpg",
                         hi=("#475569", "#94a3b8"), name="Monochrome (Light)"),
    "sunset-nebula": _light("#c026d3", "#ec4899", "#fce7f6", "#f5c2e6", "#fdf2f8", "hd-sunset-nebula.jpg",
                            hi=("#8b5cf6", "#c4b5fd"), name="Sunset Nebula (Light)"),
    # the former dashboard themes, now in this layout
    "galaxy-explorer": _dark("#5b7bff", "#1fb8ff", "#070a22", "hd-galaxy-explorer.jpg", name="Galaxy Explorer"),
    "aurora-light": _light("#6b5cff", "#3c8bff", "#ebe8ff", "#d2ccff", "#eceeff", "hd-aurora-light.jpg",
                           name="Aurora Light"),
    "aurora-glow": _dark("#a855f7", "#c084fc", "#0b0c22", "hd-aurora-glow.jpg", name="Aurora Glow (Dark)"),
    "forest-night": _dark("#10b981", "#34d399", "#07150f", "hd-forest-night.jpg", hi=("#2dd4bf", "#99f6e4"),
                          name="Forest Night (Dark)"),
    "midnight-ocean": _dark("#3b82f6", "#60a5fa", "#06101f", "hd-midnight-ocean.jpg", name="Midnight Ocean (Dark)"),
    "royal-purple": _dark("#9333ea", "#c084fc", "#100822", "hd-royal-purple.jpg", hi=("#e879f9", "#f5d0fe"),
                          name="Royal Purple (Dark)"),
    "solar-eclipse": _dark("#f59e0b", "#fbbf24", "#140b05", "hd-solar-eclipse.jpg", hi=("#fb923c", "#fdba74"),
                           name="Solar Eclipse (Dark)"),
}

# Standalone progress window look per file kind: accent colours and pictures.
KINDS = {
    "archive": dict(title="ZIP Archive", a1="#2563eb", a2="#38bdf8", soft="#e6efff"),
    "video": dict(title="Video", a1="#f97316", a2="#fb923c", soft="#fff0e4"),
    "music": dict(title="Audio", a1="#c026d3", a2="#e879f9", soft="#fbe8ff"),
    "document": dict(title="Document", a1="#16a34a", a2="#4ade80", soft="#e6f8ec"),
    "program": dict(title="Application", a1="#6d28d9", a2="#8b5cf6", soft="#efe8ff"),
    "disc": dict(title="Disc Image", a1="#d97706", a2="#fbbf24", soft="#fff5dc"),
    "image": dict(title="Images", a1="#0891b2", a2="#22d3ee", soft="#e2f8fc"),
    "unknown": dict(title="File", a1="#475569", a2="#94a3b8", soft="#eef1f5"),
    "live": dict(title="Live Stream", a1="#dc2626", a2="#f43f5e", soft="#ffe8ea"),
}
EXT_KIND = {}
for kind, exts in {
    "archive": "zip rar 7z tar gz tgz bz2 xz zst",
    "video": "mp4 mkv webm avi mov m4v flv wmv ts",
    "music": "mp3 flac wav ogg m4a aac opus wma",
    "document": "pdf doc docx odt rtf txt md epub xls xlsx ods ppt pptx odp csv",
    "program": "exe msi deb rpm appimage apk dmg pkg flatpak snap sh run",
    "disc": "iso img bin cue nrg",
    "image": "jpg jpeg png gif webp bmp svg tiff heic",
}.items():
    for e in exts.split():
        EXT_KIND[e] = kind
FILE_ICON = {"archive": "archive", "video": "video", "music": "music", "program": "program", "disc": "disc",
             "image": "image", "unknown": "unknown", "live": "live"}


def kind_of(item):
    """File kind of a download (decides colours, illustration and icon)."""
    if item.get("kind") in ("hls", "ffmpeg") or (item.get("url", "").split("?")[0].endswith(".m3u8")):
        return "live"
    name = (item.get("filename") or item.get("url", "")).split("?")[0]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext == "bin":
        return "unknown"
    return EXT_KIND.get(ext) or ("video" if item.get("kind") == "ytdlp" else "unknown")


def file_icon(item_or_name):
    """Coloured document icon for the list, the details pane and the window header."""
    name = item_or_name if isinstance(item_or_name, str) else (item_or_name.get("filename") or item_or_name.get("url", ""))
    ext = name.split("?")[0].rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext == "pdf":
        return "draco-f-pdf"
    if ext in ("xls", "xlsx", "ods", "csv"):
        return "draco-f-sheet"
    if ext in ("doc", "docx", "odt", "rtf", "txt", "md", "epub", "ppt", "pptx", "odp"):
        return "draco-f-document"
    kind = kind_of({"filename": name}) if isinstance(item_or_name, str) else kind_of(item_or_name)
    return f"draco-f-{FILE_ICON.get(kind, 'unknown')}"


def _url(name):
    return (ART_DIR / name).as_uri()


TEMPLATE = """
@define-color window_bg_color {base};
@define-color window_fg_color {fg};
@define-color view_bg_color {card_solid};
@define-color view_fg_color {fg};
@define-color headerbar_bg_color {base};
@define-color headerbar_fg_color {fg};
@define-color popover_bg_color {surface};
@define-color popover_fg_color {fg};
@define-color dialog_bg_color {surface};
@define-color dialog_fg_color {fg};
@define-color card_bg_color {surface};
@define-color card_fg_color {fg};
@define-color accent_bg_color {accent};
@define-color accent_fg_color #ffffff;
@define-color accent_color {accent};

window.bw-window {{
  background-color: {base}; background-image: url("{bg_url}");
  background-size: auto 270px; background-position: right top; background-repeat: no-repeat;
  color: {fg};
}}
.bw-root {{ padding: 0 14px 12px 14px; }}
.bw-brand-title {{ font-size: 21pt; font-weight: 800; color: {fg}; text-shadow: {glow3}; }}
.bw-brand-sub {{ font-size: 12.5pt; font-weight: 700; color: {fg}; text-shadow: {glow3}; }}
.bw-brand-tag {{ font-size: 8.5pt; font-weight: 700; color: {a1}; text-shadow: {glow3}; }}
.bw-logo {{ border-radius: 14px; }}
button.bw-sq, menubutton.bw-sq > button {{
  min-width: 34px; min-height: 34px; padding: 0; border-radius: 10px; background: {sq_bg};
  border: 1px solid {tile_border}; color: {fg}; box-shadow: 0 1px 3px rgba(40,60,120,0.08);
}}
button.bw-sq:hover, menubutton.bw-sq > button:hover {{ background: {surface}; }}
button.bw-sq:checked {{ background: {accent_soft}; color: {accent}; border-color: {accent_line}; }}
button.bw-flat, menubutton.bw-flat > button {{ background: none; border: none; box-shadow: none; color: {fg}; min-width: 30px; }}
windowcontrols {{ background: {sq_bg}; border: 1px solid {tile_border}; border-radius: 999px; padding: 3px;
  margin-left: 6px; box-shadow: 0 2px 8px rgba(20,30,70,0.12); }}
windowcontrols button {{ background: none; border: none; box-shadow: none; border-radius: 999px; padding: 0;
  min-width: 28px; min-height: 28px; margin: 0 1px; color: {fg}; transition: background 120ms ease; }}
windowcontrols button image {{ color: {fg}; -gtk-icon-size: 14px; }}
windowcontrols button:hover {{ background: alpha(currentColor, 0.12); }}
windowcontrols button:active {{ background: alpha(currentColor, 0.22); }}
windowcontrols button.close:hover {{ background: #e5484d; }}
windowcontrols button.close:hover image {{ color: #ffffff; }}

button.bw-tile {{
  min-width: 70px; min-height: 62px; padding: 4px 10px; border-radius: 12px; color: {fg};
  background: {tile_bg}; border: 1px solid {tile_border}; box-shadow: 0 2px 8px {shadow};
}}
button.bw-tile label {{ font-size: 9pt; font-weight: 600; }}
button.bw-tile:hover {{ background: {surface}; box-shadow: 0 3px 12px {shadow}; }}
button.bw-tile:disabled {{ opacity: 1; background: {tile_bg}; }}
button.bw-tile:disabled > box {{ opacity: 0.4; }}
button.bw-tile.primary {{
  min-width: 82px; background: linear-gradient(160deg, {a2}, {a1}); color: #ffffff; border-color: transparent;
  box-shadow: 0 4px 14px alpha({a1}, 0.35);
}}
button.bw-tile.primary image {{ color: #ffffff; }}

.bw-card {{ background: {card}; border: 1px solid {border}; border-radius: 14px;
  box-shadow: 0 2px 10px {shadow}; }}

.bw-side list {{ background: none; color: {fg}; }}
.bw-side row {{ padding: 7px 12px 7px 10px; border-radius: 10px; margin: 1px 6px; }}
.bw-side row label {{ font-size: 9.5pt; font-weight: 600; color: {fg}; }}
.bw-side row .bw-count {{ font-weight: 600; color: {fg}; }}
.bw-side row:hover:not(:selected) {{ background: alpha({accent_soft}, 0.6); }}
.bw-side row:selected {{ background: {accent_soft}; box-shadow: inset 3px 0 0 0 {accent}; }}
.bw-side row:selected label {{ color: {accent}; }}
.bw-side-head {{ font-size: 10pt; font-weight: 800; color: {fg}; margin: 12px 14px 2px 14px; }}
.bw-side row.bw-queue {{ padding-top: 3px; padding-bottom: 3px; }}
.bw-side row.bw-queue label {{ font-weight: 500; color: {dim}; }}
.bw-side row.bw-queue .bw-count {{ font-weight: 500; color: {dim}; }}

.bw-tabs button.toggle {{
  border-radius: 10px; padding: 5px 14px; background: none; border: none; color: {fg}; font-weight: 600;
  box-shadow: none;
}}
.bw-tabs button.toggle:checked {{ background: {accent_soft}; color: {accent}; }}
entry.bw-search, .bw-search {{ background: {sq_bg}; border: 1px solid {tile_border};
  border-radius: 10px; min-height: 36px; color: {fg}; }}

columnview.bw-list {{ background: none; color: {fg}; }}
columnview.bw-list > header > button {{
  background: none; border: none; border-bottom: 1px solid {border}; color: {fg}; font-weight: 600;
  padding: 7px 8px; box-shadow: none; font-size: 9pt;
}}
columnview.bw-list > listview {{ background: none; }}
columnview.bw-list > listview > row {{ min-height: 34px; border-radius: 8px; }}
columnview.bw-list > listview > row > cell {{ padding: 2px 8px; font-size: 9pt; }}
columnview.bw-list > listview > row:hover:not(:selected) {{ background: alpha({accent_soft}, 0.55); }}
columnview.bw-list > listview > row:selected {{ background: {accent_soft}; color: {fg}; }}
.bw-index {{ color: {fg}; }}
row:selected .bw-index {{ color: {accent}; font-weight: bold; }}

progressbar.bw-bar {{ min-width: 40px; }}
progressbar.bw-bar > trough {{ background: {trough}; border-radius: 6px; min-height: 18px; min-width: 40px; border: none; }}
progressbar.bw-bar > trough > progress {{
  background: linear-gradient(90deg, {p1}, {p2}); border-radius: 6px; min-height: 18px; border: none; }}
progressbar.bw-bar.hi > trough > progress {{ background: linear-gradient(90deg, {hi1}, {hi2}); }}
progressbar.bw-bar.done > trough > progress {{ background: linear-gradient(90deg, #16a34a, #4ade80); }}
progressbar.bw-bar.failed > trough > progress {{ background: linear-gradient(90deg, {err}, {err}); }}
progressbar.bw-thin > trough, progressbar.bw-thin > trough > progress {{ min-height: 8px; }}
.bw-pct {{ font-size: 8.5pt; color: {fg}; }}

.bw-ptabs {{ border-bottom: 1px solid {border}; }}
.bw-ptabs button.toggle {{ background: none; border: none; border-radius: 10px 10px 0 0; padding: 7px 14px;
  color: {fg}; font-weight: 500; box-shadow: none; font-size: 9.5pt; }}
.bw-ptabs button.toggle:checked {{ background: {surface}; color: {accent}; font-weight: 700;
  box-shadow: inset 0 2px 0 0 {accent}, 1px 0 0 {border}, -1px 0 0 {border}; }}
.bw-detail-name {{ font-size: 12.5pt; font-weight: 800; color: {fg}; }}
.bw-url {{ font-size: 8.5pt; color: {accent}; }}
.bw-ring-num {{ font-size: 17pt; font-weight: 800; color: {fg}; }}
.bw-state {{ font-size: 10.5pt; font-weight: 700; color: {fg}; }}
.bw-small {{ font-size: 8.5pt; color: {fg}; }}
.bw-key {{ font-size: 9pt; color: {dim}; }}
.bw-val {{ font-size: 9pt; color: {fg}; }}
.bw-yes {{ font-size: 9pt; color: {ok}; }}
.bw-speed-val {{ font-size: 9.5pt; font-weight: 800; color: {accent}; }}
button.bw-pause {{ background: linear-gradient(180deg, {a2}, {a1}); color: #ffffff; border-radius: 8px;
  min-height: 36px; font-weight: 600; border: none; }}
button.bw-cancel {{ background: {cancel_bg}; color: {err}; border-radius: 8px; min-height: 36px; font-weight: 600;
  border: none; }}
button.bw-cancel image {{ color: {err}; }}
separator.bw-sep {{ background: {border}; min-height: 1px; }}

.bw-status {{ padding: 8px 14px; }}
.bw-status label {{ font-size: 9.5pt; color: {fg}; }}
.bw-strong {{ font-weight: 800; }}
.bw-badge {{ background: {accent}; color: #ffffff; border-radius: 12px; min-width: 22px; min-height: 22px;
  font-weight: 700; font-size: 8.5pt; }}
.bw-badge-plain {{ background: {accent_soft}; color: {fg}; border-radius: 6px; padding: 1px 7px; font-weight: 800; }}
.bw-vsep {{ background: {border}; min-width: 1px; margin: 4px 4px; }}
switch:checked {{ background: {accent}; }}
dropdown.bw-drop > button, .bw-drop > button {{ background: {surface}; border: 1px solid {tile_border}; border-radius: 9px;
  font-weight: 700; padding: 4px 10px; }}
.draco-dialog-head {{ font-size: 11pt; font-weight: bold; }}
.draco-field-title {{ color: {dim}; }}
.draco-conn-table label {{ font-family: monospace; font-size: 9pt; }}
.draco-conn-table .head {{ font-weight: bold; font-family: sans-serif; }}
button.suggested-action {{ background: linear-gradient(180deg, {a2}, {a1}); color: #ffffff; }}
{kind_css}
"""

KIND_TEMPLATE = """
window.pk-{key} {{
  background-color: #f6f8fc; background-image: url("{bg_url}"); background-size: cover; color: #16213e;
}}
window.pk-{key} .pk-name {{ font-size: 13pt; font-weight: 800; color: #16213e; }}
window.pk-{key} .pk-size {{ font-size: 10pt; color: #2b3654; }}
window.pk-{key} .pk-tabs button.toggle {{ background: rgba(255,255,255,0.75); border: 1px solid rgba(210,218,235,0.9);
  border-radius: 8px 8px 0 0; padding: 5px 18px; color: #16213e; box-shadow: none; margin-right: 3px; }}
window.pk-{key} .pk-tabs button.toggle:checked {{ background: linear-gradient(180deg, {a2}, {a1}); color: #ffffff;
  border-color: transparent; font-weight: 700; }}
window.pk-{key} .pk-card {{ background: rgba(255,255,255,0.82); border: 1px solid rgba(220,226,240,0.9);
  border-radius: 12px; }}
window.pk-{key} .pk-key {{ font-size: 9pt; color: #3b4766; }}
window.pk-{key} .pk-val {{ font-size: 9pt; color: #16213e; }}
window.pk-{key} .pk-yes {{ font-size: 9pt; color: #16a34a; font-weight: 600; }}
window.pk-{key} .pk-speed {{ font-size: 11pt; font-weight: 800; color: {a1}; }}
window.pk-{key} .pk-pct {{ font-size: 12pt; font-weight: 800; color: #16213e; }}
window.pk-{key} .pk-small {{ font-size: 9.5pt; color: #16213e; }}
window.pk-{key} progressbar > trough {{ background: #e5e9f2; border-radius: 7px; min-height: 13px; border: none; }}
window.pk-{key} progressbar > trough > progress {{ background: linear-gradient(90deg, {a1}, {a2});
  border-radius: 7px; min-height: 13px; border: none; }}
window.pk-{key} button.pk-pause {{ background: linear-gradient(180deg, {a2}, {a1}); color: #ffffff; border: none;
  border-radius: 8px; min-height: 38px; min-width: 124px; font-weight: 700; font-size: 11pt; }}
window.pk-{key} button.pk-cancel {{ background: #ffe8ea; color: #e11d48; border: none; border-radius: 8px;
  min-height: 38px; min-width: 116px; font-weight: 600; font-size: 10.5pt; }}
window.pk-{key} button.pk-cancel image {{ color: #e11d48; }}
window.pk-{key} button.pk-sq, window.pk-{key} menubutton.pk-sq > button {{ background: rgba(255,255,255,0.9); border: 1px solid rgba(215,222,238,0.95);
  border-radius: 9px; min-width: 38px; min-height: 38px; color: #2b3654; }}
window.pk-{key} windowcontrols button {{ background: none; border: none; min-width: 28px; min-height: 28px;
  color: #2b3654; margin-left: 4px; }}
window.pk-{key} .pk-log label {{ font-family: monospace; font-size: 9pt; }}
"""


def css_for(key):
    vals = dict(BRIGHT[key])
    vals["bg_url"] = _url(vals["bg"])
    vals["kind_css"] = "".join(KIND_TEMPLATE.format(key=k, bg_url=_url(f"pw2-bg-{k}.png"), **v) for k, v in KINDS.items())
    return TEMPLATE.format(**vals) + SCENE_CSS


# Live planet in the details pane (planet_scene.py): dark text on the light themes' pale sky,
# white text on the dark themes' night sky.
SCENE_CSS = """
.ps-scene { margin: 0 6px 6px 6px; }
.ps-big { font-size: 26px; font-weight: 800; font-feature-settings: "tnum"; }
.ps-small { font-size: 12px; font-weight: 700; }
.ps-dark .ps-big, .ps-dark .ps-small { color: #ffffff; text-shadow: 0 1px 6px rgba(0, 0, 30, 0.85); }
.ps-light .ps-big, .ps-light .ps-small { color: #ffffff; text-shadow: 0 1px 5px rgba(20, 20, 70, 0.75); }
"""
