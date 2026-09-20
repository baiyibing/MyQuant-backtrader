# Plan: industry-align P3 δ6 production ex-div economics (2026-09-19)

> **状态交叉引用（2026-09-20）**：Human GO P2=B 仅授权书 trades 的 `session_phase` / `price_rule` 两列，覆盖本文历史 P2 延后记录；P1 已 closed as A，P4 仍 deferred，本文 δ 合同不重开。见 [schema SSOT](engine-ashare-correctness.md#p2-trades-标签列human-go-b2026-09-20)。
> **Status**: **v0.4 · production economics landed · Human GO C/A/B/B/A**（2026-09-19，Asia/Shanghai）。本刀的 must-cut-C 已满足；economics-off 保留旧残留，economics-on 的显式事件守恒经 public APIs 验收，见 §8.4。
> **IMPLEMENTATION_BASE**: `f145ffdec5e378c9092d3f8b990f104979d89141`（#130 merge tip，δ5 volume-cap production；开工时 HEAD 与指定分支已核对）。
> **Human GO**: **P3δ6.1=C / .2=A / .3=B / .4=B / .5=A**，覆盖 #128 的 A 残留+oracle / B docs 冻结，**仅对本刀生效**。历史 A 记录保留于 §10。
> **交付**: `/workspace/wt-p3-d6-exdiv-econ-prod`，分支 `feat/industry-align-p3-d6-exdiv-econ-prod`；提交到本地分支，由 host push/PR。本刀串行，不开子代理。
> **前序**: [δ1 fees](plan-industry-align-p3-fees-2026-09-19.md)、[δ2 reference](plan-industry-align-p3-d2-exdiv-2026-09-19.md)、[δ5 cap](plan-industry-align-p3-d5-volume-cap-2026-09-19.md)、[engine SSOT](engine-ashare-correctness.md)。

## 0) One-line scope

为 daily/minute book 与 v7 的公开模拟接口提供显式、默认关闭的送转增股、现金应收/到账与 NAV 接线；保留独立 E-R6 参考价缩放。无 CLI/loader/湖事件源接线。

## 1) Why now

E-R6 只把 cost/peak 等参考量映射到除权价域，不能补偿原股数与 raw mark 的经济差额。#128 只固定残留和设计 oracle；本次新 Human GO C 批准独立生产变更。k 无法识别 b/c，因此本次由调用者提供完整事件，既不从 k 推算权益，也不采集/合并数据。

## 2) Production anchors（本次编辑后的 file:line）

| 面 | 生产落点 | 合同 |
|---|---|---|
| 输入/独立账 | `backtest/research/ashare_exdiv_economics.py:19`、`:61`、`:85`、`:127` | frozen ExDivEvent、一次性资格快照、event_id 去重、应收与结算 |
| book 参考/权益 | `backtest/research/csv_ledger.py:151`、`:163`、`:313` | rescale 原实现不变；增股不动 refs；卖出过滤新股限售量 |
| daily public | `backtest/research/csv_daily_backtest.py:208`、`:302`、`:317` | session start 到账；原 bar/昨收门后权益→参考缩放→卖出扫描 |
| minute public | `backtest/research/csv_minute_backtest.py:511`、`:597`、`:616` | 原 daily/minute/昨收门后同序处理；原扫描/成交时点不变 |
| book NAV | `backtest/research/csv_simulate_loop.py:411` | cash + shares×传入 mark + outstanding receivables |
| v7 public | `backtest/research/csv_minute_backtest_v7.py:191`、`:203`、`:315`、`:359`、`:379`、`:483` | records 门后权益→原 rescale→扫描；独立 bonus lots；NAV 加应收 |
| v7 可卖量 | `backtest/research/csv_minute_backtest_v7.py:256` | 原 `_sell_lots` / t1_sellable 原样处理 list_date bonus lot |

**economics-off**（省略参数或 None）仍保持原股数、现金、lot、trades、stats 与 NAV 残留；byte snapshots 钉住本固定 base 的公开输出。Position 字段与 trades.csv schema 不变；SimState/SimResult 新增可空的运行内经济账句柄。`exdiv` 仍独立控制参考价，不挂经济账也可继续 rescale。

## 3) Deferred boundaries

P1/P2/P4 继续 deferred。δ4 fail-closed 与 δ5 cap 已在基线落地，本次仅组合使用，不重开语义。Mode A/B 生产零 diff；Mode B 的 float `shares /= k` 是独立近似，没有移植。

δ2 因子 PIT/修订、恢复日错域、噪声门、SMA/qlib 混域与 rescale helper 非幂等均未修复。实际事件数据、税费/负债、经济成本分配、登记日资格与权益修订/跨运行重放不在本刀；不能声称真实全市场总回报或历史收益已校正。

## 4) F-R* hard locks（C cut 适用）

| ID | 合同 |
|---|---|
| F-R1 | 仅 §8.1 allowlist；生产仅六文件，§9 的五个旧文件为本次明确例外。 |
| F-R2 | E-R6 cost/peak×k 独立；经济层不改 refs、不 shares/=k。默认关闭保留 δ2 残留。 |
| F-R3 | Mode B 近似与代数 oracle 不能替代 public 生产权益守恒测试。 |
| F-R4 | k 不是 b/c；缺失、invalid 输入不发明权益。 |
| F-R5 | ex_date 锁 q；新股 list_date/ex_date 为取得日，严格后续 session 才可卖。 |
| F-R6 | 守恒 fixture 隔离额外市场变化/税费/外部流；应收→现金不产生第二次收益。 |
| F-R7 | 新账按 event_id 幂等；旧 rescale helper 非幂等不变，不宣称持久恢复或修订支持。 |
| F-R8 | 不改 P1/P2/P4、ST PIT、fee 数字/公式、limit/volume-cap 语义。 |
| F-R9 | 内存/tmp_path、指定 Python；无湖、CLI backtest、网络/下载、子代理；固定 SIMULATE_HOT_PATH enum 不扩展。 |
| F-R10 | §9 其它行及 allowlist 外全路径零 diff；不复活 live/LEBS/MockQMT/Cerebro/PortAnaRecord。 |

## 5) Human cuts（当前有效 C/A/B/B/A）

| ID | Human GO | 生产合同 |
|---|---|---|
| P3δ6.1 | **C** | 独立生产增股/入账/NAV wiring；本次 must-cut-C satisfied |
| P3δ6.2 | **A** | caller-supplied 显式经济事件；不从 k 猜 b/c，无湖采集/merge |
| P3δ6.3 | **B** | ex 日锁 eligible q、加股并开应收；pay 日应收转现金；同日 pay 可立即到账 |
| P3δ6.4 | **B** | 每个现存 lot `floor(q*b)` 整数新股；零碎余数丢弃，不做现金替代 |
| P3δ6.5 | **A** | 不改 trades.csv schema；公司行动不是 BUY/SELL，不收 δ1 佣金；运行内 stats 可诊断 |

### 5.1 Explicit API

```python
from backtest.research.ashare_exdiv_economics import ExDivEvent

events = {
    ("600000.SH", "20260902"): ExDivEvent(
        event_id="600000.SH:20260902:fixture-1",
        bonus_ratio=1, cash_div_per_share=1,
        ex_date="20260902", pay_date="20260903",
    ),
}
# daily.simulate(..., exdiv_economics=events)
# minute.simulate(..., exdiv_economics=events)
# v7.simulate_v7(..., exdiv_economics=events)
```

支持 Mapping `(engine_symbol, YYYYMMDD) -> ExDivEvent | None` 或 callable `(symbol, ds) -> ExDivEvent | None`。值须为 ExDivEvent，不接受未验证 dict；event_id 是运行内跨股票唯一的非空字符串。b/c 为有限非负 numeric（float/Decimal，整数也可），日期为有效 YYYYMMDD，ex_date 须等于查询日，pay/list 不早于 ex，list_date 默认 ex_date。数据与 raw bars 的经济一致性由调用者负责，函数不认证价格域；CLI 不自动启用。

lookup None 返回表示当日无事件；LookupError 也视为缺失。错误类型、负数、非有限值、非法日期/日期顺序等跳过并计 `exdiv_econ_invalid_event`，不部分入账；调用者 callback 的其它错误直接抛出。明确事件不受 E-R6 k 存在性/噪声门限制。

### 5.2 Ordering / lifecycle

1. 每个模拟 session 开始先结算已开应收；pay_date 非模拟 session 时，在首个 `session >= pay_date` 到账。即使已卖空或该股票当天无 bar，权益仍存活。若 pay_date 晚于模拟窗口，末日保留应收，不提前支付。
2. 已持仓 symbol 通过既有处理门后，ex_date 一次快照所有现存 lot 的 q；此后当日买入无该次权益。book 要当日日线/昨收，minute book 还要当日分钟；v7 要 records，继承它原有 rescale 前置条件。
3. 每 lot 加 `floor(q*b)`，开总应收 `sum(q)*c`，同日 pay 立即转换。**先权益、后原 E-R6 rescale、再 scan**；新旧股仅一次计量，cost/peak/entry_A/avg_cost 等仍只由参考路径乘 k。
4. 缺 ex-day bar/前置条件不回放到后续日期。event_id 只允许应用一次；本刀无冲销/修订、持久化、跨运行恢复。截止日仍持应收纳入 NAV。

book 新股并入原 Position，用经济账中按 lot identity 保存的 list-date 限售量过滤 `_sell`；保持 lot 数、entry_idx、ride/step 身份和原成本参考。独立 lot 可卖原股、保留限售新股；随后卖出规则照旧重新评估（daily 原 pending 保持），不新增退出队列。存在跟单链接时，在任一相关 bonus 仍限售时整组暂缓，计 `exdiv_econ_defer_linked_t1`，避免父/子孤立；解锁后沿用既有整组退出/容量规则。cap-on 的 pending 退出也必须等待全部新股解锁，计 `exdiv_econ_defer_pending_t1`，继续保持 δ5 的整笔语义。

v7 每个旧 lot 追加 `kind="exdiv_bonus"` 的 entitlement lot，复制 source lot.price，buy_date=list_date；既有 t1_sellable 自然保护新股，stage/last_add_date 不因公司行动更新。floor 按各引擎当时的 lot 划分执行，多次送转后不保证不同 lot 划分产生相同零碎舍弃量。

### 5.3 NAV / precision / diagnostics

NAV = cash + 全部已确认股份（含尚不可卖新股）×mark + receivables − liabilities；本刀无产生负债的事件，liabilities=0。新股从 ex_date 确认并按原始 mark 估值，未来 list_date 仅延后可卖，不另重复记一个股权资产。book 仍用当日/最近历史 close（无行情才 cost fallback），v7 仍用 last_prices/avg_cost fallback。

b/c 经 Decimal 字符串转整数比率；整股 floor 不依赖 Decimal context 精度。gross 进入既有 float 现金账，不新设分币舍入/税务规则；碎股直接舍弃，因此非整数 q*b 的夹具允许相应价值损失，不能强行要求3000守恒。

诊断在 `state.exdiv_economics.stats`，book 同时反映到 `state.stats`：events、bonus_shares、cash_entitled、cash_posted、receivable_open、invalid_event、duplicate_event（均带 `exdiv_econ_` 前缀）。`receivable_open` 是当前金额，posted/entitled 是累计金额。公司行动不调用 volume clamp/consume，不写交易行、不收佣金；随后真实成交照旧调用 δ1 费用。

## 6) Migration / rollback

默认 economics-off 是部署安全开关，保持旧残留；显式提供经济 lookup 才启用。没有数据或产物 schema 迁移，无持久账恢复承诺。回滚为 revert 本 PR，或调用者撤掉 exdiv_economics 参数后重新模拟。无历史收益/宿主回测结论。

## 7) Slices A → B → C（生产验收）

Slice A 更新本 plan / engine §2.5 / README，记录 C/A/B/B/A 与冻结例外。Slice B 为真实 helper/public simulate 接线及测试，保留 #128 全部 design_only 与 δ2 residual pins。Slice C 运行 §8、检查差异范围、提交本地分支，不 push/PR。

| 验收面 | 生产证据（tests/） |
|---|---|
| B3 纯送转 | `test_ashare_exdiv_economics.py::test_ledger_b3_b4_b5_conserve_without_reference_share_inflate`；`test_exdiv_refprice_engines.py::test_d6_public_book_production_conservation`；`test_csv_minute_backtest_v7.py::test_d6_v7_production_conservation_and_pay_without_symbol_bar`：100→200，raw10→5，cash2000，NAV3000 |
| B4 现金 | 同上三入口/ledger：ex 日100股×9+cash2000+recv100=3000，pay 日cash2100/recv0，NAV3000 |
| B5 混合 | 同上：200×4.5+2000+100=3000；明确不使用 q/k，不得到3100 |
| 幂等/整股/输入 | `test_integer_floor_per_lot_and_idempotent_snapshot`、`test_same_day_payment_and_duplicate_id_across_lookup_dates`、`test_invalid_event_is_diagnosed_without_partial_state`、`test_missing_none_and_callable_lookup_and_no_k_inference` |
| 默认 invariance | `test_d6_book_off_byte_snapshot_matches_f145ffde`（daily/minute × 有无 k）、`test_d6_v7_off_byte_snapshot_matches_f145ffde`；基线 archive 独立运行产出6个 SHA256，比较 cash/positions/lots/trades/equity/book stats；省略/None/空 lookup 一致 |
| 生命周期/T+1 | book `test_d6_book_missing_ex_bar_is_not_replayed`、`test_d6_book_cash_event_without_k_and_pay_after_exit`、`test_d6_book_public_bonus_t1_and_following_sale`、`test_d6_book_exday_pool_add_has_no_entitlement`；v7 `test_d6_v7_multilot_eligible_snapshot_and_no_entitlement_for_new_trial` |
| volume/fee 组合 | ledger `test_book_t1_listing_partial_exit_and_real_trade_fees`（cap on/off、future list_date）、`test_book_linked_exit_waits_for_bonus_t1_without_orphaning_rider`、`test_cap_pending_exit_stays_atomic_while_bonus_is_locked`；v7 `test_d6_v7_bonus_t1_and_cap_consumes_only_real_fills`；δ1 wiring 与 δ5 suite 全绿 |
| 旧残留/独立模型 | 原 `test_d2_economic_residual_small_oracle`、public book raw-mark、v7 multilot、design_only B3–B5 均原样保留；Mode B suite 原样运行，不能把其近似视为本刀实现 |

## 8) Linux/CI isomorphic acceptance

### 8.1 固定基线 / actual allowlist

基线固定为 `f145ffdec5e378c9092d3f8b990f104979d89141`；审计覆盖 base→HEAD、index/worktree 及 untracked。实际仅以下12路径可变，UTF-8 无 BOM/NUL，`git diff --check` 清洁：

- 生产：`backtest/research/ashare_exdiv_economics.py`（新增）、`csv_ledger.py`、`csv_daily_backtest.py`、`csv_minute_backtest.py`、`csv_minute_backtest_v7.py`、`csv_simulate_loop.py`（以上均在 `backtest/research/`）。
- 文档：`docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md`、`docs/backtest/engine-ashare-correctness.md`、`docs/backtest/README.md`。
- 测试：`tests/test_ashare_exdiv_economics.py`（新增）、`tests/test_exdiv_refprice_engines.py`、`tests/test_csv_minute_backtest_v7.py`。

### 8.2 实际测试命令

使用用户指定 `/tmp/industry-align-venv/bin/python`，不安装依赖；内存/tmp_path，现有入口测试只运行 stub，不启动真实 CLI backtest。8个指定完整套件，加上受 `_sell` 接线影响的 δ1 wiring：

```bash
/tmp/industry-align-venv/bin/python -m pytest -q -m 'not production and not benchmark' \
  tests/test_ashare_exdiv_economics.py \
  tests/test_exdiv_refprice_engines.py \
  tests/test_csv_daily_backtest.py \
  tests/test_csv_minute_backtest.py \
  tests/test_csv_minute_backtest_v7.py \
  tests/test_ashare_volume_cap.py \
  tests/test_ashare_simulate_import_fence.py \
  tests/test_unified_exit_modeb_exdiv.py \
  tests/test_ashare_fee_wiring.py
```

### 8.3 Freeze proof

§9 原22行保留，五行获本 C cut 限定例外：csv_ledger、csv_simulate_loop（仅应收 mark）、csv_daily_backtest、csv_minute_backtest、csv_minute_backtest_v7。新增 ashare_exdiv_economics 是本刀专用 helper，不扩 SIMULATE_HOT_PATH。**其余17行零 diff**；另核 ashare_volume_cap、import-fence 测试、CI、其它全仓路径均零 diff。

```bash
BASE=f145ffdec5e378c9092d3f8b990f104979d89141
git diff --name-status "$BASE" -- backtest/research/
git diff --exit-code "$BASE" -- backtest/research/ \
  ':(exclude)backtest/research/ashare_exdiv_economics.py' \
  ':(exclude)backtest/research/csv_ledger.py' \
  ':(exclude)backtest/research/csv_simulate_loop.py' \
  ':(exclude)backtest/research/csv_daily_backtest.py' \
  ':(exclude)backtest/research/csv_minute_backtest.py' \
  ':(exclude)backtest/research/csv_minute_backtest_v7.py'
git diff --exit-code "$BASE" -- tests/test_ashare_simulate_import_fence.py .github/
git diff --check "$BASE"
```

### 8.4 本次运行记录与验收范围

2026-09-19（Asia/Shanghai），Linux / CPython **3.12.13**，指定工作树/分支。受测对象为本地提交前的完整实现；最终 feat SHA 由交付回报给出，避免文档自引用。无湖/网络/下载/依赖安装/真实 CLI 回测。

| 命令 / 检查 | 结果 | exit |
|---|---|---|
| §8.2 完整命令，含费用 wiring | **339 passed / 0 failed / 0 skipped，2 warnings，1.94s** | 0 |
| 基线独立 byte snapshots | 通过 `git archive` 提取指定40位 base，在独立临时目录执行既有公开 fixture；6个输出 hash 均由新增回归匹配 | 0 |
| 保留测试 | δ2 residual / design_only 原函数 AST 不变；δ1 wiring、δ4/v7、δ5 cap、Mode B、import fence 均通过 | 0 |
| §8.1 allowlist / encoding / whitespace | **PASS：12路径白名单，UTF-8/BOM=0/NUL=0，whitespace clean** | 0 |
| §8.3 research / §9 remaining freeze / CI | **PASS：六个授权生产文件；原22行保留、五行明确例外、其余17行零 diff；cap/fence/CI 零 diff** | 0 |

两条 warning 来自未改动 `ashare_bars.py:503` 的 pandas copy 参数弃用，不是新 skip。开发阶段的失败已解决：初版给 Position 加字段破坏既有 δ5 字节快照，现改为运行内独立锁量；v7 夹具最初误认 trial fraction，现以 `1000 / TRIAL_FRACTION` 固定100股，不改策略/费率。最终339为单次完整结果，不累加开发运行次数；新增54例，既有285例（含7例费用）。

**production economics landed；Human GO C/A/B/B/A；must-cut-C satisfied。** 守恒仅对明确事件/受控 raw fixture 成立；默认旧经济残留、缺 bar 不回放和其它 §3 边界继续保留。回滚无 schema/data 迁移，提交后由 host 发布。

## 9) Frozen production file table（原22行保留；本 C cut 例外见 §8.3）

| File | 冻结理由 / 来源 |
|---|---|
| `backtest/research/ashare_fees.py` | δ1 费率/default/asymmetry/floor 不漂移 |
| `backtest/research/csv_ledger.py` | δ1/δ2 双向现金、整股、lot、参考价 rescale |
| `backtest/research/csv_simulate_loop.py` | δ1/δ2 chase/pool/step、资金门与 raw mark |
| `backtest/research/csv_daily_backtest.py` | δ1/δ2 daily 名称/档位/缩放顺序/入口域与费率 |
| `backtest/research/csv_minute_backtest.py` | δ1/δ2 minute 扫描/前置数据/门/入口域 |
| `backtest/research/csv_minute_backtest_v7.py` | δ1/δ2 v7 独立 lot/股数/现金/stage/时点 |
| `backtest/research/ashare_session.py` | δ1/δ2 ST/context、昨收、None predicates、T+1 |
| `backtest/research/market_layer.py` | δ1 ST 优先/板块/Decimal 档位 |
| `backtest/research/csv_common.py` | δ1/δ2 书 as-of、named band、bar/昨收前置条件 |
| `backtest/research/csv_artifacts.py` | δ1 产物 schema；P2 挂起 |
| `backtest/research/exdiv_map.py` | δ2 事件门/LAG/阈值/k/缺失行为，不改成权益源 |
| `backtest/research/exdiv_hold_hits.py` | δ2 引用的日期 normalize 与既有探针冻结 |
| `backtest/research/ashare_bars.py` | δ2 分钟帧/源域/缺 bar 与 volume 丢列行为 |
| `backtest/research/csv_daily_loader.py` | δ2 域/零量过滤与输出列 |
| `backtest/research/ashare_fill_clock.py` | δ2 已列；P1 时钟命名冻结 |
| `backtest/research/qlib_bin_daily.py` | δ2 qlib_day 域声明/读取不变 |
| `backtest/research/qlib_bin_1min.py` | δ2 qlib_1min 域/输出帧不变 |
| `backtest/research/csv_pool.py` | 新扩展：名称第二列/by-day/窗口/空名合同 |
| `backtest/research/csv_strategy_books.py` | 新扩展：BOOKS/hooks/卖出策略/P4 边界 |
| `backtest/research/strategy5_rules.py` | 新扩展：既有 force-sell 时点，不为 cap/None 改写 |
| `backtest/research/unified_exit_modea.py` | 新扩展：独立研究网格合同，不统一到 CSV 账本 |
| `backtest/research/unified_exit_modeb.py` | 新扩展：fractional-shares 近似保持独立，不借用作经济闭环 |

表内 csv_ledger / csv_simulate_loop / csv_daily_backtest / csv_minute_backtest / csv_minute_backtest_v7 五行仅在本次 δ6 allowlist 内解冻；其它17行相对 IMPLEMENTATION_BASE 必须零 diff。此例外不更改 δ1/δ2 历史验收结论，表行原文保留。

## 10) Changelog

- **v0.4 (2026-09-19，Asia/Shanghai)**：新 Human GO **P3δ6.1=C / .2=A / .3=B / .4=B / .5=A** 覆盖 #128 的 A 残留+oracle 冻结，仅为本刀授权独立生产权益/NAV。固定 IMPLEMENTATION_BASE 为 #130 `f145ffdec5e378c9092d3f8b990f104979d89141`，接线显式事件、整股 floor、ex 应收/pay 现金、T+1、独立 E-R6；默认 off 与旧 pins 保留。§7–8 改为生产验收，§9 五行例外、其它冻结。生产经济落地，P1/P2/P4 继续 deferred，revert 无迁移；仅本地提交，不 push/PR。


- **v0.3 (2026-09-19，Asia/Shanghai)**：按 Human GO A + 可选账本 B docs 完成 Slice A→B→C；基线刷新为 #127 merge `3668e256abec1258759b99a72e3b3c17d082e75c`，复核 §2 锚点并更正 v7 pin 行号。engine SSOT §2.5 / README 落残留、B3–B6 设计 oracle 与账本候选；复用 δ2/Mode B pins，仅新增4个 design_only 函数/5例。§8.4 记录 **85 passed**、五路径审计与22文件/全 research/非测试 Python 冻结证明，保留 §9 原表；经济残留未关闭，C 未授权/未实施，未提交交付。

- **v0.2 (2026-09-19，Asia/Shanghai)**：录入 Human GO P3δ6.1=A（残留+oracle），账本设计可选 B 且仅 docs；明确非 C，生产增股/入账/NAV 须另裁显式 C，本轮不授权且禁止修改。P1/P2/P4 继续挂起，保留 MC-2 勘误；未实施 slices、未新增/执行测试，经济残留未关闭，基线、白名单、冻结表与 §8 命令不变。
- **v0.1.1 (2026-09-19)**：r1 勘误——§2 书 NAV 收窄为「传入 close；none/raw 才是 raw mark」（见 reviews `plan-industry-align-p3-d345-econ-r1` MC-2）。
- **v0.1 (2026-09-19)**：post #123 核实 δ2/E-R6 仅参考价与书/v7 原股数/现金残留，隔离 Mode B fractional-shares 近似；打开经济 deferred 面，提出必须人裁 A/B/C（默认 A，可 B）、生命周期设计与纯送转/现金/混合 NAV oracle。仅 docs，无生产/测试修改、无回测/湖，经济残留未关闭、C 未授权。
