<!-- agent=cursor:auto cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\index.js --model auto -p --output-format text --trust -f --mode ask --workspace E:\PycharmProjects\MyQuant-backtrader <prompt> -->
并行目录里其余评审员文件仍只有 prompt 壳、无正文，以下独立取证完成。

---

## 盲区核对（摘要）

| 盲区 | 结论 |
|------|------|
| T+1 / `pending_exit` | 本 plan 不改卖核；现码买入日 `n_days=0` 不可卖，日线止盈记 `pending_exit`、次日开盘卖（`csv_daily_backtest.py:332-338`）。无未来 bar。 |
| 复权 | P-R7 锁 `none`；加载 `dividend_type=none`（`:237-238`）。 |
| 盈筹 | P-R7「不适用」；不进 1–8。 |
| 涨跌停 / 北交 / ST | E-R2 已锁；R0 无名按前缀、不当 E-R2 验收——正确。 |
| 包边界 | 落点均在 `backtest/research/` + `scripts/data/`；禁 LEBS/`presets`/Cerebro——正确。 |
| 超时/安全阀 | 本 plan **无新增** timeout/budget/async；既有 `ThreadPoolExecutor` 属加载现状，非本轮设计。未做实验（无可测新阀）。 |

行号抽检：`load_pool_name_map` L68–89、`run` 日 L518 / 分 L805、加载无 `volume` 日 L213 / 分 L156——与代码一致。

---

## 🔴 必须修

### R1. `name_asof` 形式化谓词写成 `max{name:…}`，会误导成「名字字典序 max」

```76:76:docs/backtest/plan-pool-pipeline-r0r1-2026-09-12.md
| **P-R2** | **谓词**…`name_asof(code, ds) = 当日非空名，否则 max{name : ymd<=ds 且非空}`…
```

同条又写 `last_seen` / `禁止无上界 max`（指日期上界）。集合记号 `max{name:…}` 在实现时极易被读成对 **name 字符串** 取 max，而非 **argmax_ymd**。  
**应改成**（择一写进契约）：

- `name_asof(code,ds) = name[ds] if 非空 else last_seen[code]`，`last_seen` 仅在 `ymd≤ds` 且非空时覆盖；或  
- `name of (max ymd ≤ ds with nonempty name)`。

否则 B 切片与 `pool-csv-contract.md` 会再次出现「后日赢换皮 / 字典序」类实现事故。

### R2. C 落地时「≡缺 K」未钉死 **剔除点**，净值路径会漏改

```75:76:docs/backtest/plan-pool-pipeline-r0r1-2026-09-12.md
…`last_close_mark` 公式保持「缺行 → 昨收」；volume=0 日由调用方按缺行处理，不把零量 close 标进净值…
```

现净值直接：

```146:155:backtest/research/csv_ledger.py
def last_close_mark(df, day, fallback: float) -> float:
    ...
    if day in df.index:
        return float(df.loc[day]["close"])
```

交易环「缺行」是 `day not in index → continue`（含追买不 pop，`:402-403`）。若 C 只在买卖分支加 `volume==0` 判断、**仍把该日留在 index**，则 `last_close_mark` / EOD_MARK 仍会吃零量 close，违反 P-R1。  
**须在 plan 写死**：加载后 **丢弃 `volume==0` 行**（或等价地从不进入 index），使「≡缺 K」对交易环与净值环同一谓词；禁止「双路径（交易跳过 + index 仍在）」。

---

## 🟡 应修

### Y1. `pool_names` 与 `pool_names_by_day` 同时传入时优先级未锁

P-R2 只说「只加可选 by_day；扁平类型不变」。测试已有整窗扁平 `*ST`（`tests/test_csv_daily_backtest.py:782`）。若两者皆非 `None` 未定义优先级，易出现「以为在测 as-of、实际整天一张表」。  
**锁**：`pool_names_by_day is not None` → 只走 as-of；否则走扁平（测试冻结语义）。

### Y2. 空名单元格不得清空 `last_seen`

现生产合并已是 `if name:` 才写入（`csv_pool.py:87-88`）。谓词写了「当日非空名」，但 B 的三条单测未覆盖「D2 有码、名称列空 → 仍用 D1 名」。补一条，避免实现写成 `names[code]=""` 后主板档被抬成「无 ST」却丢了历史 ST（或反之）。

### Y3. C 默认文档降级时，HELP / E-R4 必须改成「仅缺行」，避免文档双 SSOT

```143:143:backtest/research/csv_daily_backtest.py
  停牌：冻仓；净值用最近有 K 的 close，不用成本价冒充。
```

```27:27:docs/backtest/engine-ashare-correctness.md
| **E-R4** | 停牌仍冻仓。…
```

与「加载器不读 volume」（`:213`）并存时，读者会以为 volume=0 已冻。P-R3 要求改文档——**完成定义应写明改写句**：例如「E-R4 = 当日无 K 行；湖若写 volume=0 现热路径仍当正常日（已知失真，见 plan §6）」。

### Y4. `last_seen` 推进键 = 名单文件日，不是 `calendar ∩ 有买卖`

日历来自 bars 并集（`build_calendar`）。若只在「当日有持仓处理」时 merge 名称，极端日（全日无该码 K、但仍有池文件）可能漏推进。B 实现说明应写：按 `sorted(by_day keys ≤ ds)` 或「每个日历日开盘前先 ingest 当日池名」。

### Y5. R0 验收 `--start 20260303` 与窗含 03-02 的关系写一句

P-R4：空列表不写文件；P-R5 从 03-03 跑。合理，但应注明「03-02 无 CSV、非漏跑」，避免实施把 start「修回」03-02 却对空窗困惑。

---

## 🟢 可选

- `.gitignore` 用 `exports/r0_*/` 或 `exports/r0_*` 比笼统 `exports/` 更窄（当前仓内尚无其它 exports 用途，风险低）。
- C 即使默认降级，实施阶段仍建议跑一次同路径只读探测并把「未检出 / 检出」写进 `engine-ashare-correctness.md`（plan 已倾向如此，可当硬完成定义）。
- 无名 ST 前缀列举补上 `302/689` 与 `market_layer._BOARD_20` 对齐（行为已由 `board_limit_pct` 覆盖，仅文档完备性）。

---

## ✅ 做对的地方

1. **后日赢**诊断正确：扁平并表 + 一次注入（`csv_pool.py:68-89`，日 `:518`，分 `:805`）；`test_load_pool_name_map_keeps_st_column` 正是 later-wins。  
2. **P-R2 `ymd≤ds` + 禁无上界 max + 三条单测**（含「后日 *ST 不得污 D2」）对准 A 股 as-of 名称 / ST 5% 档，是本轮最大正确性收益。  
3. **C 默认可降级**：加载确无 `volume`；不与 D 互验；禁止筹码/`StockDataReader`——符合 path-SSOT。  
4. **R0 胶水**：`scripts/data/`、单源 `持仓标的列表:`、不写 `stock_pool/`、不喂 v7、不当净值/档位验收——包边界干净。  
5. **validate 严格 / parse 宽松 / `run()` 不 Exit**：保住现网带后缀 CSV（`_cell_to_bare` search），同时给胶水 fail-closed。  
6. **禁改** `execute_buy`/`_sell`/`limit_pct`/`presets`/卖点：与 `engine-positioning-ssot.md`、E-R* 锁一致。  
7. **复权 none / 盈筹不适用** 写死，避免筹码 front/`cyqk` 渗进 CSV 书。

---

## 总评

v1.1 在对抗回填后范围清楚、SSOT 对齐良好，**B（ST as-of）+ D（R0 管道）值得做**；C 降级策略对小团队正确。  
修掉 **R1（谓词记号）** 与 **R2（volume=0 必须在加载侧≡缺行）**，并补上 Y1 优先级后，**可以进人裁「按 plan 实施」**；在此之前不宜开写业务代码。
