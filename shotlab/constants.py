"""物理与球场几何常量（SI 单位）。

坐标系约定见 engine.py 模块注释。数值取 FIBA/NBA 标准球场尺寸：
篮筐高度 3.05 m，筐内径 45.72 cm，筐圈中心距篮板面 0.375 m，
篮板下沿 2.90 m、上沿 3.95 m，标准 7 号球质量 0.624 kg、半径约 0.12 m。
"""

# --- 重力与空气 ---
G = 9.81                 # m/s^2
RHO_AIR = 1.225          # kg/m^3

# --- 篮球 ---
BALL_MASS = 0.624        # kg（22 oz）
BALL_RADIUS = 0.12       # m
BALL_AREA = 3.141592653589793 * BALL_RADIUS ** 2
BALL_INERTIA = (2.0 / 3.0) * BALL_MASS * BALL_RADIUS ** 2  # 薄壳球
DRAG_COEFF = 0.50        # 篮球典型 Cd ≈ 0.47~0.54

# --- 篮筐 / 篮板几何 ---
RIM_HEIGHT = 3.05        # m
RIM_RADIUS = 0.2286      # m（筐开口半径，内径 45.72 cm）
RIM_TUBE_RADIUS = 0.016  # m（筐圈圆管截面半径）
RIM_CENTER_FROM_BOARD = 0.375  # m（筐心到篮板面）
BOARD_BOTTOM = 2.90      # m
BOARD_TOP = 3.95         # m

# --- 碰撞参数 ---
BOARD_RESTITUTION = 0.70   # 篮板法向恢复系数
RIM_RESTITUTION = 0.45     # 筐圈法向恢复系数
FRICTION_MU = 0.35         # 接触切向摩擦系数
GROUND_RESTITUTION = 0.65

# --- 便于检查的派生尺寸 ---
# 筐圈后沿到篮板的缝隙 = 0.375 - 0.2286 = 0.1464 m
# 球 + 筐管直径的一半 = 0.136 m → 球几乎卡不进筐后沿与篮板之间（与真实球场一致）
