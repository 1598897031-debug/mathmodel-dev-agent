# Experiment Report

## 1. Basic Information

- **Title**: sample_optimization
- **Problem Type**: 待分类（无 API key）
- **Objective**: 
- **Approach**: 线性规划 (LP)

## 2. Evaluation Metrics

| Metric | Value |
|--------|-------|
| n_samples | 7 |
| rmse | 1700.3185 |
| mape | 25.4571 |
| mae | 1067.1429 |
| r_squared | -1.6399 |
| accuracy_10pct | 0.0% |
| accuracy_20pct | 0.0% |

### Metric Descriptions

- **RMSE** (Root Mean Square Error): Lower is better
- **MAPE** (Mean Absolute Percentage Error): Lower is better, in percentage
- **MAE** (Mean Absolute Error): Lower is better
- **R-squared**: Closer to 1 is better
- **Accuracy**: Higher is better

## 4. Raw Output

```
==================================================
  优化模型求解
==================================================

顶点分析:
  (0, 0): 利润=0 [可行]
  (60, 0): 利润=3000 [可行]
  (0, 30): 利润=1200 [可行]
  (54, 12): 利润=3180 [可行]

最优解:
  产品A产量: 54.00
  产品B产量: 12.00
  最大利润: 3180.00

```

## 5. Conclusion

- RMSE = 1700.3185
- R-squared = -1.6399
- Model performance: **Poor**
