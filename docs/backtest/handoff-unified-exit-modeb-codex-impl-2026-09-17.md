# 交接 · 统一卖出规则网格 · 模式 B 实施（Codex 接手）

> 日期：2026-09-17
> 实施状态：**A–C 已提交，D 因 Q38 STOP 待人裁**（2026-09-17；见提案 §十 Q38）。
> 状态：✅ **已人裁 GO**（2026-09-17；P1=A 窄网格 / P2=A 宿主smoke→4090 / P3=A exdiv_map）。以 plan v1.1 为准，**可开工**。
> 权威对象：[plan-unified-exit-modeb-2026-09-17.md](plan-unified-exit-modeb-2026-09-17.md) v1.0；口径母本 [stock-backtest-unified-exit-proposal-2026-09-17.md](stock-backtest-unified-exit-proposal-2026-09-17.md)（§一 Mode B / §9.5 Q29=B / §十二）。
> 前置：Mode A 已合（含 perf #92）；master tip 撰写时 `e018924`。
> 分支（**仅 GO 后**）：从当时 master 开 `feat/unified-exit-modeb`；切片 A/B/C/D 分 commit。
> 宿主数据就绪（可先做）：[host-runbook-unified-exit-modeb-smoke-2026-09-17.md](host-runbook-unified-exit-modeb-smoke-2026-09-17.md)。业务网格 runbook **GO+impl 后另开**（非本交接合入门）。

## ✅ 开工闸

plan 头部已为「✅ 已人裁 GO」。从当时 master 开 `feat/unified-exit-modeb`，按切片 A→D 实施。

---

## 0. 硬边界（勿越）

复制 plan **R\***（摘要）+ 已裁 P\*：

1. **R1**：新代码只落 `unified_exit_modeb.py` + `run_unified_exit_modeb.py`。复用 Mode A 装配/实例键/网格枚举/报告形状。**禁止**改 `csv_ledger.rescale_position` 使 1–6/8 的 shares 跟着 ÷k。
2. **R2**：买 = none 日线 close；触发 = 1m high/low；成交 = 该分钟 close。禁止 front 日线与 none 分钟混用。
3. **R3**：同根分钟 TP&SL 双触 → **先止损**。
4. **R4**：除权 E-R6 + `shares/=k` **仅 Mode B 模块内**（Q29=B）；现金红利不入账。
5. **R5**：网格/锚线/稳健性对等 Mode A（P1=A 窄网格）。**Mode B 不测** r2 N=1≡r1（Q37=A）；改测盘中先触发非等价反例。Mode A 等价性不动。
6. **R6**：CI data-free；全网格宿主-only（prefer 4090）；无硬编码盘符。
7. **R7**：不 import qlib；不复活 backtrader / Cerebro。
8. **P4 锁**：A/B 报告分目录，永不混排 NAV 表。
9. **P\* 已裁**：P1=A 冠军族（r2 X∈{5,7,10} Y∈{5,10,∞} N∈{8,10}）+ 四锚线；P2=A 宿主 smoke→4090；P3=A `ex_date_index`+`exdiv_map`；P4/P5 锁。
12. **Q36=A / Q37=A**（2026-09-17）。**Cache**：复用 warmup 起点 `minute_none_20251013_20260909`（超集），勿重建字面 20251023 key。
13. **Q38=A**（2026-09-17）：oracle 仅排除跌停分钟；同日其他分钟可候选。切片 D 可开工。
10. 发现提案未覆盖边界 → **停下回写提案 §十（Q36+）**，不自裁。
11. 新文件 UTF-8 无 BOM、NUL=0；验证命令用 vanna312 全路径。

**代码事实锚点（master `e018924`）**——实现时若行号漂移，以符号名为准、回写本表：

| 符号 | 锚点 |
|------|------|
| `MINUTE_LAKE_END` / `CACHE_ROOT` | `backtest/research/csv_minute_backtest.py:93` / `:143` |
| `minute_cache_path` → `minute_none_{start}_{end}.parquet` | `csv_minute_backtest.py:233-235` |
| `load_minute_bars` | `csv_minute_backtest.py:399` |
| 分钟湖根 `resolve_period_root("1m") / "dividend_type=none"` | `csv_minute_backtest.py:376` |
| Mode A `assemble_instances` | `unified_exit_modea.py:234` |
| Mode A `evaluate_exit`（日线 close 语义，Mode B 需平行实现） | `unified_exit_modea.py:378` |
| Mode A `evaluate_matrix` / `run_modea` / 报告 | `unified_exit_modea.py:502` / `:1021` / `:934` |
| `load_exdiv_ratios` | `exdiv_map.py:220` |
| 引擎 `rescale_position`（**只读对照；勿改 shares**） | `csv_ledger.py:157-166`（docstring：shares untouched X-R1） |

---

## 1. 切片 A · 分钟装载 / fixture / 覆盖

**步骤**

1. Mode B 买入侧：加载 **none 日线**（不要 Mode A 的 front root）；名单装配尽量复用 `assemble_instances` 的身份字段，或抽共享 helper——**价域换成 none close**，涨停判定仍 ±0.2% 容差 + `limit_pct`。
2. 监控侧：对实开（或 fixture）码集调用 `load_minute_bars(codes, start, end, use_cache=True)`；默认 cache 路径 `backtest_output/bar_cache/minute_none_{start}_{end}.parquet`。
3. 覆盖率 helper（可脚本可函数）：Mode A 宿主实开 4167 码（或从 Mode A 明细 CSV 读）∩ 分钟 cache/湖可得；记录缺失码与 `MINUTE_LAKE_END`。
4. 合成 fixture：`tmp_path` 造假 minute parquet（含 ymd/hm/high/low/close）+ 假名单；**零真实 symbol**。

**测试**

- cache miss → 写 cache → hit；子集请求不冲掉全量（与现 `load_minute_bars` 行为一致）。
- 覆盖 helper 在全缺失 / 全命中 fixture 下计数正确。

**DoD**：pytest 绿；无盘符字面量；不进 CI 湖门禁。

---

## 2. 切片 B · 退出求值器（1m high/low + close 成交）

**步骤**

1. 新 `evaluate_exit_modeb`（名可调整）：按市场交易日推进 N（Q32）；日内按分钟序扫描。
2. 触发：`high >= buy×(1+X%)` / `low <= buy×(1−Y%)` / trailing 用分钟 close 更新 peak；**成交价 = 该分钟 close**。
3. **同根双触 → 先止损**（R3）。
4. T+1：买入日整日不可卖。
5. 跌停：用当日（或该分钟）相对昨收的跌停判定；触发日若跌停则**不卖**，下一交易日再评（提案 Q7）。
6. 停牌 / 无分钟 K：冻仓；N 按市场日推进；到期遇无 K 顺延到复牌首个有 K 日（Q32）。
7. 规则 1 到期：到期日用**当日最后一根可交易分钟 close**（或文档锁定的等价口径；若提案未钉「末分钟 vs 日线 close」→ **STOP 开 Q36**，勿自裁）。*初稿倾向：Mode B 监控全日分钟，到期日以当日最后一根 session 分钟 close 成交，与「触发分钟 close」一致。*
8. 期末 20260909 未平仓：按最后可得 close 估值，不记卖出（Q12）。

**测试（建议向量 ≥12）**

- 同根 TP&SL → reason=stop、价=该分钟 close。
- 仅 TP / 仅 SL / trailing。
- N=1：按 Q37=A 测 r2 盘中提前成交与 r1_n1 末分钟成交的非等价反例；Mode A 等价测试不动。
- 跌停顺延；halt 冻 peak；买入日不触发。
- 无早退出 hold_end 锚。

**DoD**：向量表全绿；与 Mode A `evaluate_exit` **不共享错误价域**。

---

## 3. 切片 C · E-R6 + shares/=k（Mode B only）

**步骤**

1. 若 **P3=A**（建议）：持仓期遇 `load_exdiv_ratios` 事件日，对该实例 `cost*=k; peak*=k; shares/=k`（总成本不变）；除权后**不再**整百取整（提案 §八.2）。
2. 缩放发生在 Mode B 模块内的 lot/实例状态上；**禁止**调用并修改 `csv_ledger.rescale_position` 去动 shares。
3. 现金红利不入账；噪声带随 `exdiv_map`（≤0.5% 不修正）。
4. 若 **P3=B**：本切片改为文档边界 + 测试标明「未缩放」；实现跳过缩放路径。

**测试**

- 大送转级 k≈0.5：市值对齐、止损阈值随 cost 缩放、shares 翻倍（shares/=k）。
- 派息级小 k；无事件码路径不变。
- 断言 `inspect.getsource(csv_ledger.rescale_position)` 仍含 shares untouched / 或 git diff 引擎文件为空。

**DoD**：P3 裁后路径与测试一致；引擎 ledger 零行为变更。

---

## 4. 切片 D · 聚合 / 锚线 / 稳健性 / CLI

**步骤**

1. 指标口径照搬 Mode A（Q30）：总收益率基数 11 亿、年化 `(1+r)^(365/322)-1`、最大回撤、胜率、盈亏比、持有天数、峰值并发资金等。
2. 锚线：hold_end / N=1 / oracle（分钟域最优离场——定义须与提案 R5.2 对齐；若算力过大可先日线 oracle 对照并声明）/ 退市敏感性（Q33）。
3. Q34 四件套：半窗 / 邻域平台 / 板块+按月 / 次日开盘买敏感性。
4. CLI：`scripts/research/run_unified_exit_modeb.py`（sys.path 注入同 Mode A）。
5. 产出目录：`backtest_output/unified_exit_modeb/`（**禁止**写入 `unified_exit_modea/`）。
6. README + AGENTS Research 入口各一行。

**测试**：小 fixture 手算总收益率 / 回撤 / 并发峰值。

**DoD**：pytest 绿；HELP 中文；目录隔离。

---

## 5. 切片 E · 宿主业务网格（非合入门）

- 按 P1（窄 vs 全）与 P2（F 湖 smoke → 4090）执行；短记另落。
- **实现 PR / CI 不得勾选本切片完成。**
- 数据就绪步骤见 smoke runbook（可与编码并行，但**不是** Mode B 网格结果）。

---

## 6. 门禁

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
```

全绿 + CI data-free gates + fixture 外零真实 symbol。完成后回写 plan 状态与本交接完成标记。

---

## 7. 完成标记（Codex 填；GO 后）

- [x] 人裁 GO 已写回 plan（`0ce1db5`；Q36/Q37/cache 补裁 `d65442b`）
- [x] A · 分钟装载 + 覆盖 helper + fixtures（`2482072`）
- [x] B · 分钟退出求值器 + SL-first 向量（`3550c38`）
- [x] C · E-R6 + shares/=k（P3=A；`c3506bc`）
- [ ] D · 聚合 / CLI / README
- [ ] E · 宿主网格（host-only；另短记）
- [x] STOP / 新开 Q38：oracle「剔除跌停日」的分钟候选粒度待人裁；D 暂停。Q36/Q37 已裁且实现。
- 验证：显式 Linux vanna312 环境，Mode A + Mode B 合成测试 71 passed；Mode A / csv_ledger diff 为空。CI 同口径全套 733 passed / 2 skipped / 24 deselected；四项 data-free gates 通过；UTF-8 无 BOM、NUL=0。宿主 E 未执行。
