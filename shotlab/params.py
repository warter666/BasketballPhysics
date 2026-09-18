"""出手参数与预设（presets）。"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ShotParams:
    """一次出手的全部输入。

    v0             出手速度 m/s
    angle_deg      出手仰角（度，相对水平面）
    release_height 出手高度 m
    distance       出手点到篮筐中心的水平距离 m
    spin           后旋角速度 rad/s（>0 为后旋 backspin）
    drag / magnus  气动开关（做对照实验用）
    dt             积分步长 s（RK4）
    max_time       单次模拟上限 s
    """

    v0: float = 7.55
    angle_deg: float = 52.5
    release_height: float = 2.0
    distance: float = 4.19   # 罚球线：篮筐中心前约 4.19 m
    spin: float = 6.0
    drag: bool = True
    magnus: bool = True
    dt: float = 0.002
    max_time: float = 8.0

    def with_(self, **kw) -> "ShotParams":
        return replace(self, **kw)


# 经典出手档案（参数由 examples/tune.py 网格搜索得到，保证能命中）
PRESETS = {
    "free_throw": {
        "label": "罚球线急停跳投",
        "v0": 7.55,
        "angle_deg": 52.5,
        "release_height": 2.00,
        "distance": 4.19,
        "spin": 6.0,
    },
    "bank": {
        "label": "正面打板",
        "v0": 7.45,
        "angle_deg": 50.0,
        "release_height": 2.00,
        "distance": 3.60,
        "spin": 5.0,
    },
    "three": {
        "label": "三分线干拔",
        "v0": 9.55,
        "angle_deg": 50.0,
        "release_height": 2.20,
        "distance": 7.24,   # NBA 三分弧顶 23.75 ft
        "spin": 7.0,
    },
}


def preset_params(name: str, **overrides) -> ShotParams:
    base = dict(PRESETS[name])
    base.pop("label", None)
    base.update(overrides)
    return ShotParams(**base)
