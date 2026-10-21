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

    def test_progress_look_follows_category_and_choice(self):
        self.assertIsNone(style.progress_style("classic", "Video"))
        self.assertEqual(style.progress_style("galaxy-explorer", "Video"), "video")
        self.assertEqual(style.progress_style("galaxy-explorer", "Programs"), "galaxy")
        self.assertEqual(style.progress_style("aurora-light", "General"), "compressed")
        chosen = {"Video": "documents", "General": "music", "Music": "auto"}
        self.assertEqual(style.progress_style("galaxy-explorer", "Video", chosen), "documents")
        self.assertEqual(style.progress_style("galaxy-explorer", None, chosen), "music")
        self.assertEqual(style.progress_style("galaxy-explorer", "Music", chosen), "music")


if __name__ == "__main__":
    unittest.main()
