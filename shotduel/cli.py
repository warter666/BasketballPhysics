"""SHOT DUEL · 终端退化模式（无 tkinter 环境也能玩同一套对局）。"""

from __future__ import annotations

from shotlab.params import ShotParams
from shotlab.render_ascii import render_canvas

from .session import DuelSession, SoloSession


def _ask(prompt: str, default: float) -> float:
    raw = input(prompt).strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print("  输入无效，使用默认值")
        return default


def _aim_prompt(session, player: int = 0):
    v0 = _ask(f"  力度 m/s [7.5]: ", 7.5)
    angle = _ask(f"  仰角 ° [50]: ", 50.0)
    spin = _ask(f"  后旋 rad/s [6]: ", 6.0)
    return v0, angle, spin


def _show_round_header(session, r):
    print(f"\n{'═' * 62}")
    print(f"  回合 {r.index + 1} · {r.rule_desc}")
    for i, sk in enumerate(r.skills):
        who = session.names[i] if isinstance(session, DuelSession) else "你"
        print(f"  {who} 抽到 {sk.icon} {sk.name}（{sk.kind}）：{sk.desc}")
    p = r.params_by_player[0]
    print(f"  篮筐距离 {p.distance:.2f} m · 高度 {p.rim_height:.2f} m"
          + (f" · 风 {p.wind_ax:+.1f} m/s²" if abs(p.wind_ax) > 1e-6 else ""))


def _show_shot(result, params, score):
    print(render_canvas(result, params))
    for line in score.breakdown:
        print("   " + line)
    print(f"   ⇒ 本回合得分 {score.pts:+d}  {'★' * score.stars}")


def run_cli(mode: str = "solo", seed=None):
    if mode == "duel":
        session = DuelSession(seed=seed)
        print("SHOT DUEL · 双人对决（终端模式）")
        while not session.match_over:
            if session.need_rule_pick():
                offers = session.prepare_offers()
                chooser = session.names[session.next_chooser]
                print(f"\n  ✋ {chooser} 挑选下一块场地：")
                for i, rule in enumerate(offers, 1):
                    print(f"   [{i}] {rule.icon} {rule.name}（★{rule.stars}）— {rule.desc}")
                idx = int(_ask("  输入 1-3: ", "1")) - 1
                r = session.pick_rule(max(0, min(2, idx)))
            else:
                r = session.start_round()
            for player in range(2):
                _show_round_header(session, r)
                input(f"  —— 把键盘交给 {session.names[player]}（回车）")
                v0, angle, spin = _aim_prompt(session, player)
                result, score = session.shoot(v0, angle, spin, player=player)
                _show_shot(result, r.params_by_player[player], score)
            print("\n" + session.conclude_round())
        champ = session.names[session.champion]
        print(f"\n  🏆 {champ} 赢得对决！"
              f"（{session.round_wins[0]}:{session.round_wins[1]}）")
    else:
        session = SoloSession(seed=seed)
        print("SHOT DUEL · 单人生存赛季（终端模式）")
        while not session.finished:
            r = session.start_round()
            _show_round_header(session, r)
            v0, angle, spin = _aim_prompt(session, 0)
            result, score = session.shoot(v0, angle, spin)
            _show_shot(result, r.params_by_player[0], score)
        print()
        print(session.summary())
