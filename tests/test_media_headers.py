"""ffmpeg -headers must not carry CR/LF from header values (cookie/referer injection)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from draco import media
from draco.config import Settings
from draco.engine import RateLimiter


class FfmpegHeaderTest(unittest.TestCase):
    def test_crlf_stripped_from_header_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(Path(tmp) / "s.json")
            it = {"id": "m1", "url": "https://example.com/v.m3u8", "save_dir": tmp, "filename": "v.mp4",
                  "cookies": "a=1\r\nX-Evil: yes\r\n", "referer": "https://example.com/\nX-Bad: 1"}
            task = media.FfmpegTask(it, settings, RateLimiter(0))
            seen = {}

            def fake_popen(cmd, **kw):
                seen["cmd"] = cmd
                raise OSError("stop here")
            with mock.patch.object(media, "FFMPEG", "ffmpeg"), \
                    mock.patch.object(media.subprocess, "Popen", side_effect=fake_popen):
                with self.assertRaises(OSError):
                    task._run_ffmpeg(it["url"], 0)
            blob = seen["cmd"][seen["cmd"].index("-headers") + 1]
            lines = blob.split("\r\n")
            self.assertEqual(lines[-1], "")
            for line in lines[:-1]:
                self.assertNotIn("\n", line)
                self.assertNotIn("\r", line)
            self.assertFalse(any(line.startswith(("X-Evil", "X-Bad")) for line in lines), lines)
            self.assertTrue(any(line.startswith("Cookie: a=1") for line in lines), lines)


if __name__ == "__main__":
    unittest.main()
