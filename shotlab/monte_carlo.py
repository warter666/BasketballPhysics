"""蒙特卡洛命中率实验：给名义出手叠加人类级别的执行噪声，统计命中率。"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from .engine import Simulator
from .params import ShotParams

# 默认执行噪声（可视为一名训练有素的射手的手感波动）
DEFAULT_SIGMAS = {
    "v0": 0.12,             # m/s
    "angle_deg": 0.8,       # °
    "release_height": 0.04, # m
    "spin": 0.5,            # rad/s
}


@dataclass
class MCResult:
    n: int
    hits: int
    swishes: int
    sigmas: dict
    result_labels: dict

    @property
    def rate(self) -> float:
        return self.hits / self.n

    @property
    def swish_rate(self) -> float:
        return self.swishes / self.n


def run_mc(params: ShotParams, n: int = 300, seed: int = 42,
           sigmas: dict | None = None) -> MCResult:
    sig = {**DEFAULT_SIGMAS, **(sigmas or {})}
    rng = random.Random(seed)
    hits = swishes = 0
    labels: dict[str, int] = {}
    for _ in range(n):
        q = params.with_(
            v0=max(1.0, rng.gauss(params.v0, sig["v0"])),
            angle_deg=rng.gauss(params.angle_deg, sig["angle_deg"]),
            release_height=max(0.3, rng.gauss(params.release_height, sig["release_height"])),
            spin=rng.gauss(params.spin, sig["spin"]),
        )
        r = Simulator(q).run()
        hits += r.scored
        swishes += r.label == "SWISH"
        labels[r.label] = labels.get(r.label, 0) + 1
    return MCResult(n=n, hits=hits, swishes=swishes, sigmas=sig, result_labels=labels)
