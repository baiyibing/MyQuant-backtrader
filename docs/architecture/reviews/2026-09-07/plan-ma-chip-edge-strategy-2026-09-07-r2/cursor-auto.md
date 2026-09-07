<!-- agent=cursor:auto cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.02-c22c1a3\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.02-c22c1a3\index.js --model auto -p --output-format text --trust -f --mode ask --workspace E:\PycharmProjects\MyQuant-backtrader <prompt> -->
# 评审：`docs/backtest/plan-ma-chip-edge-strategy-2026-09-07.md`（v3）

侧重：SSOT + 行级取证。已读 plan 全文、实现 `backtest/research/ma_chip_edge_backtest.py`、单测、r2 已完成票（kimi / claude / codex / `merge-consensus.md`）。`_parallel/` 下仅 cursor-auto stub，无其它并行正文可交叉。

## 本人实验（只读，可复现）

`PENDING_BUY_MAX_GAP_DAYS=4` + `MaChipEdgeStrategy` + `cheat_on_open=True, runonce=False`：

| ID | 设定 | 结果 |
|----|------|------|
| E1 | Fri 信号→Mon（gap=3） | BUY@Mon，周末放行 |
| E2 | 01-03 信号→01-24（gap=21） | `skip_buy(stale)`，无成交（**kimi/claude R1 已修，CONFIRMED**） |
| E3 | Wed→Fri 停 1 日（gap=2） | 仍 BUY（短缺口放行） |
| E5 | Wed→Mon（gap=5） | `skip_buy(stale)` |
| E4 | 买入日收阳但仍 `<SMA5` | 次日开盘卖（**codex R1 已修**） |
| E6 | 卖日出 edge | 仅 1 次 BUY，卖日不重入（**claude Y1 已锁**） |

`get_cyqk_c` 合成窗实测 ∈(0,1)。`hasattr(bt.Order,"Open") is False`。

---

## 🔴 必须修

本轮**无新的交易因果 / 前视 / 单位 / 复权级 🔴**。r2 三条架构 🔴（stale 买、买入日同评 SMA5、卖日不重入）已在 plan §2 与代码对齐，并经上表复现。

---

## 🟡 应修

**Y1（文档自洽）：§5 与文首/§7 矛盾**  
文首称已吸收 r1/r2（plan:3–8），§7 称架构 🔴 已吸收（plan:107）；§5 仍写「本轮不做 classic fan-out 第二轮（额度用尽/超时）」（plan:95）。r2 `merge-consensus.md` 已存在。元信息不一致，易让下游以为 r2 未闭环。改 §5 删除或改为「r1 未补票；r2 已跑并吸收」。

**Y2（口径精确性）：`T=D+1` 与「≤4 自然日的下一根 bar」混写**  
plan:30 同时锁「T=D+1」与「下一根 bar 且 gap≤4」。E3 证明短停牌时成交日是 **D 后第二根交易 bar**，不是下一交易日。实现 `ma_chip_edge_backtest.py:390-408` 与「下一根 bar + 自然日预算」一致，与字面 `T=D+1` 不完全一致。建议 §2 改成：「默认下一交易日开盘；若 feed 下一根 bar 距信号 ≤4 自然日则成交，否则 `skip_buy(stale)`（周末放行，长假/长停牌故意丢弃）」。

**Y3（统计窗 feed 截断，附议 codex Y5）：固定 14 自然日 warmup 会丢掉窗前末 edge**  
`run_one`：`warmup_from = stats_start - 14d` 再切片（`ma_chip_edge_backtest.py:508-510`），而 `mask_pre_window_edges` 故意保留窗前最后一日 edge（plan:46；同文件:240-248）。个股窗前停牌/长假 >14 日时，合法「窗内首日开盘买」被静默切掉。应用「窗前最后交易日」反推 feed 起点，或 plan 明文接受该损失。

**Y4（报表分母未定义，附议 codex Y4）**  
`mean_single_name_return` 对全部抽样（含 `n_buys=0`）取均值（`ma_chip_edge_backtest.py:544,630`）。plan:49 只列 `names_with_buy`，未定义分母。30 只框架下 mean≈0 易误读。§2 应锁定：全样本 / 触发样本双口径，或 summary 明示分母。

**Y5（§4 单测承诺 vs 落地）**  
§4 要求「D 与 D-1 都满足→不买」「D-1 NaN→不买」等 **cond 级**用例；现有单测大量手工 `edge` 列驱动（`tests/test_ma_chip_edge_strategy.py:85+`），`build_signal_frame` 路径在无股本时可能 `pytest.skip`（:67-68）。FSM 已较稳，信号链合成覆盖仍薄。按 plan「不依赖 F 盘」应 mock 股本，补 cond 连续 True / prev NaN 两条。

---

## 🟢 可选

- **G1**：chip 调用链仍依赖 `oskh_factors.chip.shares` 下划线 API（`ma_chip_edge_backtest.py:34-38`）；plan:14 写 `as_of_date=D`，实现是预置整窗 `turnover_rate` 后再 `adapt_columns`（此时 as_of 基本 noop，`core.py:51-58`）。研究可跑；公开 `cyqk_series_asof` 可留后续（同意 r2 降 🟢）。
- **G2**：`DEFAULT_CASH=1e6`（:46）未进 §2「组合」行；`--end` 默认 today 影响输出目录复现（§4 示例未带 `--end`）。
- **G3**：`689*.SH` 未按 20% 档；股本 asof 无 >90d gap 告警（对比 `shares.py` 公共路径有告警）。

---

## ✅ 做对的地方（保留）

1. **T+1 / COO**：禁 `bt.Order.Open`（本环境无该属性）；`Cerebro(cheat_on_open=True, runonce=False)` + `next_open` Market（plan:30；实现:514-520,370+）——与 r2 实验一致。  
2. **复权 SSOT**：`period=1d adjust_type=front`（plan:31；`load_front_daily` :477-482）；禁 `load_single_stock_data` 有据（`qmt_utils_adv.py:62-68` 默认 1m/`none`）。  
3. **cyqk_c 0–1 / 阈值 0.70**：`qlib_cost/cyq.py:184-193,229-245`；不读 `ChipDistribution.cyqk_c[0]` 正确——窗口 `range(-period,0)` 不含当日且无 as_of（`chip_indicator.py:104-123`）。  
4. **20 周均线**：真 `W-FRI` + `_last_day` backward，同构 `weekly_macd_divergence.py:86-103`；末端 partial week 口径已写入 plan:33。  
5. **path-SSOT**：抽样 `resolve_period_root` ∩ `resolve_source_parquet`（实现:443-463；`data_root.py:189-249`）；股本经 `stock_data_path`→同源（`paths.py:16-24`）。  
6. **包边界**：CLI+Strategy 在 `backtest/research/`（README:11-12）；算法经 `chip_algorithm` re-export（头注勿加算法）。  
7. **skip FSM / 统计窗 / 费用 / 卖日不重入**：与 §2 及单测一致；events 已按 `stats_start` 过滤（:522-523）。

---

## 总评

相对 r2 吸收前版本，因果链（COO、T+1、等号、SMA5 同日评、stale 买、卖日不重入、front/cyqk/周均线/path-SSOT）已行级自洽且经复现；**可维持实现 / 可进下一轮试验**。建议同轮只清 Y1–Y2 文档措辞，Y3–Y5 按风险择要补；无需再开交易语义级返工。
