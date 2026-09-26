# 策略 8 家族：按信号日期独立持仓（2026-09-26）

本工作树基于 master `5518323`，分支 `fix/s8-independent-positions`。本次直接纠正六本书的默认 `per_name` 行为：8、8.2、8.3、8.4、8.5、8.6；不增加开关或新策略版本。日线及分钟 `fix_minute_cash_order=False/True` 都在范围内。8.1、v7、其他书及六本书的非 `per_name` 行为不在范围内。

本次按用户要求纠正默认规则。首次复现既有低资金 fixture 的预期冲突后曾暂停；用户随后明确批准仅迁移目标六书旧低资金/`skip_cash` 预期，并要求校验现金异常的五个字段。所有资金、8.1 及其他书的 `skip_cash` 预期保持原值。默认 2,100 万场景或目标 OFF golden 如出现资金不足，仍须停止报告。

## 1. 规则及实现口径

1. 池中同码在后续信号日期再现时，建立新的独立持仓，身份形如 `600000.SH@20251031`。再现不是旧仓加仓，不再用旧仓全部 lots 的成本/峰值调用 `add_gate`。**新信号，包括已有同码时的再现，按新仓经过指数新仓 gate**。8.2 本身没有指数 gate，继续没有。六书继续允许卖出当天按新信号首买，没有增加 `skip_sold_today`。
2. 每个独立持仓有自己的首笔成本、预算和价格加仓状态。8/8.4/8.5 以自己的首笔成本为锚，按原有 +20% 台阶触发，每次仍使用一份 `name_budget`；按该持仓历史成功执行级数计数，成交后递增，step lot 卖出不回退。原首笔 lot 卖出但该组其他 lots 尚在时，仍保留该组成本锚及级数；所有 lots 卖完才关闭，关闭后不再加仓。
3. 8.3 每次独立信号各有 50% 试仓、50% 确认补仓。补仓检查该持仓自身 `px >= 首笔成本` 且 `peak >= 首笔成本 × 1.03`，与当天是否在池无关；成功后本持仓只补一次。8.2、8.6 不增加价格加仓。
4. 价格加仓沿用已有扫描时点：日线在收盘池买之后扫描，分钟在 14:55 池买之后扫描，沿用 14:30–14:55 缺 bar 回退。8.3 分钟 OFF 的确认峰值限定截至 14:55，防止全日卖出扫描写回的15:00新高倒灌补仓判断；不改变原卖出扫描峰值或资金结算顺序。原“每码每日最多一笔台阶”改为“每独立持仓每日最多一级”。涨停时价格加仓仍跳过、不生成追买。8.3 价格补仓继续遵守自身 `INDEX_BLOCKS_ADD=True`；8/8.4/8.5 的旧持仓价格台阶不受仅挡新仓的指数 gate 限制。
5. 追买队列按独立信号身份保存，携带规范代码、原信号日期及预算，不同日期互不覆盖。8.3 的预算先算为 50% 再入队，消除旧 `per` 变量泄漏导致首次追买用 100 万的问题。分钟继续使用 09:45/原有回退；日线继续用当日 open 与 close 近似该条件。T+1 从实际成交日计算。
6. 首仓及加仓 lot 继续按各自成交价、入场日、peak、止损/止盈/trail/stale、T+1、跌停延迟规则独立退出；卖出一个 lot 不会连带其他日期持仓。未改变两引擎原有的卖出成交时点，以及分钟 OFF 先处理全日旧仓卖出、ON 按真实时点处理的区别。
7. 六书 `per_name` 下，池首买、追买、价格加仓的现金必须足以支付按原整手规则算出的买单及费用；不足抛出 `InsufficientCashError` 并停止。异常包含 `date`、`code`、`needed`、`available`、`shortfall`。不缩单、不改预算、不提高默认总资金 `21,000,000`。8.1 和其他书继续原 `skip_cash`。
8. 目标书 trades 的 BUY/SELL/EOD_MARK 在保留原列后增加 `position_id`、`entry_signal_date`；存活 lot 序列化也带这两个字段。lot 编号按持仓从 0 开始，完整归属键为 `(position_id, lot)`；跨信号日期同为 lot 0 不会混淆。未对非目标书增加输出列或统计键。六份 HELP_LOCK 已按上述口径修订，删除“单码单日上限 2 笔”。

## 2. Baseline 保存方式与范围

原文件 `tests/fixtures/off_byte_baseline_eff77f3.json` 与 `tests/fixtures/off_canonical_baseline_eff77f3.json` 保持逐字节不变，SHA-256 分别为：

- raw：`3bfe51b6d3e20b665c3fed0449ebf8569988022719da275b7fcc9635a9988c6c`。
- canonical：`34f611da359f1a1d059bc78be75b2e9e2458c533b1dc3b46cfd61130fca7a04e`。

新增 `tests/fixtures/off_byte_baseline_s8_independent_20260926.json`，仅保存六书 × 日线/分钟共 12 case。`tests/test_off_byte_baseline.py` 仍执行全部 39 case 的参数省略及显式 OFF 两种调用；目标 12 case 选择新文件，其余 27 case 继续原 raw/library CSV 字节与 canonical/account 契约。新增测试锁定两个历史文件哈希和新文件覆盖范围。`generate_off_byte_baseline.py --check` 使用同样的选择逻辑；`--record-s8` 只可录制这 12 case，要求 pandas 3.0.6，且拒绝覆盖已有新文件。

原 fixture 参数未改：总现金 500 万、单笔预算 100 万，同一 `600000.SH` 在 2025-10-29、10-31、11-06 三次入池。该 fixture 没有触发现金不足或涨停追买，价格也未达到 +20% 台阶。因此它验证输出兼容和 8.3 的确认补仓，不能替代专门的台阶、追买、现金失败及分钟 ON 场景测试。

以下均比较旧 eff77f3 baseline 加既有 #205 的 `daily_quota` 元数据，与本次新文件；金额单位为元。所有 12 case 的 trades 字节均因身份列而改变。除 8.3 两例外，其余 10 case 的 equity 原始字节、成交金额、价格、日期和卖因均保持不变。没有新增 stats 键。

| Case | BUY/SELL 旧→新 | 期末现金旧→新 | 期末权益旧→新 | 本例差异及原因 |
|---|---|---|---|---|
| version8/daily | 3/3→3/3 | 5,116,090.9375→同值 | 5,116,090.9375→同值 | 仅身份列；原 lot 都是 0，stats 无差异；10/31 卖后再首买保留。 |
| version8/minute | 3/3→3/3 | 5,121,173.35→同值 | 5,121,173.35→同值 | 仅身份列；原 lot 都是 0，stats 无差异。 |
| version8_2/daily | 3/1→3/1 | 2,958,862.825→同值 | 4,969,862.825→同值 | 三次首买从全码 lot 0/1/2 变为各组 lot 0；两笔存活仓/EOD_MARK 增加身份；`add_lots` 2→0，再现不再算加仓。 |
| version8_2/minute | 3/1→3/1 | 3,008,812.825→同值 | 5,019,812.825→同值 | 同上；逐 lot 卖点和两个未平仓数量不变；`add_lots` 2→0。 |
| version8_3/daily | 3/2→6/5 | 4,395,790.5625→4,308,003.6375 | 4,935,790.5625→4,848,003.6375 | 三个日期组各增加一次确认补仓及独立退出；期末仍持 11/06 首买 54,000 股。详细成交与 stats 见下。 |
| version8_3/minute | 2/2→6/5 | 4,945,740.0625→4,380,381.1875 | 4,945,740.0625→4,920,381.1875 | 取消旧仓 `skip_add_loser` 后新增 11/06 首买，三组各补一次；期末新增该组 54,000 股/EOD_MARK。详细成交与 stats 见下。 |
| version8_4/daily | 3/2→3/2 | 3,790,655.2→同值 | 4,871,655.2→同值 | 10/31 首买和其卖出 lot 1→组内 lot 0；存活 11/06 仓/EOD_MARK 标识身份；`add_lots` 1→0。 |
| version8_4/minute | 3/1→3/1 | 2,891,555.2→同值 | 4,972,555.2→同值 | 10/31、11/06 首买 lot 1→各组 lot 0，避免旧编号复用歧义；两笔存活仓/EOD_MARK 标识身份；`add_lots` 2→0。 |
| version8_5/daily | 3/3→3/3 | 5,046,410.6875→同值 | 5,046,410.6875→同值 | 仅身份列；lot 与 stats 无差异，逐 lot 卖点不变。 |
| version8_5/minute | 3/3→3/3 | 5,019,412.7125→同值 | 5,019,412.7125→同值 | 仅身份列；lot 与 stats 无差异，逐 lot 卖点不变。 |
| version8_6/daily | 3/3→3/3 | 5,116,090.9375→同值 | 5,116,090.9375→同值 | 仅身份列；lot 与 stats 无差异，没有价格加仓。 |
| version8_6/minute | 3/3→3/3 | 5,121,173.35→同值 | 5,121,173.35→同值 | 仅身份列；lot 与 stats 无差异，没有价格加仓。 |

8.3 两引擎新增的三笔确认买均为 `reason=add:confirm3`、组内 lot 1：10/30 买 47,600 股 @10.5，归属 10/29 信号；11/03 买 45,400 股 @11，归属 10/31 信号；11/07 买 51,200 股 @9.75，归属 11/06 信号。预算均为 50 万，成交本金按整手向下取整，佣金沿原规则另扣。

日线新增加仓 lot 的退出分别为：10/29 组加仓 lot 在 11/05 以 9.625、`trail:band:2` 卖出；10/31 组加仓 lot 在 11/05 以 9.625、`stop_loss:gap_open` 卖出；11/06 组加仓 lot 在 11/13 以 10.125、`trail:band:2` 卖出。原三笔首买及原有两笔卖出的价格/日期/数量不变，10/31 的首买及卖出 lot 1 改为该组 lot 0。逐 lot 退出会让同组补仓和首买在不同日期退出；权益下降 87,786.925，来自新增补仓的盈亏与费用，并非重设旧仓退出线。

分钟中，11/06 的 54,000 股 @9.25 原来因旧仓亏损被跳过，现在按新信号首买并期末保留；新增加仓 lot 分别在 11/04 以 10.5、`trail:band:2`，11/05 以 9.625、`stop_loss:gap_open`，11/12 以 9.75、`trail:band:2` 卖出。旧两笔首买及旧两笔卖出的经济字段保持不变，10/31 首买/卖出 lot 1 改为该组 lot 0。权益下降 25,358.875，来自新增的三笔确认补仓、恢复的 11/06 首买及费用。

8.3 的全部 stats 差异：

| 字段 | 日线旧→新 | 分钟旧→新 | 原因 |
|---|---|---|---|
| `buys` | 3→6 | 2→6 | 每组确认补仓；分钟另恢复一次再现首买。 |
| `add_lots` | 1→3 | 1→3 | 再现首买不再算加仓，只统计三笔组内补仓。 |
| `sell_stop` | 2→3 | 1→2 | 10/31 组新增补仓 lot 独立止损。 |
| `sell_trail` | 0→2 | 1→3 | 另外两组补仓 lot 独立回撤退出。 |
| `skip_add_loser` | 0→0（不变） | 1→0 | 11/06 再现不再受旧持仓 gate 限制。 |
| `invested_notional` | 1,499,375→2,997,775 | 999,875→2,997,775 | 新增实际成交本金；不含佣金。 |

### 2.1 S1/策略12旧输出指纹的必要更新

`tests/test_partial_sell.py` 另有一份较早的24case快照。原 `tests/fixtures/strategy12_default_outputs.json` 保持原字节，SHA-256为 `2f578d6fe9e601ad84a94bb6a269e1b5193c51ca4dd908366022769f0e1f31c2`。新增 `tests/fixtures/strategy12_default_outputs_s8_independent_20260926.json` 只覆盖原矩阵中的8/8.2/8.3 × 日/分钟6case；其余18case继续校验历史hash。临时仅在比对探针中禁用新配置后，全部24case精确复现旧hash，确认没有把其他变化重录进去。**这组fixture使用默认总资金21,000,000，资金未改且无不足异常。**

| Case | BUY/SELL旧→新 | 期末现金旧→新 | 期末权益旧→新 | 原因 |
|---|---|---|---|---|
| version8/daily | 3/3→3/3 | 21,188,058.33→同值 | 21,188,058.33→同值 | 仅trades身份列变化，stats和equity字节不变。 |
| version8/minute | 3/3→3/3 | 21,107,958.51→同值 | 21,107,958.51→同值 | 同上。 |
| version8_2/daily | 3/2→3/2 | 20,074,213.29→同值 | 21,000,383.29→同值 | 三次首买全码lot0/1/2改各组lot0；BUY/SELL/EOD增加身份；add_lots2→0，equity字节不变。 |
| version8_2/minute | 3/2→3/2 | 20,135,482.5594→同值 | 21,061,652.5594→同值 | 同上，仍留一个EOD lot。 |
| version8_3/daily | 3/3→5/4 | 20,946,540.892→20,417,310.652 | 20,946,540.892→20,942,510.652 | 两组增加确认补仓、一笔新增卖出，期末新增一个加仓lot；trades/equity字节都变。 |
| version8_3/minute | 2/2→5/4 | 20,947,717.6942→20,516,589.0742 | 20,947,717.6942→21,041,789.0742 | 恢复11/06再现首买、两组确认补仓、逐lot独立退出；期末留一个加仓lot，trades/equity字节都变。 |

8.3两引擎各新增10/30买47,600股@10.5（归10/29组）、11/07买52,000股@9.6（归11/06组），均为 `add:confirm3`。10/31组自身峰值11.22未达到10.9×1.03=11.227，所以没有补仓；这与主baseline的行情不同，并非规则差异。

日线第一新增lot在11/05以9.9按`trail:band:2`卖出；最后新增52,000股期末按10.1标价525,200元。原三买三卖经济字段不变，总权益差−4,030.24。分钟取消11/06旧`skip_add_loser`后新增54,900股@9.1的首买，11/10以10.3按`trail:band:3`卖出；第一新增确认lot在11/04以10.6按`trail:band:2`卖出；末次确认lot同样存留期末。原两买两卖经济字段不变，总权益差+94,071.38。

8.3全部stats差异：日线`buys`3→5、`add_lots`1→2、`sell_trail`1→2、`invested_notional`1,498,810→2,497,810；分钟`buys`2→5、`add_lots`1→2、`sell_trail`1→3、`skip_add_loser`1→0、`invested_notional`999,220→2,497,810。其余stats均不变。

## 3. 获批迁移的低资金旧测试

以下 **18 个既有参数 case** 改为断言 `InsufficientCashError`，逐项校验 `date`、`code`、`needed`、`available`、`shortfall`。这些用例原本刻意验证目标书低现金跳单，与新规则直接冲突；不提高资金、不缩小预算，不改其他书预期。表中金额为元；`needed / available / shortfall` 均含原费用约定。

| 文件与测试 | 改动参数 case | date / code | needed / available / shortfall | 原因及保留断言 |
|---|---|---|---|---|
| `test_minute_cash_chronology.py::test_pool_boundary_same_close_sell_proceeds_are_immediately_available` | `close-896-False`、`open-896-False`（2） | 20260902 / 600001.SH | 600.60 / 0 / 600.60 | 14:55 买时 14:56 卖款尚不可用；中断前 audit 只有已成交首买。 |
| 同文件 `test_chase_cannot_spend_afternoon_sale_and_does_not_retry` | ON（1） | 20260902 / 600001.SH | 600.60 / 0 / 600.60 | 09:45 追买不能借 14:59 卖款；OFF 原成功与现金338.46断言保留。 |
| 同文件 `test_unsold_position_contributes_no_cash` | `no_signal`、`limit_down`、`zero_capacity`（3） | 20260902 / 600001.SH | 600.60 / 0 / 600.60 | 没卖出不产生现金；捕获中断账户，保留旧仓100股、现金0断言。 |
| 同文件 `test_partial_sale_only_credits_actual_shares_net_of_fee` | `min_cost=0`、`min_cost=5`（2） | 20260902 / 600001.SH | 1801.80 / 1408.59 / 393.21；1805 / 1405 / 400 | 部分卖150股扣费用后不足支付预算对应整单；保留余50股、peak10和实际卖出断言。 |
| 同文件 `test_whole_pool_denominator_ration_and_commission_match_legacy` | `version8_2-file_order`、`version8_2-seeded_shuffle`（2） | 20260901 / file_order为600002.SH，shuffle为600001.SH | 均1001 / 0 / 1001 | 两例分别验证OFF/ON错误及先前两笔成交audit一致。**version8_1两例原预期保留**。 |
| 同文件 `test_close_clear_milestones_with_chronological_clock` | `version8_5-4-force_sell:t4_close-900-False`、`...-896-False`（2） | 20260907 / 600001.SH | 600.60 / 0 / 600.60 | 14:55买时15:00/14:56末bar强平尚未发生；14:50先强平的原成功例保留。 |
| 同文件 `test_close_clear_milestones_with_chronological_clock` | `version8_6-1-force_sell:t1_close-900-False`、`...-896-False`（2） | 20260902 / 600001.SH | 600.60 / 0 / 600.60 | 同上，保持8.6原真实末bar强平时钟。 |
| `test_minute_cash_audit.py::test_sidecar_preserves_state_and_records_real_clock_cash` | `True`（1） | 20251105 / 600001.SH | 600.60 / 0 / 600.60 | 有/无audit均抛相同字段异常，audit仅有中断前首买。False原成功预期保留。 |
| 同文件 `test_shared_cli_audit_sidecar_preserves_csv_surface` | `True`（1） | 20251105 / 600001.SH | 600.60 / 0 / 600.60 | CLI传播异常，不写未完成的trades.csv/audit文件；False原成功预期保留。 |
| `test_minute_cash_red.py::test_chronological_cash_cannot_borrow_future_proceeds` | ON（1） | 20251105 / 600001.SH | 600.60 / 0 / 600.60 | 14:55不能使用14:59卖款；原OFF借用未来卖款的历史行为测试及现金338.46断言保持原文。 |
| `test_csv_daily_backtest.py::test_d4_step_none_limits_rejects_before_floor_cash_gate` | `one-fen-short-known_board`（1） | 20251103 / 600000.SH | 1205 / 1204.99 / 0.01 | 台阶单本金1200、最低佣金5，差1分即停；账户现金和首仓不变、无成交。无昨收/未知板块仍在现金前跳过，足额1205仍成交。 |

非资金预期的必要适配：

- 日线/分钟 v8 再现测试改为不同 `position_id` 的组内 lot0，`add_lots` 不再统计再现首买。
- `test_csv_simulate_v8_hooks.py` 的状态显式配置六书新默认；再现受指数新仓 gate。
- `test_ashare_volume_cap.py::test_public_book_pool_step_share_actual_quote_bucket` 与上表日线台阶测试的手工预置仓加入独立组身份。保持原资金和共享行情桶容量验证。
- 两处手工 pending 由代码键改为代码@原信号日期：`test_fallback_quote_does_not_backdate_decision_or_borrow_capacity[584-580]`、`test_chase_cannot_spend_afternoon_sale_and_does_not_retry`。
- 旧 `test_opening_snapshot_pool_plan_budget_and_step_see_current_lots` 改名 `test_opening_snapshot_sees_codes_but_reappearance_budget_sees_new_position`：开盘快照仍按码，再现预算只看新仓，旧全码 step hook 不再参与独立组加仓。
- 旧 `test_future_high_cannot_open_add_gate` 改名 `test_future_high_does_not_gate_reappearance_or_set_new_peak`：再现绕过旧add_gate，两日分别首买；旧仓peak11，T0新仓peak10，不受旧仓及后续high污染。

## 4. 验证

解释器 `~/.venvs/bt-ci/bin/python`，pandas 3.0.6。专项追买样例已使用显式 warmup 昨收构造真实涨停，断言源信号日、实际成交日和50%预算。新增 `tests/test_s8_independent_positions.py` 共27个测试函数、157个参数化用例，全部通过。覆盖日线、分钟OFF/ON、并存追买、每仓历史级数、首lot卖后的台阶及除权锚、8.3各自50/50、指数gate、T+1/peak/stale/跌停、现金异常、8.1与其他书隔离，以及同日重复信号不误报现金不足。

四个 contract gates 与 `ruff check bt_contract` 已通过；主OFF/canonical基线测试105通过。旧低资金相关三文件94通过；日线台阶费用边界六例通过；补充的原现金时钟两例通过。专项与两套baseline联合复核270项通过。

完整CI已通过：

```text
~/.venvs/bt-ci/bin/python scripts/gates/verify_oskh_data_contract.py
~/.venvs/bt-ci/bin/python scripts/gates/verify_data_path_ssot.py
~/.venvs/bt-ci/bin/python scripts/gates/verify_no_hardcoded_machine_paths.py
~/.venvs/bt-ci/bin/python scripts/gates/verify_tr_bridge_import_ssot.py
# 四项均通过
~/.venvs/bt-ci/bin/python -m ruff check bt_contract
# All checks passed!
~/.venvs/bt-ci/bin/python -m pytest -q -m "not production and not benchmark"
# 2812 passed, 67 skipped, 24 deselected, 10 warnings in 33.36s
```

独立只读审查发现并复现了8.3分钟OFF读取15:00未来peak的问题，已修复并加强14:55价格10.01、15:00首次峰值10.4的回归，确认OFF/ON均等到次日补仓。最后全套选择是在该修复后运行；没有用主/次baseline重录掩盖此次缺陷，修复前后两套已录目标快照仍一致。所有修改Python/Markdown按UTF-8无BOM保存，NUL为0。本次仅创建获授权的本地commit，不push、不开PR、不merge。

## 5. 保留语义与未决问题

- 首买与价格加仓 lot 继续各自按成交价独立退出，已按要求实施并测试；“是否最终改为组内统一退出”保留为待用户确认的策略问题，本次没有组内连带卖出。
- 六书保持卖出当天允许新信号首买；分钟OFF先结算全日旧仓卖出、ON按时点结算、日线追买用open/close近似09:45等原时钟均保留。
- 原人工分析包按代码FIFO配对、按代码汇总持仓的后处理未纳入本次引擎修改；原始trades的身份列不表示该后处理已经按身份正确归因，消费新输出时需另行迁移核验。
- 低资金旧测试与新规则的冲突已按用户明确批准迁移；目前未发现需要变更用户业务规则的冲突。默认资金与目标OFF golden均未因新规则报资金不足。

## 6. 改动文件

- 成交/持仓与引擎：`backtest/research/csv_ledger.py`、`csv_simulate_loop.py`、`csv_daily_backtest.py`、`csv_minute_backtest.py`、`minute_cash_order.py`。
- 六书说明：`backtest/research/strategy8_rules.py`、`strategy8_2_rules.py`、`strategy8_3_rules.py`、`strategy8_4_rules.py`、`strategy8_5_rules.py`、`strategy8_6_rules.py`。
- 主baseline：`scripts/research/generate_off_byte_baseline.py`、`tests/test_off_byte_baseline.py`、`tests/fixtures/off_byte_baseline_s8_independent_20260926.json`。
- 次级baseline：`tests/test_partial_sell.py`、`tests/fixtures/strategy12_default_outputs_s8_independent_20260926.json`（仅六个目标case，见§2.1）。
- 测试：`tests/test_csv_daily_backtest.py`、`test_csv_daily_backtest_v8.py`、`test_csv_minute_backtest_v8.py`、`test_csv_simulate_v8_hooks.py`、`test_ashare_volume_cap.py`、`test_minute_cash_chronology.py`、`test_minute_cash_audit.py`、`test_minute_cash_red.py`、新增 `test_s8_independent_positions.py`。
- 说明：本文；另更新用户指定的 `/home/box/agent-data/bt-s8-reappear-2026-09-26/prb-body.md`，不创建远程PR。
