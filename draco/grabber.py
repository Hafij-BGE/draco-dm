"""Site grabber: crawl a website and collect links to downloadable files."""

import html.parser
import threading
import urllib.error
import urllib.parse
from collections import deque

from .engine import build_headers, build_opener, open_url

PAGE_TYPES = ("text/html", "application/xhtml+xml")
PAGE_EXTS = ("", ".html", ".htm", ".php", ".asp", ".aspx", ".jsp", ".shtml", "/")


class _LinkParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for key in ("href", "src", "data-src"):
            if a.get(key):
                self.links.append(a[key])
        if tag == "source" and a.get("srcset"):
            self.links += [p.strip().split(" ")[0] for p in a["srcset"].split(",") if p.strip()]


def extract_links(html_text, base):
    p = _LinkParser()
    try:
        p.feed(html_text)
    except Exception:
        pass
    out = []
    for link in p.links:
        link = link.strip()
        if link.startswith(("javascript:", "mailto:", "data:", "#", "tel:")):
            continue
        absu = urllib.parse.urljoin(base, link).split("#", 1)[0]
        if absu.startswith(("http://", "https://", "ftp://")):
            out.append(absu)
    return out


def _ext(url):
    path = urllib.parse.urlparse(url).path
    last = path.rsplit("/", 1)[-1]
    return ("." + last.rsplit(".", 1)[-1].lower()) if "." in last else ("/" if path.endswith("/") else "")


class SiteGrabber:
    """Breadth-first crawler. Calls on_found(url) for each matching file link."""

    def __init__(self, settings, start_url, depth=2, exts=None, same_site=True,
                 stay_under_path=False, max_pages=300, on_found=None, on_progress=None, on_done=None,
                 referer_cookies=None):
        self.settings = settings
        self.start_url = start_url
        self.depth = depth
        self.exts = {("." + e.lower().lstrip(".")) for e in (exts or [])}
        self.same_site = same_site
        self.stay_under_path = stay_under_path
        self.max_pages = max_pages
        self.on_found = on_found or (lambda url: None)
        self.on_progress = on_progress or (lambda pages, found, current: None)
        self.on_done = on_done or (lambda: None)
        self.cookies = referer_cookies or ""
        self.stop_event = threading.Event()
        self.found = set()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.stop_event.set()

    def _allowed(self, url):
        su, u = urllib.parse.urlparse(self.start_url), urllib.parse.urlparse(url)
        if self.same_site and u.netloc != su.netloc:
            return False
        if self.stay_under_path:
            prefix = su.path.rsplit("/", 1)[0] + "/"
            if not u.path.startswith(prefix):
                return False
        return True

    def _matches(self, url):
        ext = _ext(url)
        if self.exts:
            return ext in self.exts
        return ext not in PAGE_EXTS

    def _run(self):
        opener = build_opener(self.settings)
        item = {"url": self.start_url, "cookies": self.cookies}
        headers = build_headers(item, self.settings)
        seen = {self.start_url}
        queue = deque([(self.start_url, 0)])
        pages = 0
        try:
            while queue and not self.stop_event.is_set() and pages < self.max_pages:
                url, d = queue.popleft()
                self.on_progress(pages, len(self.found), url)
                try:
                    with open_url(opener, url, dict(headers, Referer=url), self.settings["timeout"]) as r:
                        ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip()
                        if ctype not in PAGE_TYPES:
                            continue
                        raw = r.read(5 * 1024 * 1024)
                        charset = r.headers.get_content_charset() or "utf-8"
                        base = r.geturl() or url
                except (urllib.error.URLError, OSError, ValueError):
                    continue
                pages += 1
                for link in extract_links(raw.decode(charset, "replace"), base):
                    if link in seen:
                        continue
                    seen.add(link)
                    if self._matches(link):
                        if link not in self.found:
                            self.found.add(link)
                            self.on_found(link)
                    elif d + 1 <= self.depth and self._allowed(link) and _ext(link) in PAGE_EXTS:
                        queue.append((link, d + 1))
        finally:
            self.on_progress(pages, len(self.found), "")
            self.on_done()
