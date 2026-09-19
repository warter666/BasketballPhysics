"""SHOT DUEL 对局逻辑测试：计分 / 技能 / 规则 / 单人与双人流程。"""

import random
import unittest

from shotduel.rules import RULE_BY_ID, draw_rule
from shotduel.scoring import score_shot
from shotduel.session import DuelSession, SoloSession
from shotlab.engine import Simulator
from shotlab.params import ShotParams, preset_params


class TestScoring(unittest.TestCase):
    def test_perfect_window(self):
        # 罚球预设：偏心 0.003m、入射角 41.7°、无接触 → PERFECT 3 分
        r = Simulator(preset_params("free_throw")).run()
        s = score_shot(r)
        self.assertEqual((s.pts, s.stars, s.title), (3, 3, "PERFECT!"))

    def test_bank_scores_one(self):
        r = Simulator(preset_params("bank")).run()
        s = score_shot(r)
        self.assertEqual((s.pts, s.stars), (1, 1))

    def test_miss_zero(self):
        r = Simulator(preset_params("free_throw").with_(angle_deg=20.0)).run()
        s = score_shot(r)
        self.assertEqual(s.pts, 0)

    def test_gambler_multiplier_and_penalty(self):
        made = Simulator(preset_params("free_throw")).run()
        self.assertEqual(score_shot(made, score_mult=2.0).pts, 6)
        missed = Simulator(preset_params("free_throw").with_(angle_deg=15.0)).run()
        self.assertEqual(score_shot(missed, miss_penalty=2).pts, -2)


class TestRulesSkills(unittest.TestCase):
    def test_wind_rules_change_params(self):
        p = ShotParams()
        self.assertGreater(RULE_BY_ID["tailwind"].build(p, random.Random(0)).wind_ax, 0)
        self.assertLess(RULE_BY_ID["headwind"].build(p, random.Random(0)).wind_ax, 0)
        g = RULE_BY_ID["gale"].build(p, random.Random(0))
        self.assertIn(g.wind_ax, (-2.2, 2.2))

    def test_moving_rule(self):
        p = RULE_BY_ID["moving"].build(ShotParams(), random.Random(1))
        self.assertGreater(p.rim_amp, 0)
        self.assertGreater(p.rim_period, 0)

    def test_double_combines_two(self):
        from shotduel.rules import build_double
        p, subs = build_double(ShotParams(), random.Random(2))
        self.assertEqual(len(subs), 2)
        self.assertNotEqual(subs[0].id, subs[1].id)

    def test_skill_distance_shift(self):
        p = ShotParams(distance=4.19)
        self.assertAlmostEqual(
            RULE_BY_ID["tailwind"].build(p, random.Random(0)).distance, 4.19)
        from shotduel.skills import SKILL_BY_ID
        self.assertAlmostEqual(
            SKILL_BY_ID["lucky_step"].build(p, random.Random(0)).distance, 3.69)
        self.assertAlmostEqual(
            SKILL_BY_ID["retreat"].build(p, random.Random(0)).distance, 4.69)

    def test_magnet_flag(self):
        from shotduel.skills import SKILL_BY_ID
        p = SKILL_BY_ID["magnet"].build(ShotParams(), random.Random(0))
        self.assertGreater(p.magnet, 0)


class TestSolo(unittest.TestCase):
    def test_full_run_deterministic(self):
        a, b = SoloSession(seed=7), SoloSession(seed=7)
        for s in (a, b):
            while not s.finished:
                s.start_round()
                # 罚球线附近的保守出手（可能不中，但流程必须走通）
                s.shoot(7.5, 50.0, 6.0)
                if s.awaiting_upgrade:
                    s.choose_upgrade(0)
        self.assertEqual(a.total, b.total)
        self.assertEqual([h[2] for h in a.history], [h[2] for h in b.history])

    def test_streak_and_scores_recorded(self):
        s = SoloSession(seed=1)
        s.start_round()
        r, sc = s.shoot(7.55, 52.5, 6.0)
        self.assertEqual(len(s.history), 1)
        self.assertIn(sc.stars, (0, 1, 2, 3))
        self.assertLessEqual(s.round.index, 4)

    def test_first_round_rule_is_easy(self):
        s = SoloSession(seed=3)
        r = s.start_round()
        self.assertLessEqual(r.rule.stars, 2)

    def test_upgrade_changes_build_and_persists(self):
        s = SoloSession(seed=21)
        s.start_round()
        s.shoot(7.55, 52.5, 6.0)
        self.assertTrue(s.awaiting_upgrade)
        chosen = s.choose_upgrade(0)
        self.assertIn(chosen.id, s.upgrades)
        self.assertFalse(s.awaiting_upgrade)
        self.assertIsNone(s.round)
        r = s.start_round()
        self.assertGreaterEqual(len(s.upgrades), 1)

    def test_run_has_ten_nodes_and_bosses(self):
        s = SoloSession(seed=2, n_rounds=10)
        bosses = []
        while not s.finished:
            r = s.start_round()
            bosses.append(r.boss)
            s.shoot(7.55, 52.5, 6.0)
            if s.awaiting_upgrade:
                s.choose_upgrade(0)
        self.assertEqual(len(s.history), 10)
        self.assertEqual(bosses, [False, False, False, False, True,
                                  False, False, False, False, True])


class TestDuel(unittest.TestCase):
    def _shoot_all(self, sess, v0=7.55, a=52.5, spin=6.0):
        for i in range(2):
            sess.shoot(v0, a, spin, player=i)

    def test_first_round_random_then_loser_picks(self):
        s = DuelSession(seed=5)
        s.start_round()
        self.assertFalse(s.need_rule_pick())
        self._shoot_all(s)
        self.assertTrue(s.both_shot())
        s.conclude_round()
        # 首局结束：输家挑场地（平局则随机）
        self.assertIsNotNone(s.next_chooser)
        offers = s.prepare_offers()
        self.assertEqual(len(offers), 3)
        s.pick_rule(0)
        self._shoot_all(s)
        s.conclude_round()

    def test_hoop_drifts_on_makes(self):
        s = DuelSession(seed=9)
        s.start_round()
        before = s.hoop_shift
        # 用罚球预设参数出手（大概率命中 → 漂移）
        self._shoot_all(s)
        self.assertGreaterEqual(s.hoop_shift, before)

    def test_match_ends_at_three_round_wins(self):
        s = DuelSession(seed=11)
        # 直接灌入 2:2 的回合胜场，从骤死阶段打到分出冠军
        s.round_wins = [2, 2]
        s.next_chooser = 0
        s.round_idx = 4
        for _ in range(30):
            if s.need_rule_pick():
                s.prepare_offers()
                s.pick_rule(0)
            else:
                s.start_round()
            self._shoot_all(s)
            s.conclude_round()
            if s.match_over:
                break
        self.assertIsNotNone(s.champion)

    def test_shoot_order_enforced(self):
        s = DuelSession(seed=13)
        s.start_round()
        with self.assertRaises(RuntimeError):
            s.shoot(7.5, 50, 6, player=1)  # 还没轮到玩家2


if __name__ == "__main__":
    unittest.main()
