# Turnover-Resist 桥接选型：PyO3 FFI vs CLI 子进程

> **状态**：benchmark 已完成（2026-06-06）
> **范围**：`turnover-resist/` Rust 模块接入 Python 主循环的桥接方式
> **结论**：推荐 PyO3 FFI。速度不是决策因素（两者端到端差异 <0.5%），但 PyO3 对 Python 调用方的集成便捷性显著优于 CLI。

---

## 1. 背景

`turnover-resist` Rust 模块（换手阻力 + 布林带）已完成：
- 精度对齐：`verify_rust_python_alignment.py` 通过
- 性能：Rust 版较 Python 版有数量级提升
- 未决问题：**如何从 Python 交易主循环调用 Rust 计算**

候选方案：
- **A）CLI 子进程**：保持现状（`verify_rust_python_alignment.py` 通过 `subprocess.run` 调 `turnover-resist.exe`）
- **B）PyO3 FFI**：用 `maturin` 构建 Python extension，直接 `import turnover_resist`

---

## 2. Benchmark 结果

环境：`D:\anaconda3\envs\vanna311\python.exe`，Windows 11，`E:\rust-targets\release\turnover-resist.exe`。

### 2.1 子进程启动开销

| 方案 | 调用方式 | 延迟（median） |
|------|----------|---------------|
| CLI echo baseline | `subprocess.run(["echo", "hello"])` | **39 ms** |
| PyO3 FFI nop | `turnover_resist.nop()` | **0.2 μs** |
| **差距** | — | **~2×10⁵×** |

### 2.2 全市场批量（~5 500 只股票）端到端

| 指标 | CLI（子进程） | PyO3（FFI，推算） |
|------|--------------|-------------------|
| 子进程 / FFI 调用 | 39 ms | 0.0002 ms |
| Parquet 批量加载 | ~56 s（冷）/ ~23 s（热，OS 缓存） | 同上（同一 Rust 代码） |
| 核心计算（capital + compute） | ~8 s | 同上 |
| 结果传递（CSV 写+读 / JSON 序列化） | ~100 ms | ~17 ms（5k 行 JSON） |
| **端到端总计** | **~64 s（冷）/ ~27 s（热）** | **~64 s（冷）/ ~27 s（热）** |

> **关键事实**：两种方案的瓶颈都是 **Parquet 批量加载** 和 **rayon 核心计算**，桥接方式本身对总时间影响 <0.5%。

### 2.3 数据传递规模（PyO3 JSON 序列化）

| 行数 | JSON 大小 | 序列化 median |
|------|-----------|---------------|
| 100 | 0.04 MB | 0.2 ms |
| 1 000 | 0.36 MB | 3.2 ms |
| 5 000 | 1.8 MB | 17 ms |
| 50 000 | 18 MB | 184 ms |

---

## 3. 技术原理与工程差异

### 3.1 核心原理：寄快递 vs 同事递文件

| | **CLI（命令行子进程）** | **PyO3 FFI（直接绑定）** |
|---|---|---|
| **本质** | Python 启动一个**独立的 Rust 程序**，像调用外部工具 | Python **直接载入 Rust 编译成的动态链接库**，像调用本地函数 |
| **类比** | 你给仓库发**快递单**（命令行参数），仓库打包好**寄回包裹**（CSV 文件） | 你和同事**坐在同一办公室**，直接伸手递文件 |
| **进程关系** | Python 和 Rust 是**两个独立进程**（父子关系） | Python 和 Rust 是**同一个进程内的两个模块** |
| **数据怎么传** | 通过**命令行参数 + 文件系统**（CSV/JSON） | 通过**共享内存**（PyO3 自动转换 Python 对象和 Rust 结构体） |

### 3.2 代码层面真实对比

以"计算 2026-05-25 全市场换手阻力"为例：

**CLI 方案（当前现状）**
```python
import subprocess
import pandas as pd

# 第 1 步：发快递（启动子进程，等它跑完）
cp = subprocess.run([
    r"E:\rust-targets\release\turnover-resist.exe",
    "--date", "20260525",
    "--sort-by", "free",
    "--output", "backtest_output/result.csv"
], capture_output=True, text=True)

# 第 2 步：检查快递是否丢件（子进程可能崩溃）
if cp.returncode != 0:
    raise RuntimeError(f"Rust 挂了：{cp.stderr}")

# 第 3 步：去快递柜取包裹（读 CSV 文件）
df = pd.read_csv("backtest_output/result.csv")
```

**PyO3 FFI 方案（推荐方向）**
```python
import turnover_resist  # 像 import numpy 一样

# 直接调用，返回值就在内存里，没有中间文件
json_str = turnover_resist.compute_turnover_resist(
    date="20260525",
    window=80,
    step=0.01,
    sort_by="free",
    ...
)

import json
data = json.loads(json_str)  # list[dict]
```

### 3.3 工程维护视角的长期差异

| 维度 | CLI | PyO3 FFI |
|---|---|---|
| **构建产物** | 一个 `.exe` 文件，谁都能跑 | 一个 `.pyd`（Windows 动态库），**必须与 Python 版本严格匹配**（cp311 的库不能给 cp310 用） |
| **构建工具** | `cargo build --release`（已熟悉） | 需要 `maturin` 或 `setuptools-rust`（新工具链） |
| **Rust 改一行代码后** | 重编 `.exe`，替换文件即可 | 重编 `.pyd`，且要确保 Python 环境没卸载/升级 |
| **调试 Rust** | 直接命令行 `./turnover-resist.exe --date ...`，看 stderr 输出 | 需要写 Python 测试脚本触发，或用 `gdb`/`lldb` attach 到 Python 进程 |
| **CI/部署** | 把 `.exe` 拷贝到服务器即可 | 需要每台目标机器都有对应 Python 版本的 wheel，或现场编译 |
| **跨语言复用** | Java/Go/Node 都能调 `.exe` | 只能 Python 用 |

### 3.4 本项目具体痛点

**痛点 1：调用代码的整洁度**
```python
# CLI：每次调用像写 shell 脚本，还要管临时文件
subprocess.run([binary, "--date", date, "--output", f"tmp_{uuid4()}.csv"], ...)
df = pd.read_csv(f"tmp_{uuid4()}.csv")
os.remove(f"tmp_{uuid4()}.csv")  # 还得记得删

# PyO3：一行搞定
data = turnover_resist.compute_turnover_resist(date=date)
```

**痛点 2：错误处理**
```python
# CLI：Rust panic 了，Python 拿到的是字符串，得自己 parse
cp = subprocess.run([...])
if cp.returncode != 0:
    print(cp.stderr)  # 一大段文本

# PyO3：直接抛异常，和 Python 原生库一样
data = turnover_resist.compute_turnover_resist(date="20269999")
# → RuntimeError: invalid date '20269999': ...
```

**痛点 3：未来扩展**
如果有一天只想算 **10 只自选股的 turnover-resist**，而不是全市场 5000 只：
- CLI：没法传 `list[str]`，只能写临时文件给 Rust 读
- PyO3：直接 `compute_turnover_resist(stock_codes=["000001.SZ", ...])`

---

## 4. 场景分析

| 场景 | CLI 是否够用 | 说明 |
|------|-------------|------|
| **回测 / 每日选股**（全市场 5k 只，一天 1–3 次） | ✅ 够用 | 子进程 39 ms 相对于 27–64 s 可忽略；实现零额外工作量 |
| **盘中实时单只/小批量**（每秒 1–10 次） | ❌ 不可行 | 39 ms × 10 次 = 390 ms/s，子进程启动成为瓶颈 |
| **盘中实时全市场**（每小时 1 次） | ✅ 够用 | 与回测场景类似，频率低 |

---

## 5. 选型结论

**推荐 PyO3 FFI 作为主力桥接方案。**

理由（按优先级排序）：

1. **Python 调用方最方便**（核心决策因素）
   - CLI：`subprocess.run([...])` → 管理临时 CSV 路径 → `pd.read_csv(...)` → 手动清理文件；错误需检查 `returncode` 和 `stderr`。
   - PyO3：`turnover_resist.compute_turnover_resist(date="20260525", ...)` → 直接拿到 `list[dict]`；错误直接抛 Python `RuntimeError`，Traceback 可追踪。
   - **对主循环开发者而言，PyO3 是"普通函数调用"，CLI 是"运维脚本调用"，心智负担不在一个量级。**

2. **性能无劣势**
   - 全市场批量场景端到端差异 <0.5%（瓶颈在 parquet 加载和 rayon 计算，不在桥接层）。
   - 子进程方案的唯一性能优势（免 FFI 序列化）在全市场批量下被 CSV 写+读抵消。

3. **代码结构已就绪，投产门槛低**
   - 核心计算已提取到 `engine.rs`，CLI / PyO3 共用同一份逻辑，无代码重复。
   - `lib.rs` 中已含最小 PyO3 绑定（`compute_turnover_resist` → JSON），且已通过 `cargo check`。
   - 生产化只需把 JSON 返回改为 `Vec<PyDict>`，工作量 **≤0.5 人日**。

4. **构建链已有解**
   - `release-fast` profile（无 LTO）编译时间从 ~20 min 降至 ~2 min，日常开发可接受。
   - CI 可缓存 `E:\rust-targets`（sccache + cargo artifact lock），全量重编只在依赖升级时触发。

**CLI 的保留场景**
- 独立调试/排错：直接在命令行 `turnover-resist.exe --date ...` 跑，不依赖 Python 环境。
- 跨语言复用：若未来需要 Java/Go 调用，CLI 比 PyO3 更易适配。

---

## 6. 已落地的原型资产（供未来复用）

| 资产 | 位置 | 说明 |
|------|------|------|
| 核心计算提取 | `turnover-resist/src/engine.rs` | `run(&Cli) -> Vec<OutputRow>`，CLI / PyO3 共用 |
| PyO3 最小绑定 | `turnover-resist/src/lib.rs` | `compute_turnover_resist(...)` → JSON 字符串；已编译通过 |
| Benchmark 脚本 | `scripts/diagnostics/benchmark_turnover_resist_bridge.py` | 可复跑 CLI / PyO3 对比 |
| PyO3 微型 stub | `turnover-resist/pyo3_bench_stub/` | 纯 FFI 开销测量 crate，不依赖 polars |

> 若未来决定切 PyO3，只需：① 把 `lib.rs` 中的 JSON 返回改为 `Vec<PyDict>`；② `maturin develop --release`；③ 替换 `subprocess.run` 为 `turnover_resist.compute_turnover_resist(...)`。工作量 **≤0.5 人日**。

---

*维护：选型结论变更需重新跑 benchmark 并更新本文件。*
