## Rust vs Python 换手阻力精度差异排查

### 背景

Rust 版和 Python 版全市场换手阻力计算结果存在差异：4594 只共同股票中，2000+ 只的 cyqk 差异超 1e-6，最大差 0.039。

**已确认不是数据源问题**：资本数值（`circulating_capital` / `FloatVolume`）完全一致，差异来自算法实现层面——curpdf、cumpdf 或 window 切分的浮点累积路径不同。

### 差异最大的 3 只股票

```
002374.SZ: cyqk_T  rust=0.587200  py=0.548100  diff=0.039100
000727.SZ: cyqk_T  rust=0.901900  py=0.864100  diff=0.037800
000088.SZ: cyqk_T  rust=0.159900  py=0.196400  diff=0.036500
```

### 排查方法

对以上 3 只股票，分别用 Rust 和 Python 跑，打印每个中间环节的输出，逐环节对比定位偏差首次出现的位置：

**1. 窗口对齐**：确认 T 窗口和 T-1 窗口覆盖的交易日完全相同。打印 Rust 和 Python 各自的窗口起止日期（`first_date`, `last_date`）、K 线条数。

**2. curpdf（三角分布）**：取 T 窗口中间一天的 curpdf 向量（如第 500 天），对比 Rust 和 Python 的值。打印前 10 个和最后 10 个非零 bin 的值。

**3. cumpdf（衰减累积）**：取最终 cumpdf 向量，对比前 10 个 bin 的值。cumdf 是递推的，差异会在千次累积中放大。

**4. cyqk**：`winner / total`，对比 winner（收盘价以下筹码量）和 total（总筹码量）两个中间值。

### 运行方式

```bash
# Rust（从 turnover-resist/ 目录）
cd turnover-resist && cargo build --release
./target/release/turnover-resist --date 20260525 --output backtest_output/_debug.csv 2>&1

# Python
D:/anaconda3/envs/vanna311/python.exe scripts/data/full_market_canonical_resist.py \
  --date 20260525 --method batch --workers 1 --batch-end 1 --output backtest_output/_debug.csv
```

建议先只跑 002374.SZ 一只，确认偏差来源后再扩展到 3 只验证。

### 预期产出

定位到具体是哪个环节（curpdf / cumpdf / window alignment / turnover rate）首次出现 >1e-6 的差异，给出修正建议。
