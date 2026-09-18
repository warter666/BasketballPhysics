"""SHOT DUEL · tkinter 火柴人动画界面（Python 标准库，零依赖）。

操控（v0.2）：鼠标移动 = 瞄准弧度；按住空格 = 蓄力（1.1s 充满，
过充缓慢泄力）；松开空格 = 出手。三个输入通道互相独立。
"""

from __future__ import annotations

import math
import tkinter as tk

from shotlab.engine import Simulator

from .session import DuelSession, SoloSession

FPS = 30
DT_FRAME = 1.0 / FPS

# 操控参数（策划书 §8 v0.2）
CHARGE_TIME = 1.1          # s，0 → 满力
V0_MIN, V0_MAX = 1.5, 13.5
OVERCHARGE_DECAY = 0.25    # 满力后泄力速率（power/s）
OVERCHARGE_FLOOR = 0.60

# 调色板（画面清晰度重制）
C_BG = "#0e1420"
C_FLOOR = "#b98a4e"
C_FLOOR_LINE = "#8a6134"
C_FLOOR_DARK = "#a37a41"
C_HUD = "#e6edf3"
C_DIM = "#7d8b9d"
C_PANEL = "#161d2b"
C_ACCENT = "#7fd4ff"
C_ACCENT2 = "#ffb3ba"
C_HOOP = "#ff6b3d"
C_NET = "#dfe7ee"
C_BOARD = "#e8f0f8"
C_BALL = "#ff9f43"
C_BALL_SEAM = "#b3541e"
C_TRAIL = "#ffd479"
C_WIND_POS = "#5dade2"
C_WIND_NEG = "#ec7063"
C_METER = "#2ecc71"
C_METER_HOT = "#e74c3c"

W, H = 1120, 640


# ---------------------------------------------------------------- 火柴人姿态
def _lerp(a, b, k):
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def pose_idle():
    return dict(head=(0, 1.58), neck=(0, 1.42), hip=(0, 0.92),
                lknee=(-0.07, 0.46), lfoot=(-0.09, 0.0),
                rknee=(0.07, 0.46), rfoot=(0.09, 0.0),
                lelbow=(-0.22, 1.14), lhand=(-0.16, 0.90),
                relbow=(0.22, 1.14), rhand=(0.16, 0.90))


def pose_crouch():
    return dict(head=(0, 1.22), neck=(0, 1.08), hip=(0, 0.66),
                lknee=(-0.20, 0.36), lfoot=(-0.13, 0.0),
                rknee=(0.20, 0.36), rfoot=(0.13, 0.0),
                lelbow=(-0.30, 0.84), lhand=(-0.36, 0.60),
                relbow=(0.30, 0.84), rhand=(0.36, 0.60))


def pose_extend(aim_rad):
    ux, uy = math.cos(aim_rad), math.sin(aim_rad)
    hand_l = (0.02 + 0.42 * ux, 1.60 + 0.42 * uy)
    hand_r = (0.02 + 0.50 * ux, 1.60 + 0.50 * uy)
    return dict(head=(0.02, 1.80), neck=(0.02, 1.62), hip=(0.0, 1.06),
                lknee=(-0.05, 0.53), lfoot=(-0.08, 0.0),
                rknee=(0.06, 0.53), rfoot=(0.09, 0.0),
                lelbow=(0.02 + 0.22 * ux, 1.62 + 0.22 * uy), lhand=hand_l,
                relbow=(0.02 + 0.26 * ux, 1.62 + 0.26 * uy), rhand=hand_r)


def pose_follow():
    return dict(head=(0.06, 1.70), neck=(0.05, 1.54), hip=(0.02, 1.00),
                lknee=(-0.06, 0.50), lfoot=(-0.09, 0.0),
                rknee=(0.10, 0.50), rfoot=(0.14, 0.0),
                lelbow=(0.18, 1.28), lhand=(0.30, 1.06),
                relbow=(0.24, 1.26), rhand=(0.38, 1.02))


def blend(p1, p2, k):
    return {j: _lerp(p1[j], p2[j], k) for j in p1}


class ShotDuelApp:
    def __init__(self, root: tk.Tk, session, selftest: bool = False):
        self.root = root
        self.session = session
        self.selftest = selftest
        self.is_duel = isinstance(session, DuelSession)

        root.title("SHOT DUEL · 斗球实验室")
        self.canvas = tk.Canvas(root, width=W, height=H, bg=C_BG,
                                highlightthickness=0)
        self.canvas.pack()
        bar = tk.Frame(root, bg=C_PANEL)
        bar.pack(fill="x")
        self.lbl_aim = tk.Label(bar, text="", fg=C_ACCENT, bg=C_PANEL,
                                font=("Consolas", 12), width=46, anchor="w")
        self.lbl_aim.pack(side="left", padx=10, pady=5)
        self.lbl_card = tk.Label(bar, text="", fg="#ffd479", bg=C_PANEL,
                                 font=("Microsoft YaHei UI", 11))
        self.lbl_card.pack(side="left", padx=10)

        # ---- 操控状态 ----
        self.mouse = (W * 0.55, H * 0.3)   # 画布像素
        self.charging = False
        self.charge_t = 0.0
        self.power = 0.0
        self.spin = 6.0

        # ---- 流程状态 ----
        self.phase = "boot"      # intro/aim/anim/result/pass/pick/end
        self.t_round = 0.0
        self.fly = None
        self.particles = []
        self.result_shown = None
        self.player = 0
        self.overlay_lines = []
        self.overlay_title = ""
        self._frame = 0

        self._bind()
        self._boot()

    # ------------------------------------------------------------------ 流程
    def _boot(self):
        if self.is_duel:
            if self.session.need_rule_pick():
                self._phase_pick("上一回合结束，请输家挑场地")
            else:
                self._start_round()
        else:
            self._start_round()

    def _start_round(self):
        if self.is_duel and self.session.round is None:
            if self.session.need_rule_pick():
                self._phase_pick(f"{self.session.names[self.session.next_chooser]} "
                                 f"挑选下一块场地")
                return
            self.session.start_round()
        elif not self.is_duel:
            self.session.start_round()
        self.t_round = 0.0
        self.player = 0
        self.spin = 6.0
        self._stop_charge()
        self._phase_intro()

    def _round(self):
        return self.session.round

    def _rule_flags(self):
        r = self._round()
        rules = [r.rule] + list(r.subs)
        return (any(x.fog for x in rules), any(x.moving for x in rules))

    def _phase_intro(self):
        r = self._round()
        fog, moving = self._rule_flags()
        lines = [r.rule_desc]
        if fog:
            lines.append("（本回合无预览，飞行不可见——凭手感！）")
        for i, sk in enumerate(r.skills):
            tag = self.session.names[i] if self.is_duel else "你"
            lines.append(f"{tag} 抽到 {sk.icon} {sk.name}（{sk.kind}）：{sk.desc}")
        dist = r.params_by_player[0].distance
        lines.append(f"篮筐距离 {dist:.2f} m · 篮筐高度 {r.base_params.rim_height:.2f} m")
        lines.append("鼠标瞄准弧度 · 按住空格蓄力 · 松开出手")
        self._overlay("回合开始", lines)
        self.phase = "intro"

    def _phase_pick(self, title):
        self.phase = "pick"
        self.session.prepare_offers()
        self.overlay_title = title
        self.overlay_lines = []

    def _choose(self, idx):
        offers = self.session.offers
        if not offers or not (0 <= idx < len(offers)):
            return
        self.session.pick_rule(idx)
        self._start_round()

    # ------------------------------------------------------------------ 出手
    def fire_with(self, v0: float):
        """用明确的速度出手（蓄力释放 / 自检直接调用）。"""
        if self.phase != "aim":
            return
        r = self._round()
        params = r.params_by_player[self.player]
        rim_phase = None
        if params.rim_period > 0:
            rim_phase = (params.rim_phase
                         + 2 * math.pi * self.t_round / params.rim_period) % (2 * math.pi)
        result, score = self.session.shoot(
            v0, self.aim_angle(), self.spin,
            player=self.player, rim_phase=rim_phase)
        self.fly_phase = rim_phase if rim_phase is not None else params.rim_phase
        self.fly = dict(result=result, score=score, t=0.0, released=False,
                        traj=result.trajectory, dt=params.dt, seam=0.0,
                        spin=params.spin, v0=v0)
        self.phase = "anim"

    def aim_angle(self) -> float:
        """鼠标位置 → 仰角（从出手点指向光标），5°~85°。"""
        p = self._round().params_by_player[self.player]
        ox, oy = self._px(0.0, p.release_height)
        dx = self.mouse[0] - ox
        dy = oy - self.mouse[1]
        ang = math.degrees(math.atan2(max(dy, 1.0), max(dx, 6.0)))
        return min(85.0, max(5.0, ang))

    def _charge_power(self) -> float:
        if self.charge_t <= CHARGE_TIME:
            return self.charge_t / CHARGE_TIME
        return max(OVERCHARGE_FLOOR, 1.0 - OVERCHARGE_DECAY * (self.charge_t - CHARGE_TIME))

    def _start_charge(self):
        if self.phase == "aim" and not self.charging:
            self.charging = True
            self.charge_t = 0.0

    def _release_charge(self):
        if not (self.charging and self.phase == "aim"):
            self.charging = False
            return
        self.charging = False
        self.fire_with(V0_MIN + (V0_MAX - V0_MIN) * self._charge_power())

    def _stop_charge(self):
        self.charging = False
        self.charge_t = 0.0
        self.power = 0.0

    def _after_result(self):
        r = self._round()
        if self.is_duel:
            if len(r.results) < 2:
                self.player = 1
                self.spin = 6.0
                self._stop_charge()
                self._overlay("交棒", [
                    f"把键盘交给 {self.session.names[1]}",
                    "（空格开始瞄准）"])
                self.phase = "pass"
            else:
                text = self.session.conclude_round()
                if self.session.match_over:
                    self._phase_end()
                else:
                    self._overlay("回合结算", text.split("\n"))
                    self.phase = "pass"
        else:
            if self.session.finished:
                self._phase_end()
            else:
                self.session.start_round()
                self.t_round = 0.0
                self.spin = 6.0
                self._stop_charge()
                self._phase_intro()

    def _phase_end(self):
        self.phase = "end"
        if self.is_duel:
            champ = self.session.champion
            lines = [f"🏆 {self.session.names[champ]} 赢得对决！",
                     f"回合胜场 {self.session.round_wins[0]}:"
                     f"{self.session.round_wins[1]}",
                     f"总得分 {self.session.total_pts[0]}:"
                     f"{self.session.total_pts[1]}"]
        else:
            lines = self.session.summary().split("\n")
        lines.append("空格 = 再来一局   Esc = 退出")
        self._overlay("比赛结束", lines)

    # ------------------------------------------------------------------ 输入
    def _bind(self):
        self.root.bind("<Key>", self._on_key)
        self.root.bind("<KeyRelease>", self._on_keyup)
        c = self.canvas
        c.bind("<Motion>", self._on_motion)

    def _on_motion(self, ev):
        self.mouse = (ev.x, ev.y)

    def _on_key(self, ev):
        key = ev.keysym
        if self.phase == "end":
            if key == "space":
                self._restart()
            elif key == "Escape":
                self.root.destroy()
            return
        if self.phase in ("intro", "result", "pass"):
            if key == "space":
                if self.phase == "intro":
                    self.phase = "aim"
                elif self.phase == "result":
                    self._after_result()
                else:
                    if self.session.round is None:
                        self._start_round()
                    else:
                        self.phase = "aim"
            return
        if self.phase == "pick":
            if key in ("1", "2", "3"):
                self._choose(int(key) - 1)
            return
        if self.phase == "aim":
            if key == "space":
                self._start_charge()
            elif key == "Left":
                self.spin = max(-12.0, self.spin - 0.5)
            elif key == "Right":
                self.spin = min(12.0, self.spin + 0.5)
            elif key == "Up":
                self.mouse = (self.mouse[0], self.mouse[1] - 8)
            elif key == "Down":
                self.mouse = (self.mouse[0], self.mouse[1] + 8)

    def _on_keyup(self, ev):
        if ev.keysym == "space" and self.charging:
            self._release_charge()

    def _restart(self):
        if self.is_duel:
            self.session = DuelSession()
        else:
            self.session = SoloSession()
        self.is_duel = isinstance(self.session, DuelSession)
        self._boot()

    # ------------------------------------------------------------------ 主循环
    def tick(self):
        self.t_round += DT_FRAME
        if self.charging:
            self.charge_t += DT_FRAME
            self.power = self._charge_power()
        if self.phase == "anim":
            self._advance_anim()
        self._redraw()
        self._frame += 1
        if not self.selftest:
            self.root.after(int(DT_FRAME * 1000), self.tick)

    def run(self):
        self.tick()
        self.root.mainloop()

    def _advance_anim(self):
        f = self.fly
        if f is None:
            return
        f["t"] += DT_FRAME
        f["seam"] += f["spin"] * DT_FRAME
        t_rel = 0.30
        if f["t"] >= t_rel:
            f["released"] = True
        idx = int((f["t"] - t_rel) / f["dt"]) if f["t"] >= t_rel else 0
        if f["released"] and idx >= len(f["traj"]) - 1:
            f["t_end"] = f.get("t_end", f["t"] + 0.45)
            if f["t"] >= f["t_end"]:
                self._show_result()

    def _show_result(self):
        s = self.fly["score"]
        self._overlay(f"{s.title}   {'★' * s.stars}",
                      s.breakdown + [f"本回合得分 {s.pts:+d}"])
        self.phase = "result"

    # ------------------------------------------------------------------ 坐标
    def _domain(self):
        r = self._round()
        p = r.params_by_player[self.player] if r else None
        d = (p.distance if p else 4.2)
        v0 = (V0_MIN + (V0_MAX - V0_MIN) * self.power) if self.charging else 8.0
        g = (p.gravity if p else 9.81)
        h = (p.release_height if p else 2.0)
        apex = h + max(v0, 8.0) ** 2 / (2 * g)
        y_max = min(max(4.6, apex * 1.05), 12.0)
        return (-2.1, d + 1.5, -0.62, y_max)

    def _sx(self):
        x0, x1, y0, y1 = self._domain()
        pad_l, pad_r, pad_t, pad_b = 40, 40, 58, 64
        scale = min((W - pad_l - pad_r) / (x1 - x0), (H - pad_t - pad_b) / (y1 - y0))
        ox = pad_l + (-x0) * scale + ((W - pad_l - pad_r) - (x1 - x0) * scale) / 2
        oy = H - pad_b
        return scale, ox, oy

    def _px(self, x, y):
        s, ox, oy = self._sx()
        return ox + x * s, oy - y * s

    def _overlay(self, title, lines):
        self.overlay_title = title
        self.overlay_lines = list(lines)

    # ------------------------------------------------------------------ 渲染
    def _redraw(self):
        cv = self.canvas
        cv.delete("all")
        fog, _moving = self._rule_flags()
        self._draw_court()
        self._draw_hoop()
        self._draw_particles()
        self._draw_stickman()
        if self.phase == "aim":
            self._draw_aim(fog)
        if self.phase == "anim" and self.fly:
            self._draw_ball_flight(fog)
        self._draw_meter()
        self._draw_hud()
        if self.phase in ("intro", "result", "pass", "pick", "end"):
            self._draw_overlay()

    def _draw_court(self):
        cv = self.canvas
        _, oy = self._px(0, 0)
        # 木地板
        cv.create_rectangle(0, oy, W, H, fill=C_FLOOR, outline="")
        for k in range(8):
            yy = oy + 8 + k * (H - oy) / 8
            cv.create_line(0, yy, W, yy, fill=C_FLOOR_LINE)
        # 米尺与出手点标记
        for xm in range(int(self._domain()[0]) + 1, int(self._domain()[1]) + 1):
            px, _ = self._px(xm, 0)
            cv.create_text(px, oy + 22, text=f"{xm}m", fill="#6b4f2a",
                           font=("Consolas", 10, "bold"))
        rx, _ = self._px(0, 0)
        cv.create_line(rx, oy, rx, oy - 14, fill="#6b4f2a", width=3)
        cv.create_text(rx, oy + 40, text="出手点", fill="#6b4f2a",
                       font=("Microsoft YaHei UI", 10))

    def _draw_hoop(self):
        cv = self.canvas
        r = self._round()
        p = r.params_by_player[self.player]
        if self.phase == "anim" and self.fly and self.fly["released"]:
            t = self.fly["t"] - 0.30
            off = p.rim_amp * math.sin(2 * math.pi * t / p.rim_period + self.fly_phase) \
                if p.rim_period > 0 else 0.0
        else:
            off = p.rim_amp * math.sin(2 * math.pi * self.t_round / p.rim_period
                                       + p.rim_phase) if p.rim_period > 0 else 0.0
        cx_hoop = p.distance + off
        rh = p.rim_height
        rr = p.rim_radius
        # 篮板 + 内方框
        bx = cx_hoop + 0.375
        x1, y1 = self._px(bx, rh - 0.15)
        x2, y2 = self._px(bx, rh + 0.90)
        cv.create_line(x1, y1, x2, y2, fill=C_BOARD, width=8)
        sq1 = self._px(bx, rh + 0.45)
        sq2 = self._px(bx, rh + 0.10)
        cv.create_line(sq1[0], sq1[1], sq2[0], sq2[1], fill="#9fb3c8", width=2)
        # 筐
        fx, fy = self._px(cx_hoop - rr, rh)
        gx, gy = self._px(cx_hoop + rr, rh)
        cv.create_line(fx, fy, gx, gy, fill=C_HOOP, width=5)
        for px_, py_ in ((fx, fy), (gx, gy)):
            cv.create_oval(px_ - 4, py_ - 4, px_ + 4, py_ + 4,
                           fill=C_HOOP, outline=C_BOARD)
        # 网（4 根 + 底部横线）
        for k in (0.1, 0.37, 0.63, 0.9):
            xa, ya = self._px(cx_hoop - rr + 2 * rr * k, rh)
            xb, yb = self._px(cx_hoop - rr * (1 - k * 0.72), rh - 0.28)
            cv.create_line(xa, ya, xb, yb, fill=C_NET)
        n1 = self._px(cx_hoop - rr * 0.3, rh - 0.28)
        n2 = self._px(cx_hoop + rr * 0.3, rh - 0.28)
        cv.create_line(n1[0], n1[1], n2[0], n2[1], fill=C_NET)

    def _draw_particles(self):
        r = self._round()
        if not r:
            return
        p = r.params_by_player[self.player]
        wind = p.wind_ax
        if abs(wind) < 0.1:
            return
        cv = self.canvas
        target = min(34, int(abs(wind) * 11))
        x0, x1, _, _ = self._domain()
        while len(self.particles) < target:
            self.particles.append([x0 + (x1 - x0)
                                   * ((self._frame * 37 + 13 * len(self.particles)) % 100) / 100,
                                   0.4 + (len(self.particles) * 0.53) % 3.4])
        self.particles = self.particles[:target]
        color = C_WIND_POS if wind > 0 else C_WIND_NEG
        for pt in self.particles:
            pt[0] += wind * 0.5 * DT_FRAME
            if pt[0] > x1:
                pt[0] = x0
            if pt[0] < x0:
                pt[0] = x1
            px, py = self._px(pt[0], pt[1])
            dx = 8 if wind > 0 else -8
            cv.create_line(px, py, px + dx, py, fill=color, width=2)

    def _stickman_poses(self):
        aim_rad = math.radians(self.aim_angle())
        if self.phase == "anim" and self.fly:
            t = self.fly["t"]
            if t < 0.16:
                return blend(pose_idle(), pose_crouch(), t / 0.16), -1.1
            if t < 0.30:
                k = (t - 0.16) / 0.14
                return blend(pose_crouch(), pose_extend(aim_rad), k), -1.1 + 0.35 * k
            if t < 0.42:
                k = (t - 0.30) / 0.12
                return blend(pose_extend(aim_rad), pose_follow(), k), -0.75
            return pose_follow(), -0.75
        base = pose_idle()
        ux, uy = math.cos(aim_rad), math.sin(aim_rad)
        base["lhand"] = (0.0 + 0.34 * ux, 1.42 + 0.34 * uy)
        base["rhand"] = (0.02 + 0.42 * ux, 1.42 + 0.42 * uy)
        base["lelbow"] = (0.0 + 0.18 * ux - 0.08 * uy, 1.42 + 0.18 * uy + 0.08 * ux)
        base["relbow"] = (0.02 + 0.20 * ux + 0.08 * uy, 1.42 + 0.20 * uy - 0.08 * ux)
        return base, -1.1

    def _draw_stickman(self):
        cv = self.canvas
        pose, sx = self._stickman_poses()
        s, _, _ = self._sx()
        color = C_ACCENT if (not self.is_duel or self.player == 0) else C_ACCENT2

        def P(name):
            x, y = pose[name]
            return self._px(sx + x, y)

        hx, hy = P("head")
        r_head = 0.115 * s
        cv.create_oval(hx - r_head, hy - r_head, hx + r_head, hy + r_head,
                       fill=color, outline="")
        nx, ny = P("neck")
        px_, py_ = P("hip")
        cv.create_line(nx, ny, px_, py_, fill=color, width=5,
                       capstyle="round")
        for a, b in (("hip", "lknee"), ("lknee", "lfoot"),
                     ("hip", "rknee"), ("rknee", "rfoot"),
                     ("neck", "lelbow"), ("lelbow", "lhand"),
                     ("neck", "relbow"), ("relbow", "rhand")):
            x1, y1 = P(a)
            x2, y2 = P(b)
            cv.create_line(x1, y1, x2, y2, fill=color, width=4,
                           capstyle="round")
        if self.is_duel:
            cv.create_text(hx, hy - r_head - 14,
                           text=self.session.names[self.player], fill=color,
                           font=("Microsoft YaHei UI", 12, "bold"))
        if self.phase == "aim":
            bx, by = P("rhand")
            rb = 0.12 * s
            cv.create_oval(bx - rb, by - rb, bx + rb, by + rb,
                           fill=C_BALL, outline=C_BALL_SEAM, width=2)

    def _draw_aim(self, fog):
        cv = self.canvas
        r = self._round()
        p = r.params_by_player[self.player]
        a = math.radians(self.aim_angle())
        v0_now = (V0_MIN + (V0_MAX - V0_MIN) * self.power) if self.charging else 8.0
        # 瞄准线（虚线箭头，长度随力度）
        x0, y0 = self._px(0.15, p.release_height)
        ln = 1.0 + 1.4 * ((v0_now - V0_MIN) / (V0_MAX - V0_MIN))
        x1, y1 = self._px(0.15 + ln * math.cos(a),
                          p.release_height + ln * math.sin(a))
        cv.create_line(x0, y0, x1, y1, fill=C_TRAIL, width=2,
                       dash=(6, 5), arrow="last")
        cv.create_text(x1, y1 - 16, text=f"{self.aim_angle():.1f}°",
                       fill=C_TRAIL, font=("Consolas", 12, "bold"))
        # 预测弹道（物理之眼 + 无雾；蓄力时实时跟随力度）
        if r.preview[self.player] and not fog:
            sim = Simulator(p.with_(v0=v0_now, angle_deg=self.aim_angle(),
                                    spin=self.spin)).run()
            for x, y in sim.trajectory[::6]:
                px, py = self._px(x, y)
                cv.create_oval(px - 1.5, py - 1.5, px + 1.5, py + 1.5,
                               fill="#5dade2", outline="")

    def _draw_meter(self):
        """蓄力条：左侧竖条，过充区变红。"""
        if self.phase != "aim":
            return
        cv = self.canvas
        mx, mt, mb = 26, 120, 560
        frac = self.power if self.charging else 0.0
        cv.create_rectangle(mx, mt, mx + 18, mb, fill=C_PANEL,
                            outline=C_DIM, width=2)
        fh = int((mb - mt) * frac)
        hot = self.charging and self.charge_t > CHARGE_TIME
        color = C_METER_HOT if hot else C_METER
        if fh > 0:
            cv.create_rectangle(mx + 2, mb - fh, mx + 16, mb - 2,
                                fill=color, outline="")
        for k in (0.25, 0.5, 0.75, 1.0):
            yy = mb - int((mb - mt) * k)
            cv.create_line(mx, yy, mx + 22, yy, fill=C_DIM)
        label = "泄力!" if hot else ("蓄力中…" if self.charging else "力度")
        cv.create_text(mx + 9, mt - 18, text=label, fill=(C_METER_HOT if hot else C_HUD),
                       font=("Microsoft YaHei UI", 10, "bold"))
        if self.charging:
            v0 = V0_MIN + (V0_MAX - V0_MIN) * self.power
            cv.create_text(mx + 9, mb + 18, text=f"{v0:.1f}", fill=C_HUD,
                           font=("Consolas", 11, "bold"))

    def _draw_ball_flight(self, fog):
        f = self.fly
        cv = self.canvas
        p = self._round().params_by_player[self.player]
        s, _, _ = self._sx()
        t_rel = 0.30
        if not f["released"]:
            return
        idx = min(int((f["t"] - t_rel) / f["dt"]), len(f["traj"]) - 1)
        traj = f["traj"]
        if not fog:
            for j in range(max(0, idx - 30), idx, 3):
                x, y = traj[j]
                px, py = self._px(x, y)
                cv.create_oval(px - 1.5, py - 1.5, px + 1.5, py + 1.5,
                               fill=C_TRAIL, outline="")
        if not fog:
            x, y = traj[idx]
            bx, by = self._px(x, y)
            rb = p.ball_radius * s
            cv.create_oval(bx - rb, by - rb, bx + rb, by + rb,
                           fill=C_BALL, outline=C_BALL_SEAM, width=3)
            for ang in (f["seam"], f["seam"] + math.pi / 2):
                cv.create_line(bx - rb * math.cos(ang), by - rb * math.sin(ang),
                               bx + rb * math.cos(ang), by + rb * math.sin(ang),
                               fill=C_BALL_SEAM)

    def _draw_hud(self):
        cv = self.canvas
        r = self._round()
        if r:
            p = r.params_by_player[self.player]
            fog, moving = self._rule_flags()
            bits = [f"回合 {r.index + 1}"]
            if self.is_duel:
                bits.append(f"{self.session.names[0]} {self.session.round_wins[0]} : "
                            f"{self.session.round_wins[1]} {self.session.names[1]}")
                bits.append(f"篮筐漂移 {self.session.hoop_shift:+.2f} m")
            else:
                bits.append(f"总分 {self.session.total}")
                if self.session.streak > 1:
                    bits.append(f"🔥连击 x{self.session.streak}")
            if abs(p.wind_ax) > 1e-6:
                bits.append(f"风 {p.wind_ax:+.1f} m/s²")
            if moving:
                bits.append("篮筐移动中")
            if fog:
                bits.append("浓雾")
            # 顶栏面板
            cv.create_rectangle(0, 0, W, 44, fill=C_PANEL, outline="")
            cv.create_text(W / 2, 22, text="  ·  ".join(bits), fill=C_HUD,
                           font=("Microsoft YaHei UI", 14, "bold"))
        ang = self.aim_angle() if r else 0
        v0_now = (V0_MIN + (V0_MAX - V0_MIN) * self.power) if self.charging else 8.0
        self.lbl_aim.config(text=f"力度 {v0_now:5.2f} m/s   仰角 {ang:5.1f}°   "
                                 f"后旋 {self.spin:5.1f} rad/s")
        if r:
            sk = r.skills[self.player]
            self.lbl_card.config(text=f"{sk.icon} {sk.name}：{sk.desc}")

    def _draw_overlay(self):
        cv = self.canvas
        cv.create_rectangle(200, 130, W - 200, 470, fill="#0d1117",
                            outline="#3a4450", width=2)
        cv.create_text(W / 2, 170, text=self.overlay_title, fill="#ffd479",
                       font=("Microsoft YaHei UI", 22, "bold"))
        y = 220
        for line in self.overlay_lines[:9]:
            cv.create_text(W / 2, y, text=line, fill=C_HUD,
                           font=("Microsoft YaHei UI", 13))
            y += 28
        if self.phase == "pick":
            for i, rule in enumerate(self.session.offers):
                bx = 260 + i * 220
                cv.create_rectangle(bx, 320, bx + 200, 420,
                                    fill="#1b2430", outline=C_ACCENT, width=2,
                                    tags=f"opt{i}")
                cv.create_text(bx + 100, 344, text=f"[{i + 1}] {rule.icon} {rule.name}",
                               fill="#ffd479", font=("Microsoft YaHei UI", 14, "bold"),
                               tags=f"opt{i}")
                cv.create_text(bx + 100, 374, text=rule.desc, fill="#aebbc8",
                               font=("Microsoft YaHei UI", 11), width=190,
                               tags=f"opt{i}")
                cv.create_text(bx + 100, 404, text="★" * rule.stars, fill=C_HOOP,
                               font=("Consolas", 11), tags=f"opt{i}")
                cv.tag_bind(f"opt{i}", "<Button-1>",
                            lambda _e, i=i: self._choose(i))
        else:
            hint = "—— 空格 继续 ——" if self.phase != "aim" else ""
            if hint:
                cv.create_text(W / 2, 445, text=hint, fill=C_ACCENT,
                               font=("Microsoft YaHei UI", 12))


def run_gui(mode: str = "solo", seed=None):
    root = tk.Tk()
    if mode == "duel":
        session = DuelSession(seed=seed)
    else:
        session = SoloSession(seed=seed)
    app = ShotDuelApp(root, session)
    app.run()
    return app


def run_selftest() -> bool:
    """无头自检：蓄力出手 + 完整对局流程。"""
    root = tk.Tk()
    root.withdraw()
    session = SoloSession(seed=3)
    app = ShotDuelApp(root, session, selftest=True)
    app.tick()
    assert app.phase == "intro", app.phase
    app._on_key(type("E", (), {"keysym": "space"})())
    assert app.phase == "aim"

    # --- 蓄力机制：按住 0.55s ≈ 半力，松开触发出手 ---
    app._start_charge()
    for _ in range(16):          # ~0.53s
        app.tick()
    assert app.charging and abs(app.power - 0.53 / CHARGE_TIME) < 0.05
    mid_v0 = V0_MIN + (V0_MAX - V0_MIN) * app.power
    app._release_charge()
    assert app.phase == "anim", app.phase
    assert abs(app.fly["v0"] - mid_v0) < 1e-6

    for _ in range(6000):
        app.tick()
        if app.phase in ("result", "end"):
            break
    assert app.phase == "result", f"anim 未收敛: {app.phase}"
    assert len(app.session.history) == 1

    # --- 打完剩余回合（状态机无关推进） ---
    def _key(k="space"):
        app._on_key(type("E", (), {"keysym": k})())
    for _ in range(40):
        if app.phase == "end":
            break
        if app.phase in ("intro", "result", "pass"):
            _key()
        if app.phase == "aim":
            app._start_charge()
            for _ in range(40):   # 充满（1.33s）后过充一段
                app.tick()
            app._release_charge()
            for _ in range(6000):
                app.tick()
                if app.phase in ("result", "end"):
                    break
    assert app.phase == "end", f"未到达终局: {app.phase}"
    total = app.session.total
    root.destroy()
    print(f"SELFTEST OK · 蓄力出手验证 · 5回合跑通 · 总分 {total}")
    return True
