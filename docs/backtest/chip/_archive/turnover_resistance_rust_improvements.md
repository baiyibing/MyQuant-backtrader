# Rust 换手阻力程序改进建议

> 日期：2026-05-30 | 基准：Rust 0.1.0（当前代码）

对照 Rust 最佳实践和 A 股量化回测软件行业习惯，逐项分析改进方向。

---

## 一、布林带标准差 ddof（P0，精度差异）

**当前代码**（`bollinger.rs:49`）：

```rust
let variance = window.iter().map(|v| (v - mean) * (v - mean)).sum::<f64>() / period as f64;
```

这是**总体标准差**（ddof=0）。但 Python `pandas.rolling(20).std()` 默认 ddof=1（**样本标准差**）。period=20 时差异约 2.6%。

**修复**：
```rust
let variance = window.iter().map(|v| (v - mean) * (v - mean)).sum::<f64>() / (period - 1) as f64;
```

改动 3 个字符，消除与 Python `bb_position` 的无谓差异。A 股量化的行业习惯是用 `ddof=1`（pandas/talib 默认值）。

---

## 二、文档过时（P0，版本不同步）

`turnover_resistance_rust.md` 多处与实际代码不一致：

| 位置 | 文档 | 实际 |
|------|------|------|
| §2.3 数据流 step g | `按 \|turnover_resistance\| 降序排序` | 已改为 `\|turnover_resistance_free\|` |
| §3.6 输出格式 | 14 列 | 18 列（缺 `turnover_free`/`turnover_resistance_free`/`circulating_capital`/`free_float_capital`） |
| §3.6 排序 | `按 \|turnover_resistance\| 降序` | 已改为 `\|turnover_resistance_free\|` 降序 |
| §3.5 `float_shares.parquet` | `float_shares` 列 | 已改为 `FloatVolume` |
| §2.3 数据流 step f | `volume * 100 / float_shares` | 双口径：`circulating_capital` + `freeFloatCapital` |
| §8 项目文件清单 | 行数 187/96/165 等 | 当前各文件实际行数已增长 |

**建议**：每次发布同步更新 §3.6 输出格式表和 §8 文件清单。

---

## 三、并行批处理参数（P1，行业习惯）

当前 `process_one_stock` 读全时段日线再过滤 `time_ms <= target_date_ms`，浪费 I/O（读 20 年数据只用了最近 1000 天）。

**A 股回测软件常见做法**（如 vnpy、zipline）：
- 预加载 → 内存缓存 → 切片。polars 的 `scan_parquet` 已支持 **谓词下推**（predicate pushdown），可以在 parquet 层面只读最后 N 行：

```rust
let df = LazyFrame::scan_parquet(path, ScanArgsParquet::default())?
    .filter(col("time").lt_eq(target_date_ms))
    .collect()?;
```

但 polars 谓词下推对排序文件的效率取决于 parquet 内部的 row group 结构。更可靠的做法是记录文件位置，`read_parquet` 只读尾部 row group。

**建议**：测量 I/O 占比（当前 ~5%），若实测 HDD 下 I/O 超过 20%，考虑实现 parquet 尾部读取优化。

---

## 四、列名蛇形化 vs CamelCase（P2，风格一致）

Rust 社区习惯 snake_case（如 `cyqk_t`、`profit_chip_diff`），但 Rust `OutputRow` 的 serde 序列化会自动把 Rust 的字段名转换为 CSV 列名（默认保持原样）。当前 Rust 字段名用 snake_case，但 miniQMT 原始字段用 camelCase（如 `freeFloatCapital`）。

| Rust 字段名 | 实际 CSV 列名 | miniQMT 原名 | 建议 |
|------------|-------------|-------------|------|
| `free_float_capital` | `free_float_capital` | `freeFloatCapital` | CSV 列名应与 Python 一致 |
| `circulating_capital` | `circulating_capital` | `circulating_capital` | ✅ 一致 |

**当前 Rust 的 `serde` 默认保持 `free_float_capital`（snake_case），Python 输出 `freeFloatCapital`（miniQMT 原名），两者不一致。**

**建议**：Rust 端用 `#[serde(rename = "freeFloatCapital")]` 标注，与 Python 输出完全对齐。

---

## 五、数据源约定（P2，行业习惯）

A 股量化回测的行业习惯是从 `StockDataReader` 统一入口读数据，而不是直接拼 parquet 路径。当前 `data.rs::load_daily_bars` 硬编码了 Hive 分区路径：

```rust
format!("{}/period=1d/dividend_type=front/{}/data.parquet", data_dir, code_dir)
```

**建议**（非必须、当前可接受）：如果将来数据目录结构变化（如 `period=1d` → `period=daily`），改为通过 `StockDataReader` 读或者配置文件约定路径模式。

---

## 六、进度输出（P2，UX 习惯）

当前每 500 只打印一次 `eprintln!`，输出格式为纯文本。A 股回测软件的行业习惯是用 `tqdm`（Python）/ `indicatif`（Rust）风格的进度条：

```
[████████████████░░░░] 4523/5531 (82%) | 342 stocks/s | ETA: 3s
```

**建议**：引入 `indicatif` crate 或改用结构化 JSON 行输出（`{"total": 5531, "done": 4523, "valid": 4510}`），方便 CI 解析。

---

## 七、缺乏灰度处理参数（P2，行业习惯）

A 股回测常见参数：
- `--exclude-st`（排除 ST 股票）
- `--exclude-new`（排除上市不满 N 天的次新股）
- `--min-turnover`（最小换手率过滤）

当前 Rust 程序不做任何过滤，全部股票输出。Python 脚本也如此，所以不算 Rust 特有问题，但作为功能建议值得记录。

---

## 八、T/T-1 窗口复用（P2，性能优化）

当前每只股票 T 和 T-1 窗口各自独立计算 curpdf 矩阵（2× 计算量）。T-1 仅比 T 少最后一天、多前一天。

A 股回测常见的做法是缓存 T 窗口的逐日 curpdf/turnover，T-1 只需增量调整首尾两天的数据。全市场 time 可从 113 秒降至 ~60 秒。

---

## 九、批量窗口计算（P3，高级优化）

当前只有单个截面日期模式。A 股回测软件常见需求是**连续日期的批量计算**（如每天收盘后更新一次）。

如果改成 `--start-date` / `--end-date` 区间模式，可以：
- 预加载日线到内存（5531 只 × 2000 日 ≈ 10M 行，内存约 500MB，可行）
- 滚动窗口复用 curpdf 矩阵（只添加新一天、移除最早一天）
- 全市场 250 个交易日从 250×2min=500min → ~30min

这不是当前必需品（当前是单日截面计算），但值得在设计上预留扩展点。

---

## 十、Unsafe 代码审核结论

当前 **零 `unsafe` 代码**。所有计算均在 safe Rust 范围内，内存安全由编译器保证。 ✅

---

## 优先级汇总

| # | 项 | 优先级 | 估 | 说明 |
|---|-----|:---:|-----|------|
| 1 | 布林带 ddof 修正 | P0 | 1 字符 | `period` → `period - 1`，消除 Python 对齐差异 |
| 2 | 文档同步 | P0 | 0.5h | 输出列数、排序规则、列名更新 |
| 3 | serde rename 对齐列名 | P2 | 5 行 | `free_float_capital` → `freeFloatCapital` |
| 4 | 进度条 | P2 | 0.5d | `indicatif` 或 JSON 行输出 |
| 5 | T/T-1 窗口复用 | P2 | 1d | 113s → 60s |
| 6 | 灰度参数 | P2 | 0.5d | `--exclude-st` / `--exclude-new` |
| 7 | 批量日期 | P3 | 2d | 连续截面计算 |

**最速胜利**：先修 #1（1 字符）+ #3（5 行）+ #2（0.5h），清理完毕后编译生效。
