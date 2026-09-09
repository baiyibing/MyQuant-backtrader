# Rust 版 canonical 换手阻力全市场计算 — Agent 持续改进提示词

## 用途

本提示词用于指导 AI Agent 对 Rust 版 canonical（换手率衰减）筹码换手阻力计算程序进行持续改进、优化和维护。

Rust 程序位于 `turnover-resist/`，是 `scripts/data/full_market_canonical_resist.py` 的高性能替代实现。当前状态：**已完成基础版本，正确性已验证**。

## 核心文档

| 文档 | 路径 | 用途 |
|------|------|------|
| **Rust 实现文档**（权威） | `docs/backtest/chip/turnover_resistance_rust.md` | 架构设计、使用指南、配置说明、已知问题、优化方向 |
| **Python 版提示词** | `docs/prompts/prompt-canonical-turnover-resistance.md` | Python 参考实现的算法描述、运行方式 |
| **换手阻力算法规格** | `docs/backtest/chip/turnover_resistance_algorithm.md` | 完整数学公式链、各层详细展开 |
| **通用 Outbox 架构** | `docs/knowledge/performance/solutions/solution-P2-outbox-generic-dispatch.md` | v6 实装参考（工程模式） |

## 源代码

```
turnover-resist/
  Cargo.toml                  # 依赖声明 + dev/test/release/release-fast profiles
  .cargo/config.toml          # sccache + rust-lld
  src/
    lib.rs                    # 库入口（algorithm/data/types/bollinger/cli）
    main.rs                   # CLI 入口 + rayon 并行编排 + 排序 + CSV 输出
    cli.rs                    # clap derive 参数定义
    types.rs                  # BarRow, OutputRow, FloatSharesInfo, ComputeContext 等 struct
    data.rs                   # polars parquet I/O + float_shares 加载 + 代码格式转换
    algorithm.rs              # 核心数学：triang_pdf, calc_curpdf, calc_cumpdf, cyqk（~200行）
    bollinger.rs              # 布林带（20日, 2σ）
```

## 执行前置条件

在运行 Rust 换手阻力计算前，必须确认：

1. **目标日期的日线 parquet 已存在且最新**  
   以下命令检查 `000001_SZ` 在 front 复权下的最新日期是否等于目标日期：
   ```bash
   D:/anaconda3/envs/vanna311/python.exe -c "
   import pandas as pd
   from pathlib import Path
   p = Path('stock_data/period=1d/dividend_type=front/symbol=000001_SZ/data.parquet')
   print(pd.read_parquet(p).index.max())
   "
   ```
   若日期不匹配，必须先按 `prompt-stock-data-backfill-export-workflow.md` 完成日线更新和 DuckDB 同步。

2. **Rust 二进制已存在**  
   确认以下路径之一存在：
   - `/e/rust-targets/release/turnover-resist.exe`
   - `./turnover-resist/target/release/turnover-resist.exe`
   - `./turnover-resist/target/release-fast/turnover-resist.exe`
   
   若不存在，先按下方“编译和运行”步骤编译。

## 编译和运行

```bash
# 进入项目目录
cd E:/PycharmProjects/OSkhQuant1.3/turnover-resist

# 日常迭代（推荐，release-fast：无 LTO，最快重编译）
cargo build --profile release-fast

# 质量门禁
cargo fmt --check
cargo test --all-targets
cargo clippy --all-targets --all-features -- -D warnings

# 发布构建（thin LTO）
cargo build --release

# 回到仓库根目录运行
cd E:/PycharmProjects/OSkhQuant1.3

# 可选：覆盖线程栈大小（未设置时程序默认 8MB）
# export RUST_MIN_STACK=8388608
```

> **⚠️ 二进制路径注意**：`turnover-resist/.cargo/config.toml` 及全局环境变量可能将 `CARGO_TARGET_DIR` 指向非本地目录（如 `E:\rust-targets`）。编译后请先确认二进制实际位置：
> ```bash
> # 本地默认路径
> ls ./turnover-resist/target/release/turnover-resist.exe
> # 或全局重定向路径（以 E:\rust-targets 为例）
> ls /e/rust-targets/release/turnover-resist.exe
> ls /e/rust-targets/release-fast/turnover-resist.exe
> ```

```bash
# 全市场计算（默认 window=1000 个交易日，≈4 年）
# 注意：根据实际编译输出路径替换以下二进制路径
/e/rust-targets/release/turnover-resist.exe \
  --date 20260604 \
  --sort-by free \
  --window 1000 \
  --step 0.01 \
  --free-float-policy warn-zero \
  --output backtest_output/canonical_resist_rust_20260604.csv  # 推荐显式带 _rust_ 后缀
```

**参数**：
- `--date YYYYMMDD`：截面日期
- `--window 1000`（默认）：筹码衰减窗口（交易日），不足自动用全部
- `--step 0.01`（默认）：价格步长
- `--sort-by free|circulating`（默认 `free`）：排序口径
- `--free-float-policy warn-zero|skip|fail`（默认 `warn-zero`）：缺自由流通股本时策略。**与 Python 默认一致**
  - `warn-zero`：缺数据时 freeFloatCapital=0，继续计算
  - `skip`：跳过该股票
  - `fail`：报错退出

**输出**：18 列 CSV，按 `|turnover_resistance_free|`（自由流通股本口径换手阻力绝对值）降序排列。

**超时设置**：全市场 5500+ 只股票、window=1000 时，运行时间约 **60–180 秒**。前台执行 timeout 建议 **≥ 300s**；若使用后台任务，建议 `disable_timeout=true` 或 timeout ≥ 600s。

**典型运行输出示例**：
```
date=20260604 window=1000 step=0.01 max_grid_points=250000 stocks=5531 sort_by=Free ...
  parquet load 500/5531 stocks
  ...
  [Timing] batch loaded 5530 stocks in 10.1s
  parquet stats: requested=5531 loaded=5530 missing_path=1 ...
  500/5531 processed
  ...

Total: valid=5516, skipped=15
  skip breakdown:
    -            insufficient_bars: 10
    -        curpdf_window_invalid: 3
    -         target_date_mismatch: 1
    -                 missing_bars: 1

[Timing] setup=0.0s  capital=0.2s  compute=67.2s  sort+csv=0.0s  total=77.6s

Output: backtest_output/canonical_resist_rust_20260604.csv  rows=5516

Top 20 by |turnover_resistance_free|:
   1. 601816.SH     京沪高铁 resist=  -55.3165 cyqk_T=  0.2315 ...
   ...
```

## 输出验证

Rust 程序退出后必须执行：

```bash
ls -lh backtest_output/canonical_resist_rust_YYYYMMDD.csv
head -n 3 backtest_output/canonical_resist_rust_YYYYMMDD.csv
wc -l backtest_output/canonical_resist_rust_YYYYMMDD.csv
```

- 文件必须存在且非空。
- 第一行必须是 CSV 表头（以 `\u{FEFF}stock_code,stock_name,date,...` 开头）。
- 行数应等于 Rust 输出中的 `valid` 数量加 1（表头）。
- 若 `valid=0` 或文件为空，说明输入数据缺失或日期错误，需回查前置条件。

### 与 Python 全市场对齐验证（推荐每次更新日线后执行）

```bash
# 1. 跑 Python 参考实现（注意 PYTHONUNBUFFERED=1 确保进度可见）
PYTHONUNBUFFERED=1 D:/anaconda3/envs/vanna311/python.exe scripts/data/full_market_canonical_resist.py \
  --date 20260616 --sort-by free --free-float-policy warn-zero --target-date-policy strict \
  --output backtest_output/canonical_resist_batch_20260616.csv

# 2. 跑 Rust
/e/rust-targets/release/turnover-resist.exe \
  --date 20260616 --sort-by free --window 1000 --step 0.01 \
  --output backtest_output/canonical_resist_rust_20260616.csv

# 3. 快速对比（行数 + 核心列 + Top-1000 重叠率）
D:/anaconda3/envs/vanna311/python.exe -c "
import pandas as pd
py = pd.read_csv('backtest_output/canonical_resist_batch_20260616.csv', encoding='utf-8-sig')
rust = pd.read_csv('backtest_output/canonical_resist_rust_20260616.csv', encoding='utf-8-sig')
print(f'Python: {len(py)} rows, Rust: {len(rust)} rows')
m = py.merge(rust, on='stock_code', how='outer', indicator=True)
print(m['_merge'].value_counts())
common = m[m['_merge'] == 'both']
for col in ['cyqk_T', 'turnover_resistance', 'turnover_resistance_free']:
    diff = (common[f'{col}_x'] - common[f'{col}_y']).abs()
    print(f'{col}: max_diff={diff.max():.6e}, diff_rows={(diff > 1e-10).sum()}')
py['abs'] = py['turnover_resistance_free'].abs()
rust['abs'] = rust['turnover_resistance_free'].abs()
top_b = set(py.sort_values('abs', ascending=False).head(1000)['stock_code'])
top_r = set(rust.sort_values('abs', ascending=False).head(1000)['stock_code'])
print(f'Top-1000 overlap: {len(top_b & top_r) / len(top_b):.4f}')
"
```

**验收标准**：
- Python 与 Rust 行数相同
- 核心列 `cyqk_T`, `cyqk_T_1`, `turnover_resistance`, `turnover_resistance_free` 的 `max_diff < 1e-10`
- Top-1000 重叠率 100%
- `turnover` / `turnover_free` 允许 1e-6 四舍五入差异
- `bb_middle` / `bb_position` 允许微小浮点差异

**若行数不同，按以下顺序排查**：
1. Python 是否使用 `--target-date-policy strict`（Rust 默认 strict）
2. Python 是否启用动态窗口（可用交易日不足 `window+1` 时自动缩短，与 Rust 一致）
3. Python 是否应用最小 20 交易日过滤（与 Rust `insufficient_bars` 一致）
4. Python `--free-float-policy` 是否为 `warn-zero`（与 Rust 一致）

**核心列差异 > 1e-10**：算法实现不一致，需单只股票中间量对比，优先检查 `make_price_grid`、三角 PDF、衰减公式。

**编译时间说明**：按 `docs/backtest/chip/turnover_resistance_rust_build_optimization.md`，日常推荐 `release-fast`，发布用 `--release`。

## 与 Python 对照验证

每次算法改动后，必须与 Python 参考实现对照验证。

### 单只股票精确对比

```bash
cd E:/PycharmProjects/OSkhQuant1.3

# 选 3-5 只代表性股票（大盘蓝筹、小盘成长、次新股、高价股）
D:/anaconda3/envs/vanna311/python.exe -c "
import pandas as pd
import numpy as np
from qlib_cost import cyq
from backtest.chip_algorithm import adapt_columns

# 用 Python 跑同一只股票，导出中间量（xs、curpdf[0]、cumpdf[0]、cyqk）
# 在 Rust 侧加 debug print 对比
"
```

### 全市场 CSV 对比

```bash
# 1. 跑 Python
D:/anaconda3/envs/vanna311/python.exe scripts/data/full_market_canonical_resist.py \
  --date 20260522 --window 100 --output backtest_output/py_test.csv

# 2. 跑 Rust
./turnover-resist/target/release/turnover-resist \
  --date 20260522 --window 100 --sort-by free --output backtest_output/rust_test.csv

# 3. 对比
D:/anaconda3/envs/vanna311/python.exe -c "
import pandas as pd, numpy as np
rust = pd.read_csv('backtest_output/rust_test.csv')
py = pd.read_csv('backtest_output/py_test.csv')
m = rust.merge(py, on='stock_code', suffixes=('_r','_p'))
d = (m['cyqk_t'] - m['cyqk_T']).abs()
print(f'cyqk mean diff: {d.mean():.6f}')
print(f'cyqk max diff: {d.max():.6f}')
print(f'cyqk <0.001: {(d<0.001).sum()}/{len(m)}')
"
```

**验收标准**：
- 输出行数一致
- cyqk_T mean diff < 0.002
- Top 20 |turnover_resistance| 重叠 ≥ 18/20
- 无系统性偏差（无大批量 cyqk=1.0 或 0.0 的异常）

## 已知待优化项（按优先级）

以下来自文档 §7，Agent 可选择一项或多项推进：

### 优先（影响精度/可用性）

1. **`free_float_shares.parquet` 支持** ✅ 已完成（2026-05-30）  
   Rust 现已加载 `free_float_shares.parquet`（`data.rs::load_free_float_shares`），merge_asof 查 `circulating_capital` + `freeFloatCapital`。输出双口径换手阻力（`turnover_resistance` / `turnover_resistance_free`），与 Python `full_market_canonical_resist.py` 对齐。

2. **结果一致性验证脚本**（~0.5 人日）  
   新建 `scripts/gates/verify_rust_python_alignment.py`，自动运行 Rust + Python 同参数并输出差异统计。

### 可选（改善体验/性能）

3. **T/T-1 窗口复用**（~1 人日）  
   当前 T 和 T-1 窗口各自独立计算 curpdf 矩阵（2× 计算量）。T-1 仅比 T 少最后一天、多前一天，可缓存 T 的 curpdf/turnover，增量计算 T-1。  
   **预期收益**：全市场耗时从 113 秒降至 ~60 秒。  
   **改动点**：`algorithm.rs` 新增增量计算函数，`main.rs` 中复用 T 的计算缓存。

4. **进度条**（~0.5 人日）  
   当前每 500 只打印一行。用 `indicatif` crate 替换为进度条。  
   **改动点**：`Cargo.toml` 新增依赖，`main.rs` 中替换 `eprintln!` 进度汇报。

5. **可移植二进制**（~0.5 人日）  
   当前 `target-cpu=native` 生成的二进制不可移植。改为 `x86-64-v2` 基线或提供多 profile。  
   **改动点**：`.cargo/config.toml`

## 算法改动注意事项

### 三角 PDF（最敏感的代码）

`algorithm.rs::triang_pdf_single` 和 `calc_single_day_curpdf` 必须与 Python 的 `distribution_of_chips.py:52-153` 语义完全一致。改动时重点验证：

- 涨跌停日（`high == low`）：全量集中到 close bin，不是分散
- `c == 0` vs `c == 1` 的退化情形：四种分支不能合并
- 归一化：`pdf / sum(pdf) * vol`，不是 `pdf * vol / sum(pdf)`
- `f64::NAN` 传播：非法参数返回 NaN 而非 panic

### 衰减累积（性能热点）

`algorithm.rs::calc_cumpdf_decay` 是 O(n_days × n_prices) 的双重循环，占比 > 80% 运行时间。改动时：

- 保持扁平 `Vec<f64>`（不要改为 `Vec<Vec<f64>>`）
- 内层循环编译器已自动向量化，不要手动 SIMD（维护成本 > 收益）
- 如需分块（chunk），保持 4-8 元素对齐

### 日期处理（历史 bug 高发区）

parquet 的 `time` 列是 **UTC 午夜** 毫秒（非 CST 午夜）。`date_to_ms()` 必须用 `.and_utc()`。  
**错误示范**：`FixedOffset::east_opt(8*3600).and_local_timezone()` → 窗口错位一天。  
详见文档 §5.1。

## 依赖更新

```bash
# 查看可更新的依赖
cargo update --dry-run

# polars 单独更新（最关键的依赖）
cargo update -p polars

# 更新后必须全量重新编译 + 运行验证
cargo build --release
# ... 跑全市场 CSV 对比 ...
```

polars 版本升级注意事项：
- feature 名称可能变化（如 `dtype-f64` → `dtype-full`）
- API 可能 breaking change，关注 `LazyFrame::scan_parquet` 和 `col()` 签名

## 性能基准

```bash
cd E:/PycharmProjects/OSkhQuant1.3

# 基准测试（window=1000 全市场）
time /e/rust-targets/release/turnover-resist.exe --date 20260604 --window 1000 --sort-by free

# 当前基线：~78 秒（8 核，window=1000，5516 只有效结果，2026-06-04）
# 目标：< 60 秒（结合 T/T-1 窗口复用）
```

## 工程约束

1. **不引入新语言/运行时**：保持纯 Rust，不嵌入 Python/C。
2. **不增加新的重量级依赖**：除非有明确的性能或可用性收益（如 `indicatif`）。
3. **算法改动必须对照 Python 验证**：不接受"应该是等价的"——必须跑全市场 CSV 对比。
4. **不改变输出格式**：CSV 列名、顺序、精度、排序规则必须与 Python 完全一致。当前 18 列（含双口径换手阻力 + 流通股本 + 自由流通股本）。
5. **不删除 `dir_to_stock_code`**：虽然当前未使用，但作为工具函数保留。
6. **不删除 `BarRow` 的 `open`/`amount` 字段**：它们是 parquet schema 的完整映射，即使当前算法未使用。
7. **UTF-8 BOM**：CSV 输出必须带 `\u{FEFF}` 前缀（与 Python `utf-8-sig` 一致）。
8. **不引入 `unsafe` 代码**：所有优化必须通过 safe Rust 实现。

## 参考文件索引

| 文件 | 角色 |
|------|------|
| `qlib_cost/distribution_of_chips.py` | 三角 PDF 的**唯一权威实现**，Rust 必须逐行对齐 |
| `qlib_cost/cyq.py` | CYQK + ChipFactor 的**唯一权威实现** |
| `scripts/data/full_market_canonical_resist.py` | Python 端到端参考，窗口切分 + 布林带的权威行为 |
| `backtest/chip_algorithm.py` | `adapt_columns`（换手率公式）+ `derived_chip_factors` |
| `stock_data/float_shares.parquet` | 流通股本快照（列：stock_code, FloatVolume, TotalVolume, name, updated_at） |
| `stock_data/free_float_shares.parquet` | 历史股本（列：stock_code, m_timetag, freeFloatCapital, circulating_capital, restrict_circulating_capital, total_capital） |
| `stock_data/period=1d/dividend_type=front/symbol=*/data.parquet` | 日线前复权数据（列：time, open, high, low, close, volume, amount） |

## v1.1 同步变更（2026-06-07）

| 变更 | 说明 |
|------|------|
| `--free-float-policy` | Rust/Python 参数完全一致（warn-zero/skip/fail）。缺自由流通股本时 skip 跳过数量对齐 |
| WarnZero capital 修复 | `circ_cap_hist` 从 `circ_cap_t` 改为 `circ_cap_t1`（输出列 `circulating_capital` 准确反映历史值） |
| PyO3 FFI 桥接 | `oskh_core/turnover_resist_bridge.py`；`maturin build --profile release-fast` 构建 wheel |
| 精度验证通过 | `verify_rust_python_alignment.py --free-float-policy warn-zero`：4595 只全 diff=0 |

## v1.2 同步变更（2026-06-16）

| 变更 | 说明 |
|------|------|
| Python 动态窗口 | `batch` 方法在交易日不足 `window+1` 时自动缩短窗口，不再硬性要求 1001 天 |
| Python 目标日期策略 | 新增 `--target-date-policy strict|last-available`，默认 `strict` 与 Rust 对齐 |
| Python 最小交易日过滤 | 上市 <20 天的股票跳过，与 Rust `insufficient_bars` 对齐 |
| Python free_missing 对齐 | 缺失 `freeFloatCapital` 时复用 circ 口径计算，与 Rust `warn-zero` 输出一致 |
| 全市场对齐验证 | 20260616 验证：Python 5521 行 vs Rust 5521 行，核心列完全一致，Top-1000 重叠率 100% |

## 执行注意事项（2026-06-16 复盘）

1. **Rust 计算完成后必须与 Python 全市场对齐验证**  
   不要只相信 Rust 输出。每次更新日线后，同时跑 Python 和 Rust，用上面“与 Python 全市场对齐验证”脚本对比。

2. **Python 多进程必须无缓冲输出**  
   对比验证时若 Python 长时间无输出，不是 Rust 更快，而是 Python stdout 被缓冲。必须加 `PYTHONUNBUFFERED=1`。

3. **行数差异优先查边界策略**  
   Python/Rust 行数不一致时，90% 是边界策略问题（目标日期、动态窗口、最小交易日、free_float 缺失处理），不是算法 bug。

4. **核心列 vs 辅助列差异容忍度不同**  
   `cyqk_T`, `turnover_resistance`, `turnover_resistance_free` 必须完全一致；`bb_middle`/`bb_position` 允许浮点差异。

---

*编码：UTF-8（无 BOM）。最后更新：2026-06-16（v1.2 Python/Rust 全市场对齐 + 执行流程固化）。
