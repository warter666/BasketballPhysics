"""对局流程（GUI 无关）：单人生存赛季 / 双人同屏对决。

GUI 与 CLI 都构建在这些 Session 之上；Session 只负责：
抽规则 → 技能 → 接收玩家动作参数（叠加执行噪声）→ 模拟 → 计分 → 推进。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from shotlab.engine import Simulator
from shotlab.params import ShotParams

from .rules import EASY_RULES, RULES, Rule, build_double, draw_rule
from .scoring import ShotScore, score_shot
from .skills import Skill, draw_skill

# 执行噪声（策划书 §6：技能改变的是执行误差）
SIGMA_V0 = 0.10       # m/s
SIGMA_ANGLE = 0.7     # °
SIGMA_SPIN = 0.4      # rad/s

SOLO_DISTANCES = [4.2, 5.0, 5.8, 6.6, 7.24]
DUEL_DISTANCES = [4.19, 4.8, 5.5, 6.2, 6.8, 7.24]


@dataclass
class RoundState:
    index: int
    rule: Rule
    subs: list                    # 「双重奏」的子规则
    base_params: ShotParams       # 规则构建后（未含个人技能）
    skills: list                  # 每位玩家的变数卡
    params_by_player: list        # 含个人技能的最终参数
    noise: list                   # 执行噪声倍率
    preview: list                 # 是否显示预测弹道
    score_mult: list
    miss_penalty: list
    results: list = field(default_factory=list)
    scores: list = field(default_factory=list)

    @property
    def n_players(self) -> int:
        return len(self.skills)

    @property
    def rule_desc(self) -> str:
        if self.subs:
            return f"{self.rule.icon} {self.rule.name}：{' + '.join(s.desc for s in self.subs)}"
        return f"{self.rule.icon} {self.rule.name}：{self.rule.desc}"


class SoloSession:
    """单人 · 生存赛季：5 回合，规则随机，连击倍率。"""

    def __init__(self, seed=None, n_rounds=5):
        self.rng = random.Random(seed)
        self.n_rounds = n_rounds
        self.round_idx = -1
        self.round: RoundState | None = None
        self.streak = 0
        self.best_streak = 0
        self.total = 0
        self.history = []          # (rule_name, skill_name, pts, stars, title)
        self.used_rules = set()
        self.finished = False

    def start_round(self) -> RoundState:
        self.round_idx += 1
        rule = draw_rule(self.rng, self.round_idx, self.used_rules)
        subs = []
        if rule.id == "double":
            base, subs = build_double(
                ShotParams(release_height=2.0,
                           distance=SOLO_DISTANCES[min(self.round_idx, 4)]),
                self.rng)
            self.used_rules.update(r.id for r in subs)
        else:
            base = rule.build(
                ShotParams(release_height=2.0,
                           distance=SOLO_DISTANCES[min(self.round_idx, 4)]),
                self.rng)
            self.used_rules.add(rule.id)
        skill = draw_skill(self.rng)
        self.round = RoundState(
            index=self.round_idx, rule=rule, subs=subs, base_params=base,
            skills=[skill],
            params_by_player=[skill.build(base, self.rng)],
            noise=[skill.noise_scale], preview=[skill.preview],
            score_mult=[skill.score_mult], miss_penalty=[skill.miss_penalty],
        )
        return self.round

    def shoot(self, v0: float, angle_deg: float, spin: float,
              player: int = 0, rim_phase: float | None = None):
        r = self.round
        ns = r.noise[player]
        actual_v0 = v0 + self.rng.gauss(0.0, SIGMA_V0 * ns)
        actual_angle = angle_deg + self.rng.gauss(0.0, SIGMA_ANGLE * ns)
        actual_spin = spin + self.rng.gauss(0.0, SIGMA_SPIN * ns)
        params = r.params_by_player[player].with_(
            v0=actual_v0, angle_deg=actual_angle, spin=actual_spin)
        if rim_phase is not None and params.rim_period > 0:
            params = params.with_(rim_phase=rim_phase)
        result = Simulator(params).run()
        score: ShotScore
        if result.scored:
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
            bonus = min(self.streak - 1, 2)
        else:
            self.streak = 0
            bonus = 0
        score = score_shot(result, score_mult=r.score_mult[player],
                           miss_penalty=r.miss_penalty[player],
                           streak_bonus=bonus)
        r.results.append(result)
        r.scores.append(score)
        self.total += score.pts
        self.history.append((r.rule.name, r.skills[player].name,
                             score.pts, score.stars, score.title))
        if self.round_idx >= self.n_rounds - 1:
            self.finished = True
        return result, score

    def summary(self) -> str:
        lines = [f"  生存赛季结束 · 总分 {self.total} · 最高连击 {self.best_streak}"]
        for i, (rule, skill, pts, stars, title) in enumerate(self.history, 1):
            lines.append(f"  R{i} {'★' * stars:<3} {title:<10} "
                         f"+{pts:>3} 分   [{rule} · {skill}]")
        return "\n".join(lines)


class DuelSession:
    """双人 · 同屏对决：先拿 3 个回合胜场；输家挑场地；篮筐会"记住"。"""

    WIN_TARGET = 3

    def __init__(self, seed=None, names=("玩家 1", "玩家 2")):
        self.rng = random.Random(seed)
        self.names = list(names)
        self.round_idx = 0
        self.round: RoundState | None = None
        self.round_wins = [0, 0]
        self.total_pts = [0, 0]
        self.hoop_shift = 0.0          # 篮筐漂移（球进一次就动）
        self.next_chooser: int | None = None   # 输家挑场地；None=首局随机
        self.offers: list[Rule] = []
        self.champion: int | None = None
        self.last_round_text = ""

    # ------------------------------------------------------------------ 回合
    def need_rule_pick(self) -> bool:
        return self.round is None and self.next_chooser is not None

    def prepare_offers(self) -> list[Rule]:
        self.offers = self.rng.sample(RULES, 3)
        return self.offers

    def _build_round(self, rule: Rule) -> RoundState:
        subs = []
        base_d = DUEL_DISTANCES[min(self.round_idx, len(DUEL_DISTANCES) - 1)]
        if rule.id == "double":
            base, subs = build_double(
                ShotParams(release_height=2.0,
                           distance=base_d + self.hoop_shift), self.rng)
        else:
            base = rule.build(
                ShotParams(release_height=2.0,
                           distance=base_d + self.hoop_shift), self.rng)
        skills = [draw_skill(self.rng), draw_skill(self.rng)]
        self.round = RoundState(
            index=self.round_idx, rule=rule, subs=subs, base_params=base,
            skills=skills,
            params_by_player=[s.build(base, self.rng) for s in skills],
            noise=[s.noise_scale for s in skills],
            preview=[s.preview for s in skills],
            score_mult=[s.score_mult for s in skills],
            miss_penalty=[s.miss_penalty for s in skills],
        )
        return self.round

    def start_round(self) -> RoundState:
        """首局（或无需挑选时）直接开一局：随机简单规则。"""
        if self.next_chooser is None:
            rule = self.rng.choice(EASY_RULES)
            return self._build_round(rule)
        raise RuntimeError("需要先由输家挑场地：pick_rule()")

    def pick_rule(self, idx: int) -> RoundState:
        rule = self.offers[idx]
        self.offers = []
        return self._build_round(rule)

    # ------------------------------------------------------------------ 出手
    def shoot(self, v0: float, angle_deg: float, spin: float,
              player: int = 0, rim_phase: float | None = None):
        r = self.round
        if len(r.results) != player:
            raise RuntimeError("轮次错误：还没到这位玩家出手")
        ns = r.noise[player]
        actual_v0 = v0 + self.rng.gauss(0.0, SIGMA_V0 * ns)
        actual_angle = angle_deg + self.rng.gauss(0.0, SIGMA_ANGLE * ns)
        actual_spin = spin + self.rng.gauss(0.0, SIGMA_SPIN * ns)
        params = r.params_by_player[player].with_(
            v0=actual_v0, angle_deg=actual_angle, spin=actual_spin)
        if rim_phase is not None and params.rim_period > 0:
            params = params.with_(rim_phase=rim_phase)
        result = Simulator(params).run()
        score = score_shot(result, score_mult=r.score_mult[player],
                           miss_penalty=r.miss_penalty[player])
        r.results.append(result)
        r.scores.append(score)
        self.total_pts[player] += score.pts
        if result.scored:
            # 篮筐会"记住"：每次命中，筐基座漂移一段
            self.hoop_shift += self.rng.uniform(0.03, 0.08)
        return result, score

    def both_shot(self) -> bool:
        return self.round is not None and len(self.round.results) == 2

    def conclude_round(self) -> str:
        """双方都已出手：结算回合，返回播报文本。"""
        r = self.round
        p0, p1 = r.scores[0].pts, r.scores[1].pts
        if p0 > p1:
            winner = 0
        elif p1 > p0:
            winner = 1
        else:
            winner = None
        if winner is None:
            self.next_chooser = self.rng.choice([0, 1])
            text = f"  平局（{p0}:{p1}）！本回合无人得分，{self.names[self.next_chooser]} 挑场地"
        else:
            self.round_wins[winner] += 1
            loser = 1 - winner
            self.next_chooser = loser
            text = (f"  {self.names[winner]} 拿下本回合（{p0}:{p1}）"
                    f"  回合胜场 {self.round_wins[0]}:{self.round_wins[1]}"
                    f"\n  → 输家 {self.names[loser]} 挑选下一块场地")
            if self.round_wins[winner] >= self.WIN_TARGET:
                self.champion = winner
        self.last_round_text = text
        self.round_idx += 1
        self.round = None
        return text

    @property
    def match_over(self) -> bool:
        return self.champion is not None
