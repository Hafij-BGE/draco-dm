"""Loopback bridge tests: origin/host checks, pairing, token, command filter."""

import http.client
import json
import tempfile
import unittest
from pathlib import Path

from draco.bridge import Bridge
from draco.config import Settings

EXT = "chrome-extension://majhnibnfcmhjemhkkddkojdbpedmmep"


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.tmp.name) / "s.json")
        self.got = []
        self.approve = True
        self.bridge = Bridge(self.settings, lambda m: (self.got.append(m), {"ok": True})[1],
                             lambda origin: self.approve, "majhnibnfcmhjemhkkddkojdbpedmmep", "9.9")
        self.port = self.bridge.start()
        self.assertIsNotNone(self.port)

    def tearDown(self):
        self.bridge.stop()
        self.tmp.cleanup()

    def req(self, method, path, body=None, origin=EXT, token=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Content-Type": "application/json"}
        if origin:
            h["Origin"] = origin
        if token:
            h["X-Draco-Token"] = token
        if host:
            h["Host"] = host
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, (json.loads(data) if data else {})

    def pair(self):
        st, j = self.req("POST", "/pair", {})
        self.assertEqual(st, 200)
        return j["token"]

    def test_ping(self):
        st, j = self.req("GET", "/ping", origin=None)
        self.assertEqual((st, j["app"]), (200, "draco"))

    def test_web_page_rejected(self):
        self.assertEqual(self.req("GET", "/ping", origin="https://evil.example")[0], 403)
        self.assertEqual(self.req("POST", "/pair", {}, origin="https://evil.example")[0], 403)
        self.assertEqual(self.req("POST", "/msg", {"cmd": "add", "url": "http://x"}, origin=None)[0], 403)

    def test_dns_rebinding_rejected(self):
        self.assertEqual(self.req("GET", "/ping", origin=None, host="evil.example:47823")[0], 403)

    def test_needs_token(self):
        self.assertEqual(self.req("POST", "/msg", {"cmd": "add", "url": "http://x"})[0], 401)
        self.assertEqual(self.req("POST", "/msg", {"cmd": "add", "url": "http://x"}, token="wrong")[0], 401)
        self.assertEqual(self.got, [])

    def test_pair_and_send(self):
        tok = self.pair()
        st, j = self.req("POST", "/msg", {"cmd": "add", "url": "http://x/a.zip", "evil": 1}, token=tok)
        self.assertEqual((st, j["ok"]), (200, True))
        self.assertEqual(self.got[0]["url"], "http://x/a.zip")
        self.assertNotIn("evil", self.got[0])
        self.assertEqual(self.got[0]["source"], "browser")

    def test_declined(self):
        self.approve = False
        self.assertEqual(self.req("POST", "/pair", {})[0], 403)

    def test_bad_command(self):
        tok = self.pair()
        self.assertEqual(self.req("POST", "/msg", {"cmd": "quit"}, token=tok)[0], 400)

    def test_firefox_origin(self):
        st, j = self.req("POST", "/pair", {}, origin="moz-extension://1234-abcd")
        self.assertEqual(st, 200)


if __name__ == "__main__":
    unittest.main()
