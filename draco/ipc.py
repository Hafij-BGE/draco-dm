"""Local IPC: single-instance handoff (second `draco URL` call), the CLI, and the browser
native-messaging host. One JSON object per line in each direction.

Linux: a per-user Unix socket (mode 0600) and the peer's uid is checked.
Windows: a 127.0.0.1 TCP port with a random secret token; port and token are written to
         %LOCALAPPDATA%\\Draco\\run\\ipc.json, which only the user can read. Every request
         must carry the token. (Set DRACO_IPC=tcp to use this mode on Linux for testing.)
"""

import hmac
import json
import os
import secrets
import socket
import socketserver
import threading
from pathlib import Path

from .config import SOCKET_PATH

MAX_MSG = 16 * 1024 * 1024
USE_TCP = os.name == "nt" or os.environ.get("DRACO_IPC") == "tcp" or not hasattr(socket, "AF_UNIX")


def _info_path(path):
    return Path(path).with_name("ipc.json")


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        if not USE_TCP:
            # Unix socket: only accept connections from the same user.
            try:
                creds = self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
                if int.from_bytes(creds[4:8], "little") != os.getuid():
                    return
            except OSError:
                return
        line = self.rfile.readline(MAX_MSG)
        try:
            msg = json.loads(line)
            if USE_TCP:
                token = msg.pop("_token", "") if isinstance(msg, dict) else ""
                if not hmac.compare_digest(str(token), self.server.token):
                    return  # wrong or missing token: say nothing
            reply = self.server.dispatch(msg)
        except Exception as e:
            reply = {"ok": False, "error": str(e)}
        self.wfile.write((json.dumps(reply) + "\n").encode())


if hasattr(socketserver, "UnixStreamServer"):
    class _UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
        daemon_threads = True
        allow_reuse_address = True


class _TcpServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = False


class IpcServer:
    def __init__(self, dispatch, path=SOCKET_PATH):
        self.path = str(path)
        self.dispatch = dispatch
        self.server = None

    def start(self):
        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        if ping(self.path):
            raise RuntimeError("another instance is running")
        if USE_TCP:
            self.server = _TcpServer(("127.0.0.1", 0), _Handler)
            self.server.token = secrets.token_urlsafe(32)
            info = _info_path(self.path)
            fd = os.open(info, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as fh:
                json.dump({"port": self.server.server_address[1], "token": self.server.token}, fh)
        else:
            if os.path.exists(self.path):
                os.unlink(self.path)
            old = os.umask(0o177)
            try:
                self.server = _UnixServer(self.path, _Handler)
            finally:
                os.umask(old)
        self.server.dispatch = self.dispatch
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            for p in (_info_path(self.path) if USE_TCP else Path(self.path),):
                try:
                    os.unlink(p)
                except OSError:
                    pass


def send(msg, path=SOCKET_PATH, timeout=10):
    if USE_TCP:
        info = json.loads(_info_path(path).read_text())   # OSError if Draco isn't running
        msg = dict(msg, _token=info["token"])
        s = socket.create_connection(("127.0.0.1", int(info["port"])), timeout=timeout)
    else:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(str(path))
    with s:
        s.sendall((json.dumps(msg) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf or b"{}")


def ping(path=SOCKET_PATH):
    try:
        return send({"cmd": "ping"}, path, timeout=2).get("ok", False)
    except (OSError, ValueError, KeyError):
        return False
