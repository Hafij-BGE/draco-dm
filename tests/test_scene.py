"""The live planet follows the engine's real state and never runs ahead of the real progress."""

import unittest

from draco.gui.scene_model import SceneMotion, scene_state

MB = 1024 * 1024


def item(status, frac=0.0, speed=0.0, size=100 * MB, id_="a"):
    return {"id": id_, "url": "https://x/f", "status": status, "size": size,
            "downloaded": int(size * frac), "speed": speed}


class StageTest(unittest.TestCase):
    def stage(self, *a, **k):
        return scene_state(item(*a, **k)).stage

    def test_stages_by_progress(self):
        self.assertEqual(self.stage("downloading", 0.02, MB), "initializing")
        self.assertEqual(self.stage("connecting", 0.40), "initializing")
        self.assertEqual(self.stage("downloading", 0.35, MB), "downloading")
        self.assertEqual(self.stage("downloading", 0.82, MB), "highspeed")
        self.assertEqual(self.stage("downloading", 0.99, MB), "finalizing")
        self.assertEqual(self.stage("merging", 1.0), "finalizing")
        self.assertEqual(self.stage("complete", 0.3), "completed")

    def test_other_states(self):
        self.assertEqual(self.stage("paused", 0.4), "paused")
        self.assertEqual(self.stage("stopped", 0.4), "paused")
        self.assertEqual(self.stage("queued", 0.0), "paused")
        self.assertEqual(scene_state(item("queued")).label, "Queued")
        self.assertEqual(self.stage("error", 0.2), "error")
        self.assertEqual(scene_state(None).stage, "idle")

    def test_completed_is_full_and_speed_only_while_downloading(self):
        self.assertEqual(scene_state(item("complete", 0.3)).fraction, 1.0)
        self.assertEqual(scene_state(item("paused", 0.4, speed=5 * MB)).speed, 0.0)

    def test_unknown_size(self):
        st = scene_state(item("downloading", speed=MB, size=-1))
        self.assertEqual(st.fraction, -1.0)


class MotionTest(unittest.TestCase):
    def test_ring_never_ahead_of_real_progress(self):
        m = SceneMotion()
        m.set_state(scene_state(item("downloading", 0.30, MB)))
        m.set_state(scene_state(item("downloading", 0.40, MB)))
        real = 0.40
        for _ in range(200):
            m.update(1 / 30)
            self.assertLessEqual(m.arc, real + 1e-9)
        self.assertAlmostEqual(m.arc, real, places=3)

    def test_paused_has_no_data_flow(self):
        m = SceneMotion()
        m.set_state(scene_state(item("downloading", 0.5, 5 * MB)))
        for _ in range(60):
            m.update(1 / 30)
        self.assertGreater(m.flow, 0.3)
        m.set_state(scene_state(item("paused", 0.5)))
        for _ in range(90):
            m.update(1 / 30)
        self.assertLess(m.flow, 0.01)
        self.assertLess(m.active, 0.01)
        self.assertGreater(m.hold, 0.95)

    def test_jumpy_speed_keeps_motion_steady(self):
        m = SceneMotion()
        m.set_state(scene_state(item("downloading", 0.5, 3 * MB)))
        for _ in range(90):
            m.update(1 / 30)
        seen = []
        for k in range(300):                       # speed jumping between 0.3 and 12 MB/s every 0.5 s
            if k % 15 == 0:
                m.set_state(scene_state(item("downloading", 0.5, (12 if k % 30 else 0.3) * MB)))
            m.update(1 / 30)
            seen.append((m.active, m.flow))
        self.assertTrue(all(a > 0.99 for a, _ in seen))
        flows = [f for _, f in seen[60:]]
        self.assertLess(max(flows) - min(flows), 0.15)

    def test_completed_settles(self):
        m = SceneMotion()
        m.set_state(scene_state(item("complete", 1.0)))
        for _ in range(120):
            m.update(1 / 30)
        self.assertGreater(m.calm, 0.99)
        self.assertEqual(m.flow, 0.0)

    def test_switching_download_jumps(self):
        m = SceneMotion()
        m.set_state(scene_state(item("downloading", 0.9, MB, id_="a")))
        m.set_state(scene_state(item("downloading", 0.1, MB, id_="b")))
        self.assertAlmostEqual(m.arc, 0.1, places=3)
        self.assertEqual(m.state.item_id, "b")


if __name__ == "__main__":
    unittest.main()
