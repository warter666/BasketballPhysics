"""入口：python -m shotduel [--mode solo|duel] [--cli] [--seed N] [--selftest]"""

from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(
        prog="shotduel", description="SHOT DUEL · 斗球实验室")
    ap.add_argument("--mode", choices=["solo", "duel"], default="solo",
                    help="solo=单人生存赛季，duel=双人对决（热座）")
    ap.add_argument("--cli", action="store_true", help="终端模式（默认 tkinter 窗口）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子")
    ap.add_argument("--selftest", action="store_true", help="无头自检")
    args = ap.parse_args(argv)

    if args.selftest:
        from .gui import run_selftest
        return 0 if run_selftest() else 1
    if args.cli:
        from .cli import run_cli
        run_cli(args.mode, args.seed)
        return 0
    try:
        from .gui import run_gui
        run_gui(args.mode, args.seed)
    except Exception as e:  # tkinter 缺失等 → 退化到终端
        print(f"图形界面不可用（{e}），切换到终端模式。\n")
        from .cli import run_cli
        run_cli(args.mode, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
