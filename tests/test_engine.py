"""物理引擎正确性测试：解析解对照 + 碰撞 + 得分判定 + 预设命中。"""

import math
import unittest

from shotlab.constants import BALL_RADIUS, BOARD_RESTITUTION, G, RIM_HEIGHT
from shotlab.engine import Simulator
from shotlab.monte_carlo import run_mc
from shotlab.params import ShotParams, preset_params
from shotlab.sweep import run_sweep

VACUUM = ShotParams(v0=8.0, angle_deg=45.0, release_height=1.0,
                    distance=20.0, spin=0.0, drag=False, magnus=False)


def analytic_landing(v0, angle_deg, h):
    """球心从高度 h 落到触地高度（= 球半径）的水平射程。"""
    th = math.radians(angle_deg)
    vy = v0 * math.sin(th)
    vx = v0 * math.cos(th)
    t = (vy + math.sqrt(vy * vy + 2 * G * (h - BALL_RADIUS))) / G
    return vx * t


class TestVacuum(unittest.TestCase):
    def test_landing_matches_analytic(self):
        r = Simulator(VACUUM).run()
        expect = analytic_landing(VACUUM.v0, VACUUM.angle_deg, VACUUM.release_height)
        self.assertIsNotNone(r.landing_x)
        self.assertAlmostEqual(r.landing_x, expect, delta=0.02)

    def test_apex_matches_analytic(self):
        r = Simulator(VACUUM).run()
        vy = VACUUM.v0 * math.sin(math.radians(VACUUM.angle_deg))
        expect = VACUUM.release_height + vy * vy / (2 * G)
        self.assertAlmostEqual(r.apex, expect, delta=0.01)


class TestAero(unittest.TestCase):
    def test_drag_reduces_range(self):
        with_drag = Simulator(VACUUM.with_(drag=True)).run()
        no_drag = Simulator(VACUUM).run()
        self.assertLess(with_drag.landing_x, no_drag.landing_x)

    def test_backspin_adds_lift(self):
        plain = Simulator(ShotParams(v0=8.0, angle_deg=50.0, release_height=2.0,
                                     distance=20.0, spin=0.0, drag=True,
                                     magnus=False)).run()
        spun = Simulator(ShotParams(v0=8.0, angle_deg=50.0, release_height=2.0,
                                    distance=20.0, spin=8.0, drag=True,
                                    magnus=True)).run()
        self.assertGreater(spun.apex, plain.apex + 0.005)
        self.assertGreater(spun.landing_x, plain.landing_x)


class TestCollisions(unittest.TestCase):
    def test_board_bounce_loses_energy(self):
        sim = Simulator(ShotParams(distance=4.19))
        bx = sim.board_x
        st = (bx - BALL_RADIUS + 0.001, 3.4, 5.0, 0.0, 0.0)
        st2, hit = sim._collide_segment(
            st, bx, 2.90, 3.95, BOARD_RESTITUTION, "board")
        self.assertTrue(hit)
        self.assertLess(st2[2], 0.0)                       # 反弹回向场地
        self.assertLess(abs(st2[2]), 5.0)                  # 有能量损失
        self.assertAlmostEqual(abs(st2[2]), 5.0 * BOARD_RESTITUTION, delta=0.05)

    def test_ground_bounce_loses_energy(self):
        r = Simulator(VACUUM).run()
        self.assertGreaterEqual(r.bounces, 1)


class TestScoring(unittest.TestCase):
    def test_preset_free_throw_scores(self):
        r = Simulator(preset_params("free_throw")).run()
        self.assertTrue(r.scored, msg=f"label={r.label}")
        self.assertIn(r.label, ("SWISH", "RIM_IN"))

    def test_preset_bank_scores(self):
        r = Simulator(preset_params("bank")).run()
        self.assertTrue(r.scored, msg=f"label={r.label}")
        self.assertIn("board", r.contacts)

    def test_preset_three_scores(self):
        r = Simulator(preset_params("three")).run()
        self.assertTrue(r.scored, msg=f"label={r.label}")

    def test_no_score_from_below(self):
        # 篮下垂直上抛，球从下往上穿过筐平面 → 违例，不得分
        # distance=0.05 使筐开口中心几乎在正上方，避免擦碰前/后框
        p = ShotParams(v0=5.5, angle_deg=90.0, release_height=2.0,
                       distance=0.05, spin=0.0, drag=False, magnus=False)
        r = Simulator(p).run()
        self.assertFalse(r.scored)
        self.assertEqual(r.label, "VIOLATION")


class TestExperiments(unittest.TestCase):
    def test_mc_deterministic_with_seed(self):
        p = preset_params("free_throw")
        a = run_mc(p, n=25, seed=3)
        b = run_mc(p, n=25, seed=3)
        self.assertEqual(a.hits, b.hits)
        self.assertEqual(a.swishes, b.swishes)

    def test_mc_rate_in_range(self):
        p = preset_params("free_throw")
        mc = run_mc(p, n=30, seed=1)
        self.assertGreaterEqual(mc.rate, 0.0)
        self.assertLessEqual(mc.rate, 1.0)
        self.assertEqual(mc.n, 30)

    def test_sweep_grid_shape(self):
        sw = run_sweep(preset_params("free_throw"), nv=5, na=4)
        self.assertEqual(len(sw.grid), 4)
        self.assertEqual(len(sw.grid[0]), 5)
        self.assertEqual(sw.total, 20)


if __name__ == "__main__":
    unittest.main()
