"""Exercise the code paths Windows uses, on Linux:
TCP+token IPC, seek+write instead of os.pwrite, and the native host talking over TCP."""

import hashlib
import importlib
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TcpIpcTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DRACO_IPC"] = "tcp"
        import draco.ipc
        self.ipc = importlib.reload(draco.ipc)
        self.sock = Path(self.tmp.name) / "draco.sock"
        self.got = []
        self.server = self.ipc.IpcServer(lambda m: (self.got.append(m), {"ok": True, "echo": m.get("cmd")})[1],
                                         self.sock)
        self.server.start()

    def tearDown(self):
        self.server.stop()
        os.environ.pop("DRACO_IPC", None)
        import draco.ipc
        importlib.reload(draco.ipc)
        self.tmp.cleanup()

    def test_roundtrip_with_token(self):
        self.assertTrue(self.ipc.ping(self.sock))
        r = self.ipc.send({"cmd": "add", "url": "http://x"}, self.sock)
        self.assertEqual(r["echo"], "add")
        self.assertNotIn("_token", self.got[-1])   # token is stripped before dispatch

    def test_wrong_token_rejected(self):
        info = json.loads((Path(self.tmp.name) / "ipc.json").read_text())
        s = socket.create_connection(("127.0.0.1", info["port"]), timeout=5)
        s.sendall(b'{"cmd": "add", "url": "http://evil", "_token": "nope"}\n')
        self.assertEqual(s.recv(100), b"")   # closed without an answer
        s.close()
        self.assertFalse(any(m.get("url") == "http://evil" for m in self.got))

    def test_info_file_private(self):
        mode = (Path(self.tmp.name) / "ipc.json").stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_native_host_over_tcp(self):
        host = ROOT / "native_host" / "draco_host.py"
        env = dict(os.environ, DRACO_IPC="tcp", XDG_RUNTIME_DIR=self.tmp.name, DRACO_LAUNCH='["/bin/false"]')
        frames = b""
        for m in ({"cmd": "ping"}, {"cmd": "add", "url": "https://example.com/a.zip", "evil": 1}):
            d = json.dumps(m).encode()
            frames += struct.pack("<I", len(d)) + d
        out = subprocess.run([sys.executable, str(host)], input=frames, capture_output=True, env=env, timeout=20).stdout
        replies = []
        while out:
            n = struct.unpack("<I", out[:4])[0]
            replies.append(json.loads(out[4:4 + n]))
            out = out[4 + n:]
        self.assertTrue(all(r.get("ok") for r in replies), replies)
        added = [m for m in self.got if m.get("cmd") == "add"]
        self.assertEqual(added[-1]["url"], "https://example.com/a.zip")
        self.assertNotIn("evil", added[-1])


class NoPwriteTest(unittest.TestCase):
    """Download with the Windows write path (no os.pwrite)."""

    def test_multi_connection_without_pwrite(self):
        from tests.test_engine import EngineTest, PAYLOAD
        import draco.engine as engine
        saved = engine._pwrite
        engine._pwrite = None
        try:
            t = EngineTest("test_multi_connection")
            EngineTest.setUpClass()
            try:
                t.setUp()
                it = t.item("/file")
                t.run_task(it)
                self.assertEqual(it["status"], "complete", it.get("error"))
                got = (Path(t.tmp.name) / it["filename"]).read_bytes()
                self.assertEqual(hashlib.sha256(got).hexdigest(), hashlib.sha256(PAYLOAD).hexdigest())
                t.tearDown()
            finally:
                EngineTest.tearDownClass()
        finally:
            engine._pwrite = saved


if __name__ == "__main__":
    unittest.main()
