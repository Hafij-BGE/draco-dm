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

ALLOWED = {"ping", "add", "links", "show", "grab"}
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


def read_msg():
    raw = sys.stdin.buffer.read(4)
    if len(raw) < 4:
        return None
    n = struct.unpack("<I", raw)[0]
    if n > 64 * 1024 * 1024:
        return None
    return json.loads(sys.stdin.buffer.read(n).decode("utf-8"))


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


def ensure_running():
    try:
        return forward({"cmd": "ping"})
    except (OSError, KeyError, ValueError):
        pass
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
        msg = read_msg()
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
