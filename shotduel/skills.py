"""变数卡池：每回合抽 1 张，有好有坏——赌博的乐趣。

技能只改"执行条件"（几何/噪声/倍率），不改命中率数字，符合"物理即一切"的世界观。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from shotlab.params import ShotParams


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    icon: str
    kind: str            # buff / bane / mix
    desc: str
    apply: object = None                  # Callable(ShotParams, rng) -> ShotParams
    noise_scale: float = 1.0              # 执行噪声倍率（手抖/手稳）
    score_mult: float = 1.0               # 得分倍率
    miss_penalty: float = 0.0             # 不中额外扣分
    preview: bool = False                 # 显示预测弹道
    magnet: float = 0.0                   # 磁性篮筐吸附 m/s²

    def build(self, p: ShotParams, rng: random.Random) -> ShotParams:
        if self.magnet:
            p = p.with_(magnet=self.magnet)
        return self.apply(p, rng) if self.apply else p


def _lucky(p, rng):
    return p.with_(distance=max(1.5, p.distance - 0.5))


def _retreat(p, rng):
    return p.with_(distance=p.distance + 0.5)


def _gale_boost(p, rng):
    if abs(p.wind_ax) > 1e-6:
        return p.with_(wind_ax=p.wind_ax * 1.8)
    return p.with_(wind_ax=rng.choice([-0.5, 0.5]))


def _spin_up(p, rng):
    return p.with_(spin=p.spin + 3.0)


SKILLS = [
    Skill("lucky_step", "幸运一步", "🎲", "buff", "出手点前移 0.5 m（更近）",
          apply=_lucky),
    Skill("retreat", "后撤一步", "↩️", "bane", "出手点后移 0.5 m", apply=_retreat),
    Skill("gale_boost", "疾风加持", "🌀", "bane", "风力 ×1.8（无风时来一阵小风）",
          apply=_gale_boost),
    Skill("steady", "稳如老狗", "🎯", "buff", "出手噪声 -60%", noise_scale=0.4),
    Skill("slippery", "打滑的手", "🐛", "bane", "出手噪声 +80%", noise_scale=1.8),
    Skill("eye", "物理之眼", "👁", "buff", "本回合显示预测弹道", preview=True),
    Skill("gambler", "赌徒", "💰", "mix", "得分 ×2，不中扣 2 分",
          score_mult=2.0, miss_penalty=2),
    Skill("spin_up", "后旋加持", "🏃", "buff", "后旋 +3 rad/s（弹道更稳）",
          apply=_spin_up),
    Skill("heavy_ball", "沉重之球", "🦾", "mix", "球质量 ×1.3：更抗风但更难投远",
          apply=lambda p, rng: p.with_(ball_mass=p.ball_mass * 1.3)),
    Skill("magnet", "磁性篮筐", "🧲", "buff", "偏心 ≤8cm 时轻微吸附入筐",
          magnet=1.5),
]

SKILL_BY_ID = {s.id: s for s in SKILLS}


def draw_skill(rng: random.Random) -> Skill:
    return rng.choice(SKILLS)
