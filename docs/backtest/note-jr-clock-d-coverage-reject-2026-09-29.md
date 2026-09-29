# JR-clock D bars/marks 覆盖核验：未完成 / REJECT pending host（2026-09-29）

基线：BT `05adce625b21dd3e7821517c70c177404fd2ae34`（#263）；分支 `feat/d-jr-clock-coverage`。授权：[Human D GO][go]（2026-09-29 约 20:04 CST，4090，只读覆盖核验）。依据：[ORDER_EVAL §8][order]、[身份对账 §5 gate D][identity]、[时钟交接 §2 D][handoff]。`production_C=frozen`。

## 1. 判定与证据边界

**本次 bt D：未完成 / REJECT pending host。** [HOST_D_EVIDENCE.md][host] 已收到，宿主给出的结论是 `ACCEPT missing_bars=0 missing_marks=0`；[coverage_numbers.json][numbers] 与其数字一致。但 bars 的分母来自 bars 自带的 `metadata.sessions`，尚缺完整执行/估值时点与该分母相容的证明：pack 执行日历多出尾部 `2026-01-05`，bars 止于 `2025-12-31`。此外，材料列出 bars seal 值，未报告该 pin 的 seal 复核结果。故保留已测零缺口，不将其升级为完整 D ACCEPT；待补项见 §5。

本次只读审查共享目录中的宿主报告、数字转储及仓内规范；未连接 4090、读取原始 8.73 GB bars 或运行 replay。下列宿主事实均注明来源，不声称在本机重新扫描过行情或复算过 pack/seal。**本结论不授权 E/F；E 与 F 各需独立 Human GO。** `narrow_clock_full_20260924` 的历史 B–G 完成态不变，不重新设置 `NOT_READY_FOR_MODE_B`，不推断存在 stalled pack。

## 2. 证据定位

[宿主报告][host]：`newtest_4090` / 4090bot，2026-09-29 Asia/Shanghai；方法为 `ijson` 流式扫描。数字转储记扫描开始 `2026-09-29T20:11:59.892024+08:00`、耗时 396.7 s。以下路径来自报告及数字转储，均为定位记录，不是本机访问结果。

| 对象 | 宿主路径 / 定位 |
|---|---|
| MQ run root（下文 `RUN`） | `D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95` |
| pack root（下文 `PACK`） | `D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_full_20260924` |
| B/C 回执及 pack 输入 | `PACK\RECEIPT_CLOCK_REGEN_FULL.md`（5581 B）、`PACK\CLOCK_PREP.md`（1539 B）；`PACK\metadata.json`、`freeze_metadata.json`、`sessions.json`、`snapshot.json` 均由 host 报告存在 |
| 成功线日志 | `RUN\_clock_full_pipeline_20260924_cf.log`（4464 B）；host 明确 **pack 目录下同名日志不存在**，实际位于 run root；纠正身份对账旧定位，不作为行情缺口 |
| 收窄 intents / manifest | `PACK\portfolio\joint-return-control-only-50-5-narrow-clock-614\intents.csv` / `manifest.json` |
| execution calendar | `RUN\handoff_bt_20260922\narrow_clock_20260922\execution-calendar.json`；该来源目录名不改变本次 full-regen pack 身份 |
| 本次 primary bars + marks pin | `D:\exports\joint_return_pbase_narrow_20260922\frozen_explicit_bars_clock_full_614_with_marks.json`（8,730,501,508 B）；host 按 `RECEIPT_CLOCK_REGEN_FULL.md` §5 F 定位 |
| 宿主计算材料 | `D:\exports\d_jr_clock_coverage_20260929\_verify_coverage_stream.py`、`D:\exports\d_jr_clock_coverage_20260929\coverage_numbers.json`；本机仅收到后者的转储 |

`frozen_explicit_bars_clock_patch_pin.json` 与 `frozen_explicit_bars_clock_patch_pin_with_marks.json` 仅被 host 列为同目录相关文件，**不作为本次 primary pin**。未以旧包的证券数或 marks 数代替 full-regen intents 的键集合核验。

本机对收到的证据文件计算 raw-byte SHA-256，仅绑定本次审阅版本，不是宿主 pack 的 content hash：

| 本地证据 | SHA-256 |
|---|---|
| [HUMAN_GO.md][go] | `c4835bafe76c6fc7566ccfb07ae33508c5aa5919e6854e0e3a16a549d174f21a` |
| [HOST_D_EVIDENCE.md][host] | `7e8758482d0d96be5c2429d2ac6f5ad034d12c6cfc0610eada50f1c1a70ff9ff` |
| [coverage_numbers.json][numbers] | `ad193cfa163c75a9881e8350ae5a3712ce7e50a0829f1ed864187c1ff15e0147` |

## 3. 身份、窗口与证券集合

来源：[宿主报告][host] Identity / Windows / Universe；[数字转储][numbers] `identity`、`portfolio_manifest`、`calendar_file`、`sessions`、`universe`、`bars_file`。下表 hashes 为 host 从 metadata / manifest / pin 读取的登记值。

| 字段 | 宿主证据 |
|---|---|
| pack | `narrow_clock_full_20260924` |
| contract prefix / full hash | `c6b85b9b…` / `c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7`；pack、收窄 manifest、bars metadata 登记值相同 |
| registered MQ code_sha | `b072cc3bef6f2a49af32de6c904ebf34256e55cc` |
| registered BT code_sha | `2f7937514c8d42769e02f8733c749e9b6bc966b1`；不替换为本次文档 tip |
| C run_id（full / narrow） | `joint-return-control-only-50-5-narrow-clock` / `joint-return-control-only-50-5-narrow-clock-614` |
| narrow manifest kind / intent_hash | `frozen` / `a52b6e293a1e79ef12647f5bea168a973142047853ff9da5c36eaf7f3eca0071` |
| scores content_sha256 | `11903c5b0c61c2c41123ba2693f2d595e99fc0b80fd8416e99ac246b12acfdb6` |
| freeze generated_at / pred_recorder_id | `2026-09-25T02:35:55+08:00` / `8a061ea428e04bb3a199a485ade49d0e` |
| valuation/scores window | `2025-01-02` → `2025-12-31` |
| execution calendar | 244 天，`2025-01-02` → `2026-01-05`；外部 calendar 文件与 pack `execution_calendar` 相等 |
| pack sessions | 243 行，decision 日期 `2025-01-02` → `2025-12-31`；首 `available_at` / `effective_at` = `2025-01-03T09:30:00+08:00` |
| tail next session | 最后 `available_at` / `effective_at` = `2026-01-05T09:30:00+08:00`；最后 `expires_at` = `2026-01-05T15:00:00+08:00` |
| bars calendar | 243 天，`2025-01-02` → `2025-12-31`；与 pack execution calendar **不相等**：`only_pack=[2026-01-05]`、`only_bars=[]`；[宿主报告][host] 第 59 行将该尾日归类为 “next-session day after last decision date; not a bars trading day” |
| universe | 614 证券；1891 intents，unique intent_id=1891，duplicate intent_id=0 |
| bars kind / 时间与价格域 | `frozen_explicit`；`OPEN_TIME` / 60 秒；`Asia/Shanghai` / `none` |
| bars content_sha256（登记 seal） | `83e7deae9ea580aa1aad208cc1751ad84df8157179751e252a0d43c1e28d8cdd` |

Host 报告 `identity_ok=true`。这支持上述登记身份对账；报告未提供全部 intents 的执行时点范围或尾 session 需求核对结果。`sessions.json` 的 clock 尾日存在已有记录；该日期的 bars 覆盖属于另一项核验，尚未证明，在 G1 下仍为 **未知**。

## 4. 已测 bars / marks 覆盖

来源：[宿主报告][host] Bars coverage / Marks coverage / Computation note；[数字转储][numbers] `bars_coverage`、`marks_coverage`。**下表的 0 均来自 host，不是按缺失字段补零。**

| 核验范围 | expected | observed / present | missing |
|---|---:|---:|---:|
| bars：pin 自带 `metadata.sessions` 的 58,563 个分钟机会 × 614 证券 | 35,957,682 | 35,957,682 | **0** |
| marks：本次 full-regen 收窄包的 intent_id 键集合 | 1,891 | 1,891（present ∩ expected） | **0** |
| 完整 D 所需执行/估值分钟与上述 bars 分母的相容性（含尾日处理） | 待宿主给出独立需求集合 | 尚未证明集合包含关系 | **未知，不记为 0** |

Bars raw rows=35,957,682；unknown instrument / outside session / duplicate key 均为 0；mapping 与 bars 均有 614 证券，mapping 中无 bars 的证券数为 0。本机仅复核算术 `58,563 × 614 = 35,957,682`，未扫描原始 bars。

Marks 总键数=1,891、extra=0，`exact_key_set_match=true`；这比计数相等更强，确实覆盖这 1,891 个 intent_id。字段检查仅为 **前 50 条**无异常（标的、代码、时点、域、source_kind、非 1.0 占位价），不转述为全部 1,891 条字段校验或真实源验真通过。

Host 采用的 bars 计数规则与 [frozen explicit 覆盖规则][price]、`validate_bars` 中“声明 session 分钟 × universe”的分母一致。但流式计数报告不是完整 `validate_bars` / `validate_reference_marks` 执行回执；原函数的 metadata、seal 及逐条字段校验不可由上述计数替代。

## 5. 拒绝原因与待补宿主证据

| 缺口 | 当前证据为何不足 | 转为 ACCEPT 前需补的只读证明 |
|---|---|---|
| G1：完整执行/估值窗口与 bars 需求集合尚未对齐 | 计数分母取自 bars 本身；pack 最后可执行 clock 落在 `2026-01-05`，该日不在 bars calendar。Host 已给出 §3 所引尾日分类；但报告未打印 manifest `metadata.calendar` 与 bars `metadata.calendar` 的相等性核验，也未给出 1891 intents 的执行窗分布及逐 intent 尾日处理，尚未证明尾日依合同不需要 bars | 从本次 pack / manifest / intents 与估值规则确定需求时点，逐项对照 pin 的 calendar / sessions。若尾日不属于本次研究观测窗，须给出合法截断依据及受影响 intents 的处理核对；若属于需求，报告其 expected / observed / missing。现阶段不假定尾日必须补几行，也不把“未测”写成 0 |
| G2：seal 登记值未附复核结果 | `content_sha256` 已提供，但报告与数字转储未记录 canonical content hash 复算相等或可绑定此 pin 的既有 seal 校验回执 | 补该精确 pin 的只读 seal 校验结果，或可核对至该工件的既有完整校验回执；记录登记值、复核值及相等结果。沿用既有合同，不修改工件或重写 seal |

仅当宿主补足范围相容与 seal 证明，且所需 bars missing=0、marks missing=0 均有对应证据，才能另行记录 D ACCEPT。补证不等于获准导湖；若发现真实行情缺口，先列 gap，再另获 Human GO。本次不推导或伪造完整窗口的 missing 数字，不启动补数任务。

## 6. 范围锁与交付验证

- 无 lake export；不探盘，不造 bars/marks，不重映射旧 marks，不覆盖 pack、outs、旧回执或 seals。
- 不重生成 clocks，不运行 B/C/E/F，不更改任何生产 `.py`；G5 分配政策、fill/fee/clock/tie-break、L1/L2 均不在本刀范围。
- 仅新增本 note，并在身份对账 §5 增加本次独立 D GO 的结果指针；不改历史 B–G 归档结论。
- 验证为证据转储对账、算术、文档路径/链接、allowlist、UTF-8 无 BOM / NUL=0、`git diff --check`。未运行代码测试、宿主 replay 或行情导出。

提交、PR 和验证结果写入 [D_RECEIPT.md][receipt]。**未经 Human「合」不合并；本次 REJECT 记录不授权 E/F。**

[go]: /workspace/handoffs/d_jr_clock_coverage_20260929/HUMAN_GO.md
[host]: /workspace/handoffs/d_jr_clock_coverage_20260929/HOST_D_EVIDENCE.md
[numbers]: /workspace/handoffs/d_jr_clock_coverage_20260929/coverage_numbers.json
[order]: /workspace/handoffs/next_tracks_abcde_order_20260929/ORDER_EVAL.md
[identity]: note-jr-clock-pack-identity-reconcile-2026-09-29.md
[handoff]: handoff-joint-return-clock-regen-2026-09-24.md
[price]: joint-return-frozen-explicit-price.md
[receipt]: /workspace/handoffs/d_jr_clock_coverage_20260929/D_RECEIPT.md
