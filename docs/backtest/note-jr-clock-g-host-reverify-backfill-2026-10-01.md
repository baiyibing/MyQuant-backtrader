# JR-clock G 宿主复核文档回填（2026-10-01）

基线：BT `2685926f9016862f2fc9d9b59579314ce5024543`（#281）；分支 `docs/jr-clock-g-host-reverify-backfill-2026-10-01`。授权：[Human GO「开 JR-G」][go]。本刀只回填 `narrow_clock_full_20260924` 的 2026-09-29 D-close / E / F 宿主复核链；`production_C=frozen`。

## 1. 判定与证据层级

**D ACCEPT（G1 CLOSED / G2 CLOSED）+ E P-BASE PASS + F Mode B PASS；本次 re-verify 证据层级为「宿主证据已复核（4090 D-close/E/F）」。** 三份宿主报告及对应数字转储均已取得并逐项对账：[D-close][host-d] / [D 数字][numbers-d]、[E P-BASE][host-e] / [E 数字][numbers-e]、[F Mode B][host-f] / [F 数字][numbers-f]。

[Identity note §§1–4][identity] 的「文档完成；宿主证据本轮未复核」保留为此前 reconcile 轮次的证据限定，不改写为当时已核宿主。本次升级仅对应上述具名包的 D-close/E/F 复核链，不扩张为 B/C 全量输入链重新验真。宿主报告均由 `newtest_4090` / 4090bot 于 2026-09-29 提供；本机只审阅这些已取得材料，没有连接或派发 4090、扫描原始 bars、复算宿主 pin、运行 replay 或读取湖。

## 2. Pack 身份与宿主定位

以下路径均为来源材料记录的宿主定位，本机未访问原始工件。身份沿用 [D-close §2、§4][d-close] 与 [identity §2][identity]；合同只引用既有前缀，不补造新 hash，不以本次文档 tip 替换 pack 的历史 `code_shas`。

| 字段 | 已记录身份 / 路径 | 来源 |
|---|---|---|
| Pack | `narrow_clock_full_20260924` | [D-close][d-close]、[E][host-e]、[F][host-f] |
| Pack root | `D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_full_20260924` | [D-close §2][d-close]、[E Identity][host-e] |
| Portfolio / run_id | `joint-return-control-only-50-5-narrow-clock-614`；pack 下 `portfolio\joint-return-control-only-50-5-narrow-clock-614\manifest.json` / `intents.csv`，1891 intents | [D-close §2–§3][d-close]、[E][host-e]、[F][host-f] |
| 合同前缀 | `c6b85b9b…` | [Identity §2][identity]、[D-close §2][d-close] |
| Bars + marks pin | `D:\exports\joint_return_pbase_narrow_20260922\frozen_explicit_bars_clock_full_614_with_marks.json` | [D-close][host-d]、[E][host-e]、[F][host-f] |
| Bars seal | `83e7deae9ea580aa1aad208cc1751ad84df8157179751e252a0d43c1e28d8cdd`（`83e7deae…`） | [D G2 registered / recomputed][numbers-d]；[E][numbers-e] / [F][numbers-f] 登记相同 |
| D 宿主数字 | `D:\exports\d_jr_clock_close_20260929\g1_g2_numbers.json` | [HOST_D_CLOSE_EVIDENCE.md][host-d] |
| E 宿主 out | `D:\exports\e_jr_clock_pbase_20260929\replay_M-LAG_P-BASE\joint-return-control-only-50-5-narrow-clock-614` | [HOST_E_PBASE.md][host-e]；宿主回执 `D:\exports\e_jr_clock_pbase_20260929\RECEIPT_E_PBASE.md` |
| F 宿主 out | `D:\exports\f_jr_clock_modeb_20260929\replay_modeb\joint-return-control-only-50-5-narrow-clock-614` | [HOST_F_MODEB.md][host-f]；宿主回执 `D:\exports\f_jr_clock_modeb_20260929\RECEIPT_F_MODEB.md` |

## 3. D / E / F 复核链

| 阶段 | Tip / 证据 | 复核结果 |
|---|---|---|
| D-close | [宿主报告][host-d] / [数字转储][numbers-d] 的 requested tip 为 `f267e60`；[D-close note][d-close] 随 [PR #265][d-pr] 合入至 `6528ac9` | **D ACCEPT；G1 CLOSED / G2 CLOSED**。所需 bars missing=0、marks missing=0 的既有覆盖继续成立；本阶段不运行 replay，不产生 fills |
| E P-BASE × M-LAG | [HOST_E_PBASE.md][host-e] / [e_pbase_numbers.json][numbers-e]；BT `6528ac944c7036fad65743158d9ffc1ad75ceddb`（`6528ac9`，#265） | **PASS / `BT_RESEARCH_REPLAY_PASS`**；fills **3631**，orders_with_fills **47**；net_return **0.5908987132604587**（≈0.5909 / +59.1%） |
| F Mode B：P-BASE × M-REF / M-LAG | [HOST_F_MODEB.md][host-f] / [f_modeb_numbers.json][numbers-f]；BT `6528ac944c7036fad65743158d9ffc1ad75ceddb` | **PASS / `BT_RESEARCH_REPLAY_PASS`**；M-REF **21** / M-LAG **3631** fills；cash **1e8**，不是旧 cash=1e9 fork |

D 的宿主 requested tip 与 #265 合并 tip 分别记录，不将 `6528ac9` 倒填为 D 检查时的 requested tip。[D-close §3–§5][d-close] / [宿主报告][host-d] 已闭合：manifest/bars 观测日历同为 243 天（2025-01-02 → 2025-12-31）；同一组 10 条尾日 intents 的下一 session `2026-01-05` 仅在 execution_calendar 内，按合法截断处理，该日 bars expected/observed/missing 均为 **N/A**，不虚构尾日 missing=0；G2 完整复算 seal 与登记值相等。共同观测日历内 bars expected=observed=35,957,682、marks expected=present=1,891，missing 均为 0，沿用 D-close 已接收证据。D-close 的 marks 字段/真实源核验范围不因本次回填而扩张。

E/F 数字对账：F M-LAG 的 fills、orders_with_fills、net_return、turnover、max_drawdown 与 E 相同；其中 turnover=`1.294644391717594`、max_drawdown=`0.2960604395329206`。F M-REF 的 orders_with_fills 为 **21**、net_return=`0.2207932854358422`。以上均直接来自 [E 数字][numbers-e] / [F 数字][numbers-f]，没有新增回放或以归档近似值替代本轮 PASS。

D-close 本身不授权 E/F；[E 报告][host-e] 记录独立 Human「开 4090 E」，[F 报告][host-f] 记录独立 Human「开 4090 F」，F 本身不授权 G。此次 G 文档范围由 [2026-10-01 Human「开 JR-G」][go] 单独授权。

## 4. 非主张与停点

- 历史 B–G 收官及 `NOT_READY_FOR_MODE_B` 解除已在 [原交接终版][archive] 完成；本次 **不重复解除**，不重写历史，不将归档包降回未完成。
- 仅登记上述宿主 re-verify PASS，**不新增 Mode B 授权**，不派发下一轮 replay。此包下一 operational **无强制宿主门**，无需回到 B/C 重生成。
- 不重生成 pack，不读取、改写或导出湖，不覆盖 pack、outs、旧回执或 seals；不修改 `.py`、MatchCore / Fees / Clock / SSOT；`production_C=frozen`。
- **不授权 δ5 / B-L2 / G5 policy**；δ5、B-L2 旁路须另 GO，G5 候选政策仍须 MQ/BT 联合 Human GO，不将本次结果转为 L2 NAV 比较授权。
- 本刀文档回填 **已合 [#282](https://github.com/baiyibing/MyQuant-backtrader/pull/282)**（MERGED `2026-10-01T01:06:14Z` ≈ 09:06 CST；mergeCommit `eccc750`；提交 `4bb2b66`）；G 正文在 tip `d9238c79`（blob `e072de6e…` 与 #282 同字节）。原「OPEN + 回执、待合」停点已闭合。

## 5. 文档范围与验证

新增本 note；仅更新 [identity §5][identity] 的 D/E/F 完成记录、G 行和相关停点文字，§§1–4 及该节外历史保持原样。[研究入口 §5.1/§5.6][entry] 与 [AGENTS JR 指针][agents] 已记录 3631 / 21 及归档完成态，无需追加指针。

验证限于三份宿主报告及数字转储对账、来源链接、allowlist、identity §5 外字节不变、UTF-8 无 BOM / NUL=0 与 `git diff --check`；不运行代码测试、4090 或湖任务。提交、PR、作者/提交者及最终检查结果写入 [G_BACKFILL_RECEIPT.md][receipt]。

[go]: /workspace/handoffs/g_jr_clock_backfill_20261001/HUMAN_GO.md
[identity]: note-jr-clock-pack-identity-reconcile-2026-09-29.md
[d-close]: note-jr-clock-d-coverage-close-2026-09-29.md
[d-pr]: https://github.com/baiyibing/MyQuant-backtrader/pull/265
[host-d]: /workspace/handoffs/d_jr_clock_close_20260929/HOST_D_CLOSE_EVIDENCE.md
[numbers-d]: /workspace/handoffs/d_jr_clock_close_20260929/g1_g2_numbers.json
[host-e]: /workspace/handoffs/e_jr_clock_pbase_20260929/HOST_E_PBASE.md
[numbers-e]: /workspace/handoffs/e_jr_clock_pbase_20260929/e_pbase_numbers.json
[host-f]: /workspace/handoffs/f_jr_clock_modeb_20260929/HOST_F_MODEB.md
[numbers-f]: /workspace/handoffs/f_jr_clock_modeb_20260929/f_modeb_numbers.json
[archive]: handoff-joint-return-clock-regen-2026-09-24.md
[entry]: research-backtest-entry.md
[agents]: ../../AGENTS.md
[receipt]: /workspace/handoffs/g_jr_clock_backfill_20261001/G_BACKFILL_RECEIPT.md
