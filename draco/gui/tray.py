"""Top-bar tray icon (StatusNotifierItem over D-Bus) so a hidden Draco is easy to find and quit.

GTK 4 has no tray API. Desktops show these icons natively (KDE, Cinnamon, XFCE, Budgie) or
through the AppIndicator extension (Ubuntu's GNOME). Without a StatusNotifierWatcher on the
bus nothing is shown, and the icon appears by itself once one starts.
"""

import os
from pathlib import Path

from gi.repository import Gio, GLib

from .. import APP_ID, APP_NAME

WATCHER = "org.kde.StatusNotifierWatcher"
ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
ICON_FILE = Path(__file__).resolve().parent.parent / "icons" / f"{APP_ID}.png"

XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="Activate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="SecondaryActivate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="ContextMenu"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="Scroll"><arg name="delta" type="i" direction="in"/><arg name="orientation" type="s" direction="in"/></method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus"><arg name="status" type="s"/></signal>
  </interface>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/><arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/><arg type="(ia{sv}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/><arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{sv})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/><arg type="s" name="name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/><arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/><arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" name="events" direction="in"/><arg type="ai" name="idErrors" direction="out"/>
    </method>
    <method name="AboutToShow"><arg type="i" name="id" direction="in"/><arg type="b" name="needUpdate" direction="out"/></method>
    <method name="AboutToShowGroup">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="ai" name="updatesNeeded" direction="out"/><arg type="ai" name="idErrors" direction="out"/>
    </method>
    <signal name="LayoutUpdated"><arg type="u" name="revision"/><arg type="i" name="parent"/></signal>
    <signal name="ItemsPropertiesUpdated">
      <arg type="a(ia{sv})" name="updatedProps"/><arg type="a(ias)" name="removedProps"/>
    </signal>
  </interface>
</node>
"""


def _pixmaps():
    """The app icon as ARGB32 (network byte order) for trays that can't find it by name."""
    try:
        from gi.repository import GdkPixbuf
        out = []
        for size in (22, 32, 48):
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(str(ICON_FILE), size, size)
            if not pb.get_has_alpha():
                pb = pb.add_alpha(False, 0, 0, 0)
            w, h, stride, px = pb.get_width(), pb.get_height(), pb.get_rowstride(), pb.get_pixels()
            argb = bytearray()
            for y in range(h):
                row = px[y * stride: y * stride + w * 4]
                for x in range(0, w * 4, 4):
                    r, g, b, a = row[x:x + 4]
                    argb += bytes((a, r, g, b))
            out.append((w, h, bytes(argb)))
        return out
    except Exception:  # noqa: BLE001 - the icon name still works on most trays
        return []


class Tray:
    """Click: show Draco. Menu: Show Draco, Add URL…, Quit Draco."""

    def __init__(self, app):
        self.app = app
        self.bus = None
        self.owner_id = 0
        self.watch_id = 0
        self.reg_ids = []
        self.name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self.revision = 1
        self.tooltip = APP_NAME
        self.pixmaps = None
        self.items = [  # id, label, callback (None = separator)
            (1, "Show Draco", app.show_main),
            (2, "Add URL…", lambda: (app.show_main(), app.show_add_url())),
            (3, None, None),
            (4, "Quit Draco", app._quit),
        ]
        self.node = Gio.DBusNodeInfo.new_for_xml(XML)

    # ------------------------------------------------------------ lifecycle
    def start(self):
        if self.owner_id:
            return
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        for iface, path in ((self.node.interfaces[0], ITEM_PATH), (self.node.interfaces[1], MENU_PATH)):
            self.reg_ids.append(self.bus.register_object(path, iface, self._call, self._get, None))
        self.owner_id = Gio.bus_own_name_on_connection(self.bus, self.name, Gio.BusNameOwnerFlags.NONE,
                                                       None, None)
        # (re)register whenever a tray host appears, e.g. after GNOME Shell restarts
        self.watch_id = Gio.bus_watch_name_on_connection(self.bus, WATCHER, Gio.BusNameWatcherFlags.NONE,
                                                         self._register, None)

    def stop(self):
        if not self.bus:
            return
        if self.watch_id:
            Gio.bus_unwatch_name(self.watch_id)
        if self.owner_id:
            Gio.bus_unown_name(self.owner_id)
        for rid in self.reg_ids:
            self.bus.unregister_object(rid)
        self.watch_id = self.owner_id = 0
        self.reg_ids = []

    def _register(self, bus, *_):
        bus.call(WATCHER, "/StatusNotifierWatcher", WATCHER, "RegisterStatusNotifierItem",
                 GLib.Variant("(s)", (self.name,)), None, Gio.DBusCallFlags.NONE, -1, None, None)

    def set_tooltip(self, text):
        if text != self.tooltip and self.bus:
            self.tooltip = text
            self.bus.emit_signal(None, ITEM_PATH, "org.kde.StatusNotifierItem", "NewToolTip", None)

    # ------------------------------------------------------------ D-Bus
    def _get(self, conn, sender, path, iface, prop):
        if iface == "com.canonical.dbusmenu":
            return {"Version": GLib.Variant("u", 3), "TextDirection": GLib.Variant("s", "ltr"),
                    "Status": GLib.Variant("s", "normal"),
                    "IconThemePath": GLib.Variant("as", [])}.get(prop)
        if prop == "IconPixmap":
            if self.pixmaps is None:
                self.pixmaps = _pixmaps()
            return GLib.Variant("a(iiay)", self.pixmaps)
        if prop == "ToolTip":
            return GLib.Variant("(sa(iiay)ss)", (APP_ID, [], APP_NAME, self.tooltip))
        return {"Category": GLib.Variant("s", "ApplicationStatus"), "Id": GLib.Variant("s", "draco"),
                "Title": GLib.Variant("s", APP_NAME), "Status": GLib.Variant("s", "Active"),
                "IconName": GLib.Variant("s", APP_ID), "IconThemePath": GLib.Variant("s", ""),
                "ItemIsMenu": GLib.Variant("b", False),
                "Menu": GLib.Variant("o", MENU_PATH)}.get(prop)

    def _props(self, item_id):
        for i, label, _cb in self.items:
            if i == item_id:
                if label is None:
                    return {"type": GLib.Variant("s", "separator")}
                return {"label": GLib.Variant("s", label), "enabled": GLib.Variant("b", True),
                        "visible": GLib.Variant("b", True)}
        if item_id == 0:
            return {"children-display": GLib.Variant("s", "submenu")}
        return {}

    def _layout(self):
        children = [GLib.Variant("(ia{sv}av)", (i, self._props(i), [])) for i, _l, _c in self.items]
        return (0, self._props(0), children)

    def _run(self, item_id):
        for i, _label, cb in self.items:
            if i == item_id and cb:
                GLib.idle_add(lambda: (cb(), False)[1])

    def _call(self, conn, sender, path, iface, method, params, inv):
        if method in ("Activate", "SecondaryActivate"):
            GLib.idle_add(lambda: (self.app.show_main(), False)[1])
            inv.return_value(None)
        elif method in ("ContextMenu", "Scroll"):
            inv.return_value(None)
        elif method == "GetLayout":
            inv.return_value(GLib.Variant("(u(ia{sv}av))", (self.revision, self._layout())))
        elif method == "GetGroupProperties":
            ids = params.unpack()[0] or [i for i, _l, _c in self.items]
            inv.return_value(GLib.Variant("(a(ia{sv}))", ([(i, self._props(i)) for i in ids],)))
        elif method == "GetProperty":
            item_id, name = params.unpack()
            value = self._props(item_id).get(name, GLib.Variant("s", ""))
            inv.return_value(GLib.Variant("(v)", (value,)))
        elif method == "Event":
            item_id, event = params.unpack()[:2]
            if event == "clicked":
                self._run(item_id)
            inv.return_value(None)
        elif method == "EventGroup":
            for item_id, event, _d, _t in params.unpack()[0]:
                if event == "clicked":
                    self._run(item_id)
            inv.return_value(GLib.Variant("(ai)", ([],)))
        elif method == "AboutToShow":
            inv.return_value(GLib.Variant("(b)", (False,)))
        elif method == "AboutToShowGroup":
            inv.return_value(GLib.Variant("(aiai)", ([], [])))
        else:
            inv.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)
