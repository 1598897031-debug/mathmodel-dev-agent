"""
MathModel Dev Agent - 优化模型求解代码 (纯标准库版本)
"""
import math

def solve():
    """线性规划求解 (单纯形法简化版)"""
    print("=" * 50)
    print("  优化模型求解")
    print("=" * 50)

    # 示例: max 50x + 40y
    # 约束: 2x + y <= 120, x + 3y <= 90, x >= 0, y >= 0
    # 使用穷举顶点法求解

    # 找到可行域顶点
    vertices = []

    # 约束交点
    # 2x + y = 120 与 x + 3y = 90 的交点
    # 解方程组: 2x + y = 120, x + 3y = 90
    # => x = (360 - 90) / 5 = 54, y = (120 - 108) / 5 = 12/5 = 2.4... 不对
    # 2x + y = 120 => y = 120 - 2x
    # x + 3(120 - 2x) = 90 => x + 360 - 6x = 90 => -5x = -270 => x = 54
    # y = 120 - 2*54 = 12
    # 但 x + 3y = 54 + 36 = 90 OK
    # 2x + y = 108 + 12 = 120 OK

    vertices.append((0, 0))           # 原点
    vertices.append((60, 0))          # 2x+y=120, y=0
    vertices.append((0, 30))          # x+3y=90, x=0
    vertices.append((54, 12))         # 两约束交点

    # 计算目标函数值
    best_val = -float("inf")
    best_point = (0, 0)
    print("\n顶点分析:")
    for x, y in vertices:
        val = 50 * x + 40 * y
        feasible = (2 * x + y <= 120 + 0.001) and (x + 3 * y <= 90 + 0.001)
        status = "可行" if feasible else "不可行"
        print(f"  ({x}, {y}): 利润={val:.0f} [{status}]")
        if feasible and val > best_val:
            best_val = val
            best_point = (x, y)

    print(f"\n最优解:")
    print(f"  产品A产量: {best_point[0]:.2f}")
    print(f"  产品B产量: {best_point[1]:.2f}")
    print(f"  最大利润: {best_val:.2f}")

    return {"x": list(best_point), "profit": best_val}

if __name__ == "__main__":
    solve()
