"""网格搜索经典出手的命中参数，供 presets 与文档使用。

用法: python examples/tune.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shotlab.engine import Simulator  # noqa: E402
from shotlab.params import ShotParams  # noqa: E402


def tune(name, distance, height, spin, v_lo, v_hi, a_lo, a_hi,
         want_board=False, step_v=0.05, step_a=0.5):
    best = None
    v = v_lo
    while v <= v_hi + 1e-9:
        a = a_lo
        while a <= a_hi + 1e-9:
            p = ShotParams(v0=round(v, 2), angle_deg=round(a, 1),
                           release_height=height, distance=distance, spin=spin)
            r = Simulator(p).run()
            if r.scored and abs((r.crossed_x or 0) - distance) < 0.07:
                board_ok = ("board" in r.contacts) == want_board
                entry = r.entry_angle_deg or 0.0
                forward_ok = want_board or 25.0 <= entry <= 75.0
                if not (board_ok and forward_ok):
                    a += step_a
                    continue
                clean = 0.0 if r.label in ("SWISH", "BANK_IN") else 1.0
                margin = abs((r.crossed_x or distance) - distance)
                score = clean + margin
                if best is None or score < best[0]:
                    best = (score, p, r)
            a += step_a
        v += step_v
    if best is None:
        print(f"{name}: 未找到命中参数，请扩大搜索范围")
        return
    _, p, r = best
    print(f"{name}: v0={p.v0:.2f}  angle={p.angle_deg:.1f}°  → {r.label} "
          f"(入口 {r.entry_speed:.1f} m/s @ {r.entry_angle_deg:.1f}°, "
          f"偏心 {r.crossed_x - distance:+.3f} m)")


if __name__ == "__main__":
    tune("free_throw", distance=4.19, height=2.00, spin=6.0,
         v_lo=6.5, v_hi=8.0, a_lo=46.0, a_hi=58.0)
    tune("bank", distance=3.60, height=2.00, spin=5.0,
         v_lo=5.5, v_hi=7.5, a_lo=48.0, a_hi=64.0, want_board=True)
    tune("three", distance=7.24, height=2.20, spin=7.0,
         v_lo=8.8, v_hi=10.2, a_lo=44.0, a_hi=56.0)
