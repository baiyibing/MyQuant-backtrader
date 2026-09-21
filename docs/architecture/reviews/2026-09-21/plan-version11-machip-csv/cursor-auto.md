<!-- agent=cursor:auto cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.18-9a7762b\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.18-9a7762b\index.js --model auto -p --output-format text --trust -f --mode plan --workspace E:\PycharmProjects\OSkhQuant1.3 <prompt> -->
# 评审意见：plan-version11-machip-csv-2026-09-21（v0.3）

侧重：SSOT 一致性 + 行级精确性。取证对象是当前工作树，不是 docstring。交叉核对：claude 稿已完成（其 R1/R2 成立）；kimi/codex 稿未当作事实来源。本方案没有 timeout / budget / 熔断器，因此没有做 slow-fn 实验；若照抄 `with ThreadPoolExecutor`（`csv_daily_loader.py:126`），`__exit__` 会 `shutdown(wait=True)`，调用方不会按 budget 提前返回——plan 也没声称会。

提示词点名的 `docs/backtest/data/symbol-format-ssot.md`、`docs/SSOT.md`、`docs/operations/disclosure-data-source-ssot.md` 在本仓不存在。实际会冲突的 SSOT 是：`docs/backtest/pool-csv-contract.md`、`docs/backtest/engine-ashare-correctness.md` E-R5、`docs/backtest/data/daily-adjusted-update-ssot.md` §1，以及 `oskh_data/symbol_format.py`。

## 🔴 必须修

### R1｜信号价格域被 R4 抹成引擎 `none`，与归档锁定和 E-R5 分家相反（同 claude R1，独立复核成立）

归档锁定行还在，v0.3 转录表丢掉了它：

```31:31:docs/backtest/_archive/plans/plan-ma-chip-edge-strategy-2026-09-07.md
| 价格 | 日线 `period=1d` **`adjust_type=front`**。禁止 `load_single_stock_data`（默认 1m + none） |
```

v0.3 R4（plan:53）写「除权一律用 CSV 引擎现行口径」。现行引擎是 `none`，且非 `none` 会关掉 E-R6：

```108:111:backtest/research/csv_daily_loader.py
    dividend_type: str = "none",
...
    """日线湖装载。默认 ``none``（不复权）；``front`` / ``back`` 读对应分区。
```

```600:604:backtest/research/csv_daily_backtest.py
    # lake none only: E-R6 remap. front/back/qlib $close already continuous.
    if use_qlib_bins or str(dividend_type or "none").strip().lower() != "none":
        exdiv = None
```

9 号导出器先例也是 `dividend_type=none`（`export_strategy9_pool.py:141`）。照抄则 200 日窗、SMA、布林、周线在除权日制造假突破。E-R5（`engine-ashare-correctness.md:124`）锁的是成交/估值走 `none`，不是信号走 `none`。ma_infra 已裁「v11 导出器自行传 front」（`plan-ma-infra-shared-2026-09-21.md:50`，共识 C5）。

修法：§1 补一行——信号（MA/布林/周线/cyqk OHLC）=`front`；成交、涨跌停、T+1、费用=`none` + `mapped_prev_close`。R4 的「除权」只约束执行侧。禁止为对齐信号把引擎默认改成 front（会双计除权并跳过 E-R6）。

### R2｜买日 T 未定义到「该股下一根 bar」，导出器 stale 会被 `skip_no_bar` 当天吃掉（同 claude R2，成立）

归档 FSM 等的是该股自己的下一根 bar，且只覆盖信号日后 ≤4 个自然日（`plan-ma-chip-edge-strategy-2026-09-07.md:30`）。v0.3 只写「≤T-1 计算写入买日 T」（plan:19），没说 T 是市场日历次日还是该股下一根 bar。

池文件当天没有 bar 会当场消耗，不会留到下一交易日：

```260:263:backtest/research/csv_simulate_loop.py
        quoted = buy_quote_for(code)
        if quoted is None:
            st.stats["skip_no_bar"] += 1
            continue
```

若 T=全市场次日，停牌 1 天、间隔仍 ≤4 自然日的票会被丢掉，和归档「下一根 bar 仍买」相反。切片 B 把 stale 放导出器（plan:85）只有在「名字写在该股下一根 bar 那天的文件里」时才成立。

修法：写死 **T = 该码 D 之后第一根有 bar 的交易日，且 `T.date - D.date ≤ 4` 自然日；超出则不写池，manifest 计 `skip_buy(stale)`，并记下原信号日 D**。

### R3｜R3 与 R8 仍互斥；ma_infra 共识 C9 要求改的那句没有回写（不同意 claude ✅5「衔接一致」）

```52:56:docs/backtest/plan-version11-machip-csv-2026-09-21.md
| **R3** | chip/周线计算**复用** `turnover_resist` / `oskh_factors` 既有件，不改其公共 API |
| **R8** | MA/布林/周线一律消费共享基础设施 ma_infra（`sma_asof`/`sma_series`/`bb_asof`/`weekly_sma_asof`） |
```

`docs/architecture/reviews/2026-09-21/plan-ma-infra-shared/merge-consensus.md:19`（C9）已裁：v11 R3 改为周线走 `ma_infra.weekly_sma_asof`；`_daily_to_weekly` 保持私有。v0.3 没改。`_daily_to_weekly` 仍是私有函数且无 asof 参数（`oskh_factors/weekly_macd_divergence.py:86-104`）。`backtest/research/ma_infra.py` 当前不在树上，切片 A 不能 import。

修法：R3 只锁 chip → `turnover_resist.compute_cyqk_series`，周线从 R3 删掉；切片 A 前置改为「ma_infra 代码已合并」。全市场必须每票一次 `sma_series` / `weekly_sma_series` / `bb_series`，禁止逐日 `*_asof`（ma_infra plan:22 已记标量路径不可行）。

### R4｜切片 C「t1_sellable 旁路」会把「买入日禁止卖单」做成当日卖出

`t1_sellable` 是严格的下一日才可卖：

```39:41:backtest/research/ashare_session.py
def t1_sellable(buy_date: date, session: date) -> bool:
    """A-share T+1: a lot is sellable only on a later session than ``buy_date``."""
    return buy_date < session
```

日线已有路径是：`pending_exit` 非空且 `t1_sellable` 才按开盘卖（`csv_daily_backtest.py:344-349`）。买入日 `buy_date < session` 为假，卖不出去。这和锁定口径「买入日禁止任何卖单、T 收盘只产生次日开盘卖」一致。

切片 C（plan:86）写「t1_sellable 旁路方案按 P2」。P2（plan:66）说的是日线 `pending_exit` 原样，并不是旁路。旁路 = 买入日就能卖，直接违反 §1。

修法：删掉「旁路」。钩子只在 **当日买循环之后** 用 T 收盘写 `pending_exit`；卖仍走现有 `t1_sellable` 次日开盘。分钟侧同样只在 T 的最后一根之后写 pending，09:30 才成交。

## 🟡 应修

### Y1｜P1 的 a/b 没贴标签，且和池契约的收盘成交不是同一件事

`pool-csv-contract.md:11-12`：文件名日期 = 买入日 T，「当日尾盘/收盘成交」，不是 T+1 信号日。日线买价就是收盘（`csv_daily_backtest.py:458` `return float(row["close"])`）。归档要的是 D+1 **开盘**。

P1（plan:65）问题栏里两个选项都没有标 a/b，建议栏却写「以分钟 b 为准」。修法：a = 日线保持契约收盘（偏差写入 HELP_LOCK）；b = 分钟 09:30 开盘。日线不要另造 09:30 钟，除非同时改 `pool-csv-contract.md` 的 As-of 句。涨停/一字/volume=0 测试挂在 b 上。

### Y2｜「卖出日不重入」没有现成闸（同 claude Y2）

买侧只看还在不在仓里（`csv_simulate_loop.py:252-255`）。日循环先处理 `pending_exit`（`csv_daily_backtest.py:344`）再 `run_pool_buys_day`（`:460`）。开盘卖掉之后同日池里再出现该码就会买回。切片 C 只在 DoD 里写了测试名。修法：显式 sold-today 集合，买侧过滤。

### Y3｜「复用 TR store 缓存」会读到 window=1000 的 cyqk / 布林（同 claude Y3）

store 列里就有 `cyqk_t`（`oskh_data/turnover_resistance_store.py:31-32`）。bridge 默认 `window=1000`（`oskh_factors/bridge/turnover_resist.py:74`）；导出先例写明只许 `resist_tr_bb_1000`（`scripts/data/export_ta_pool.py:46`）。策略窗是 200，布林是 SMA20+2σ、ddof=1，不是 store 的 bb 列。修法：P3 改为复用装载/股本解析，**禁读 `cyqk_t` 和 store 布林**；`compute_cyqk_series(..., window=200)` 现算。

### Y4｜§1 自称转录归档 §2，但丢了会改交易集的行

至少这三行不在 v0.3 表里：板块（归档:45，沪主板排 688、深主板 `000/001/002/003`、创业板 `300/301`）、抽样（归档:44，seed=`20240907`、front ∩ `float_shares`、每板 10）、股本（归档:35，`circulating_capital` 逐日 backward asof，禁止用 D 日一条股本铺整窗）。P4 重开全市场后，688/北交所/ST 会进池。无名称列时 ST 按代码前缀走 10% 而不是 5%（`pool-csv-contract.md:19-21`；`market_layer.py:63-65`）。归档:42 写明「ST 5% 本轮不做」。seed-30 可继续不做；全市场必须滤 ST 或写名称列。池文件必须是裸六位（`export_strategy9_pool.py:60-68`），不要写 `600000.SH`。

### Y5｜R10 的两种失败不是同一种

窗无效返回整列 NaN（`turnover-resist/src/algorithm.rs:448-455`，子窗 `unwrap_or(NaN)` 在 `:474`）。长度不等在 pyo3 层直接 `PyValueError`（`turnover-resist/src/lib.rs:109-112`），不会变成 NaN。不按票捕获会中断整次导出。等权法非等价的判断成立（`oskh_factors/chip/core.py:580-587`）。修法：NaN → 该日该码 skip；`PyValueError` → 该码 skip 并计数，不换算法。

### Y6｜`apply()` 缺两个键会在注册时抛，R9 的 False 必须出现在返回值里

```137:140:backtest/research/csv_strategy_books.py
    if hooks.get("take_profit") is None:
        raise RuntimeError(f"{book.name} book missing take_profit")
    if hooks.get("record_params") is None:
        raise RuntimeError(f"{book.name} book missing record_params")
```

`limit_up_chase` 是 `setdefault(..., True)`（`:134`）。只在文档里 pin False 无效；必须像 topk 那样在 `apply()` 里返回 `"limit_up_chase": False`（`:811`）。`FORBIDDEN_DEFAULT_STOCK_POOL` 目前只有 version9/10（`:47`）。

## 🟢 可选

- 切片 A 的 `exit_signal(t_close, prev_close, sma5)` 盖不住两段 FSM（收阴次日开盘 vs 收阳后才盯 SMA5，且买入日收阳仍要评 SMA5）。DoD 加一个 `hold_mode` pin。
- §8 的 `pytest -q tests/` 与 CI 口径不一致。CI 是 `-m "not production and not benchmark"`（`.github/workflows/python-tests.yml:56`）。补一条 `csv_daily_backtest.py --strategy 11 --help`。
- `--help` 写上 P0：`cyqk>0.70` 在仓内被当成获利盘抛压/短期反转（归档:68；`cost-migration-implementation-plan.md:377-378` 排除 HIGH>0.8），本版是框架移植，不是已验证多头。

## ✅ 做对的地方

- §2 锚点与代码一致：`export_strategy9_pool.py:2-4` 与 `:62-63`；`csv_ledger.py:79`；日线 `pending_exit` 开盘卖且跌停 defer（`csv_daily_backtest.py:344-349`）；分钟文件无 `pending_exit`；chase 缺 bar 不过期（`csv_simulate_loop.py:145-147`）；`limit_up_chase` 默认 True；`AGENTS.md:22` 预留句。R9 有必要。
- 契约日改成「≤T-1 计算、文件名仍是买日 T」、明确不要照搬 export9 的 `date<=T`，方向对。前提是 R2 把 T 定义死。
- R10 拒绝等权回退、统计窗前 edge 放导出器、不复活 Cerebro、1–10 书零变更，都对。
- P0 建议 a（框架先行、不宣称有效）适合未上线的小团队；0.70 的方向问题不要挡移植，但必须印在 `--help` 上。

**总评：** 锚点和「不要照搬 export9 买即用」是对的，但现在不能进实现。R1 会在除权日系统性改信号，R2 会让停牌票的交易集和归档分叉，R3 两把锁必破一把，R4 的「旁路」会在买入日卖出。这四条改完，并且 P0–P7 人裁、`ma_infra.py` 已进树之后，才可以 GO。不同意 claude 总评里「只修两处即可进实现」。


[runner] cursor:auto 经 2 次尝试完成（含 rc=0 空输出自动重试）
