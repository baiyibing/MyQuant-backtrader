<!-- agent=cursor:kimi-k3-high cmd-prefix=/home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/node /home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/index.js --model kimi-k3-high -p --output-format text --trust -f --mode ask --workspace /workspace/wt-p3-d2-exdiv-plan <prompt> -->
grok 仍在进行中，不等待。codex 与 cursor-auto 已完成并已交叉核对。以下是我的评审。

---

# 评审：P3 δ2 ex-div / lot-cost rescale plan v0.2（kimi-k3-high，侧重实验验证）

基线核对：HEAD=`796b2354…`，IMPLEMENTATION_BASE=`1ad010c…`（PR #121 merge）确为分支起点，`git diff --name-only` 显示基线后仅 plan + codex-adv-r1 评审目录（tracked）+ 本轮 r1 评审目录（untracked），F-R1 路径纪律本 PR 自身合规。

## 实验验证摘要（可复现，scratch 在 /tmp，未触碰仓库）

环境：系统 python3.13 + `/tmp/p3d2env`（venv 装 pandas/numpy/pyarrow/pytest），仓库根 `sys.path` 直跑真实生产函数。

**Exp1 事件门/k 方向/E-d2-01**（`/tmp/p3d2_exp1_event_gate.py`：合成 parquet 两路径显式传入 `load_exdiv_ratios`）原始输出：

```
[float] j(200->201)=0.005 == NOISE_EPS(0.005)? True; <= ? True
[float] j(100->101)=0.01 == FALLBACK_JUMP_EPS(0.01)? True; > ? False
[A ex+j==0.5%] map: {} skipped: 0            => 噪声带等号不修正 ✓
[B ex+j=1%]    map: {'600000.SH': {'20250902': 0.9900990099009901}}  = 200/202 ✓
[C noex+j==1%] map: {}                       => 严格 > 成立 ✓
[D noex+j=2%]  map: {... '20250902': 0.9803921568627451} = 100/102 ✓
[E ex+factor drop] k=2.0                     => k=prev_cum/cum，可 >1 ✓
[F ex-day NaN, recover 09-03] map: {'600000.SH': {'20250903': 2.0}} skipped: 1
```

**E-d2-01 实证**：除权日因子 NaN 时，k=100/50=**2.0** 落在恢复日 09-03（对最后有效前行取值），除权日记 skipped=1。plan:66 的残留声明不仅成立且可量化——恢复日行情已在新域，存量 lot 会被再乘一次 2.0，属严重错域。

**Exp2 Decimal 半分链**（`/tmp/p3d2_exp2_decimal.py`，真实 `session_prev_close`/`session_limit_prices`）：

```
mapped prev_close = 1.65；session_limit_prices(600000.SH, 1.65) = (1.82, 1.49)  ✓ plan B4 oracle 值正确
raw-domain limits = (3.63, 2.97)；ST 5% on 1.65 = (1.73, 1.57)
```

**Exp3 非幂等**：`rescale_position(pos, 0.5)` 两次 → cost 10→5→**2.5**（plan:60「重复调用会重复相乘」✓）；k=0/−1 早退不变 ✓（`csv_ledger.py:152-153`）。

**Exp4 边界输入**（新发现）：`k=inf` **穿过** `k_for`/`mapped_prev_close` 守卫（仅排 `k<=0` 或 NaN，`exdiv_map.py:89-91`/`:104-106`）→ mapped=inf、did_map=True。loader 侧 `:306`/`:314` 有 `math.isfinite` 拦截，故仅手工注入 map 可触发。plan:64「仅排除非正数/NaN」措辞**精确属实**。

**Exp5 §2.4 数值 oracle**（真实 `daily.simulate`，fees=0，total_cash=3000，quota=1000）：

```
trades: BUY 100@10.0 (11-03)；EOD_MARK 5.0（末日标记，无 reason 键）
equity: 3000.0 → 3000.0 → 2500.0 → 2500.0 → 2500.0
held: shares=100 cost=5.0 peak=5.0；cash=2000.0
stats: exdiv_adjusted_lots=1 mapped=1
```

plan:98 oracle 完全复现：重标定 cost 10→5、股数/现金不动、权益 3000→2500，差额=100×10×(1−0.5)=500 ✓。**副产物**：EOD_MARK 行无 `reason` 键（`csv_simulate_loop.py:411-421`），直接印证 B5「不把 EOD_MARK 当真实 SELL」——我首版脚本对它取 `t["reason"]` 即 KeyError。

**Exp6 float vs Decimal 分岔**（复核 cursor-auto 🟢 断言）：

```
float 1.65*0.9 = 1.4849999999999999 → round_fen = 1.48
limit_prices(600000.SH, 1.65) = (1.82, 1.49)   # Decimal HALF_UP
```

cursor-auto 断言属实：B4 夹具若用 float 自算跌停价会得到 **1.48** 的错误期望值。

## 🔴 必须修

**K-R1｜`load_exdiv_rates` 不存在（同意 codex R1 / cursor-auto R1，独立复核确认）。** plan:66、:185 两处要求「经真实 `load_exdiv_rates`」；仓内只有 `load_exdiv_ratios`（`exdiv_map.py:220`、`__all__:349`；五个生产调用点全部用 ratios 名）。照此实现直接 `ImportError`。adv-r1 errata 原文用名正确，系 v0.2 回填笔误。改为 `load_exdiv_ratios` 即可，无需别名。

## 🟡 应修

**K-Y1｜B1「绝不走真实 resolver」须钉死双路径（cursor-auto R2 成立，补实验旁证）。** `exdiv_map.py:246-253` 两个路径参数各自独立回落 `resolve_source_parquet`；只传其一时，另一个在已配置湖的机器上会**静默读真实 parquet**（未配置则 `UnconfiguredDataRootError`，`data_root.py:154-157` fail-loud）。我的 Exp1 正是两路径皆显式才做到 hermetic。B1 应写明 `load_exdiv_ratios(..., adj_factor_path=..., ex_date_index_path=...)` 缺一不可。

**K-Y2｜P3δ2.5=A 保留 minute/v7 混域脚枪（同意 cursor-auto Y1，补一处行级证据）。** 分钟 `run()` 无条件 `load_exdiv_ratios`（`csv_minute_backtest.py:883`），且 CLI `--qlib-day-root` 强制 `daily_source="qlib_day"`（`:968`）；`qlib_day` 为后复权 dump（`qlib_bin_daily.py:6`），对已连续域昨收再乘 k → 档位/止损距错位，属「会亏大钱」级。plan:75-80 如实记录并冻结，结构上有人裁出口（P3δ2.5 的 B）。按「模拟柜台激进一次到位」原则，**建议人裁把 P3δ2.5 提到 B 或 A+窄约束**（入口检测到 `daily=qlib_day` 且 map 非空即 fail-closed），至少 B6 把该组合标为危险必测 + 文档红字，而非「差异照录」。

**K-Y3｜B6 stub 清单不足（同意 codex R2 / cursor-auto Y2）。** v7 无 `run()`，入口是 `main()`（`csv_minute_backtest_v7.py:547`），非空 pool 必调 `load_index_daily`（`:577-579`）并写产物（`:586-588`）；书 minute 两源走不同 loader（`csv_minute_backtest.py:852-872`）；整 stub `load_limit_context` 会绕过「map 确实加载」的证明，且空 codes 时根本不调 loader（`ashare_session.py:99`）。B6 需逐入口列 patch 点（消费模块绑定名）、非空合成 pool、隔离指数 loader/writer。

**K-Y4｜B5 oracle 在 v7 公开入口不可达（同意 codex R3，行级复核确认）。** `simulate_v7` 无 Position 注入（`:277-282`），试仓=`NAME_BUDGET×TRIAL_FRACTION`=100万×0.2（`strategy7_rules.py:22`），px=10 时自然买 20,000 股；cash=3000 会直接 `skip_cash`。B5 须分层：小数值 oracle 给书侧（我的 Exp5 证明书侧公开 `simulate` 可达），v7 用自然买入 + 事件前快照比 Δ。

**K-Y5｜缺 pending_exit × 除权日 pin（同意 codex R4，复核确认）。** `csv_daily_backtest.py:333` pending 分支用当日 open + 已映射跌停门、优先于重评卖点；且 `:404-407` `same_bar` 分支当日收盘成交、否则写 pending——「字段保留」不等于「成交顺序正确」。补两向量：D−1 写 pending → D 除权正常开盘成交 / 开盘跌停续 defer。

**K-Y6｜冻结表缺域声明读取器（同意 cursor-auto Y5）。** §2.3/B6 的域约定依赖 `qlib_bin_daily.py:6` / `qlib_bin_1min.py:4` 的 docstring 声明，二者不在 §9 冻结表。建议显式列入，避免「表内零 diff」被误读为域 SSOT 未动。

## 🟢 可选

- **K-G1｜inf 穿透 pin**：loader 永不产 inf（`exdiv_map.py:306`/`:314` `isfinite`），但手工注入 map 的 inf 会穿过 `k_for`/`mapped_prev_close`（Exp4）。B1 加一条 pin 把「inf 透传」钉为有意识契约，防未来有人「顺手修」改行为。
- **K-G2｜B2/B5 夹具陷阱（实验发现）**：v1 止盈 `drawdown=(peak−px)/(peak−cost)`（`strategy1_rules.py:40-42`）在 rescale 后 peak≈cost 时分母趋零，**任何微小回撤即触发** `profit_take:drawdown:50`——我的 flat 夹具 high 仅超 cost 0.05 就在次日被卖。多事件/复合 k 夹具必须严格控制 high ≤ cost，否则断言被止盈干扰。
- **K-G3｜B4 明文禁止 float 旁路**：Exp6 证明 float 自算跌停得 1.48 ≠ 真实 1.49；B4 应写死「期望值只允许来自真实 `limit_prices` 调用」（cursor-auto 同类建议，我升级为应写明文）。
- **K-G4｜B5 pin 断言 schema 键集合**：EOD_MARK 无 `reason` 键（Exp5 副产物），pin 应显式断言键集而非仅「不当 SELL」。
- **K-G5｜Non-goals 补盈筹排除**：`backtest/chip_indicator.py` 不存在（评审 prompt 的 SSOT 引用已过时；筹码研究码在 `backtest/research/chip/`，0–1 阈）。本刀与 cyqk 无关，建议 Non-goals 写一句显式排除。
- **K-G6｜§8.3 路径白名单未含本轮 r1 评审目录**（当前 untracked）；若随 PR 提交需扩白名单，否则保持不入库。

## ✅ 做对的地方（实验/读码双重确认）

- 事件门四格、阈值等号语义、k=prev\_cum/cum 方向、k>1 可行——Exp1 全绿，与 `exdiv_map.py:294-316` 一致；plan:58 提议的 200→201 / 100→101 等号输入在 float 下精确成立，可直接作 pin。
- 「一次性=扫描前对存量 lot 缩放一次、helper 非幂等」——Exp3 + `csv_daily_backtest.py:300-327` / `csv_minute_backtest.py:586-636` / v7 `:316-340` 调用顺序全部属实。
- E-d2-01 因子恢复日错配——Exp1-F 实证 k=2.0 落恢复日，plan:66 的残留声明与「修复另案」定性准确，无夸大。
- §2.4 经济残留 oracle——Exp5 经真实引擎复现 3000→2500、股数现金不动，「(1−k) 结构性失真」表述精确（含「不能当固定百分比」的限定）。
- `test_ashare_session.py:21-33` 算出 mapped=9.5 却把 raw 送档位——证据缺口判定正确，B4 的 (1.82,1.49) 链经真实函数验证（Exp2）。
- 复牌测试 k 直接放复牌日（`test_exdiv_refprice_engines.py:313-337`）、v7 `:295` 混域夹具（分钟 100 vs 日收 50）、minute/v7 无连续域跳过（`:883`、v7 `:571`）、`qlib_day`≠`qlib_1min` 域声明——逐条复核属实。
- T+1 三引擎口径正确：书 `t1_sellable`（`ashare_session.py:39-41`）、分钟扫描器 `n_days<1` 拦截（`csv_minute_backtest.py:276-277`）、v7 按 lot 过滤（`csv_minute_backtest_v7.py:229-241`）；E-d2-07「同日 stop 只卖老 lot」与 `_sell_lots` 代码一致。
- F-R1–F-R11 自洽；冻结表确为 δ1 超集；不混 LEBS/Cerebro/Mode A/B；EOD_MARK 警告有代码根据。

## 必查盲区逐条

| 盲区 | 结论 |
|---|---|
| T+1/隔日 | 买日不可卖 ✓；日线普通止盈→pending 次日开、`same_bar` 当日收（`:404-407`），plan 未误概括；无未来 bar（昨收取自先前 closes，`csv_common.py:43`） |
| 复权口径 | 默认 none（`ashare_bars.py:88`/`:177`）；daily 连续域跳过保留；未把筹码 front 套入；混域残留见 K-Y2 |
| 盈筹率 | 本刀不涉及；`backtest/chip_indicator.py` 不存在（prompt SSOT 引用过时），建议 K-G5 |
| 涨跌停/停牌 | E-R2 档位含北交 30%/ST 5%/未知 fail-closed（`market_layer.py:44-64`）；涨停禁买/跌停禁卖在 `ashare_session.py:73-79`；缺 bar 键不回放已如实披露 |
| 包边界 | 全程 `backtest/research/`；无 LEBS/MockQMT/presets 误植；Cerebro 未复活 |

## 同行交叉核对

- **同意并独立复核**：codex R1（=K-R1）、R2/R3/R4（=K-Y3/Y4/Y5）；cursor-auto R1、R2（=K-Y1）、Y1（=K-Y2）、Y5（=K-Y6）。
- **纠正 cursor-auto Y6（部分误判）**：plan:226 的行锚 `:27-43`/`:49-56` 实际准确（setup-python `:28`、gates `:38`、install `:49`、pytest `:55`）；§8.2 先 import pandas 再跑 gates 的顺序差与 CI 不同，但四 gate 本身不依赖 pandas，无功能影响。降为 🟢 措辞建议即可。
- **我独有的实验增量**：E-d2-01 量化实证（k=2.0 落恢复日）、§2.4 oracle 真实引擎复现、inf 穿透（K-G1）、drawdown 夹具陷阱（K-G2）、float/Decimal 1.48≠1.49 分岔复现（K-G3）。

**总评**：v0.2 的 as-built 事实层质量很高——我抽查的 30+ 处 file:line 锚点全部属实，关键语义均经真实代码/实验复现；唯一硬伤是 K-R1 的 API 名笔误。**修掉 K-R1、落实 K-Y1 双路径写明后可进实现**（人裁 GO → Slice A→B→C，docs + data-free tests）；K-Y2 建议人裁认真考虑把 P3δ2.5 从纯 A 提为 A+混域 fail-closed，这是本刀范围内唯一「会亏大钱」级的活风险。
