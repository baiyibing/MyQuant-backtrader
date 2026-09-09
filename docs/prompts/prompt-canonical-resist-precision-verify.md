## 换手阻力精度回归验证

对全市场换手阻力计算的两个方法（`--method batch` 优化版 vs `--method original` 原始基准）做全面精度对比。

### 第一步：生成两个日期的全量 CSV

```bash
cd "E:/PycharmProjects/OSkhQuant1.3"

# 日期 1: 20260525
PYTHONUNBUFFERED=1 D:/anaconda3/envs/vanna311/python.exe scripts/data/full_market_canonical_resist.py \
  --date 20260525 --method batch --workers 7 \
  --free-float-policy warn-zero --target-date-policy strict \
  --output backtest_output/canonical_resist_batch_20260525.csv

PYTHONUNBUFFERED=1 D:/anaconda3/envs/vanna311/python.exe scripts/data/full_market_canonical_resist.py \
  --date 20260525 --method original --workers 7 \
  --free-float-policy warn-zero --target-date-policy strict \
  --output backtest_output/canonical_resist_original_20260525.csv

# 日期 2: 20260529（前一个交易日）
PYTHONUNBUFFERED=1 D:/anaconda3/envs/vanna311/python.exe scripts/data/full_market_canonical_resist.py \
  --date 20260529 --method batch --workers 7 \
  --free-float-policy warn-zero --target-date-policy strict \
  --output backtest_output/canonical_resist_batch_20260529.csv

PYTHONUNBUFFERED=1 D:/anaconda3/envs/vanna311/python.exe scripts/data/full_market_canonical_resist.py \
  --date 20260529 --method original --workers 7 \
  --free-float-policy warn-zero --target-date-policy strict \
  --output backtest_output/canonical_resist_original_20260529.csv
```

预计总耗时：batch 约 2-5 分钟 × 2 + original 约 10-20 分钟 × 2 ≈ **30–50 分钟**。

> **为什么加 `PYTHONUNBUFFERED=1`**：多进程下 stdout 被缓冲，不加会导致长时间看不到进度，误以为卡住。
（已优化：original 也走 duckdb_persistent 批量加载 + capital 预加载，只保留原始 4×cyqk 算法不变）

### 第二步：逐列对比

对每个日期，运行以下 Python 脚本。**核心列必须完全一致**（diff = 0），辅助列允许浮点正常波动：

```python
import pandas as pd
import numpy as np

for date in ['20260525', '20260529']:
    b = pd.read_csv(f'backtest_output/canonical_resist_batch_{date}.csv')
    o = pd.read_csv(f'backtest_output/canonical_resist_original_{date}.csv')
    
    print(f"\n===== {date} =====")
    print(f"batch: {len(b)} rows, original: {len(o)} rows")
    
    # 确保行数一致
    assert len(b) == len(o), f"Row count mismatch: {len(b)} vs {len(o)}"
    
    # 核心数值列——必须完全一致
    core_cols = ['close', 'cyqk_T', 'cyqk_T_1', 'profit_chip_diff', 
                 'turnover', 'turnover_resistance', 'turnover_free', 'turnover_resistance_free']
    
    all_pass = True
    for col in core_cols:
        # 按 stock_code 对齐后对比
        merged = b[['stock_code', col]].merge(o[['stock_code', col]], on='stock_code', suffixes=('_b', '_o'))
        diff = (merged[f'{col}_b'] - merged[f'{col}_o']).abs()
        max_diff = diff.max()
        
        if max_diff > 1e-10:
            n_diff = (diff > 1e-10).sum()
            print(f"  ❌ {col}: max_diff={max_diff:.2e}, {n_diff} rows differ")
            all_pass = False
        else:
            print(f"  ✅ {col}: identical (max_diff={max_diff:.2e})")
    
    # 股本列——允许合理差异（原版和优化版查询路径不同但语义等价）
    for col in ['circulating_capital', 'freeFloatCapital']:
        merged = b[['stock_code', col]].merge(o[['stock_code', col]], on='stock_code', suffixes=('_b', '_o'))
        diff = (merged[f'{col}_b'] - merged[f'{col}_o']).abs()
        rel_diff = diff / merged[f'{col}_o'].abs().clip(lower=1e-12)
        bad = (diff > 1e-6) & (rel_diff > 1e-9)
        if bad.sum() > 0:
            print(f"  ⚠️  {col}: {bad.sum()} rows differ >1e-6, checking rel...")
            bad_rel = (diff > 1) & (rel_diff > 0.01)  # >1 且 >1% 才算真问题
            if bad_rel.sum() > 0:
                print(f"  ❌ {col}: {bad_rel.sum()} rows have >1% relative difference!")
                all_pass = False
            else:
                print(f"  ✅ {col}: minor differences within tolerance")
        else:
            print(f"  ✅ {col}: identical")
    
    # 布林带
    for col in ['bb_upper', 'bb_middle', 'bb_lower', 'bb_position', 'bb_width']:
        merged = b[['stock_code', col]].merge(o[['stock_code', col]], on='stock_code', suffixes=('_b', '_o'))
        diff = (merged[f'{col}_b'] - merged[f'{col}_o']).abs()
        max_diff = diff.max()
        if max_diff > 1e-6:
            print(f"  ⚠️  {col}: max_diff={max_diff:.2e}")
        else:
            print(f"  ✅ {col}: identical")
    
    # 排序稳定性——Top 1000 重叠率
    b['_abs'] = b['turnover_resistance_free'].abs()
    o['_abs'] = o['turnover_resistance_free'].abs()
    top_b = set(b.sort_values('_abs', ascending=False).head(1000)['stock_code'])
    top_o = set(o.sort_values('_abs', ascending=False).head(1000)['stock_code'])

## v1.1 精度说明（2026-06-07）

Python `full_market_canonical_resist.py` 已修复 `np.arange` 浮点累积误差（`make_price_grid` 改用 `min_p + np.arange(n) * step`）。`--method batch` 和 `--method original` 均使用同一网格函数。两方法 diff=0。

Rust 与 Python 同等参数下（`--free-float-policy warn-zero`）4595 只全 diff=0。验证：`scripts/gates/verify_rust_python_alignment.py --date YYYYMMDD --free-float-policy warn-zero`。
    overlap = len(top_b & top_o) / len(top_b)
    print(f"  {'✅' if overlap > 0.999 else '❌'} Top-1000 overlap: {overlap:.4f}")
    if overlap <= 0.999:
        diff_codes = top_b.symmetric_difference(top_o)
        print(f"     Diff codes: {list(diff_codes)[:10]}")
        all_pass = False
    
    print(f"\n  {'ALL PASS' if all_pass else 'SOME FAILURES'}")

print("\n===== DONE =====")
```

### 第三步：输出报告

报告格式：
```
换手阻力精度回归验证报告
日期：2026-05-31
验证日期：20260525, 20260529

结果：
- 20260525: 8 个核心列全部一致 ✅，Top-1000 重叠率 99.9%+ ✅
- 20260529: 8 个核心列全部一致 ✅，Top-1000 重叠率 99.9%+ ✅

结论：batch 和 original 在两个日期上精度完全一致，优化未引入数值偏差。
```

### 预期结果

| 日期 | 核心列 | 股本列 | 布林带 | Top-1000 |
|------|--------|--------|--------|----------|
| 20260525 | 8/8 完全一致 | 一致 | 一致 | >99.9% |
| 20260529 | 8/8 完全一致 | 一致 | 一致 | >99.9% |

如果任一日期的核心列出现差异 > 1e-10，终止并报告。

---

## 与 Rust 对齐验证（v1.2 新增）

batch/original 内部一致后，还必须与 Rust CLI 对齐。步骤见 `prompt-rust-turnover-resistance.md` 的“与 Python 全市场对齐验证”小节。

**关键提醒**：
- Python 命令必须加 `PYTHONUNBUFFERED=1`
- Python 必须使用 `--target-date-policy strict` 和 `--free-float-policy warn-zero`
- 若 Python 与 Rust 行数不同，优先检查边界策略（目标日期、动态窗口、最小交易日、free_float 缺失处理），不是算法 bug
- 若 batch/original 行数相同但与 Rust 行数不同，说明 Python 内部一致但边界策略未与 Rust 对齐
