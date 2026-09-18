"""matplotlib 绘图（可选依赖）。"""

from __future__ import annotations

from .constants import BOARD_BOTTOM, BOARD_TOP, RIM_HEIGHT

_MSG = "需要 matplotlib：pip install matplotlib（或 pip install -e .[plot]）"


def plot_shot(result, params, out_path: str) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(_MSG) from e

    fig, ax = plt.subplots(figsize=(9, 5.5))
    xs = [x for x, _ in result.trajectory]
    ys = [y for _, y in result.trajectory]
    ax.plot(xs, ys, lw=1.2, color="#e67e22", label="trajectory")
    ax.axhline(RIM_HEIGHT, xmin=0, xmax=1, color="#bbbbbb", lw=0.5)
    rim_c = params.distance
    ax.plot([rim_c - 0.2286, rim_c + 0.2286], [RIM_HEIGHT, RIM_HEIGHT],
            color="#c0392b", lw=4, solid_capstyle="round", label="rim")
    bx = rim_c + 0.375
    ax.plot([bx, bx], [BOARD_BOTTOM, BOARD_TOP], color="#2c3e50", lw=5,
            solid_capstyle="butt", label="backboard")
    ax.plot([0], [params.release_height], "o", color="#2980b9", ms=8, label="release")
    if result.scored:
        ax.set_title(f"SCORE — {result.label} ({result.label_cn})", color="#27ae60")
    else:
        ax.set_title(f"MISS — {result.label} ({result.label_cn})", color="#c0392b")
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def plot_sweep(sw, params, out_path: str) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(_MSG) from e

    fig, ax = plt.subplots(figsize=(9, 5))
    im = ax.imshow([row[:] for row in sw.grid], origin="lower", aspect="auto",
                   cmap="Greens", extent=[sw.v_range[0], sw.v_range[-1],
                                          sw.a_range[0], sw.a_range[-1]])
    ax.set_xlabel("v0 (m/s)")
    ax.set_ylabel("angle (°)")
    ax.set_title(f"hit map ({sw.hits}/{sw.total} cells)")
    fig.colorbar(im, ax=ax, ticks=[0, 1], label="hit")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path
