<!-- agent=cursor:auto cmd-prefix=/home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/node /home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/index.js --model auto -p --output-format text --trust -f --mode ask --workspace /workspace/wt-p3-fees-review <prompt> -->
## 评审：`plan-industry-align-p3-fees-2026-09-19.md`（v0.3.1）

并行 `_parallel/*` 尚无完整评审正文（仅 prompt 壳），以下独立取证。`IMPLEMENTATION_BASE=f548cc2…` 与当前 `origin/master` 一致（只读 `git rev-parse`）。本 plan 无 timeout/并发安全阀，未跑该类实验。

---

### 🔴 必须修

**R1 · E-r2-02 回填未完成：§2.4 缺可锁定的两 lot 数值 oracle**  
Host errata 要求 “two-lot **numeric** example”；现稿只有定性句（“两次 floor”“总量可不等”），Slice B 却写 “locks the *documented* as-built totals”——文档未给出 totals → 实现无验收靶。

代码算术（已用 `trade_commission` 复核）：两 lot×100 股×10 元、卖侧 15bp/min5 →

- 书路径：两次 `_sell` → `2 × max(1.5, 5) = 10`
- v7：一次 `credit_sell(2000)` → `max(3, 5) = 5`

```242:245:backtest/research/csv_ledger.py
def _sell(st: SimState, code: str, pos: Position, px: float, day, reason: str) -> None:
    notional = pos.shares * px
    comm = trade_commission(notional, st.sell_cost_rate, st.min_cost)
```

```223:242:backtest/research/csv_minute_backtest_v7.py
def _sell_lots(...):
    ...
    state.cash += fee.credit_sell(sold * price)
```

**要求**：在 §2.4（或 Slice B）写死上例期望值 + 锚点；否则 E-r2-02 仍未闭合。

**R2 · Slice B「DEFAULT_SCHEDULE is BILATERAL_10BP」不足以钉书引擎默认费率**  
书/分钟热路径扣费走 `SimState.buy_cost_rate/sell_cost_rate/min_cost`（默认绑 `COMMISSION`），**不**经 `FeeSchedule` 对象：

```87:89:backtest/research/csv_ledger.py
    buy_cost_rate: float = COMMISSION
    sell_cost_rate: float = COMMISSION
    min_cost: float = 0.0
```

`DEFAULT_SCHEDULE` 主要服务 v7。只钉 `is` 身份会漏「分钟/日线默认 = SimState 三字段」。Slice B 须并列：`SimState()` 三字段 == `COMMISSION/COMMISSION/0`，且与 `DEFAULT_SCHEDULE` 数值同构（identity 仅对 v7/模块指针）。

---

### 🟡 应修

**Y1 · §2.1 行号漂移（行级精确性）**  
| Plan 锚点 | 实际 |
|---|---|
| `ashare_fees.py:24` `trade_commission` | **def 在 :23**；:24 是 docstring |
| `FeeSchedule` `:34` | `@dataclass` :34；**class :35** |

其余消费锚点（daily `:272-280`/`:683-685`、ledger `:211`/`:244`、loop `:287-289`、v7 `:204`/`:225`/`:279`、fence `:46-48`）核对通过。

**Y2 · §1 历史引用偏一行**  
称 refactor `:131-132` 记 P3/P4；该处实际是 **P2 + P3**，P4 在 `:133`。应改为 `:132-133`（或写清 P2–P4）。

**Y3 · 「不新增 trades.csv commission 列」易与 as-built 混淆**  
书路径 `trades` 字典**已有** `commission`，`write_run_artifacts` 整表落盘：

```229:230:backtest/research/csv_ledger.py
            "commission": comm,
            "reason": reason,
```

```149:150:backtest/research/csv_artifacts.py
    pd.DataFrame(st.trades).to_csv(
        out_dir / "trades.csv", index=False, encoding="utf-8"
```

v7 `_event` **无** commission 字段（`:196-199`）。§2.5 应写清：as-built 书产物已有列；δ1 不改 schema / 不给 v7 补列；内存 oracle 可对书路径 `trades[].commission` 断言（≠ 旧 P2 的 session_phase 列）。

**Y4 · EOD_MARK 零佣金未入契约表**  
`csv_simulate_loop.py:337` 写 `"commission": 0.0`。建议 §2.4/2.5 一行钉住，避免 Slice B 把估值行当卖出扣费。

**Y5 · 研究费 SSOT 边界未点名 Mode A/B**  
`unified_exit_modea.py:21` 直接 `COMMISSION`，用 `(1±COMMISSION)` 线性近似，**不走** `trade_commission` floor，也不在本 plan freeze/热路径清单。δ1 应显式「parked / 非 CSV 书引擎消费面」，防后人把 Mode A/B 当 fee SSOT 第二实现。

**Y6 · Slice B 可复用却未点名的现成接线测**  
`tests/test_qlib_bin_daily.py:129-135` 已对 `execute_buy` + qlib rates 做 cash/commission 数值钉。Quick suite 可引用/扩展，避免只扩公式单测。

**Y7 · §8 冻结声明已收窄（E-r2-03 方向对），但 path-allowlist 仍 optional**  
小团队可接受；实施 handoff 建议把 “仅 docs/ + data-free tests/ + freeze 集” 写成 **硬门**（一次 `git diff --name-only`），否则 `ashare_bars`/`csv_daily_loader` 仍可在十文件零 diff 下改窗口/零量过滤（adv r2 D-03 仍成立，只是 claim 已不再假装锁住它们）。

---

### 🟢 可选

- OSS 类比表保持 “analogy only”——好；可再点一句 qlib Exchange 仅对应 `--qlib-cost` 分支，非默认。  
- `test_ashare_fees` 的 ledger re-export 依赖 `csv_ledger` 的 `import trade_commission` 副作用，可注明，防误删 import。

---

### ✅ 做对的地方

- 单船 δ1 + P1/P2/P4 停放；人裁 P3.1/2/3=A/A/A 与 as-built 一致。  
- 消费地图正确：日线 `--qlib-cost` 可覆盖；分钟无 override、吃 `SimState` 默认；v7 显式 `FeeSchedule`。  
- F-R4/P3.2 commission-only + fence 禁 `trade_fee_policy` 与 `engine-ashare-correctness.md:13`、fence 测试一致。  
- E-r2-01/03/04/05 主方向已回填；§8 gate 脚本均为真实路径；无 ghost script。  
- 生产 freeze 含 session/market/artifacts，避免借费用船改 T+1/涨跌停/产物 schema。

---

### 本仓必查盲区（本船范围核对）

| 盲区 | 结论 |
|------|------|
| T+1 / `n_days=0` | 卖前 `t1_sellable`（`buy_date < session`）；买入日不可卖。δ1 冻结 `ashare_session`，不改。 |
| 日线止盈时点 | `pending_exit` → 次日可卖 open（`csv_daily_backtest.py:329-333`）。非费用船。 |
| 复权 | 默认 `dividend_type=none`；本 plan 不碰。 |
| 盈筹 `cyqk` | 未引入 1–8 书。OK。 |
| 涨跌停/停牌 | 冻结 `market_layer`/`ashare_session`；档位仍以 correctness E-R2 为准。 |
| 包边界 | 研究 `ashare_fees` + fence；不拉 LEBS/MockQMT/`presets`。OK。 |

---

### 总评

v0.3.1 方向正确、主锚点大体可编码，adv r2 大半已吸收；**在补上两 lot 数值 oracle，并纠正「DEFAULT_SCHEDULE identity ≠ 书引擎默认」之前，不宜进 Slice B。** Slice A 文档整理可先做。  
**是否可进实现：有条件否（先修 R1/R2，再开 A→B→C docs/tests）。**
