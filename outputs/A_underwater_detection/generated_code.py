"""
2026年重庆邮电大学数学建模竞赛 A题: 水下目标探测与定位

深海铁锰结核探测 — 多波束声呐回波定位模型

坐标系: 海平面为XOY平面, Z轴竖直向上, 探测船(0,0,0)
声速: c = 1500 m/s (海底沉积物中)

Q1: 由5个船位回波时间定位2个点状结核
Q2: 由4个声呐位置回波延迟定位球形结核(中心+半径)
Q3: 推导船沿X轴移动时回波时间t与x的函数关系
Q4: 2D等时线分析 + 梯度路径规划
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import json
import os
import sys
import logging
from dataclasses import dataclass
from typing import Tuple, List

# ============================================================
# 日志与目录
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(SCRIPT_DIR, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(SCRIPT_DIR, "execution.log"),
                            mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================
# 全局参数
# ============================================================
C = 1500.0  # 声速 m/s


# ============================================================
# Q1: 定位两个点状结核
# ============================================================
def solve_q1():
    """
    Q1: 探测船在5个位置测量两个结核的回波时间, 求结核坐标。

    模型: 结核在海底平面 z=0 上, 坐标 (x, y, 0)
    回波时间: t = 2 * sqrt((x_s - x_n)^2 + (y_s - y_n)^2) / c
    船位: (x, 0, 0), x ∈ {-100, -50, 0, 50, 100}

    对每个结核, 有5个方程, 3个未知数 (x_n, y_n, h_n)
    使用最小二乘法求解。
    """
    logger.info("=" * 60)
    logger.info("Q1: 定位两个点状结核")
    logger.info("=" * 60)

    # 数据
    ship_x = np.array([-100.0, -50.0, 0.0, 50.0, 100.0])
    t_A_ms = np.array([136.78, 134.45, 133.42, 133.78, 135.21])
    t_B_ms = np.array([140.32, 137.89, 136.78, 136.24, 138.45])

    t_A = t_A_ms / 1000.0  # 转换为秒
    t_B = t_B_ms / 1000.0

    # 距离 = t * c / 2
    d_A = t_A * C / 2.0
    d_B = t_B * C / 2.0

    logger.info(f"结核A回波时间 (ms): {t_A_ms.tolist()}")
    logger.info(f"结核A距离 (m): {d_A.tolist()}")
    logger.info(f"结核B回波时间 (ms): {t_B_ms.tolist()}")
    logger.info(f"结核B距离 (m): {d_B.tolist()}")

    # 求解结核A
    pos_A = locate_point_nodule(ship_x, d_A, "A")
    # 求解结核B
    pos_B = locate_point_nodule(ship_x, d_B, "B")

    logger.info(f"结核A坐标: ({pos_A[0]:.2f}, {pos_A[1]:.2f}, {pos_A[2]:.2f}) m")
    logger.info(f"结核B坐标: ({pos_B[0]:.2f}, {pos_B[1]:.2f}, {pos_B[2]:.2f}) m")

    # 验证
    logger.info("--- 验证 ---")
    for i, xs in enumerate(ship_x):
        d_calc_A = np.sqrt((xs - pos_A[0])**2 + pos_A[1]**2 + pos_A[2]**2)
        t_calc_A = 2 * d_calc_A / C * 1000
        d_calc_B = np.sqrt((xs - pos_B[0])**2 + pos_B[1]**2 + pos_B[2]**2)
        t_calc_B = 2 * d_calc_B / C * 1000
        logger.info(f"  x={xs:.0f}: A实测={t_A_ms[i]:.2f}ms 计算={t_calc_A:.2f}ms | "
                     f"B实测={t_B_ms[i]:.2f}ms 计算={t_calc_B:.2f}ms")

    # 绘图
    plot_q1(ship_x, t_A_ms, t_B_ms, pos_A, pos_B)

    return {
        'nodule_A': {'x': float(pos_A[0]), 'y': float(pos_A[1]), 'z': float(pos_A[2])},
        'nodule_B': {'x': float(pos_B[0]), 'y': float(pos_B[1]), 'z': float(pos_B[2])},
    }


def locate_point_nodule(ship_x, distances, name):
    """
    非线性最小二乘定位点状结核。

    模型: d_i = sqrt((x_si - x_n)^2 + y_n^2 + z_n^2)
    未知数: (x_n, y_n, z_n)
    方法: 线性化初始解 + Levenberg-Marquardt局部优化
    """
    d_sq = distances**2

    # Step 1: 线性化初始解
    # d_i^2 = x_si^2 - 2*x_si*x_n + (x_n^2 + y_n^2 + z_n^2)
    # 令 a = x_n, b = x_n^2 + y_n^2 + z_n^2
    A_mat = np.column_stack([2 * ship_x, -np.ones_like(ship_x)])
    b_vec = ship_x**2 - d_sq
    result, _, _, _ = np.linalg.lstsq(A_mat, b_vec, rcond=None)
    x0 = result[0]
    R_sq = result[1]  # = x_n^2 + y_n^2 + z_n^2

    # 分配 y 和 z (假设 z=0 优先, 即海底平面)
    yz_sq = max(R_sq - x0**2, 0)
    y0 = np.sqrt(yz_sq)
    z0 = 0.0

    logger.info(f"  {name} 初始解: x={x0:.2f}, y={y0:.2f}, z={z0:.2f}")

    # Step 2: 非线性最小二乘 (梯度下降 + 自适应步长)
    def cost(p):
        d_calc = np.sqrt((ship_x - p[0])**2 + p[1]**2 + p[2]**2)
        return np.sum((d_calc - distances)**2)

    p = np.array([x0, y0, z0])
    lr = 1.0
    eps = 1e-8
    prev_cost = cost(p)

    for it in range(5000):
        grad = np.zeros(3)
        c0 = cost(p)
        for k in range(3):
            pe = p.copy()
            pe[k] += eps
            grad[k] = (cost(pe) - c0) / eps
        gnorm = np.linalg.norm(grad)
        if gnorm < 1e-15:
            break
        p_new = p - lr * grad / gnorm
        new_cost = cost(p_new)
        if new_cost < prev_cost:
            p = p_new
            prev_cost = new_cost
            lr = min(lr * 1.1, 10.0)
        else:
            lr *= 0.5
            if lr < 1e-10:
                break

    x_n, y_n, z_n = p
    final_cost = cost(p)
    rms = np.sqrt(final_cost / len(distances)) * 1000  # mm

    logger.info(f"结核{name}: x={x_n:.2f}, y={y_n:.2f}, z={z_n:.2f} (RMS={rms:.2f}mm)")

    return p


def plot_q1(ship_x, t_A_ms, t_B_ms, pos_A, pos_B):
    """Q1可视化: 回波时间曲线 + 结核位置"""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # (a) 回波时间 vs 船位
    ax = axes[0]
    ax.plot(ship_x, t_A_ms, 'bo-', markersize=8, linewidth=2, label='Nodule A')
    ax.plot(ship_x, t_B_ms, 'rs-', markersize=8, linewidth=2, label='Nodule B')
    ax.set_xlabel('Ship X Position (m)')
    ax.set_ylabel('Echo Time (ms)')
    ax.set_title('(a) Echo Time vs Ship Position')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (b) 距离 vs 船位
    ax = axes[1]
    d_A = t_A_ms * C / 2.0 / 1000  # km
    d_B = t_B_ms * C / 2.0 / 1000
    ax.plot(ship_x, d_A, 'bo-', markersize=8, linewidth=2, label='Nodule A')
    ax.plot(ship_x, d_B, 'rs-', markersize=8, linewidth=2, label='Nodule B')
    ax.set_xlabel('Ship X Position (m)')
    ax.set_ylabel('Distance (km)')
    ax.set_title('(b) Distance vs Ship Position')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (c) 结核位置俯视图
    ax = axes[2]
    ax.plot(pos_A[0], pos_A[1], 'b^', markersize=15, label=f'A ({pos_A[0]:.1f}, {pos_A[1]:.1f})')
    ax.plot(pos_B[0], pos_B[1], 'rv', markersize=15, label=f'B ({pos_B[0]:.1f}, {pos_B[1]:.1f})')
    for xs in ship_x:
        ax.axvline(x=xs, color='gray', linestyle='--', alpha=0.3)
    ax.plot(ship_x, np.zeros_like(ship_x), 'k.', markersize=10, label='Ship positions')
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_title('(c) Nodule Positions (Top View)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal')

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'q1_localization.png'), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Q1 图表已保存")


# ============================================================
# Q2: 定位球形结核
# ============================================================
def solve_q2():
    """
    Q2: 由4个声呐位置的回波延迟, 求球形结核的球心和半径。

    模型: 球心 (x_c, y_c, z_c), 半径 R
    回波延迟 t_i 对应距离 d_i = t_i * c / 2
    声呐到球心距离: D_i = d_i + R
    D_i^2 = (x_si - x_c)^2 + (y_si - y_c)^2 + (z_si - z_c)^2

    4个方程, 4个未知数 (x_c, y_c, z_c, R)
    """
    logger.info("=" * 60)
    logger.info("Q2: 定位球形结核")
    logger.info("=" * 60)

    # 数据
    sonar_pos = np.array([
        [0.0, 0.0, 0.0],
        [50.0, 0.0, 0.0],
        [0.0, 50.0, 0.0],
        [50.0, 50.0, 0.0],
    ])
    t_delay_ms = np.array([133.42, 135.89, 136.24, 138.57])
    t_delay = t_delay_ms / 1000.0

    # 距离 = t * c / 2
    d_meas = t_delay * C / 2.0

    logger.info(f"声呐位置: {sonar_pos.tolist()}")
    logger.info(f"回波延迟 (ms): {t_delay_ms.tolist()}")
    logger.info(f"测量距离 (m): {d_meas.tolist()}")

    # 非线性最小二乘: D_i = d_i + R
    # 声呐到球心距离: D_i = sqrt((x_si-x_c)^2 + (y_si-y_c)^2 + (z_si-z_c)^2)
    # 约束: D_i = d_i + R (声呐到球面距离 = d_i, 球心距离 = d_i + R)

    def cost(params):
        x_c, y_c, z_c, R = params
        D_calc = np.sqrt(np.sum((sonar_pos - np.array([x_c, y_c, z_c]))**2, axis=1))
        return np.sum((D_calc - (d_meas + R))**2)

    # 网格搜索 + 局部优化
    best_cost = np.inf
    best_p = None
    for x0 in np.linspace(-20, 70, 8):
        for y0 in np.linspace(-20, 70, 8):
            for z0 in np.linspace(-120, 0, 8):
                for R0 in [1, 3, 5, 8, 10, 15]:
                    p0 = np.array([x0, y0, z0, R0])
                    c = cost(p0)
                    if c < best_cost:
                        best_cost = c
                        best_p = p0

    # 局部梯度下降
    params = best_p.copy()
    lr = 0.001
    eps = 1e-7
    for it in range(5000):
        grad = np.zeros(4)
        c0 = cost(params)
        for k in range(4):
            pe = params.copy()
            pe[k] += eps
            grad[k] = (cost(pe) - c0) / eps
        params -= lr * grad
        if it % 1000 == 0:
            lr *= 0.8

    x_c, y_c, z_c, R = params
    sol_cost = cost(params)

    logger.info(f"球心坐标: ({x_c:.2f}, {y_c:.2f}, {z_c:.2f}) m")
    logger.info(f"半径: {R:.2f} m")
    logger.info(f"残差: {sol_cost:.6f}")

    # 验证
    logger.info("--- 验证 ---")
    for i in range(4):
        D_calc = np.sqrt(np.sum((sonar_pos[i] - np.array([x_c, y_c, z_c]))**2))
        t_calc = 2 * (D_calc - R) / C * 1000
        logger.info(f"  声呐{i+1}: 实测={t_delay_ms[i]:.2f}ms 计算={t_calc:.2f}ms")

    plot_q2(sonar_pos, t_delay_ms, np.array([x_c, y_c, z_c]), R)

    return {
        'center': {'x': float(x_c), 'y': float(y_c), 'z': float(z_c)},
        'radius': float(R),
        'residual': float(sol_cost),
    }


def plot_q2(sonar_pos, t_ms, center, R):
    """Q2可视化: 球形结核3D示意"""
    fig = plt.figure(figsize=(16, 5))

    # (a) 3D视图
    ax1 = fig.add_subplot(131, projection='3d')
    ax1.scatter(*sonar_pos.T, c='blue', s=100, marker='^', label='Sonar')
    ax1.scatter(*center, c='red', s=100, marker='o', label='Sphere Center')

    # 画球体
    u = np.linspace(0, 2*np.pi, 30)
    v = np.linspace(0, np.pi, 20)
    xs = center[0] + R * np.outer(np.cos(u), np.sin(v))
    ys = center[1] + R * np.outer(np.sin(u), np.sin(v))
    zs = center[2] + R * np.outer(np.ones_like(u), np.cos(v))
    ax1.plot_surface(xs, ys, zs, alpha=0.2, color='red')

    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Y (m)')
    ax1.set_zlabel('Z (m)')
    ax1.set_title('(a) 3D View')
    ax1.legend()

    # (b) 俯视图
    ax2 = fig.add_subplot(132)
    ax2.scatter(sonar_pos[:, 0], sonar_pos[:, 1], c='blue', s=100, marker='^', label='Sonar')
    ax2.scatter(center[0], center[1], c='red', s=100, marker='o', label='Center')
    circle = plt.Circle((center[0], center[1]), R, fill=False, color='red',
                         linestyle='--', linewidth=2)
    ax2.add_patch(circle)
    ax2.set_xlabel('X (m)')
    ax2.set_ylabel('Y (m)')
    ax2.set_title('(b) Top View')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_aspect('equal')

    # (c) 回波延迟对比
    ax3 = fig.add_subplot(133)
    labels = [f'P{i+1}' for i in range(4)]
    x_pos = np.arange(4)
    ax3.bar(x_pos - 0.15, t_ms, 0.3, label='Measured', color='blue', alpha=0.7)
    # 计算理论值
    d_calc = np.sqrt(np.sum((sonar_pos - center)**2, axis=1))
    t_calc = 2 * (d_calc - R) / C * 1000
    ax3.bar(x_pos + 0.15, t_calc, 0.3, label='Calculated', color='red', alpha=0.7)
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(labels)
    ax3.set_ylabel('Echo Delay (ms)')
    ax3.set_title('(c) Measured vs Calculated')
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'q2_sphere.png'), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Q2 图表已保存")


# ============================================================
# Q3: 回波时间函数 t(x)
# ============================================================
def solve_q3():
    """
    Q3: 船沿X轴移动 (x, 0, 0), 目标在 (100, 50, -100)。

    (1) 推导 t(x) 的函数关系
    (2) 绘制 t-x 曲线, 分析几何特征
    """
    logger.info("=" * 60)
    logger.info("Q3: 回波时间函数 t(x)")
    logger.info("=" * 60)

    # 目标参数
    x_t, y_t, z_t = 100.0, 50.0, -100.0

    # (1) 推导
    # 船位: (x, 0, 0)
    # 距离: d(x) = sqrt((x - x_t)^2 + y_t^2 + z_t^2)
    # 回波时间: t(x) = 2*d(x)/c = 2*sqrt((x-100)^2 + 50^2 + 100^2) / 1500

    logger.info("推导:")
    logger.info("  船位: (x, 0, 0)")
    logger.info(f"  目标: ({x_t}, {y_t}, {z_t})")
    logger.info("  d(x) = sqrt((x-100)^2 + 50^2 + 100^2)")
    logger.info("  t(x) = 2*d(x)/c = 2*sqrt((x-100)^2 + 12500) / 1500")

    # 数值计算
    x_arr = np.linspace(-200, 400, 500)
    d_arr = np.sqrt((x_arr - x_t)**2 + y_t**2 + z_t**2)
    t_arr = 2 * d_arr / C * 1000  # ms

    # 最小回波时间
    idx_min = np.argmin(t_arr)
    x_min = x_arr[idx_min]
    t_min = t_arr[idx_min]
    d_min = d_arr[idx_min]

    logger.info(f"最短回波时间: t_min = {t_min:.2f} ms at x = {x_min:.1f} m")
    logger.info(f"最短距离: d_min = {d_min:.2f} m")
    logger.info(f"理论最小: x = {x_t} = {x_t:.1f} m, d = sqrt(y_t^2+z_t^2) = {np.sqrt(y_t**2+z_t**2):.2f} m")

    # 几何特征分析
    logger.info("几何特征:")
    logger.info(f"  对称轴: x = {x_t:.0f} (目标x坐标)")
    logger.info(f"  最小值: t({x_t:.0f}) = {2*np.sqrt(y_t**2+z_t**2)/C*1000:.2f} ms")
    logger.info(f"  曲线类型: 双曲线 (sqrt函数)")
    logger.info(f"  渐近线: t ≈ 2|x-{x_t:.0f}|/c (远场)")

    # 实际意义
    logger.info("实际意义:")
    logger.info("  1. 最小回波时间点对应船在目标正上方 (x=x_t)")
    logger.info("  2. 曲线关于 x=x_t 对称")
    logger.info("  3. 梯度方向指向目标 (x增加方向指向x_t)")
    logger.info("  4. 可通过搜索最小回波时间快速定位目标x坐标")

    plot_q3(x_arr, t_arr, x_t, y_t, z_t, x_min, t_min)

    return {
        'target': {'x': x_t, 'y': y_t, 'z': z_t},
        'formula': 't(x) = 2*sqrt((x-100)^2 + 12500) / 1500',
        'min_echo_time_ms': float(t_min),
        'min_echo_x': float(x_min),
        'min_distance_m': float(d_min),
        'symmetry_axis': float(x_t),
    }


def plot_q3(x_arr, t_arr, x_t, y_t, z_t, x_min, t_min):
    """Q3可视化: t-x曲线 + 几何分析"""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # (a) t-x 曲线
    ax = axes[0]
    ax.plot(x_arr, t_arr, 'b-', linewidth=2)
    ax.axvline(x=x_t, color='r', linestyle='--', alpha=0.5, label=f'x = {x_t:.0f}')
    ax.plot(x_min, t_min, 'r*', markersize=15, label=f'Min ({x_min:.0f}, {t_min:.2f}ms)')
    ax.set_xlabel('Ship X Position (m)')
    ax.set_ylabel('Echo Time t (ms)')
    ax.set_title('(a) t-x Curve')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (b) 几何示意
    ax = axes[1]
    # 海底平面
    xb = np.array([-200, 400])
    ax.fill_between(xb, 0, 60, color='saddlebrown', alpha=0.3, label='Seabed')
    ax.axhline(y=0, color='blue', linewidth=2, label='Sea Surface')

    # 目标
    ax.plot(x_t, z_t, 'r*', markersize=15, label=f'Target ({x_t},{y_t},{z_t})')

    # 船位示意
    for xs in [-100, 0, 100, 200]:
        d = np.sqrt((xs - x_t)**2 + y_t**2 + z_t**2)
        t = 2 * d / C
        ax.plot(xs, 0, 'b^', markersize=10)
        ax.plot([xs, x_t], [0, z_t], 'k--', alpha=0.3)

    ax.set_xlabel('X (m)')
    ax.set_ylabel('Z (m)')
    ax.set_title('(b) Geometry (Side View)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(-150, 50)

    # (c) 梯度方向
    ax = axes[2]
    x_grid = np.linspace(-100, 300, 100)
    t_grid = 2 * np.sqrt((x_grid - x_t)**2 + y_t**2 + z_t**2) / C * 1000
    ax.plot(x_grid, t_grid, 'b-', linewidth=2, label='t(x)')

    # 梯度箭头
    for xs in [-50, 50, 150, 250]:
        dt_dx = 2 * (xs - x_t) / (C * np.sqrt((xs - x_t)**2 + y_t**2 + z_t**2))
        t_val = 2 * np.sqrt((xs - x_t)**2 + y_t**2 + z_t**2) / C * 1000
        ax.annotate('', xy=(xs - 20*np.sign(xs - x_t), t_val),
                     xytext=(xs, t_val),
                     arrowprops=dict(arrowstyle='->', color='red', lw=2))
        ax.text(xs, t_val + 0.5, f'grad', ha='center', fontsize=8, color='red')

    ax.axvline(x=x_t, color='r', linestyle='--', alpha=0.5)
    ax.set_xlabel('Ship X Position (m)')
    ax.set_ylabel('Echo Time t (ms)')
    ax.set_title('(c) Gradient Direction')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'q3_echo_time.png'), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Q3 图表已保存")


# ============================================================
# Q4: 2D 等时线分析
# ============================================================
def solve_q4():
    """
    Q4: 在问题3基础上, 船可在海面 (x, y, 0) 任意移动。

    (1) 回波时间 t 关于 (x, y) 的二元函数
    (2) 三维曲面图 + 二维等高线图 (等时线), 梯度路径规划
    """
    logger.info("=" * 60)
    logger.info("Q4: 2D 等时线分析")
    logger.info("=" * 60)

    x_t, y_t, z_t = 100.0, 50.0, -100.0

    logger.info(f"目标: ({x_t}, {y_t}, {z_t})")
    logger.info("t(x, y) = 2*sqrt((x-100)^2 + (y-50)^2 + 100^2) / 1500")

    # 网格
    x_arr = np.linspace(-100, 300, 200)
    y_arr = np.linspace(-100, 200, 200)
    X, Y = np.meshgrid(x_arr, y_arr)
    Z_dist = np.sqrt((X - x_t)**2 + (Y - y_t)**2 + z_t**2)
    T = 2 * Z_dist / C * 1000  # ms

    # 梯度
    dT_dx = 2 * (X - x_t) / (C * Z_dist) * 1000  # ms/m
    dT_dy = 2 * (Y - y_t) / (C * Z_dist) * 1000

    # 等时线值
    t_levels = np.linspace(T.min(), T.max(), 20)

    logger.info(f"最小回波时间: {T.min():.2f} ms at ({x_t:.0f}, {y_t:.0f})")
    logger.info(f"最大回波时间: {T.max():.2f} ms")

    # 梯度路径规划模拟
    # 从起点 (-50, -50) 出发, 沿负梯度方向移动
    start = np.array([-50.0, -50.0])
    path = [start.copy()]
    lr = 5.0  # 步长
    for _ in range(100):
        pos = path[-1]
        gx = 2 * (pos[0] - x_t) / (C * np.sqrt((pos[0]-x_t)**2 + (pos[1]-y_t)**2 + z_t**2))
        gy = 2 * (pos[1] - y_t) / (C * np.sqrt((pos[0]-x_t)**2 + (pos[1]-y_t)**2 + z_t**2))
        new_pos = pos - lr * np.array([gx, gy])
        path.append(new_pos)
        if np.linalg.norm(new_pos - np.array([x_t, y_t])) < 1.0:
            break
    path = np.array(path)

    logger.info(f"梯度路径: {len(path)} 步, 终点 ({path[-1,0]:.1f}, {path[-1,1]:.1f})")

    plot_q4(X, Y, T, t_levels, x_t, y_t, z_t, dT_dx, dT_dy, path)

    return {
        'target': {'x': x_t, 'y': y_t, 'z': z_t},
        'formula': 't(x,y) = 2*sqrt((x-100)^2 + (y-50)^2 + 10000) / 1500',
        'min_time_ms': float(T.min()),
        'max_time_ms': float(T.max()),
        'gradient_path_steps': len(path),
        'gradient终点': {'x': float(path[-1, 0]), 'y': float(path[-1, 1])},
    }


def plot_q4(X, Y, T, t_levels, x_t, y_t, z_t, dT_dx, dT_dy, path):
    """Q4可视化: 3D曲面 + 等时线 + 梯度路径"""
    fig = plt.figure(figsize=(20, 12))

    # (a) 3D 曲面图
    ax1 = fig.add_subplot(221, projection='3d')
    surf = ax1.plot_surface(X, Y, T, cmap='viridis', alpha=0.8)
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Y (m)')
    ax1.set_zlabel('Echo Time (ms)')
    ax1.set_title('(a) 3D Surface: t(x, y)')
    fig.colorbar(surf, ax=ax1, shrink=0.5, label='Time (ms)')

    # (b) 等时线图 (等高线)
    ax2 = fig.add_subplot(222)
    cs = ax2.contour(X, Y, T, levels=t_levels, cmap='coolwarm')
    ax2.contourf(X, Y, T, levels=t_levels, cmap='coolwarm', alpha=0.3)
    ax2.clabel(cs, inline=True, fontsize=8, fmt='%.1f')
    ax2.plot(x_t, y_t, 'r*', markersize=15, label=f'Target ({x_t},{y_t})')
    ax2.set_xlabel('X (m)')
    ax2.set_ylabel('Y (m)')
    ax2.set_title('(b) Isochrone Map (Equal-Time Lines)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_aspect('equal')

    # (c) 梯度场
    ax3 = fig.add_subplot(223)
    skip = 10
    ax3.quiver(X[::skip, ::skip], Y[::skip, ::skip],
               -dT_dx[::skip, ::skip], -dT_dy[::skip, ::skip],
               color='blue', alpha=0.5, scale=50)
    ax3.plot(x_t, y_t, 'r*', markersize=15, label='Target')
    ax3.set_xlabel('X (m)')
    ax3.set_ylabel('Y (m)')
    ax3.set_title('(c) Negative Gradient Field')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_aspect('equal')

    # (d) 梯度路径规划
    ax4 = fig.add_subplot(224)
    cs2 = ax4.contour(X, Y, T, levels=t_levels, cmap='coolwarm', alpha=0.5)
    ax4.plot(path[:, 0], path[:, 1], 'k.-', markersize=4, linewidth=1,
             label='Gradient Descent Path')
    ax4.plot(path[0, 0], path[0, 1], 'go', markersize=10, label='Start')
    ax4.plot(path[-1, 0], path[-1, 1], 'r*', markersize=15, label='End')
    ax4.plot(x_t, y_t, 'rx', markersize=15, markeredgewidth=3, label='Target')
    ax4.set_xlabel('X (m)')
    ax4.set_ylabel('Y (m)')
    ax4.set_title('(d) Gradient Path Planning')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    ax4.set_aspect('equal')

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'q4_isochrone.png'), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Q4 图表已保存")


# ============================================================
# 综合可视化
# ============================================================
def plot_comprehensive(q1, q2, q3, q4):
    """6合1综合分析图"""
    fig, axes = plt.subplots(2, 3, figsize=(20, 12))

    # (a) 海底探测几何
    ax = axes[0, 0]
    xb = np.linspace(-200, 400, 300)
    ax.fill_between(xb, 0, 60, color='saddlebrown', alpha=0.3)
    ax.axhline(y=0, color='blue', linewidth=2, label='Sea Surface')
    # 标记结核位置
    for name, pos in [('A', q1['nodule_A']), ('B', q1['nodule_B'])]:
        ax.plot(pos['x'], pos['z'] if pos['z'] != 0 else 0, 'o',
                markersize=10, label=f'Nodule {name}')
    ax.plot(0, 0, 'b^', markersize=12, label='Ship')
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Z (m)')
    ax.set_title('(a) Detection Geometry')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (b) Q1 回波时间
    ax = axes[0, 1]
    ship_x = np.array([-100, -50, 0, 50, 100])
    t_A = np.array([136.78, 134.45, 133.42, 133.78, 135.21])
    t_B = np.array([140.32, 137.89, 136.78, 136.24, 138.45])
    ax.plot(ship_x, t_A, 'bo-', label='Nodule A')
    ax.plot(ship_x, t_B, 'rs-', label='Nodule B')
    ax.set_xlabel('Ship X (m)')
    ax.set_ylabel('Echo Time (ms)')
    ax.set_title('(b) Q1: Echo Times')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (c) Q2 球形结核
    ax = axes[0, 2]
    center = q2['center']
    R = q2['radius']
    theta = np.linspace(0, 2*np.pi, 50)
    ax.plot(center['x'] + R*np.cos(theta), center['y'] + R*np.sin(theta),
            'r-', linewidth=2, label=f'Sphere (R={R:.1f}m)')
    ax.plot(center['x'], center['y'], 'r*', markersize=15)
    sonar_pos = [[0,0],[50,0],[0,50],[50,50]]
    for p in sonar_pos:
        ax.plot(p[0], p[1], 'b^', markersize=8)
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_title('(c) Q2: Sphere Location')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # (d) Q3 t-x 曲线
    ax = axes[1, 0]
    x_arr = np.linspace(-200, 400, 200)
    t_arr = 2 * np.sqrt((x_arr - 100)**2 + 12500) / C * 1000
    ax.plot(x_arr, t_arr, 'b-', linewidth=2)
    ax.axvline(x=100, color='r', linestyle='--', alpha=0.5)
    ax.set_xlabel('Ship X (m)')
    ax.set_ylabel('Echo Time (ms)')
    ax.set_title('(d) Q3: t(x) Curve')
    ax.grid(True, alpha=0.3)

    # (e) Q4 等时线
    ax = axes[1, 1]
    x_g = np.linspace(-100, 300, 100)
    y_g = np.linspace(-100, 200, 100)
    Xg, Yg = np.meshgrid(x_g, y_g)
    Tg = 2 * np.sqrt((Xg-100)**2 + (Yg-50)**2 + 10000) / C * 1000
    cs = ax.contour(Xg, Yg, Tg, levels=15, cmap='coolwarm')
    ax.contourf(Xg, Yg, Tg, levels=15, cmap='coolwarm', alpha=0.3)
    ax.plot(100, 50, 'r*', markersize=15, label='Target')
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_title('(e) Q4: Isochrone Map')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (f) 模型总结
    ax = axes[1, 2]
    ax.axis('off')
    summary = (
        "Model Summary\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Q1: Point Nodule Localization\n"
        f"  A: ({q1['nodule_A']['x']:.1f}, {q1['nodule_A']['y']:.1f})\n"
        f"  B: ({q1['nodule_B']['x']:.1f}, {q1['nodule_B']['y']:.1f})\n\n"
        f"Q2: Sphere Fitting\n"
        f"  Center: ({q2['center']['x']:.1f}, {q2['center']['y']:.1f}, {q2['center']['z']:.1f})\n"
        f"  Radius: {q2['radius']:.2f} m\n\n"
        f"Q3: t(x) Analysis\n"
        f"  Min: {q3['min_echo_time_ms']:.2f} ms at x={q3['min_echo_x']:.0f}\n\n"
        f"Q4: Isochrone Analysis\n"
        f"  Gradient path: {q4['gradient_path_steps']} steps"
    )
    ax.text(0.1, 0.9, summary, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'comprehensive_analysis.png'), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("综合分析图已保存")


# ============================================================
# 主程序
# ============================================================
def main():
    logger.info("=" * 60)
    logger.info("2026 CQUPU Math Modeling A: Underwater Target Detection")
    logger.info("=" * 60)
    logger.info(f"声速: c = {C} m/s")

    q1 = solve_q1()
    q2 = solve_q2()
    q3 = solve_q3()
    q4 = solve_q4()

    plot_comprehensive(q1, q2, q3, q4)

    # 保存结果
    def convert(obj):
        if isinstance(obj, (np.bool_, np.integer)):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    all_results = {'Q1': q1, 'Q2': q2, 'Q3': q3, 'Q4': q4}
    output_path = os.path.join(SCRIPT_DIR, 'results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=convert)

    logger.info(f"结果已保存: {output_path}")
    logger.info("=" * 60)
    logger.info("所有问题求解完成!")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
