# Vendor bar alignment：docs-only PLAN（2026-10-01）

Human GO via bt executor；基线 `f9ba3158b8e2bd82ac6eb5ab54668add224873c2`（`f9ba315`，#291）。分支 `docs/vendor-bar-alignment-ssot`。

本刀交付 [Wind / THS / QMT bar alignment SSOT](../ssot/vendor-bar-alignment-ssot.md)、本 PLAN 与 README 单行入口；提交、推送并开面向 master 的 draft PR，交接至 `/workspace/handoffs/vendor_bar_alignment_ssot_20261001/`。

只读证据入口：[host RECEIPT](/workspace/handoffs/topk_s1_cap_cli_host_20261001/RECEIPT.md)，并核对同目录 market_PIN.json、GAPS.json 与 prepare/PIN.json。START+sparse 是单次研究 overlay 的 Human 接受，三个 vendor 标的未写湖；THS 1m 未证实，不推断其标签。

验证：docs-only diff、相对链接、UTF-8 无 BOM / NUL=0、git diff --check；PR CI 状态与实际 tip/PR URL 记入交接 RUN.md。不重跑湖、不新增代码测试。

后续 vendor→lake alignment adapter CLI **不在范围内**，须未来独立 Human GO。无 MatchCore / Fees / engine 改动，无 δ5 certified / R4，无湖写入。

**禁止自动合；勿合，等待 Human「合」。** draft PR 与交接完成即停。
