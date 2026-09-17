# 交接 · 统一卖出规则网格 · 模式 A 实施（Codex 接手）

> 日期：2026-09-17
> 状态：**🟡 待 Codex 接手**（A/B/C 未开工）。
> 权威对象：[stock-backtest-unified-exit-proposal-2026-09-17.md](stock-backtest-unified-exit-proposal-2026-09-17.md)（Q1–Q35 全锁定；口径以 §一核心约束表 + §十二速查为入口，实现规格见 §二/§三/§四，数据事实见 §9.7）。
> 前置：本 PR（#88）合并——Codex 需要其中的提案文档与 `unified_exit_precheck.py`（接口用法参考）。
> 分支：从合并后 master 开 `feat/unified-exit-modea`；A/B/C 分 commit。
> 宿主切片 D（真数据跑数）见 [host-runbook-unified-exit-modea-2026-09-17.md](host-runbook-unified-exit-modea-2026-09-17.md)，**非合入门**。

## 0. 硬边界（勿越）

1. **规则口径唯一权威 = 提案 §一/§十二**（Q1–Q35 已全部锁定）。发现未覆盖的边界语义 → **停下回写提案 §十（新开 Q36+）**，不自裁。
2. 新代码独立落点：`backtest/research/unified_exit_modea.py`（库）+ `scripts/research/run_unified_exit_modea.py`（CLI，参照 `report_unified_exit_precheck.py` 的 sys.path 注入式样）。`csv_ledger.py` / `csv_simulate_loop.py` / 成交核 / `csv_daily_backtest.py` / v7 / 1–6/8/9/10 书**一行不碰**。
3. 不用 backtrader / Cerebro；不复活 Rolling / Qlib PortAnaRecord。
4. **Codex VM 无 F 湖**：湖访问只经 resolvers（`resolve_period_root` / `resolve_index_daily_root`）；禁止硬编码盘符、cwd `stock_data/` 字面量、真实 symbol。单测全部合成 fixture（`tmp_path` 造假 parquet + 假名单 CSV）。CI data-free gates（`verify_no_hardcoded_machine_paths.py` 等）必须过。
5. master 可复用接口（已核验存在）：`csv_daily_loader._read_one_daily`（front root 直读）、`csv_pool.parse_pool_csv_entries`、`csv_minute_backtest_v7.load_index_daily`（日历；master 无 loader 版 `load_index_daily_closes`，勿引用）、`exdiv_map.load_exdiv_ratios`（仅模式 B 需要，本任务不用）、`market_layer.limit_pct` / `board_limit_pct`。`backtest/research/unified_exit_precheck.py`（本 PR）是这些接口的现成用法参考。
6. 新文件 UTF-8 无 BOM、NUL=0；验证命令一律 vanna312 全路径。

## 1. 切片 A · 装配层（instances 表）

- front 日线装载：`resolve_period_root("1d") / "dividend_type=front"`（**不是** `load_daily_bars` 默认的 none）。
- 名单实例表：窗口 20251023–20260909，`stock_pool/YYYYMMDD.csv` 每行一实例（canonical 码 + 名称 + 名单日）；**缺 20260525/20260605 = 当天无名单，不买、不报错**（Q 定性）。
- 买入过滤（Q6/Q5）：名单日无 K → 不买；收盘封板 → 不买不追。封板判定：`pct = close/prev_close − 1 ≥ limit_pct − 0.002`（复权价无舍入，±0.2% 容差，板块幅度用 `limit_pct(code, name)`；本窗口名单 0 只 ST）。
- 会话日历：v7 `load_index_daily(date(2025,10,23), date(2026,9,9))` 的 keys（217 个交易日）。
- 产出：`instances` 表（symbol、name、名单日、买入价=名单日 front close、实际开仓标记）。**预期量级（宿主真数据）**：5061 实例 / 跳过约 795 封板 / 实开约 4266——单测不依赖这些数字。
- 单测（合成数据）：封板跳过、无 K 跳过、正常买入、prev_close 取上一根 K（跨停牌）四场景。

## 2. 切片 B · 退出求值器（`(实例 × 策略)` 收益矩阵）

- **入场集与离场参数无关**（名义现金池 11 亿不触顶，Q30）→ 每实例对每策略求一个 (退出日, 退出价, reason)，再算 return%（0.1% 佣金双边）。
- 策略网格（280 组全跑、233 有效去重解读，提案 §三）：
  - 规则 1 固定 N：N ∈ {1,2,3,5,8,10,15,20}
  - 规则 2 止盈 X × 止损 Y × N：X ∈ {2,3,5,7,10,15,∞}、Y ∈ {2,3,5,7,10,∞}、N ∈ {1,3,5,8,10,15}
  - 规则 3 trailing：Y ∈ {3,5,8,10,15} × N ∈ {5,10,15,20}（Q31）
- 语义要点（提案 §二/§四，全部已锁定）：
  - T+1：买入日不可卖；N 按**市场交易日**计（Q32），到期遇停牌**顺延到复牌后首个有 K 日**执行。
  - 触发判定一律用当日 front close（模式 A 无同 K 双触；「先止损」只在模式 B 有意义，不实现）。
  - 跌停（`pct ≤ −(limit−0.002)`）当日不卖，次一交易日按规则重评。
  - 停牌/无 K：冻仓（不触发、N 顺延见上、trailing peak 冻结）。
  - 规则 3：peak = max(买入价, 持有期各日 close **含买入日**)；买入日只计 peak 不触发；可卖日 `close < peak×(1−Y%)` 触发。
  - 期末（20260909）未平仓：按当日（或最后有 K 日）front close 估值，不记成交（Q12）；日线早断码冻在最后收盘（Q33 主口径）。
- 单测：手算期望向量表（建议 ≥12 行：N=1 等价性、跌停顺延、停牌顺延、trailing 买入日 peak、断码冻结、到期与触发同日等）。
- **不做**：模式 B 分钟路径、E-R6、`shares /= k`、`rescale_position` 改动（全部后补，见提案 §9.5）。

## 3. 切片 C · 聚合与报告

- 指标口径（Q30 锁定）：每参数组算 **总收益率（基数 11 亿名义现金池）**、年化 `(1+r)^(365/322)−1`、最大回撤（11 亿初始净值每日曲线）、胜率（分母=实例数）、盈亏比、平均持有天数（买入→卖出自然交易日差，Q32）、每实例平均/中位 return%、总 PnL、**峰值并发资金**（每日在持笔数×100 万取 max）。总收益率与每实例平均并列（同序校验）。
- 锚线四条：① 持有到期末（N=∞ 不设 TP/SL）② N=1 ③ oracle 上界（每实例 T+1 起剔除跌停日的最优退出日，明示非可交易）④ 退市敏感性（9 笔受冻实例按 0 计，Q33）。
- 稳健性四件套（Q34 必做）：前后半窗（20251023–20260404 / 20260407–20260909）各排一次 + top 20 名次一致性；参数邻域平台性；主板/创业/科创 + 按月分层；「次日开盘买」敏感性组（换买入价重跑矩阵）。
- 输出：`backtest_output/unified_exit_modea/`（排名 CSV、实例明细 CSV、汇总 JSON）；HELP/docstring 中文、ASCII print；AGENTS.md Research entries 加一行；`docs/backtest/README.md` 入口补一行。
- 单测：聚合口径（用小 fixture 手算总收益率/回撤/并发峰值）。

## 4. 切片 D · 宿主真数据跑（非合入门，宿主执行）

见 [host-runbook-unified-exit-modea-2026-09-17.md](host-runbook-unified-exit-modea-2026-09-17.md)。合入门（PR）**只含 A/B/C**。

## 5. 门禁

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
```

全绿 + CI data-free gates 过 + fixture 之外零真实 symbol。完成后回写本交接状态与提案 §状态行。

## 6. 完成标记（Codex 填）

- A/B/C：分支 `feat/unified-exit-modea`，commit `____`。
- pytest：`____ passed / ____ skipped`。
- STOP 记（遇到的口径歧义、与提案冲突处，逐条列出）：`____`。
