#!/usr/bin/env python3
"""Native-messaging host: forwards browser-extension messages to the running Draco app.

Browsers start this script themselves (stdio, 4-byte length-prefixed JSON).
Only a fixed set of commands is forwarded. If Draco isn't running, it is started.
"""

import json
import os
import socket
import struct
import subprocess
import sys
import time

ALLOWED = {"ping", "add", "links", "show", "grab", "cookies", "wanted_cookies"}
FIELDS = {"cmd", "url", "urls", "referer", "cookies", "filename", "size", "user_agent", "kind",
          "content_type", "title", "description", "headers", "silent", "quality", "subs", "sub_lang", "verify"}
LAUNCH = os.environ.get("DRACO_LAUNCH") or "@LAUNCH@"   # JSON list (or a plain path) filled in at install
IS_WIN = os.name == "nt"
if LAUNCH == "@LAUNCH@" and getattr(sys, "frozen", False):
    # Built Windows app: draco-host.exe sits next to Draco.exe
    LAUNCH = json.dumps([os.path.join(os.path.dirname(sys.executable), "Draco.exe")])
USE_TCP = IS_WIN or os.environ.get("DRACO_IPC") == "tcp"

if IS_WIN:  # native messaging is a binary protocol: no CRLF translation
    import msvcrt
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)


def runtime_dir():
    if IS_WIN:
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local"), "Draco", "run")
    return os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/draco-{os.getuid()}"


def socket_path():
    return os.path.join(runtime_dir(), "draco.sock")


def launch_cmd():
    if LAUNCH.startswith("["):
        return json.loads(LAUNCH)
    import shlex
    return shlex.split(LAUNCH)


MAX_MSG = 64 * 1024 * 1024   # sanity cap (browsers send at most a few MB to a host)


class BadMessage(Exception):
    """A frame that isn't a usable JSON message. `fatal`: the stream can't be resynced."""

    def __init__(self, error, fatal=False):
        super().__init__(error)
        self.fatal = fatal


def read_msg(stream=None):
    stream = stream or sys.stdin.buffer
    raw = stream.read(4)
    if len(raw) < 4:
        return None
    n = struct.unpack("<I", raw)[0]
    if n > MAX_MSG:
        raise BadMessage("message too large", fatal=True)
    body = stream.read(n)
    if len(body) < n:
        raise BadMessage("truncated message", fatal=True)
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise BadMessage("invalid JSON message") from None


def write_msg(obj):
    data = json.dumps(obj).encode()
    sys.stdout.buffer.write(struct.pack("<I", len(data)) + data)
    sys.stdout.buffer.flush()


def forward(msg):
    if USE_TCP:
        with open(os.path.join(runtime_dir(), "ipc.json")) as fh:   # OSError if Draco isn't running
            info = json.load(fh)
        msg = dict(msg, _token=info["token"])
        s = socket.create_connection(("127.0.0.1", int(info["port"])), timeout=30)
    else:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(30)
        s.connect(socket_path())
    with s:
        s.sendall((json.dumps(msg) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf or b"{}")


class win_launch_lock:
    """Windows: only one helper at a time may start Draco. The browser runs a helper per message,
    so when it hands over several downloads at once each would otherwise start its own copy."""

    def __enter__(self):
        os.makedirs(runtime_dir(), exist_ok=True)
        self.fh = open(os.path.join(runtime_dir(), "launch.lock"), "a+")
        for _ in range(3):   # LK_LOCK gives up after about 10 s
            try:
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_LOCK, 1)
                break
            except OSError:
                continue
        return self

    def __exit__(self, *exc):
        try:
            self.fh.seek(0)
            msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self.fh.close()


def ensure_running():
    try:
        return forward({"cmd": "ping"})
    except (OSError, KeyError, ValueError):
        pass
    if not IS_WIN:
        return launch()
    with win_launch_lock():
        try:   # another helper may have started it while this one waited
            return forward({"cmd": "ping"})
        except (OSError, KeyError, ValueError):
            pass
        return launch()


def launch():
    cmd = launch_cmd() + ["--background"]
    if IS_WIN:
        flags = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags, close_fds=True)
    else:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    for _ in range(40):
        time.sleep(0.25)
        try:
            return forward({"cmd": "ping"})
        except (OSError, KeyError, ValueError):
            continue
    raise OSError("Draco did not start")


def main():
    while True:
        try:
            msg = read_msg()
        except BadMessage as e:   # reply instead of dying silently; keep reading unless out of sync
            write_msg({"ok": False, "error": str(e)})
            if e.fatal:
                return
            continue
        if msg is None:
            return
        try:
            if not isinstance(msg, dict) or msg.get("cmd") not in ALLOWED:
                write_msg({"ok": False, "error": "unsupported command"})
                continue
            clean = {k: v for k, v in msg.items() if k in FIELDS}
            clean["source"] = "browser"
            info = ensure_running()
            reply = info if clean["cmd"] == "ping" else forward(clean)
            write_msg(reply)
        except Exception as e:  # report to the extension instead of crashing
            write_msg({"ok": False, "error": str(e)})


if __name__ == "__main__":
    main()
