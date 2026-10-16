"""YtdlpTask against a fake yt-dlp script (no network). Run: python3 -m unittest discover tests"""

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from draco import media
from draco.config import Settings

# Fails with YouTube's "reload" error until it has been run FAIL_TIMES times, then "downloads".
FAKE = r'''#!{python}
import os, sys
from pathlib import Path
state = Path(os.environ["FAKE_STATE"])
n = int(state.read_text()) if state.exists() else 0
state.write_text(str(n + 1))
if os.environ.get("FAIL_WITH_COOKIES") and any(a.startswith("Cookie:") for a in sys.argv):
    print("ERROR: [site] abc: HTTP Error 401: Unauthorized")
    sys.exit(1)
if n < int(os.environ["FAIL_TIMES"]):
    print("ERROR: [youtube] abc: " + os.environ["FAIL_MSG"])
    sys.exit(1)
out = Path(sys.argv[sys.argv.index("-P") + 1]) / "Clip.mp4"
out.write_bytes(b"x" * 1000)
print("DRACONAME Clip")
print("DRACO 1000 1000 NA 500")
print("DRACOFILE " + str(out))
'''


class YtdlpRetryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        fake = d / "yt-dlp"
        fake.write_text(FAKE.replace("{python}", sys.executable))
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.state = d / "runs"
        os.environ["FAKE_STATE"] = str(self.state)
        self._saved = (media.YTDLP, media.YTDLP_RETRY_WAIT, media._js_args)
        media.YTDLP, media.YTDLP_RETRY_WAIT, media._js_args = str(fake), (0.1, 0.1, 0.1), []
        self.settings = Settings(d / "s.json")

    def tearDown(self):
        media.YTDLP, media.YTDLP_RETRY_WAIT, media._js_args = self._saved
        self.tmp.cleanup()

    def run_task(self, fail_times, msg, url="https://www.youtube.com/watch?v=abc", cookies=""):
        os.environ["FAIL_TIMES"], os.environ["FAIL_MSG"] = str(fail_times), msg
        item = {"url": url, "save_dir": self.tmp.name, "filename": "", "cookies": cookies,
                "kind": "ytdlp", "ytdlp_quality": "720", "downloaded": 0, "size": -1}
        task = media.YtdlpTask(item, self.settings, None)
        return item, task._run()

    def test_retries_youtube_reload_error(self):
        item, ok = self.run_task(2, "The page needs to be reloaded.")
        self.assertTrue(ok)
        self.assertEqual(self.state.read_text(), "3")
        self.assertEqual(item["filename"], "Clip.mp4")

    def test_gives_up_after_last_try(self):
        item, ok = self.run_task(10, "The page needs to be reloaded.")
        self.assertFalse(ok)
        self.assertEqual(self.state.read_text(), str(len(media.YTDLP_RETRY_WAIT) + 1))
        self.assertIn("reloaded", item["error"])

    def test_no_retry_for_permanent_error(self):
        item, ok = self.run_task(10, "Video unavailable. This video is private")
        self.assertFalse(ok)
        self.assertEqual(self.state.read_text(), "1")


    def test_youtube_never_gets_browser_cookies(self):
        self.assertEqual(media.ytdlp_cookie_args("https://www.youtube.com/watch?v=abc", "SID=1"), [])
        self.assertEqual(media.ytdlp_cookie_args("https://youtu.be/abc", "SID=1"), [])
        self.assertEqual(media.ytdlp_cookie_args("https://m.youtube.com/watch?v=abc", "SID=1"), [])
        self.assertEqual(media.ytdlp_cookie_args("https://vimeo.com/1", "a=1"), ["--add-header", "Cookie:a=1"])

    def test_other_site_retries_without_cookies(self):
        os.environ["FAIL_WITH_COOKIES"] = "1"
        try:
            item, ok = self.run_task(0, "", url="https://vimeo.com/1", cookies="a=1")
        finally:
            del os.environ["FAIL_WITH_COOKIES"]
        self.assertTrue(ok)
        self.assertEqual(self.state.read_text(), "2")


if __name__ == "__main__":
    unittest.main()
