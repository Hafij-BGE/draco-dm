"""BitTorrent downloads (magnet links and .torrent files), run by aria2c.

* The torrent's file list ("metadata") comes first: a .torrent link is fetched like any file,
  a local .torrent is read, and a magnet link asks the swarm (aria2c --bt-metadata-only).
  The .torrent is kept in DATA_DIR/torrents/<info hash>.torrent, so pausing, restarting
  Draco and seeding never need the swarm for it again.
* Then one aria2c per torrent downloads the chosen files (--select-file) into the chosen
  folder (--dir, --index-out when the top folder/file was renamed). Draco reads its progress
  over aria2's JSON-RPC on 127.0.0.1 with a random secret.
* Pausing shuts aria2 down cleanly, so its .aria2 control file is current and the next start
  continues. When the files are complete the download counts as finished; with seeding on it
  keeps sharing (status "seeding") until the ratio or time limit, then it is "complete".
"""

import base64
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .config import DATA_DIR
from .engine import DownloadError, build_headers, build_opener, open_url, sanitize_filename, sanitize_name
from .media import _TaskBase
from .osdeps import IS_WIN, popen_kwargs, which
from .upnp import MAPPER

ARIA2 = which("aria2c")
TORRENT_DIR = DATA_DIR / "torrents"
MAX_TORRENT_FILE = 32 * 1024 * 1024
DHT_BOOTSTRAP = "dht.transmissionbt.com:6881"
# Well-known open trackers added to public torrents and magnet links (never to private ones):
# a magnet with one dead tracker otherwise finds few or no peers.
PUBLIC_TRACKERS = ("udp://tracker.opentrackr.org:1337/announce", "udp://open.demonii.com:1337/announce",
                   "udp://open.stealth.si:80/announce", "udp://tracker.torrent.eu.org:451/announce",
                   "udp://exodus.desync.com:6969/announce", "udp://explodie.org:6969/announce",
                   "udp://tracker.dler.org:6969/announce", "udp://opentracker.io:6969/announce")
INSTALL_HINT = ("Torrents need aria2c.exe next to Draco.exe (reinstall Draco)" if IS_WIN
                else "Torrents need aria2 (sudo apt install aria2)")


# ---------------------------------------------------------------- bencode
def _decode(data, i):
    c = data[i:i + 1]
    if c == b"i":
        end = data.index(b"e", i)
        return int(data[i + 1:end]), end + 1
    if c == b"l":
        out, i = [], i + 1
        while data[i:i + 1] != b"e":
            v, i = _decode(data, i)
            out.append(v)
        return out, i + 1
    if c == b"d":
        out, i = {}, i + 1
        while data[i:i + 1] != b"e":
            k, i = _decode(data, i)
            start = i
            v, i = _decode(data, i)
            out[k] = v
            if k == b"info":
                out[b"\0info-span"] = (start, i)     # the info dict as it was written (for the hash)
        return out, i + 1
    if c.isdigit():
        colon = data.index(b":", i)
        n = int(data[i:colon])
        if n < 0 or colon + 1 + n > len(data):
            raise ValueError("bad string length")
        return data[colon + 1:colon + 1 + n], colon + 1 + n
    raise ValueError(f"bad bencode at byte {i}")


def bdecode(data):
    try:
        value, end = _decode(bytes(data), 0)
    except (IndexError, ValueError, RecursionError) as e:
        raise ValueError(f"not a torrent file ({e})") from None
    return value


def bencode(v):
    if isinstance(v, bool):
        v = int(v)
    if isinstance(v, int):
        return b"i%de" % v
    if isinstance(v, str):
        v = v.encode()
    if isinstance(v, (bytes, bytearray)):
        return b"%d:%s" % (len(v), bytes(v))
    if isinstance(v, (list, tuple)):
        return b"l" + b"".join(bencode(x) for x in v) + b"e"
    if isinstance(v, dict):
        items = sorted((k.encode() if isinstance(k, str) else k, x) for k, x in v.items())
        return b"d" + b"".join(bencode(k) + bencode(x) for k, x in items) + b"e"
    raise TypeError(type(v))


# ---------------------------------------------------------------- torrent files
def _text(d, key):
    raw = d.get(key + b".utf-8", d.get(key, b""))
    return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)


def _safe_part(part):
    part = sanitize_name(part).strip()   # never percent-decoded: aria2 writes the name as it is
    return "_" if part in ("", ".", "..") else part


def parse_torrent(data):
    """{'name', 'info_hash', 'size', 'files': [{'path', 'size', 'pad'}], 'private'} from .torrent bytes.

    File paths start with the torrent's name (the top folder, or the file itself), use "/" and
    are made safe (no "..", no characters the file system refuses). The list order is aria2's
    file index (1-based)."""
    meta = bdecode(data)
    if not isinstance(meta, dict) or not isinstance(meta.get(b"info"), dict):
        raise ValueError("not a torrent file")
    start, end = meta[b"\0info-span"]
    info = meta[b"info"]
    raw_name = _text(info, b"name") or "torrent"
    name = _safe_part(raw_name)
    files = []
    differs = name != raw_name          # aria2 would write another path than ours: Draco names each file
    if b"files" in info:
        for f in info[b"files"]:
            raw = f.get(b"path.utf-8") or f.get(b"path") or []
            pad = b"p" in (f.get(b"attr") or b"") or raw[:1] == [b".pad"]
            texts = [p.decode("utf-8", "replace") for p in raw]
            parts = [_safe_part(p) for p in texts]
            differs = differs or parts != texts
            files.append({"path": "/".join([name] + parts), "size": int(f.get(b"length", 0)), "pad": pad})
    elif b"length" in info:
        files.append({"path": name, "size": int(info[b"length"]), "pad": False})
    else:
        raise ValueError("BitTorrent v2-only torrents are not supported")
    return {"name": name, "info_hash": hashlib.sha1(bytes(data)[start:end]).hexdigest(),
            "size": sum(f["size"] for f in files if not f["pad"]), "files": files,
            "private": bool(info.get(b"private")), "paths_differ": differs}


def save_torrent(data):
    """Keep a .torrent in Draco's own folder; returns (path, parsed info)."""
    info = parse_torrent(data)
    TORRENT_DIR.mkdir(parents=True, exist_ok=True)
    path = TORRENT_DIR / f"{info['info_hash']}.torrent"
    if not path.exists() or path.read_bytes() != bytes(data):
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(bytes(data))
        os.replace(tmp, path)
    return path, info


def load_torrent(path):
    return parse_torrent(Path(path).read_bytes())


# ---------------------------------------------------------------- links
_BTIH = re.compile(r"urn:btih:([0-9a-fA-F]{40}|[A-Za-z2-7]{32})")


def is_magnet(url):
    return (url or "").strip().lower().startswith("magnet:?")


def local_torrent(url):
    """A .torrent file on this computer (path or file:// link), else None."""
    url = (url or "").strip()
    if url.lower().startswith("file://"):
        url = urllib.parse.unquote(urllib.parse.urlparse(url).path)
        if os.name == "nt" and re.match(r"^/[A-Za-z]:", url):
            url = url[1:]
    if not url.lower().endswith(".torrent"):
        return None
    p = Path(url).expanduser()
    return p if p.is_absolute() and p.is_file() else None


def is_torrent_link(url, content_type=""):
    url = (url or "").strip()
    if is_magnet(url) or local_torrent(url):
        return True
    if "bittorrent" in (content_type or "").lower():
        return True
    if url.lower().startswith(("http://", "https://")):
        return urllib.parse.urlparse(url).path.lower().endswith(".torrent")
    return False


def magnet_info(url):
    """(info hash in hex or "", display name or "") of a magnet link."""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url.strip()).query)
    ih = ""
    for xt in q.get("xt", []):
        m = _BTIH.search(xt)
        if m:
            h = m.group(1)
            ih = h.lower() if len(h) == 40 else base64.b32decode(h.upper()).hex()
            break
    return ih, (q.get("dn") or [""])[0]


def guess_name(url):
    """A first name for the list while the torrent's own name is still unknown."""
    if is_magnet(url):
        ih, dn = magnet_info(url)
        return sanitize_filename(dn) if dn else (f"torrent {ih[:8]}" if ih else "torrent")
    p = local_torrent(url)
    base = p.name if p else urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
    stem = base[:-8] if base.lower().endswith(".torrent") else base
    return sanitize_filename(stem or "torrent")


# ---------------------------------------------------------------- aria2
def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


_PORTS_LOCK = threading.Lock()
_PORTS_USED = set()


def _peer_port_free(port):
    for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
        with socket.socket(socket.AF_INET, kind) as s:
            try:
                s.bind(("0.0.0.0", port))
            except OSError:
                return False
    return True


def _home_port():
    """This install's own peer port: picked once at random, so the router mapping, other peers and
    the DHT can keep finding it, without clashing with another torrent app on the same network."""
    f = TORRENT_DIR / "port"
    try:
        port = int(f.read_text().strip())
        if 1024 < port < 65000:
            return port
    except (OSError, ValueError):
        pass
    port = 20000 + secrets.randbelow(40000)
    try:
        TORRENT_DIR.mkdir(parents=True, exist_ok=True)
        f.write_text(str(port))
    except OSError:
        pass
    return port


class PeerPort:
    """One TCP+UDP port for one aria2 process, opened on the router (UPnP) while it is held."""

    def __init__(self, settings):
        s = settings or {}
        want = str(s.get("torrent_port", "") or "").strip()
        m = re.fullmatch(r"(\d{2,5})(?:-(\d{2,5}))?", want)
        if m:
            lo = int(m.group(1))
            hi = max(lo, int(m.group(2) or lo))
        else:
            lo = _home_port()
            hi = lo + 49
        self.port = None
        with _PORTS_LOCK:
            for p in range(lo, min(hi, 65535) + 1):
                if p not in _PORTS_USED and _peer_port_free(p):
                    self.port = p
                    _PORTS_USED.add(p)
                    break
        self._held = []
        if self.port and s.get("torrent_upnp", True):
            self._held = [(self.port, "TCP"), (self.port, "UDP")]
            MAPPER.hold(self._held)

    def close(self):
        if self._held:
            MAPPER.release(self._held)
            self._held = []
        with _PORTS_LOCK:
            _PORTS_USED.discard(self.port)


_RPC_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def rpc_call(port, secret, method, *params):
    """One aria2 JSON-RPC call on 127.0.0.1; None when aria2 isn't answering."""
    body = json.dumps({"jsonrpc": "2.0", "id": "draco", "method": method,
                       "params": [f"token:{secret}", *params]}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/jsonrpc", body, {"Content-Type": "application/json"})
    try:
        with _RPC_OPENER.open(req, timeout=3) as r:
            return json.loads(r.read().decode()).get("result")
    except (OSError, ValueError):
        return None


def _rpc_opts(port, secret):
    return ["--enable-rpc=true", "--rpc-listen-all=false", f"--rpc-listen-port={port}", f"--rpc-secret={secret}"]


def peer_rows(peers, num_pieces=0):
    """aria2.getPeers result -> [{'addr', 'down', 'up', 'have' (0..1 or None), 'seeder', 'choked'}]."""
    out = []
    for p in peers or []:
        try:
            have = None
            bf = p.get("bitfield") or ""
            if num_pieces > 0 and bf:
                have = min(1.0, sum(bin(int(c, 16)).count("1") for c in bf) / num_pieces)
            ip = p.get("ip", "")
            out.append({"addr": (f"[{ip}]" if ":" in ip else ip) + f":{p.get('port', '')}",
                        "down": int(p.get("downloadSpeed") or 0), "up": int(p.get("uploadSpeed") or 0),
                        "have": 1.0 if p.get("seeder") == "true" else have,
                        "seeder": p.get("seeder") == "true", "choked": p.get("peerChoking") == "true"})
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda r: (-r["down"], -r["up"], r["addr"]))
    return out


def _base_opts(peer_port=None, settings=None, private=False):
    TORRENT_DIR.mkdir(parents=True, exist_ok=True)
    s = settings or {}
    extra = []
    if peer_port:            # TCP for peers and UDP for DHT on one known port, so the router can open it
        extra += [f"--listen-port={peer_port}", f"--dht-listen-port={peer_port}"]
    if not private and s.get("torrent_public_trackers", True):
        extra.append("--bt-tracker=" + ",".join(PUBLIC_TRACKERS))
    # keep looking for more peers until the torrent is really fast (aria2 stops at 50 KB/s)
    extra += ["--bt-max-peers=100", "--bt-request-peer-speed-limit=10M"]
    return extra + ["--console-log-level=error", "--summary-interval=0", "--enable-color=false",
            "--download-result=hide", f"--stop-with-process={os.getpid()}",
            "--enable-dht=true", f"--dht-file-path={TORRENT_DIR / 'dht.dat'}", "--bt-enable-lpd=true",
            # aria2 has no built-in DHT bootstrap: without one, an empty dht.dat stays empty and a magnet
            # whose trackers give no reachable peers never gets its file list
            f"--dht-entry-point={DHT_BOOTSTRAP}",
            "--follow-torrent=false", "--file-allocation=none", "--auto-file-renaming=false"]


_ERRORS = {"9": "Not enough disk space", "13": "A file with this name is already there",
           "16": "Could not create a file in the download folder", "17": "Could not write the file",
           "18": "Could not create the folder", "6": "Network problem", "2": "Timed out",
           "3": "Not found", "26": "Bad torrent file", "27": "Bad magnet link"}


def _error_text(lines, rc):
    for line in reversed(lines):
        m = re.search(r"errorCode=(\d+)\s*(.*)", line)
        if m:
            return f"{_ERRORS.get(m.group(1), 'aria2 error')}: {m.group(2).strip()[:200]}"
    for line in reversed(lines):
        if "[ERROR]" in line or "Exception" in line:
            return line.strip()[:240]
    return _ERRORS.get(str(rc), f"aria2 stopped (exit code {rc})")


def fetch_metadata(item, settings, stop_event=None, timeout=180, on_proc=None, on_status=None):
    """Make sure the item has its .torrent; returns (path, info). Raises DownloadError."""
    stop_event = stop_event or threading.Event()
    if item.get("torrent_file") and Path(item["torrent_file"]).is_file():
        try:
            return Path(item["torrent_file"]), load_torrent(item["torrent_file"])
        except (OSError, ValueError):
            pass                                   # damaged copy: fetch it again
    url = item["url"].strip()
    local = local_torrent(url)
    try:
        if local:
            data = local.read_bytes()[:MAX_TORRENT_FILE + 1]
        elif is_magnet(url):
            data = _magnet_metadata(url, stop_event, timeout, on_proc, on_status, settings)
        else:
            resp = open_url(build_opener(settings), item.get("final_url") or url,
                            build_headers(item, settings), settings["timeout"])
            data = resp.read(MAX_TORRENT_FILE + 1)
        if len(data) > MAX_TORRENT_FILE:
            raise DownloadError("The .torrent file is too large")
        path, info = save_torrent(data)
    except ValueError as e:
        raise DownloadError(f"The link did not give a usable .torrent file ({e})") from None
    except OSError as e:
        raise DownloadError(str(e)) from None
    item["torrent_file"], item["info_hash"] = str(path), info["info_hash"]
    return path, info


def _complete_torrent(path):
    try:
        parse_torrent(path.read_bytes())
        return True
    except (OSError, ValueError):
        return False           # still being written


def _magnet_metadata(url, stop_event, timeout, on_proc=None, on_status=None, settings=None):
    """The .torrent of a magnet link, from the peers. on_status(peers, seeds, peer_rows) while waiting."""
    if not ARIA2:
        raise DownloadError(INSTALL_HINT)
    ih, _dn = magnet_info(url)
    if ih and (TORRENT_DIR / f"{ih}.torrent").is_file():
        return (TORRENT_DIR / f"{ih}.torrent").read_bytes()
    work = TORRENT_DIR / f".meta-{secrets.token_hex(4)}"
    work.mkdir(parents=True, exist_ok=True)
    port, secret = _free_port(), secrets.token_hex(16)
    peer = PeerPort(settings)
    cmd = [ARIA2] + _base_opts(peer.port, settings) + _rpc_opts(port, secret) + [
        "--bt-metadata-only=true", "--bt-save-metadata=true", "--seed-time=0", f"--dir={work}", url]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", **popen_kwargs())
    except OSError:
        peer.close()
        raise
    if on_proc:
        on_proc(proc)
    lines = []
    threading.Thread(target=lambda: [lines.append(x) for x in proc.stdout], daemon=True).start()
    try:
        end = time.monotonic() + timeout
        next_poll = 0.0
        while proc.poll() is None:
            if stop_event.wait(0.3):
                raise DownloadError("Stopped")
            found = sorted(work.glob("*.torrent"))
            if found and _complete_torrent(found[0]):
                break        # RPC mode: aria2 keeps running after the file list arrived
            if time.monotonic() > end:
                raise DownloadError("No one shared this torrent's file list in time "
                                    "(no peers yet; try again later)")
            if time.monotonic() >= next_poll:
                next_poll = time.monotonic() + 1.0
                act = rpc_call(port, secret, "aria2.tellActive", ["gid", "connections", "numSeeders"])
                if act and on_status:
                    peers = rpc_call(port, secret, "aria2.getPeers", act[0]["gid"]) or []
                    on_status(int(act[0].get("connections") or 0), int(act[0].get("numSeeders") or 0),
                              peer_rows(peers))
                elif act == []:          # stopped: finished (file list written) or failed
                    st = (rpc_call(port, secret, "aria2.tellStopped", 0, 1,
                                   ["status", "errorCode", "errorMessage"]) or [{}])[0]
                    if st.get("status") == "error":
                        code = str(st.get("errorCode", ""))
                        raise DownloadError(f"{_ERRORS.get(code, 'aria2 error')}: "
                                            f"{(st.get('errorMessage') or '').strip()[:200]}".rstrip(": "))
        found = sorted(work.glob("*.torrent"))
        if not found:
            raise DownloadError(_error_text(lines, proc.returncode))
        return found[0].read_bytes()
    finally:
        if proc.poll() is None:
            rpc_call(port, secret, "aria2.shutdown")
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
        peer.close()
        for p in work.glob("*"):
            try:
                p.unlink()
            except OSError:
                pass
        try:
            work.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------- where the files are
def selected_indices(item, info):
    """aria2 file numbers (1-based) to download: the user's choice, never padding files."""
    files = info["files"]
    chosen = item.get("torrent_select")
    wanted = set(chosen) if chosen else set(range(1, len(files) + 1))
    return [i for i in range(1, len(files) + 1) if i in wanted and not files[i - 1]["pad"]]


def _fix_legacy_name(item, info):
    """Older Draco versions decoded "%2E" in a torrent's name ("report%2Epdf" -> "report.pdf") while
    aria2 wrote the literal name: point such an item back at the files aria2 really wrote."""
    name = item.get("filename")
    if name and not item.get("torrent_rename") and name != info["name"] and name == sanitize_filename(info["name"]):
        item["filename"] = info["name"]


def mapped_path(item, info, rel):
    """A torrent file path (starting with the torrent's name) under the root the item uses."""
    root = item.get("filename") or info["name"]
    return root + rel[len(info["name"]):] if root != info["name"] else rel


def data_paths(item):
    """The item's files on disk (for deleting a download), top folder last."""
    try:
        info = load_torrent(item["torrent_file"])
    except (KeyError, OSError, ValueError, TypeError):
        return []
    _fix_legacy_name(item, info)
    base = Path(item["save_dir"])
    out = [base / mapped_path(item, info, info["files"][i - 1]["path"]) for i in selected_indices(item, info)]
    root = base / (item.get("filename") or info["name"])
    for name in {item.get("filename") or "", info["name"]} - {""}:
        out.append(base / (name + ".aria2"))
    if len(info["files"]) > 1 or info["files"][0]["path"] != info["name"]:
        out.append(root)                           # the folder, removed only when empty
    return out


def _is_partial(p, sizes):
    """For an unfinished download: is `p` this torrent's own part? Only while aria2's control file
    is there, and never a file bigger than the torrent's (so a user's own file of that name stays)."""
    if p.is_dir() or p.suffix == ".aria2":
        return True
    try:
        return p in sizes and p.stat().st_size <= sizes[p]
    except OSError:
        return False


def delete_data(item, partial_only=False):
    """Delete the item's files. partial_only (removing an unfinished download without "delete
    files"): only the part aria2 is writing, recognised by its .aria2 control file and size."""
    sizes = {}
    if partial_only:
        try:
            info = load_torrent(item["torrent_file"])
        except (KeyError, OSError, ValueError, TypeError):
            return
        _fix_legacy_name(item, info)
        base = Path(item["save_dir"])
        names = {item.get("filename") or "", info["name"]} - {""}
        if not any((base / (n + ".aria2")).is_file() for n in names):
            return                                   # no control file: nothing here is a part of ours
        sizes = {base / mapped_path(item, info, f["path"]): f["size"] for f in info["files"]}
    for p in data_paths(item):
        if partial_only and not _is_partial(p, sizes):
            continue
        try:
            if p.is_dir():
                for sub in sorted(p.rglob("*"), key=lambda x: len(x.parts), reverse=True):
                    if sub.is_dir():
                        try:
                            sub.rmdir()            # only empty folders: never someone else's files
                        except OSError:
                            pass
                p.rmdir()
            elif p.is_file():
                p.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- the task
class TorrentTask(_TaskBase):
    kind = "torrent"
    on_downloaded = None        # set by the manager: called once when all chosen files are there

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.port = 0
        self.secret = ""
        self.gid = None
        self.done = False
        self._meta_proc = None
        self.peer = None                # PeerPort while aria2 runs
        self.peer_list = []             # [{'addr', 'down', 'up', 'have', 'seeder', 'choked'}] for the window
        self._peers_at = 0.0

    def stop(self):
        # aria2 is shut down from the task's own loop (cleanly, so it can save where it was)
        self.stop_event.set()
        mp = self._meta_proc
        if mp and mp.poll() is None:
            mp.terminate()

    def set_speed_limit(self, kbps):
        super().set_speed_limit(kbps)
        if self.gid:
            threading.Thread(target=self._rpc, args=("aria2.changeOption", self.gid,
                                                     {"max-download-limit": f"{int(kbps)}K"}),
                             daemon=True).start()

    def _rpc(self, method, *params):
        return rpc_call(self.port, self.secret, method, *params)

    def _meta_status(self, peers, seeds, rows):
        it = self.item
        it["peers"], it["seeds"] = peers, seeds
        self.peer_list = rows
        self.on_update(it)

    def _command(self, path, info):
        it, s = self.item, self.settings
        cmd = [ARIA2] + _base_opts(self.peer.port if self.peer else None, s, info.get("private")) + \
            _rpc_opts(self.port, self.secret) + [
            f"--dir={it['save_dir']}", "--continue=true",
            "--bt-save-metadata=false", "--rpc-save-upload-metadata=false"]
        idx = selected_indices(it, info)
        if len(idx) < len(info["files"]):
            cmd.append("--select-file=" + ",".join(map(str, idx)))
        if (it.get("filename") or info["name"]) != info["name"] or info.get("paths_differ"):
            # every file, not only the chosen ones: aria2 also writes the edge pieces of the others
            for i in range(1, len(info["files"]) + 1):
                cmd.append(f"--index-out={i}={mapped_path(it, info, info['files'][i - 1]['path'])}")
        root = Path(it["save_dir"]) / (it.get("filename") or info["name"])
        control = Path(str(root) + ".aria2")
        if root.exists() and not control.exists():
            cmd.append("--check-integrity=true")    # files already there: keep the good pieces
        if s.get("torrent_seed", True):
            cmd.append(f"--seed-ratio={max(0.0, float(s.get('torrent_seed_ratio', 1.0) or 0))}")
            minutes = int(s.get("torrent_seed_minutes", 60) or 0)
            if minutes > 0:                             # 0 = no time limit (aria2: no --seed-time)
                cmd.append(f"--seed-time={minutes}")
        else:
            cmd.append("--seed-time=0")
        up = int(s.get("torrent_upload_kbps", 0) or 0)
        if up:
            cmd.append(f"--max-upload-limit={up}K")
        down = int(it.get("speed_limit_kbps") or 0)
        if down:
            cmd.append(f"--max-download-limit={down}K")
        if s["speed_limit_kbps"]:
            cmd.append(f"--max-overall-download-limit={int(s['speed_limit_kbps'])}K")
        return cmd + [str(path)]

    def _apply_info(self, info):
        it = self.item
        it["torrent_name"] = info["name"]
        it["torrent_files"] = [{"path": f["path"], "size": f["size"], "pad": f["pad"]} for f in info["files"]]
        idx = selected_indices(it, info)
        _fix_legacy_name(it, info)
        it["size"] = sum(info["files"][i - 1]["size"] for i in idx)
        if not it.get("torrent_named"):
            root = sanitize_filename(it["torrent_rename"]) if it.get("torrent_rename") else info["name"]
            reserve = getattr(self, "reserve_name", None)
            it["filename"] = reserve(it, root) if reserve else root
            it["torrent_named"] = True
        self.on_update(it)

    def _run(self):
        it = self.item
        if not ARIA2:
            raise DownloadError(INSTALL_HINT)
        self._set(status="connecting", speed=0, peers=0, seeds=0)
        path, info = fetch_metadata(it, self.settings, self.stop_event,
                                    on_proc=lambda p: setattr(self, "_meta_proc", p), on_status=self._meta_status)
        self.peer_list = []
        if self.stop_event.is_set():
            return False
        self._apply_info(info)
        Path(it["save_dir"]).mkdir(parents=True, exist_ok=True)
        self.port, self.secret = _free_port(), secrets.token_hex(16)
        self.peer = PeerPort(self.settings)
        try:
            return self._run_aria2(path, info)
        finally:
            self.peer.close()

    def _run_aria2(self, path, info):
        it = self.item
        self.proc = subprocess.Popen(self._command(path, info), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", **popen_kwargs())
        lines = []

        def read():
            for line in self.proc.stdout:
                lines.append(line.rstrip())
                del lines[:-40]
        threading.Thread(target=read, daemon=True).start()
        keys = ["gid", "status", "totalLength", "completedLength", "uploadLength", "downloadSpeed",
                "uploadSpeed", "connections", "numSeeders", "seeder", "verifiedLength", "errorCode", "errorMessage",
                "numPieces"]
        quit_sent = 0.0
        failed = ""
        while self.proc.poll() is None:
            if self.stop_event.is_set() or failed or (self.done and quit_sent):
                if not quit_sent:
                    quit_sent = time.monotonic()
                    self._rpc("aria2.forceShutdown")
                elif time.monotonic() - quit_sent > 8:
                    self.proc.terminate()
                    try:
                        self.proc.wait(5)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                    break
            else:
                # With RPC on, aria2 keeps running after the torrent stops (complete, seeding
                # limit reached or failed): read it from the stopped list and shut aria2 down.
                active = self._rpc("aria2.tellActive", keys)
                st = active[0] if active else None
                if active == []:
                    st = (self._rpc("aria2.tellStopped", 0, 1, keys) or [None])[0]
                if st:
                    self._update(st)
                    if st.get("status") == "error":
                        failed = st.get("errorMessage") or f"aria2 error {st.get('errorCode', '')}".strip()
                    if st.get("status") in ("complete", "error", "removed"):
                        quit_sent = time.monotonic()
                        self._rpc("aria2.shutdown")
            time.sleep(0.5)
        self.proc.wait()
        try:
            self.proc.stdout.close()
        except OSError:
            pass
        rc = self.proc.returncode
        if failed and not self.done:
            it["error"] = failed[:240]
            return False
        if self.done or (rc == 0 and not self.stop_event.is_set()):
            self._mark_done()
            it["downloaded"] = it["size"]
            return True
        if self.stop_event.is_set():
            return False
        it["error"] = _error_text(lines, rc)
        return False

    def _update(self, st):
        it = self.item

        def n(k):
            try:
                return int(st.get(k) or 0)
            except ValueError:
                return 0
        self.gid = st.get("gid")
        total, done = n("totalLength"), n("completedLength")
        it["downloaded"] = min(done, it["size"]) if it.get("size", -1) > 0 else done
        if total and it.get("size", -1) <= 0:
            it["size"] = total
        it["speed"] = self.speed = n("downloadSpeed")
        it["up_speed"] = n("uploadSpeed")
        it["uploaded"] = n("uploadLength")
        it["peers"], it["seeds"] = n("connections"), n("numSeeders")
        if self.gid and time.monotonic() - self._peers_at > 2 and st.get("status") == "active":
            self._peers_at = time.monotonic()
            self.peer_list = peer_rows(self._rpc("aria2.getPeers", self.gid), n("numPieces"))
        if st.get("seeder") == "true" or (total and done >= total):
            it["downloaded"] = it["size"]
            seeding = st.get("status") == "active" and self.settings.get("torrent_seed", True)
            it["status"] = "seeding" if seeding else "checking"
            it["speed"] = self.speed = 0
            self._mark_done()
        elif "verifiedLength" in st:
            it["status"] = "checking"          # checking the files that are already there
        else:
            it["status"] = "downloading" if (it["peers"] or it["speed"]) else "connecting"
        self.on_update(it)

    def _mark_done(self):
        if not self.done:
            self.done = True
            it = self.item
            it["finished"] = time.time()
            if self.on_downloaded:
                self.on_downloaded(it)
