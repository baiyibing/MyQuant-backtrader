# Rust vs Python 换手阻力全市场端到端验证报告

**日期**: 2026-06-01
**验证目标**: 确认 `make_price_grid` 精度修复 + Rust T-1 capital 修复后，全市场无回归

---

## 1. 验证背景

本次验证覆盖两项修复：

| 修复 | 文件 | 内容 |
|------|------|------|
| Python 价格网格精度 | 5 个 Python 文件，10 处替换 | `np.arange` → `make_price_grid` |
| Rust T-1 capital 分离 | `algorithm.rs` + `main.rs` | `compute_cyqk_from_curpdfs` 接受 T/T-1 各自 capital |

此前仅对 3 只差异最大股票（002374.SZ、000727.SZ、000088.SZ）做了定点验证。本次扩展到全市场。

## 2. 验证方法

### 2.1 运行环境

- 日期：2026-05-25（交易日）
- 窗口：1000 日，步长 0.01
- Rust 二进制：`E:\rust-targets\release\turnover-resist.exe`（含 T-1 capital 修复，22:27 编译）
- Python：`scripts/full_market_canonical_resist.py --method batch`（含 `make_price_grid` 修复）

### 2.2 运行命令

```bash
# Rust（从 turnover-resist/ 目录）
E:\rust-targets\release\turnover-resist.exe \
  --date 20260525 --data-dir ../stock_data \
  --output ../backtest_output/_rust_e2e_v2.csv

# Python（从仓库根目录）
D:/anaconda3/envs/vanna311/python.exe scripts/full_market_canonical_resist.py \
  --date 20260525 --method batch \
  --output backtest_output/_python_e2e.csv
```

### 2.3 对比方法

```python
rust = pd.read_csv('_rust_e2e_v2.csv', encoding='utf-8-sig')
py   = pd.read_csv('_python_e2e.csv',    encoding='utf-8-sig')
merged = rust.merge(py, on='stock_code', suffixes=('_rust', '_py'), how='inner')

# 逐股票对比 4 项指标的精确匹配
for col in ['cyqk_T', 'cyqk_T_1', 'turnover_resistance', 'turnover_resistance_free']:
    diff = (merged[f'{col}_rust'] - merged[f'{col}_py']).abs()
    # 统计 max diff、>1e-4 数量、>1e-6 数量、精确匹配数量
```

## 3. 验证结果

### 3.1 数据规模

| 端 | 股票数 |
|----|-------|
| Rust | 5513 |
| Python | 4594 |
| 共同股票 | **4594** |

Rust 多出的 919 只为 Python 端 free_float_shares 数据缺失或 capital ≤ 0 被过滤的股票。

### 3.2 对比结果

| 指标 | max diff | >1e-4 | >1e-6 | 精确匹配 |
|------|----------|-------|-------|---------|
| cyqk_T | **0** | 0 | 0 | **4594/4594** |
| cyqk_T_1 | **0** | 0 | 0 | **4594/4594** |
| turnover_resistance | **0** | 0 | 0 | **4594/4594** |
| turnover_resistance_free | **0** | 0 | 0 | **4594/4594** |

**4594 只共同股票，4 项指标全部精确匹配（diff = 0）。**

### 3.3 关键验证点

- **精度修复无回归**：`make_price_grid` 替换后，不仅 3 只差异最大股票修复，全市场 4594 只均精确匹配
- **T-1 capital 修复生效**：5 只在 2026-05-25 有 capital 变更的股票（603889.SH、002396.SZ、605100.SH、688168.SH、300757.SZ）cyqk_T_1 也精确匹配
- **Rust 多出的 919 只**：Python 端因 capital 数据缺失返回 None 被过滤，属于数据覆盖差异，非算法差异

## 4. 过程中的问题与教训

### 4.1 二进制路径混淆

`CARGO_TARGET_DIR=E:\rust-targets` 导致编译输出到 `E:\rust-targets\release\` 而非 `turnover-resist/target/release/`。初次对比时使用了旧二进制（不含 T-1 capital 修复），误报 19 只 cyqk_T_1 差异。

**教训**：Rust 二进制位置以 `CARGO_TARGET_DIR` 环境变量为准，不要假设在 `target/` 子目录。

### 4.2 sccache 误判

`cargo clean --release` 后全量重编时 sccache 缓存失效报错，但编译本身成功。问题不在 sccache。

**教训**：sccache 报错不影响编译结果，应检查实际编译输出而非仅看 sccache 日志。

## 5. 结论

| 项目 | 状态 |
|------|------|
| Python `make_price_grid` 精度修复 | ✅ 全市场验证通过 |
| Rust T-1 capital 分离修复 | ✅ 全市场验证通过 |
| Rust 与 Python 对齐 | ✅ 4594/4594 精确匹配 |
| 回归风险 | ✅ 无回归 |

**turnover-resist 精度修复与 T-1 capital 修复均已通过全市场端到端验证。**

---

**输出文件**：
- Rust: `backtest_output/_rust_e2e_v2.csv`
- Python: `backtest_output/_python_e2e.csv`
