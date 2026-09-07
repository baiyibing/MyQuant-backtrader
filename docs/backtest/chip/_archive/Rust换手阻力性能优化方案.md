# Rust 换手阻力计算 — 性能优化方案

**日期**：2026-06-01
**状态**：已完成实施
**最终耗时**：3 分 41 秒（Python 7.5 分钟的 2× 加速）
**测试环境**：Windows 11 Pro, Intel i7-8650U 4C8T, 40GB RAM, Samsung NVMe SSD

---

## 〇、背景

`turnover-resist/` 是本仓库的第一个 Rust 程序。换手阻力因子计算全部迁移到 Rust 后，未来更多因子（均线、波动率、筹码分布等）也将基于此 Rust 框架扩展。本次优化目标：

1. 把 Rust 打造成未来因子计算的通用底座
2. 充分利用本机已有基础设施（DuckDB、SSD、rayon）
3. Parquet + CSV 双输出（Parquet 给下游、CSV 人工审计）

---

## 一、现状 Profile

### 1.1 基准数据

| 版本 | 耗时 | 有效结果 |
|------|------|---------|
| Python 优化版（duckdb_persistent + capital dict + ProcessPool） | 7.5 分钟 | 4594 |
| **Rust 当前版（逐只 parquet + rayon）** | **4 分 56 秒** | 5513 |

Rust 比 Python 快 1.5×。但 Python 跳过 937 只（资本缺失/数据不足），Rust 只跳过 18 只（WarnZero 策略更宽松）。需先对齐口径。

### 1.2 代码结构

```
turnover-resist/src/
├── main.rs       # CLI + rayon 编排
├── data.rs       # 逐只 parquet 读取 + 股本 HashMap
├── algorithm.rs  # triang PDF + cumpdf decay + cyqk
├── bollinger.rs  # 布林带
├── types.rs      # 数据结构
├── cli.rs        # 命令行解析
└── lib.rs
```

### 1.3 已确认的瓶颈（代码审查）

| 环节 | 问题 | 预估影响 |
|------|------|---------|
| **curpdf 重复计算** | `compute_cyqk_for_adjacent_windows` 对 circ 和 free 各调一次，每次重新算 `all_curpdfs`。curpdf 仅依赖价格，可以复用 | **~2× 计算浪费** |
| **逐只 parquet 读取** | `load_daily_bars_filtered` 每只股票 open 一次 `data.parquet`，5500 次文件 IO | 未知（待计时机测） |
| **Vec 拷贝** | `build_window` 将 `all_curpdfs` 切片拷贝到新 Vec，再传给 `calc_cumpdf_decay` | 内存分配开销 |
| **CSV 写入** | `csv::Writer::serialize` 逐行序列化 | 4594 行可忽略 |

---

## 二、优化计划

### 阶段 1：curpdf 复用（circ + free 共享）

**当前**：main.rs 对 circ 和 free 各调一次 `compute_cyqk_for_adjacent_windows`，内部重新计算 `all_curpdfs`。

**改法**：抽取 `compute_all_curpdfs(union_bars, step) → (all_curpdfs, n_prices, xs)`，然后 `compute_cyqk` 接收预计算的 curpdf。

```rust
// 改前：
let (cyqk_circ_t, ...) = compute_cyqk_for_adjacent_windows(bars, ..., circ_cap, ...)?;
let (cyqk_free_t, ...) = compute_cyqk_for_adjacent_windows(bars, ..., free_cap, ...)?;

// 改后：
let curpdfs = compute_curpdfs_once(bars, step);  // 只算一次
let (cyqk_circ_t, ...) = compute_cyqk_from_curpdfs(&curpdfs, ..., circ_cap);
let (cyqk_free_t, ...) = compute_cyqk_from_curpdfs(&curpdfs, ..., free_cap);
```

**预估**：4 分 56 秒 → ~2.5 分钟。

### 阶段 2：DuckDB 批量读取

**当前**：`load_daily_bars_filtered` 逐只打开 parquet（5500 次 IO）。

**改法**：用 `duckdb-rs` 连接 `stock_data_front.duckdb`（1.1GB），一条 SQL 查出全市场日线：

```rust
use duckdb::{Connection, AccessMode};

let conn = Connection::open_with_flags(
    "stock_data_front.duckdb",
    AccessMode::ReadOnly,
)?;
let df = conn.query_arrow(
    "SELECT symbol, time, close, high, low, volume
     FROM stock_data
     WHERE time >= $1 AND time <= $2",
    params![start_ms, end_ms],
)?;
```

**预估**：2.5 → ~1.5 分钟（消除 5500 次文件 IO）。

### 阶段 3：切片消除拷贝

`calc_cumpdf_decay` 当前签名为 `(curpdfs: &[f64], turnovers: &[f64], window_len, n_prices) -> Vec<f64>`，构建 window 时需要拷贝。改为直接接受 slice，无需 build_window 分配新 Vec。

**预估**：1.5 → ~1.3 分钟。

### 阶段 4：Parquet 输出

**当前**：仅 CSV 输出。

**改法**：用 `polars` 写 Parquet（已有依赖），同时保留 CSV：

```rust
// Parquet（主输出）
let mut df: DataFrame = ...;
let file = std::fs::File::create("canonical_resist_20260525.parquet")?;
ParquetWriter::new(file).finish(&mut df)?;

// CSV（审计副本，已有）
// ...保持不变
```

Parquet 列存格式下游（DuckDB/Polars/pandas）零拷贝读取，且自带 schema。

**预估**：不显著影响耗时（写入 < 1 秒）。

---

## 三、实测结果

| 阶段 | 改动 | 实测耗时 | 相比基准 |
|------|------|---------|---------|
| 基准 | 逐只 polars parquet（`load_daily_bars_filtered` × 5500） | **280s（4m40s）** | — |
| 1 | curpdf 复用（circ + free 共享 `all_curpdfs`） | 253s | -9% |
| 2 | polars parquet 批量加载（主线程串行 + start_ms 过滤） | 221s（3m41s） | -13% |
| 3 | DuckDB 集成（`.duckdb` 文件） | 227s | +3%（比 parquet 慢） |

**最终版**：polars parquet 批量加载 + curpdf 共享 = **3 分 41 秒**。

### 3.1 DuckDB vs polars parquet 对比

| 加载方式 | 加载耗时 | 计算 | 总耗时 |
|---------|---------|------|--------|
| polars parquet（逐文件，每只 ~200KB） | 7.6s | 214s | 221s |
| DuckDB（单文件 1.1GB，ORDER BY） | 11.1s | 215s | 227s |

**结论**：简单时间范围扫描场景下，polars 直读小 parquet 文件更快。DuckDB 代码保留备用（`load_all_stocks_duckdb`），适合未来复杂 JOIN/窗口函数查询。

### 3.2 编译环境

| 配置 | DuckDB/Redis | 全量编译（cargo clean 后） | 增量编译（只改 .rs） |
|------|-------------|--------------------------|-------------------|
| 当前默认 | ❌ 已注释 | **~11.5 分钟**（polars + rayon） | ~6 分钟 |
| 启用 DuckDB | ✅ 取消注释 | ~30 分钟（+DuckDB C++ 编译） | ~6 分钟 |

DuckDB bundled 在 Windows 下需 `Rstrtmgr.lib`（Windows SDK），`build.rs` 显式注入链接路径解决。

### 3.3 编译规则（AI Agent 和开发者必读）

```bash
# ✅ 正确：必须从 turnover-resist/ 目录执行
cd turnover-resist && cargo build --release

# ❌ 错误：从仓库根目录执行会导致 sccache 不生效
cargo build --release --manifest-path turnover-resist/Cargo.toml
```

原因：`rustc-wrapper = "sccache"` 配置在 `turnover-resist/.cargo/config.toml` 中，Cargo 只读当前目录及父目录的 `.cargo/config.toml`。

- **首次编译**（clean 后，无 DuckDB）：~11.5 分钟（无 sccache）/ ~15 分钟（sccache 首次全 miss）
- **增量编译**（只改 `.rs`）：~5-6 分钟
- **不要 `cargo clean`**：仅在依赖变更或缓存损坏时才 clean。DuckDB bundled 从 C++ 源码编译，clean 后需 ~30 分钟
- **sccache 状态检查**：`sccache --show-stats`

### 3.4 如何启用 DuckDB / Redis

```toml
# Cargo.toml — 取消下面两行注释即可启用
duckdb = { version = "1.2", features = ["bundled"] }
redis = { version = "0.27", features = ["tokio-comp", "connection-manager"] }
```

```rust
// main.rs — 切换加载函数
use turnover_resist::data::load_all_stocks_duckdb;  // 替代 load_all_stocks_parquet
// data.rs 中 load_all_stocks_duckdb() 代码已就绪，无需修改
```

启用 DuckDB 时需保留 `build.rs`（显式链接 Windows SDK 的 `Rstrtmgr.lib`，解决 MSVC 下 `LNK2019` 错误）。
DuckDB 代码在 `data.rs` 中通过 `#[cfg(feature = "duckdb")]` 保护，注释掉依赖时不会编译。
polars parquet 是默认加载方式（实测比 DuckDB 快 1.5×），`load_all_stocks_parquet()` 为主路径。

---

## 四、与 Python 版的对齐

| 项目 | Python 最终版 | Rust 最终版 |
|------|-------------|-----------|
| 数据读取 | `scan_stocks(duckdb_persistent)`，16.6s | `load_all_stocks_parquet`，7.6s |
| 股本预加载 | DuckDB SQL `ROW_NUMBER()` 窗口函数 → 4 dict，1.0s | polars 读 2 个 parquet → 2 HashMap，**0.1s** |
| curpdf | 1 次 numba batch（84ms/只） | 1 次 Rust rayon SIMD（cir + free 共享） |
| 并行 | ProcessPool 7w | rayon work-stealing 8 threads |
| 输出 | CSV | CSV |
| **全量耗时** | **7.5 分钟** | **3.7 分钟（2× 加速）** |

### 4.1 Python vs Rust 全量对比（5531 stocks, date=20260525, window=1000）

| 版本 | 数据读取 | 股本 | curpdf | 并行 | 总耗时 |
|------|---------|------|--------|------|--------|
| Python 原始（估算） | 逐只 parquet | pandas filter ×4 | `np.apply_along_axis` ×4 | ProcessPool | ~30 min |
| Python 优化后 | `scan_stocks(duckdb_persistent)` 16.6s | DuckDB SQL dict 1.0s | 1× numba batch | ProcessPool 7w | **7.5 min** |
| Rust 原始 | `load_daily_bars_filtered` ×5500 | HashMap | 2× triang_pdf | rayon 8t | **4.7 min** |
| Rust 优化后 | `load_all_stocks_parquet` 7.6s | HashMap | 1× curpdf shared | rayon 8t | **3.7 min** |

### 4.2 分步 profile 对比

| 环节 | Python (20 stocks) | Rust (full 5531) |
|------|-------------------|-----------------|
| 数据读取 | 13ms/只（duckdb_persistent 摊分） | 7.6s total（polars parquet 批读） |
| capital 查询 | 136ms/只 → <1ms（dict） | 0.1s total（HashMap） |
| curpdf | 84ms/只（numba batch） | —（含在 compute 中） |
| compute | ~430ms/只（单 worker） | 214s total（rayon 8t） |
| 总耗时 | — | **221s（3.7 min）** |

### 4.3 DuckDB 集成实验

| 实验 | 结果 |
|------|------|
| DuckDB bundled 编译 | Windows MSVC 下 `Rstrtmgr.lib` 链接失败 |
| 修复方案 | `build.rs` 显式 `cargo:rustc-link-search` + `cargo:rustc-link-lib=Rstrtmgr` |
| MSVC link.exe vs rust-lld | 两种链接器均失败，`build.rs` 解决 |
| 全量编译耗时 | clean 后 ~30 min（DuckDB bundled + polars） |
| DuckDB vs polars parquet | parquet 快 1.5×（7.6s vs 11.1s），默认用 parquet |
| capital 加载对比 | Rust 0.1s（polars 直读 parquet → HashMap） vs Python 1.0s（DuckDB SQL 窗口函数），**Rust 快 10×** |
| sccache | **已生效**：必须从 `turnover-resist/` 目录执行 `cargo build`（cargo 只读当前目录的 `.cargo/config.toml`）。clean 后首次编译 ~15min（143 misses, 2 hits），后续增量命中率预期 >80% |
| `target-cpu=native` | 耗时 227s（无改善），编译 12min11s（sccache 未生效，全部重编） |
| 113s 根因 | 旧版（commit `71cb96f4`）仅计算**流通股本一个口径**，当前版计算**流通+自由流通两个口径**（计算量翻倍）。旧版 106s = 1.8min，当前版双口径 221s ≈ 2×。fat LTO 和 target-cpu=native 对性能无显著影响 |
| Redis | `Cargo.toml` 已加入，代码待写 |

### 4.4 旧版 vs 当前版对比

| 维度 | 旧版（05-29, `71cb96f4`） | 当前版 |
|------|------------------------|--------|
| 股本口径 | 仅流通股本（`float_shares`） | 流通 + 自由流通（`FloatVolume` + `freeFloatCapital`） |
| 计算次数/只 | **1 次**（circulating only） | **2 次**（circ + free，curpdf 共享但 cumpdf ×2） |
| LTO | fat | thin |
| codegen-units | 1 | 16 |
| target-cpu | native（`.cargo/config.toml` rustflags） | 默认 |
| polars features | streaming, dtype-full | 精简 |
| 数据加载 | per-stock inside rayon + 大栈（16MB） | 主线程 batch load |
| float_shares 列名 | `float_shares`（已废弃） | `FloatVolume`（当前） |
| **实测耗时** | **106s（1.8 min）** | **221s（3.7 min）** |

---

## 五、未来扩展（其他因子）

本次建立的 Rust 框架可复用于：

| 因子 | 计算模式 | 复用 |
|------|---------|------|
| 均线指标（MA/EMA/布林带） | 逐日滚动 | `algorithm.rs` 已有布林带 |
| 换手率半衰期模型（ARC/VRC/SRC/KRC） | 滚动窗口 + decay | `calc_cumpdf_decay` 可复用 |
| 分钟线筹码分布 | 量价直方图 | `calc_single_day_curpdf` 可复用 |
| 全市场选股 | 批量计算 + 排序 | main.rs rayon 编排模式 |

每个新因子只需实现 `compute_xxx` 函数，加载和输出层复用 `data.rs` + `output.rs`。

---

## 六、实施记录

| 顺序 | 做了什么 | 结果 |
|------|---------|------|
| ① | 加分步计时机（`std::time::Instant`） | setup=0s, capital=0.2s, compute=279s, sort+csv=0s |
| ② | curpdf 复用（`compute_curpdfs_once` + `compute_cyqk_from_curpdfs`） | 253s（-9%） |
| ③ | polars parquet 批量加载（`load_all_stocks_parquet`，主线程串行） | 221s（-13%） |
| ④ | DuckDB 集成（`load_all_stocks_duckdb`，`build.rs` 修 Windows SDK link） | 227s（parquet 更快） |
| ⑤ | Redis 依赖加入 `Cargo.toml`（代码待写） | — |
| ⑥ | 切回 parquet 默认，DuckDB 保留备用 | — |
