"""SHOT DUEL · tkinter 火柴人动画界面（Python 标准库，零依赖）。

操作：
  鼠标拖拽画布 = 瞄准（向量长度=力度，方向=仰角）
  ← → 微调仰角   ↑ ↓ 微调力度   Q / E 后旋 -/+   空格 = 出手/继续
  1 2 3 = 双人模式挑选场地
"""

from __future__ import annotations

import math
import tkinter as tk

from shotlab.engine import Simulator

from .scoring import score_shot
from .session import DuelSession, SoloSession

FPS = 30
DT_FRAME = 1.0 / FPS


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
        self.canvas = tk.Canvas(root, width=980, height=560, bg="#101418",
                                highlightthickness=0)
        self.canvas.pack()
        bar = tk.Frame(root, bg="#181d24")
        bar.pack(fill="x")
        self.lbl_aim = tk.Label(bar, text="", fg="#7fd4ff", bg="#181d24",
                                font=("Consolas", 11), width=52, anchor="w")
        self.lbl_aim.pack(side="left", padx=8, pady=4)
        self.lbl_card = tk.Label(bar, text="", fg="#ffd479", bg="#181d24",
                                 font=("Microsoft YaHei UI", 10))
        self.lbl_card.pack(side="left", padx=8)

        # ---- 状态 ----
        self.phase = "boot"      # intro/aim/anim/result/pass/pick/end
        self.aim = dict(v0=7.5, angle=50.0, spin=6.0)
        self.t_round = 0.0       # 本回合已流逝秒数（篮筐相位连续性用）
        self.fly = None          # 飞行播放状态
        self.particles = []      # 风粒子 (x, y)
        self.drag_start = None
        self.drag_now = None
        self.result_shown = None
        self.player = 0          # duel 当前出手玩家
        self.overlay_lines = []
        self.overlay_title = ""
        self._frame = 0

        self._bind()
        self._boot()

    # ------------------------------------------------------------------ 流程
    def _boot(self):
        if self.is_duel:
            if self.session.need_rule_pick():
                self._phase_pick("上一回合平局/结束，请输家挑场地")
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
        self.aim = dict(v0=7.5, angle=50.0, spin=6.0)
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
        self._overlay("回合开始", lines)
        self.phase = "intro"

    def _phase_pick(self, title):
        self.phase = "pick"
        self.session.prepare_offers()
        self.overlay_title = title
        self.overlay_lines = []
        self._redraw()

    def _choose(self, idx):
        offers = self.session.offers
        if not offers or not (0 <= idx < len(offers)):
            return
        self.session.pick_rule(idx)
        self._start_round()

    def fire(self):
        if self.phase != "aim":
            return
        r = self._round()
        params = r.params_by_player[self.player]
        rim_phase = None
        if params.rim_period > 0:
            rim_phase = (params.rim_phase
                         + 2 * math.pi * self.t_round / params.rim_period) % (2 * math.pi)
        result, score = self.session.shoot(
            self.aim["v0"], self.aim["angle"], self.aim["spin"],
            player=self.player, rim_phase=rim_phase)
        self.fly_phase = rim_phase if rim_phase is not None else params.rim_phase
        self.fly = dict(result=result, score=score, t=0.0, released=False,
                        traj=result.trajectory, dt=params.dt, seam=0.0,
                        spin=params.spin)
        self.phase = "anim"

    def _after_result(self):
        r = self._round()
        if self.is_duel:
            if len(r.results) < 2:
                self.player = 1
                self.aim = dict(v0=7.5, angle=50.0, spin=6.0)
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
                self.aim = dict(v0=7.5, angle=50.0, spin=6.0)
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
        c = self.canvas
        c.bind("<Button-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)

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
                else:  # pass
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
                self.fire()
            elif key == "Left":
                self.aim["angle"] = min(89.0, self.aim["angle"] + 0.5)
            elif key == "Right":
                self.aim["angle"] = max(5.0, self.aim["angle"] - 0.5)
            elif key == "Up":
                self.aim["v0"] = min(13.5, self.aim["v0"] + 0.1)
            elif key == "Down":
                self.aim["v0"] = max(1.5, self.aim["v0"] - 0.1)
            elif key in ("q", "Q"):
                self.aim["spin"] = max(-12.0, self.aim["spin"] - 0.5)
            elif key in ("e", "E"):
                self.aim["spin"] = min(12.0, self.aim["spin"] + 0.5)

    def _restart(self):
        if self.is_duel:
            self.session = DuelSession()
        else:
            self.session = SoloSession()
        self.is_duel = isinstance(self.session, DuelSession)
        self._boot()

    def _on_press(self, ev):
        if self.phase == "aim":
            self.drag_start = (ev.x, ev.y)
            self.drag_now = (ev.x, ev.y)

    def _on_drag(self, ev):
        if self.phase == "aim" and self.drag_start:
            self.drag_now = (ev.x, ev.y)
            dx = ev.x - self.drag_start[0]
            dy = self.drag_start[1] - ev.y  # 屏幕y向下 → 取反
            self.aim["angle"] = min(89.0, max(5.0, math.degrees(math.atan2(dy, max(dx, 1)))))
            self.aim["v0"] = min(13.5, max(1.5, math.hypot(dx, dy) * 0.032))

    def _on_release(self, _ev):
        self.drag_start = None

    # ------------------------------------------------------------------ 主循环
    def tick(self):
        self.t_round += DT_FRAME
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
        f = self.fly
        s = f["score"]
        title = f"{s.title}   {'★' * s.stars}"
        self._overlay(title, s.breakdown + [f"本回合得分 {s.pts:+d}"])
        self.phase = "result"

    # ------------------------------------------------------------------ 渲染
    def _domain(self):
        r = self._round()
        p = r.params_by_player[self.player] if r else None
        d = (p.distance if p else 4.2)
        v0 = self.aim["v0"] if self.phase == "aim" else 7.5
        g = (p.gravity if p else 9.81)
        h = (p.release_height if p else 2.0)
        apex = h + v0 * v0 / (2 * g)
        y_max = min(max(4.6, apex * 1.06), 12.0)
        x_max = d + 1.35
        return (-1.9, x_max, 0.0, y_max)

    def _sx(self):
        """坐标系 → 像素映射参数。"""
        x0, x1, y0, y1 = self._domain()
        pad_l, pad_r, pad_t, pad_b = 30, 30, 54, 46
        w = 980 - pad_l - pad_r
        hgt = 560 - pad_t - pad_b
        scale = min(w / (x1 - x0), hgt / (y1 - y0))
        ox = pad_l + (-x0) * scale + (w - (x1 - x0) * scale) / 2
        oy = 560 - pad_b
        return scale, ox, oy

    def _px(self, x, y):
        s, ox, oy = self._sx()
        return ox + x * s, oy - y * s

    def _overlay(self, title, lines):
        """仅设置浮层内容；phase 由调用方显式设置。"""
        self.overlay_title = title
        self.overlay_lines = list(lines)

    def _redraw(self):
        cv = self.canvas
        cv.delete("all")
        fog, _moving = self._rule_flags()
        scale, ox, oy = self._sx()

        # 地面与米尺
        cv.create_line(0, oy, 980, oy, fill="#3a4450", width=2)
        x0m = int(self._domain()[0]) + 1
        while x0m <= self._domain()[1]:
            px, _ = self._px(x0m, 0)
            cv.create_line(px, oy, px, oy + 5, fill="#3a4450")
            cv.create_text(px, oy + 14, text=str(x0m), fill="#5a6675",
                           font=("Consolas", 8))
            x0m += 1

        self._draw_hoop()
        self._draw_particles()
        self._draw_stickman()
        self._draw_aim()
        if self.phase == "anim" and self.fly:
            self._draw_ball_flight(fog)
        self._draw_hud()

        if self.phase in ("intro", "result", "pass", "pick", "end"):
            self._draw_overlay()

    def _draw_hoop(self):
        cv = self.canvas
        r = self._round()
        if not r:
            return
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
        # 篮板
        bx = cx_hoop + 0.375
        x1, y1 = self._px(bx, rh - 0.15)
        x2, y2 = self._px(bx, rh + 0.90)
        cv.create_line(x1, y1, x2, y2, fill="#c8d6e5", width=6)
        # 筐
        fx, fy = self._px(cx_hoop - rr, rh)
        gx, gy = self._px(cx_hoop + rr, rh)
        cv.create_line(fx, fy, gx, gy, fill="#ff6b3d", width=4)
        for px_, py_ in ((fx, fy), (gx, gy)):
            cv.create_oval(px_ - 3, py_ - 3, px_ + 3, py_ + 3, fill="#ff6b3d", outline="")
        # 网
        for k in (0.22, 0.5, 0.78):
            nx1 = cx_hoop - rr + 2 * rr * k
            xq1, yq1 = self._px(cx_hoop - rr * (1 - k * 0.7), rh - 0.26)
            xa, ya = self._px(nx1, rh)
            cv.create_line(xa, ya, xq1, yq1, fill="#8899aa")

    def _draw_particles(self):
        r = self._round()
        if not r:
            return
        p = r.params_by_player[self.player]
        wind = p.wind_ax
        if abs(wind) < 0.1:
            return
        cv = self.canvas
        target = min(30, int(abs(wind) * 10))
        while len(self.particles) < target:
            self.particles.append([self._domain()[0] + (self._domain()[1] - self._domain()[0])
                                   * ((self._frame * 37 + 13 * len(self.particles)) % 100) / 100,
                                   0.4 + (len(self.particles) * 0.53) % 3.2])
        self.particles = self.particles[:target]
        x0, x1, _, _ = self._domain()
        for pt in self.particles:
            pt[0] += wind * 0.5 * DT_FRAME
            if pt[0] > x1:
                pt[0] = x0
            if pt[0] < x0:
                pt[0] = x1
            px, py = self._px(pt[0], pt[1])
            dx = 6 if wind > 0 else -6
            cv.create_line(px, py, px + dx, py, fill="#4f6b8f", width=1)

    def _stickman_poses(self):
        """返回当前应绘制的姿态（含动画插值）。"""
        aim_rad = math.radians(self.aim["angle"])
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
        # 瞄准姿态：手臂指向瞄准方向
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
        active = (not self.is_duel) or self.phase != "pass"
        color = "#7fd4ff" if (not self.is_duel or self.player == 0) else "#ffb3ba"

        def P(name):
            x, y = pose[name]
            px, py = self._px(sx + x, y)
            return px, py

        hx, hy = P("head")
        r_head = 0.115 * s
        cv.create_oval(hx - r_head, hy - r_head, hx + r_head, hy + r_head,
                       outline=color, width=2)
        nx, ny = P("neck")
        px_, py_ = P("hip")
        cv.create_line(nx, ny, px_, py_, fill=color, width=3)
        for a, b in (("hip", "lknee"), ("lknee", "lfoot"),
                     ("hip", "rknee"), ("rknee", "rfoot"),
                     ("neck", "lelbow"), ("lelbow", "lhand"),
                     ("neck", "relbow"), ("relbow", "rhand")):
            x1, y1 = P(a)
            x2, y2 = P(b)
            cv.create_line(x1, y1, x2, y2, fill=color, width=2)
        if self.is_duel:
            tag = self.session.names[self.player]
            cv.create_text(hx, hy - r_head - 12, text=tag, fill=color,
                           font=("Microsoft YaHei UI", 10))
        # 瞄准阶段的球在手上
        if self.phase == "aim":
            bx, by = P("rhand")
            rb = 0.12 * s
            cv.create_oval(bx - rb, by - rb, bx + rb, by + rb,
                           fill="#e67e22", outline="#f9e79f")

    def _draw_aim(self):
        if self.phase != "aim":
            return
        cv = self.canvas
        r = self._round()
        p = r.params_by_player[self.player]
        fog, _ = self._rule_flags()
        a = math.radians(self.aim["angle"])
        # 箭头
        x0, y0 = self._px(0.15, p.release_height)
        x1, y1 = self._px(0.15 + 1.15 * math.cos(a) * (self.aim["v0"] / 9.0),
                          p.release_height + 1.15 * math.sin(a) * (self.aim["v0"] / 9.0))
        cv.create_line(x0, y0, x1, y1, fill="#f9e79f", width=2, arrow="last")
        # 预测弹道（技能"物理之眼"且无雾）
        if r.preview[self.player] and not fog:
            sim = Simulator(p.with_(v0=self.aim["v0"],
                                    angle_deg=self.aim["angle"],
                                    spin=self.aim["spin"])).run()
            for x, y in sim.trajectory[::8]:
                px, py = self._px(x, y)
                cv.create_oval(px - 1, py - 1, px + 1, py + 1,
                               fill="#5dade2", outline="")

    def _draw_ball_flight(self, fog):
        f = self.fly
        cv = self.canvas
        r = self._round()
        p = r.params_by_player[self.player]
        s, _, _ = self._sx()
        t_rel = 0.30
        if not f["released"]:
            return
        idx = min(int((f["t"] - t_rel) / f["dt"]), len(f["traj"]) - 1)
        traj = f["traj"]
        if not fog:
            # 尾迹
            for j in range(max(0, idx - 26), idx, 3):
                x, y = traj[j]
                px, py = self._px(x, y)
                cv.create_oval(px - 1.2, py - 1.2, px + 1.2, py + 1.2,
                               fill="#7d5a3c", outline="")
        # 球（雾中隐藏）
        if not fog:
            x, y = traj[idx]
            bx, by = self._px(x, y)
            rb = p.ball_radius * s
            cv.create_oval(bx - rb, by - rb, bx + rb, by + rb,
                           fill="#e67e22", outline="#f9e79f", width=2)
            ang = f["seam"]
            cv.create_line(bx - rb * math.cos(ang), by - rb * math.sin(ang),
                           bx + rb * math.cos(ang), by + rb * math.sin(ang),
                           fill="#a04000")

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
            cv.create_text(490, 16, text="  ·  ".join(bits), fill="#cfd8dc",
                           font=("Microsoft YaHei UI", 12))
        aim_txt = (f"力度 {self.aim['v0']:5.2f} m/s   仰角 {self.aim['angle']:5.1f}°   "
                   f"后旋 {self.aim['spin']:5.1f} rad/s")
        self.lbl_aim.config(text=aim_txt)
        if r:
            sk = r.skills[self.player]
            self.lbl_card.config(text=f"{sk.icon} {sk.name}：{sk.desc}")

    def _draw_overlay(self):
        cv = self.canvas
        cv.create_rectangle(140, 120, 840, 440, fill="#0d1117", outline="#3a4450", width=2)
        cv.create_text(490, 156, text=self.overlay_title, fill="#ffd479",
                       font=("Microsoft YaHei UI", 20, "bold"))
        y = 205
        big = self.phase in ("result", "pick", "end")
        for line in self.overlay_lines[:9]:
            cv.create_text(490, y, text=line,
                           fill="#e6edf3" if not big else "#cfd8dc",
                           font=("Microsoft YaHei UI", 13 if big else 12))
            y += 26
        if self.phase == "pick":
            for i, rule in enumerate(self.session.offers):
                bx = 200 + i * 210
                cv.create_rectangle(bx, 300, bx + 190, 396,
                                    fill="#1b2430", outline="#7fd4ff", width=2,
                                    tags=f"opt{i}")
                cv.create_text(bx + 95, 322, text=f"[{i + 1}] {rule.icon} {rule.name}",
                               fill="#ffd479", font=("Microsoft YaHei UI", 13, "bold"),
                               tags=f"opt{i}")
                cv.create_text(bx + 95, 350, text=rule.desc, fill="#aebbc8",
                               font=("Microsoft YaHei UI", 10), width=180,
                               tags=f"opt{i}")
                cv.create_text(bx + 95, 380, text="★" * rule.stars, fill="#ff6b3d",
                               font=("Consolas", 10), tags=f"opt{i}")
                cv.tag_bind(f"opt{i}", "<Button-1>",
                            lambda _e, i=i: self._choose(i))
        elif self.phase != "pass":
            cv.create_text(490, 415, text="—— 空格 继续 ——", fill="#7fd4ff",
                           font=("Microsoft YaHei UI", 11))
        else:
            cv.create_text(490, 415, text="—— 空格 继续 ——", fill="#7fd4ff",
                           font=("Microsoft YaHei UI", 11))


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
    """无头自检：驱动完整对局流程，验证动画状态机与计分接线。"""
    root = tk.Tk()
    root.withdraw()
    session = SoloSession(seed=3)
    app = ShotDuelApp(root, session, selftest=True)
    app.tick()
    assert app.phase == "intro", app.phase
    app._on_key(type("E", (), {"keysym": "space"})())
    assert app.phase == "aim"
    app.aim.update(v0=7.55, angle=52.5, spin=6.0)
    app.fire()
    assert app.phase == "anim"
    for _ in range(4000):
        app.tick()
        if app.phase == "result":
            break
    assert app.phase == "result", f"anim 未收敛: {app.phase}"
    assert len(app.session.history) == 1
    # 打完剩余回合（状态机无关的推进循环）
    def _key(k="space"):
        app._on_key(type("E", (), {"keysym": k})())
    for _ in range(40):
        if app.phase == "end":
            break
        if app.phase in ("intro", "result", "pass"):
            _key()
        if app.phase == "aim":
            app.aim.update(v0=7.55, angle=52.5, spin=6.0)
            app.fire()
            for _ in range(6000):
                app.tick()
                if app.phase in ("result", "end"):
                    break
    assert app.phase == "end", f"未到达终局: {app.phase}"
    total = app.session.total
    root.destroy()
    print(f"SELFTEST OK · 5回合跑通 · 总分 {total}")
    return True
