# Host errata — P3 δ2 ex-div plan adversarial r1 (host-parallel Codex)

> Date: 2026-09-19
> Input plan: `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md` **v0.1** (PR #122 tip `23024cc`)
> Lanes: host-parallel independent `codex exec` (`gpt-6-astra` + `xhigh`) via `scripts/run/run_codex_adversarial_lanes.py`
> Artifacts: `dissent-steelman.md` / `domain-safety.md` / `pattern-evidence.md` (all rc=0; ~470s / ~423s / ~438s)
> This host synthesis is **not** an independent vote; evidence over ballots.

## Lane verdicts (evidence summary)

| Lane | Verdict | Top themes |
|------|---------|------------|
| dissent-steelman | **REQUEST_CHANGES** on v0.1 B1–B6 / full-A readiness; keeps δ2 docs-only | DS-01 factor-recovery wrong domain; add1_A1 reachability; Decimal half-boundary; step-add wiring |
| domain-safety | **REQUEST_CHANGES** on contract/acceptance text; keeps δ2 + production zero-diff | factor PIT/as-of; v7 fixture mixed scales; T+1 mixed-lot pin; Decimal chain |
| pattern-evidence | **CONDITIONAL** support for δ2 docs-only; no redo E-R6 | qlib_day≠qlib_1min; fixture evidence limits; helper vs public state; v7 provenance |

**Host decision:** do **not** treat v0.1 as Slice B/C implementation-ready. Stay docs-only. Backfill plan to **v0.2**. Do **not** reopen P1/P2/P4. Do **not** redo E-R6 production behavior. Do **not** pull δ3/δ4/δ5, shares/cash-div accounting, or lake/host backtests into this ship. Human-cut defaults remain **A/A/A/A/A** after the docs clarifications below (no finding forces a B/C reopen note).

## Errata table (E-d2-*)

| ID | Sev | Sources | Issue | Host decision | v0.2 backfill |
|----|-----|---------|-------|---------------|---------------|
| **E-d2-01** | HIGH | dissent DS-01 | 有效因子恢复日落日可与行情已换域错配：缺行日无 k，下一日写出有限 k，昨收与除权日新买 lot 会再乘一次；与“停牌日键不回放”不同 | **ACCEPT-docs** — 记为 as-built 残留；收窄“已映射到 D 域”前提；未来 B1–B4 规划跨层合成链 pin；**不**本刀修 loader/生产 | §2.2 错配残留 + §2.4 触发错域行；B1/B2 观察点 |
| **E-d2-02** | HIGH | domain DS-1 | 日期 LAG / 前一有效行 ≠ 决策时刻可得；F_D 由当日 close_front/close_none 构造，无 as-of/版本过滤；不能写“未来函数已排除” | **ACCEPT-docs** — 区分“不读 D 之后行”与“F_D 在开盘/扫描前可得”；后者标未证/历史观测近似；不归入已关闭面；不借 δ3 ST PIT 代替 | §2.2 + §6 non-goals；B1 前缀一致性仅限合成、不证原始 PIT |
| **E-d2-03** | MED | dissent DS-02, PE-03 | B3“完整字段”含非空 `add1_A1`，但公开 `simulate_v7` 自然路径从不赋该字段；全字段公开接线会空过或夸大 | **ACCEPT-docs** — 拆 B3：helper 人工非空矩阵 vs 公开可达字段；非空 `add1_A1` 标兼容分支，禁写“已验证自然加仓赋值” | §2.5 + B3 两层证明 |
| **E-d2-04** | MED | dissent DS-03, domain DS-4 | B4 唯一明列链 `10×0.5→5→(5.50,4.50)` 不能区分 Decimal HALF_UP；`1.65→(1.82,1.49)` 已知能辨但不在定向验收 | **ACCEPT-docs** — 未来 B4 增补 `raw_prev=3.30,k=0.5→1.65→(1.82,1.49)`，mapped 必须送入真实档位函数；保留 10→5 直观例 | B4 数值链；§2.5 session 行 |
| **E-d2-05** | MED | dissent DS-04 | 台阶加仓是独立消费点（`csv_simulate_loop` step）；B2/B4 可全绿而不触达 step+exdiv | **ACCEPT-docs** — B2/B4 明列 step 路径与两引擎 exdiv 传参；至少“映射后涨停挡 step”与“允许 step 时新 lot 保持原始 cost” | B2/B4 观察点 |
| **E-d2-06** | MED | domain DS-2, PE-02 | 既有 v7 trial-stop 夹具同日分钟买价 100 / 日收 50 混域；可作公开 API 布线证据，不能当同域“参考价—档位—成交”oracle | **ACCEPT-docs** — §2.5 写明夹具限度；未来 B3/B4 增自洽 held 夹具并分断言缩放/档位/成交 | §2.5 证据限度 |
| **E-d2-07** | MED | domain DS-3 | B3“新买/加仓不重乘”未要求除权日老/新 lot 混持后同日 stop 只卖老 lot（T+1） | **ACCEPT-docs** — 未来 B3 经公开 `simulate_v7` pin 混持 T+1；缩放本身不增减现金与后续真实成交现金分断言；不声称当前源码 T+0 | B3 混持 T+1 |
| **E-d2-08** | MED | PE-01 | “front/back/qlib 连续域”易被读成任意 qlib 源；`qlib_day`（后复权约定）≠ `qlib_1min`（none 约定）；B6 只钉了 daily 四态 | **ACCEPT-docs** — §2.3 将 daily“qlib”明确为 `qlib_day`；注明读取器不认证域；B6 对 minute/v7 列 `daily_source×minute_source` 受控接线（现状仍加载 map），不宣称域一致 | §2.3 + B6 |
| **E-d2-09** | LOW | PE-04 | “E-R6 已落地”统一叙述缺历史分界：原 E-R6 人裁不含 v7；v7 `_rescale_position` 由后续 shared-session 提交引入 | **ACCEPT-docs** — §2 加一句沿革；保留旧 plan 历史人裁；不重审/回滚既有接线 | §2 沿革短注 |

## Explicit non-goals (unchanged)

- No P1 14:57 window, P2 trades columns, P4 touch↔mark.
- No production Python / tests / backtests / lake reads in this docs ship.
- No redo of E-R6 event gate, k direction, noise band, or call-site order.
- No shares / cash-dividend / total-return accounting; economic residual stays deferred.
- No δ3 ST PIT, δ4 `limits=None` policy change, δ5 participation cap.
- No Cerebro / PortAna / Mode A/B revival; OSS analogy only.
- No chip_indicator resurrection; no StockDataReader swap-in for δ2.

## Human-cut posture

| Cut | After v0.2 | Note |
|---|---|---|
| P3δ2.1–P3δ2.5 | defaults stay **A/A/A/A/A** | E-d2-01/02 are residual/docs pins under A, not a forced reopen to B/C event redesign or full CA accounting |
| Blocks human cut? | **No** (after v0.2 clarifications) | Cut still **pending human GO**; this errata only clears docs/acceptance-definition blockers, not implementation GO |

## Next after v0.2

1. Human cut on P3δ2.1–P3δ2.5 (defaults still A/A/A/A/A unless reopened).
2. Optional multi-ai fan-out on v0.2 text.
3. Only then Slice A/B/C implementation (tests+docs; freeze proof; production zero-diff).
