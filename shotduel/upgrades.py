"""本局 Roguelike 升级池：升级改变下一回合的物理/执行条件，而不是凭空增加命中率。"""
from __future__ import annotations

from dataclasses import dataclass

from shotlab.params import ShotParams


@dataclass(frozen=True)
class Upgrade:
    id: str
    name: str
    icon: str
    desc: str
    max_stacks: int = 3
    noise_mul: float = 1.0
    score_mul: float = 1.0
    spin_bonus: float = 0.0
    rim_mul: float = 1.0
    wind_mul: float = 1.0
    height_bonus: float = 0.0
    hp_gain: int = 0
    coin_gain: int = 0

    def apply(self, p: ShotParams, stacks: int = 1) -> ShotParams:
        return p.with_(
            spin=p.spin + self.spin_bonus * stacks,
            rim_radius=p.rim_radius * (self.rim_mul ** stacks),
            wind_ax=p.wind_ax * (self.wind_mul ** stacks),
            release_height=p.release_height + self.height_bonus * stacks,
        )


UPGRADES = [
    Upgrade("steady_hand", "稳定器", "🎯", "执行噪声 ×0.88", noise_mul=0.88),
    Upgrade("hot_streak", "热手", "🔥", "得分倍率 +12%", score_mul=1.12),
    Upgrade("spin_master", "旋转大师", "🌀", "基础后旋 +1.5 rad/s", spin_bonus=1.5),
    Upgrade("soft_rim", "柔和篮筐", "⭕", "篮筐有效半径 +4%", rim_mul=1.04),
    Upgrade("windbreaker", "风阻外套", "🧥", "风效应 ×0.80", wind_mul=0.80),
    Upgrade("high_release", "高点出手", "⬆️", "出手高度 +8 cm", height_bonus=0.08),
    Upgrade("insurance", "保险", "❤️", "立即回复 1 点生命", hp_gain=1, max_stacks=2),
    Upgrade("sponsor", "街球赞助", "🪙", "立即获得 3 枚筹码", coin_gain=3, max_stacks=3),
]


UPGRADE_BY_ID = {u.id: u for u in UPGRADES}
