<!-- agent=cursor:auto cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.02-c22c1a3\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.02-c22c1a3\index.js --model auto -p --output-format text --trust -f --mode plan --workspace E:\PycharmProjects\MyQuant-backtrader <prompt> -->
核对完成：其他并行评审员本轮均未产出有效意见（kimi/claude 配额失败，codex/cursor-auto 空壳）；以下独立以代码与最小实验为准。

---

## 评审：`plan-ma-chip-edge-strategy-2026-09-07.md`（v2）
**侧重**：SSOT 一致性 + 行级精确性  
**交叉核对**：`_parallel/{kimi,claude,codex,cursor-auto}` 本轮无完成意见可引；对照已吸收的 [`review-by-cursor.md`](docs/architecture/reviews/2026-09-07/plan-ma-chip-edge-strategy-2026-09-07/review-by-cursor.md)。未跟踪稿 [`ma_chip_edge_backtest.py`](backtest/research/ma_chip_edge_backtest.py) 仅作「方案是否可照抄落地」取证，不当作已验收 SSOT。

---

### 必查盲区核对（事实）

| 盲区 | 结论 | 证据 |
|------|------|------|
| T+1 / 隔日成交 | 方案意图正确：D 收盘确认 → D+1 开盘买；买入日不挂卖；卖出次日 Open | plan L28/L35–L36 |
| 复权口径 | 日线 `front` 统一；禁止 `load_single_stock_data` 正确 | plan L29；`oskh_data/reader.py` `adjust_type='front'` 默认；筹码 hybrid 亦 front（`chip_indicator.py:136-142`） |
| `cyqk_c` 尺度 | **0–1**，阈值 **0.70** 单位正确 | `qlib_cost/cyq.py:184-193` → `get_winner` 累加占比 |
| 20 周均线 | **W-FRI resample + SMA(20) + `_last_day` backward asof**，非 100 日近似 | plan L31；同构 `weekly_macd_divergence.py:86-104` |
| 包边界 | research CLI + `chip_algorithm`→`oskh_factors`/`qlib_cost`；不进 rolling/根目录 | plan L45/L22；`README.md:11-12`；`chip_algorithm.py` re-export |

---

### 🔴 必须修

**R1. `buy/sell(exectype=Open)` 在本仓 backtrader 不存在，照抄必崩**

plan §2 L28/L35 写 `buy(exectype=Open)` / `sell(exectype=Open)`。本环境：

```text
hasattr(bt.Order, 'Open') == False
# buy(..., exectype=bt.Order.Open) → AttributeError
```

`ExecTypes` 仅有 Market/Close/Limit/Stop/…，无 Open。业内等价做法是：**前一日收盘挂 Market（或 pending 状态机）+ 次日 open 成交**；未跟踪稿用 `pending_*` + `set_coo(True)`（`ma_chip_edge_backtest.py:203-228,325`）才是可跑路径。  
**须改写 §2**：删掉 `exectype=Open`，锁「状态机 pending / Market + 次 bar 开盘成交」，并注明勿写不存在的 `bt.Order.Open`。

**R2. 涨跌停 skip 后持仓退出 FSM 未锁定 → 会留下永不退出的多头**

plan L38 只说「不成交、不进净值、写 events」，**未规定 skip 后 `hold_mode`/`pending_sell` 是否保留**。未跟踪实现已踩坑：skip 后清空状态，仓位仍在却无法再触发卖出：

```203:219:backtest/research/ma_chip_edge_backtest.py
        if self.pending_sell and self.position:
            if vol <= 0 or is_limit_open(...):
                self.events.append({..., "event": "skip_sell", ...})
            else:
                self.sell(...)
            self.pending_sell = False
            self.hold_mode = None
            self.buy_ref_close = None
```

最小逻辑实验（镜像上述清空）：

```text
{'hold_mode': None, 'pending_sell': False, 'can_rearm_exit': False, 'still_long': True}
```

A 股跌停无法卖出是常态；**fail-closed 应保留 pending_sell（或 hold_mode），下一交易日继续尝试**。§2 必须显式锁定，并加单测：skip_sell 后仍持仓 → 次日再试卖。

**R3. §1 口头规则与 §2 锁定表在等号上自相矛盾（会误导读 §1 的实现者）**

- §1 L19：`T 收盘 < t-1` → 卖；`T 收盘 > T-1` → 走 MA5（**等号悬空**）
- §2 L34：`≤` fail-closed（正确、应保留）

同文档两口径。v2 既已锁定 ≤，**§1 须改成与 §2 一致的 ≤**，否则评审/实现会再吵一轮。

---

### 🟡 应修

**Y1. 「统计窗」未锁「禁止窗前成交」**  
TL;DR / L42 宣称统计自 2024-01-01，但未写：warmup 加载可从 2022-07-01，**`edge` 触发的买卖不得早于 stats_start**（或报表必须按窗过滤）。未跟踪稿 `run_one` 用 `stats_start - 14d` 作 feed 起点且不过滤成交（`ma_chip_edge_backtest.py:317-319`）——窗前交易会污染 `mean_single_name_return`。§2 补一行即可。

**Y2. ST 5% / none 昨收写了要求、无数据契约**  
L38：ST 5%、优先 none 昨收。本仓无现成 ST 列表 SSOT；`ChipDistribution`/reader 亦无 ST 标记。要么迁入 §5，要么指名用哪张 parquet/字段。否则「声明偏差」也无法验收。主板/创业板 10%/20% 可先落地。

**Y3. 关闭条件「§2 进 `--help`」与摘要指标未在 §2 钉死**  
L96 / L63：`--help` 要带 §2；summary 要触发数/收益/**回撤**/skip。§2 输出表未列回撤与等权净值拼法；未跟踪稿 summary 无回撤、无等权曲线（`ma_chip_edge_backtest.py:349-360`）。把「报表字段清单」写进 §2，避免关闭条件空转。

**Y4. `set_coo` docstring 不可信，方案勿绑 COO 语义**  
实验：日线 `set_coo(True/False)` 均在次日 open=11.0 成交；官方 `set_coo` docstring 写 “buy the close on order bar”，与观测不符。方案应绑定**可测行为**（pending 次日 open），COO 标为可选实现细节，不作 SSOT。

**Y5. 对抗回填与现行 §2 的 SMA 表述曾漂移**  
`review-by-cursor.md:11` 曾写「均线只用 `[-1]`」；现行 plan L30 正确改为：在 D 的 next 评 `cond[D]` 时 `sma[0]` 含 D 合法，禁止的是在 **T 日用含 T 的 sma 去判 T-1**。建议在 plan 勘误/对抗段加一句「S-F2 已由 v2 重述」，避免后人再引旧 host 条目回退。

---

### 🟢 可选

- G1. `replaced` 字段与「预热不足重抽」 provenance（plan L40）可写清：功能重抽即可，`replaced=True` 非硬门槛。  
- G2. 单测清单 L69–75 补：双真不买、D-1 NaN 不买、首日收阳走 MA5、skip_sell 保 FSM。  
- G3. CLI exit：空宇宙/零可用票是否非 0，小团队可保留 exit 0 + 打印告警。

---

### ✅ 做对的地方（保留）

1. **拒绝**直接读 `ChipDistribution.cyqk_c[0]`：窗口 `range(-period, 0)` 不含当日 OHLC，却用 `close[0]` 定价（`chip_indicator.py:102-108,161-164`）；且默认不传 `as_of_date`。v2 含 D 窗口 + `as_of_date=D` 正确。  
2. **`cyqk_c∈[0,1]` + 阈值 0.70** 与 `get_winner`/`get_cost` 契约一致；「抛压区」仅作框架试验披露（plan L62 + `cyq.py:188-190`）合适。  
3. **周线 asof** 对齐 `_daily_to_weekly`（`W-FRI` + `_last_day=max`），未完成周丢弃——因果正确。  
4. **path-SSOT**：`resolve_period_root("1d")/dividend_type=front` ∩ `resolve_source_parquet("float_shares.parquet")`；禁止 `oskh_data.float_shares` 下载模块——与 `AGENTS.md`/`data_root.py`/`chip/paths.py→resolve_source_parquet` 一致。  
5. **包边界**：`backtest/research/` + 不改 rolling/full；算法走 `chip_algorithm`/`oskh_factors`/`qlib_cost`——对齐 README。  
6. **边缘定义**要求 D 与 D-1 双侧有限（NaN≠边缘）——防 warmup 伪信号。  
7. **单票独立 Cerebro + 等额本金** 与多 feed 共享资金划清，适合 30 只框架试验。

---

### 总评

口径在复权、盈筹率单位、周均线、ChipDistribution 规避、包边界上已对齐本仓 SSOT，**可以进实现**；但须先修订 **R1（假 API `Order.Open`）、R2（skip 后退出状态机）、R3（§1/§2 等号）**——否则实现者会按错误 API 崩掉，或在跌停日留下无法平仓的仓位，把框架试验净值做成不可解释结果。修完这三条 + Y1 统计窗过滤后，再跑 30 只试验。


[runner] cursor:auto 经 2 次尝试完成（含 rc=0 空输出自动重试）
