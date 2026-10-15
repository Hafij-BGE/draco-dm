"""Multi-connection HTTP(S)/FTP download engine.

Design:
  * A probe request (Range: bytes=0-0) discovers size, resumability and filename.
  * The target file is pre-sized and split into segments. Each connection owns
    one segment and writes with os.pwrite at its own offsets.
  * Dynamic segmentation: when a connection finishes its segment it takes over
    the second half of the largest remaining segment, so all connections stay
    busy until the very end.
  * Segment positions are saved in the download record, so a paused/crashed
    download continues from where every connection stopped.
"""

import base64
import email.message
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CHUNK = 64 * 1024
_pwrite = getattr(os, "pwrite", None)   # missing on Windows: fall back to seek + write (under the task lock)


def write_at(fd, data, offset):
    if _pwrite is not None:
        _pwrite(fd, data, offset)
    else:
        os.lseek(fd, offset, os.SEEK_SET)
        os.write(fd, data)


class DownloadError(Exception):
    pass


class RateLimiter:
    """Token bucket shared by any number of threads. rate=0 means unlimited."""

    def __init__(self, rate=0):
        self._lock = threading.Lock()
        self.rate = rate
        self._tokens = 0.0
        self._last = time.monotonic()

    def set_rate(self, rate):
        with self._lock:
            self.rate = max(0, int(rate))
            self._tokens = 0.0
            self._last = time.monotonic()

    def consume(self, n, stop_event=None):
        if self.rate <= 0:
            return
        with self._lock:
            now = time.monotonic()
            self._tokens = min(self.rate, self._tokens + (now - self._last) * self.rate)
            self._last = now
            self._tokens -= n
            wait = -self._tokens / self.rate if self._tokens < 0 else 0
        while wait > 0 and not (stop_event and stop_event.is_set()):
            step = min(wait, 0.2)
            time.sleep(step)
            wait -= step


# ---------------------------------------------------------------------------
# Request helpers
# ---------------------------------------------------------------------------

def build_headers(item, settings):
    headers = {
        "User-Agent": item.get("user_agent") or settings["user_agent"],
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }
    if item.get("referer"):
        headers["Referer"] = item["referer"]
    if item.get("cookies"):
        headers["Cookie"] = item["cookies"]
    for k, v in (item.get("headers") or {}).items():
        headers[k] = v
    login = None
    if item.get("auth_user"):
        login = (item["auth_user"], item.get("auth_password", ""))
    else:
        login = settings.login_for(item["url"])
    if login:
        token = base64.b64encode(f"{login[0]}:{login[1]}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    return headers


def build_opener(settings):
    proxy = (settings["proxy"] or "").strip()
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy, "ftp": proxy}))
    return urllib.request.build_opener(*handlers)


def open_url(opener, url, headers, timeout, byte_range=None):
    h = dict(headers)
    if byte_range is not None:
        start, end = byte_range
        h["Range"] = f"bytes={start}-" if end is None else f"bytes={start}-{end}"
    req = urllib.request.Request(url, headers=h)
    return opener.open(req, timeout=timeout)


_WIN_BAD = str.maketrans({c: "_" for c in '<>:"|?*'} | {chr(i): None for i in range(32)})
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def sanitize_filename(name):
    name = urllib.parse.unquote(name or "").replace("/", "_").replace("\\", "_").replace("\0", "")
    if os.name == "nt":   # characters and names Windows does not allow
        name = name.translate(_WIN_BAD)
        if name.split(".")[0].upper() in _WIN_RESERVED:
            name = "_" + name
    name = name.strip().strip(".") or "download"
    while len(name.encode()) > 200:
        stem, dot, ext = name.rpartition(".")
        name = (stem[:-1] + dot + ext) if stem and len(ext) < 16 else name[:-1]
    return name


def filename_from_response(resp, url):
    cd = resp.headers.get("Content-Disposition")
    if cd:
        msg = email.message.Message()
        msg["content-disposition"] = cd
        fn = msg.get_filename()
        if fn:
            return sanitize_filename(fn)
    path = urllib.parse.urlparse(resp.geturl() or url).path
    base = path.rstrip("/").rsplit("/", 1)[-1]
    if not base:
        base = urllib.parse.urlparse(url).netloc or "download"
    if "." not in base:
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
        ext = {"text/html": ".html", "application/pdf": ".pdf", "application/zip": ".zip",
               "video/mp4": ".mp4", "audio/mpeg": ".mp3", "image/jpeg": ".jpg",
               "image/png": ".png", "application/json": ".json"}.get(ctype, "")
        base += ext
    return sanitize_filename(base)


def probe(item, settings):
    """Return dict(size, resumable, filename, final_url, content_type)."""
    opener = build_opener(settings)
    headers = build_headers(item, settings)
    url = item["url"]
    last_err = None
    for byte_range in ((0, 0), None):
        try:
            resp = open_url(opener, url, headers, settings["timeout"], byte_range)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (416, 400, 405, 501) and byte_range is not None:
                continue
            raise DownloadError(f"HTTP {e.code} {e.reason}") from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise DownloadError(str(getattr(e, "reason", e))) from e
        with resp:
            status = getattr(resp, "status", None) or resp.getcode()
            size, resumable = -1, False
            cr = resp.headers.get("Content-Range")
            if status == 206 and cr:
                m = re.match(r"bytes\s+\d+-\d+/(\d+|\*)", cr)
                if m and m.group(1) != "*":
                    size, resumable = int(m.group(1)), True
            if size < 0:
                cl = resp.headers.get("Content-Length")
                if cl and cl.isdigit() and status == 200:
                    size = int(cl)
            if not url.lower().startswith("http"):
                resumable = False  # urllib's FTP handler ignores Range
            return {
                "size": size,
                "resumable": resumable,
                "filename": filename_from_response(resp, url),
                "final_url": resp.geturl() or url,
                "content_type": (resp.headers.get("Content-Type") or "").split(";")[0].strip(),
            }
    raise DownloadError(str(last_err))


def unique_path(path: Path, reserved=()):
    path = Path(path)
    if not path.exists() and str(path) not in reserved:
        return path
    stem, suffix = path.stem, path.suffix
    if path.name.endswith(".tar" + suffix):
        stem, suffix = path.name[: -len(".tar" + suffix)], ".tar" + suffix
    i = 1
    while True:
        cand = path.with_name(f"{stem} ({i}){suffix}")
        if not cand.exists() and str(cand) not in reserved:
            return cand
        i += 1


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class HttpTask:
    """Runs one download in background threads. Mutates the `item` record."""

    kind = "http"

    def __init__(self, item, settings, global_limiter, on_update=None, on_finish=None):
        self.item = item
        self.settings = settings
        self.global_limiter = global_limiter
        self.limiter = RateLimiter(item.get("speed_limit_kbps", 0) * 1024)
        self.on_update = on_update or (lambda item: None)
        self.on_finish = on_finish or (lambda item, ok: None)
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
        self.thread = None
        self.speed = 0.0
        self.active_connections = 0
        self._fd = None
        self._fatal = None

    # -- public ------------------------------------------------------------
    def start(self):
        self.thread = threading.Thread(target=self._run, name=f"dl-{self.item['id']}", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def join(self, timeout=None):
        if self.thread:
            self.thread.join(timeout)

    def set_speed_limit(self, kbps):
        self.item["speed_limit_kbps"] = kbps
        self.limiter.set_rate(kbps * 1024)

    # -- internals -----------------------------------------------------------
    def _set(self, **kw):
        self.item.update(kw)
        self.on_update(self.item)

    def temp_path(self):
        return Path(self.item["save_dir"]) / (self.item["filename"] + self.settings["temp_suffix"])

    def _prepare_segments(self):
        it = self.item
        size, tmp = it["size"], self.temp_path()
        segs = it.get("segments") or []
        if segs and tmp.exists() and it.get("resumable"):
            return  # resume existing layout
        if size > 0 and it.get("resumable"):
            n = max(1, min(int(it.get("connections") or self.settings["connections"]),
                           size // max(1, self.settings["min_split_kb"] * 1024) or 1))
            step = size // n
            segs = []
            for i in range(n):
                s = i * step
                e = size if i == n - 1 else (i + 1) * step
                segs.append({"s": s, "e": e, "p": s})
        else:
            segs = [{"s": 0, "e": size if size > 0 else -1, "p": 0}]
        it["segments"] = segs
        it["downloaded"] = 0
        if tmp.exists():
            tmp.unlink()

    def _open_file(self):
        tmp = self.temp_path()
        tmp.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(tmp, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
        size = self.item["size"]
        if size > 0 and os.fstat(fd).st_size < size:
            try:
                os.posix_fallocate(fd, 0, size)
            except (OSError, AttributeError):   # AttributeError: Windows
                os.ftruncate(fd, size)
        return fd

    def _run(self):
        it = self.item
        try:
            self._set(status="connecting", error="", last_try=time.time())
            if it.get("size", -1) in (-1, None) or not it.get("probed"):
                info = probe(it, self.settings)
                it.update(size=info["size"], resumable=info["resumable"], probed=True,
                          final_url=info["final_url"], content_type=info["content_type"])
                if not it.get("filename"):
                    reserve = getattr(self, "reserve_name", None)
                    it["filename"] = reserve(it, info["filename"]) if reserve else info["filename"]
            if self.stop_event.is_set():
                self._set(status="paused")
                return
            self._prepare_segments()
            self._fd = self._open_file()
            self._set(status="downloading")
            self._run_workers()
        except DownloadError as e:
            self._fatal = str(e)
        except Exception as e:  # keep the app alive no matter what
            self._fatal = f"{type(e).__name__}: {e}"
        finally:
            if self._fd is not None:
                try:
                    os.fsync(self._fd)
                except OSError:
                    pass
                os.close(self._fd)
                self._fd = None
        self._finish()

    def _finish(self):
        it = self.item
        segs = it.get("segments") or []
        done = segs and all(sg["e"] >= 0 and sg["p"] >= sg["e"] for sg in segs)
        if self._fatal and not done:
            self._set(status="error", error=self._fatal)
            self.on_finish(it, False)
            return
        if not done:
            self._set(status="paused")
            self.on_finish(it, False)
            return
        tmp = self.temp_path()
        final = Path(it["save_dir"]) / it["filename"]
        if final.exists() and self.settings["duplicate_action"] != "overwrite":
            final = unique_path(final)
            it["filename"] = final.name
        os.replace(tmp, final)
        self._set(status="complete", downloaded=it["size"], finished=time.time(), speed=0)
        self.on_finish(it, True)

    def _run_workers(self):
        it = self.item
        n_conn = int(it.get("connections") or self.settings["connections"]) if it.get("resumable") else 1
        assigned = set()
        workers = []

        def take_segment():
            with self.lock:
                segs = it["segments"]
                for idx, sg in enumerate(segs):
                    if idx not in assigned and (sg["e"] < 0 or sg["p"] < sg["e"]):
                        assigned.add(idx)
                        return idx
                if not it.get("resumable"):
                    return None
                # Dynamic segmentation: split the largest active segment.
                min_split = self.settings["min_split_kb"] * 1024
                best, best_rem = None, 0
                for idx, sg in enumerate(segs):
                    rem = sg["e"] - sg["p"]
                    if idx in assigned and rem > best_rem:
                        best, best_rem = idx, rem
                if best is None or best_rem < 2 * min_split:
                    return None
                sg = segs[best]
                mid = sg["p"] + best_rem // 2
                segs.append({"s": mid, "e": sg["e"], "p": mid})
                sg["e"] = mid
                idx = len(segs) - 1
                assigned.add(idx)
                return idx

        def worker():
            while not self.stop_event.is_set():
                idx = take_segment()
                if idx is None:
                    return
                ok = self._download_segment(idx)
                with self.lock:
                    assigned.discard(idx)
                if not ok:
                    return

        for _ in range(n_conn):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            workers.append(t)
            time.sleep(0.05)  # stagger connection setup slightly

        last_bytes, last_t = it.get("downloaded", 0), time.monotonic()
        samples = []
        last_save = time.monotonic()
        while any(t.is_alive() for t in workers):
            time.sleep(0.5)
            now = time.monotonic()
            with self.lock:
                cur = sum(sg["p"] - sg["s"] for sg in it["segments"])
                it["downloaded"] = cur
            samples.append((cur - last_bytes) / max(1e-6, now - last_t))
            samples = samples[-6:]
            self.speed = sum(samples) / len(samples)
            it["speed"] = self.speed
            last_bytes, last_t = cur, now
            if now - last_save > 2:
                last_save = now
                it["_dirty"] = True
            self.on_update(it)
        with self.lock:
            it["downloaded"] = sum(sg["p"] - sg["s"] for sg in it["segments"])
        it["speed"] = self.speed = 0
        # Workers can all die from errors while work remains: report it.
        segs = it["segments"]
        if not self.stop_event.is_set() and not self._fatal:
            unfinished = [sg for sg in segs if sg["e"] < 0 or sg["p"] < sg["e"]]
            if unfinished:
                self._fatal = getattr(self, "_last_error", None) or "Connection lost"

    def _download_segment(self, idx):
        it = self.item
        retries = int(self.settings["retries"])
        attempt = 0
        opener = build_opener(self.settings)
        url = it.get("final_url") or it["url"]
        while not self.stop_event.is_set():
            with self.lock:
                sg = it["segments"][idx]
                start, end = sg["p"], sg["e"]
            if end >= 0 and start >= end:
                return True
            try:
                headers = build_headers(it, self.settings)
                rng = (start, end - 1 if end > 0 else None) if it.get("resumable") else None
                with open_url(opener, url, headers, self.settings["timeout"], rng) as resp:
                    status = getattr(resp, "status", None) or resp.getcode()
                    if rng and status != 206:
                        if start == 0 and len(it["segments"]) == 1:
                            pass  # server ignored Range but we want the whole thing anyway
                        else:
                            raise DownloadError("Server stopped honouring byte ranges")
                    if not it.get("resumable") and start:
                        # Not resumable: restart this stream from scratch.
                        with self.lock:
                            sg["p"] = 0
                        start = 0
                    with self.lock:
                        self.active_connections += 1
                    try:
                        self._pump(resp, sg)
                    finally:
                        with self.lock:
                            self.active_connections -= 1
                if sg["e"] < 0 and not self.stop_event.is_set():
                    with self.lock:  # unknown length: EOF marks the end
                        sg["e"] = sg["p"]
                        it["size"] = sg["p"]
                    return True
                if sg["e"] >= 0 and sg["p"] >= sg["e"]:
                    return True
                # premature EOF: retry
                raise DownloadError("Connection closed early")
            except urllib.error.HTTPError as e:
                err = f"HTTP {e.code} {e.reason}"
                if e.code in (401, 403, 404, 410):
                    self._fatal = err
                    self.stop_event.set()
                    return False
            except (urllib.error.URLError, OSError, DownloadError, ValueError) as e:
                err = str(getattr(e, "reason", e)) or type(e).__name__
            self._last_error = err
            attempt += 1
            if attempt > retries:
                return False
            delay = min(30, 1.5 ** attempt)
            self.stop_event.wait(delay)
        return False

    def _pump(self, resp, sg):
        fd = self._fd
        while not self.stop_event.is_set():
            data = resp.read(CHUNK)
            if not data:
                return
            self.global_limiter.consume(len(data), self.stop_event)
            self.limiter.consume(len(data), self.stop_event)
            with self.lock:
                if sg["e"] >= 0:
                    data = data[: max(0, sg["e"] - sg["p"])]
                if data:
                    write_at(fd, data, sg["p"])
                    sg["p"] += len(data)
                if sg["e"] >= 0 and sg["p"] >= sg["e"]:
                    return
