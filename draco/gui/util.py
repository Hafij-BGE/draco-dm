"""Formatting and desktop helpers shared by the GUI."""

import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

STATUS_TEXT = {
    "stopped": "Stopped", "queued": "Queued", "connecting": "Connecting…",
    "downloading": "Downloading", "merging": "Merging…", "paused": "Paused",
    "error": "Error", "complete": "Complete",
}

CATEGORY_ICONS = {
    "General": "folder-download-symbolic",
}


def fmt_size(n):
    if n is None or n < 0:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024


def fmt_speed(bps):
    if not bps or bps <= 0:
        return ""
    return fmt_size(bps) + "/s"


def fmt_eta(seconds):
    if seconds is None or seconds < 0 or seconds == float("inf"):
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def fmt_time(ts):
    if not ts:
        return ""
    d = datetime.fromtimestamp(ts)
    if d.date() == datetime.now().date():
        return d.strftime("%H:%M")
    return d.strftime("%b %d %Y")


def fraction(item):
    if item.get("status") == "complete":
        return 1.0
    if item.get("fraction"):
        return item["fraction"]
    if item.get("seg_total"):
        return item.get("seg_done", 0) / item["seg_total"]
    size = item.get("size", -1)
    if size and size > 0:
        return min(1.0, item.get("downloaded", 0) / size)
    return 0.0


def eta(item):
    size, done, speed = item.get("size", -1), item.get("downloaded", 0), item.get("speed", 0)
    if item.get("status") != "downloading" or not speed or size is None or size <= 0:
        return None
    return (size - done) / speed


def status_text(item):
    st = item.get("status", "stopped")
    if st == "downloading":
        f = fraction(item)
        return f"{f * 100:.1f}%" if (item.get("size", -1) > 0 or item.get("seg_total")) else fmt_size(item.get("downloaded", 0))
    if st == "error":
        return "Error: " + (item.get("error") or "")
    if st == "paused" and item.get("downloaded"):
        return f"Paused {fraction(item) * 100:.1f}%"
    return STATUS_TEXT.get(st, st)


def file_path(item):
    return Path(item["save_dir"]) / item["filename"]


def open_path(path):
    from ..osdeps import open_file
    open_file(path)


def open_folder(path):
    """Open the containing folder with the file selected when the file manager supports it."""
    from ..osdeps import reveal
    reveal(path)


def play_complete_sound():
    from ..osdeps import play_complete_sound as play
    play()


def looks_like_url(text):
    text = (text or "").strip()
    return text.startswith(("http://", "https://", "ftp://")) and " " not in text and "\n" not in text


def icon_for_file(filename):
    ctype, _ = Gio.content_type_guess(filename, None)
    icon = Gio.content_type_get_icon(ctype)
    return icon


def label(text="", xalign=0, css=None, wrap=False, selectable=False, ellipsize=True):
    from gi.repository import Pango
    lb = Gtk.Label(label=text, xalign=xalign)
    if ellipsize and not wrap:
        lb.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
    if wrap:
        lb.set_wrap(True)
        lb.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    lb.set_selectable(selectable)
    for c in (css or []):
        lb.add_css_class(c)
    return lb


def now():
    return time.time()
