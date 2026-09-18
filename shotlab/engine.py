"""2D 篮球出手轨迹模拟引擎。

坐标系：出手点为原点，x 沿地面指向篮筐，y 竖直向上，单位米。
spin 为标量，spin > 0 表示后旋（backspin）——对向 +x 飞行的球产生升力。

物理模型：
  * 抛体运动（RK4 积分）
  * 空气阻力   F_d = -1/2 · ρ · Cd · A · |v| · v
  * Magnus 力  F_m = 1/2 · ρ · Cl · A · |v|^2 · (ẑ×v̂)·sign(ω)，
                Cl = 1 / (2 + v/(r·ω))（旋转球升力系数经验拟合）
  * 篮板碰撞   竖直线段（x = 筐心+0.375 m，y ∈ [2.90, 3.95]）
  * 篮筐碰撞   前/后筐点视为半径 1.6 cm 的圆管截面（圆-圆碰撞）
  * 碰撞含法向恢复系数 + 切向摩擦，摩擦会改变球的自旋
  * 得分判定   球心自上而下穿过筐平面 y=3.05，且位于前后筐点之间；
               自下而上穿过筐平面记为违例（真实规则：从下方进球无效）
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .constants import (
    BALL_AREA,
    BALL_INERTIA,
    BALL_MASS,
    BALL_RADIUS,
    BOARD_BOTTOM,
    BOARD_RESTITUTION,
    BOARD_TOP,
    DRAG_COEFF,
    FRICTION_MU,
    G,
    GROUND_RESTITUTION,
    RHO_AIR,
    RIM_CENTER_FROM_BOARD,
    RIM_HEIGHT,
    RIM_RADIUS,
    RIM_RESTITUTION,
    RIM_TUBE_RADIUS,
)

LABEL_CN = {
    "SWISH": "空心入网",
    "RIM_IN": "弹框入筐",
    "BANK_IN": "打板入筐",
    "RIM_OUT": "弹框不中",
    "BOARD_MISS": "打板不中",
    "AIRBALL_SHORT": "三不沾（短）",
    "AIRBALL_LONG": "三不沾（长）",
    "VIOLATION": "从下方穿筐（违例）",
}


@dataclass
class ShotResult:
    scored: bool = False
    label: str = ""
    flight_time: float = 0.0
    apex: float = 0.0
    entry_speed: float | None = None    # 入筐（穿筐平面）瞬间速度
    entry_angle_deg: float | None = None  # 入筐瞬间速度与水平面夹角
    crossed_x: float | None = None      # 穿筐平面时球心 x（筐心为 distance）
    contacts: list[str] = field(default_factory=list)  # rim_front/rim_back/board
    bounces: int = 0
    landing_x: float | None = None      # 第一次触地时的球心 x
    events: list[str] = field(default_factory=list)
    trajectory: list[tuple[float, float]] = field(default_factory=list)

    @property
    def label_cn(self) -> str:
        return LABEL_CN.get(self.label, self.label)


class Simulator:
    def __init__(self, params):
        self.p = params
        self.front_rim_x = params.distance - RIM_RADIUS
        self.back_rim_x = params.distance + RIM_RADIUS
        self.board_x = params.distance + RIM_CENTER_FROM_BOARD

    # ------------------------------------------------------------------ 气动
    def _accel(self, x, y, vx, vy, spin):
        ax, ay = 0.0, -G
        speed = math.hypot(vx, vy)
        if speed > 1e-9:
            if self.p.drag:
                k = 0.5 * RHO_AIR * DRAG_COEFF * BALL_AREA * speed / BALL_MASS
                ax -= k * vx
                ay -= k * vy
            if self.p.magnus and spin != 0.0:
                spin_ratio = BALL_RADIUS * abs(spin) / speed
                cl = 1.0 / (2.0 + 1.0 / max(spin_ratio, 1e-9))
                m = 0.5 * RHO_AIR * BALL_AREA * cl * speed * speed / BALL_MASS
                s = 1.0 if spin > 0.0 else -1.0
                ax += m * (-vy / speed) * s
                ay += m * (vx / speed) * s
        return ax, ay

    def _rk4_step(self, s, dt):
        def deriv(st):
            ax, ay = self._accel(st[0], st[1], st[2], st[3], st[4])
            return (st[2], st[3], ax, ay, 0.0)

        k1 = deriv(s)
        k2 = deriv(tuple(si + 0.5 * dt * ki for si, ki in zip(s, k1)))
        k3 = deriv(tuple(si + 0.5 * dt * ki for si, ki in zip(s, k2)))
        k4 = deriv(tuple(si + dt * ki for si, ki in zip(s, k3)))
        return tuple(
            si + dt / 6.0 * (a + 2.0 * b + 2.0 * c + d)
            for si, a, b, c, d in zip(s, k1, k2, k3, k4)
        )

    # ------------------------------------------------------------------ 碰撞
    def _collide_segment(self, st, sx, y_lo, y_hi, restitution, contact_name):
        """球与竖直线段（如篮板）的圆-线段碰撞。"""
        x, y, vx, vy, w = st
        cy = min(max(y, y_lo), y_hi)
        dx, dy = x - sx, y - cy
        dist = math.hypot(dx, dy)
        if dist >= BALL_RADIUS or dist <= 1e-12:
            return st, False
        nx, ny = dx / dist, dy / dist
        x, y = sx + nx * BALL_RADIUS, cy + ny * BALL_RADIUS
        touched = False
        vn = vx * nx + vy * ny
        if vn < 0.0:
            jn = (1.0 + restitution) * (-vn)
            vx += jn * nx
            vy += jn * ny
            # 切向摩擦：接触点在球面 -n·R 处，接触点切向速度 = v·t - ω·R
            tx, ty = -ny, nx
            vt_rel = vx * tx + vy * ty - w * BALL_RADIUS
            dvt = -FRICTION_MU * jn * (1.0 if vt_rel > 0.0 else -1.0)
            if abs(dvt) > abs(vt_rel):
                dvt = vt_rel
            vx += dvt * tx
            vy += dvt * ty
            w += -1.5 * dvt / BALL_RADIUS  # 摩擦力矩改变自旋
            touched = True
        return (x, y, vx, vy, w), touched

    def _collide_rim_point(self, st, cx):
        """球与前/后筐点的圆-圆碰撞（筐管截面半径 RIM_TUBE_RADIUS）。"""
        x, y, vx, vy, w = st
        dx, dy = x - cx, y - RIM_HEIGHT
        dist = math.hypot(dx, dy)
        rr = BALL_RADIUS + RIM_TUBE_RADIUS
        if dist >= rr or dist <= 1e-12:
            return st, False
        nx, ny = dx / dist, dy / dist
        x, y = cx + nx * rr, RIM_HEIGHT + ny * rr
        touched = False
        vn = vx * nx + vy * ny
        if vn < 0.0:
            jn = (1.0 + RIM_RESTITUTION) * (-vn)
            vx += jn * nx
            vy += jn * ny
            tx, ty = -ny, nx
            vt_rel = vx * tx + vy * ty - w * BALL_RADIUS
            dvt = -FRICTION_MU * jn * (1.0 if vt_rel > 0.0 else -1.0)
            if abs(dvt) > abs(vt_rel):
                dvt = vt_rel
            vx += dvt * tx
            vy += dvt * ty
            w += -1.5 * dvt / BALL_RADIUS
            touched = True
        return (x, y, vx, vy, w), touched

    def _collide_ground(self, st):
        x, y, vx, vy, w = st
        if y >= BALL_RADIUS:
            return st, False
        y = BALL_RADIUS
        if self.result.landing_x is None:
            self.result.landing_x = x
        if vy < 0.0:
            if -vy > 0.3:  # 明显的落地反弹才计数
                self.result.bounces += 1
                self.result.contacts.append("ground")
            vy = -vy * GROUND_RESTITUTION
            vx *= 0.85
            w *= 0.8
            if abs(vy) < 0.25:
                vy = 0.0
        return (x, y, vx, vy, w), True

    # ------------------------------------------------------------------ 主循环
    def run(self) -> ShotResult:
        p = self.p
        self.result = ShotResult()
        res = self.result
        theta = math.radians(p.angle_deg)
        st = (0.0, p.release_height,
              p.v0 * math.cos(theta), p.v0 * math.sin(theta), float(p.spin))
        res.events.append(
            f"t=0.000  出手  v0={p.v0:.2f} m/s  θ={p.angle_deg:.1f}°  "
            f"h={p.release_height:.2f} m  ω={p.spin:.1f} rad/s"
        )

        dt = p.dt
        t = 0.0
        apex, apex_t = st[1], 0.0
        wedged_steps = 0
        scored = False
        violation = False

        for _ in range(int(p.max_time / dt) + 1):
            prev_x, prev_y = st[0], st[1]
            st = self._rk4_step(st, dt)
            t += dt
            x, y, vx, vy, w = st

            if y > apex:
                apex, apex_t = y, t

            # --- 穿筐平面判定（先于碰撞，用本步位移插值） ---
            if prev_y > RIM_HEIGHT >= y and vy < 0.0:
                frac = (prev_y - RIM_HEIGHT) / max(prev_y - y, 1e-12)
                cx = prev_x + frac * (x - prev_x)
                if self.front_rim_x < cx < self.back_rim_x:
                    res.scored = True
                    res.crossed_x = cx
                    res.entry_speed = math.hypot(vx, vy)
                    res.entry_angle_deg = math.degrees(math.atan2(-vy, vx))
                    res.events.append(
                        f"t={t:.3f}  ✓ 入筐  入口 {res.entry_speed:.1f} m/s "
                        f"@ {res.entry_angle_deg:.1f}°  (偏心 {cx - p.distance:+.3f} m)"
                    )
                    scored = True
                    break
            elif prev_y <= RIM_HEIGHT < y and vy > 0.0:
                frac = (RIM_HEIGHT - prev_y) / max(y - prev_y, 1e-12)
                cx = prev_x + frac * (x - prev_x)
                if self.front_rim_x < cx < self.back_rim_x:
                    violation = True
                    res.events.append(f"t={t:.3f}  ✗ 球从下方穿过筐平面（违例）")
                    break

            # --- 碰撞解算 ---
            st, hit = self._collide_segment(
                st, self.board_x, BOARD_BOTTOM, BOARD_TOP, BOARD_RESTITUTION, "board")
            if hit:
                res.contacts.append("board")
                res.events.append(f"t={t:.3f}  碰撞篮板 (y={st[1]:.2f} m)")
            for rim_x, name in ((self.front_rim_x, "rim_front"),
                                (self.back_rim_x, "rim_back")):
                st, hit = self._collide_rim_point(st, rim_x)
                if hit:
                    res.contacts.append(name)
                    side = "前框" if name == "rim_front" else "后框"
                    res.events.append(f"t={t:.3f}  碰撞{side} (y={st[1]:.2f} m)")
            st, _ = self._collide_ground(st)
            if self.result.landing_x is not None and not scored:
                res.events.append(f"t={t:.3f}  落地 (x={st[0]:.2f} m)")
                break  # 触地未进 = 不可能再得分（反弹高度远低于筐）

            res.trajectory.append((st[0], st[1]))

            # --- 终止条件 ---
            speed = math.hypot(st[2], st[3])
            on_ground = st[1] <= BALL_RADIUS + 1e-9
            if on_ground and speed < 0.15:
                break
            if st[0] < -1.5 or st[0] > self.board_x + 2.0:
                break
            if st[1] > BALL_RADIUS + 0.005 and speed < 0.02:
                wedged_steps += 1
                if wedged_steps > 250:
                    res.events.append(f"t={t:.3f}  卡在筐沿上")
                    break
            else:
                wedged_steps = 0

        res.flight_time = t
        res.apex = apex
        res.trajectory.append((st[0], st[1]))
        res.events.insert(1, f"t={apex_t:.3f}  最高点 y={apex:.2f} m")

        if scored:
            if "board" in res.contacts:
                res.label = "BANK_IN"
            elif res.contacts:
                res.label = "RIM_IN" if "rim_front" in res.contacts or "rim_back" in res.contacts else "SWISH"
            else:
                res.label = "SWISH"
        elif violation:
            res.label = "VIOLATION"
        elif "rim_front" in res.contacts or "rim_back" in res.contacts:
            res.label = "RIM_OUT"
        elif "board" in res.contacts:
            res.label = "BOARD_MISS"
        elif res.trajectory and max(x for x, _ in res.trajectory) < self.front_rim_x:
            res.label = "AIRBALL_SHORT"
        else:
            res.label = "AIRBALL_LONG"
        return res
