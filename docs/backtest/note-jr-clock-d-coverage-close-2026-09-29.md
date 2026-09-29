# JR-clock D bars/marks 覆盖 G1/G2 收口：D ACCEPT（2026-09-29）

基线：BT `f267e60cbda76a0d349a966d6403f4ab83f91e24`（[#264][prior-pr]）；分支 `feat/d-jr-clock-close`。授权：[Human D-close GO][go]。本次接续 [D 初次 REJECT 记录 §5][reject]，仅审阅宿主 G1/G2 补证并记录 D 接收；`production_C=frozen`。

## 1. 判定与证据边界

**本次 bt D：D ACCEPT。G1 CLOSED，G2 CLOSED；所需 bars missing=0、marks missing=0 的既有宿主证据继续成立。** [HOST_D_CLOSE_EVIDENCE.md][host-close] 已补齐 manifest/bars 日历相等、尾日逐 intent 处理及精确 pin 的完整 seal 复算；[g1_g2_numbers.json][close-numbers] 与报告一致。#264 的 **REJECT pending host** 是补证前的历史判定，原文保留，本 note 记录后续状态变化。

本结论基于 `newtest_4090` / 4090bot 于 2026-09-29 Asia/Shanghai 提供的只读报告，以及 [此前覆盖报告][host-prior] / [coverage_numbers.json][prior-numbers]。本机核对这些材料与算术、文档，不声称重新扫描 8.73 GB bars、复算宿主 pin 或运行 replay。宿主报告已完整给出本刀要求的 G1/G2 证据；剩余 G1/G2 residue：**无**。这不是完整 replay 或全部 marks 字段/真实源验真的新回执。

**D ACCEPT 不授权 E/F；E 与 F 各需独立 Human GO。未经 Human「合」不合并。** 历史 B–G 完成态不变，不重设 `NOT_READY_FOR_MODE_B`，不重跑 B/C。

## 2. 证据与工件绑定

以下宿主路径为报告定位，本机未访问原始工件：

| 对象 | 定位 / 身份 |
|---|---|
| pack root（`PACK`） | `D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_full_20260924` |
| narrow manifest / intents | `PACK\portfolio\joint-return-control-only-50-5-narrow-clock-614\manifest.json` / `intents.csv` |
| 合同 / manifest intent_hash | `c6b85b9b8fdb4799425980b98f51596ed5b4d3a9ca781092e06f81a0a14d11f7` / `a52b6e293a1e79ef12647f5bea168a973142047853ff9da5c36eaf7f3eca0071` |
| primary bars + marks pin | `D:\exports\joint_return_pbase_narrow_20260922\frozen_explicit_bars_clock_full_614_with_marks.json`；8,730,501,508 bytes |
| close 宿主数字定位 | `D:\exports\d_jr_clock_close_20260929\g1_g2_numbers.json`；报告另列 `g2_numbers.json`、`g1_intents.json`、`bars_calendar.json`，本机收到的是合并数字转储 |

完整登记身份沿用 [初次记录 §3][reject]；不以本次文档 tip 替换 pack 的 MQ/BT code_shas，不换用 `clock_patch_pin`。以下为本机对收到材料计算的 **raw-byte SHA-256**，只绑定审阅版本，不是 bars canonical content hash：

| 本地证据 | SHA-256 |
|---|---|
| [HUMAN_GO.md][go] | `531646230b1864533b7c61764a034b056c090a6f49378974971af7de7f8130bd` |
| [HOST_D_CLOSE_EVIDENCE.md][host-close] | `0ebecd0f197f32222223ceb04f40fb6d473aec7cd0e7390e87becf377184ba2f` |
| [g1_g2_numbers.json][close-numbers] | `4329c84387d5c20d34980d4faf17e3d21722ab84427bc877be93641d41e927c6` |
| [HOST_D_EVIDENCE.md][host-prior] | `7e8758482d0d96be5c2429d2ac6f5ad034d12c6cfc0610eada50f1c1a70ff9ff` |
| [coverage_numbers.json][prior-numbers] | `ad193cfa163c75a9881e8350ae5a3712ce7e50a0829f1ed864187c1ff15e0147` |

## 3. G1 CLOSED：观测日历相等，尾日合法截断

来源：[host close 的 G1 calendars / intents / Disposition][host-close]；[数字转储 `g1`][close-numbers]。

| 日历 | 天数 | 首日 | 末日 |
|---|---:|---|---|
| portfolio manifest `metadata.calendar` | 243 | 2025-01-02 | 2025-12-31 |
| bars pin `metadata.calendar` | 243 | 2025-01-02 | 2025-12-31 |
| pack `metadata.calendar` / freeze | 243 | 2025-01-02 | 2025-12-31 |
| pack `execution_calendar` | 244 | 2025-01-02 | 2026-01-05 |

Host 直接比较 manifest 与 bars 的日历列表：`list_equality=true`，`only_manifest=[]`、`only_bars=[]`。执行日历相对观测日历仅多 `only_execution_vs_manifest=["2026-01-05"]`；不再仅凭 bars 自带日历推断需求分母。

1891 条 intents 中，去除 CSV 时间戳字段的外层引号后，`available_at`、`effective_at`、`expires_at` 日期为 `2026-01-05` 的数量各为 **10**；任一时钟命中也是 **10**，即同一组 intent_id。全部满足 `decision_at=2025-12-31T15:02:00+08:00`、`available_at=effective_at=2026-01-05T09:30:00+08:00`、`expires_at=2026-01-05T15:00:00+08:00`。宿主逐 intent 清单如下：

| intent_id | instrument | side / reason |
|---|---|---|
| `dcfa8186c85595dfaa2c1f9f4e6b7640099b2c9b158eed59aa400fd1421101da` | SH603007 | SELL / TOPK_DROPOUT_SELL |
| `ef3c3d89801ffdd502e2c72d52278bf50687bdd6f8cce14cbc1140cc6516da8c` | SH603843 | SELL / TOPK_DROPOUT_SELL |
| `c37610b1c9938ff63cd9275d8ec1b1c2c7c5f1b289da751e3b5cf9d0c6e33952` | SH688323 | SELL / TOPK_DROPOUT_SELL |
| `9295271b53b31ad95554ef8f66f5e8657db9c6e345356469943eedb85084aa2c` | SZ000659 | SELL / TOPK_DROPOUT_SELL |
| `9959cca2c34f34cf16851390afdadcb05a60b13ec9992615f66c69c8b44d8e63` | SZ301486 | SELL / TOPK_DROPOUT_SELL |
| `fdc5a64720ddf32796fe972f5e7f1cf98e0ebbd4e75b64aab91656e0d9538cd5` | SH600828 | BUY / TOPK_DROPOUT_BUY |
| `eece354f64e9f8f8f8d5bf19a6b8ec5f9a76d9f5ea32e82f600fde854dd5b0a1` | SZ001270 | BUY / TOPK_DROPOUT_BUY |
| `226843f788e2f716485f72c33e6977a47ead7e9b57bd779f56c7d73254bec443` | SZ001330 | BUY / TOPK_DROPOUT_BUY |
| `24e1c6e63230e9de04f231411806764c73c564f378e6f0b1596db447cbbcbaa0` | SZ002796 | BUY / TOPK_DROPOUT_BUY |
| `c083a081cc41b052e473701967dfb71fb2c226895124c37eeabc183814c284fa` | SZ301338 | BUY / TOPK_DROPOUT_BUY |

合法截断依据与处理核对：host 报告 `joint_return_replay._validate_bar_metadata` 要求 `bars.metadata.calendar == manifest.metadata.calendar`，session opportunities 仅在该共同日历内构建；[frozen explicit 合同][price] 要求覆盖声明日历内 session 分钟 × universe。Scores/观测窗及 manifest/bars 日历均止于 `2025-12-31`。上述 10 条为窗口末日决策产生的下一 session clocks，均在共同观测日历之外；其存在不扩张本次 bars 需求集。

因此该组 intents 按 **legal truncation** 处理：保留冻结记录与 clocks，排除其窗外下一 session 对本次 bars 需求的扩张；不删除 intents、不改时间戳、不补 bars。它们仍属于全部 1891 个 marks 键的覆盖范围。本次没有 replay，不推导新的订单终态或 fills。

| 范围 | expected bars | observed bars | missing bars |
|---|---|---|---|
| `2026-01-05`（不属于本次研究观测需求日） | **N/A** | **N/A** | **N/A** |

该尾日未被测为 missing=0；本次是证明其 **不在需求集**。**G1 CLOSED。**

## 4. G2 CLOSED：精确 primary pin 的完整 seal 相等

来源：[host close 的 G2 seal recompute][host-close]；[数字转储 `g2`][close-numbers]。Host 对 §2 的 8,730,501,508-byte primary pin 执行 `json.loads`，随后计算 `joint_return_replay.content_hash({k:v for k,v in bundle.items() if k != "content_sha256"})`；符合 [canonical JSON seal 合同][price]，不是文件 raw-byte hash，也不是只读取登记字段。

| 字段 | 宿主复核结果 |
|---|---|
| registered（文件字段） | `83e7deae9ea580aa1aad208cc1751ad84df8157179751e252a0d43c1e28d8cdd` |
| recomputed（完整 bundle 去除顶层 `content_sha256`） | `83e7deae9ea580aa1aad208cc1751ad84df8157179751e252a0d43c1e28d8cdd` |
| equal / `equal_to_target` | **true** |
| 总耗时 | 150.806 s（报告约 151 s，读取/解码/解析约 63 s，hash 约 88 s） |

Host 报告解析后顶层键为 `bars`、`content_sha256`、`corporate_actions`、`kind`、`metadata`、`schema_version`。登记与完整复算相等，宿主没有重写 seal；本机只对账报告和数字转储。**G2 CLOSED。**

## 5. 沿用零缺口覆盖，D 接收

来源：[此前 host 覆盖报告][host-prior] / [数字转储][prior-numbers]；[host close Verdict][host-close] 明确此前零缺口仍成立。G1 将该已测分母绑定到 manifest 的研究观测需求，G2 复核同一 primary pin 的 seal。

| 所需覆盖范围 | expected | observed / present | missing |
|---|---:|---:|---:|
| 共同观测日历内 58,563 个 session 分钟 × 614 证券 | 35,957,682 | 35,957,682 | **0** |
| 全部冻结 intent_id 的 reference_marks 键集合 | 1,891 | 1,891 | **0** |

Bars unknown instrument / outside session / duplicate key 均为 0；marks extra=0、`exact_key_set_match=true`。本机复核 `58,563 × 614 = 35,957,682`。Marks 字段检查仍仅为旧报告的前 50 条无异常，不升级为全部 1891 条字段验证或真实湖价/PIT 验真。Seal 相等证明内容绑定，不替代真实源验收。

**G1 CLOSED + G2 CLOSED + 所需 bars/marks missing 均为 0 → D ACCEPT。** 本次仅收口 #264 的两个 residue，不生成 E/F replay PASS，不覆盖历史 pack、outs、回执或 seals。

## 6. 交付与停点

仅新增本 note，在初次 REJECT note 与身份对账 §5 增加/更新状态指针。验证范围为证据数字与 hashes 对账、逐 intent 转录、算术、文档链接、变更 allowlist、UTF-8 无 BOM / NUL=0 及 `git diff --check`；不运行代码测试，不修改 `.py`，不导湖或造 bars/marks。

提交、PR 与验证结果写入 [D_CLOSE_RECEIPT.md][receipt]。本轮止于 PR open + receipt；**未经 Human「合」不合并，E/F 仍各需另行 GO**。`production_C=frozen`。

[prior-pr]: https://github.com/baiyibing/MyQuant-backtrader/pull/264
[reject]: note-jr-clock-d-coverage-reject-2026-09-29.md
[go]: /workspace/handoffs/d_jr_clock_close_20260929/HUMAN_GO.md
[host-close]: /workspace/handoffs/d_jr_clock_close_20260929/HOST_D_CLOSE_EVIDENCE.md
[close-numbers]: /workspace/handoffs/d_jr_clock_close_20260929/g1_g2_numbers.json
[host-prior]: /workspace/handoffs/d_jr_clock_coverage_20260929/HOST_D_EVIDENCE.md
[prior-numbers]: /workspace/handoffs/d_jr_clock_coverage_20260929/coverage_numbers.json
[price]: joint-return-frozen-explicit-price.md
[receipt]: /workspace/handoffs/d_jr_clock_close_20260929/D_CLOSE_RECEIPT.md
