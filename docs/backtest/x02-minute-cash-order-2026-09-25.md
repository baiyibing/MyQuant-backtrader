# X-02 分钟现金与持仓时序（默认 OFF）

对应 [审查 X-02](../reviews/2026-09-25-minute-engine-review/README.md)。共享分钟入口过去先扫描所有旧仓全天的卖点，再处理 09:45/14:55 买单；v7 过去逐股扫描全天。两者都可能提前使用未来卖款和未来持仓状态。

本次按批准计划 §2、§6、§8 实施；B01–B11 均已人裁 A。只修 X-02，共享书与 v7 独立实现、独立测试、独立 A/B。不实施 X-01/X-03，不自动改默认，不改策略版本。

## 开关与时钟

- 两个分钟 CLI：`--fix-minute-cash-order`；库参数：`fix_minute_cash_order=False`。省略与显式 False 保持旧 CSV/库级状态。日线没有这个开关；策略 12 收到 ON 明确报错。
- ON 按日期、hm、open/close 阶段和既有稳定次序推进账户。独立卖单实际净款在同 hm close 阶段立即供随后的买单使用（B11=A）。close 卖款不能支持同 hm 更早 open 买单。
- 共享书每 lot 当天首个卖点尝试后停止扫描；跌停、量拒绝、部分卖也不增加重试。peak、peak_hm、reserved、lu_today 和真正末根状态随游标推进，保持原谓词、reserve_limit_up、缺 15:00 的末根清仓合同。
- 09:45 chase → 14:55 完整 pool → step；v11 精确 09:30 open 与 volume=A 不变。pool 每天只调用一次完整名单，保留分母、file_order/seeded_shuffle、seed 与 X-04 原预算行为。opening-held 每天绑定一次，planned_for_day 在实际买时刻生成。
- B04=A：目标 bar 缺失时，仍在 09:45/14:55 决策，报价可沿用原更早 bar。审计分别记 decision_hm、quote_hm；容量仍使用报价桶，不能借目标时刻的新量。
- v7 当天跨股合并 hm；独立止损卖 → 当刻所有买侧 → 买后状态的真正末根 timer。成功加仓可续期，timer 卖款不倒补失败买单；没有 09:45 chase。参考调整和显式权益仍只对当天原有持仓处理一次，缺 bar 的 X-13 资格逻辑保留。

共享 `run()` 在外层统计/manifest 写开关及 cash_order_policy、same_hm_policy、fallback_order_clock、stable_order；`simulate()` 的 OFF stats 不增加键。v7 用独立 run-config.json。审计独立于旧 trades/equity CSV，保留原调用顺序，绝不事后排序重算现金来隐藏 OFF 逆时序。

## 合成验证与 OFF 基线

基线来自 master `eff77f3` 上 PR #202 的 `6d6d1fd`、`3028136`，已 cherry-pick；golden 未重录。19 本 × daily/minute × trades/equity 共 76 hash，另 v7 两个 hash，每组均含真实 BUY/SELL。测试同时核正式 writer、库层 CSV bytes、结构化成交/账户；省略和显式 False 分别运行。

```bash
~/.venvs/bt-ci/bin/python -m pytest -p no:cacheprovider -q tests/test_off_byte_baseline.py
~/.venvs/bt-ci/bin/python scripts/research/report_minute_cash_order.py --output-dir "$X02_REPORT_DIR"
```

报告包括冻结输入/参数/源码/golden 哈希，OFF/ON 逐事件 sidecar、现金前后、hm/decision_hm/quote_hm/phase、首个逆时调用、成交差异、持仓股数、拒绝计数与 EOD 估值。金额按 Decimal HALF_UP 到分核对，不改变 ledger float 或 CSV 格式。

| 合成场景 | OFF | ON |
|---|---|---|
| 共享 A 14:59 卖、B 14:55 买 | 先卖再买，余 338.46 | B 拒买，余 939.06 |
| 共享同 14:55 close | 卖净款 939.06，买含费 600.60 | 同样成交，余 338.46 |
| 共享 14:53 卖、14:55 决策借 14:50 报价 | 余 338.46 | 同样成交；quote=890，decision=895 |
| v7 A 15:00 卖、B 14:45 加仓 | 未来卖款支持加仓，余 540.32 | 加仓失败，余 200420.00 |

首个逆时分歧分别是共享 14:59→14:55、v7 15:00→14:45；ON 按实际决策时刻观察现金，后续持仓/估值差异属于因果传播。B11 同 close 与 B04 fallback 是无差异控制，不声称收益改善。

## M 清单回归映射

| 清单 | 验证 |
|---|---|
| M01–04 | 新时序测试：旧/新 lot T+1、真实净款、量拒/部分卖、未知板块与午休；既有 partial_sell、ashare_volume_cap、simulate_predicates/fill_clock/import_fence |
| M05–10 | s12 ON 拒绝；完整 strategy12_engine/rules 与 OFF 字节矩阵隔离 |
| M11–12 | 非 1 参考因子 × economics OFF/ON；旧仓一次调整、新 lot 不二次调整；min fee、容量及权益守恒；既有 exdiv_refprice_engines/ashare_exdiv_economics |
| M13–16 | v11 09:30、pending、volume=A、无 chase、卖日不重入的 ON 变体；既有 exporter/rules；Slice D/信号收益仍未验 |
| M17–18 | 8.x close-clear/fallback、reserve、gap15、stale/profit 优先级；pool 分母/配给/chase/X-04；v7 阶段、末根 timer 续期/失败不补买 |

## 真实数据未验证，待 4090

本机只做合成输入和数据无关测试，没有真湖 A/B，没有收益/parity/生产验收结论。保持原冻结窗口 `20251023–20260909`、池顺序、分数/资格/指数输入、费率、预算、seed、参考 map、解释器版本和湖快照。所有路径由配置 resolver 给出；缺输入直接失败，禁止猜盘或下载补齐。

共享各受影响书与独立 v7 各自比自己；资金紧张与默认资金两组都跑。每组先 OFF，再仅加 `--fix-minute-cash-order` 跑 ON；X-01/X-03 不混入本次归因。其它数据/参数完全一致，输出目录独立，不覆盖旧报告或市场湖。

共享入口原命令使用 `--out-dir`、`--emit-run-manifest`；v7 使用 `--output-dir`，独立 run-config.json。两者可加 `--execution-audit-file <独立 JSON 路径>` 保存真实调用 sidecar。记录实际命令全文、head、依赖、resolver 和文件哈希；无专用池/分数的书明确列缺口，不能空池假验收。

逐笔比对价格/数量/原因/时钟，按现金可用、持仓可用和后续传播归因。核现金最低值、量预算、股数、拒绝/缺失计数、EOD mark 与公司行动资格；任何未解释规则变化都需停下调查。合成报告不是 4090 回执。

## 已知限制与待确认

同 bar 仍沿用研究扫描器 high 先于 gap-open 检查的 OHLC 近似；保留同 close 先卖后买的人裁，分钟数据不证明真实逐笔先后。fallback 可以是陈旧报价；14:57–15:00 撮合仍是研究近似。X-04/05/06/07/10/11/12/13/20/27 等未修，尤其缺 bar 权益漏记和 v7 原索引日历不变。

没有新增策略语义分叉待裁。待确认仅为 4090 数据/参数冻结与验收结果，以及独立 defect-first 审查；本 PR 不 merge、不 auto-merge。
