"""规则变体池：每一回合一个新玩法（风 / 移动筐 / 小筐 / 月球重力…）。

变体只改物理参数与画面标记，玩家无法控制环境——玩家只控制动作参数。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from shotlab.params import ShotParams


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    icon: str
    desc: str
    stars: int                      # 难度 1~4
    wind_visual: float = 0.0        # 画面风粒子强度/方向（m/s²，仅供显示）
    moving: bool = False            # 画面是否播放篮筐移动
    fog: bool = False               # 浓雾：无预览、飞行不可见
    apply: object = None            # Callable(ShotParams, rng) -> ShotParams

    def build(self, p: ShotParams, rng: random.Random) -> ShotParams:
        return self.apply(p, rng) if self.apply else p


def _tailwind(p, rng):
    return p.with_(wind_ax=+1.2)


def _headwind(p, rng):
    return p.with_(wind_ax=-1.2)


def _gale(p, rng):
    return p.with_(wind_ax=rng.choice([-2.2, 2.2]))


def _moving(p, rng):
    return p.with_(rim_amp=0.18, rim_period=rng.uniform(2.2, 3.2),
                   rim_phase=rng.uniform(0, 2 * math.pi))


def _small_rim(p, rng):
    return p.with_(rim_radius=p.rim_radius * 0.72)


def _moon(p, rng):
    return p.with_(gravity=p.gravity * 0.55)


def _heavy(p, rng):
    return p.with_(ball_radius=p.ball_radius * 1.25, ball_mass=p.ball_mass * 1.2)


def _deep(p, rng):
    return p.with_(distance=p.distance * 1.35)


def _fog(p, rng):
    return p


RULES = [
    Rule("tailwind", "顺风", "🌬", "风向篮筐吹 +1.2 m/s²", 1,
         wind_visual=1.2, apply=_tailwind),
    Rule("headwind", "逆风", "🌫", "风往回吹 -1.2 m/s²，加力！", 2,
         wind_visual=-1.2, apply=_headwind),
    Rule("gale", "疾风", "🌪", "风力 ±2.2 m/s²，方向随机", 3,
         apply=_gale),
    Rule("moving", "移动篮筐", "🎪", "篮筐（含篮板）水平往复 ±0.18 m", 3,
         moving=True, apply=_moving),
    Rule("small_rim", "小筐", "🧷", "筐内径 ×0.72", 3, apply=_small_rim),
    Rule("moon", "月球重力", "🌙", "g × 0.55，球会飘", 2, apply=_moon),
    Rule("heavy", "铅球", "🏋", "球更大更沉（阻力剧增）", 2, apply=_heavy),
    Rule("deep", "压哨远射", "📏", "距离 ×1.35", 2, apply=_deep),
    Rule("fog", "浓雾", "🌫", "无预览、飞行不可见，只有结果", 3, fog=True),
    Rule("double", "双重奏", "🎭", "随机叠加两个其他变体", 4, apply=None),
]


RULE_BY_ID = {r.id: r for r in RULES}
EASY_RULES = [r for r in RULES if r.stars <= 2 and r.id != "double"]


def build_double(p: ShotParams, rng: random.Random) -> tuple:
    """「双重奏」：随机叠两个非 double 变体。返回 (params, [子规则…])。"""
    subs = rng.sample([r for r in RULES if r.id != "double"], 2)
    for r in subs:
        p = r.build(p, rng)
    return p, subs


def draw_rule(rng: random.Random, round_idx: int, exclude: set) -> Rule:
    """单人模式抽规则：第 1 回合必抽 ★~★★，之后按难度加权。"""
    pool = [r for r in RULES if r.id not in exclude]
    if round_idx == 0:
        pool = [r for r in pool if r.stars <= 2]
    weights = [1.0 / (r.stars ** 1.2) for r in pool]
    return rng.choices(pool, weights=weights, k=1)[0]
