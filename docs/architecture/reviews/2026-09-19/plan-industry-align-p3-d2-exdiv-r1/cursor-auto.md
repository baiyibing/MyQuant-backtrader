<!-- agent=cursor:auto cmd-prefix=/home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/node /home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/index.js --model auto -p --output-format text --trust -f --mode ask --workspace /workspace/wt-p3-d2-exdiv-plan <prompt> -->
# 评审：P3 δ2 ex-div / lot-cost rescale plan v0.2

对照 `IMPLEMENTATION_BASE=1ad010c…` 源码与 CI 路径取证。并行目录中 **codex 已完成**；其 R1/R2/R3/R4 经复核成立，下文引用并补 SSOT/行级项。本方案无 timeout/budget/并发设计，**无对应时限实验**（N/A）。

---

## 🔴 必须修

### R1｜合成链 API 名写错：`load_exdiv_rates` 不存在（同意 codex R1）

`plan:66`、`:185` 写 `load_exdiv_rates`；生产与测试均为 `load_exdiv_ratios`（`exdiv_map.py:220`、`__all__:349`；`tests/test_exdiv_map.py:44`）。adversarial errata 原文用对名，v0.2 回填写错——实现会直接 `ImportError`。

### R2｜B1「绝不走真实 resolver」与 loader 双路径默认不一致（会误导 data-free）

B1（`plan:184`）要求合成 parquet + 不走真实 resolver，但未钉死**两个**显式路径。未传参时各自回落 `resolve_source_parquet`：

```246:253:backtest/research/exdiv_map.py
    adj_path = Path(adj_factor_path) if adj_factor_path else resolve_source_parquet(
        "adj_factor.parquet"
    )
    ex_path = (
        Path(ex_date_index_path)
        if ex_date_index_path
        else resolve_source_parquet("ex_date_index.parquet")
    )
```

只 stub 其中一个 → 另一个仍解析湖根（未配置则 `UnconfiguredDataRootError`，`data_root.py:154-155`）。B1/B2 须写明：`load_exdiv_ratios(..., adj_factor_path=..., ex_date_index_path=...)` 两路径皆显式。

---

## 🟡 应修

### Y1｜P3δ2.5=A 保留 minute/v7「后复权日线 × 仍加载 map」活脚枪（经验取舍）

日线 `run()` 在 `use_qlib_bins` / `dividend_type!='none'` 时置 `exdiv=None`（`csv_daily_backtest.py:585-588`）；分钟始终 `load_exdiv_rates`（`csv_minute_backtest.py:883`），且 `--qlib-day-root` 会迫使 `daily_source=qlib_day`（`:968`）。`qlib_day` dump 为后复权（`qlib_bin_daily.py:6`），分钟多为 none（`qlib_bin_1min.py:4`）。对已连续域昨收再乘 k → 档位/涨停门错位，属「会亏大钱」级混域。

计划如实记录（`:75-80`、B6），但推荐全 A 只契约化、不 fail-closed。小团队 + 模拟柜台一次到位：人裁时至少加窄约束（CLI/入口拒绝 `daily=qlib_day` 且仍加载 map，或强制 `exdiv=None`），否则 B6 须把该组合标为**危险组合必测 + README 红字**，不能只当「差异照录」。

### Y2｜B6 入口/stub 清单不足（同意 codex R2）

- 书 minute：`qlib_1min` vs lake 分叉 loader（`csv_minute_backtest.py:852-872`）。
- v7 无 `run()`，CLI 为 `main`（`:547`）；非空 pool 必调 `load_index_daily`（`:577-579`）并写产物（`:586-588`）。
- 整 stub `load_limit_context` 会 concurrent 绕过「确实加载 map」证明；空 `codes` 时不调 loader（`ashare_session.py:99`）。

B6 需逐入口 patch 消费模块绑定名，并隔离指数 loader / writer。

### Y3｜B5 数值 oracle 不能直接当 v7 公开入口初态（同意 codex R3）

`plan:98` 的 100 股 / cost=10 / cash=2000 适合书 helper；`simulate_v7` 无 Position 注入（`:277-280`），试仓 `NAME_BUDGET×0.2`（`csv_minute_backtest_v7.py:57-58` + `strategy7_rules.py:22`）在 px=10 时约 2 万股。B5 须分层：helper 用小数值；公开 v7 用事件前快照比 Δ。

### Y4｜缺「pending_exit 跨除权日」公开日线 pin（同意 codex R4；补 T+1 盲区）

日线 pending 先于重评卖点，用当日 open + **已映射**跌停门（`csv_daily_backtest.py:308-338`）。B2 未钉：D−1 写 pending → D 除权后正常开盘成交 / 开盘跌停续 defer。与「字符串字段保留」不是同一证明。

### Y5｜域声明文件未进冻结表

`§2.3` / B6 依赖 `qlib_bin_daily.py` / `qlib_bin_1min.py` 的域约定，但 `§9` 冻结表未列。全路径审计能兜底，建议显式列入，避免「表内零 diff = 域 SSOT 未动」的误读。

### Y6｜§8.2 与 CI 同构表述略漂移

四 gate 在 `.github/workflows/python-tests.yml:38-43`（**pip 之前**）；`:49-56` 是 install/numba/pytest。计划 `:226` 把 gates 归到两段合并叙述，且 §8.2 先 `import pandas…` 再跑 gate——路径对、顺序/行号归因易误导「逐字同构」。建议改成「同路径、允许顺序差」并修正行锚。

---

## 🟢 可选

- Non-goals 补一句：不涉及盈筹/`cyqk`（仓内无 `backtest/chip_indicator.py`；筹码筛选仍 0–1 阈）。
- Slice A 同步 `engine-ashare-correctness.md` E-R6「仅 `run()` 加载」→ 写明 minute/v7 始终加载 + daily 连续域跳过差异。
- B4 夹具禁止对 `mapped*0.9` 用 float 自算档位：`1.65*0.9` 浮点 → `round_fen` 得 **1.48**，Decimal/`limit_prices('600000.SH',1.65)` 得 **(1.82,1.49)**（已复现）。计划要求送入真实档位函数是对的，宜在 B4 明文禁止 float 旁路。

---

## ✅ 做对的地方

- 范围清晰：docs-only、零生产 diff、经济残留 deferred、不 redo E-R6；与 δ1 `:98`/`:134`、next plan P1–P4 挂起一致。
- 事件门 / `k=prev_cum/cum` / 噪声 `j<=5e-3` / fallback `j>1e-2` / 非幂等「一次性」——与 `exdiv_map.py:28-30,294-316`、`csv_ledger.py:147-156` 一致。
- 书 cost/peak only vs v7 多参考字段分叉、E-d2-01/02/03/06/08 证据限度写清。
- `test_ashare_session.py:21-33` 算出 mapped=9.5 却用 raw 定档——计划正确标为证据缺口，B4 补半分链。
- path-SSOT：解析失败 vs 缺文件降级区分正确（`plan:82` ↔ `exdiv_map.py:246-272`）。
- F-R10 / 冻结表为 δ1 十文件超集；不混 LEBS/Cerebro/Mode A/B。

---

## 必查盲区（逐条）

| 盲区 | 结论 |
|------|------|
| T+1 / pending | 买日不可卖：`t1_sellable`（`ashare_session.py:39-41`）；分钟另有 `n_days<1`（`csv_minute_backtest.py:276`）。日线普通止盈→`pending_exit` 次日开；`same_bar` 仍可当日收。见 Y4。 |
| 复权 | 默认 `dividend_type=none`（`ashare_bars.py:88`）；未把筹码 front 套进 CSV 书；混域脚枪见 Y1。 |
| 盈筹 | 本刀未引入；建议 Non-goals 显式排除。 |
| 涨跌停/停牌 | 继承 E-R2（`market_layer.py:17-64`）；涨停禁买/跌停禁卖在 `ashare_session`；缺 bar 不回放已披露。 |
| 包边界 | 锚定 `backtest/research/`；F-R10 正确。 |

---

## 与同行交叉

- **同意** codex R1（API 名）、R2（B6 stub）、R3（B5/v7 股数）、R4（pending×除权）。
- **补充**：R2 双路径 resolver；Y1 混域脚枪人裁；Y5/Y6 冻结与 CI 行锚；B4 float 半分实验。

---

**总评**：v0.2 作为 as-built 契约稿质量高、多数锚点准确；**修正 R1/R2 后，人裁 GO 可进 docs + data-free tests（Slice A→B→C）**。不可据此改生产行为或宣称经济守恒已闭合；P3δ2.5 建议在「纯文档 A」之上至少加混域 fail-closed/红字必测。
