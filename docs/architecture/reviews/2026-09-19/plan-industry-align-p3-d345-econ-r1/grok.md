# grok 评审：P3 δ3–δ6 docs pack v0.1（实现 / 协议 / Linux-VM CLI）

> 注：原席位输出文件曾出现中段 UTF-8 损坏；本文件由 host 按可恢复正文与总裁决规范化重写，**裁决与 R1/R2/Y\* 实质不变**。原损坏字节已丢弃。

对照 `IMPLEMENTATION_BASE=1049b904bdd818dbb79f51f1830a008c8f83b141` 与 PR HEAD `1e9994e88a67d0f5f651953fa7ad0e57b59a3677`。base→HEAD 仅五份 Markdown；§9 22 文件相对 base 零 diff。侧重 as-built 能否当 pin 规格、契约用词是否越界、§8 能否在干净 Linux 树上 headless 跑通。未跑 pytest/gates/模拟/湖。已读对抗三路；R1/R2 与 PE-01/DS-02、PE-02/DS-01 交叉一致。

## 🔴 必须修

### R1｜δ4 书侧「未知板块 → skip_unknown_board」未限定 named-band

`plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md:38`（minute `:39`、DoD `:107`）把未知板块无条件写成早拒。这只在默认 named-band 成立。`csv_common.py:80-82` 在 `qlib_limit_pct is not None` 时走固定 band；topk 书已接线（`csv_strategy_books.py:713`、`:788`）。δ3 `:32` 已记录例外。

**最小回填**：§2.2 表头改为「默认 named-band、非 ST、且算得 `limits is None`」；加固定 band 对照行；B2/B5 pins 显式 `qlib_limit_pct is None`。

### R2｜δ6 把「输入 close」写成普遍 `raw close`

`plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md:28`。`csv_ledger.py:173-178` 只读传入 close。3000→2500 残留仅在 none/raw 夹具成立。

**最小回填**：改为「消费传入 close；仅默认 none/raw 路径才是 raw mark」。

## 🟡 应修

1. **Y1** §8.2 解释器链含 `VANNA311_PYTHON` 却 `assert == (3,12)` — Linux 链只留 MERGE/312，或收窄文案。
2. **Y2** 「不允许 CLI」与整文件 pytest 调 `main()` 字面冲突 — 禁宿主/湖；允许 tmp_path `main()` 单元。
3. **Y3** δ4 held-None 自然可达性未锁；δ3 未来 C 须重做可达性矩阵。
4. **Y4** δ5 部分成交缺「零成交后继续扫描」合同；`.3=A` 收口前补状态表或暂 `.3=B`。
5. **Y5** δ6 B6 无 bar 缺估值真值；B2 行号范围略宽。
6. **Y6** δ3 真实 `load_limit_context → names=` 接线应升为 Slice B 必需 pin。
7. **Y7** δ4 chase None 早拒发生在 `pending_chase.pop` 之后 — 表内写明 pending 已消耗、无成交。

## ✅ 做对的地方

生产冻结与白名单可落地；§8 无幽灵路径；δ6 C 锁死、无 Mode B creep；P1/P2/P4 未重开；人裁表可用；关键 as-built（除 R1/R2）抽查属实。

## 总裁决

1. **GO-WITH-NITS** — docs-only 包可进人裁；R1/R2 必须勘误回填 as-built 表。不构成生产 GO，不授权编码。
2. **建议人裁表**（维持工作假设，非代裁）：δ3=A；δ4=A（先收窄 named-band）；δ5=B（仅设计）；δ6=A（账本可选 B；生产须显式 `.1=C`）；P1/P2/P4 继续 deferred。
3. **是否可进人裁：yes**（人裁 GO 前仍禁止编码；建议人裁包附带 R1/R2 勘误）
