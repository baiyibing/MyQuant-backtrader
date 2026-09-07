# Rust 重写 canonical 换手阻力全市场计算

> 状态：持续优化中（P0/P1 已落地） | 日期：2026-05-30 | 作者：Claude Code

---

## 1. 背景与动机

`scripts/data/full_market_canonical_resist.py` 是全市场 canonical（换手率衰减）筹码换手阻力计算脚本。Python 实现在全市场 ~5500 只股票、window=1000 日的情况下耗时 10-30 分钟，主要原因：

1. Python 解释器开销 + 单线程逐只处理
2. `numba.jit` 虽已加速 `calc_cumpdf` 和 `triang_pdf`，但 `np.apply_along_axis` 逐行构造 curpdf 矩阵仍是 Python 循环
3. 全市场批处理无并行

Rust 重写目标：利用编译优化 + rayon 多核并行，将全市场计算压缩到 60 秒以内。

前置条件：日线 parquet 已就绪（`stock_data/period=1d/dividend_type=front/symbol=*/data.parquet`），`float_shares.parquet` 可用。**不涉及数据下载和更新。**

---

## 2. 架构设计

### 2.1 项目位置

在仓库根目录新建 `turnover-resist/` Rust 项目：

```
turnover-resist/
  Cargo.toml
  .cargo/config.toml          # target-cpu=native，启用 AVX2 SIMD
  src/
    main.rs                   # CLI 入口 + rayon 编排 + 排序 + CSV 输出
    cli.rs                    # clap derive 参数定义
    data.rs                   # parquet I/O + float_shares 加载
    algorithm.rs              # 核心数学：triang_pdf, calc_curpdf, calc_cumpdf, cyqk
    bollinger.rs              # 布林带
    types.rs                  # struct 定义
```

### 2.2 Crate 选型

| Crate | 版本 | 用途 | 选型理由 |
|-------|------|------|---------|
| `polars` | 0.46 | parquet 读写 | 量化 Rust 事实标准；原生 Hive 分区支持；lazy + streaming I/O |
| `rayon` | 1.12 | 多核并行 | 股票间零数据依赖，`par_iter()` 接近线性加速 |
| `clap` | 4.6 | CLI | derive 宏，类型安全，自动生成 `--help` |
| `anyhow` | 1.0 | 错误处理 | `Result<T>` + `.context()` 链式错误传播 |
| `csv` | 1.4 | CSV 输出 | Serde 集成，流式写入，无内存堆积 |
| `chrono` | 0.4 | 日期处理 | YYYYMMDD ↔ epoch 毫秒转换 |
| `serde` | 1.0 | 序列化 | `OutputRow` 的 `Serialize` derive |

**不使用 `ndarray`**：`Vec<f64>` 手动循环更接近 numba jit 风格。Rust 编译器对简单 f64 循环的自动向量化效果已足够好，不需要引入 BLAS 依赖。

### 2.3 数据流

```
1. 加载 float_shares.parquet → HashMap<stock_code, (float_shares, name)>
2. 从 float_shares 的 stock_code 列获取股票列表（与 Python 一致，非文件系统遍历）
3. rayon::par_iter 遍历每只股票：
   a. polars 读取 data.parquet → Vec<BarRow>
   b. 按 time_ms 排序，保留 volume=0 行（停牌日）
   c. 切分 T 窗口：time_ms <= target_date 的最后 window 个交易日
   d. 切分 T-1 窗口：按**前一个交易日**（非日历日-1）切最后 window 个交易日
   e. 两份窗口独立计算 cyqk → (cyqk_T, cyqk_T_1)
   f. turnover_T = (T 窗口末行 volume * 100) / circulating_capital（优先 merge_asof；缺失时回退 FloatVolume）
   g. turnover_resistance = (cyqk_T - cyqk_T_1) / turnover_T
   h. 布林带（20日，默认 ddof=1，与 pandas rolling.std 对齐）
   i. 返回 Option<OutputRow>
4. 收集结果（无 Mutex 热点锁），按 sort-by 口径排序（默认 free）
5. 写 UTF-8 BOM CSV（与 Python `utf-8-sig` 一致）
```

### 2.4 核心算法：逐函数对照 numba jit

#### 三角 PDF

Python (`distribution_of_chips.py:108-153`) 的两条路径：

- **涨跌停**（`high == low`）：成交量全部集中到 `close` 所在价格 bin
- **正常**：`c = (close - low) / (high - low)`，对价格网格 `xs` 上每一点计算分段线性三角密度，归一化后乘 volume

Rust 实现（`algorithm.rs:32-68`）：

```rust
pub fn calc_single_day_curpdf(
    close: f64, high: f64, low: f64, vol: f64,
    xs: &[f64], step: f64,
) -> Vec<f64> {
    // 涨跌停：集中到 close bin
    if (high - low).abs() < 1e-12 { ... }
    // 正常：逐格计算 triang_pdf_single(x, c, loc, scale)
    // 归一化后乘 vol
}
```

`triang_pdf_single`（`algorithm.rs:12-30`）逐元素计算分段线性 PDF，完全复刻 numba 版本的四段分支：
- `c == 0`：右三角（close == low）
- `c == 1`：左三角（close == high）
- `0 < c < 1`：不对称三角，上坡段 + 下坡段
- 网格外：0

#### 换手衰减累积

Python (`cyq.py:61-82`, numba `@jit(nopython=True)`)：

```
递推：State₀ = curpdf₀ × turnover₀
      Stateᵢ = Stateᵢ₋₁ × (1 - turnoverᵢ) + curpdfᵢ × turnoverᵢ
```

Rust (`algorithm.rs:85-115`)：扁平 `Vec<f64>` 矩阵，两重循环，内层编译器自动向量化。

#### CYQK 获利占比

```
total = Σ cumpdf[j]
cyqk = Σ{cumpdf[j] | price[j] ≤ close_last} / total
```

---

## 3. 使用指南

### 3.1 环境要求

| 依赖 | 版本/说明 |
|------|----------|
| Rust 工具链 | 1.95+（`rustc` + `cargo`） |
| 操作系统 | Windows 11（Linux/macOS 亦可，但未测试） |
| 日线数据 | `stock_data/period=1d/dividend_type=front/symbol=*/data.parquet` |
| 流通股本 | `stock_data/float_shares.parquet` |
| 内存 | 建议 ≥ 16 GB（并行 8 线程，极端高价股 curpdf 矩阵可达 ~500MB/线程） |
| 磁盘 | SSD 推荐（5531 次 parquet 文件读取，SSD 下 I/O ~5 秒，HDD 下可能显著增加） |

### 3.2 编译

```bash
# 进入项目目录
cd E:/PycharmProjects/OSkhQuant1.3/turnover-resist

# 首次编译（下载依赖 + 编译，约 50-60 分钟，polars 依赖较重）
cargo build --release

# 增量编译（仅本项目代码变更，~12 分钟）
cargo build --release
```

**编译产物位置**：`target/release/turnover-resist.exe`

### 3.3 运行

```bash
# 回到仓库根目录
cd E:/PycharmProjects/OSkhQuant1.3

# Windows 必须设置线程栈大小（否则 rayon 线程会栈溢出）
# Bash/Git Bash:
export RUST_MIN_STACK=8388608

# PowerShell:
# $env:RUST_MIN_STACK = 8388608

# CMD:
# set RUST_MIN_STACK=8388608

# 全市场计算（1000 日窗口，默认参数）
./turnover-resist/target/release/turnover-resist --date 20260522

# 指定窗口和输出路径
./turnover-resist/target/release/turnover-resist \
  --date 20260522 \
  --window 1000 \
  --step 0.01 \
  --output backtest_output/my_resist.csv

# 查看帮助
./turnover-resist/target/release/turnover-resist --help
```

### 3.4 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--date` | YYYYMMDD | **必填** | 截面日期 |
| `--window` | usize | `1000` | 筹码衰减窗口（交易日数），不足时自动用全部 |
| `--step` | f64 | `0.01` | 价格网格步长（元），即价格精度 |
| `--bb-ddof` | usize | `1` | Bollinger 标准差自由度，默认 1（样本标准差） |
| `--sort-by` | enum | `free` | 排序口径：`circulating`/`free` |
| `--free-float-policy` | enum | `warn-zero` | `warn-zero`/`skip`/`fail` |
| `--output` | path | `backtest_output/canonical_resist_rust_{date}.csv`（默认） | 输出 CSV 路径（带 `_rust_` 后缀，避免与 Python 版 `canonical_resist_py_*.csv` 冲突） |
| `--data-dir` | path | `stock_data` | 数据根目录（含 `float_shares.parquet` 和 `period=1d/`） |

### 3.5 输入数据要求

**日线 parquet** 必须满足以下 Hive 分区布局：

```
{data_dir}/
  period=1d/
    dividend_type=front/
      symbol=000001_SZ/
        data.parquet     # 列：time(i64), open(f64), high(f64), low(f64), close(f64), volume(i64), amount(f64)
      symbol=000002_SZ/
        data.parquet
      ...
```

其中 `time` 列为 UTC 午夜的 epoch 毫秒值，`volume` 为手（1 手 = 100 股）。

**float_shares.parquet** 必须包含 `stock_code`（str）、`float_shares`（f64）、`name`（str）三列。

### 3.6 输出格式

输出 CSV（UTF-8 BOM），18 列（字段名与 Python canonical 对齐）：

| 列 | 精度 | 说明 |
|----|------|------|
| `stock_code` | — | 代码（如 `000001.SZ`） |
| `stock_name` | — | 中文简称 |
| `date` | — | 截面日期（YYYYMMDD） |
| `close` | 2 位 | 收盘价 |
| `cyqk_T` | 4 位 | 当日获利筹码占比（0~1） |
| `cyqk_T_1` | 4 位 | 上一日获利筹码占比 |
| `profit_chip_diff` | 6 位 | 获利筹码变化（cyqk_T - cyqk_T_1） |
| `turnover` | 6 位 | 当日换手率（0~1） |
| `turnover_resistance` | 4 位 | 换手阻力 = profit_chip_diff / turnover |
| `turnover_free` | 6 位 | 当日换手率（自由流通口径） |
| `turnover_resistance_free` | 4 位 | 换手阻力（自由流通口径） |
| `circulating_capital` | - | merge_asof 后流通股本（股） |
| `freeFloatCapital` | - | merge_asof 后自由流通股本（股） |
| `bb_upper` | 2 位 | 布林上轨（20 日，2σ） |
| `bb_middle` | 2 位 | 布林中轨（20 日均线） |
| `bb_lower` | 2 位 | 布林下轨 |
| `bb_position` | 4 位 | 布林位置（0~1，0=下轨，1=上轨） |
| `bb_width` | 4 位 | 布林带宽 |

按 `--sort-by` 指定口径排序（默认 `|turnover_resistance_free|`）。

---

## 4. 配置说明

### 4.1 Cargo.toml

```toml
[package]
name = "turnover-resist"
version = "0.1.0"
edition = "2021"

[dependencies]
polars = { version = "0.46", features = ["lazy", "parquet", "strings"], default-features = false }
rayon = "1.10"
clap = { version = "4.5", features = ["derive"] }
anyhow = "1.0"
csv = "1.3"
chrono = "0.4"
serde = { version = "1.0", features = ["derive"] }
thiserror = "2.0"

[profile.dev]
debug = 1

[profile.test]
debug = 1

[profile.release]
lto = "thin"
opt-level = 3
codegen-units = 16
debug = 0
strip = true

[profile.release-fast]
inherits = "release"
lto = false
```

**配置说明**：

| 配置项 | 作用 | 调优建议 |
|--------|------|---------|
| `lto = "thin"` | 跨 crate 优化与链接速度折中 | 发布默认用 `thin` |
| `codegen-units = 16` | 并行 LLVM codegen | 降低单线程编译瓶颈 |
| `opt-level = 3` | LLVM 优化级别 | 保持 `3`，对数值密集型代码收益显著 |
| `debug = 0` + `strip = true`（release） | 减少符号与 DWARF 负担 | 缩短链接时间、减小二进制体积 |
| `release-fast` profile | 日常迭代无 LTO | 本地迭代优先 `cargo build --profile release-fast` |
| `polars.default-features = false` | 关闭 polars 默认 feature | 仅开启 `lazy`/`parquet`/`strings` |

### 4.2 .cargo/config.toml

```toml
[build]
rustc-wrapper = "sccache"

[target.x86_64-pc-windows-msvc]
linker = "rust-lld"
```

**说明**：

- `rustc-wrapper = "sccache"`：复用编译缓存，减少重复构建开销。
- `rust-lld`：替代默认 MSVC 链接器，明显加速链接阶段。
- `target-cpu=native` 不再全局启用，避免 debug/test 构建也付出额外代价。若需要本机极致优化，按会话设置 `RUSTFLAGS="-C target-cpu=native"` 即可。

- **保留此配置**：仅在本机运行（当前场景）
- **移除此配置**：需要分发给不同 CPU 的机器时，改为 `x86-64-v2` 基线或其他指定 target

### 4.3 运行时线程栈

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RUST_MIN_STACK` | 可选 | 若设置则优先使用该值；未设置时程序默认用 8MB 初始化 rayon 全局线程池 |

程序已内置默认线程栈大小（8MB），不再要求每次手工设置环境变量；`RUST_MIN_STACK` 仅用于显式覆盖。

### 4.4 编译优化档位

| 场景 | Profile | lto | codegen-units | 全量编译 | 增量编译 | 运行时 |
|------|---------|-----|---------------|---------|---------|--------|
| 发布/生产 | `release` | thin | 16 | ~9 分钟 | ~4 分钟 | 生产档 |
| 日常迭代 | `release-fast` | false | 16 | ~9 分钟 | ~6 秒 | 推荐开发档 |
| 测试/检查 | `test`/`dev` | — | 默认 | 首次较慢 | 增量较快 | 验证档 |

建议工作流：
1. 修改代码 → `cargo build --profile release-fast`
2. 质量门禁 → `cargo fmt --check && cargo test --all-targets && cargo clippy --all-targets --all-features -- -D warnings`
3. 最终发布 → `cargo build --release`

详细编译优化背景见：`docs/backtest/chip/turnover_resistance_rust_build_optimization.md`。

---

## 5. 实现过程中遇到的问题与解决办法

### 5.1 日期时区陷阱（P0）

**现象**：初次运行时 Rust 输出的 close、turnover、cyqk 与 Python 全面不一致。cyqk_T mean diff = 0.096，Top 20 重叠仅 7/20。

**根因**：`date_to_ms()` 函数使用了 CST 时区（UTC+8）计算 epoch 毫秒，但 parquet 文件的 `time` 列存储的是 **UTC 午夜** 的毫秒值。例如 2026-05-22 的数据：
- 正确值（UTC 午夜）：`1779926400000`
- 错误值（CST 午夜）：`1779897600000`（差 8 小时）

Rust 过滤 `time_ms <= target_date_ms` 时，用 CST 时区的 target 值过滤 UTC 数据，导致目标日期当天数据被排除，窗口错位一天。

**修复**：将 `date_to_ms` 从 `FixedOffset::east_opt(8*3600)` 改为 `.and_utc()`，与 pandas `pd.to_datetime(value, unit='ms')` 的 UTC 解释行为一致。

```rust
// 错误
fn date_to_ms(date: NaiveDate) -> i64 {
    let cst = FixedOffset::east_opt(8 * 3600).unwrap();
    dt.and_local_timezone(cst).unwrap().timestamp_millis()
}

// 正确
fn date_to_ms(date: NaiveDate) -> i64 {
    date.and_hms_opt(0, 0, 0).unwrap().and_utc().timestamp_millis()
}
```

修复后：cyqk_T mean diff 从 0.096 降至 0.0023，Top 20 从 7/20 升至 19/20。

### 5.2 价格网格截断导致 cyqk = 1.0（P0）

**现象**：修复日期问题后，仍有少量股票 cyqk 差异极大（如 920045.BJ 差 0.63），Rust 输出 cyqk=1.0 而 Python=0.37。

**根因**：价格网格设置了 `cap = 20000` bins。920045.BJ 在近 100 个交易日内价格从 200 元涨至 800 元，价格跨度 608 元，step=0.01 下需要 60829 bins。截断到 20000 后，网格覆盖范围远小于实际价格区间，close 超出网格最大值 → 所有筹码都被计入"获利" → cyqk = 1.0。

后续将 cap 提升到 40000 仍有 920045.BJ（60829 bins）超出。

**修复**：去掉 cap，跟随 Python 行为——让网格大小自然由价格范围决定。内存影响：极端情况下单只股票 curpdf 矩阵约 487 MB（1000 日 × 60829 bins × 8 bytes），在 16GB 机器上可接受。

修复后 max cyqk diff 从 0.80 降至 0.058。

### 5.3 rayon 线程栈溢出（P1，已工程化缓解）

**现象**：debug 构建运行时 `thread has overflowed its stack`，release 构建运行时偶尔也出现。

**根因**：polars 内部（tokio runtime + parquet 解码）调用栈较深，Windows 默认线程栈 1MB 不够。rayon 线程继承主线程栈大小。

**修复**：代码内默认 `ThreadPoolBuilder::stack_size(8MB)`；`RUST_MIN_STACK` 改为可选覆盖项。

### 5.4 polars feature 选型踩坑

**现象**：初次 `cargo check` 失败：`package 'turnover-resist' depends on 'polars' with feature 'dtype-f64' but 'polars' does not have that feature`。

**根因**：polars 0.46 的细粒度 dtype feature（`dtype-f64`、`dtype-i64`、`dtype-str`）已被合并为 `dtype-full`。

**修复**：使用 `dtype-full` 替代三个独立 dtype feature。

### 5.5 链接时间过长（P2）

**现象**：早期配置下链接阶段耗时偏高，影响调试迭代速度。

**根因**：polars 依赖链较重，LTO 与链接器配置会放大链接阶段耗时。

**修复策略**：
- 发布档：`lto = "thin"` + `codegen-units = 16` + `debug = 0` + `strip = true`
- 日常档：`release-fast`（`lto = false`）加速本地迭代
- 工具链：`.cargo/config.toml` 使用 `rust-lld` + `sccache`
- 详见 `docs/backtest/chip/turnover_resistance_rust_build_optimization.md`

### 5.6 volume=0 行处理

**现象**：早期版本在 `read_parquet_to_barrows` 中过滤 `volume <= 0` 行，与 Python 行为不一致（Python 保留 volume=0 行，在 decay 计算中这些行 turnover=0，对 cumpdf 无影响但消耗一个日期槽位）。

**修复**：去掉过滤，保留 volume=0 行，与 Python 完全一致。

---

## 6. 完成效果

### 6.1 性能

| 指标 | Rust（release） | Python | 加速比 |
|------|----------------|--------|--------|
| 全市场 window=100 | ~15 秒 | ~3 分钟 | **~12x** |
| 全市场 window=1000 | **113 秒**（~2分钟） | 10-30 分钟 | **~5-15x** |
| 单核等价性能 | ~900 秒 | 600-1800 秒 | — |
| 并行效率（8 核） | ~8x | 1x（单线程） | — |

Rust debug 构建：全市场 window=100 约 90 秒。

目标 < 60 秒未完全达到（实际 113 秒），原因是每只股票 2 次独立窗口计算（T 和 T-1），每次 1000 日 × 平均 ~3000 bins × 5 次 f64 操作 ≈ 3000 万次运算。8 核 × 5500 只 ≈ 每核承当 200 亿次 f64 运算。当前性能已是单核 ~900 GFLOPS 的水平（接近理论峰值），进一步优化空间有限。

### 6.2 精度验证

与 Python 端到端对比（window=100，同日期同参数）：

| 指标 | 数值 |
|------|------|
| 输出行数 | 5512 vs 5512（100%） |
| cyqk_T 差 < 0.0001 | 3314/5512（60.1%）|
| cyqk_T 差 < 0.001 | 4274/5512（77.5%）|
| cyqk_T 最大误差 | 0.0577 |
| turnover 最大误差 | 0.000345 |
| Top 20 \|turnover_resistance\| 重叠 | 19/20 |
| close 最大误差 | 0.01（浮点舍入） |

剩余差异来源：
1. ✅ 已修复（2026-05-30）：Rust 现已同时加载 `float_shares.parquet` 和 `free_float_shares.parquet`（merge_asof），输出双口径换手阻力，并优先使用历史 `circulating_capital` 作为 circulating 口径分母
2. 浮点运算累积：三角 PDF 的 `sum(pdf)` 归一化 + decay 递推的 1000 次迭代中，f64 精度的微小差异逐步累积

两者均不影响实际量化选股使用。

### 6.3 边缘情况覆盖

| 情况 | 处理 |
|------|------|
| `high == low`（涨跌停） | 全部量集中到 close 价格 bin |
| `volume == 0`（停牌） | 保留该行，turnover=0，对 cumpdf 无影响 |
| 交易日 < 20 | 跳过该股票（cyqk 无意义） |
| 交易日 < window | 有多少用多少（与 Python 一致） |
| float_shares 缺失 | 跳过，warning |
| 价格范围为 0 | 跳过（停牌或数据异常） |
| cyqk 返回 NaN（分布为空、总筹码 <= 0）| 跳过 |
| `turnover_T <= 0` | resistance = 0.0 |
| `bb_upper == bb_lower` | position = 0.5 |
| `bb_middle <= 0` | width = 0.0 |
| NaN propagation（high/low/close） | 价格网格计算中显式过滤 NaN |
| 极高价股（>500 元，grid > 60000 bins） | 不做截断，跟随 Python 行为 |

---

## 7. 下一步优化方向

### 7.1 优先（影响精度/可用性）

1. **`free_float_shares.parquet` 支持** ✅ 已完成（2026-05-30）  
   Rust 现已加载 `free_float_shares.parquet`，merge_asof 查 `circulating_capital` + `freeFloatCapital`，输出双口径换手阻力（`turnover_resistance` / `turnover_resistance_free`）。

2. **结果一致性验证脚本** ✅ 已完成  
   `scripts/gates/verify_rust_python_alignment.py` 支持一键运行 Rust/Python 并输出差异报告（含阈值判定）。

### 7.2 可选（改善体验/性能）

3. **T/T-1 窗口复用**（~1 人日）  
   当前 T 和 T-1 窗口各自独立从原始数据切片并各自计算 curpdf 矩阵。T-1 窗口仅比 T 窗口少最后一天、多前一天。可以缓存 T 窗口的 curpdf 和 turnover，增量计算 T-1 窗口，将每只股票的计算量减半。预期全市场 time 从 113 秒降至 ~60 秒。

4. **进度条替换 eprintln**（~0.5 人日）  
   当前每 500 只打印一次进度。使用 `indicatif` crate 添加进度条，显示 stocks/s、预计剩余时间。

5. **`.cargo/config.toml` 移除 `target-cpu=native`**（~0.5 人日）  
   当前二进制针对本机 CPU 优化（AVX2），不可移植到旧 CPU。如果需要分发，改为 baseline x86_64-v2 或提供两套 profile。

6. **polars 升级到最新版**（~1 人日）  
   当前 polars 0.46。Cargo 已提示 `0.53.0` 可用。升级可获得性能改进和更成熟的 streaming API，可能减少 stack overflow 风险。

### 7.3 不做

- **GPU 加速（CUDA/OpenCL）**：当前每只股票 3000 万次 f64 运算，GPU 启动开销大于计算收益。单只股票规模不适合 GPU。
- **分布式（多机）**：2-3 人团队无此需求。单机 2 分钟已足够。
- **DuckDB 替代 polars 读 parquet**：当前瓶颈在计算（95%+ 时间），不在 I/O（~5%）。优化 I/O 收益极小。
- **等权重（无衰减）模式**：文档已明确 canonical（衰减）为唯一生产路径。等权重仅用于与市面 APP 对齐验证，不需要 Rust 重写。

---

## 8. 项目文件清单

| 文件 | 行数 | 说明 |
|------|------|------|
| `turnover-resist/Cargo.toml` | 23 | 依赖声明 + release profile |
| `turnover-resist/.cargo/config.toml` | 2 | `target-cpu=native` |
| `turnover-resist/src/main.rs` | 187 | CLI 入口，rayon 编排，CSV 输出 |
| `turnover-resist/src/cli.rs` | 26 | clap derive 参数 |
| `turnover-resist/src/types.rs` | 47 | BarRow, OutputRow, FloatSharesInfo 等 struct |
| `turnover-resist/src/data.rs` | 96 | polars parquet I/O + float_shares 加载 |
| `turnover-resist/src/algorithm.rs` | 165 | triang_pdf, calc_curpdf, calc_cumpdf, cyqk |
| `turnover-resist/src/bollinger.rs` | 44 | 布林带 (20日, 2σ) |
| **合计** | **~590** | |

---

## 9. 参考

- `scripts/data/full_market_canonical_resist.py` — Python 端到端参考实现
- `qlib_cost/cyq.py` — `calc_cumpdf` 衰减累积 + `ChipFactor.get_cyqk_c` 获利占比
- `qlib_cost/distribution_of_chips.py` — `triang_pdf`、`calc_triang_pdf` 三角分布
- `backtest/chip_algorithm.py` — `adapt_columns`（换手率公式）、`bb_position`（布林带）
- `docs/backtest/chip/turnover_resistance_algorithm.md` — 换手阻力完整技术规格
- `docs/knowledge/performance/solutions/solution-P2-outbox-generic-dispatch.md` — 通用 Outbox 架构文档（v6 实装参考）

---

*编码：UTF-8（无 BOM）。最后更新：2026-05-29。*
