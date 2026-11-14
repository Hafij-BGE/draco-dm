"""Torrent tests: .torrent parsing and links, and (when aria2c is installed) real downloads from a
local aria2c seeder found through a tiny local tracker. Run: python3 -m unittest tests.test_torrent"""

import base64
import hashlib
import http.server
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path

from draco import torrent
from draco.config import Settings
from draco.engine import RateLimiter
from draco.torrent import TorrentTask, bdecode, bencode

PIECE = 16 * 1024


def make_torrent(root, tracker=None, single=False, pad_after_first=False):
    """Build a v1 .torrent for the file or folder `root`; returns the .torrent bytes."""
    root = Path(root)
    if single:
        paths, info = [root], {"name": root.name, "length": root.stat().st_size}
    else:
        paths = sorted(p for p in root.rglob("*") if p.is_file())
        files = [{"length": p.stat().st_size, "path": list(p.relative_to(root).parts)} for p in paths]
        if pad_after_first:
            files.insert(1, {"length": 0, "path": [".pad", "0"], "attr": "p"})
        info = {"name": root.name, "files": files}
    blob = b"".join(p.read_bytes() for p in paths)
    info["piece length"] = PIECE
    info["pieces"] = b"".join(hashlib.sha1(blob[i:i + PIECE]).digest() for i in range(0, len(blob), PIECE))
    meta = {"info": info, "created by": "draco tests"}
    if tracker:
        meta["announce"] = tracker
    return bencode(meta)


def info_hash(data):
    return hashlib.sha1(bencode(bdecode(data)[b"info"])).hexdigest()


class TorrentFormatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self._old_dir = torrent.TORRENT_DIR
        torrent.TORRENT_DIR = self.dir / "store"

    def tearDown(self):
        torrent.TORRENT_DIR = self._old_dir
        self.tmp.cleanup()

    def test_bencode_round_trip(self):
        v = {b"a": [1, b"x", {b"k": -5}], b"b": b""}
        data = bencode(v)
        self.assertEqual(data, b"d1:ali1e1:xd1:ki-5eee1:b0:e")
        self.assertEqual(bdecode(data), v)
        for bad in (b"", b"d1:a", b"5:ab", b"x"):
            with self.assertRaises(ValueError):
                bdecode(bad)

    def test_parse_multi_file(self):
        root = self.dir / "Album"
        (root / "cd1").mkdir(parents=True)
        (root / "cd1" / "a.bin").write_bytes(os.urandom(40000))
        (root / "b.txt").write_bytes(b"hello")
        data = make_torrent(root, pad_after_first=True)
        info = torrent.parse_torrent(data)
        self.assertEqual(info["name"], "Album")
        self.assertEqual(info["info_hash"], info_hash(data))
        self.assertEqual([f["path"] for f in info["files"]], ["Album/b.txt", "Album/pad/0", "Album/cd1/a.bin"])
        self.assertEqual([f["pad"] for f in info["files"]], [False, True, False])
        self.assertEqual(info["size"], 40005)
        self.assertFalse(info["private"])
        # padding files are never asked for, and the user's choice is kept
        self.assertEqual(torrent.selected_indices({}, info), [1, 3])
        self.assertEqual(torrent.selected_indices({"torrent_select": [3]}, info), [3])

    def test_unsafe_paths_are_made_safe(self):
        info = {"name": "..", "piece length": PIECE, "pieces": b"\0" * 20,
                "files": [{"length": 1, "path": ["..", "..", "etc", "passwd"]}]}
        parsed = torrent.parse_torrent(bencode({"info": info}))
        path = parsed["files"][0]["path"]
        self.assertNotIn("..", path.split("/"))
        self.assertTrue(path.endswith("/etc/passwd"))
        self.assertNotIn(parsed["name"], ("", ".", ".."))

    def test_v2_only_and_garbage(self):
        with self.assertRaises(ValueError):
            torrent.parse_torrent(bencode({"info": {"name": "x", "file tree": {}, "meta version": 2}}))
        with self.assertRaises(ValueError):
            torrent.parse_torrent(b"<html>not a torrent</html>")

    def test_magnet_links(self):
        ih = "c9e15763f722f23e98a29decdfae341b98d53056"
        self.assertEqual(torrent.magnet_info(f"magnet:?xt=urn:btih:{ih.upper()}&dn=Some+Show"), (ih, "Some Show"))
        b32 = base64.b32encode(bytes.fromhex(ih)).decode()
        self.assertEqual(torrent.magnet_info(f"magnet:?xt=urn:btih:{b32}")[0], ih)
        self.assertEqual(torrent.guess_name(f"magnet:?xt=urn:btih:{ih}&dn=a/b"), "a_b")
        self.assertEqual(torrent.guess_name(f"magnet:?xt=urn:btih:{ih}"), "torrent c9e15763")
        self.assertEqual(torrent.guess_name("https://x.org/files/Linux%20ISO.torrent?k=1"), "Linux ISO")

    def test_torrent_links(self):
        f = self.dir / "x.torrent"
        f.write_bytes(b"d4:infod4:name1:x6:lengthi1eee")
        self.assertTrue(torrent.is_torrent_link("magnet:?xt=urn:btih:" + "a" * 40))
        self.assertTrue(torrent.is_torrent_link(str(f)))
        self.assertTrue(torrent.is_torrent_link(f.as_uri()))
        self.assertTrue(torrent.is_torrent_link("https://x.org/a.torrent"))
        self.assertTrue(torrent.is_torrent_link("https://x.org/dl?id=4", "application/x-bittorrent"))
        self.assertFalse(torrent.is_torrent_link("https://x.org/a.torrent.html"))
        self.assertFalse(torrent.is_torrent_link("relative/x.torrent"))
        self.assertFalse(torrent.is_torrent_link(str(self.dir / "missing.torrent")))

    def test_looks_like_url(self):
        try:
            from draco.gui.util import looks_like_url
        except (ImportError, ValueError):
            self.skipTest("GTK 4 is not installed")
        f = self.dir / "x.torrent"
        f.write_bytes(b"x")
        self.assertTrue(looks_like_url("magnet:?xt=urn:btih:" + "a" * 40))
        self.assertFalse(looks_like_url("magnet:?dn=nothing"))
        self.assertTrue(looks_like_url(str(f)))
        self.assertFalse(looks_like_url(str(self.dir / "nope.torrent")))
        self.assertFalse(looks_like_url("https://a.org/x\nhttps://b.org/y"))

    def test_fetch_metadata_from_local_file_is_cached(self):
        root = self.dir / "one.bin"
        root.write_bytes(os.urandom(1000))
        src = self.dir / "one.torrent"
        src.write_bytes(make_torrent(root, single=True))
        item = {"url": str(src)}
        path, info = torrent.fetch_metadata(item, Settings(self.dir / "s.json"))
        self.assertEqual(path.parent, torrent.TORRENT_DIR)
        self.assertEqual(item["info_hash"], info["info_hash"])
        src.unlink()                                  # the kept copy is used from now on
        self.assertEqual(torrent.fetch_metadata(item, None)[1]["name"], "one.bin")

    def test_delete_data_keeps_other_files(self):
        root = self.dir / "dl" / "Pack"
        (root / "sub").mkdir(parents=True)
        (root / "a.bin").write_bytes(b"a" * 100)
        (root / "sub" / "b.bin").write_bytes(b"b" * 100)
        path, info = torrent.save_torrent(make_torrent(root))
        (root / "mine.txt").write_bytes(b"not from the torrent")
        (self.dir / "dl" / "Pack.aria2").write_bytes(b"ctl")
        item = {"torrent_file": str(path), "save_dir": str(self.dir / "dl"), "filename": "Pack"}
        torrent.delete_data(item)
        self.assertFalse((root / "a.bin").exists())
        self.assertFalse((root / "sub").exists())
        self.assertFalse((self.dir / "dl" / "Pack.aria2").exists())
        self.assertTrue((root / "mine.txt").exists())

    def test_command_options(self):
        root = self.dir / "Pack"
        root.mkdir()
        for n in "abc":
            (root / f"{n}.bin").write_bytes(n.encode() * 10)
        path, info = torrent.save_torrent(make_torrent(root))
        s = Settings(self.dir / "s.json")
        s["torrent_seed"], s["torrent_seed_minutes"], s["torrent_port"] = True, 0, "6881-6889"
        item = {"save_dir": str(self.dir / "out"), "filename": "Renamed", "torrent_select": [1, 3]}
        task = TorrentTask(item, s, RateLimiter(0))
        cmd = task._command(path, info)[1:]          # [0] is aria2c (None when it isn't installed)
        self.assertIn("--select-file=1,3", cmd)
        self.assertIn("--index-out=1=Renamed/a.bin", cmd)
        self.assertIn("--index-out=3=Renamed/c.bin", cmd)
        self.assertIn("--index-out=2=Renamed/b.bin", cmd)     # not chosen, but its edge pieces land there
        self.assertIn("--seed-ratio=1.0", cmd)
        self.assertFalse(any(c.startswith("--seed-time") for c in cmd))   # 0 minutes = no time limit
        self.assertFalse(any(c.startswith("--listen-port") for c in cmd))   # no port held yet
        self.assertIn("--bt-tracker=" + ",".join(torrent.PUBLIC_TRACKERS), cmd)
        s["torrent_upnp"] = False
        task.peer = torrent.PeerPort(s)
        try:
            cmd = task._command(path, info)
            self.assertTrue(6881 <= task.peer.port <= 6889)
            self.assertIn(f"--listen-port={task.peer.port}", cmd)
            self.assertIn(f"--dht-listen-port={task.peer.port}", cmd)
            other = torrent.PeerPort(s)              # a second torrent at the same time gets another port
            self.assertNotEqual(other.port, task.peer.port)
            other.close()
            self.assertFalse(any(c.startswith("--bt-tracker") for c in task._command(path, dict(info, private=True))))
        finally:
            task.peer.close()
        s["torrent_seed"] = False
        self.assertIn("--seed-time=0", task._command(path, info))


# ---------------------------------------------------------------- real downloads (needs aria2c)
class Tracker(http.server.BaseHTTPRequestHandler):
    peers = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query, encoding="latin-1")
        ih = q.get("info_hash", [""])[0].encode("latin-1")
        port = int(q.get("port", ["0"])[0])
        swarm = Tracker.peers.setdefault(ih, set())
        if q.get("event", [""])[0] == "stopped":
            swarm.discard(port)
        elif port:
            swarm.add(port)
        compact = b"".join(socket.inet_aton("127.0.0.1") + p.to_bytes(2, "big") for p in swarm if p != port)
        body = bencode({"interval": 2, "min interval": 1, "peers": compact})
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

    def test_peer_rows(self):
        rows = torrent.peer_rows([
            {"ip": "10.0.0.2", "port": "6881", "downloadSpeed": "100", "uploadSpeed": "0", "bitfield": "f0",
             "seeder": "false", "peerChoking": "false"},
            {"ip": "::1", "port": "51413", "downloadSpeed": "900", "uploadSpeed": "5", "bitfield": "ff",
             "seeder": "true", "peerChoking": "true"},
            {"ip": "bad", "port": "1", "downloadSpeed": "x"}], num_pieces=8)
        self.assertEqual([r["addr"] for r in rows], ["[::1]:51413", "10.0.0.2:6881"])   # fastest first
        self.assertEqual(rows[1]["have"], 0.5)
        self.assertTrue(rows[0]["seeder"])
        self.assertEqual(rows[0]["have"], 1.0)


@unittest.skipUnless(shutil.which("aria2c"), "aria2c is not installed")
class TorrentDownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self._old = torrent.TORRENT_DIR, torrent.ARIA2
        torrent.TORRENT_DIR, torrent.ARIA2 = self.dir / "store", shutil.which("aria2c")
        Tracker.peers = {}
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Tracker)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.tracker = f"http://127.0.0.1:{self.httpd.server_address[1]}/announce"
        # what the seeder shares: a folder with three files
        self.src = self.dir / "seed" / "Pack"
        (self.src / "sub").mkdir(parents=True)
        for name, n in (("a.bin", 700_000), ("sub/b.bin", 1_300_000), ("c.txt", 900)):
            (self.src / name).write_bytes(os.urandom(n))
        self.data = make_torrent(self.src, self.tracker)
        self.tfile = self.dir / "Pack.torrent"
        self.tfile.write_bytes(self.data)
        self.seeder = None
        self.settings = Settings(self.dir / "settings.json")
        self.settings["torrent_seed"] = False
        self.settings["torrent_upnp"] = False             # never touch the real router from tests
        self.settings["torrent_public_trackers"] = False  # and stay off the internet

    def tearDown(self):
        if self.seeder and self.seeder.poll() is None:
            self.seeder.terminate()
            self.seeder.wait(10)
        self.httpd.shutdown()
        torrent.TORRENT_DIR, torrent.ARIA2 = self._old
        self.tmp.cleanup()

    def seed(self, upload_kbps=0):
        cmd = [torrent.ARIA2, "--console-log-level=error", "--summary-interval=0", "--enable-dht=false",
               "--bt-enable-lpd=false", "--check-integrity=true", "--seed-ratio=0.0",
               f"--listen-port={_port()}", f"--dir={self.src.parent}", str(self.tfile)]
        if upload_kbps:
            cmd.insert(1, f"--max-upload-limit={upload_kbps}K")
        self.seeder = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def item(self, url, **kw):
        it = {"id": "t1", "kind": "torrent", "url": url, "save_dir": str(self.dir / "out"),
              "filename": "", "size": -1}
        it.update(kw)
        return it

    def run_task(self, it, until=None, timeout=90):
        done, seen = threading.Event(), []
        task = TorrentTask(it, self.settings, RateLimiter(0),
                           on_update=lambda i: seen.append(i.get("status")),
                           on_finish=lambda i, ok: done.set())
        task.on_downloaded = lambda i: seen.append("downloaded")
        task.start()
        if until:
            end = time.monotonic() + timeout
            while not until(it, seen) and time.monotonic() < end and not done.is_set():
                time.sleep(0.2)
            task.stop()
        self.assertTrue(done.wait(timeout), f"torrent timed out; status {it.get('status')} {it.get('error')}")
        return task, seen

    def same(self, rel, root="Pack"):
        return (self.dir / "out" / root / rel).read_bytes() == (self.src / rel).read_bytes()

    def test_download_all_files(self):
        self.seed()
        it = self.item(str(self.tfile))
        _task, seen = self.run_task(it)
        self.assertEqual(it["status"], "complete", it.get("error"))
        self.assertEqual(it["filename"], "Pack")
        self.assertEqual(it["size"], 700_000 + 1_300_000 + 900)
        for rel in ("a.bin", "sub/b.bin", "c.txt"):
            self.assertTrue(self.same(rel), rel)
        self.assertIn("downloaded", seen)
        self.assertFalse((self.dir / "out" / "Pack.aria2").exists())

    def test_some_files_renamed_folder(self):
        self.seed()
        info = torrent.parse_torrent(self.data)
        want = [i + 1 for i, f in enumerate(info["files"]) if f["path"].endswith("c.txt")]
        it = self.item(str(self.tfile), torrent_select=want, torrent_rename="My pack")
        self.run_task(it)
        self.assertEqual(it["status"], "complete", it.get("error"))
        self.assertEqual(it["filename"], "My pack")
        self.assertEqual(it["size"], 900)
        self.assertTrue(self.same("c.txt", "My pack"))
        self.assertFalse((self.dir / "out" / "Pack").exists())

    def test_pause_and_resume(self):
        self.seed(upload_kbps=250)
        it = self.item(str(self.tfile))
        self.run_task(it, until=lambda i, s: i.get("downloaded", 0) > 200_000)
        self.assertEqual(it["status"], "paused", it.get("error"))
        self.assertLess(it["downloaded"], it["size"])
        self.assertTrue((self.dir / "out" / "Pack.aria2").exists())   # aria2 saved where it was
        self.seeder.terminate()
        self.seeder.wait(10)
        self.seed()
        it.pop("finished", None)
        self.run_task(it)
        self.assertEqual(it["status"], "complete", it.get("error"))
        for rel in ("a.bin", "sub/b.bin", "c.txt"):
            self.assertTrue(self.same(rel), rel)

    def test_seeding_then_stop_counts_as_complete(self):
        self.seed()
        self.settings["torrent_seed"] = True
        it = self.item(str(self.tfile))
        _task, seen = self.run_task(it, until=lambda i, s: "seeding" in s)
        self.assertIn("seeding", seen)
        self.assertEqual(seen.count("downloaded"), 1)
        self.assertLess(seen.index("downloaded"), len(seen))
        self.assertEqual(it["status"], "complete", it.get("error"))
        self.assertTrue(self.same("sub/b.bin"))

    def test_magnet_link(self):
        self.seed()
        ih = info_hash(self.data)
        magnet = f"magnet:?xt=urn:btih:{ih}&dn=Pack&tr={urllib.parse.quote(self.tracker, safe='')}"
        it = self.item(magnet)
        self.run_task(it)
        self.assertEqual(it["status"], "complete", it.get("error"))
        self.assertEqual(it["info_hash"], ih)
        self.assertIn("peers", it)
        self.assertTrue((torrent.TORRENT_DIR / f"{ih}.torrent").is_file())
        self.assertTrue(self.same("sub/b.bin"))
        self.assertEqual(list(torrent.TORRENT_DIR.glob(".meta-*")), [])

    def test_manager_seeding_then_remove(self):
        from draco.manager import Manager
        self.seed()
        self.settings["torrent_seed"] = True
        self.settings["download_dir"] = str(self.dir / "out")
        m = Manager(self.settings, store=self.dir / "downloads.json")
        events = []
        m.listeners.append(lambda ev, it: events.append((ev, it.get("status") if isinstance(it, dict) else None)))
        it = m.new_item(str(self.tfile))
        self.assertEqual(it["kind"], "torrent")
        it["save_dir"] = str(self.dir / "out")
        m.add(it, start=True)
        end = time.monotonic() + 90
        while ("finished", "seeding") not in events and time.monotonic() < end:
            time.sleep(0.2)
        self.assertIn(("finished", "seeding"), events)          # announced once, while it seeds
        self.assertTrue(self.same("sub/b.bin", it["filename"]))
        m.remove([it["id"]])                                    # finished: the files stay
        self.assertTrue(self.same("sub/b.bin", it["filename"]))
        self.assertEqual([e for e in events if e[0] == "finished"], [("finished", "seeding")])

    def test_manager_cancel_deletes_partial_data(self):
        from draco.manager import Manager
        self.seed(upload_kbps=200)
        m = Manager(self.settings, store=self.dir / "downloads.json")
        it = m.new_item(str(self.tfile))
        it["save_dir"] = str(self.dir / "out")
        m.add(it, start=True)
        end = time.monotonic() + 60
        while it.get("downloaded", 0) < 100_000 and time.monotonic() < end:
            time.sleep(0.2)
        self.assertGreater(it.get("downloaded", 0), 0)
        m.remove([it["id"]])
        self.assertFalse((self.dir / "out" / "Pack").exists())
        self.assertFalse((self.dir / "out" / "Pack.aria2").exists())


if __name__ == "__main__":
    unittest.main()
