"""Dashboard themes: CSS builds, art exists, progress look per category. Run: python3 -m unittest discover tests"""

import unittest

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from draco.gui import style  # noqa: E402


class ThemeTest(unittest.TestCase):
    def test_every_theme_builds_css(self):
        for key, _ in style.theme_names():
            css = style.css_for(key)
            if key != "system":
                self.assertIn("@define-color window_bg_color", css, key)

    def test_art_files_exist(self):
        for t in style.MODERN.values():
            self.assertTrue((style.ART_DIR / t["bg"]).exists(), t["bg"])
        for p in style.PROGRESS_STYLES.values():
            self.assertTrue((style.ART_DIR / p["art"]).exists(), p["art"])
            self.assertTrue((style.ART_DIR / p["bg"]).exists(), p["bg"])

    def test_picture_themes_use_their_own_progress_windows(self):
        self.assertIsNone(style.progress_style("classic", "Video"))
        for key in ("galaxy-explorer", "aurora-light", "solar-eclipse"):
            self.assertTrue(style.is_bright(key))
            self.assertIsNone(style.progress_style(key, "Video"))


class ThemeGroupTest(unittest.TestCase):
    def test_every_theme_is_in_exactly_one_category(self):
        groups = style.theme_groups()
        self.assertEqual([t for t, _ in groups], ["Light", "Dark", "Classic"])
        keys = [k for _, items in groups for k, _ in items]
        self.assertEqual(sorted(keys), sorted(k for k, _ in style.theme_names()))
        self.assertEqual(len(keys), len(set(keys)))
        names = [n for _, items in groups for _, n in items]
        self.assertEqual(len(names), len(set(names)), "two themes would look the same in a menu")
        for title, items in groups[:2]:
            for k, _ in items:
                self.assertEqual(style.BRIGHT[k].get("dark", False), title == "Dark", k)


class BrightThemeTest(unittest.TestCase):
    def test_light_picture_themes_build_and_have_art(self):
        from draco.gui import bright_style
        for key in bright_style.BRIGHT:
            self.assertTrue(style.is_bright(key))
            self.assertIn("bw-window", style.css_for(key))
            self.assertTrue((bright_style.ART_DIR / bright_style.BRIGHT[key]["bg"]).exists(), key)
        for kind in bright_style.KINDS:
            self.assertTrue((bright_style.ART_DIR / f"pw2-ill-{kind}.png").exists(), kind)
            self.assertTrue((bright_style.ART_DIR / f"pw2-bg-{kind}.jpg").exists(), kind)

    def test_file_kind_picks_window_look(self):
        from draco.gui.bright_style import file_icon, kind_of
        self.assertEqual(kind_of({"filename": "a.zip"}), "archive")
        self.assertEqual(kind_of({"filename": "talk.MP4"}), "video")
        self.assertEqual(kind_of({"filename": "x.flac"}), "music")
        self.assertEqual(kind_of({"filename": "paper.pdf"}), "document")
        self.assertEqual(kind_of({"filename": "setup.exe"}), "program")
        self.assertEqual(kind_of({"filename": "ubuntu.iso"}), "disc")
        self.assertEqual(kind_of({"filename": "photo.jpg"}), "image")
        self.assertEqual(kind_of({"filename": "blob.bin"}), "unknown")
        self.assertEqual(kind_of({"filename": "", "url": "https://x/live.m3u8", "kind": "hls"}), "live")
        self.assertEqual(file_icon("paper.pdf"), "draco-f-pdf")
        self.assertEqual(file_icon("a.rar"), "draco-f-archive")


if __name__ == "__main__":
    unittest.main()
