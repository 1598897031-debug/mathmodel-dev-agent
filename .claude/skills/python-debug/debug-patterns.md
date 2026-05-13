# Python Debug Patterns Reference

## 常见 Traceback 模式速查

### Pattern 1: Import Error
```
Traceback (most recent call last):
  File "solution.py", line 5, in <module>
    import numpy as np
ModuleNotFoundError: No module named 'numpy'
```
**Fix**: `pip install numpy`

### Pattern 2: Shape Mismatch
```
Traceback (most recent call last):
  File "solution.py", line 42, in solve
    result = np.dot(A, b)
ValueError: shapes (3,4) (3,) not aligned
```
**Fix**: 检查矩阵维度，转置或重塑

### Pattern 3: Division by Zero
```
Traceback (most recent call last):
  File "solution.py", line 28, in normalize
    return (x - mean) / std
ZeroDivisionError: float division by zero
```
**Fix**: 添加 `if std == 0: return np.zeros_like(x)` 保护

### Pattern 4: File Not Found
```
Traceback (most recent call last):
  File "solution.py", line 12, in load_data
    df = pd.read_csv("data.csv")
FileNotFoundError: [Errno 2] No such file or directory: 'data.csv'
```
**Fix**: 使用 `Path(__file__).parent / "data.csv"` 或创建示例数据

### Pattern 5: Type Error
```
Traceback (most recent call last):
  File "solution.py", line 35, in optimize
    result = minimize(obj, x0, constraints=cons)
TypeError: minimize() got an unexpected keyword argument 'constraints'
```
**Fix**: 检查函数签名，`scipy.optimize.minimize` 用 `constraints` 是正确的，可能是版本问题

### Pattern 6: Singularity Matrix
```
Traceback (most recent call last):
  File "solution.py", line 55, in solve
    x = np.linalg.solve(A, b)
numpy.linalg.LinAlgError: Singular matrix
```
**Fix**: 使用伪逆 `np.linalg.pinv(A)` 或最小二乘 `np.linalg.lstsq(A, b, rcond=None)`

### Pattern 7: Subprocess Failed
```
Traceback (most recent call last):
  File "solution.py", line 80, in run_git
    result = subprocess.run(["git", "status"], capture_output=True)
FileNotFoundError: [Errno 2] No such file or directory: 'git'
```
**Fix**: 检查外部命令是否安装，或使用 try-except 优雅降级

### Pattern 8: Encoding Error
```
UnicodeDecodeError: 'gbk' codec can't decode byte 0xaf in position 100
```
**Fix**: 添加 `encoding="utf-8"` 参数

## 科学计算常见陷阱

### 1. 浮点精度
```python
# 错误
if result == 0.0:
# 正确
if abs(result) < 1e-10:
```

### 2. 数组 vs 标量
```python
# 错误
result = np.array([1, 2, 3]) + 1  # 广播正常
result = np.array([1, 2, 3]) + np.array([1, 2])  # 维度不匹配
```

### 3. 原地修改
```python
# 错误 — 修改了原始数据
data[data < 0] = 0

# 正确 — 创建副本
data = data.copy()
data[data < 0] = 0
```

### 4. 空数组处理
```python
# 错误
np.mean([])  # RuntimeWarning

# 正确
arr = np.array([])
result = np.mean(arr) if len(arr) > 0 else 0.0
```

### 5. 随机种子
```python
# 为了可重复性
np.random.seed(42)
# 或者
rng = np.random.default_rng(42)
```
