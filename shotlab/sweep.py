"""参数扫描：速度 × 仰角 网格上的命中/失手地图。"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from .engine import Simulator
from .params import ShotParams


@dataclass
class SweepResult:
    v_range: list
    a_range: list
    grid: list  # grid[i][j]，i 对应 a_range（仰角），j 对应 v_range（速度）
    hits: int

    @property
    def total(self) -> int:
        return len(self.a_range) * len(self.v_range)


def run_sweep(params: ShotParams, v_min=5.5, v_max=8.5, nv=24,
              a_min=42.0, a_max=62.0, na=14, per_cell: int = 1,
              seed: int = 7, sigmas: dict | None = None) -> SweepResult:
    """per_cell=1 时每格跑一次确定性模拟；>1 时每格做微型蒙特卡洛。"""
    v_range = [v_min + (v_max - v_min) * j / (nv - 1) for j in range(nv)]
    a_range = [a_min + (a_max - a_min) * i / (na - 1) for i in range(na)]
    grid = [[0] * nv for _ in range(na)]
    hits = 0
    for i, ang in enumerate(a_range):
        for j, v in enumerate(v_range):
            if per_cell <= 1:
                r = Simulator(params.with_(v0=v, angle_deg=ang)).run()
                ok = r.scored
            else:
                rng = random.Random(seed * 1000003 + i * 1000 + j)
                ok = False
                for _ in range(per_cell):
                    q = params.with_(
                        v0=max(1.0, rng.gauss(v, 0.12)),
                        angle_deg=rng.gauss(ang, 0.8),
                    )
                    if Simulator(q).run().scored:
                        ok = True
                        break
            grid[i][j] = 1 if ok else 0
            hits += ok
    return SweepResult(v_range=v_range, a_range=a_range, grid=grid, hits=hits)


def render_sweep_text(sw: SweepResult) -> str:
    na, nv = len(sw.a_range), len(sw.v_range)
    lines = ["  ── 参数扫描：命中=█ 失手=· （行=仰角，列=出手速度） " + "─" * 8]

    # 速度刻度（每 ~6 列一个）
    tick = [" "] * nv
    step = max(1, nv // 6)
    for j in range(0, nv, step):
        s = f"{sw.v_range[j]:.1f}"
        for k, ch in enumerate(s):
            if j + k < nv:
                tick[j + k] = ch
    head = "          " + "".join(tick)
    lines.append(head + "   v0 m/s")

    for i in range(na - 1, -1, -1):
        row = "".join("█" if c else "·" for c in sw.grid[i])
        lines.append(f"  {sw.a_range[i]:5.1f}°  {row}")
    foot = [" "] * nv
    for j in range(0, nv, step):
        foot[j] = "|"
    lines.append("          " + "".join(foot))

    best = None
    for i in range(na):
        for j in range(nv):
            if sw.grid[i][j] and (best is None or sw.v_range[j] < best[0]):
                best = (sw.v_range[j], sw.a_range[i])
    lines.append(
        f"  命中格: {sw.hits}/{sw.total}"
        + (f"   最省力命中点 ≈ v0={best[0]:.2f} m/s @ {best[1]:.1f}°" if best else "")
    )
    return "\n".join(lines)
