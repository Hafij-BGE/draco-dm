"""Loopback HTTP bridge for sandboxed (snap/flatpak) browsers that can't use native messaging.

Security model:
  * Listens on 127.0.0.1 only; the Host header must be a loopback name (blocks DNS rebinding).
  * Every request except GET /ping must carry an extension Origin
    (chrome-extension://<Draco's ID> or moz-extension://...). Web pages cannot fake Origin.
  * An extension pairs once: POST /pair asks the user in Draco's window; on approval it gets a
    random token. Every later message needs that token (X-Draco-Token header).
  * Only the same small set of commands as the native host is accepted.
"""

import hmac
import http.server
import json
import secrets
import threading

PORTS = range(47823, 47828)
ALLOWED = {"ping", "add", "links", "show", "grab"}
FIELDS = {"cmd", "url", "urls", "referer", "cookies", "filename", "size", "user_agent", "kind",
          "content_type", "title", "description", "headers", "silent", "quality", "subs", "sub_lang"}
MAX_BODY = 8 * 1024 * 1024
LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}


class Bridge:
    def __init__(self, settings, dispatch, ask_pair, chrome_id, version):
        """dispatch(msg) -> dict; ask_pair(origin) -> bool (blocks until the user decides)."""
        self.settings = settings
        self.dispatch = dispatch
        self.ask_pair = ask_pair
        self.chrome_origin = f"chrome-extension://{chrome_id}"
        self.version = version
        self.server = None
        self.port = None
        self._pair_lock = threading.Lock()

    # -- origin / token checks -------------------------------------------
    def origin_ok(self, origin):
        return bool(origin) and (origin == self.chrome_origin or origin.startswith("moz-extension://"))

    def token_ok(self, token):
        if not token:
            return False
        return any(hmac.compare_digest(token, t) for t in self.settings.get("bridge_tokens", []))

    def new_token(self):
        tok = secrets.token_urlsafe(32)
        toks = list(self.settings.get("bridge_tokens", []))[-9:] + [tok]
        self.settings["bridge_tokens"] = toks
        self.settings.save()
        return tok

    # -- server -----------------------------------------------------------
    def start(self):
        bridge = self

        class Handler(http.server.BaseHTTPRequestHandler):
            server_version = "Draco"
            sys_version = ""

            def log_message(self, *a):
                pass

            def _host_ok(self):
                host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
                return host in LOOPBACK_HOSTS

            def _send(self, code, obj, origin=None):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                if origin and bridge.origin_ok(origin):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > MAX_BODY:
                    return None
                try:
                    return json.loads(self.rfile.read(n))
                except ValueError:
                    return None

            def do_OPTIONS(self):
                origin = self.headers.get("Origin")
                if not self._host_ok() or not bridge.origin_ok(origin):
                    self._send(403, {"ok": False})
                    return
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "GET, POST")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Draco-Token")
                self.send_header("Access-Control-Max-Age", "600")
                self.end_headers()

            def do_GET(self):
                origin = self.headers.get("Origin")
                if not self._host_ok() or self.path != "/ping" or (origin and not bridge.origin_ok(origin)):
                    self._send(403, {"ok": False})
                    return
                self._send(200, {"ok": True, "app": "draco", "version": bridge.version,
                                 "paired": bridge.token_ok(self.headers.get("X-Draco-Token"))}, origin)

            def do_POST(self):
                origin = self.headers.get("Origin")
                if not self._host_ok() or not bridge.origin_ok(origin):
                    self._send(403, {"ok": False, "error": "forbidden"})
                    return
                if self.path == "/pair":
                    with bridge._pair_lock:  # one approval dialog at a time
                        if bridge.ask_pair(origin):
                            self._send(200, {"ok": True, "token": bridge.new_token()}, origin)
                        else:
                            self._send(403, {"ok": False, "error": "pairing declined"}, origin)
                    return
                if self.path != "/msg":
                    self._send(404, {"ok": False}, origin)
                    return
                if not bridge.token_ok(self.headers.get("X-Draco-Token")):
                    self._send(401, {"ok": False, "error": "not paired"}, origin)
                    return
                msg = self._body()
                if not isinstance(msg, dict) or msg.get("cmd") not in ALLOWED:
                    self._send(400, {"ok": False, "error": "unsupported command"}, origin)
                    return
                clean = {k: v for k, v in msg.items() if k in FIELDS}
                clean["source"] = "browser"
                self._send(200, bridge.dispatch(clean), origin)

        for port in PORTS:
            try:
                self.server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
                self.server.daemon_threads = True
                self.port = port
                break
            except OSError:
                continue
        if self.server:
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self.port

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
