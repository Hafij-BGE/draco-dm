"""Preferences."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402


def _spin(title, lo, hi, step, value, subtitle=""):
    r = Adw.SpinRow.new_with_range(lo, hi, step)
    r.set_title(title)
    if subtitle:
        r.set_subtitle(subtitle)
    r.set_value(value)
    return r


class PrefsDialog(Adw.PreferencesDialog):
    def __init__(self, app):
        super().__init__(title="Preferences", search_enabled=True)
        self.app = app
        s = app.settings
        self.rows = {}

        # ---------------- General
        p = Adw.PreferencesPage(title="General", icon_name="emblem-system-symbolic")
        g = Adw.PreferencesGroup(title="Capturing")
        self._switch(g, "clipboard_monitor", "Watch the clipboard for download links")
        self._switch(g, "start_immediately", "Start downloads without showing the file info dialog")
        self._entry(g, "capture_exts", "File types caught from the clipboard (browser: set in the extension)")
        from . import style
        self.theme_keys = [k for k, _ in style.theme_names()]
        self.theme_row = Adw.ComboRow(title="Theme", subtitle="Also under View → Theme",
                                      model=Gtk.StringList.new([n for _, n in style.theme_names()]))
        cur = s.get("theme") or "classic"
        self.theme_row.set_selected(self.theme_keys.index(cur) if cur in self.theme_keys else 0)
        self.theme_row.connect("notify::selected",
                               lambda r, _p: app.set_theme(self.theme_keys[r.get_selected()]))
        g.add(self.theme_row)
        from .. import native
        self.autostart = Adw.SwitchRow(title="Start Draco hidden at login",
                                       subtitle="Needed for snap/flatpak browsers and scheduled queues",
                                       active=native.autostart_enabled())
        g.add(self.autostart)
        p.add(g)
        g = Adw.PreferencesGroup(title="Dialogs and notifications")
        self._switch(g, "show_progress_dialog", "Show the progress window when a download starts")
        self._switch(g, "show_complete_dialog", "Show the download complete dialog")
        self._switch(g, "notify", "Desktop notification when a download finishes")
        self._switch(g, "sound", "Play a sound when a download finishes")
        p.add(g)
        self.add(p)

        # ---------------- Connection
        p = Adw.PreferencesPage(title="Connection", icon_name="network-transmit-receive-symbolic")
        g = Adw.PreferencesGroup(title="Speed")
        self.rows["connections"] = _spin("Connections per download", 1, 32, 1, s["connections"],
                                         "More connections = faster on most servers")
        self.rows["max_active"] = _spin("Downloads at once in the main queue", 1, 20, 1, s["queues"][0].get("max_active", 3))
        self.rows["speed_limit_kbps"] = _spin("Global speed limit (KB/s, 0 = off)", 0, 1024 * 1024, 64, s["speed_limit_kbps"])
        self.rows["min_split_kb"] = _spin("Smallest piece to split (KB)", 64, 65536, 64, s["min_split_kb"])
        for k in ("connections", "max_active", "speed_limit_kbps", "min_split_kb"):
            g.add(self.rows[k])
        p.add(g)
        g = Adw.PreferencesGroup(title="Network")
        self.rows["retries"] = _spin("Retries per connection", 0, 100, 1, s["retries"])
        self.rows["timeout"] = _spin("Timeout (seconds)", 5, 300, 5, s["timeout"])
        g.add(self.rows["retries"])
        g.add(self.rows["timeout"])
        self._entry(g, "proxy", "Proxy (http://host:port, empty = system/none)")
        self._entry(g, "user_agent", "User agent")
        p.add(g)
        self.add(p)

        # ---------------- Save to
        p = Adw.PreferencesPage(title="Save To", icon_name="folder-download-symbolic")
        g = Adw.PreferencesGroup(title="Folders",
                                 description=f"Empty = your Downloads folder ({s.base_dir()})")
        self._entry(g, "download_dir", "Main download folder")
        self._switch(g, "use_category_folders", "Sort into a sub-folder per category")
        self.dup = Adw.ComboRow(title="If the file already exists",
                                model=Gtk.StringList.new(["Add a number to the name", "Overwrite"]))
        self.dup.set_selected(1 if s["duplicate_action"] == "overwrite" else 0)
        g.add(self.dup)
        p.add(g)
        g = Adw.PreferencesGroup(title="Categories", description="Extensions are separated by spaces")
        self.cat_rows = []
        for cat in s["categories"]:
            exp = Adw.ExpanderRow(title=cat["name"])
            ext = Adw.EntryRow(title="Extensions", text=cat["exts"])
            fol = Adw.EntryRow(title="Folder (empty = default)", text=cat.get("folder", ""))
            exp.add_row(ext)
            exp.add_row(fol)
            g.add(exp)
            self.cat_rows.append((cat, ext, fol))
        p.add(g)
        self.add(p)

        # ---------------- Sites / security
        p = Adw.PreferencesPage(title="Sites", icon_name="dialog-password-symbolic")
        g = Adw.PreferencesGroup(title="Site logins",
                                 description="Sent as HTTP Basic auth to addresses containing the pattern. "
                                             "Stored unencrypted in ~/.config/draco/settings.json (mode 600).")
        self.login_box = g
        self.login_rows = []
        for entry in s["site_logins"]:
            self._login_row(entry)
        add = Gtk.Button(label="Add login", halign=Gtk.Align.START)
        add.connect("clicked", lambda *_: self._login_row({}))
        g.set_header_suffix(add)
        p.add(g)
        g = Adw.PreferencesGroup(title="After download")
        self._entry(g, "antivirus_cmd", "Virus scan command, {file} = path (e.g. clamscan --no-summary {file})")
        p.add(g)
        self.add(p)

        self.connect("closed", lambda *_: self._save())

    def _switch(self, group, key, title):
        r = Adw.SwitchRow(title=title, active=bool(self.app.settings[key]))
        self.rows[key] = r
        group.add(r)

    def _entry(self, group, key, title):
        r = Adw.EntryRow(title=title, text=str(self.app.settings[key] or ""))
        self.rows[key] = r
        group.add(r)

    def _login_row(self, entry):
        exp = Adw.ExpanderRow(title=entry.get("pattern") or "New login", expanded=not entry)
        pat = Adw.EntryRow(title="Address contains", text=entry.get("pattern", ""))
        user = Adw.EntryRow(title="User", text=entry.get("user", ""))
        pw = Adw.PasswordEntryRow(title="Password", text=entry.get("password", ""))
        for r in (pat, user, pw):
            exp.add_row(r)
        self.login_box.add(exp)
        self.login_rows.append((pat, user, pw))

    def _save(self):
        s = self.app.settings
        for key, row in self.rows.items():
            if isinstance(row, Adw.SwitchRow):
                s[key] = row.get_active()
            elif isinstance(row, Adw.SpinRow):
                s[key] = int(row.get_value())
            elif isinstance(row, Adw.EntryRow):
                s[key] = row.get_text().strip()
        s["queues"][0]["max_active"] = int(self.rows["max_active"].get_value())
        s["duplicate_action"] = "overwrite" if self.dup.get_selected() == 1 else "rename"
        for cat, ext, fol in self.cat_rows:
            cat["exts"] = " ".join(ext.get_text().lower().replace(",", " ").split())
            cat["folder"] = fol.get_text().strip()
        s["site_logins"] = [{"pattern": p.get_text().strip(), "user": u.get_text(), "password": w.get_text()}
                            for p, u, w in self.login_rows if p.get_text().strip()]
        s.save()
        from .. import native
        from ..__main__ import _launch_cmd
        if self.autostart.get_active() != native.autostart_enabled():
            native.set_autostart(self.autostart.get_active(), _launch_cmd())
        self.app.manager.global_limiter.set_rate(s["speed_limit_kbps"] * 1024)
        self.app.manager.pump_queues()
        if self.app.window:
            self.app.window.limit_toggle.set_active(bool(s["speed_limit_kbps"]))
            if s["speed_limit_kbps"]:
                self.app.window.limit_spin.set_value(s["speed_limit_kbps"])
