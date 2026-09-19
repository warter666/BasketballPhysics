"""对局流程：单人生存 Roguelike / 双人同屏对决。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from shotlab.engine import Simulator
from shotlab.params import ShotParams

from .rules import EASY_RULES, RULES, Rule, build_double, draw_rule
from .scoring import ShotScore, score_shot
from .skills import Skill, draw_skill
from .upgrades import UPGRADE_BY_ID, UPGRADES, Upgrade

SIGMA_V0 = 0.10
SIGMA_ANGLE = 0.7
SIGMA_SPIN = 0.4

SOLO_DISTANCES = [4.2, 4.8, 5.3, 5.8, 6.2, 6.6, 6.9, 7.1, 7.24, 7.5]
DUEL_DISTANCES = [4.19, 4.8, 5.5, 6.2, 6.8, 7.24]


@dataclass
class RoundState:
    index: int
    rule: Rule
    subs: list
    base_params: ShotParams
    skills: list
    params_by_player: list
    noise: list
    preview: list
    score_mult: list
    miss_penalty: list
    boss: bool = False
    results: list = field(default_factory=list)
    scores: list = field(default_factory=list)

    @property
    def n_players(self) -> int:
        return len(self.skills)

    @property
    def rule_desc(self) -> str:
        prefix = "👑 BOSS · " if self.boss else ""
        if self.subs:
            return f"{prefix}{self.rule.icon} {self.rule.name}：{' + '.join(s.desc for s in self.subs)}"
        return f"{prefix}{self.rule.icon} {self.rule.name}：{self.rule.desc}"


class SoloSession:
    """单人 · 10 节点 Roguelike：生命、筹码、构筑、Boss 与三选一升级。"""

    def __init__(self, seed=None, n_rounds=10):
        self.rng = random.Random(seed)
        self.n_rounds = n_rounds
        self.round_idx = -1
        self.round: RoundState | None = None
        self.streak = 0
        self.best_streak = 0
        self.total = 0
        self.hp = 3
        self.max_hp = 3
        self.coins = 0
        self.upgrades: list[str] = []
        self.upgrade_counts: dict[str, int] = {}
        self.offers: list[Upgrade] = []
        self.awaiting_upgrade = False
        self.history = []
        self.used_rules = set()
        self.finished = False
        self.won = False

    @property
    def build_text(self) -> str:
        if not self.upgrades:
            return "尚未构筑"
        return " · ".join(
            f"{UPGRADE_BY_ID[i].icon}{UPGRADE_BY_ID[i].name}"
            + (f"×{self.upgrade_counts[i]}" if self.upgrade_counts[i] > 1 else "")
            for i in dict.fromkeys(self.upgrades)
        )

    @property
    def boss_round(self) -> bool:
        return self.round_idx in (4, 9)

    def _apply_build(self, p: ShotParams) -> ShotParams:
        for uid in self.upgrades:
            u = UPGRADE_BY_ID[uid]
            p = u.apply(p, 1)
        return p

    def _build_noise(self, skill: Skill) -> float:
        n = skill.noise_scale
        for uid in self.upgrades:
            n *= UPGRADE_BY_ID[uid].noise_mul
        return n

    def _build_score_mult(self, skill: Skill) -> float:
        m = skill.score_mult
        for uid in self.upgrades:
            m *= UPGRADE_BY_ID[uid].score_mul
        return m

    def start_round(self) -> RoundState:
        if self.finished:
            raise RuntimeError("本局已经结束")
        if self.round is not None:
            raise RuntimeError("当前回合尚未完成")
        if self.awaiting_upgrade:
            raise RuntimeError("请先选择本回合升级")

        self.round_idx += 1
        rule = draw_rule(self.rng, self.round_idx, self.used_rules)
        subs = []
        base = ShotParams(
            release_height=2.0,
            distance=SOLO_DISTANCES[min(self.round_idx, len(SOLO_DISTANCES) - 1)],
        )
        if rule.id == "double":
            base, subs = build_double(base, self.rng)
            self.used_rules.update(r.id for r in subs)
        else:
            base = rule.build(base, self.rng)
            self.used_rules.add(rule.id)

        # 两个 Boss 节点：强制叠加压力，但仍由同一个物理引擎处理。
        boss = self.boss_round
        if boss:
            if self.round_idx == 4:
                base = base.with_(rim_radius=base.rim_radius * 0.78)
            else:
                base = base.with_(distance=base.distance * 1.12,
                                  rim_radius=base.rim_radius * 0.82)

        skill = draw_skill(self.rng)
        final_base = self._apply_build(base)
        self.round = RoundState(
            index=self.round_idx,
            rule=rule,
            subs=subs,
            base_params=final_base,
            skills=[skill],
            params_by_player=[skill.build(final_base, self.rng)],
            noise=[self._build_noise(skill)],
            preview=[skill.preview],
            score_mult=[self._build_score_mult(skill)],
            miss_penalty=[skill.miss_penalty],
            boss=boss,
        )
        return self.round

    def _reward(self, score: ShotScore):
        # 得分直接转成少量筹码；Perfect 额外奖励，让高水平打法支持后续构筑。
        self.coins += max(0, score.pts)
        if score.stars == 3:
            self.coins += 2

    def _prepare_upgrades(self):
        available = [
            u for u in UPGRADES
            if self.upgrade_counts.get(u.id, 0) < u.max_stacks
        ]
        if not available:
            self.offers = []
            self.awaiting_upgrade = False
            return
        self.offers = self.rng.sample(available, min(3, len(available)))
        self.awaiting_upgrade = True

    def choose_upgrade(self, idx: int) -> Upgrade:
        if not self.awaiting_upgrade:
            raise RuntimeError("当前没有升级选择")
        if not (0 <= idx < len(self.offers)):
            raise IndexError("升级选项不存在")
        u = self.offers[idx]
        self.upgrades.append(u.id)
        self.upgrade_counts[u.id] = self.upgrade_counts.get(u.id, 0) + 1
        if u.hp_gain:
            self.hp = min(self.max_hp, self.hp + u.hp_gain)
        if u.coin_gain:
            self.coins += u.coin_gain
        self.offers = []
        self.awaiting_upgrade = False
        return u

    def shoot(self, v0: float, angle_deg: float, spin: float,
               player: int = 0, rim_phase: float | None = None):
        r = self.round
        if r is None:
            raise RuntimeError("还没有开始回合")
        ns = r.noise[player]
        actual_v0 = v0 + self.rng.gauss(0.0, SIGMA_V0 * ns)
        actual_angle = angle_deg + self.rng.gauss(0.0, SIGMA_ANGLE * ns)
        actual_spin = spin + self.rng.gauss(0.0, SIGMA_SPIN * ns)
        params = r.params_by_player[player].with_(
            v0=actual_v0, angle_deg=actual_angle, spin=actual_spin)
        if rim_phase is not None and params.rim_period > 0:
            params = params.with_(rim_phase=rim_phase)
        result = Simulator(params).run()

        if result.scored:
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
            bonus = min(self.streak - 1, 2)
        else:
            self.streak = 0
            bonus = 0
            self.hp -= 1

        # 构筑中的“热手”会让得分更值钱，但不会改变物理命中判定。
        score = score_shot(
            result,
            score_mult=r.score_mult[player],
            miss_penalty=r.miss_penalty[player],
            streak_bonus=bonus,
        )
        r.results.append(result)
        r.scores.append(score)
        self.total += score.pts
        self._reward(score)
        self.history.append((
            r.rule.name, r.skills[player].name, score.pts,
            score.stars, score.title, self.hp, self.coins, r.boss
        ))

        if self.hp <= 0:
            self.finished = True
            self.won = False
        elif self.round_idx >= self.n_rounds - 1:
            self.finished = True
            self.won = True
        else:
            self._prepare_upgrades()
        self.round = None
        return result, score

    def summary(self) -> str:
        perf = sum(1 for h in self.history if h[3] == 3)
        swish = sum(1 for h in self.history if h[3] == 2)
        status = "通关" if self.won else "体力耗尽"
        lines = [
            f"  Roguelike 赛季{status} · 总分 {self.total} · "
            f"最高连击 {self.best_streak}",
            f"  生命 {self.hp}/{self.max_hp} · 筹码 {self.coins} · "
            f"PERFECT {perf} · 空心 {swish}",
            f"  构筑：{self.build_text}",
        ]
        for i, h in enumerate(self.history, 1):
            rule, skill, pts, stars, title, hp, coins, boss = h
            tag = " BOSS" if boss else ""
            lines.append(
                f"  R{i}{tag} {'★' * stars:<3} {title:<10} "
                f"{pts:+3} 分 · HP {hp} · 🪙 {coins} [{rule} · {skill}]"
            )
        return "\n".join(lines)


class DuelSession:
    """双人 · 同屏对决：先拿 3 个回合胜场；输家挑场地。"""

    WIN_TARGET = 3

    def __init__(self, seed=None, names=("玩家 1", "玩家 2")):
        self.rng = random.Random(seed)
        self.names = list(names)
        self.round_idx = 0
        self.round: RoundState | None = None
        self.round_wins = [0, 0]
        self.total_pts = [0, 0]
        self.hoop_shift = 0.0
        self.next_chooser: int | None = None
        self.offers: list[Rule] = []
        self.champion: int | None = None
        self.last_round_text = ""

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
                ShotParams(release_height=2.0, distance=base_d + self.hoop_shift),
                self.rng)
        else:
            base = rule.build(
                ShotParams(release_height=2.0, distance=base_d + self.hoop_shift),
                self.rng)
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
        if self.next_chooser is None:
            rule = self.rng.choice(EASY_RULES)
            return self._build_round(rule)
        raise RuntimeError("需要先由输家挑场地：pick_rule()")

    def pick_rule(self, idx: int) -> RoundState:
        rule = self.offers[idx]
        self.offers = []
        return self._build_round(rule)

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
            self.hoop_shift += self.rng.uniform(0.03, 0.08)
        return result, score

    def both_shot(self) -> bool:
        return self.round is not None and len(self.round.results) == 2

    def conclude_round(self) -> str:
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
            text = f"  平局（{p0}:{p1}）！{self.names[self.next_chooser]} 挑场地"
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
