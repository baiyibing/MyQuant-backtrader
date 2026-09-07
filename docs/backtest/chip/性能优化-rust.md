# turnover-resist Rust 性能优化

> 合并自 5 个源文件，涵盖运行时优化、编译优化、已完成项和已评审关闭项。

---

## 1. 运行时优化

### 1.1 curpdf 复用（circ + free 共享）✅

**问题**：circulating 和 free-float 两个口径各自独立计算 `all_curpdfs`，三角分布计算量翻倍。

**方案**：`compute_curpdfs_once` 提取为统一预计算入口，curpdf 只依赖价格/成交量（与股本无关），circ 和 free 共用同一份 curpdf，仅在 `compute_cyqk_from_curpdfs` 中用不同 `scale` 缩放 turnover。

**效果**：280s → 253s（**-9%**）

**涉及**：`algorithm.rs`（`PrecomputedCurpdf` 结构体 + `ComputeCurpdfError` 枚举）

### 1.2 polars parquet 批量加载 ✅

**问题**：`load_daily_bars_filtered` 逐只打开 parquet 文件（5500 次 I/O），每次读取全量历史后在 main.rs 过滤。

**方案**：`load_all_stocks_parquet` 主线程串行批读，polars lazy scan + 谓词下推（`time >= start_ms && time <= target_ms`），只投影需要的 7 列。

**效果**：数据加载 7.6s，总耗时 253s → 221s（**-13%**）

**涉及**：`data.rs`（`ParquetLoadResult` + `ParquetLoadStats`）

### 1.3 DuckDB 集成实验（未采用）✅

**问题**：尝试用 DuckDB 替代 polars per-file parquet，单 SQL 查询全市场日线。

**结果**：DuckDB 11.1s vs polars 7.6s，**polars 更快**。DuckDB 需编译 bundled C++ 源码（+20min 首次编译），且 `.duckdb` 文件 1.1GB 维护成本高。

**结论**：保留 polars parquet 方案，DuckDB 代码作为 `feature = "duckdb"` 可选保留。

### 1.4 Vec 拷贝消除 + 预分配缓冲 ✅

**问题**：`build_window` 每次复制 ~1000 × n_prices 的 curpdf 切片到新 Vec；`calc_single_day_curpdf` 每次分配新 Vec（1000 天 × 5500 只 = 550 万次堆分配）。

**方案**：
- `calc_single_day_curpdf_into` 复用预分配 `day_buf`
- `calc_cumpdf_decay_window_scaled` 接受全局 `all_curpdfs` 切片 + 窗口偏移，不再构建窗口局部 Vec
- `compute_cyqk_from_curpdfs` 内部复用单个 `cumpdf_buf`

**涉及**：`algorithm.rs`

### 1.5 Mutex<Vec> → filter_map.collect ✅

**问题**：`Mutex<Vec<OutputRow>>` + `par_iter().for_each()` 存在锁竞争，限制并行扩展性。

**方案**：rayon `filter_map` + `collect`，零锁竞争：
```rust
let outcomes: Vec<Result<OutputRow, SkipReason>> = codes
    .par_iter()
    .map(|code| process_one_stock(code, &ctx, info, ff_info, ff_info_prev, ...))
    .collect();
```

### 1.6 T-1 窗口 clone 消除 ✅

**问题**：T-1 窗口对 ~1000 根 BarRow 做深拷贝。

**方案**：`union_bars` 切片 + 偏移量传递，零拷贝。

---

## 2. 编译优化

### 2.1 瓶颈分析

| 配置项 | 优化前 | 问题 |
|--------|--------|------|
| `lto` | `"fat"` | 单线程全 IR 优化，polars 250+ crate 极慢 |
| `codegen-units` | `1` | 单线程 LLVM codegen |
| `debug` | 默认 `2` | 全量 DWARF 符号，拖慢编译+链接 |
| polars features | `streaming` + `dtype-full` | 编译未使用的 crate |
| 编译缓存 | 无 | `cargo clean` 后 250+ 依赖从零编译 |

**核心发现**：瓶颈在链接阶段，不在编译。

### 2.2 四轮优化

| 轮次 | 措施 | 效果 |
|------|------|------|
| 1 | polars 裁剪（5→3 features）+ fat→thin LTO + codegen-units 1→16 | 链接快 5x |
| 2 | `debug=0` + `strip=true` + `rust-lld` 链接器 | 二进制 80→34MB，链接快 2-4x |
| 3 | sccache 编译缓存 | 增量编译 crate 缓存 |
| 4 | `release-fast` profile（`lto=false`） | 增量重编 **6s** |

### 2.3 最终效果

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| Clean build | ~15-20min | ~9min | ~2x |
| **增量编译（日常）** | ~10-15min | **6s** | **100-150x** |
| 二进制大小 | ~80MB | 34MB | ~2.4x |

### 2.4 Profile 策略

| Profile | LTO | 用途 | 编译时间 |
|---------|-----|------|---------|
| `dev` | 无 | 调试/测试 | ~30s |
| `release` | thin | 正式发布 | ~10min |
| `release-fast` | 无 | 日常开发 | ~2min（增量 6s） |

---

## 3. 性能基线

### 3.1 全市场耗时（2026-05-25，window=1000）

| 阶段 | 耗时 |
|------|------|
| 数据加载（polars batch） | 9.8s |
| Capital 加载 | 0.1s |
| 计算（rayon 并行） | 224.2s |
| 排序 + CSV 输出 | <1s |
| **总计** | **234.2s（~3.9min）** |

### 3.2 旧版 vs 当前版本

| 维度 | 旧版（05-29） | 当前 |
|------|-------------|------|
| Capital 口径 | 仅 Float | Circulating + Free float |
| 计算量/只 | 1× | 2×（curpdf 共享但 cumpdf ×2） |
| LTO | fat | thin |
| codegen-units | 1 | 16 |
| 数据加载 | rayon 内逐只 | 主线程批量 |
| **总耗时** | **106s（1.8min）** | **234s（3.9min）** |

耗时增加是因为计算量翻倍（双口径）+ 精度修复（T-1 capital 分离），但功能完整性大幅提升。

---

## 4. 已评审关闭项

以下优化经可行性评估后决定不实施（详见 `turnover-resist-第三步性能深化可行性评估.md`）：

| 项目 | 原因 |
|------|------|
| T/T-1 curpdf 增量复用 | cumpdf 仅占总计算 ~21%；反向衰减值不稳定；T/T-1 不同 capital 使增量不可行 |
| 显式 SIMD hints | 编译器自动向量化已足够 |
| Parquet 谓词下推 tail read | I/O 仅占 ~5%，收益不抵复杂度 |
| 批量日期范围计算 | 当前无此需求 |

---

## 5. 源文件索引

本文档合并自以下文件（已归档至 `_archive/`）：

| 原文件 | 内容 |
|--------|------|
| `Rust换手阻力性能优化方案.md` | 运行时优化（§1.1-1.3, §3） |
| `turnover_resistance_rust_build_optimization.md` | 编译优化（§2） |
| `turnover_resistance_rust_improvements.md` | 改进建议中的性能项 |
| `review-turnover-resist-rust.md` | 代码审查中的性能项（§1.1-1.4, §3） |
| `turnover_resist_progress_note.md` | 执行总结（§2.2 P1） |
