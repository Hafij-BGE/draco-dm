"""Open the torrent ports on the home router with UPnP (Internet Gateway Device), standard library only.

Without this, peers outside the router can't connect to Draco: it can only reach peers that
accept incoming connections themselves, so many seeds stay out of reach and the ones it does
reach come and go. aria2 has no UPnP of its own.

Everything here is best effort: no router, UPnP off on the router or any error just means
the ports stay closed, exactly as before."""

import re
import socket
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SSDP = ("239.255.255.250", 1900)
SEARCH_TARGETS = ("urn:schemas-upnp-org:device:InternetGatewayDevice:1",
                  "urn:schemas-upnp-org:device:InternetGatewayDevice:2",
                  "urn:schemas-upnp-org:service:WANIPConnection:1")
SERVICES = ("urn:schemas-upnp-org:service:WANIPConnection:2",
            "urn:schemas-upnp-org:service:WANIPConnection:1",
            "urn:schemas-upnp-org:service:WANPPPConnection:1")
LEASE = 3600                 # seconds; renewed well before it runs out
RENEW = 20 * 60
DESCRIPTION = "Draco torrent"

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # the router is local: no proxy


class Gateway:
    def __init__(self, control_url, service, local_ip):
        self.control_url, self.service, self.local_ip = control_url, service, local_ip

    def _soap(self, action, args, timeout=4):
        body = "".join(f"<{k}>{v}</{k}>" for k, v in args)
        envelope = ('<?xml version="1.0"?>'
                    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
                    's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
                    f'<u:{action} xmlns:u="{self.service}">{body}</u:{action}>'
                    '</s:Body></s:Envelope>').encode()
        req = urllib.request.Request(self.control_url, envelope, {
            "Content-Type": 'text/xml; charset="utf-8"', "SOAPAction": f'"{self.service}#{action}"'})
        try:
            with _OPENER.open(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:      # UPnP errors come back as HTTP 500 + <errorCode>
            text = e.read().decode("utf-8", "replace")
            m = re.search(r"<errorCode>(\d+)</errorCode>", text)
            raise UPnPError(int(m.group(1)) if m else e.code, text) from None

    def add(self, port, proto, lease=LEASE):
        args = [("NewRemoteHost", ""), ("NewExternalPort", port), ("NewProtocol", proto),
                ("NewInternalPort", port), ("NewInternalClient", self.local_ip), ("NewEnabled", 1),
                ("NewPortMappingDescription", DESCRIPTION), ("NewLeaseDuration", lease)]
        try:
            self._soap("AddPortMapping", args)
        except UPnPError as e:
            if e.code != 725 or not lease:       # 725 = OnlyPermanentLeasesSupported
                raise
            self.add(port, proto, 0)

    def delete(self, port, proto):
        self._soap("DeletePortMapping", [("NewRemoteHost", ""), ("NewExternalPort", port),
                                         ("NewProtocol", proto)])

    def external_ip(self):
        m = re.search(r"<NewExternalIPAddress>([^<]*)<", self._soap("GetExternalIPAddress", []))
        return m.group(1) if m else ""


class UPnPError(Exception):
    def __init__(self, code, text=""):
        super().__init__(f"UPnP error {code}")
        self.code = code


def _ssdp_locations(timeout=2.0):
    found = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        s.settimeout(0.3)
        for st in SEARCH_TARGETS:
            msg = (f'M-SEARCH * HTTP/1.1\r\nHOST: {SSDP[0]}:{SSDP[1]}\r\nMAN: "ssdp:discover"\r\n'
                   f"MX: 2\r\nST: {st}\r\n\r\n").encode()
            try:
                s.sendto(msg, SSDP)
            except OSError:
                return found
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                data, _ = s.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            m = re.search(rb"(?im)^location:\s*(\S+)", data)
            if m:
                loc = m.group(1).decode("ascii", "replace")
                if loc.startswith("http://") and loc not in found:
                    found.append(loc)
    return found


def _local_ip_for(host):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((host, 1900))                  # no packet is sent: this only picks the route
        return s.getsockname()[0]


def gateway_from_description(location, xml_text):
    """Gateway for the WAN connection service in a device description, or None."""
    root = ET.fromstring(xml_text)

    def tag(el):
        return el.tag.rsplit("}", 1)[-1]
    base = location
    for el in root.iter():
        if tag(el) == "URLBase" and (el.text or "").strip():
            base = el.text.strip()
    services = {}
    for el in root.iter():
        if tag(el) != "service":
            continue
        fields = {tag(c): (c.text or "").strip() for c in el}
        if fields.get("serviceType") in SERVICES and fields.get("controlURL"):
            services.setdefault(fields["serviceType"], fields["controlURL"])
    for st in SERVICES:
        if st in services:
            url = urllib.parse.urljoin(base, services[st])
            host = urllib.parse.urlsplit(url).hostname
            return Gateway(url, st, _local_ip_for(host))
    return None


def discover(timeout=2.0):
    """The router's port-mapping service, or None."""
    for loc in _ssdp_locations(timeout):
        try:
            with _OPENER.open(loc, timeout=4) as r:
                gw = gateway_from_description(loc, r.read(512 * 1024))
        except (OSError, ET.ParseError, ValueError):
            continue
        if gw:
            return gw
    return None


class PortMapper:
    """Keeps (port, protocol) pairs open on the router while torrents use them.

    Several aria2 processes (one per torrent) each ask for their own ports; mappings are
    renewed in one background thread and removed when the last user lets go."""

    def __init__(self, finder=discover):
        self._finder = finder
        self._lock = threading.Lock()
        self._users = {}             # (port, proto) -> count
        self._mapped = set()
        self._gw = None
        self._searched = 0.0
        self._wake = threading.Event()
        self._thread = None
        self.status = ""             # for Preferences/logs: "", "open", "no router", "refused"

    def hold(self, ports):
        with self._lock:
            for p in ports:
                self._users[p] = self._users.get(p, 0) + 1
            if not self._thread:
                self._thread = threading.Thread(target=self._loop, daemon=True, name="draco-upnp")
                self._thread.start()
        self._wake.set()

    def release(self, ports):
        with self._lock:
            for p in ports:
                n = self._users.get(p, 0) - 1
                if n > 0:
                    self._users[p] = n
                else:
                    self._users.pop(p, None)
        self._wake.set()

    def _gateway(self):
        if self._gw is None and time.monotonic() - self._searched > 300:
            self._searched = time.monotonic()
            self._gw = self._finder()
            if not self._gw:
                self.status = "no router"
        return self._gw

    def _loop(self):
        renew_at = 0.0
        while True:
            self._wake.wait(30)
            self._wake.clear()
            with self._lock:
                want = set(self._users)
            gone, new = self._mapped - want, want - self._mapped
            if time.monotonic() >= renew_at:
                new = want                       # renew every lease, not only the new ones
                renew_at = time.monotonic() + RENEW
            if not (gone or new):
                continue
            gw = self._gateway()
            if not gw:
                continue
            for port, proto in sorted(gone):
                try:
                    gw.delete(port, proto)
                except (OSError, UPnPError):
                    pass
                self._mapped.discard((port, proto))
            for port, proto in sorted(new):
                try:
                    gw.add(port, proto)
                    self._mapped.add((port, proto))
                    self.status = "open"
                except UPnPError:
                    self.status = "refused"      # e.g. the port is taken by another device
                except OSError:
                    self._gw = None              # router went away or changed: look again later
                    self._searched = 0.0
                    break

    def close(self):
        """Remove every mapping now (on quit)."""
        with self._lock:
            self._users.clear()
            mapped, self._mapped = set(self._mapped), set()
        gw = self._gw
        for port, proto in mapped:
            try:
                gw.delete(port, proto)
            except (OSError, UPnPError, AttributeError):
                pass


MAPPER = PortMapper()
