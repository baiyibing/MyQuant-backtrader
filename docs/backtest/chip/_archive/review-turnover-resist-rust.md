# turnover-resist Rust 实现评审报告

> **Date**: 2026-05-30
> **评审对象**: `turnover-resist/` (Cargo.toml + 5 个源文件, ~590 行)
> **参照**: Rust 最佳实践 + 中国 A 股量化回测行业惯例（vnpy/backtrader/qlib/聚宽/米筐）

---

## 0) 总体评价

代码质量高：模块划分清晰（cli/data/algorithm/bollinger/types/main），注释详尽（特别是日期时区陷阱和价格网格截断的 P0 修复记录），rayon 并行编排合理。113 秒完成全市场 5500 只股票 × 1000 日窗口的计算，性能优秀。

以下按 **Rust 工程实践** 和 **A 股行业对齐** 两个维度提出改进建议。

---

## 一、Rust 工程实践问题

### P0 — 必须修复

#### 1.1 `Mutex<Vec>` 反模式（main.rs:230-263）

当前使用 `Mutex<Vec<OutputRow>>` + `par_iter().for_each()` 收集结果。这是 rayon 的反模式——锁竞争会限制并行扩展性。

```rust
// 当前（有锁竞争）
let results: Mutex<Vec<OutputRow>> = Mutex::new(Vec::with_capacity(codes.len()));
codes.par_iter().for_each(|code| {
    match process_one_stock(code, &ctx, info, ff_info) {
        Some(row) => { results.lock().unwrap().push(row); }
        None => { skipped.fetch_add(1, Ordering::Relaxed); }
    }
});
```

**修复**：使用 rayon 的 `filter_map` + `collect`，零锁竞争：

```rust
let results: Vec<OutputRow> = codes
    .par_iter()
    .filter_map(|code| {
        let info = fs_map.get(code)?;
        let ff_info = ff_map.as_ref().and_then(|m| m.get(code));
        process_one_stock(code, &ctx, info, ff_info)
    })
    .collect();
```

进度汇报和跳过计数可改用 `AtomicU64` 计数器 + `enumerate()` 或 `inspect()`。

#### 1.2 T-1 窗口不必要的 clone（main.rs:89-101）

```rust
let t1_window: Vec<BarRow> = t1_bars[t1_start..].iter().map(|&r| r.clone()).collect();
```

`compute_cyqk_for_window` 接收 `&[BarRow]`，不需要 owned `Vec`。当前代码对 T-1 窗口的所有 BarRow 做了深拷贝（每只股票 ~1000 次 clone），完全多余。

**修复**：先过滤再切片，直接传引用：

```rust
let t1_end = bars.partition_point(|b| b.time_ms <= ctx.target_date_prev_ms);
let t1_start = if t1_end > ctx.window { t1_end - ctx.window } else { 0 };
let t1_window = &bars[t1_start..t1_end];
let cyqk_circ_t_1 = compute_cyqk_for_window(t1_window, circ_cap, ctx.step)?;
```

这样 T-1 窗口也是 `&[BarRow]`，零分配。同时消除了 T-1 窗口的冗余 `filter` 遍历（当前遍历了两次 bars：一次 filter 到 `t1_bars`，一次 slice_window）。

### P1 — 强烈建议

#### 1.3 `load_daily_bars` 读取全量历史（data.rs:189）

每只股票读取 parquet 文件的全部历史行（可能 5000+ 行），然后在 main.rs 中 filter 到 target_date 之前。window=1000 时，大部分数据被丢弃。

**修复**：在 polars lazy 层做 filter + tail，减少 I/O 和内存：

```rust
pub fn load_daily_bars(data_dir: &str, code_dir: &str, target_ms: i64, window: usize) -> Result<Vec<BarRow>> {
    let df = LazyFrame::scan_parquet(...)?
        .filter(col("time").lt_eq(lit(target_ms)))
        .sort("time", Default::default())
        .tail(Some((window + 20) as u32))  // 多取 20 行留余量
        .collect()?;
    // ...
}
```

预期收益：对于上市 10 年（~2500 交易日）的股票，I/O 量减少约 60%。

#### 1.4 `calc_single_day_curpdf` 每次分配新 Vec（algorithm.rs:74）

热路径中每只股票 1000 天 × 5500 只 = 550 万次 `vec![0.0f64; n]` 分配。`n_prices` 在同一窗口内不变，可以复用缓冲区。

**修复**：将 `compute_cyqk_for_window` 改为预分配 curpdfs 矩阵，逐日就地填充：

```rust
let mut curpdfs = vec![0.0f64; n_days * n_prices];
for (i, bar) in bars.iter().enumerate() {
    let row = &mut curpdfs[i * n_prices..(i + 1) * n_prices];
    calc_single_day_curpdf_into(bar, &xs, step, row);  // 写入预分配的行
}
```

预期收益：减少 550 万次堆分配，对极端高价股（60000+ bins）尤为明显。

#### 1.5 缺少单元测试（`#[cfg(test)]`）

核心算法函数（`triang_pdf_single`、`calc_cumpdf_decay`、`calc_cyqk`、`bollinger_bands`）无单元测试。文档中提到与 Python 对齐验证，但这是端到端验证，不能替代单元测试。

**建议**：在 `algorithm.rs` 和 `bollinger.rs` 底部添加 `#[cfg(test)]` 模块：

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_triang_pdf_symmetric() {
        // c=0.5 时三角分布应对称
        let pdf = triang_pdf_single(0.5, 0.5, 0.0, 1.0, 1.0, 1.0);
        assert!((pdf - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_cumpdf_single_day() {
        // 单日衰减：cumpdf = curpdf * turnover
        let curpdfs = vec![1.0, 2.0, 3.0];
        let cumpdf = calc_cumpdf_decay(&curpdfs, &[0.5], 1, 3);
        assert_eq!(cumpdf, vec![0.5, 1.0, 1.5]);
    }
}
```

#### 1.6 `unwrap()` 在并行上下文中（main.rs:249, 266）

`results.lock().unwrap()` — 如果某个 rayon 线程 panic 导致 Mutex 中毒，`unwrap()` 会再次 panic。在并行计算 5500 只股票的场景下，一只股票的异常不应导致全部崩溃。

**修复**：使用 `if let Ok(mut r) = results.lock()` 或在 `process_one_stock` 内部捕获 panic（`std::panic::catch_unwind`）。

### P2 — 建议改进

#### 1.7 `ThreadPoolBuilder` 显式配置

当前依赖 `RUST_MIN_STACK` 环境变量防止栈溢出。如果用户忘记设置，程序会崩溃且错误信息不友好。

**修复**：在 main 中显式构建线程池：

```rust
rayon::ThreadPoolBuilder::new()
    .stack_size(8 * 1024 * 1024)  // 8MB
    .build_global()
    .expect("failed to build rayon thread pool");
```

这样 `RUST_MIN_STACK` 不再是必需的。

#### 1.8 进度汇报改进

当前每 500 只打印一次进度（eprintln）。建议使用 `indicatif` crate 的进度条，或至少改为百分比：

```rust
if n % 500 == 0 || n == total {
    eprintln!("  [{}/{}] {:.1}% done, valid={}, skipped={}",
        n, total, n as f64 / total as f64 * 100.0, valid, sk);
}
```

#### 1.9 排序字段不一致

main.rs:281 按 `|turnover_resistance_free|` 排序，但 Top 20 打印（main.rs:316-323）显示的是 `turnover_resistance`（流通股本口径）。应统一或同时显示两个口径。

---

## 二、A 股行业对齐问题

### P1 — 强烈建议

#### 2.1 涨跌停判定过于简化

当前用 `(high - low).abs() < 1e-12` 检测一字板。这在以下场景不准确：

| 场景 | 当前行为 | 正确行为 |
|------|---------|---------|
| 涨停开盘→打开→封回（high > low, close == high） | 正常三角分布 | 应识别为涨停日，筹码集中在 close |
| 跌停开盘→打开→封回（high > low, close == low） | 正常三角分布 | 应识别为跌停日，筹码集中在 close |
| 一字涨停（high == low == close） | 集中到 close bin ✅ | 正确 |

**A 股行业惯例**（vnpy/聚宽/米筐）：涨跌停日筹码应集中在涨停/跌停价位，不论 high 是否等于 low。

**建议修复**：

```rust
// 涨跌停检测：不仅看 high==low，还要看 close 是否触及涨跌停价
let limit_up = close >= high && (close - low) / close > 0.05;  // 近似判断
let limit_down = close <= low && (high - close) / close > 0.05;

if (high - low).abs() < 1e-12 || limit_up || limit_down {
    // 集中到 close bin
}
```

更精确的做法是引入涨跌停价计算（根据股票代码判断板块：主板 10%、创业板/科创板 20%、北交所 30%、ST 5%）。

#### 2.2 板块涨跌幅差异未处理

A 股不同板块的涨跌停幅度不同：

| 板块 | 代码前缀 | 涨跌停幅度 | 当前处理 |
|------|---------|-----------|---------|
| 主板（沪） | 600/601/603/605 | 10% | 未区分 |
| 主板（深） | 000/001/002/003 | 10% | 未区分 |
| 创业板 | 300/301 | 20% | 未区分 |
| 科创板 | 688/689 | 20% | 未区分 |
| 北交所 | 8/4/920 | 30% | 未区分 |
| ST/*ST | 带 ST 标记 | 5% | 未区分 |

这影响两个地方：
1. **筹码分布**：涨跌停日的筹码集中位置
2. **布林带**：极端涨跌幅会拉大布林带宽度

**建议**：添加 `stock_category(code: &str) -> StockCategory` 函数，返回板块类型和涨跌停幅度。在筹码分布计算中使用板块信息。

#### 2.3 布林带标准差 ddof 不一致（bollinger.rs:46-48）

代码注释已指出：Rust 用 ddof=0（总体标准差），Python pandas 用 ddof=1（样本标准差）。period=20 时差异约 2.6%。

**A 股行业惯例**：通达信/同花顺/聚宽/米筐的布林带均使用 **ddof=1**（样本标准差）。

**修复**：

```rust
let variance: f64 = window.iter()
    .map(|v| (v - mean) * (v - mean))
    .sum::<f64>() / (period - 1) as f64;  // ddof=1，与 pandas/行业一致
```

#### 2.4 停牌/节假日未区分

当前保留 volume=0 行（停牌），在 decay 计算中 turnover=0，对 cumpdf 无影响但消耗一个日期槽位。这在技术上是正确的，但：

- **连续停牌多日**：如果一只股票停牌 30 天，窗口中 30 个槽位被无效数据占据，实际有效筹码窗口被压缩
- **节假日**：volume=0 行不应出现（parquet 中通常不含非交易日），但如果数据源包含节假日行，会同样消耗槽位

**建议**：添加一个可选的 `--skip-zero-volume` 参数，或在文档中明确说明当前行为对长期停牌股的影响。

### P2 — 建议改进

#### 2.5 复权类型未验证

代码读取 `dividend_type=front`（前复权）数据。前复权是 A 股回测的标准选择（保证最新价格与市价一致），但代码未验证数据确实是前复权的。

**建议**：在加载数据时检查 parquet 的 metadata 或文件名，确认 `dividend_type=front`。如果用户误传了后复权或不复权数据路径，应给出警告。

#### 2.6 新股/次新股处理

上市不足 20 天的股票被跳过（`bars.len() < 20`），这是正确的。但 A 股新股上市首日有 44% 涨幅限制（主板），之后连续一字涨停是常见现象。对于上市 20-60 天的次新股：

- 筹码分布极不稳定（历史数据太短）
- 一字涨停天数占比高，三角分布模型不适用

**建议**：对上市 < 60 天的股票在输出中标记 `is_new_stock=true`，或在排序时降低其权重。

#### 2.7 输出 CSV 缺少行业/板块列

A 股量化研究中，按行业/板块分组分析换手阻力是常见需求。当前输出 14 列中无行业信息。

**建议**：如果 `float_shares.parquet` 中有行业字段，添加到输出中。否则在文档中说明用户需要自行 join 行业数据。

---

## 三、性能优化机会

### 3.1 T/T-1 窗口复用（文档 §7.2.3 已提及）

当前 T 和 T-1 窗口各自独立计算 curpdf 矩阵和 decay。T-1 窗口仅比 T 窗口少最后一天、多前一天。可以：

1. 先计算 T 窗口的 curpdf 矩阵
2. 去掉最后一天的 curpdf 行
3. 在最前面插入前一天的 curpdf 行
4. 重新计算 decay

预期收益：计算量减半，全市场时间从 113s → ~60s。

### 3.2 价格网格共享

当前每只股票独立构建价格网格。同一窗口的 T 和 T-1 可以共享同一个价格网格（取两者的 min/max 并集），减少一次网格构建和 curpdf 分配。

### 3.3 SIMD 显式提示

`calc_cumpdf_decay` 的内层循环（algorithm.rs:177-179）：

```rust
for j in 0..n_prices {
    cumpdf[j] = cumpdf[j] * diff + curpdfs[offset + j] * t;
}
```

编译器应能自动向量化，但可以通过 `#[inline(always)]` 和 `#[rustfmt::skip]` 确保不被打断。也可以用 `std::simd`（nightly）或 `wide` crate 做显式 SIMD。

---

## 四、与行业工具的对比

| 维度 | 本实现 | vnpy | qlib | 聚宽/米筐 | 通达信/同花顺 |
|------|--------|------|------|----------|-------------|
| 筹码模型 | 三角分布 + 指数衰减 | 无内置 | 三角分布 + 指数衰减 | 三角分布 | 三角分布/正态分布 |
| 涨跌停处理 | 仅 high==low | 精确到 tick | 未处理 | 精确 | 精确 |
| 板块差异 | 未区分 | 区分 | 未区分 | 区分 | 区分 |
| 布林带 ddof | 0（总体） | 1（样本） | — | 1（样本） | 1（样本） |
| 复权 | 前复权（未验证） | 前复权 | 前复权 | 前复权 | 前复权 |
| 换手率口径 | 流通 + 自由流通 | 流通 | 流通 | 流通 + 自由流通 | 流通 |
| 并行计算 | rayon 多核 | 无 | 多进程 | 云端 | 无 |

---

## 五、优先级排序

```
P0（必须修复，影响正确性/性能）:
  1. Mutex<Vec> → par_iter().filter_map().collect()    [30min]
  2. T-1 窗口消除不必要的 clone                        [15min]

P1（强烈建议，影响精度/行业对齐）:
  3. 布林带 ddof=0 → ddof=1                            [5min]
  4. 涨跌停判定增强（close 触及涨停价）                 [2h]
  5. 板块涨跌幅差异（10%/20%/30%/5%）                   [3h]
  6. load_daily_bars lazy filter + tail                 [1h]
  7. curpdf 预分配复用                                  [2h]
  8. 单元测试（algorithm + bollinger）                  [3h]

P2（建议改进）:
  9. ThreadPoolBuilder 显式配置                         [15min]
  10. 进度条 / indicatif                                [30min]
  11. 排序字段一致性                                    [10min]
  12. T/T-1 窗口复用                                    [1d]
  13. 新股标记                                          [1h]
  14. 行业/板块列输出                                   [1h]
```

---

## 六、一句话结论

**代码质量高，架构清晰，性能优秀。** 最大的改进空间在 A 股行业对齐：涨跌停判定（仅 high==low 不够）、板块涨跌幅差异（10%/20%/30%）、布林带 ddof（应为 1 而非 0）。Rust 工程方面，`Mutex<Vec>` 反模式和 T-1 窗口的不必要 clone 是最容易的速赢。

---

*编码：UTF-8（无 BOM）。评审日期：2026-05-30。*
