<!-- agent=cursor:auto cmd-prefix=C:\Users\wangc\AppData\Local\cursor-agent\versions\2026.09.15-d2fe57e\node.exe C:\Users\wangc\AppData\Local\cursor-agent\versions\2026.09.15-d2fe57e\index.js --model auto -p --output-format text --trust -f --mode ask --workspace D:\PycharmProjects\MyQuant-backtrader <prompt> -->
# 评审意见 · `plan-ashare-engine-refactor-2026-09-18.md` v1.2

**侧重**：SSOT 一致性 + 行级精确性。平行目录仅 **composer-2.5-fast** 有完整意见（交叉引用）；auto / grok 未完成，不轮询。本 plan **无 timeout/budget/safety-valve 类设计** → 不做虚假 docstring 实验；并发仅沿用既有 `ThreadPoolExecutor` 加载（无超时承诺）。

---

## 🔴 必须修

### R1 · 切片 A 未钉 v7↔书帧消费契约（同意 composer R1，失败模式补正）

§5-A 要求 v7 默认改走 `load_minute_ohlc`，但消费端仍按 **compact 的 `date` 列**切片；书帧是 **DatetimeIndex + `ymd`/`hm`，无 `date` 列**：

```258:264:backtest/research/csv_minute_backtest_v7.py
def _day_frame_records(frame: Any, day: date) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    sl = frame.loc[frame["date"] == day]
```

```322:361:backtest/research/ashare_bars.py
def read_lake_minute_ohlc(...):
    """Book-engine lake frame: DatetimeIndex + open/high/low/close/ymd/hm."""
    # ... 产出 ymd/hm，无 date 列
```

compact 才显式造 `date`（`ashare_bars.py:159-168`）。按字面换 loader → 典型是 **`KeyError: 'date'`**（非整窗静默空跑；若被吞异常才变空切片假绿）。

**要求**：§5-A / §7 三选一写死——(a) 复用 1–10 `_slice_day`；(b) 改 `_day_frame_records` 认 `ymd`/DatetimeIndex；(c) 薄适配 `book→v7 records`。DoD 加「改造后合成窗非空 bar 计数 > 0」。§5-A「六差异·列」不够——须点名 **消费 API 列契约**。

### R2 · handoff 与 plan v1.2 双 SSOT（同意 composer R2）

Plan 头部以 handoff 为实施入口（plan:8），但 handoff 仍：

- 切片 B 标题「唯一 lot 日历」（`handoff…:62`），与 E-01「谓词统一、双账本保留」冲突；
- §3 围栏未列 11 文件枚举（`:81-85`），与 plan §5-C 冲突；
- 更危险：handoff §2.3 写死「`execute_buy`/`_sell`…涨跌停只调 `skip_buy_at_limit`/`defer_sell_at_limit`」（`:68`）。

**GO 前须同步 handoff 至 v1.2 语义**，否则 Codex 以 handoff 为准会误实施。

### R3 · 「只调 skip/defer」会把书引擎从 fail-closed 拧成 fail-open（升格 composer Y1）

`skip_*` / `defer_*` 在 `limits is None` 时返回 False（**放行**）：

```73:78:backtest/research/ashare_session.py
def skip_buy_at_limit(price: float, limits: tuple[float, float] | None) -> bool:
    return limits is not None and hit_limit_up(price, limits[0])

def defer_sell_at_limit(price: float, limits: tuple[float, float] | None) -> bool:
    return limits is not None and hit_limit_down(price, limits[1])
```

书引擎先拒 None 再解包（未知板 **整日不交易**）：

```257:260:backtest/research/csv_simulate_loop.py
        if limits is None:
            st.stats["skip_unknown_board"] += 1
            continue
```

且涨跌停判定在 **simulate 环**（`csv_daily_backtest.py:327-399`、`csv_minute_backtest.py:643-649`），**不在** `execute_buy`/`_sell`（`csv_ledger.py:194-276` 无 limits/T+1）。

若按 plan §5-B / handoff §2 把书侧改成「只调 skip/defer、且塞进 ledger」→ 未知板/缺昨收可静默开卖开买；并漏掉 `reserve_limit_up` / `forbid_all_trade_at_limit` / chase 等对 `hit_limit_up` 的用法（`csv_strategy_books.py:126` 默认 False；topk 才 True）。

**要求**：收窄为「T+1 → `t1_sellable`；买卖闸在**现有调用点**统一包装；书侧保持 `limits is None` 先拒；`hit_limit_*` 保留给 reserve/open_board/forbid_all；ledger 填单函数不强制吞谓词」。

### R4 · 切片 C「围栏测绿」无可执行测试锚（同意 composer R3）

现状 `tests/test_research_face_imports.py:110-119` 只 rglob 禁 **backtrader**；`engine.py:21-24` 仍 import `trade_fee_policy`（errata S2 已验）。§5-C 枚举正确，但未钉 **新测路径 / `SIMULATE_HOT_PATH` 常量表与 §5-C 字节级一致**。DoD「测绿」不可验收。

---

## 🟡 应修

### Y1 · P2 旗名 `--fees full` 与现网 `--qlib-cost` 冲突

现网对照费率开关是 `--qlib-cost`（`csv_daily_backtest.py:656,681-683`）→ `QLIB_PORTANA`。P2 新造 `--fees full` 且声明抄 `trade_fee_policy` 口径（近似，E-11 已认）。须写清：新旗 vs 扩展现旗；禁止两个 SSOT 名并存。

### Y2 · 缺码 cache 整仓合并门缺可复现验收（同意 composer Y2）

`ashare_bars.py:572-575`：`read_minute_cache(path, None)` 整读再 merge——E-07 事实成立。DoD「不得整仓物化」缺 fixture / 峰值或相对阈值 / data-free 近似测法。

### Y3 · 切片 D reason 桶映射仍非机器可读（同意 composer Y3）

未知前缀落 `sell_pos_trail`（`csv_ledger.py:271-272`）已钉；§5-D 仍无原则句。须给 yaml/tests dict 一行示例，否则宿主对照不可重复。

### Y4 · `minute_cache_path` 无新鲜度（E-15）挂 v7 后风险放大

仅 `(start,end)` 键（`ashare_bars.py:397-399`）。§5-A 应写「本船不改 = 已知限制」或文档化 `--rebuild`。

### Y5 · Mode A 第三套持仓未入正文（同意 composer Y5）

errata E-01 已提 `unified_exit_modea.Instance`；§5-B 只写双账本。脚注「Mode A 不进本船」防误并账本。

### Y6 · 一句话「唯一撮合核」vs A–C 实际交付

交付是谓词/加载收口，**双账本 + 双卖环 + 双费率 API 仍在**。建议改成「谓词与加载 SSOT 收口」，避免实施过度合并。

---

## 🟢 可选

- P5=A「薄包装」补允许改的 argv/exit 边界（adversarial 亦 abstain）。
- 围栏是否只读纳入 `market_layer.py`（经 session 间接）。
- 本 plan 无 timeout 语义；若日后给 loader 加 budget，须对 `ThreadPoolExecutor.__exit__→shutdown(wait=True)` 做单调时钟实验——**勿只信 docstring**。

---

## ✅ 做对的地方

| 项 | 结论 | 证据 |
|---|---|---|
| 三仓/包边界 | LEBS 只在 1.3；不复活 Cerebro；研究面 `backtest/research/` | plan §0.2–0.3、R1–R2；`engine-positioning-ssot.md` |
| T+1 / `n_days=0` | 买入日不可卖 | 日线 `n_days>=1`（`csv_daily_backtest.py:327,334`）；分钟 `can_sell=(n_days>=1)`（`:618`）；v7 `t1_sellable`（`v7:228`） |
| 日线止盈 | 非 same_bar → `pending_exit`，次日开卖 | `csv_daily_backtest.py:396-399`；`csv_ledger.py:74` |
| 未来 bar | 持仓用截至昨收/当日行；`day_bar_and_prev_closes` 无前瞻 | `csv_common.py:22-45` |
| 复权 | 链默认 `dividend_type=none`；未把筹码 front 套进书 | E-R5；`ashare_bars.py:177`；plan 仅名单管道提 chip |
| 盈筹 | **未**接入 1–8 书 | plan 全文无 cyqk/winner_ratio 进撮合 |
| 涨跌停/停牌 | E-R1/2/4；北交 30%/ST 5%/未知 skip；缺 bar 冻仓 | `market_layer.py:57-65`；日线无 K `continue` |
| 涨停可卖 | 默认 `forbid_all_trade_at_limit=False`，卖侧主拦跌停 | `csv_strategy_books.py:126`；日线 `:382-386` |
| v1.2 勘误 | E-01/02/04/05/06/09/16 与代码一致，应保留 | errata + plan §5 |
| 基线 tip | `a61b1ad` = #104 merge，与仓 HEAD 一致 | `git rev-parse` |

对 composer：**R1/R2/R3 同意**（R1 失败模式改为 KeyError 为主）；**Y1 升本评 R3**（fail-open 证据）；其余 Y 互为补集。

---

## 总评

**v1.2 守界与盲区对齐正确，对抗回填到位；阻塞编码的是切片 A 帧契约、handoff 双 SSOT、以及 skip/defer 误用导致的板档 fail-open。**  
**是否可进实现**：**docs 可合；编码不可 GO**——须人裁 P1–P5 + 修 R1–R4（至少 plan↔handoff 同步 + 帧适配写死 + 谓词落点/None 语义收窄 + 围栏测锚点）后再交 Codex。
