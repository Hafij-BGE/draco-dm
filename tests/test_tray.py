"""Each tray menu item runs its own action (Show Draco used to quit the app)."""

import unittest

from gi.repository import GLib

from draco.gui.tray import Tray


class FakeApp:
    def __init__(self):
        self.calls = []

    def show_main(self):
        self.calls.append("show")

    def show_add_url(self):
        self.calls.append("add")

    def _quit(self):
        self.calls.append("quit")


def run(item_id):
    app = FakeApp()
    Tray(app)._run(item_id)
    ctx = GLib.MainContext.default()
    while ctx.iteration(False):
        pass
    return app.calls


class TrayMenuTest(unittest.TestCase):
    def test_show_draco_shows(self):
        self.assertEqual(run(1), ["show"])

    def test_add_url(self):
        self.assertEqual(run(2), ["show", "add"])

    def test_quit(self):
        self.assertEqual(run(4), ["quit"])

    def test_separator_does_nothing(self):
        self.assertEqual(run(3), [])


if __name__ == "__main__":
    unittest.main()
