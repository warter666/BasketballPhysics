"""物理计分：偏心 + 入射角 + 接触情况 → 分数。实验室读数就是计分板。"""

from __future__ import annotations

from dataclasses import dataclass

# PERFECT 窗口（策划书 §5；由 Monte Carlo 标定管线监控）
PERFECT_OFFSET = 0.03      # m，|偏心| ≤ 3cm
PERFECT_ANGLE = (40.0, 55.0)  # 入射角窗口


@dataclass
class ShotScore:
    pts: int
    stars: int            # 3=PERFECT 2=空心 1=进筐 0=不中
    title: str            # 结果称号
    breakdown: list       # 结算行（偏心/入射角/倍率…）


def score_shot(result, score_mult: float = 1.0, miss_penalty: float = 0.0,
               streak_bonus: int = 0) -> ShotScore:
    """把一次模拟结果折算成分数。result: shotlab.engine.ShotResult"""
    lines = []
    if not result.scored:
        pts = -int(miss_penalty)
        lines.append(f"不中 ✗（{result.label} {result.label_cn}）")
        if miss_penalty:
            lines.append(f"赌徒代价 -{int(miss_penalty)} 分")
        return ShotScore(pts=pts, stars=0, title="MISS", breakdown=lines)

    rel = abs(result.crossed_rel or 0.0)
    ang = result.entry_angle_deg or 0.0
    lines.append(f"偏心 {rel * 100:.1f} cm · 入射角 {ang:.1f}° · "
                 f"入口 {result.entry_speed:.1f} m/s")

    if rel <= PERFECT_OFFSET and PERFECT_ANGLE[0] <= ang <= PERFECT_ANGLE[1]:
        base, stars, title = 3, 3, "PERFECT!"
        lines.append("死点入筐 + 黄金入射角 → 满分！")
    elif not result.contacts:
        base, stars, title = 2, 2, "SWISH 空心"
        lines.append("全程无接触，干净利落")
    else:
        base, stars, title = 1, 1, "进筐"
        if "board" in result.contacts:
            lines.append("打板入筐")
        else:
            lines.append("弹框入筐")

    pts = base
    if streak_bonus > 0:
        pts += streak_bonus
        lines.append(f"连击加成 +{streak_bonus}")
    if score_mult != 1.0:
        pts = int(round(pts * score_mult))
        lines.append(f"得分倍率 ×{score_mult:g} → {pts} 分")
    return ShotScore(pts=pts, stars=stars, title=title, breakdown=lines)
