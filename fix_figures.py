"""
Final Presentation Polish — Figure Regeneration + Title Fix
Regenerates all figures with Chinese labels at 2x resolution.
"""
import sys, os
for _site in ["D:/Lib/site-packages", "D:\\Lib\\site-packages"]:
    if os.path.isdir(_site) and _site not in sys.path:
        sys.path.insert(0, _site)

import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams
from pathlib import Path

# Chinese font config
rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False
rcParams['figure.dpi'] = 300
rcParams['savefig.dpi'] = 300

C = 1500.0  # m/s
FIG_DIR = Path("outputs/A_underwater_detection/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Load data
with open("outputs/A_underwater_detection/parsed_problem.json", encoding="utf-8") as f:
    pd = json.load(f)
with open("outputs/A_underwater_detection/results.json", encoding="utf-8") as f:
    res = json.load(f)

ship_x = pd["questions"]["Q1"]["ship_positions_x"]
t_A = pd["questions"]["Q1"]["nodule_A_echo_times_ms"]
t_B = pd["questions"]["Q1"]["nodule_B_echo_times_ms"]
a = res["Q1"]["nodule_A"]
b = res["Q1"]["nodule_B"]
q2c = res["Q2"]["center"]
q2r = res["Q2"]["radius"]
q3t_raw = res["Q3"]["target"]
q3t = [q3t_raw["x"], q3t_raw["y"], q3t_raw["z"]]


def plot_q1():
    """图1：问题一点状结核定位分析"""
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # (a) 回波时间
    ax = axes[0]
    ax.plot(ship_x, t_A, 'o-', label='结核A', markersize=6)
    ax.plot(ship_x, t_B, 's-', label='结核B', markersize=6)
    ax.set_xlabel('船位X坐标 / m')
    ax.set_ylabel('回波时间 / ms')
    ax.set_title('(a) 回波时间与船位关系')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (b) 距离
    ax = axes[1]
    d_A = np.array(t_A) * C / 2000
    d_B = np.array(t_B) * C / 2000
    ax.plot(ship_x, d_A, 'o-', label='结核A', markersize=6)
    ax.plot(ship_x, d_B, 's-', label='结核B', markersize=6)
    ax.set_xlabel('船位X坐标 / m')
    ax.set_ylabel('距离 / m')
    ax.set_title('(b) 距离与船位关系')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (c) 定位结果俯视图
    ax = axes[2]
    ax.plot(a["x"], a["y"], 'r*', markersize=15, label=f'结核A ({a["x"]:.1f}, {a["y"]:.1f})')
    ax.plot(b["x"], b["y"], 'b^', markersize=12, label=f'结核B ({b["x"]:.1f}, {b["y"]:.1f})')
    ax.plot(ship_x, [0]*len(ship_x), 'ks', markersize=8, label='船位')
    for i, sx in enumerate(ship_x):
        ax.annotate(f'S{i+1}', (sx, -3), fontsize=8, ha='center')
    ax.set_xlabel('X / m')
    ax.set_ylabel('Y / m')
    ax.set_title('(c) 定位结果俯视图')
    ax.legend(fontsize=8)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(str(FIG_DIR / "q1_localization.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  图1: q1_localization.png — OK")


def plot_q2():
    """图2：问题二球形结核定位分析"""
    sonar_pos = np.array(pd["questions"]["Q2"]["sonar_positions"])
    echo_delays = pd["questions"]["Q2"]["echo_delays_ms"]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # (a) 球体三维视图
    ax = fig.add_subplot(131, projection='3d')
    u = np.linspace(0, 2*np.pi, 30)
    v = np.linspace(0, np.pi, 20)
    xs = q2c["x"] + q2r * np.outer(np.cos(u), np.sin(v))
    ys = q2c["y"] + q2r * np.outer(np.sin(u), np.sin(v))
    zs = q2c["z"] + q2r * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(xs, ys, zs, alpha=0.3, color='steelblue')
    ax.scatter(*q2c.values(), color='red', s=50, label='球心')
    for i, sp in enumerate(sonar_pos):
        ax.scatter(*sp, color='green', s=40)
        ax.text(sp[0], sp[1], sp[2]+5, f'S{i+1}', fontsize=8)
    ax.set_xlabel('X / m')
    ax.set_ylabel('Y / m')
    ax.set_zlabel('Z / m')
    ax.set_title('(a) 球体三维视图')
    ax.legend(fontsize=8)

    # (b) 回波延迟对比
    ax = axes[1]
    x_labels = [f'S{i+1}' for i in range(len(sonar_pos))]
    D = np.sqrt(np.sum((sonar_pos - np.array([q2c["x"], q2c["y"], q2c["z"]]))**2, axis=1))
    t_calc = 2 * (D - q2r) / C * 1000
    x_pos = np.arange(len(sonar_pos))
    ax.bar(x_pos - 0.2, echo_delays, 0.4, label='实测值', color='steelblue')
    ax.bar(x_pos + 0.2, t_calc, 0.4, label='计算值', color='coral')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels)
    ax.set_xlabel('声呐位置')
    ax.set_ylabel('回波延迟 / ms')
    ax.set_title('(b) 回波延迟对比')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (c) 拟合残差
    ax = axes[2]
    errors = np.abs(np.array(echo_delays) - t_calc)
    ax.bar(x_pos, errors, 0.6, color='steelblue')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels)
    ax.set_xlabel('声呐位置')
    ax.set_ylabel('绝对误差 / ms')
    ax.set_title('(c) 拟合残差')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(str(FIG_DIR / "q2_sphere.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  图2: q2_sphere.png — OK")


def plot_q3():
    """图3：问题三回波时间函数曲线"""
    x_arr = np.linspace(-200, 400, 500)
    t_arr = 2 * np.sqrt((x_arr - q3t[0])**2 + q3t[1]**2 + q3t[2]**2) / C * 1000
    x_min = q3t[0]
    t_min = 2 * np.sqrt(q3t[1]**2 + q3t[2]**2) / C * 1000

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # (a) t-x 曲线
    ax = axes[0]
    ax.plot(x_arr, t_arr, 'b-', linewidth=2)
    ax.axvline(x_min, color='r', linestyle='--', alpha=0.7, label=f'对称轴 x={x_min:.0f}m')
    ax.plot(x_min, t_min, 'r*', markersize=15, label=f'最小值 {t_min:.2f}ms')
    ax.set_xlabel('船位X坐标 / m')
    ax.set_ylabel('回波时间 / ms')
    ax.set_title('(a) 回波时间函数 t(x)')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (b) 几何示意
    ax = axes[1]
    ax.plot([0, x_min], [0, -np.sqrt(q3t[1]**2 + q3t[2]**2)], 'b--', linewidth=1)
    ax.plot(0, 0, 'gs', markersize=12, label='船位')
    ax.plot(x_min, -np.sqrt(q3t[1]**2 + q3t[2]**2), 'r*', markersize=15, label='目标投影')
    ax.set_xlabel('X / m')
    ax.set_ylabel('距离 / m')
    ax.set_title('(b) 几何关系示意')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (c) 梯度方向
    ax = axes[2]
    grad_x = (x_arr - q3t[0]) / np.sqrt((x_arr - q3t[0])**2 + q3t[1]**2 + q3t[2]**2)
    ax.plot(x_arr, grad_x, 'b-', linewidth=2)
    ax.axhline(0, color='k', linestyle='-', alpha=0.3)
    ax.axvline(x_min, color='r', linestyle='--', alpha=0.7)
    ax.set_xlabel('船位X坐标 / m')
    ax.set_ylabel('梯度方向余弦')
    ax.set_title('(c) 梯度方向分析')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(str(FIG_DIR / "q3_echo_time.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  图3: q3_echo_time.png — OK")


def plot_q4():
    """图4：问题四等时线与梯度分析"""
    x = np.linspace(-100, 300, 200)
    y = np.linspace(-100, 200, 200)
    X, Y = np.meshgrid(x, y)
    T = 2 * np.sqrt((X - q3t[0])**2 + (Y - q3t[1])**2 + q3t[2]**2) / C * 1000

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # (a) 三维曲面
    ax = fig.add_subplot(221, projection='3d')
    ax.plot_surface(X, Y, T, cmap='viridis', alpha=0.8)
    ax.set_xlabel('X / m')
    ax.set_ylabel('Y / m')
    ax.set_zlabel('回波时间 / ms')
    ax.set_title('(a) 回波时间三维曲面')

    # (b) 等高线图
    ax = axes[0][1]
    levels = np.linspace(T.min(), T.min()+80, 15)
    cs = ax.contour(X, Y, T, levels=levels, colors='steelblue')
    ax.clabel(cs, fontsize=8)
    ax.plot(q3t[0], q3t[1], 'r*', markersize=15, label='目标投影')
    ax.set_xlabel('X / m')
    ax.set_ylabel('Y / m')
    ax.set_title('(b) 等时线图')
    ax.legend()
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # (c) 梯度矢量场
    ax = axes[1][0]
    dT_dx = (X - q3t[0]) / np.sqrt((X - q3t[0])**2 + (Y - q3t[1])**2 + q3t[2]**2)
    dT_dy = (Y - q3t[1]) / np.sqrt((X - q3t[0])**2 + (Y - q3t[1])**2 + q3t[2]**2)
    skip = 10
    ax.quiver(X[::skip, ::skip], Y[::skip, ::skip],
              dT_dx[::skip, ::skip], dT_dy[::skip, ::skip],
              alpha=0.6, color='steelblue')
    ax.plot(q3t[0], q3t[1], 'r*', markersize=15, label='目标投影')
    ax.set_xlabel('X / m')
    ax.set_ylabel('Y / m')
    ax.set_title('(c) 梯度矢量场')
    ax.legend()
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # (d) 路径规划
    ax = axes[1][1]
    starts = [(-50, -50), (200, 150), (-80, 100), (250, -50)]
    for sx, sy in starts:
        path_x, path_y = [sx], [sy]
        cx, cy = sx, sy
        for _ in range(80):
            dx = q3t[0] - cx
            dy = q3t[1] - cy
            dist = np.sqrt(dx**2 + dy**2)
            if dist < 2:
                break
            cx += dx / dist * 5
            cy += dy / dist * 5
            path_x.append(cx)
            path_y.append(cy)
        ax.plot(path_x, path_y, '-', linewidth=1.5)
        ax.plot(sx, sy, 'o', markersize=6)
    ax.plot(q3t[0], q3t[1], 'r*', markersize=15, label='目标')
    ax.set_xlabel('X / m')
    ax.set_ylabel('Y / m')
    ax.set_title('(d) 梯度路径规划')
    ax.legend()
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(str(FIG_DIR / "q4_isochrone.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  图4: q4_isochrone.png — OK")


def plot_comprehensive():
    """图5：综合分析"""
    fig, axes = plt.subplots(2, 3, figsize=(18, 11))

    # (a) 探测几何
    ax = axes[0][0]
    ax.plot(ship_x, [0]*len(ship_x), 'gs', markersize=8, label='船位')
    ax.plot(a["x"], a["y"], 'r*', markersize=15, label='结核A')
    ax.plot(b["x"], b["y"], 'b^', markersize=12, label='结核B')
    ax.set_xlabel('X / m')
    ax.set_ylabel('Y / m')
    ax.set_title('(a) 探测几何布局')
    ax.legend(fontsize=8)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # (b) Q1 回波时间
    ax = axes[0][1]
    ax.plot(ship_x, t_A, 'o-', label='结核A')
    ax.plot(ship_x, t_B, 's-', label='结核B')
    ax.set_xlabel('船位X / m')
    ax.set_ylabel('回波时间 / ms')
    ax.set_title('(b) Q1: 回波时间')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # (c) Q2 球体位置
    ax = axes[0][2]
    sonar_pos = np.array(pd["questions"]["Q2"]["sonar_positions"])
    ax.scatter(sonar_pos[:, 0], sonar_pos[:, 1], c='green', s=60, label='声呐')
    circle = plt.Circle((q2c["x"], q2c["y"]), q2r, fill=False, color='steelblue', linewidth=2)
    ax.add_patch(circle)
    ax.plot(q2c["x"], q2c["y"], 'r*', markersize=15, label='球心')
    ax.set_xlabel('X / m')
    ax.set_ylabel('Y / m')
    ax.set_title('(c) Q2: 球体定位')
    ax.legend(fontsize=8)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # (d) Q3 曲线
    ax = axes[1][0]
    x_arr = np.linspace(-200, 400, 500)
    t_arr = 2 * np.sqrt((x_arr - q3t[0])**2 + q3t[1]**2 + q3t[2]**2) / C * 1000
    ax.plot(x_arr, t_arr, 'b-', linewidth=2)
    ax.axvline(q3t[0], color='r', linestyle='--', alpha=0.5)
    ax.set_xlabel('船位X / m')
    ax.set_ylabel('回波时间 / ms')
    ax.set_title('(d) Q3: 回波时间函数')
    ax.grid(True, alpha=0.3)

    # (e) Q4 等时线
    ax = axes[1][1]
    x = np.linspace(-100, 300, 100)
    y = np.linspace(-100, 200, 100)
    X, Y = np.meshgrid(x, y)
    T = 2 * np.sqrt((X - q3t[0])**2 + (Y - q3t[1])**2 + q3t[2]**2) / C * 1000
    ax.contour(X, Y, T, levels=10, colors='steelblue')
    ax.plot(q3t[0], q3t[1], 'r*', markersize=15, label='目标')
    ax.set_xlabel('X / m')
    ax.set_ylabel('Y / m')
    ax.set_title('(e) Q4: 等时线')
    ax.legend()
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # (f) 结果汇总
    ax = axes[1][2]
    ax.axis('off')
    summary = (
        f"Q1 结果:\n"
        f"  结核A: ({a['x']:.2f}, {a['y']:.2f}) m\n"
        f"  结核B: ({b['x']:.2f}, {b['y']:.2f}) m\n\n"
        f"Q2 结果:\n"
        f"  球心: ({q2c['x']:.2f}, {q2c['y']:.2f}, {q2c['z']:.2f}) m\n"
        f"  半径: {q2r:.2f} m\n\n"
        f"Q3 结果:\n"
        f"  对称轴: x = {q3t[0]:.0f} m\n"
        f"  最小回波时间: {res['Q3']['min_echo_time_ms']:.2f} ms\n\n"
        f"Q4 结果:\n"
        f"  最小时间: {res['Q4']['min_time_ms']:.2f} ms\n"
        f"  路径收敛步数: {res['Q4']['gradient_path_steps']}"
    )
    ax.text(0.1, 0.9, summary, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    ax.set_title('(f) 结果汇总')

    plt.tight_layout()
    fig.savefig(str(FIG_DIR / "comprehensive_analysis.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  图5: comprehensive_analysis.png — OK")


def plot_flowchart():
    """图6：系统流程图"""
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Box style
    box_kw = dict(boxstyle='round,pad=0.3', facecolor='lightblue', edgecolor='steelblue', linewidth=2)
    arrow_kw = dict(arrowstyle='->', color='steelblue', lw=2)

    # Title
    ax.text(7, 7.5, '系统整体流程', fontsize=16, ha='center', fontweight='bold',
            fontfamily='SimHei')

    # Row 1: Input → Parser → Strategy → Code
    boxes = [
        (1.5, 6, '题目输入\n(TXT/PDF)'),
        (4, 6, '问题解析\n(Parser Agent)'),
        (6.5, 6, '策略生成\n(Strategy Agent)'),
        (9, 6, '代码生成\n(Code Agent)'),
        (11.5, 6, '实验分析\n(Experiment)'),
    ]
    for x, y, text in boxes:
        ax.text(x, y, text, fontsize=9, ha='center', va='center',
                bbox=box_kw, fontfamily='SimHei')

    # Row 2: Paper → GitHub
    boxes2 = [
        (4, 4, '论文生成\n(Paper Agent)'),
        (6.5, 4, '格式校验\n(Validator)'),
        (9, 4, 'GitHub同步\n(Sync Agent)'),
        (11.5, 4, '输出\n(final_paper.docx)'),
    ]
    for x, y, text in boxes2:
        ax.text(x, y, text, fontsize=9, ha='center', va='center',
                bbox=box_kw, fontfamily='SimHei')

    # MC Analysis branch
    ax.text(1.5, 4, 'Monte Carlo\n灵敏度分析', fontsize=9, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', edgecolor='orange', linewidth=2),
            fontfamily='SimHei')

    # Row 3: Self-correction loop
    ax.text(6.5, 2, '自纠正回路\n(Reality Audit)', fontsize=9, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', edgecolor='orange', linewidth=2),
            fontfamily='SimHei')

    # Arrows Row 1
    for i in range(len(boxes)-1):
        ax.annotate('', xy=(boxes[i+1][0]-0.8, boxes[i+1][1]),
                    xytext=(boxes[i][0]+0.8, boxes[i][1]),
                    arrowprops=arrow_kw)

    # Arrow Code → Paper
    ax.annotate('', xy=(4+0.8, 4), xytext=(9-0.8, 6),
                arrowprops=dict(arrowstyle='->', color='steelblue', lw=2,
                                connectionstyle='arc3,rad=0.2'))

    # Arrows Row 2
    for i in range(len(boxes2)-1):
        ax.annotate('', xy=(boxes2[i+1][0]-0.8, boxes2[i+1][1]),
                    xytext=(boxes2[i][0]+0.8, boxes2[i][1]),
                    arrowprops=arrow_kw)

    # Error loop arrow
    ax.annotate('', xy=(9, 5.5), xytext=(6.5, 2.5),
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5,
                                connectionstyle='arc3,rad=-0.3', linestyle='dashed'))
    ax.text(8.5, 3.5, '失败时\n自动修复', fontsize=8, color='red', ha='center',
            fontfamily='SimHei')

    # MC arrow
    ax.annotate('', xy=(4-0.8, 4), xytext=(1.5+0.8, 4),
                arrowprops=dict(arrowstyle='<->', color='orange', lw=1.5))

    plt.tight_layout()
    fig.savefig(str(FIG_DIR / "system_flowchart.png"), dpi=300, bbox_inches='tight',
                facecolor='white')
    plt.close(fig)
    print("  图6: system_flowchart.png — OK")


def plot_mc_enhanced():
    """图7：增强版 Monte Carlo 分析"""
    # Reload data
    a = res["Q1"]["nodule_A"]
    xa, ya = a["x"], a["y"]
    ship_x_arr = np.array(ship_x)
    echo_a = np.array(t_A)
    rng = np.random.default_rng(42)

    samples_x, samples_y = [], []
    for _ in range(1000):
        noisy = echo_a + rng.normal(0, 0.5, size=len(echo_a))
        dists = noisy * C / 2000
        A = np.column_stack([2 * ship_x_arr, -np.ones(len(ship_x_arr))])
        b_vec = ship_x_arr**2 - dists**2
        try:
            result, _, _, _ = np.linalg.lstsq(A, b_vec, rcond=None)
            a_coeff, b_coeff = result
            y_sq = max(0, b_coeff - a_coeff**2)
            samples_x.append(a_coeff)
            samples_y.append(np.sqrt(y_sq))
        except:
            continue

    sx, sy = np.array(samples_x), np.array(samples_y)
    dx, dy = sx - xa, sy - ya
    dist = np.sqrt(dx**2 + dy**2)

    fig = plt.figure(figsize=(16, 12))

    # Scatter + ellipse
    ax1 = fig.add_subplot(2, 2, 1)
    ax1.scatter(sx, sy, s=2, alpha=0.2, c='steelblue')
    ax1.plot(xa, ya, 'r*', markersize=15, label=f'真值 ({xa:.1f}, {ya:.1f})')
    ax1.plot(np.mean(sx), np.mean(sy), 'kx', markersize=12,
             label=f'均值 ({np.mean(sx):.2f}, {np.mean(sy):.2f})')
    from matplotlib.patches import Ellipse
    cov = np.cov(sx, sy)
    eigvals, eigvecs = np.linalg.eigh(cov)
    angle = np.degrees(np.arctan2(eigvecs[1, 0], eigvecs[0, 0]))
    for nsig, alpha_val in [(2, 0.15), (3, 0.08)]:
        ell = Ellipse((np.mean(sx), np.mean(sy)),
                      2*nsig*np.sqrt(eigvals[0]), 2*nsig*np.sqrt(eigvals[1]),
                      angle=angle, fill=True, alpha=alpha_val, color='steelblue',
                      label=f'{nsig}σ 椭圆' if nsig == 2 else None)
        ax1.add_patch(ell)
    ax1.set_xlabel('X / m')
    ax1.set_ylabel('Y / m')
    ax1.set_title('(a) 定位散点云与误差椭圆')
    ax1.legend(fontsize=8)
    ax1.set_aspect('equal')
    ax1.grid(True, alpha=0.3)

    # Offset distribution
    ax2 = fig.add_subplot(2, 2, 2)
    ax2.hist(dx, bins=50, density=True, alpha=0.6, color='steelblue', label='X偏移')
    ax2.hist(dy, bins=50, density=True, alpha=0.6, color='coral', label='Y偏移')
    ax2.axvline(0, color='k', linestyle='--')
    ax2.set_xlabel('偏移量 / m')
    ax2.set_ylabel('概率密度')
    ax2.set_title('(b) 偏移分布')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Heatmap
    ax3 = fig.add_subplot(2, 2, 3)
    h = ax3.hist2d(dx, dy, bins=50, cmap='YlOrRd', density=True)
    plt.colorbar(h[3], ax=ax3, label='密度')
    ax3.set_xlabel('X偏移 / m')
    ax3.set_ylabel('Y偏移 / m')
    ax3.set_title('(c) 偏移热图')
    ax3.set_aspect('equal')

    # Boxplot
    ax4 = fig.add_subplot(2, 2, 4)
    bp = ax4.boxplot([dx, dy, dist], labels=['X偏移', 'Y偏移', '距离'],
                    patch_artist=True, widths=0.5)
    colors = ['steelblue', 'coral', 'lightgreen']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax4.set_ylabel('误差 / m')
    ax4.set_title('(d) 误差箱线图')
    ax4.grid(True, alpha=0.3, axis='y')
    rms = np.sqrt(np.mean(dx**2 + dy**2))
    stats = f'X: μ={np.mean(dx):.4f}, σ={np.std(dx):.4f}\nY: μ={np.mean(dy):.4f}, σ={np.std(dy):.4f}\nRMS: {rms:.4f}m'
    ax4.text(0.98, 0.98, stats, transform=ax4.transAxes, fontsize=8,
             va='top', ha='right', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    fig.savefig(str(FIG_DIR / "mc_sensitivity.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  图7: mc_sensitivity.png — OK")


if __name__ == "__main__":
    print("=" * 50)
    print("  图片中文化重生成 (300 DPI)")
    print("=" * 50)
    plot_q1()
    plot_q2()
    plot_q3()
    plot_q4()
    plot_comprehensive()
    plot_flowchart()
    plot_mc_enhanced()
    print("=" * 50)
    print("  完成")
    print("=" * 50)
