# 🧪 BasketballPhysics — SHOT LAB

> 2D 篮球投篮物理实验室：调参数 → 看轨迹 → 算命中率。
> 纯 Python 标准库实现，零依赖即可运行（绘图功能可选装 matplotlib）。

```text
                                                                    ▌         ← 篮板
                             ························               ▌
                        ······                       ······         ▌
                   ·····                                  ·····     ▌
                ····                                       ●──────● ▌         ← RIM 3.05 m
             ····
          ····
       ····
     ◎··
─────┴─────────────┴─────────────┴────────────┴─────────────┴────────────┴──
     0             1             2            3             4            5

  ── SHOT LAB ────────────────────────────────────────────
   Velocity     7.55 m/s        Drag    ON
   Angle        52.5 °          Magnus  ON
   Release h    2.00 m          Spin    6.0 rad/s
   Distance     4.19 m          dt      2.0 ms
  ─────────────────────────────────────────────────
   RESULT     SWISH ✓✓  空心入网
   Flight       0.98 s          Apex    3.75 m
   Entry         5.5 m/s @  41.7°   偏心 +0.003 m
  ─────────────────────────────────────────────────
   Probability
   ██████████████░░░░░░   68.5%
   (n=200, swish 27.5%, σ_v0=0.12 m/s, σ_θ=0.8°)
```

## 快速开始

```bash
cd BasketballPhysics

# 单次出手（默认 = 罚球线空心球），附带 300 次蒙特卡洛
python -m shotlab shot

# 三个经典出手：罚球 / 打板 / 三分
python -m shotlab demo

# 交互式实验室（run / mc / sweep / set v0 8.0 …）
python -m shotlab interactive

# 蒙特卡洛命中率实验
python -m shotlab mc --n 400 --sig-v0 0.15

# 速度 × 仰角 命中地图
python -m shotlab sweep

# 保存轨迹 PNG（需要 pip install matplotlib）
python -m shotlab plot --out shots/ft.png

# 测试
python -m unittest discover -s tests
```

## 物理模型

**几何**（FIBA/NBA 标准尺寸，`constants.py`）：

| 参数 | 值 |
|---|---|
| 篮筐高度 | 3.05 m |
| 筐内径 | 45.72 cm（半径 0.2286 m） |
| 筐圈圆管截面半径 | 1.6 cm |
| 筐心距篮板面 | 0.375 m |
| 篮板 | 2.90 ~ 3.95 m |
| 球 | 质量 0.624 kg，半径 0.12 m |

**动力学**（RK4 积分，默认步长 2 ms）：

* 重力 + 空气阻力 `F_d = -½·ρ·Cd·A·|v|·v`（Cd = 0.50）
* Magnus 力（后旋升力）`F_m = ½·ρ·Cl·A·|v|²·(ẑ×v̂)`，升力系数取旋转球经验拟合 `Cl = 1/(2 + v/(r·ω))`
* 后旋在飞行中保持恒定，仅在碰撞时通过摩擦力矩改变

**碰撞**：

* 篮板 = 竖直线段，法向恢复系数 0.70；筐前/后沿 = 圆管截面（圆-圆碰撞），恢复系数 0.45
* 切向摩擦会同时改变线速度和自旋（球在筐上会"咬"住旋转）
* 校验过的物理事实：模型给出的罚球所需出手速度 ≈ 7.5 m/s，与真实测量值（7.3~7.9 m/s）一致

**得分判定**：

* 球心自上而下穿过筐平面，且位于前/后筐点之间 → 得分（空心 / 弹框入 / 打板入）
* 球自下而上穿过筐平面 → 违例，不得分（对应真实规则）
* 触地未进即终止（2D 模型中地面反弹不可能再达到筐高度）

**结果分类**：`SWISH 空心入网` / `RIM_IN 弹框入筐` / `BANK_IN 打板入筐` / `RIM_OUT 弹框不中` / `BOARD_MISS 打板不中` / `AIRBALL_SHORT/LONG 三不沾` / `VIOLATION 违例`

## 蒙特卡洛命中率

给名义出手叠加"手感噪声"（默认 σ_v0=0.12 m/s，σ_θ=0.8°，σ_h=0.04 m，σ_ω=0.5 rad/s），
重复 N 次模拟统计命中率。默认噪声下罚球线空心球命中率约 **67%**，接近真实球员水平。

> ⚠️ 局限：本实验室是 **2D 侧视模型**，没有横向（左右偏移）误差维度，
> 因此绝对命中率偏乐观；适合研究纵向参数敏感性，不适合直接当作真实命中率。

## 项目结构

```text
BasketballPhysics/
├── shotlab/
│   ├── constants.py    # 物理与球场几何常量
│   ├── params.py       # 出手参数 + 经典出手预设
│   ├── engine.py       # RK4 物理引擎 + 碰撞 + 得分判定
│   ├── render_ascii.py # ASCII 画布 + SHOT LAB 面板
│   ├── render_plot.py  # matplotlib 绘图（可选）
│   ├── monte_carlo.py  # 命中率实验
│   ├── sweep.py        # 参数扫描
│   └── cli.py          # 命令行入口
├── tests/              # 13 个测试：解析解对照 / 碰撞 / 得分 / 实验
├── examples/tune.py    # 网格搜索经典出手参数
└── ROADMAP.md          # 里程碑与 Issue 列表
```

## 与 HoopEvolution 的关系

本项目的 `Simulator` 就是未来 **HoopEvolution**（CSI + Evolution 合体）的
**比赛模拟器底座**：进化算法生成战术 → 战术分解为出手参数分布 → 用本引擎推演命中分布 →
作为 reward 反馈给进化循环。

详见 [ROADMAP.md](ROADMAP.md) 与上级 [BASKETBALL_ROADMAP.md](../BASKETBALL_ROADMAP.md)。

## License

MIT
