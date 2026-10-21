"""Download folder choice. Run: python3 -m unittest discover tests"""

import tempfile
import unittest
from pathlib import Path

from draco.config import Settings


class FixedFolderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Settings(Path(self.tmp.name) / "s.json")
        self.s["download_dir"] = str(Path(self.tmp.name) / "dl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_category_folders_by_default(self):
        self.assertEqual(self.s.folder_for("Video"), Path(self.tmp.name) / "dl" / "Video")
        self.assertEqual(self.s.folder_for("General"), Path(self.tmp.name) / "dl")

    def test_fixed_folder_wins_for_every_category_until_reset(self):
        fixed = str(Path(self.tmp.name) / "mine")
        self.s["fixed_folder"] = fixed
        for cat in ("Video", "Music", "Compressed", "General"):
            self.assertEqual(self.s.folder_for(cat), Path(fixed))
        self.s["fixed_folder"] = ""
        self.assertEqual(self.s.folder_for("Video"), Path(self.tmp.name) / "dl" / "Video")



class XdgDirTest(unittest.TestCase):
    def test_home_with_trailing_slash_means_not_set(self):
        import io
        from unittest import mock
        from draco import osdeps
        for answer in (str(Path.home()) + "/\n", str(Path.home()) + "\n", ""):
            with mock.patch("os.popen", return_value=io.StringIO(answer)):
                self.assertEqual(osdeps._xdg_user_dir("DOCUMENTS", "Documents"), Path.home() / "Documents")
        with mock.patch("os.popen", return_value=io.StringIO("/data/Docs\n")):
            self.assertEqual(osdeps._xdg_user_dir("DOCUMENTS", "Documents"), Path("/data/Docs"))


if __name__ == "__main__":
    unittest.main()
