"""Paths, persistent settings and file categories."""

import json
import os
import threading
from pathlib import Path


from . import osdeps

CONFIG_DIR = osdeps.config_dir()     # Linux: ~/.config/draco      Windows: %APPDATA%\Draco
DATA_DIR = osdeps.data_dir()         # Linux: ~/.local/share/draco Windows: %LOCALAPPDATA%\Draco
RUNTIME_DIR = osdeps.runtime_dir()
SOCKET_PATH = RUNTIME_DIR / "draco.sock"


def _migrate_old_names():
    """The app was earlier called Spectra and Hawk: carry over settings and download list once.

    Copies file by file, because the installer creates the new data folder (for the app
    itself) before the first start.
    """
    import shutil
    for new in (CONFIG_DIR, DATA_DIR):
        for old_name in ("spectra", "hawkdm"):
            old = new.parent / old_name
            if not old.is_dir():
                continue
            for item in old.iterdir():
                if item.name in ("app", "extension") or item.suffix == ".py":
                    continue
                target = new / item.name
                if target.exists():
                    continue
                try:
                    new.mkdir(parents=True, exist_ok=True)
                    if item.is_dir():
                        shutil.copytree(item, target)
                    else:
                        shutil.copy2(item, target)
                except OSError:
                    pass


if not osdeps.IS_WIN:
    _migrate_old_names()
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DOWNLOADS_FILE = DATA_DIR / "downloads.json"
STATE_DIR = DATA_DIR / "state"


def downloads_root():
    return osdeps.downloads_dir()


# Default categories mirror the usual "sort by file type" layout.
DEFAULT_CATEGORIES = [
    {"name": "Compressed", "icon": "package-x-generic-symbolic",
     "exts": "zip rar 7z gz bz2 xz tar tgz zst iso arj lzh sit sitx z ace deb rpm apk appimage flatpak snap"},
    {"name": "Documents", "icon": "x-office-document-symbolic",
     "exts": "pdf doc docx xls xlsx ppt pptx odt ods odp txt rtf epub mobi djvu csv md tex"},
    {"name": "Music", "icon": "audio-x-generic-symbolic",
     "exts": "mp3 flac wav ogg oga opus m4a aac wma ape aif aiff mid midi"},
    {"name": "Programs", "icon": "application-x-executable-symbolic",
     "exts": "exe msi bin run sh jar dmg pkg"},
    {"name": "Video", "icon": "video-x-generic-symbolic",
     "exts": "mp4 mkv avi mov wmv flv webm m4v mpg mpeg 3gp ts m2ts ogv vob rm rmvb"},
]

DEFAULT_SETTINGS = {
    "connections": 8,                # parallel connections per download
    "max_active": 3,                 # downloads running at once in the main queue
    "speed_limit_kbps": 0,           # 0 = unlimited (global)
    "per_download_limit_kbps": 0,
    "retries": 10,
    "timeout": 30,
    "min_split_kb": 512,             # dynamic segmentation won't split below this
    "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "proxy": "",                     # e.g. http://127.0.0.1:8080 or socks unsupported
    "download_dir": "",              # empty = XDG download dir
    "fixed_folder": "",              # set = every download goes here (no category folders) until reset
    "use_category_folders": True,
    "temp_suffix": ".dracopart",
    "show_progress_dialog": True,
    "progress_view": "app",            # dashboard themes: "app" = details pane in the main window, "window"
    "details_pane": True,
    "sidebar_collapsed": False,
    "progress_styles": {},             # category -> progress look (see style.PROGRESS_STYLES); missing = auto
    "ask_location_for_captures": True,   # files caught from the browser always show the File Info dialog
    "tray_icon": True,               # Draco icon in the top bar/system tray (show, quit)
    "background_on_close": True,     # closing the window keeps Draco running hidden (no taskbar entry)
    "show_complete_dialog": True,
    "start_immediately": False,      # skip the "file info" dialog for new downloads
    "clipboard_monitor": True,
    "notify": True,
    "theme": "classic",              # see draco/gui/style.py THEMES (View > Theme)
    "icon_style": "auto",            # auto (match theme) | color | flat | mono | accent
    "show_categories": True,
    "show_toolbar": True,
    "sound": True,
    "duplicate_action": "rename",    # rename | overwrite | ask
    "antivirus_cmd": "",             # e.g. clamscan --no-summary "{file}"
    "capture_exts": ("3gp 7z aac ace aif apk arj asf avi bin bz2 deb dmg exe flac flv gz gzip iso jar "
                     "lzh m4a m4v mkv mov mp3 mp4 mpeg mpg msi ogg ogv opus pdf pkg rar rpm sit sitx "
                     "tar tgz wav webm wma wmv xz z zip zst appimage epub"),
    "capture_min_kb": 0,
    "site_logins": [],
    "bridge_tokens": [],             # paired browser extensions (loopback bridge for snap browsers)               # [{"pattern": "example.com", "user": "", "password": ""}]
    "categories": DEFAULT_CATEGORIES,
    "queues": [
        {"name": "Main queue", "max_active": 3, "schedule": {
            "enabled": False, "start": "02:00", "stop": "", "days": [0, 1, 2, 3, 4, 5, 6],
            "once": False, "after": "none", "retry_failed": True}},
        {"name": "Synchronization queue", "max_active": 1, "schedule": {
            "enabled": False, "start": "", "stop": "", "days": [0, 1, 2, 3, 4, 5, 6],
            "once": False, "after": "none", "retry_failed": False}},
    ],
}


class Settings:
    """Thread-safe JSON settings with defaults."""

    def __init__(self, path=SETTINGS_FILE):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.data = json.loads(json.dumps(DEFAULT_SETTINGS))
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text()))
            except (OSError, ValueError):
                pass

    def __getitem__(self, key):
        with self._lock:
            return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def __setitem__(self, key, value):
        with self._lock:
            self.data[key] = value

    def get(self, key, default=None):
        with self._lock:
            return self.data.get(key, default)

    def save(self):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # may hold site logins
            with os.fdopen(fd, "w") as fh:
                fh.write(json.dumps(self.data, indent=2))
            os.replace(tmp, self.path)

    # --- helpers -------------------------------------------------------
    def base_dir(self):
        d = self["download_dir"]
        return Path(d).expanduser() if d else downloads_root()

    def category_for(self, filename):
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        for cat in self["categories"]:
            if ext and ext in cat["exts"].split():
                return cat["name"]
        return "General"

    def folder_for(self, category):
        if self.get("fixed_folder"):
            return Path(self["fixed_folder"]).expanduser()
        base = self.base_dir()
        if not self["use_category_folders"] or category == "General":
            return base
        for cat in self["categories"]:
            if cat["name"] == category and cat.get("folder"):
                return Path(cat["folder"]).expanduser()
        return base / category

    def login_for(self, url):
        for entry in self["site_logins"]:
            if entry.get("pattern") and entry["pattern"] in url:
                return entry.get("user", ""), entry.get("password", "")
        return None
