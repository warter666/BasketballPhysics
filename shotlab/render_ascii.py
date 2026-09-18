"""轨迹的 ASCII 渲染（SHOT LAB 画布 + 参数面板）。"""

from __future__ import annotations

from .constants import BOARD_BOTTOM, BOARD_TOP, RIM_HEIGHT
from .params import ShotParams
from .engine import ShotResult


def render_canvas(result: ShotResult, params: ShotParams,
                  width: int = 76, height: int = 20) -> str:
    board_x = params.distance + 0.375
    xs = [x for x, _ in result.trajectory] or [0.0]
    ys = [y for _, y in result.trajectory] or [params.release_height]

    x_min = min(-0.3, min(xs)) - 0.1
    x_max = max(board_x + 0.55, max(xs) + 0.2)
    y_max = max(BOARD_TOP + 0.4, max(ys) + 0.25)

    grid = [[" "] * width for _ in range(height)]

    def cell(x, y):
        col = round((x - x_min) / (x_max - x_min) * (width - 1))
        row = height - 1 - round(y / y_max * (height - 1))
        if 0 <= row < height and 0 <= col < width:
            return row, col
        return None

    # 地面
    for c in range(width):
        grid[height - 1][c] = "─"

    # 篮板
    board_cells = []
    for r in range(height):
        y = (height - 1 - r) / (height - 1) * y_max
        if BOARD_BOTTOM <= y <= BOARD_TOP:
            rc = cell(board_x, y)
            if rc:
                grid[rc[0]][rc[1]] = "▌"
                board_cells.append(rc)

    # 篮筐（侧视：前/后筐点 + 连线）
    rim_cells = []
    rim_pts = []
    rc = cell(params.distance - 0.2286, RIM_HEIGHT)
    rc2 = cell(params.distance + 0.2286, RIM_HEIGHT)
    if rc and rc2 and rc[0] == rc2[0]:
        rim_pts = [rc, rc2]
        for c in range(rc[1], rc2[1] + 1):
            grid[rc[0]][c] = "─"
            rim_cells.append((rc[0], c))

    # 轨迹
    step = max(1, len(result.trajectory) // (width * 4))
    for i, (x, y) in enumerate(result.trajectory[::step]):
        rc = cell(x, y)
        if rc and grid[rc[0]][rc[1]] == " ":
            grid[rc[0]][rc[1]] = "·"
    # 起始球
    ball_cell = cell(0.0, params.release_height)
    if ball_cell:
        grid[ball_cell[0]][ball_cell[1]] = "◎"

    # 结构压在轨迹之上
    for r, c in board_cells:
        grid[r][c] = "▌"
    for r, c in rim_cells:
        grid[r][c] = "─"
    for r, c in rim_pts:
        grid[r][c] = "●"

    lines = ["".join(row).rstrip() for row in grid]
    # 米尺刻度
    ticks = []
    labels = []
    xm = 0
    while xm <= x_max:
        if xm >= x_min:
            col = round((xm - x_min) / (x_max - x_min) * (width - 1))
            if 0 <= col < width:
                grid[height - 1][col] = "┴"
                ticks.append(col)
                labels.append((col, str(xm)))
        xm += 1
    lines = ["".join(row) for row in grid]
    tick_line = [" "] * width
    for col, text in labels:
        s = text
        start = col - len(s) // 2
        for k, ch in enumerate(s):
            if 0 <= start + k < width:
                tick_line[start + k] = ch
    lines.append("".join(tick_line).rstrip())
    lines.append(f"单位: m   出手点 x=0   篮筐中心 x={params.distance:.2f}")

    # 右侧标注
    rim_row = rim_pts[0][0] if rim_pts else None
    if rim_row is not None and rim_row < len(lines) - 2:
        lines[rim_row] += "  ← RIM 3.05 m"
    board_top_row = cell(board_x, BOARD_TOP)
    if board_top_row:
        lines[board_top_row[0]] += "  ← 篮板"

    return "\n".join(lines)


def _bar(pct: float, width: int = 20) -> str:
    n = round(pct / 100.0 * width)
    return "█" * n + "░" * (width - n)


def render_panel(result: ShotResult, params: ShotParams, mc=None) -> str:
    marks = {"SWISH": "✓✓", "RIM_IN": "✓", "BANK_IN": "✓"}.get(result.label, "✗")
    contacts = ", ".join(result.contacts) if result.contacts else "无接触"
    lines = [
        "  ── SHOT LAB " + "─" * 44,
        f"   Velocity   {params.v0:6.2f} m/s        Drag    {'ON ' if params.drag else 'OFF'}",
        f"   Angle      {params.angle_deg:6.1f} °          Magnus  {'ON ' if params.magnus else 'OFF'}",
        f"   Release h  {params.release_height:6.2f} m          Spin    {params.spin:.1f} rad/s",
        f"   Distance   {params.distance:6.2f} m          dt      {params.dt * 1000:.1f} ms",
        "  " + "─" * 49,
        f"   RESULT     {result.label} {marks}  {result.label_cn}",
        f"   Flight     {result.flight_time:6.2f} s          Apex    {result.apex:.2f} m",
    ]
    if result.entry_speed is not None:
        lines.append(
            f"   Entry      {result.entry_speed:6.1f} m/s @ "
            f"{result.entry_angle_deg:5.1f}°   偏心 {result.crossed_x - params.distance:+.3f} m")
    lines.append(f"   Contacts   {contacts}")
    if mc is not None:
        lines += [
            "  " + "─" * 49,
            "   Probability",
            f"   {_bar(mc.rate * 100)}  {mc.rate * 100:5.1f}%",
            f"   (n={mc.n}, swish {mc.swish_rate * 100:.1f}%, "
            f"σ_v0={mc.sigmas['v0']} m/s, σ_θ={mc.sigmas['angle_deg']}°)",
        ]
    else:
        lines += [
            "  " + "─" * 49,
            "   Probability  (运行 `shotlab shot --mc 400` 获取蒙特卡洛命中率)",
        ]
    lines.append("  " + "─" * 49)
    return "\n".join(lines)


def render_timeline(result: ShotResult, limit: int = 12) -> str:
    lines = ["  ── 时间线 " + "─" * 45]
    for ev in result.events[:limit]:
        lines.append("   " + ev)
    if len(result.events) > limit:
        lines.append(f"   … 共 {len(result.events)} 条")
    return "\n".join(lines)
