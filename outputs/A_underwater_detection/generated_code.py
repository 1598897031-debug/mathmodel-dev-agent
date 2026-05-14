"""
多静态声纳-海底地形协同优化 — 完整求解代码
2025高教社杯全国大学生数学建模竞赛A题

三层介质声传播模型 + Snell折射 + 射线追踪
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import json
import os
import sys
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple

# ============================================================
# 日志
# ============================================================
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(LOG_DIR, "figures"), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "execution.log"), mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ============================================================
# 参数
# ============================================================
@dataclass
class Env:
    c0: float = 1500.0       # 水层声速 m/s
    c1: float = 4200.0       # 淤泥层声速 m/s
    c2: float = 7000.0       # 硬底层声速 m/s
    h1: float = 100.0        # 淤泥层厚度 m
    h2: float = 100.0        # 硬底层计算厚度 m
    flat_depth: float = 500.0
    alpha_deg: float = 0.8
    SL: float = 120.0        # 声源级 dB
    S_depth: float = 150.0   # 声源深度 m
    Nx: int = 5              # 水平阵元数
    Nz: int = 5              # 垂直阵元数
    dx: float = 40.0         # 水平间距 m
    dz: float = 40.0         # 垂直间距 m
    threshold: float = 6.0   # 检测阈值 dB
    max_time: float = 3.0    # 最长回波时间 s
    max_range: float = 2000.0
    reef_x: float = 1000.0   # 暗礁中心水平距离
    reef_half: float = 100.0 # 底边半宽
    reef_h: float = 100.0    # 高度

    def __post_init__(self):
        self.alpha_rad = np.radians(self.alpha_deg)
        self.crit_angle = np.arcsin(self.c0 / self.c1)  # ~20.92°


# ============================================================
# 底部深度
# ============================================================
def bottom_flat(x: float) -> float:
    return 500.0

def bottom_sloped(x: float, env: Env) -> float:
    return env.flat_depth - x * np.tan(env.alpha_rad)


# ============================================================
# Snell 折射
# ============================================================
def snell_refract(theta: float, c_from: float, c_to: float) -> Optional[float]:
    """返回折射角，None=全反射"""
    s = (c_to / c_from) * np.sin(theta)
    if abs(s) >= 1.0:
        return None
    return np.arcsin(s)


# ============================================================
# 射线追踪：声源 → 海底 → 返回
# ============================================================
def trace_echo(sx: float, sy: float, rx: float, ry: float, env: Env,
               use_slope: bool = False) -> dict:
    """
    计算声源(sx,sy)发出的声波，经海底反射后到达接收阵元(rx,ry)的双程路径。

    模型:
    - 射线从声源以角度θ₀出射
    - 经水层到达海底
    - 在海底发生Snell折射进入淤泥层、硬底层
    - 在硬底层反射
    - 返回经过相同路径到达接收阵元
    - 双程扩展损失 = 2 × 20log₁₀(单程路径长)

    Returns: dict with rl, tl, time, detectable, theta0, valid
    """
    result = {'rl': -999.0, 'tl': 999.0, 'time': 999.0,
              'detectable': False, 'valid': False, 'theta0': 0.0}

    if use_slope:
        y_bot = bottom_sloped(sx, env)
    else:
        y_bot = bottom_flat(sx)

    # 射线从声源到海底某点
    # 假设射线在海底的入射点水平偏移为 Δx
    # 对于平底，我们遍历可能的入射角
    # 简化：直接计算声源到海底正下方点的路径
    dy = y_bot - sy
    if dy <= 0:
        return result

    # 声源正下方的海底点
    R0 = dy  # 水层路径（垂直）
    theta0 = 0.0  # 垂直出射

    # Snell 折射
    theta1 = snell_refract(theta0, env.c0, env.c1)
    if theta1 is None:
        return result
    theta2 = snell_refract(theta1, env.c1, env.c2)
    if theta2 is None:
        theta2 = 0.0

    # 各层路径
    R1 = env.h1 / np.cos(theta1)
    R2 = env.h2 / np.cos(theta2)

    # 单程总路径
    R_one_way = R0 + R1 + R2
    t_one_way = R0 / env.c0 + R1 / env.c1 + R2 / env.c2

    # 双程
    R_total = 2.0 * R_one_way
    t_total = 2.0 * t_one_way

    # 扩展损失 (TL = 2×20log₁₀(R) for two-way spherical spreading)
    TL = 2.0 * 20.0 * np.log10(R_total / 2.0 + 1e-10)  # 双程，R/2是单程

    RL = env.SL - TL

    # 水平偏移（声源正下方，水平偏移=0）
    # 对于有坡度的情况，接收阵元需要在正确的位置
    # 这里简化为：声源正下方的回波

    result.update({
        'rl': float(RL),
        'tl': float(TL),
        'time': float(t_total),
        'detectable': bool(RL >= env.threshold and t_total <= env.max_time),
        'valid': True,
        'theta0': float(theta0),
        'R_total': float(R_total),
    })
    return result


def trace_echo_at_angle(sx: float, sy: float, theta0: float,
                         env: Env) -> dict:
    """
    以出射角θ₀追踪射线到海底，计算双程路径。
    用于分析不同角度的检测能力。
    """
    result = {'rl': -999.0, 'tl': 999.0, 'time': 999.0,
              'detectable': False, 'valid': False,
              'x_bottom': 0.0, 'y_bottom': 0.0, 'R_total': 0.0}

    if theta0 < 0 or theta0 >= np.pi / 2:
        return result

    y_bot = bottom_flat(0)  # 平底

    # 水层：从(sx, sy)以角度θ₀出射到底部y_bot
    dy = y_bot - sy
    if dy <= 0:
        return result

    R0 = dy / np.cos(theta0)
    x_hit = sx + dy * np.tan(theta0)

    # Snell折射
    theta1 = snell_refract(theta0, env.c0, env.c1)
    if theta1 is None:
        # 全反射，声波不进入底层
        # 反射路径：水层往返
        R_total = 2.0 * R0
        t_total = 2.0 * R0 / env.c0
        TL = 2.0 * 20.0 * np.log10(R_total / 2.0 + 1e-10)
        RL = env.SL - TL
        result.update({
            'rl': float(RL), 'tl': float(TL), 'time': float(t_total),
            'detectable': bool(RL >= env.threshold and t_total <= env.max_time),
            'valid': True, 'x_bottom': float(x_hit), 'y_bottom': float(y_bot),
            'R_total': float(R_total), 'total_reflection': True,
        })
        return result

    theta2 = snell_refract(theta1, env.c1, env.c2)
    if theta2 is None:
        theta2 = 0.0

    R1 = env.h1 / np.cos(theta1)
    R2 = env.h2 / np.cos(theta2)

    R_one_way = R0 + R1 + R2
    t_one_way = R0 / env.c0 + R1 / env.c1 + R2 / env.c2

    R_total = 2.0 * R_one_way
    t_total = 2.0 * t_one_way
    TL = 2.0 * 20.0 * np.log10(R_total / 2.0 + 1e-10)
    RL = env.SL - TL

    result.update({
        'rl': float(RL), 'tl': float(TL), 'time': float(t_total),
        'detectable': bool(RL >= env.threshold and t_total <= env.max_time),
        'valid': True, 'x_bottom': float(x_hit), 'y_bottom': float(y_bot),
        'R_total': float(R_total),
    })
    return result


# ============================================================
# 暗礁几何
# ============================================================
def reef_vertices(env: Env) -> np.ndarray:
    y_bot = bottom_flat(env.reef_x)
    y_top = y_bot - env.reef_h
    return np.array([
        [env.reef_x - env.reef_half, y_bot],
        [env.reef_x + env.reef_half, y_bot],
        [env.reef_x, y_top],
    ])


def seg_intersect(a1, a2, b1, b2) -> bool:
    d1 = np.array(a2) - np.array(a1)
    d2 = np.array(b2) - np.array(b1)
    cross = d1[0]*d2[1] - d1[1]*d2[0]
    if abs(cross) < 1e-12:
        return False
    t = ((b1[0]-a1[0])*d2[1] - (b1[1]-a1[1])*d2[0]) / cross
    u = ((b1[0]-a1[0])*d1[1] - (b1[1]-a1[1])*d1[0]) / cross
    return 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0


def point_in_tri(p, tri) -> bool:
    v0, v1, v2 = tri
    d1 = (p[0]-v1[0])*(v0[1]-v1[1]) - (v0[0]-v1[0])*(p[1]-v1[1])
    d2 = (p[0]-v2[0])*(v1[1]-v2[1]) - (v1[0]-v2[0])*(p[1]-v2[1])
    d3 = (p[0]-v0[0])*(v2[1]-v0[1]) - (v2[0]-v0[0])*(p[1]-v0[1])
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def line_hits_tri(p1, p2, tri) -> bool:
    """检查线段是否与三角形相交"""
    for i in range(3):
        if seg_intersect(p1, p2, tri[i], tri[(i+1)%3]):
            return True
    return point_in_tri(p1, tri) or point_in_tri(p2, tri)


def ray_blocked_by_reef(sx, sy, rx, ry, env: Env) -> bool:
    """
    检查声源→海底→接收阵元的射线是否被暗礁遮挡。
    检查三段路径：声源→海底入射点，海底入射点→接收阵元。
    """
    tri = reef_vertices(env)

    # 声源正下方的海底入射点
    y_bot = bottom_flat(sx)
    bounce_pt = np.array([sx, y_bot])
    src_pt = np.array([sx, sy])
    recv_pt = np.array([rx, ry])

    # 检查声源→海底路径
    if line_hits_tri(src_pt, bounce_pt, tri):
        return True
    # 检查海底→接收阵元路径
    if line_hits_tri(bounce_pt, recv_pt, tri):
        return True

    return False


def ray_blocked_by_reef_angle(sx, sy, x_bottom, env: Env) -> bool:
    """检查从声源到海底入射点的射线是否被暗礁遮挡"""
    tri = reef_vertices(env)
    src_pt = np.array([sx, sy])
    bot_pt = np.array([x_bottom, bottom_flat(sx)])
    return line_hits_tri(src_pt, bot_pt, tri)


# ============================================================
# Q1: 海底平坦时的检测与阴影区
# ============================================================
def solve_q1(env: Env) -> dict:
    logger.info("=" * 60)
    logger.info("Q1: 海底平坦时的检测与阴影区分析")
    logger.info("=" * 60)

    # 声源固定在 (0, 150)
    sx, sy = 0.0, env.S_depth

    # 接收阵元
    receivers = []
    for ix in range(env.Nx):
        for iz in range(env.Nz):
            rx = ix * env.dx
            ry = env.S_depth + iz * env.dz
            receivers.append({'x': rx, 'y': ry, 'ix': ix, 'iz': iz})

    # 对于每个接收阵元，分析其能检测的声源位置范围
    # 声源水平移动，深度固定150m
    # 但本题声源固定在(0,150)，我们要分析的是：
    # 在水平距离0~2000m范围内，哪些位置的回波能被接收阵元检测到

    # 方法：对每个水平距离x_S，假设声源在(x_S, 150)，
    # 计算其正下方海底回波能否被各接收阵元检测到
    # 这实际上是分析"每个接收阵元的检测范围"

    x_range = np.linspace(10, env.max_range, 400)
    n_recv = len(receivers)
    n_x = len(x_range)

    # detection_map[i_recv, j_x] = True 表示接收阵元i可以检测到位置j的声源回波
    det_map = np.zeros((n_recv, n_x), dtype=bool)

    for j, xs in enumerate(x_range):
        # 声源在 (xs, 150)
        # 射线垂直向下到底部 y=500，反射后垂直向上
        # 双程路径：2 × (500-150) = 700m，穿过水层+淤泥层+硬底层
        # 垂直入射时 θ₀=0, θ₁=0, θ₂=0

        R0 = 500.0 - env.S_depth  # 350m 水层
        R1 = env.h1  # 100m 淤泥
        R2 = env.h2  # 100m 硬底

        R_one_way = R0 + R1 + R2  # 550m
        R_total = 2.0 * R_one_way  # 1100m 双程
        t_total = 2.0 * (R0/env.c0 + R1/env.c1 + R2/env.c2)

        TL = 2.0 * 20.0 * np.log10(R_total / 2.0 + 1e-10)
        RL = env.SL - TL

        detectable = (RL >= env.threshold) and (t_total <= env.max_time)

        # 但接收阵元不一定在声源正上方
        # 需要考虑接收阵元的位置是否在回波可达范围内
        for i, recv in enumerate(receivers):
            # 接收阵元与声源的水平距离
            drx = recv['x'] - xs
            dry = recv['y'] - env.S_depth

            # 如果接收阵元在声源正上方附近，可以接收到回波
            # 简化：接收阵元需要在声源的水平距离以内
            # 且直达路径的RL满足条件

            # 直达路径RL
            R_direct = np.sqrt(drx**2 + dry**2)
            TL_direct = 20.0 * np.log10(R_direct + 1e-10)
            RL_direct = env.SL - TL_direct
            t_direct = 2.0 * R_direct / env.c0

            # 取两种路径中较好的
            if detectable and abs(drx) < 200:  # 回波可达
                det_map[i, j] = True
            elif RL_direct >= env.threshold and t_direct <= env.max_time:
                det_map[i, j] = True

    # 阴影区 = 所有接收阵元都无法检测的区域
    shadow = np.all(~det_map, axis=0)
    shadow_pct = float(np.sum(shadow)) / n_x * 100

    logger.info(f"接收阵元数: {n_recv}")
    logger.info(f"阴影区比例: {shadow_pct:.1f}%")
    logger.info(f"可检测区域比例: {100-shadow_pct:.1f}%")

    # 阴影区范围
    shadow_ranges = []
    in_s = False
    s_start = 0
    for k in range(n_x):
        if shadow[k] and not in_s:
            s_start = x_range[k]
            in_s = True
        elif not shadow[k] and in_s:
            shadow_ranges.append({'start': float(s_start), 'end': float(x_range[k-1])})
            in_s = False
    if in_s:
        shadow_ranges.append({'start': float(s_start), 'end': float(x_range[-1])})

    logger.info(f"阴影区范围: {shadow_ranges}")

    # 绘图
    plot_q1(env, receivers, x_range, det_map, shadow)

    return {
        'shadow_ratio': shadow_pct,
        'shadow_ranges': shadow_ranges,
        'n_receivers': n_recv,
        'n_samples': n_x,
    }


def plot_q1(env, receivers, x_range, det_map, shadow):
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # 接收阵元布局
    ax = axes[0, 0]
    for recv in receivers:
        ax.plot(recv['x'], recv['y'], 'bs', markersize=6)
    ax.plot(0, env.S_depth, 'r^', markersize=12, label='Source S(0,150)')
    ax.set_xlabel('Horizontal Distance (m)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('(a) Receiver Array Layout')
    ax.invert_yaxis()
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 检测热图
    ax = axes[0, 1]
    im = ax.imshow(det_map, aspect='auto', cmap='RdYlGn',
                   extent=[x_range[0], x_range[-1], len(receivers)-1, 0])
    ax.set_xlabel('Horizontal Distance of Source (m)')
    ax.set_ylabel('Receiver Index')
    ax.set_title('(b) Detection Map (Green=Detectable)')
    plt.colorbar(im, ax=ax, shrink=0.8)

    # 阴影区
    ax = axes[1, 0]
    s_int = shadow.astype(float)
    ax.fill_between(x_range, 0, s_int, color='red', alpha=0.5, label='Shadow Zone')
    ax.fill_between(x_range, 0, 1-s_int, color='green', alpha=0.3, label='Detectable')
    ax.set_xlabel('Horizontal Distance (m)')
    ax.set_ylabel('Status')
    ax.set_title('(c) Shadow Zone Distribution')
    ax.legend()
    ax.set_ylim(-0.1, 1.1)
    ax.grid(True, alpha=0.3)

    # 海底剖面
    ax = axes[1, 1]
    xb = np.linspace(0, 2000, 300)
    yb = np.array([bottom_flat(x) for x in xb])
    ax.fill_between(xb, 0, yb, color='saddlebrown', alpha=0.4, label='Seabed')
    ax.axhline(y=0, color='blue', linewidth=2, label='Sea Surface')
    ax.plot(0, env.S_depth, 'r^', markersize=12, label='Source S')
    # 画几条射线
    for theta in [0, 10, 20, 30, 45, 60]:
        rad = np.radians(theta)
        x_end = 350 * np.tan(rad)
        ax.plot([0, x_end], [env.S_depth, 500], 'k--', alpha=0.3, linewidth=0.8)
    ax.set_xlabel('Horizontal Distance (m)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('(d) Seabed Profile & Ray Paths')
    ax.invert_yaxis()
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(LOG_DIR, 'figures', 'q1_shadow_zone.png'), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Q1 图表已保存")


# ============================================================
# Q2: 三角暗礁遮挡分析
# ============================================================
def solve_q2(env: Env) -> dict:
    logger.info("=" * 60)
    logger.info("Q2: 三角暗礁遮挡分析")
    logger.info("=" * 60)

    sx, sy = 0.0, env.S_depth

    receivers = []
    for ix in range(env.Nx):
        for iz in range(env.Nz):
            rx = ix * env.dx
            ry = env.S_depth + iz * env.dz
            receivers.append({'x': rx, 'y': ry, 'ix': ix, 'iz': iz})

    tri = reef_vertices(env)
    logger.info(f"暗礁顶点: {tri.tolist()}")

    results = []
    for recv in receivers:
        blocked = ray_blocked_by_reef(sx, sy, recv['x'], recv['y'], env)

        # 计算直达路径RL
        drx = recv['x'] - sx
        dry = recv['y'] - sy
        R = np.sqrt(drx**2 + dry**2)
        TL = 20.0 * np.log10(R + 1e-10)
        RL = env.SL - TL
        t = 2.0 * R / env.c0
        detectable = (RL >= env.threshold) and (t <= env.max_time) and (not blocked)

        results.append({
            'ix': recv['ix'], 'iz': recv['iz'],
            'x': recv['x'], 'y': recv['y'],
            'blocked': bool(blocked),
            'RL': float(RL), 'time': float(t),
            'detectable': bool(detectable),
        })

    n_det = sum(1 for r in results if r['detectable'])
    n_blk = sum(1 for r in results if r['blocked'])

    logger.info(f"能检测到暗礁: {n_det}/{len(receivers)}")
    logger.info(f"被暗礁遮挡: {n_blk}/{len(receivers)}")

    plot_q2(env, sx, sy, results, tri)

    return {
        'results': results,
        'n_detectable': n_det,
        'n_blocked': n_blk,
        'reef_vertices': tri.tolist(),
    }


def plot_q2(env, sx, sy, results, tri):
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    ax = axes[0]
    xb = np.linspace(0, 2000, 300)
    yb = np.array([bottom_flat(x) for x in xb])
    ax.fill_between(xb, 0, yb, color='saddlebrown', alpha=0.3)

    reef_patch = patches.Polygon(tri, closed=True, fc='darkred', ec='black', alpha=0.7, label='Reef')
    ax.add_patch(reef_patch)

    ax.plot(sx, sy, 'r^', markersize=15, label='Source S', zorder=5)

    for r in results:
        if r['detectable']:
            ax.plot(r['x'], r['y'], 'go', markersize=8, zorder=4)
        elif r['blocked']:
            ax.plot(r['x'], r['y'], 'rx', markersize=8, zorder=4)
        else:
            ax.plot(r['x'], r['y'], 'y^', markersize=6, zorder=4)

    # 画被遮挡的射线
    for r in results:
        if r['blocked']:
            ax.plot([sx, r['x']], [sy, r['y']], 'r--', alpha=0.3, linewidth=0.8)

    ax.set_xlabel('Horizontal Distance (m)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('Q2: Reef Obstruction Diagram')
    ax.invert_yaxis()
    ax.set_xlim(-50, 1200)
    ax.set_ylim(600, 0)
    ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)

    # 统计
    ax = axes[1]
    cats = ['Detectable\n(Green)', 'Blocked by Reef\n(Red X)', 'Below Threshold\n(Yellow)']
    counts = [
        sum(1 for r in results if r['detectable']),
        sum(1 for r in results if r['blocked']),
        sum(1 for r in results if not r['detectable'] and not r['blocked']),
    ]
    colors = ['green', 'red', 'gray']
    bars = ax.bar(cats, counts, color=colors, alpha=0.7)
    ax.set_ylabel('Number of Pairs')
    ax.set_title('Q2: Detection Statistics')
    for b, c in zip(bars, counts):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.2, str(c),
                ha='center', fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(os.path.join(LOG_DIR, 'figures', 'q2_reef_detection.png'), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Q2 图表已保存")


# ============================================================
# Q3: 声源位置优化
# ============================================================
def solve_q3(env: Env) -> dict:
    logger.info("=" * 60)
    logger.info("Q3: 声源位置优化 (200m×200m区域)")
    logger.info("=" * 60)

    # 声源在 [-200,200]×[-200,200] 区域内搜索
    # 深度固定150m，x和y是水平偏移
    gx = np.linspace(-200, 200, 41)
    gy = np.linspace(-200, 200, 41)

    receivers = []
    for ix in range(env.Nx):
        for iz in range(env.Nz):
            rx = ix * env.dx
            ry = env.S_depth + iz * env.dz
            receivers.append({'x': rx, 'y': ry})

    best_count = 0
    best_pos = (0.0, 0.0)
    grid = np.zeros((len(gx), len(gy)))

    logger.info(f"搜索网格: {len(gx)}×{len(gy)} = {len(gx)*len(gy)} 个候选点")

    for i, sx in enumerate(gx):
        for j, sy_off in enumerate(gy):
            sy = env.S_depth + sy_off  # 深度=150+偏移
            count = 0
            for recv in receivers:
                blocked = ray_blocked_by_reef(sx, sy, recv['x'], recv['y'], env)
                drx = recv['x'] - sx
                dry = recv['y'] - sy
                R = np.sqrt(drx**2 + dry**2)
                TL = 20.0 * np.log10(R + 1e-10)
                RL = env.SL - TL
                t = 2.0 * R / env.c0
                ok = (RL >= env.threshold) and (t <= env.max_time) and (not blocked)
                if ok:
                    count += 1
            grid[i, j] = count
            if count > best_count:
                best_count = count
                best_pos = (float(sx), float(sy_off))

    logger.info(f"最优声源位置: ({best_pos[0]:.1f}, {best_pos[1]:.1f})")
    logger.info(f"最大可检测组合数: {best_count}/25")

    plot_q3(env, gx, gy, grid, best_pos, best_count)

    return {
        'best_position': best_pos,
        'best_count': int(best_count),
        'grid_x': [float(x) for x in gx],
        'grid_y': [float(y) for y in gy],
        'results_grid': grid.tolist(),
    }


def plot_q3(env, gx, gy, grid, best_pos, best_count):
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    ax = axes[0]
    im = ax.imshow(grid.T, aspect='auto', cmap='YlOrRd',
                   extent=[gx[0], gx[-1], gy[0], gy[-1]], origin='lower')
    ax.plot(best_pos[0], best_pos[1], 'k*', markersize=15,
            label=f'Best ({best_pos[0]:.0f},{best_pos[1]:.0f})={best_count}')
    ax.set_xlabel('Source X Offset (m)')
    ax.set_ylabel('Source Y Offset (m)')
    ax.set_title('Q3: Detection Coverage Heatmap')
    plt.colorbar(im, ax=ax, label='Detectable Pairs')
    ax.legend(fontsize=9)

    ax = axes[1]
    sx, sy_off = best_pos
    sy = env.S_depth + sy_off
    for ix in range(env.Nx):
        for iz in range(env.Nz):
            rx = ix * env.dx
            ry = env.S_depth + iz * env.dz
            blocked = ray_blocked_by_reef(sx, sy, rx, ry, env)
            R = np.sqrt((rx-sx)**2 + (ry-sy)**2)
            TL = 20.0 * np.log10(R + 1e-10)
            RL = env.SL - TL
            t = 2.0 * R / env.c0
            ok = (RL >= env.threshold) and (t <= env.max_time) and (not blocked)
            if ok:
                ax.plot(rx, ry, 'go', markersize=10)
            elif blocked:
                ax.plot(rx, ry, 'rx', markersize=10)
            else:
                ax.plot(rx, ry, 'y^', markersize=8)

    ax.plot(sx, sy, 'r^', markersize=15, label=f'Source({sx:.0f},{sy:.0f})')
    ax.set_xlabel('Receiver X (m)')
    ax.set_ylabel('Depth (m)')
    ax.set_title(f'Q3: Best Source — {int(best_count)}/25 Detectable')
    ax.invert_yaxis()
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(LOG_DIR, 'figures', 'q3_optimization.png'), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Q3 图表已保存")


# ============================================================
# 综合可视化
# ============================================================
def plot_comprehensive(env: Env):
    """生成综合分析图"""
    fig, axes = plt.subplots(2, 3, figsize=(20, 12))

    # 1. 海底剖面与三层结构
    ax = axes[0, 0]
    xb = np.linspace(0, 2000, 300)
    yb_flat = np.array([bottom_flat(x) for x in xb])
    yb_slope = np.array([bottom_sloped(x, env) for x in xb])
    ax.fill_between(xb, 0, yb_flat, color='saddlebrown', alpha=0.3, label='Flat Bottom')
    ax.plot(xb, yb_slope, 'r-', linewidth=2, label='Sloped Bottom')
    ax.axhline(y=0, color='blue', linewidth=2)
    ax.axhline(y=env.flat_depth, color='brown', linestyle='--', alpha=0.5)
    ax.axhline(y=env.flat_depth+env.h1, color='gray', linestyle='--', alpha=0.5)
    ax.text(1800, 250, 'Water', fontsize=10, color='blue')
    ax.text(1800, 550, 'Sediment', fontsize=10, color='brown')
    ax.text(1800, 650, 'Basement', fontsize=10, color='gray')
    ax.set_xlabel('Horizontal Distance (m)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('(a) Three-Layer Ocean Model')
    ax.invert_yaxis()
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 2. Snell折射示意
    ax = axes[0, 1]
    angles = np.linspace(0, 80, 9)
    for a0 in angles:
        rad = np.radians(a0)
        # 水层
        x1 = 350 * np.tan(rad)
        ax.plot([0, x1], [150, 500], 'b-', alpha=0.5)
        # 折射到淤泥层
        th1 = snell_refract(rad, env.c0, env.c1)
        if th1 is not None:
            x2 = x1 + env.h1 * np.tan(th1)
            ax.plot([x1, x2], [500, 600], 'g-', alpha=0.5)
            # 折射到硬底层
            th2 = snell_refract(th1, env.c1, env.c2)
            if th2 is not None:
                x3 = x2 + env.h2 * np.tan(th2)
                ax.plot([x2, x3], [600, 700], 'r-', alpha=0.5)
        ax.text(x1+5, 490, f'{a0}°', fontsize=7)

    ax.axhline(y=0, color='blue', linewidth=2)
    ax.axhline(y=500, color='brown', linewidth=1.5, linestyle='--')
    ax.axhline(y=600, color='gray', linewidth=1.5, linestyle='--')
    ax.plot(0, 150, 'r^', markersize=12, label='Source')
    ax.set_xlabel('Horizontal Distance (m)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('(b) Snell Refraction — Ray Tracing')
    ax.invert_yaxis()
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 3. 折射角 vs 入射角
    ax = axes[0, 2]
    th0_arr = np.linspace(0, 89, 200)
    th1_arr = []
    th2_arr = []
    for t0 in th0_arr:
        t1 = snell_refract(np.radians(t0), env.c0, env.c1)
        th1_arr.append(np.degrees(t1) if t1 is not None else np.nan)
        if t1 is not None:
            t2 = snell_refract(t1, env.c1, env.c2)
            th2_arr.append(np.degrees(t2) if t2 is not None else np.nan)
        else:
            th2_arr.append(np.nan)

    ax.plot(th0_arr, th1_arr, 'g-', linewidth=2, label='θ₁ (Sediment)')
    ax.plot(th0_arr, th2_arr, 'r-', linewidth=2, label='θ₂ (Basement)')
    ax.axvline(x=np.degrees(env.crit_angle), color='k', linestyle='--',
               label=f'Critical Angle ({np.degrees(env.crit_angle):.1f}°)')
    ax.set_xlabel('Incident Angle θ₀ (degrees)')
    ax.set_ylabel('Refracted Angle (degrees)')
    ax.set_title('(c) Snell\'s Law Refraction Angles')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 4. RL vs 距离
    ax = axes[1, 0]
    r_arr = np.linspace(10, 2000, 200)
    rl_direct = env.SL - 20*np.log10(r_arr)
    ax.plot(r_arr, rl_direct, 'b-', linewidth=2, label='Direct Path TL')
    ax.axhline(y=env.threshold, color='r', linestyle='--', label=f'Threshold ({env.threshold} dB)')
    ax.fill_between(r_arr, rl_direct, env.threshold,
                    where=rl_direct >= env.threshold, alpha=0.2, color='green')
    ax.fill_between(r_arr, rl_direct, env.threshold,
                    where=rl_direct < env.threshold, alpha=0.2, color='red')
    ax.set_xlabel('Range (m)')
    ax.set_ylabel('Received Level (dB)')
    ax.set_title('(d) Detection Range Analysis')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 5. 暗礁几何
    ax = axes[1, 1]
    tri = reef_vertices(env)
    reef_patch = patches.Polygon(tri, closed=True, fc='darkred', ec='black', alpha=0.7)
    ax.add_patch(reef_patch)
    xb2 = np.linspace(800, 1200, 100)
    yb2 = np.array([bottom_flat(x) for x in xb2])
    ax.fill_between(xb2, 0, yb2, color='saddlebrown', alpha=0.3)
    ax.axhline(y=0, color='blue', linewidth=2)

    # 画几条被遮挡的射线
    for rx in [0, 40, 80, 120, 160]:
        blocked = ray_blocked_by_reef(0, 150, rx, 150, env)
        color = 'red' if blocked else 'green'
        ax.plot([0, rx], [150, 150], color=color, alpha=0.5, linewidth=1.5)

    ax.plot(0, 150, 'r^', markersize=12, label='Source')
    ax.set_xlabel('Horizontal Distance (m)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('(e) Reef Geometry & Ray Blocking')
    ax.invert_yaxis()
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 6. 回波时间分析
    ax = axes[1, 2]
    r_arr2 = np.linspace(10, 2000, 200)
    t_direct = 2 * r_arr2 / env.c0
    ax.plot(r_arr2, t_direct * 1000, 'b-', linewidth=2, label='Direct Path')
    ax.axhline(y=env.max_time * 1000, color='r', linestyle='--',
               label=f'Time Limit ({env.max_time*1000:.0f} ms)')
    ax.set_xlabel('Range (m)')
    ax.set_ylabel('Echo Time (ms)')
    ax.set_title('(f) Echo Time vs Range')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(LOG_DIR, 'figures', 'comprehensive_analysis.png'), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("综合分析图已保存")


# ============================================================
# 主程序
# ============================================================
def main():
    logger.info("=" * 60)
    logger.info("多静态声纳-海底地形协同优化 — 求解开始")
    logger.info("=" * 60)

    env = Env()

    logger.info(f"声源: SL={env.SL}dB, 深度={env.S_depth}m")
    logger.info(f"接收阵: {env.Nx}×{env.Nz}, 间距={env.dx}m")
    logger.info(f"水层: c₀={env.c0}m/s")
    logger.info(f"淤泥层: c₁={env.c1}m/s, 厚度={env.h1}m")
    logger.info(f"硬底层: c₂={env.c2}m/s")
    logger.info(f"海底坡度: α={env.alpha_deg}°")
    logger.info(f"检测阈值: {env.threshold}dB, 最长回波: {env.max_time}s")
    logger.info(f"临界全反射角: {np.degrees(env.crit_angle):.2f}°")

    # 综合分析图
    plot_comprehensive(env)

    # Q1
    q1 = solve_q1(env)

    # Q2
    q2 = solve_q2(env)

    # Q3
    q3 = solve_q3(env)

    # 保存结果 (确保numpy类型转换)
    def convert(obj):
        if isinstance(obj, (np.bool_, np.integer)):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    all_results = {'Q1': q1, 'Q2': q2, 'Q3': q3}

    output_path = os.path.join(LOG_DIR, 'results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=convert)

    logger.info(f"结果已保存: {output_path}")
    logger.info("=" * 60)
    logger.info("求解完成!")
    logger.info("=" * 60)

    print("\n" + "=" * 60)
    print("求解摘要")
    print("=" * 60)
    print(f"Q1 阴影区比例: {q1['shadow_ratio']:.1f}%")
    print(f"Q1 阴影区范围: {q1['shadow_ranges']}")
    print(f"Q2 能检测暗礁: {q2['n_detectable']}/25")
    print(f"Q2 被暗礁遮挡: {q2['n_blocked']}/25")
    print(f"Q3 最优声源: ({q3['best_position'][0]:.1f}, {q3['best_position'][1]:.1f})")
    print(f"Q3 最大组合数: {q3['best_count']}/25")
    print("=" * 60)


if __name__ == "__main__":
    main()
