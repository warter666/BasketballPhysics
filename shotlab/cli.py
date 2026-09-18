"""SHOT LAB 命令行入口。

  python -m shotlab shot   单次出手（画布 + 面板 + 时间线）
  python -m shotlab mc     蒙特卡洛命中率
  python -m shotlab sweep  速度 × 仰角 命中地图
  python -m shotlab demo   三个经典出手（罚球 / 打板 / 三分）
  python -m shotlab interactive  交互式实验室
  python -m shotlab plot   保存轨迹 PNG（需要 matplotlib）
"""

from __future__ import annotations

import argparse
import shlex
import sys

from .engine import LABEL_CN, Simulator
from .monte_carlo import run_mc
from .params import PRESETS, ShotParams, preset_params
from .render_ascii import render_canvas, render_panel, render_timeline
from .sweep import render_sweep_text, run_sweep


def _win_utf8():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _add_shot_args(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--v0", type=float, default=7.55, help="出手速度 m/s")
    sp.add_argument("--angle", type=float, default=52.5, help="出手仰角 度")
    sp.add_argument("--height", type=float, default=2.0, help="出手高度 m")
    sp.add_argument("--dist", type=float, default=4.19, help="到篮筐中心水平距离 m")
    sp.add_argument("--spin", type=float, default=6.0, help="后旋 rad/s")
    sp.add_argument("--dt", type=float, default=0.002, help="积分步长 s")
    sp.add_argument("--no-drag", action="store_true", help="关闭空气阻力")
    sp.add_argument("--no-magnus", action="store_true", help="关闭 Magnus 力")


def _params_from(args) -> ShotParams:
    return ShotParams(
        v0=args.v0, angle_deg=args.angle, release_height=args.height,
        distance=args.dist, spin=args.spin, dt=args.dt,
        drag=not args.no_drag, magnus=not args.no_magnus,
    )


def _print_shot(params: ShotParams, mc=None, show_timeline=True):
    r = Simulator(params).run()
    print(render_canvas(r, params))
    print()
    print(render_panel(r, params, mc=mc))
    if show_timeline:
        print()
        print(render_timeline(r))
    return r


def cmd_shot(args) -> int:
    p = _params_from(args)
    mc = None
    if args.mc > 0:
        mc = run_mc(p, n=args.mc, seed=args.seed)
        print(f"蒙特卡洛: {mc.n} 次带噪声出手，命中 {mc.hits} 次…\n")
    _print_shot(p, mc=mc)
    if args.plot:
        from .render_plot import plot_shot
        out = args.out or "shots/shot.png"
        plot_shot(_params_from(args), Simulator(_params_from(args)).run(), out)
        print(f"\n轨迹图已保存: {out}")
    return 0


def cmd_mc(args) -> int:
    p = _params_from(args)
    sig = {}
    if args.sig_v0 is not None:
        sig["v0"] = args.sig_v0
    if args.sig_angle is not None:
        sig["angle_deg"] = args.sig_angle
    mc = run_mc(p, n=args.n, seed=args.seed, sigmas=sig or None)
    print(f"  ── Monte Carlo 命中率实验 " + "─" * 26)
    print(f"   名义出手   v0={p.v0:.2f} m/s @ {p.angle_deg:.1f}°, "
          f"h={p.release_height:.2f} m, d={p.distance:.2f} m, ω={p.spin:.1f} rad/s")
    print(f"   执行噪声   σ_v0={mc.sigmas['v0']} m/s, σ_θ={mc.sigmas['angle_deg']}°, "
          f"σ_h={mc.sigmas['release_height']} m, σ_ω={mc.sigmas['spin']} rad/s")
    print(f"   样本数     n={mc.n}, seed={args.seed}")
    bar = "█" * round(mc.rate * 24) + "░" * (24 - round(mc.rate * 24))
    print(f"\n   Hit rate   {bar}  {mc.rate * 100:5.1f}%")
    bar2 = "█" * round(mc.swish_rate * 24) + "░" * (24 - round(mc.swish_rate * 24))
    print(f"   Swish rate {bar2}  {mc.swish_rate * 100:5.1f}%")
    print("\n   结果分布:")
    for label, cnt in sorted(mc.result_labels.items(), key=lambda kv: -kv[1]):
        print(f"     {label:<14} {cnt:5d}  {cnt / mc.n * 100:5.1f}%  {LABEL_CN[label]}")
    return 0


def cmd_sweep(args) -> int:
    p = _params_from(args)
    sw = run_sweep(p, v_min=args.v0_min, v_max=args.v0_max, nv=args.steps_v,
                   a_min=args.angle_min, a_max=args.angle_max, na=args.steps_a)
    print(render_sweep_text(sw))
    return 0


def cmd_demo(_args) -> int:
    for name in ("free_throw", "bank", "three"):
        pre = PRESETS[name]
        p = preset_params(name)
        print(f"\n{'═' * 66}\n  🏀 {name}  —  {pre['label']}\n{'═' * 66}")
        mc = run_mc(p, n=200, seed=13)
        _print_shot(p, mc=mc, show_timeline=(name != "three"))
    return 0


def cmd_plot(args) -> int:
    p = _params_from(args)
    r = Simulator(p).run()
    from .render_plot import plot_shot
    out = plot_shot(r, p, args.out or "shots/shot.png")
    print(f"{r.label} ({r.label_cn})  →  {out}")
    return 0


def cmd_interactive(_args) -> int:
    fields = {"v0": 7.4, "angle": 52.0, "height": 2.0, "dist": 4.19, "spin": 6.0}
    flags = {"drag": True, "magnus": True}
    print(__doc__.strip().splitlines()[0])
    print("命令: run | mc [n] | sweep | set <field> <value> | drag on/off | "
          "magnus on/off | help | quit")
    while True:
        try:
            line = input("\nshotlab> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        parts = shlex.split(line)
        cmd = parts[0].lower()
        try:
            if cmd in ("q", "quit", "exit"):
                return 0
            elif cmd == "help":
                print("set v0 7.4 / set angle 52 / run / mc 400 / sweep / "
                      "drag off / magnus off / quit")
            elif cmd == "set" and len(parts) == 3:
                if parts[1] not in fields:
                    print(f"字段: {', '.join(fields)}")
                    continue
                fields[parts[1]] = float(parts[2])
            elif cmd in ("drag", "magnus") and len(parts) == 2:
                flags[cmd] = parts[1].lower() in ("on", "true", "1")
            elif cmd == "run":
                p = ShotParams(v0=fields["v0"], angle_deg=fields["angle"],
                               release_height=fields["height"],
                               distance=fields["dist"], spin=fields["spin"],
                               drag=flags["drag"], magnus=flags["magnus"])
                _print_shot(p)
            elif cmd == "mc":
                n = int(parts[1]) if len(parts) > 1 else 300
                p = ShotParams(v0=fields["v0"], angle_deg=fields["angle"],
                               release_height=fields["height"],
                               distance=fields["dist"], spin=fields["spin"],
                               drag=flags["drag"], magnus=flags["magnus"])
                mc = run_mc(p, n=n)
                print(f"命中率 {mc.rate * 100:.1f}%  (swish {mc.swish_rate * 100:.1f}%, n={mc.n})")
            elif cmd == "sweep":
                p = ShotParams(v0=fields["v0"], angle_deg=fields["angle"],
                               release_height=fields["height"],
                               distance=fields["dist"], spin=fields["spin"],
                               drag=flags["drag"], magnus=flags["magnus"])
                print(render_sweep_text(run_sweep(p)))
            else:
                print("未知命令，输入 help 查看。")
        except ValueError as e:
            print(f"输入无效: {e}")


def main(argv=None) -> int:
    _win_utf8()
    ap = argparse.ArgumentParser(prog="shotlab", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    sp = sub.add_parser("shot", help="单次出手")
    _add_shot_args(sp)
    sp.add_argument("--mc", type=int, default=300, help="附带的蒙特卡洛样本数（0 关闭）")
    sp.add_argument("--seed", type=int, default=42)
    sp.add_argument("--plot", action="store_true", help="同时保存 PNG")
    sp.add_argument("--out", default=None, help="PNG 输出路径")
    sp.set_defaults(fn=cmd_shot)

    mp = sub.add_parser("mc", help="蒙特卡洛命中率")
    _add_shot_args(mp)
    mp.add_argument("--n", type=int, default=400)
    mp.add_argument("--seed", type=int, default=42)
    mp.add_argument("--sig-v0", type=float, default=None, help="速度噪声 σ m/s")
    mp.add_argument("--sig-angle", type=float, default=None, help="角度噪声 σ °")
    mp.set_defaults(fn=cmd_mc)

    wp = sub.add_parser("sweep", help="参数扫描")
    _add_shot_args(wp)
    wp.add_argument("--v0-min", type=float, default=5.5)
    wp.add_argument("--v0-max", type=float, default=8.5)
    wp.add_argument("--angle-min", type=float, default=42.0)
    wp.add_argument("--angle-max", type=float, default=62.0)
    wp.add_argument("--steps-v", type=int, default=24)
    wp.add_argument("--steps-a", type=int, default=14)
    wp.set_defaults(fn=cmd_sweep)

    dp = sub.add_parser("demo", help="经典出手演示")
    dp.set_defaults(fn=cmd_demo)

    ip = sub.add_parser("interactive", help="交互式实验室")
    ip.set_defaults(fn=cmd_interactive)

    pp = sub.add_parser("plot", help="保存轨迹 PNG")
    _add_shot_args(pp)
    pp.add_argument("--out", default=None)
    pp.set_defaults(fn=cmd_plot)

    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 1
    return args.fn(args)
