"""Engine tests against a local HTTP server. Run: python3 -m unittest discover tests"""

import hashlib
import http.server
import os
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path

from draco.config import Settings
from draco.engine import HttpTask, RateLimiter, probe
from draco.batch import expand_pattern

PAYLOAD = os.urandom(5 * 1024 * 1024 + 123)


class RangeHandler(http.server.BaseHTTPRequestHandler):
    support_range = True
    throttle = 0
    valid_cookie = "s=v1"   # /login-file: other cookies are sent to a sign-in page

    def log_message(self, *a):
        pass

    def do_GET(self):
        data = PAYLOAD
        if self.path.startswith("/accounts/signin"):
            page = b"<!doctype html><html><body>Sign in</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        if self.path.startswith("/login-file") and self.headers.get("Cookie") != RangeHandler.valid_cookie:
            self.send_response(302)
            self.send_header("Location", "/accounts/signin?continue=/login-file")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path.startswith("/norange"):
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.startswith("/nolength"):
            self.send_response(200)
            self.send_header("Content-Disposition", 'attachment; filename="stream.bin"')
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True
            return
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d+)-(\d*)", rng)
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else len(data) - 1
            end = min(end, len(data) - 1)
            body = data[start:end + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
        else:
            body = data
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''t%C3%A9st%20file.bin")
        self.end_headers()
        step = 32 * 1024
        for i in range(0, len(body), step):
            try:
                self.wfile.write(body[i:i + step])
            except (BrokenPipeError, ConnectionResetError):
                return
            if self.throttle:
                time.sleep(self.throttle)


class EngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.tmp.name) / "settings.json")
        self.settings["min_split_kb"] = 256
        self.settings["retries"] = 2
        RangeHandler.throttle = 0

    def tearDown(self):
        self.tmp.cleanup()

    def item(self, path, **kw):
        it = {"id": "t1", "url": self.base + path, "save_dir": self.tmp.name, "filename": "",
              "size": -1, "connections": 8}
        it.update(kw)
        return it

    def run_task(self, it, stop_after=None):
        done = threading.Event()
        task = HttpTask(it, self.settings, RateLimiter(0), on_finish=lambda i, ok: done.set())
        task.start()
        if stop_after:
            time.sleep(stop_after)
            task.stop()
        self.assertTrue(done.wait(30), "download timed out")
        return task

    def sha(self, path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def test_probe(self):
        info = probe(self.item("/file"), self.settings)
        self.assertEqual(info["size"], len(PAYLOAD))
        self.assertTrue(info["resumable"])
        self.assertEqual(info["filename"], "tést file.bin")

    def test_multi_connection(self):
        it = self.item("/file")
        self.run_task(it)
        self.assertEqual(it["status"], "complete", it.get("error"))
        self.assertGreater(len(it["segments"]), 1)
        self.assertEqual(self.sha(Path(self.tmp.name) / it["filename"]), hashlib.sha256(PAYLOAD).hexdigest())

    def test_renewed_login_cookies_continue_the_download(self):
        """The site renews its login mid-download (new requests get a sign-in page); once the
        browser's new cookies arrive, the download carries on and the file is intact."""
        RangeHandler.throttle, RangeHandler.valid_cookie = 0.03, "s=v1"
        self.settings["retries"] = 8
        it = self.item("/login-file", cookies="s=v1")

        def renew():
            time.sleep(0.4)
            RangeHandler.valid_cookie = "s=v2"   # old cookies stop working for new requests
            time.sleep(1.5)
            it["cookies"] = "s=v2"               # what the extension sends to Draco

        threading.Thread(target=renew, daemon=True).start()
        self.run_task(it)
        RangeHandler.throttle, RangeHandler.valid_cookie = 0, "s=v1"
        self.assertEqual(it["status"], "complete", it.get("error"))
        self.assertNotIn("needs_login", it)
        self.assertEqual(self.sha(Path(self.tmp.name) / it["filename"]), hashlib.sha256(PAYLOAD).hexdigest())

    def test_sign_in_page_never_replaces_downloaded_data(self):
        RangeHandler.valid_cookie = "s=v2"
        it = self.item("/login-file", cookies="s=old", size=len(PAYLOAD), resumable=True, filename="y.bin",
                       segments=[{"s": 0, "p": 1000, "e": len(PAYLOAD)}])   # not probed yet
        self.run_task(it)
        RangeHandler.valid_cookie = "s=v1"
        self.assertEqual(it["status"], "error")
        self.assertTrue(it.get("needs_login"))
        self.assertFalse(Path(self.tmp.name, "y.bin").exists())

    def test_sign_in_page_is_reported_clearly(self):
        RangeHandler.valid_cookie = "s=v2"
        self.settings["retries"] = 0
        it = self.item("/login-file", cookies="s=old", size=len(PAYLOAD), resumable=True, filename="x.bin",
                       segments=[{"s": 0, "p": 1000, "e": len(PAYLOAD)}], probed=True)
        Path(self.tmp.name, "x.bin" + self.settings["temp_suffix"]).write_bytes(PAYLOAD[:1000])
        self.run_task(it)
        RangeHandler.valid_cookie = "s=v1"
        self.assertEqual(it["status"], "error")
        self.assertIn("sign in again", it["error"])
        self.assertTrue(it.get("needs_login"))

    def test_pause_resume(self):
        RangeHandler.throttle = 0.05
        it = self.item("/file")
        self.run_task(it, stop_after=0.5)
        self.assertEqual(it["status"], "paused")
        self.assertGreater(it["downloaded"], 0)
        self.assertLess(it["downloaded"], len(PAYLOAD))
        RangeHandler.throttle = 0
        self.run_task(it)
        self.assertEqual(it["status"], "complete", it.get("error"))
        self.assertEqual(self.sha(Path(self.tmp.name) / it["filename"]), hashlib.sha256(PAYLOAD).hexdigest())

    def test_no_range_server(self):
        it = self.item("/norange/x.bin")
        self.run_task(it)
        self.assertEqual(it["status"], "complete", it.get("error"))
        self.assertEqual(len(it["segments"]), 1)
        self.assertEqual(self.sha(Path(self.tmp.name) / "x.bin"), hashlib.sha256(PAYLOAD).hexdigest())

    def test_unknown_length(self):
        it = self.item("/nolength")
        self.run_task(it)
        self.assertEqual(it["status"], "complete", it.get("error"))
        self.assertEqual(self.sha(Path(self.tmp.name) / "stream.bin"), hashlib.sha256(PAYLOAD).hexdigest())

    def test_duplicate_renamed(self):
        Path(self.tmp.name, "x.bin").write_text("old")
        it = self.item("/norange/x.bin")
        self.run_task(it)
        self.assertEqual(it["filename"], "x (1).bin")

    def test_404(self):
        self.server.RequestHandlerClass = RangeHandler
        it = self.item("/file", url="http://127.0.0.1:1/nothing")
        self.run_task(it)
        self.assertEqual(it["status"], "error")

    def test_rate_limit(self):
        lim = RateLimiter(1024 * 1024)
        t = time.monotonic()
        for _ in range(16):
            lim.consume(128 * 1024)
        self.assertGreater(time.monotonic() - t, 0.9)


class BatchTest(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(expand_pattern("http://x/a[1-3].jpg"), ["http://x/a1.jpg", "http://x/a2.jpg", "http://x/a3.jpg"])

    def test_padding_and_letters(self):
        out = expand_pattern("http://x/[08-10]/[a-b].zip")
        self.assertEqual(out[0], "http://x/08/a.zip")
        self.assertEqual(len(out), 6)


if __name__ == "__main__":
    unittest.main()
