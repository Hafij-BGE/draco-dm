"""Streaming-media downloads: HLS (.m3u8) natively, plus ffmpeg / yt-dlp bridges."""

import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
from pathlib import Path

from .engine import (CHUNK, DownloadError, RateLimiter, build_headers, build_opener,
                     open_url, sanitize_filename, unique_path)

from .osdeps import popen_kwargs, which

FFMPEG = which("ffmpeg")
HAS_FFMPEG = FFMPEG is not None
YTDLP = which("yt-dlp") or which("yt_dlp")

# YouTube answers a burst of parallel requests with "The page needs to be reloaded" / bot checks,
# so only a couple of yt-dlp downloads talk to it at the same time; the rest wait their turn.
YTDLP_SLOTS = threading.Semaphore(2)
YTDLP_TRANSIENT = re.compile(r"page needs to be reloaded|confirm you.re not a bot|HTTP Error (403|429|5\d\d)|"
                             r"timed? ?out|Connection reset|Temporary failure|Unable to download (API|webpage)|"
                             r"Remote end closed|IncompleteRead", re.I)
YTDLP_RETRY_WAIT = (5, 20, 45)    # seconds before the 2nd, 3rd and 4th try

_js_args = None
_YOUTUBE = re.compile(r"(^|\.)(youtube\.com|youtu\.be|youtube-nocookie\.com)$", re.I)


def ytdlp_cookie_args(url, cookies):
    """Browser cookies for yt-dlp, except for YouTube.

    yt-dlp cannot sign YouTube's logged-in requests from a plain Cookie header, so YouTube
    answers every one of them with "The page needs to be reloaded"; without cookies it works."""
    host = (urllib.parse.urlsplit(url).hostname or "")
    if not cookies or _YOUTUBE.search(host):
        return []
    return ["--add-header", "Cookie:" + cookies]


def ytdlp_js_args():
    """yt-dlp needs a JavaScript runtime for YouTube; it only looks for deno by itself.

    When deno is missing but node or bun is installed, point yt-dlp at that one (only if this
    yt-dlp is new enough to know the --js-runtimes option)."""
    global _js_args
    if _js_args is None:
        _js_args = []
        if YTDLP and not which("deno"):
            runtime = next((n for n in ("node", "bun") if which(n)), None)
            if runtime:
                try:
                    out = subprocess.run([YTDLP, "--help"], capture_output=True, text=True, timeout=30,
                                         **popen_kwargs()).stdout
                except (OSError, subprocess.SubprocessError):
                    out = ""
                if "--js-runtimes" in out:
                    _js_args = ["--js-runtimes", runtime]
    return list(_js_args)


def is_hls(url, content_type=""):
    path = urllib.parse.urlparse(url).path.lower()
    return path.endswith(".m3u8") or "mpegurl" in (content_type or "").lower()


def _attrs(line):
    return dict(re.findall(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)', line.split(":", 1)[1])) if ":" in line else {}


def parse_m3u8(text, base):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines or not lines[0].startswith("#EXTM3U"):
        raise DownloadError("Not an HLS playlist")
    out = {"variants": [], "segments": [], "durations": [], "key": None, "init": None, "endlist": False}
    pending_variant = None
    pending_dur = 0.0
    for line in lines[1:]:
        if line.startswith("#EXT-X-STREAM-INF"):
            a = _attrs(line)
            pending_variant = {"bandwidth": int(a.get("BANDWIDTH", "0") or 0),
                               "resolution": a.get("RESOLUTION", "").strip('"')}
        elif line.startswith("#EXT-X-KEY"):
            a = _attrs(line)
            method = a.get("METHOD", "NONE").strip('"')
            out["key"] = None if method == "NONE" else method
        elif line.startswith("#EXT-X-MAP"):
            uri = _attrs(line).get("URI", "").strip('"')
            if uri:
                out["init"] = urllib.parse.urljoin(base, uri)
        elif line.startswith("#EXTINF"):
            try:
                pending_dur = float(line.split(":", 1)[1].split(",")[0])
            except ValueError:
                pending_dur = 0.0
        elif line.startswith("#EXT-X-ENDLIST"):
            out["endlist"] = True
        elif not line.startswith("#"):
            url = urllib.parse.urljoin(base, line)
            if pending_variant is not None:
                pending_variant["url"] = url
                out["variants"].append(pending_variant)
                pending_variant = None
            else:
                out["segments"].append(url)
                out["durations"].append(pending_dur)
    return out


class _TaskBase:
    kind = "media"

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
        self.proc = None

    def start(self):
        self.thread = threading.Thread(target=self._wrap, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def join(self, timeout=None):
        if self.thread:
            self.thread.join(timeout)

    def set_speed_limit(self, kbps):
        self.item["speed_limit_kbps"] = kbps
        self.limiter.set_rate(kbps * 1024)

    def _set(self, **kw):
        self.item.update(kw)
        self.on_update(self.item)

    def _wrap(self):
        it = self.item
        try:
            self._set(status="connecting", error="", last_try=time.time())
            ok = self._run()
        except Exception as e:
            ok = False
            if not self.stop_event.is_set():
                self._set(status="error", error=str(e) or type(e).__name__, speed=0)
                self.on_finish(it, False)
                return
        if ok:
            self._set(status="complete", finished=time.time(), speed=0)
        elif self.stop_event.is_set():
            self._set(status="paused", speed=0)
        else:
            self._set(status="error", error=it.get("error") or "Failed", speed=0)
        self.on_finish(it, ok)


class HlsTask(_TaskBase):
    """Downloads HLS segments in parallel and joins them. Resumable per segment."""

    kind = "hls"

    def _fetch_text(self, opener, url):
        with open_url(opener, url, build_headers(self.item, self.settings), self.settings["timeout"]) as r:
            return r.read().decode("utf-8", "replace"), r.geturl() or url

    def _run(self):
        it = self.item
        opener = build_opener(self.settings)
        text, base = self._fetch_text(opener, it["url"])
        pl = parse_m3u8(text, base)
        if pl["variants"]:
            want = it.get("hls_variant")
            variants = sorted(pl["variants"], key=lambda v: v["bandwidth"])
            chosen = next((v for v in variants if v["url"] == want), variants[-1])
            text, base = self._fetch_text(opener, chosen["url"])
            pl = parse_m3u8(text, base)
            it["hls_variant"] = chosen["url"]
        if not it.get("filename"):
            stem = Path(urllib.parse.urlparse(it.get("referer") or it["url"]).path).stem or "video"
            it["filename"] = sanitize_filename(stem + ".mp4")
        if pl["key"] or not pl["endlist"]:
            # Encrypted or live stream: hand over to ffmpeg.
            if not HAS_FFMPEG:
                raise DownloadError("Encrypted/live HLS needs ffmpeg (sudo apt install ffmpeg)")
            return FfmpegTask._run_ffmpeg(self, it.get("hls_variant") or it["url"], sum(pl["durations"]))
        segs = pl["segments"]
        if not segs:
            raise DownloadError("Playlist has no segments")
        workdir = Path(it["save_dir"]) / f".{it['filename']}.dracohls"
        workdir.mkdir(parents=True, exist_ok=True)
        jobs = list(range(len(segs)))
        if pl["init"]:
            jobs.insert(0, -1)
        todo = [j for j in jobs if not (workdir / f"{j:06d}.seg").exists()]
        it["seg_total"] = len(jobs)
        it["seg_done"] = len(jobs) - len(todo)
        it["size"] = -1
        self._set(status="downloading")
        done_bytes = [sum(f.stat().st_size for f in workdir.glob("*.seg"))]
        it["downloaded"] = done_bytes[0]
        errors = []
        q_lock = threading.Lock()

        def worker():
            op = build_opener(self.settings)
            while not self.stop_event.is_set():
                with q_lock:
                    if not todo:
                        return
                    j = todo.pop(0)
                url = pl["init"] if j == -1 else segs[j]
                for attempt in range(int(self.settings["retries"]) + 1):
                    if self.stop_event.is_set():
                        return
                    try:
                        part = workdir / f"{j:06d}.part"
                        with open_url(op, url, build_headers(it, self.settings), self.settings["timeout"]) as r, \
                                open(part, "wb") as fh:
                            while True:
                                data = r.read(CHUNK)
                                if not data:
                                    break
                                if self.stop_event.is_set():
                                    return
                                self.global_limiter.consume(len(data), self.stop_event)
                                self.limiter.consume(len(data), self.stop_event)
                                fh.write(data)
                                with self.lock:
                                    done_bytes[0] += len(data)
                        os.replace(part, workdir / f"{j:06d}.seg")
                        with self.lock:
                            it["seg_done"] += 1
                        break
                    except (urllib.error.URLError, OSError, ValueError) as e:
                        if attempt >= int(self.settings["retries"]):
                            errors.append(str(getattr(e, "reason", e)))
                            self.stop_event.set()
                            return
                        self.stop_event.wait(min(20, 1.5 ** attempt))

        n = max(1, int(it.get("connections") or self.settings["connections"]))
        threads = [threading.Thread(target=worker, daemon=True) for _ in range(n)]
        for t in threads:
            t.start()
        self.active_connections = n
        last, last_t, samples = done_bytes[0], time.monotonic(), []
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
            now = time.monotonic()
            cur = done_bytes[0]
            samples = (samples + [(cur - last) / max(1e-6, now - last_t)])[-6:]
            self.speed = it["speed"] = sum(samples) / len(samples)
            it["downloaded"] = cur
            last, last_t = cur, now
            self.on_update(it)
        self.active_connections = 0
        if errors:
            it["error"] = errors[0]
            return False
        if self.stop_event.is_set():
            return False
        # Join segments
        self._set(status="merging", speed=0)
        joined = workdir / ("joined.mp4" if pl["init"] else "joined.ts")
        with open(joined, "wb") as out:
            for j in jobs:
                with open(workdir / f"{j:06d}.seg", "rb") as fh:
                    shutil.copyfileobj(fh, out, 1 << 20)
        final = Path(it["save_dir"]) / it["filename"]
        if not pl["init"] and not HAS_FFMPEG:
            final = final.with_suffix(".ts")
        final = unique_path(final)
        if not pl["init"] and HAS_FFMPEG:
            r = subprocess.run([FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-i", str(joined),
                                "-c", "copy", "-bsf:a", "aac_adtstoasc", str(final)],
                               capture_output=True, text=True, **popen_kwargs())
            if r.returncode != 0:  # fall back to the raw transport stream
                final = unique_path(final.with_suffix(".ts"))
                os.replace(joined, final)
        else:
            os.replace(joined, final)
        shutil.rmtree(workdir, ignore_errors=True)
        it["filename"] = final.name
        it["size"] = it["downloaded"] = final.stat().st_size
        return True


class FfmpegTask(_TaskBase):
    """Generic stream capture through ffmpeg (encrypted/live HLS, DASH .mpd)."""

    kind = "ffmpeg"

    def _run(self):
        if not self.item.get("filename"):
            self.item["filename"] = "video.mp4"
        return self._run_ffmpeg(self.item["url"], 0)

    def _run_ffmpeg(self, url, total_seconds):
        it = self.item
        hdrs = build_headers(it, self.settings)
        ua = hdrs.pop("User-Agent")
        header_blob = "".join(f"{k}: {v}\r\n" for k, v in hdrs.items())
        final = unique_path(Path(it["save_dir"]) / it["filename"])
        final.parent.mkdir(parents=True, exist_ok=True)
        cmd = [FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-user_agent", ua]
        if header_blob:
            cmd += ["-headers", header_blob]
        cmd += ["-i", url, "-c", "copy", "-progress", "pipe:1", str(final)]
        self._set(status="downloading", size=-1)
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                     **popen_kwargs())
        last_size, last_t = 0, time.monotonic()
        for line in self.proc.stdout:
            k, _, v = line.strip().partition("=")
            if k == "total_size" and v.isdigit():
                now = time.monotonic()
                size = int(v)
                self.speed = it["speed"] = (size - last_size) / max(1e-6, now - last_t)
                last_size, last_t = size, now
                it["downloaded"] = size
            elif k == "out_time_us" and v.isdigit() and total_seconds:
                it["fraction"] = min(1.0, int(v) / 1e6 / total_seconds)
            self.on_update(it)
            if self.stop_event.is_set():
                break
        self.proc.wait()
        if self.stop_event.is_set():
            return False
        if self.proc.returncode != 0:
            it["error"] = (self.proc.stderr.read() or "ffmpeg failed").strip().splitlines()[-1][:300]
            return False
        it["filename"] = final.name
        it["size"] = it["downloaded"] = final.stat().st_size
        return True


# Quality choices offered in the UI -> yt-dlp format selection.
QUALITIES = ["best", "2160", "1440", "1080", "720", "480", "360", "audio", "subs"]


def subtitle_langs(lang):
    """yt-dlp --sub-langs value: exact codes only (a loose pattern pulls dozens of auto-translated
    tracks and YouTube answers 429 Too Many Requests)."""
    import re
    lang = lang.lower() if lang and re.fullmatch(r"[A-Za-z]{2,3}", lang) else "en"
    out = [lang, f"{lang}-orig"]
    if lang == "en":
        out += ["en-US", "en-GB"]
    else:
        out += ["en", "en-orig"]
    return ",".join(out)


def valid_quality(q):
    """'best', 'audio' or a height in pixels (e.g. '1080', or '1088' from an HLS playlist)."""
    q = str(q or "")
    return q in QUALITIES or (q.isdigit() and 100 <= int(q) <= 8640)


def ytdlp_args_for_quality(q):
    q = q if valid_quality(q) else "best"
    if q == "subs":
        return ["--skip-download"]
    if q == "audio":
        return ["-f", "ba/b", "-x", "--audio-format", "mp3", "--audio-quality", "0"]
    # Highest resolution up to the chosen one; then H.264 + MP4/M4A so it plays everywhere.
    sort = (f"res:{q}," if q.isdigit() else "res,") + "vcodec:h264,ext:mp4:m4a"
    return ["-f", "bv*+ba/b", "-S", sort]


def ytdlp_info(url, cookies="", referer="", timeout=45):
    """Ask yt-dlp for title, duration and the available heights (no download)."""
    import json
    if not YTDLP:
        raise DownloadError("yt-dlp is not installed")
    cmd = [YTDLP, "-J", "--no-playlist", "--no-warnings", "--no-colors"] + ytdlp_js_args()
    if referer:
        cmd += ["--referer", referer]
    cookie_args = ytdlp_cookie_args(url, cookies)
    try:
        r = subprocess.run(cmd + cookie_args + ["--", url], capture_output=True, text=True, timeout=timeout,
                           **popen_kwargs())
        if r.returncode != 0 and cookie_args:   # the site may reject the browser's session: try without it
            r = subprocess.run(cmd + ["--", url], capture_output=True, text=True, timeout=timeout,
                               **popen_kwargs())
    except subprocess.TimeoutExpired as e:
        raise DownloadError("yt-dlp took too long to read the page") from e
    if r.returncode != 0:
        err = [l for l in r.stderr.splitlines() if "ERROR" in l]
        raise DownloadError((err[-1] if err else r.stderr.strip()[-300:]) or "yt-dlp could not read this page")
    j = json.loads(r.stdout)
    return summarize_formats(j)


def summarize_formats(j):
    """Title, length and an estimated download size per quality, from yt-dlp's JSON."""
    fmts = j.get("formats") or []
    dur = j.get("duration") or 0

    def size_of(f):
        if not f:
            return 0
        return int(f.get("filesize") or f.get("filesize_approx")
                   or ((f.get("tbr") or 0) * 1000 / 8 * dur) or 0)

    def has(f, key):
        return f.get(key) not in (None, "none")

    audio_only = [f for f in fmts if has(f, "acodec") and not has(f, "vcodec")]
    best_audio = max(audio_only, key=lambda f: (f.get("ext") == "m4a", f.get("abr") or f.get("tbr") or 0),
                     default=None)
    a_size = size_of(best_audio)
    sizes = {}
    heights = sorted({f["height"] for f in fmts if f.get("height") and has(f, "vcodec")}, reverse=True)
    for h in heights:
        cands = [f for f in fmts if f.get("height") == h and has(f, "vcodec")]
        # same preference as the download: H.264, then MP4, then bitrate
        v = max(cands, key=lambda f: ((f.get("vcodec") or "").startswith("avc"), f.get("ext") == "mp4",
                                      f.get("tbr") or 0))
        sizes[str(h)] = size_of(v) + (0 if has(v, "acodec") else a_size)
    sizes["audio"] = a_size
    if heights:
        sizes["best"] = sizes[str(heights[0])]
    return {"title": j.get("title") or "video", "duration": dur, "heights": heights, "sizes": sizes,
            "extractor": j.get("extractor_key", ""), "uploader": j.get("uploader") or j.get("channel") or ""}


class YtdlpTask(_TaskBase):
    """Uses yt-dlp for sites like YouTube. yt-dlp resumes its own .part files.

    Subtitles are fetched in a second, separate yt-dlp run so a subtitle problem never costs
    the video; they are then embedded with ffmpeg and also kept as a .srt next to the video.
    """

    kind = "ytdlp"
    _no_cookies = False   # set after the site rejected the browser's cookies

    def _common(self):
        it = self.item
        cmd = [YTDLP, "--no-playlist", "--no-colors", "--no-simulate",
               "-P", it["save_dir"], "-o", it.get("ytdlp_template") or "%(title).180B.%(ext)s",
               "--print", "video:DRACONAME %(title).180B"] + ytdlp_js_args()
        if it.get("referer"):
            cmd += ["--referer", it["referer"]]
        if not self._no_cookies:
            cmd += ytdlp_cookie_args(it["url"], it.get("cookies"))
        if self.settings["proxy"]:
            cmd += ["--proxy", self.settings["proxy"]]
        return cmd

    def _name(self, line, ext):
        title = line[10:]
        self.item["_ytdlp_title"] = title
        self.item["filename"] = sanitize_filename(title + ext)
        self.on_update(self.item)

    def _run(self):
        it = self.item
        if not YTDLP:
            raise DownloadError("yt-dlp is not installed (sudo apt install yt-dlp)")
        Path(it["save_dir"]).mkdir(parents=True, exist_ok=True)
        quality = it.get("ytdlp_quality") or "best"
        if quality == "subs":
            self._set(status="downloading", size=-1)
            subs = self._fetch_subs()
            if self.stop_event.is_set():
                return False
            if not subs:
                it["error"] = it.get("error") or "This video has no subtitles in that language"
                return False
            it["filename"] = subs[0].name
            it["size"] = it["downloaded"] = subs[0].stat().st_size
            return True

        tmpl = ("DRACO %(progress.downloaded_bytes)s %(progress.total_bytes)s "
                "%(progress.total_bytes_estimate)s %(progress.speed)s")

        def command():
            cmd = self._common() + ["--newline", "--progress", "-N", str(min(8, int(self.settings["connections"]))),
                                    "--progress-template", "download:" + tmpl,
                                    "--print", "after_move:DRACOFILE %(filepath)s"]
            cmd += ytdlp_args_for_quality(quality)
            limit = it.get("speed_limit_kbps") or self.settings["speed_limit_kbps"]
            if limit:
                cmd += ["-r", f"{int(limit)}K"]
            return cmd + ["--", it["url"]]

        for attempt in range(len(YTDLP_RETRY_WAIT) + 1):
            rc, last_err = self._download(command(), quality)
            if self.stop_event.is_set():
                return False
            if rc == 0:
                break
            if not self._no_cookies and ytdlp_cookie_args(it["url"], it.get("cookies")):
                self._no_cookies = True    # the site rejected the browser's session: retry right away without it
                rc, last_err = self._download(command(), quality)
                if self.stop_event.is_set():
                    return False
                if rc == 0:
                    break
            if attempt == len(YTDLP_RETRY_WAIT) or not YTDLP_TRANSIENT.search(last_err):
                it["error"] = last_err[:300] or "yt-dlp failed"
                return False
            # YouTube pushed back: wait a little, then try again (yt-dlp continues its .part files)
            self._set(status="connecting", speed=0)
            if self.stop_event.wait(YTDLP_RETRY_WAIT[attempt]):
                return False
        video = Path(it["save_dir"]) / it["filename"]
        if it.get("subs"):
            self._set(status="merging", speed=0)
            subs = self._fetch_subs()
            if subs and quality != "audio" and HAS_FFMPEG and video.suffix.lower() in (".mp4", ".m4v", ".mkv", ".mov"):
                self._embed(video, subs[0])
            it["subs_result"] = (", ".join(p.name for p in subs)) if subs else "no subtitles found"
        if video.exists():
            it["size"] = it["downloaded"] = video.stat().st_size
        return True

    def _download(self, cmd, quality):
        """One yt-dlp run; returns (exit code, last error line)."""
        it = self.item
        while not YTDLP_SLOTS.acquire(timeout=0.5):
            if self.stop_event.is_set():
                return 1, ""
        try:
            self._set(status="downloading", size=-1)
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                         encoding="utf-8", errors="replace", **popen_kwargs())
            last_err = ""
            base, last_done, last_total = 0, 0, 0   # video and audio arrive as two files: add them up

            def num(v):
                try:
                    return float(v)
                except ValueError:
                    return 0.0

            for line in self.proc.stdout:
                line = line.strip()
                if line.startswith("DRACO "):
                    p = line.split()
                    done, tot = num(p[1]), num(p[2]) or num(p[3])
                    if last_done and done < last_done * 0.5:   # next stream started
                        base += last_total or last_done
                    last_done, last_total = done, tot
                    it["downloaded"] = int(base + done)
                    it["size"] = int(base + tot) if tot else -1
                    self.speed = it["speed"] = num(p[4])
                    self.on_update(it)
                elif line.startswith("DRACONAME "):
                    self._name(line, ".mp3" if quality == "audio" else ".mp4")
                elif line.startswith("DRACOFILE "):
                    path = Path(line[10:])
                    it["save_dir"], it["filename"] = str(path.parent), path.name
                elif "ERROR" in line:
                    last_err = line
                if self.stop_event.is_set():
                    break
            self.proc.wait()
            return self.proc.returncode, last_err
        finally:
            YTDLP_SLOTS.release()

    def _fetch_subs(self):
        """Run yt-dlp once more for subtitles only; returns the .srt files written (newest first)."""
        it = self.item
        before = {p.name for p in Path(it["save_dir"]).glob("*.srt")}
        cmd = self._common() + ["--skip-download", "--write-subs", "--write-auto-subs",
                                "--sub-langs", subtitle_langs(it.get("sub_lang")),
                                "--convert-subs", "srt", "--", it["url"]]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     encoding="utf-8", errors="replace", **popen_kwargs())
        err = ""
        for line in self.proc.stdout:
            line = line.strip()
            if line.startswith("DRACONAME ") and it.get("ytdlp_quality") == "subs":
                self._name(line, ".srt")
            elif "ERROR" in line:
                err = line
            if self.stop_event.is_set():
                break
        self.proc.wait()
        folder = Path(it["save_dir"])
        new = [p for p in folder.glob("*.srt") if p.name not in before]
        if not new:   # already downloaded earlier: match by name (yt-dlp's own file name first)
            stems = {Path(it.get("filename") or "").stem, sanitize_filename(it.get("_ytdlp_title") or "")} - {""}
            new = [p for stem in stems for p in folder.glob(f"{glob_escape(stem)}*.srt")]
        if not new and err:
            it["error"] = err[:300]
        return sorted(new, key=lambda p: p.stat().st_mtime, reverse=True)

    def _embed(self, video, srt):
        """Add the subtitle track to the video file itself (players can switch it on/off)."""
        tmp = video.with_name(video.stem + ".subs-tmp" + video.suffix)
        codec = "srt" if video.suffix.lower() == ".mkv" else "mov_text"
        lang = (srt.stem.rsplit(".", 1)[-1] if "." in srt.stem else "eng")[:3]
        r = subprocess.run([FFMPEG, "-nostdin", "-y", "-loglevel", "error", "-i", str(video), "-i", str(srt),
                            "-map", "0", "-map", "1", "-c", "copy", "-c:s", codec,
                            "-metadata:s:s:0", f"language={lang}", str(tmp)], capture_output=True, **popen_kwargs())
        if r.returncode == 0 and tmp.exists():
            os.replace(tmp, video)
        elif tmp.exists():
            tmp.unlink()


def glob_escape(s):
    import glob
    return glob.escape(s)
