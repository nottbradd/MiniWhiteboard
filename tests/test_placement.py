import unittest

from mini_whiteboard.geometry import PlacementState, Rect, large_enough, local_point, normalized


class PlacementTests(unittest.TestCase):
    def test_exact_hold_release_workflow(self):
        state = PlacementState()
        self.assertTrue(state.begin((500, 600)))
        self.assertEqual(state.anchor, (500, 600))
        self.assertEqual(state.release((100, 200)), ("confirmed", Rect(100, 200, 400, 400)))
        self.assertFalse(state.active)
        self.assertTrue(state.begin((-600, -300)))

    def test_all_directions_and_negative_desktop(self):
        for point in [(-700, -600), (-300, -600), (-700, -200), (-300, -200)]:
            r = normalized((-500, -400), point)
            self.assertEqual((r.width, r.height), (200, 200))
            self.assertLessEqual(r.x, -500)
            self.assertLessEqual(r.y, -400)

    def test_small_release_clears_anchor(self):
        state = PlacementState()
        for point in [(100, 100), (259, 200), (260, 199)]:
            state.begin((100, 100))
            self.assertEqual(state.release(point)[0], "too_small")
            self.assertIsNone(state.anchor)
        state.begin((100, 100))
        self.assertEqual(state.release((260, 200))[0], "confirmed")

    def test_minimum_at_fractional_scales(self):
        for scale in (1, 1.25, 1.5, 1.75, 2):
            self.assertTrue(large_enough(Rect(0, 0, 160*scale, 100*scale), scale))
            self.assertFalse(large_enough(Rect(0, 0, 160*scale-1, 100*scale), scale))

    def test_conversion_uses_monitor_local_origin(self):
        self.assertEqual(local_point((-1500, 300), (-1920, 0), 1.5), (280, 200))

    def test_cancel(self):
        state = PlacementState()
        state.begin((100, 100))
        state.cancel()
        self.assertFalse(state.active)
        self.assertTrue(state.begin((500, 500)))


if __name__ == "__main__":
    unittest.main()
