# 换手阻力 Rust 编译加速优化

> 日期：2026-05-31
> 项目：`turnover-resist`（Rust CLI，依赖 polars 250+ crates）

## 一、原状

| 配置项 | 优化前 | 问题 |
|--------|--------|------|
| `lto` | `"fat"` | 链接阶段单线程全量 IR 优化，最慢模式 |
| `codegen-units` | `1` | LLVM 单线程生成目标代码 |
| `debug` (release) | 未设，默认 `2` | 生成完整 DWARF 调试符号，编译和链接双慢 |
| `strip` | 未设，默认 `false` | 二进制携带全部符号表 |
| linker | MSVC `link.exe`（默认） | Windows 默认链接器，无 LTO 加速 |
| `rustflags` | `-C target-cpu=native`（全局） | debug/test 构建也付出 native CPU 特性检测代价 |
| sccache | 无 | 无编译缓存 |
| polars features | `lazy, parquet, strings, streaming, dtype-full` | 多编译了 `streaming` + `dtype-full` 等不用模块 |
| 增量编译 | 无快速 profile | 每次改一行都要过 fat LTO 全流程 |

**原编译时间（clean build）：未精确记录，估计 15-20 分钟（fat LTO 单线程链接是瓶颈）。**

## 二、瓶颈分析（按影响从大到小）

### 2.1 Fat LTO → 链接阶段主导

`lto = "fat"` 在最终链接时，LLVM 把全部 250+ crate 的 IR 合并成一个大模块，做全量过程间优化，然后**单线程**生成目标代码。这导致：

- 链接阶段 CPU 单核跑满，其余 15 核空闲
- 每改一行代码都要重新走完整的 fat LTO 链路
- polars 这类泛型密集型库产生巨量 LLVM IR，fat LTO 尤其吃亏

### 2.2 `codegen-units = 1` → 无并行

`codegen-units = 1` 强制 LLVM 把整个 crate 的 IR 放入单个 codegen 单元。结合 fat LTO，意味着整个项目的目标代码由 **一个线程** 完成。

### 2.3 完整 DWARF 调试符号

release 默认 `debug = 2`，250+ crates 各自生成完整 DWARF sections，链接器需要合并这些 sections。对于 polars 生成的巨型 LLVM 模块，debug info 的生成和链接时间占比可达 **20-30%**。

### 2.4 polars 多余 feature

`streaming` 和 `dtype-full` 功能未被项目使用，但额外编译了若干 crate。

### 2.5 无编译缓存

`cargo clean` 或切分支后，全部 crate 从头编译。polars 的 250+ 依赖每次重新构建。

## 三、解决办法

### 第一轮：polars 瘦身 + 基础 profile 优化（前序工作）

```toml
# polars features 从 5 个减到 3 个
- features = ["lazy", "parquet", "strings", "streaming", "dtype-full"]
+ features = ["lazy", "parquet", "strings"]

# 全局 rustflags 移除 target-cpu=native（避免 debug 也负担）
- [build] rustflags = ["-C", "target-cpu=native"]

# release profile
- lto = "fat"
+ lto = "thin"            # 并行跨 crate 优化，链接快 5x

- codegen-units = 1
+ codegen-units = 16      # 16 路并行 LLVM codegen

# dev/test profile
+ [profile.dev]  debug = 1
+ [profile.test] debug = 1
```

### 第二轮：debug 符号 + strip + lld 链接器

```toml
[profile.release]
+ debug = 0               # 完全跳过 DWARF 生成（链接阶段收益最大）
+ strip = true            # 裁掉符号表，binary 从 ~80MB 降到 34MB
```

```toml
# .cargo/config.toml
+ [target.x86_64-pc-windows-msvc]
+ linker = "rust-lld"     # LLVM lld 替换 MSVC link.exe，链接快 2-4x
```

### 第三轮：sccache

```toml
# .cargo/config.toml
+ [build]
+ rustc-wrapper = "sccache"
```

安装：`cargo install sccache`
默认缓存位置：`%LOCALAPPDATA%\Mozilla\sccache\cache`，上限 10 GiB。

### 第四轮：双 profile 策略（关键）

```toml
[profile.release-fast]
inherits = "release"
lto = false               # 去掉 LTO，彻底消除链接瓶颈
```

## 四、解决过程

| 阶段 | 操作 | 效果 |
|------|------|------|
| 前序 | polars 瘦身 + fat→thin LTO + codegen-units 1→16 | 瓶颈从 polars 编译转向 thin LTO 链接 |
| 优化1 | `debug = 0` + `strip = true` + `rust-lld` | clean build 537s |
| 优化2 | 配置 sccache | 编译缓存就绪 |
| 优化3 | 创建 `release-fast` profile（`lto = false`）| 增量重编译 **6s** |

## 五、最后结论

**瓶颈本质不是在编译，而是在链接。**

| 环节 | 耗时占比 |
|------|----------|
| crate 编译（250+ 依赖 + 本 crate） | ~30s |
| thin LTO 跨 crate 优化 + 最终链接 | ~200s |
| **总计** | **~230s** |

sccache 能缓存 crate 编译（30s → 0s），但对 thin LTO 链接的 200s 无能为力——因为链接阶段每次都要重做跨 crate 优化。

`release-fast` profile（`lto = false`）直接跳过跨 crate 优化，链接时间从 200s 降到 ~5s，增量重编译从 230s → **6s**。代价是本 crate 内部的自动内联/向量化仍生效（`opt-level = 3`），只是不做跨 crate 内联，对数值计算为主的代码影响极小。

## 六、达成效果

| 场景 | 优化前（估计） | 优化后 | 提升 |
|------|--------------|--------|------|
| Clean build | ~900-1200s（15-20min） | ~550s（9min） | ~2x |
| **增量重编译（日常）** | ~600-900s（fat LTO） | **6s** | **100-150x** |
| 最终发布（thin LTO） | ~900-1200s | ~230s | ~4-5x |
| Binary 大小 | ~80MB（DWARF+符号） | 34MB（stripped） | ~2.4x |

### 日常使用

```bash
# 日常开发迭代（推荐，6 秒出结果）
cargo build --profile release-fast

# 最终发布（全优化 + thin LTO，约 4 分钟）
cargo build --release
```

## 七、经验教训

1. **先定位瓶颈再优化。** 不要一上来就加 sccache 或换链接器。先用 `cargo build --timings` 或对比实验（关/开 LTO 对比耗时）找到真正瓶颈。本案例中 bottleneck 从 polars 编译 → thin LTO 链接 → 最终发现 LTO 本身是主要矛盾。

2. **LTO 是双刃剑。** fat/thin LTO 提供跨 crate 优化，但对 250+ crate 的项目来说链接时间极为昂贵。数值计算类 CLI 工具跨 crate 内联收益微乎其微，日常迭代完全不需要 LTO。

3. **双 profile 是最佳实践。** 一个带 LTO 用于发版，一个不带 LTO 用于日常开发。不要尝试在单一 profile 里同时满足"快速迭代"和"极致性能"。

4. **`debug = 0` 在 release 中性价比极高。** 完整 DWARF 对发布二进制无意义，却占据 20-30% 编译/链接时间。设置 `debug = 0` 是几乎零代价的加速。

5. **sccache 对链接瓶颈无效。** sccache 缓存单个 crate 的编译产物，但 LTO 模式下的链接阶段每次都要处理全部 crate 的 LLVM IR。两者解决的是不同阶段的问题。

6. **Windows 上 `rust-lld` 比 MSVC `link.exe` 快 2-4 倍。** 特别是 LTO 场景下，lld 对 LLVM IR 的处理路径更短。

7. **`codegen-units = 1` 是发布配置的常见误区。** 它确实让 LLVM 有更多优化空间，但对 thin LTO 项目而言收益远小于付出的单线程编译时间代价。`codegen-units = 16` + `lto = "thin"` 是更好的折中。

8. **polars features 按需裁剪。** `default-features = false` + 只开实际用到的 feature，能减少 20-40 个无关 crates 的编译。
