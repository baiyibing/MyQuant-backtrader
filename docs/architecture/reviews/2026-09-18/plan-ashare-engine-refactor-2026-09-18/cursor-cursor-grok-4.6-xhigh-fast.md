<!-- agent=cursor:cursor-grok-4.6-xhigh-fast cmd-prefix=C:\Users\wangc\AppData\Local\cursor-agent\versions\2026.09.15-d2fe57e\node.exe C:\Users\wangc\AppData\Local\cursor-agent\versions\2026.09.15-d2fe57e\index.js --model cursor-grok-4.6-xhigh-fast -p --output-format text --trust -f --mode ask --workspace D:\PycharmProjects\MyQuant-backtrader <prompt> -->
并行目录里 **composer 已成文**，auto / grok 仍只有头。下面按代码独立取证，并交叉核对 composer 条目。Ask 模式只出评审，不落盘。

---

# 评审意见 · `plan-ashare-engine-refactor-2026-09-18.md` v1.2

**侧重**：SSOT 行级精确性。对照 positioning / correctness / `ashare_*` / 双引擎 / 围栏测试。安全阀类：本 plan **未引入** timeout / budget / circuit-breaker；现有加载器是无 timeout 的 `ThreadPoolExecutor`。Ask 模式未跑实验；CPython 行为按文档陈述，标「建议主持裁复核」。

---

## 🔴 必须修

### R1 · 切片 A 未钉 v7 帧契约（同意 composer R1，并补后果）

§5-A 写 v7 默认湖路径改走 `load_minute_ohlc`（DatetimeIndex + `ymd`/`hm`），但生产切片仍按 **`date` 列**：

```258:264:backtest/research/csv_minute_backtest_v7.py
def _day_frame_records(frame: Any, day: date) -> list[dict[str, Any]]:
    sl = frame.loc[frame["date"] == day]
```

`read_lake_minute_ohlc` 产出无 `date` 列（`ashare_bars.py:322-361`）。直换会 `KeyError`；若误把 `ymd` 与 `date` 对象比较，则全日空切片、reason 全 `skip_no_1455`，合成窗可假绿。

**要求**：§5-A / §7 三选一写死——(a) 复用 `_slice_day`；(b) `_day_frame_records` 认 `ymd`/DatetimeIndex；(c) 薄适配层。DoD 加「改造后非空 bar 计数 > 0」。

### R2 · 同文档 §5-A 与 §7 对 compact 自相矛盾

| 落点 | 原文 |
|------|------|
| §5-A | compact **降为模块私有并保留** qlib_1min + topk/`bars_from_pool` |
| §7 `ashare_bars.py` | 「compact **降级或删**」 |

`load_minute_ohlc` **无 `source`**（`ashare_bars.py:545-556`）。删 compact 会断 `--minute-source qlib_1min`（`csv_minute_backtest_v7.py:503-523`）和 `load_session_bars`→`load_minute_compact`（`ashare_bars.py:266-268`）。handoff §1.2 写「保留」比 plan §7 准。

**要求**：§7 删「或删」，与 §5-A / handoff 对齐为「私有 + 保留链」。

### R3 · topk 与 v7 **共用** `_load_cli_bars`，不是独立链

§7 写 `qlib_bin_1min.py` + topk 脚本 **不改**、compact 链共存。事实：topk **不自己加载分钟**，直接调 v7：

```22:28:backtest/research/csv_minute_backtest_topk_app_dropout.py
from backtest.research.csv_minute_backtest_v7 import (
    _load_cli_bars, ...
)
```

```144:144:backtest/research/csv_minute_backtest_topk_app_dropout.py
    minute, daily = _load_cli_bars(pools, start, end)
```

改 v7 默认湖路径 = 改 topk 湖帧，即使 topk 文件零 diff。§5-A「保留 topk/`bars_from_pool` 链」与「v7 默认改 `load_minute_ohlc`」未拆分支。

**要求**：写死 `_load_cli_bars` 的 lake / `qlib_1min` 分叉；topk 湖路径要么跟 v7 适配器走（DoD 含 topk 合成窗非空），要么独立 `cache_dir` / 仍走 compact，禁止只写「topk 脚本不改」。

### R4 · v7 挂上 `load_minute_ohlc` 默认 `use_cache=True`，会污染 1–10 / Mode B 共享 cache

```397:399:backtest/research/ashare_bars.py
def minute_cache_path(start: str, end: str, cache_dir: Optional[Path] = None) -> Path:
    return root / f"minute_none_{start}_{end}.parquet"
```

键只有 `(start,end)`，不含 symbol 集合。`load_minute_ohlc` 默认 `use_cache=True`（`:551`）。v7 名单远小于 1–10 / Mode B：同一窗若 v7 先写 cache，再被大名单 hit，就会走「缺码 + 整读合并」（`:570-576`）——这正是 E-07 要堵的 6.6–6.7GB 路径。§5-A DoD「1–10 / Mode B 测不动」与「v7 默认走带 cache 的书加载器」冲突。

**要求**：v7 湖路径 `use_cache=False`，或独立 `cache_dir` / 键含 symbol 指纹；并写明「禁止用小名单覆写大窗 cache」。

### R5 · 切片 B 把 T+1 / 涨跌停写进 `execute_buy` / `_sell`（会误导实现）

§5-B：`execute_buy` / `_sell` / v7 `_buy` / `_sell_lots` 的涨跌停与 T+1 **只调** `ashare_session`。

事实：`csv_ledger.execute_buy` / `_sell` **不含** T+1、不含涨跌停（`:194-242`、`:242-276`）。1–10 日线/分钟 **零调用** `t1_sellable` / `skip_buy_at_limit` / `defer_sell_at_limit`；T+1 是 `n_days = i - entry_idx` + `n_days >= 1`（`csv_daily_backtest.py:325-334`，`csv_minute_backtest.py:609-618`）。涨跌停在 simulate 环直调 `hit_limit_*`，另有 `reserve_limit_up` / `forbid_all_trade_at_limit` / `qlib_limit_pct`（仅 topk 书打开）。

v7 `_sell_lots` 已调 `t1_sellable`；`_buy` 不调涨跌停（调用方调）。把谓词塞进 `execute_buy` 会改签名或在买路径误加 T+1。

**要求**（收窄，部分同意 composer Y1）：本切片统一的是 **调用点** 的 `t1_sellable` + `skip_buy_at_limit` / `defer_sell_at_limit`；**不**改 `execute_buy`/`_sell` 契约；**不**替换 reserve / open_board / qlib 9.5% 带内所有 `hit_limit_*`。

### R6 · 围栏 DoD 无可执行锚点（同意 composer R3）

仓内只有 `tests/test_research_face_imports.py:110-119`：rglob 禁 **backtrader**，不管 `trade_fee_policy`。`research/engine.py:21-24` 仍 import `trade_fee_policy`。§5-C 枚举 11 文件正确（E-05），但未钉测试路径 / 常量名。handoff §3 仍写泛「热路径 AST」，未列清单。

**要求**：`tests/test_ashare_simulate_import_fence.py` + `SIMULATE_HOT_PATH` 与 §5-C **字节级一致**；handoff §3 抄同一清单。

---

## 🟡 应修

### Y1 · `limits is None` 不只有「缺昨收」

`session_limit_prices` 在 `previous is None` **或** 未知板块时都返回 `None`（`ashare_session.py:63-70` + `market_layer.py:73-79`）。v7 卖/加仓：`defer_sell_at_limit(px, None)→False` → **fail-open**（`csv_minute_backtest_v7.py:335`）。书引擎：`limits is None` → `skip_unknown_board` + `continue`，**连卖一起冻**（`csv_daily_backtest.py:320-322`）。

§5-B 只写「缺昨收」。None-limits 向量须覆盖 **无昨收** 与 **未知板块** 两支，并写明书引擎冻仓 vs v7 放行。

### Y2 · 围栏枚举漏传递依赖

热路径还会 import `csv_daily_loader` / `csv_pool` / `market_layer` / `exdiv_map` / `qlib_bin_*`（`ashare_bars.py:101-104, 220`）。单文件 AST 看不到下游 `import qlib`。应把这些列入围栏，或写「传递依赖白名单 + 递归一层」。

### Y3 · `n_days` 映射必须钉 `calendar[entry_idx]`

`Position.entry_idx` 注释已是「全局日历下标」（`csv_ledger.py:70`）。`build_calendar` 是全 symbol 日期并集（`csv_common.py:48-59`）。`t1_sellable(calendar[entry_idx], calendar[i])` 在日历严格排序时等价 `n_days>=1`。须禁止用 **个股自身有 K 日** 反推 `buy_date`（与 E-02 同构，落到 handoff 步骤 2）。

### Y4 · 切片 A 改 `load_minute_ohlc` 缓存合并 = 动共享核

缺码不整读一旦改 `load_minute_ohlc`，1–10 / Mode B 共用该函数。DoD「测不动」应改为：填价 / reason 不变；**允许** cache 写路径变。并给 data-free 缺码 fixture（同意 composer Y2）。

### Y5 · 日线止盈不是「一律次日开」

默认 `daily_same_bar_prefixes=("open_board",)`（`csv_strategy_books.py:118`）。`profit_take` / `trail` → `pending_exit` 次日开（`csv_daily_backtest.py:396-399`）；`open_board` 与 topk 的 `SAME_BAR_PREFIXES` **当日收盘卖**。切片 B 合成向量不要写成「日线止盈全是 pending」。

### Y6 · 无 timeout 的线程池（本 plan 未声称，但切片 A 会加重）

`load_minute_from_lake` / `load_minute_compact` / `load_daily_bars` 均为 `with ThreadPoolExecutor(...)`（`ashare_bars.py:380`、`224`；`csv_daily_loader.py:114`），**无 timeout**。按 CPython，`Executor.__exit__` → `shutdown(wait=True)`，单 worker 挂死则调用方不返回。本船若「激进一次到位」应在 §5-A 记为已知限制，或 `use_cache=False` 时不要暗示可取消。**未跑实验，建议主持裁复核。**

### Y7 · P2 开关名与现网冲突（P2 另开 plan，先记账）

现网对照开关是 `--qlib-cost`（`csv_daily_backtest.py:656`），不是 `--fees full`。P2=A 若日后开工须先定 CLI 名，避免第三套费率旗标。

---

## 🟢 可选

- Mode A `Instance` 第三套跟踪：§2 非目标加一句（同意 composer Y5）。
- §5-A 写明 `minute_cache_path` 无新鲜度（E-15）；v7 CLI 是否暴露 `--rebuild-cache`。
- 切片 D 词表做成 tests 内 dict（composer Y3）；小团队可宿主步骤手比，不阻塞 GO。
- `chip_indicator.py` **已随 Cerebro 删除**；筹码在 `oskh_factors.chip` / `qlib_cost`。plan 未引用该化石，正确。
- P5=A「薄包装」补允许改的 argv / exit code（否则无法验收）。

---

## ✅ 做对的地方（保留）

- **三仓守界**：§0.2–§0.3 / R1–R2 与 `engine-positioning-ssot.md` 同构；不复活 Cerebro、不 import qlib、不仿 LEBS。研究入口仍在 `backtest/research/`。
- **T+1 买入日不可卖**：日线 `n_days>=1`（`:327,334`）；分钟 `can_sell=(n_days>=1)`（`:618`）；v7 `t1_sellable(buy_date, day)`（`:39-41`、`:228`）。`n_days=0` 不能卖。
- **日线止盈默认次日开**（非 same_bar）：`pending_exit`（`csv_ledger.py:74`）。评估用当日 bar + `index < day` 昨收（`csv_common.py:22-45`），未见用未来 close 定价。
- **复权**：书链默认 `dividend_type=none`（`csv_daily_backtest.py:6-7,639-641`；`csv_daily_loader.py:96`）。plan 未把筹码默认 front 套进 1–8。
- **盈筹**：`cyqk_c` 尺度 0–1（`verify_minute_chip.py:139`；`oskh_factors/chip/core.py:430`）。1–8 策略书无 `cyqk`。plan 未接入，正确。
- **涨跌停 / 停牌**：E-R2 与代码一致——20%=`300/301/302/688/689`，30% 北交=`920/430/83/87/88`，主板 10%，ST 名 5%，未知 `None`→skip（`market_layer.py:17-65`）。涨停禁买可卖（默认不 `forbid_all_trade_at_limit`）；跌停 defer。零量日删除（日线 `csv_daily_loader.py:83-84`；分钟 `ashare_bars.py:363-365`）。缺 bar 冻仓。
- **v1.2 勘误回填**：双账本、`n_days` 联合日历、None-limits 留存、六差异+价格列、compact/qlib 链、围栏改枚举——与代码一致，应保留。
- **Mode B**：`shares/=k` 仅 `unified_exit_modeb.py:418/648/801`；`rescale_position` 不动 shares（`csv_ledger.py:141-150`）。

**交叉核对**：同意 composer **R1 / R3**。composer **R2**（handoff 双 SSOT）成立，但 handoff §1.2 对 compact「保留」比 plan §7「或删」更准——应对齐 plan §7，不是只改 handoff。composer Y1 升级为本评 **R5**（会改 `execute_buy` 契约）。未采纳「docs 可原样合」：§7「或删」+ 帧契约未钉时，Codex 会按错误表实施。

---

## 必查盲区（逐条）

| 项 | 结论 |
|----|------|
| T+1 / `n_days=0` | 三引擎买入日均不可卖 |
| 日线止盈 | 默认 `pending_exit` 次日开；`open_board` 当日收盘 |
| 未来 bar | 持仓定价未见前瞻 close；v7 ST 名窗末非 PIT（plan 已记） |
| 复权 | 成交/均线默认 none；未套 chip front |
| 盈筹 | 不适用，未进 1–8 |
| 涨跌停 / 北交 / ST | 已建模；未知 skip；P3 PIT 后置合理 |
| 包边界 | 未把 LEBS / MockQMT / `presets.py` 当本仓实现 |

---

## 总评

方向对、守界清、对抗勘误该留的都留了。阻塞点是 **切片 A 的帧 / compact / topk 共享加载 / 共享 cache 四件事没钉死**，加上 **切片 B 把谓词写进 `execute_buy`** 和 **围栏测无文件名**。这些会让第一船改成交数字或假绿。

**是否可进实现：不可。** 人裁 P1–P5 之前本就不应编码；即使按建议默认 P1=A，也须先改 plan+handoff 的 R1–R6 再交 Codex。修完后 A–C 可开工，风险可控。
