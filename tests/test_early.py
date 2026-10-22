"""Start-while-choosing: a download fetched into the temp folder ends up where the user chose."""

import tempfile
import time
import unittest
from pathlib import Path

from draco.config import Settings
from draco.manager import Manager


class EarlyDownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.s = Settings(root / "s.json")
        self.s["download_dir"] = str(root / "dl")
        self.m = Manager(self.s, store=root / "downloads.json")
        self.events = []
        self.m.listeners.append(lambda ev, it: self.events.append(ev))
        self.dest = root / "chosen"

    def tearDown(self):
        self.tmp.cleanup()

    def finished_early(self, name="f.zip", data=b"x" * 100):
        temp = self.s.temp_dir()
        temp.mkdir(parents=True)
        (temp / name).write_bytes(data)
        it = self.m.new_item("http://h/" + name, name, len(data))
        it.update(save_dir=str(temp), early=True, status="complete")
        self.m.items[it["id"]] = it
        self.m._on_finish(it, True)
        return it

    def wait_for(self, cond):
        for _ in range(100):
            if cond():
                return
            time.sleep(0.02)

    def test_temp_folder_default(self):
        self.assertEqual(self.s.temp_dir(), Path(self.tmp.name) / "dl" / "temp")

    def test_finished_early_waits_then_moves_on_confirm(self):
        it = self.finished_early()
        self.assertTrue(it["early_done"])
        self.assertNotIn("finished", self.events)          # no "done" notice for a temp file
        self.m.confirm_early(it["id"], self.dest, "report.zip")
        self.wait_for(lambda: "finished" in self.events)
        self.assertEqual((self.dest / "report.zip").read_bytes(), b"x" * 100)
        self.assertEqual((it["save_dir"], it["filename"]), (str(self.dest), "report.zip"))
        self.assertEqual(list(self.s.temp_dir().iterdir()), [])

    def test_name_taken_gets_a_number(self):
        self.dest.mkdir()
        (self.dest / "f.zip").write_bytes(b"old")
        it = self.finished_early()
        self.m.confirm_early(it["id"], self.dest, "f.zip")
        self.wait_for(lambda: "finished" in self.events)
        self.assertEqual((self.dest / "f.zip").read_bytes(), b"old")
        self.assertNotEqual(it["filename"], "f.zip")
        self.assertTrue((self.dest / it["filename"]).exists())

    def test_cancel_deletes_the_temp_copy(self):
        it = self.finished_early()
        self.m.discard_early(it["id"])
        self.assertNotIn(it["id"], self.m.items)
        self.assertEqual(list(self.s.temp_dir().iterdir()), [])

    def test_confirmed_download_moves_when_it_finishes(self):
        temp = self.s.temp_dir()
        temp.mkdir(parents=True)
        (temp / "g.zip").write_bytes(b"data")
        it = self.m.new_item("http://h/g.zip", "g.zip", 4)
        it.update(save_dir=str(temp), move_to={"dir": str(self.dest), "name": "g.zip"}, status="complete")
        self.m.items[it["id"]] = it
        self.m._on_finish(it, True)
        self.assertTrue((self.dest / "g.zip").exists())
        self.assertNotIn("move_to", it)
        self.assertIn("finished", self.events)


if __name__ == "__main__":
    unittest.main()
