# MyQuant-backtrader 头脑风暴总览（2026-09-15）

- **状态**：安全切片 **H1–H16 已合入 `master`**（PR #34–#50）；本文件为 A–F 主题对照与索引，不是新实现承诺。
- **工作方式**：本机 Codex 改 / Grok 核；GitHub Actions 绿则合；**不用** Cursor CloudAgent。
- **三仓坐标**：本仓 = 向量化研究脸；[MyQuant](https://github.com/baiyibing/MyQuant) = 训练 / 名单导出 / **numba 全市场赢筹 feeder**；[OSkhQuant1.3](https://github.com/baiyibing/OSkhQuant1.3) = LEBS / 真栈。引擎分工见 [engine-positioning-ssot.md](engine-positioning-ssot.md)。

详细 backlog：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)。  
仍开放重活队列：[plan-brainstorm-next-heavy-2026-09-15.md](plan-brainstorm-next-heavy-2026-09-15.md)。

---

## 主题 A–F（对照）

| 主题 | 一句话 | 已落地（安全切片） | 仍开放 / 延期 |
|------|--------|-------------------|---------------|
| **A 性能** | 向量化热路径加速；**不**重写 Cerebro | #34 hotpath/numba `scan_held_day`；H5 日线 mark 缓存；H8 sell `searchsorted` | 分钟卖环更深 unify；日/分钟 **sell 大合并**（有意分家，勿 big-bang） |
| **B 策略书/入口** | 共用编排，卖点书分离 | #34 `csv_simulate_loop`；H2 共用 argparse | 两套 sell 引擎仍分家（日线规则 vs `scan_held_day`） |
| **C 名单管道** | 本仓日名单契约 / 质量；名单源可来自 MyQuant | H7 `stock_pool` vs `exports`；H9+H16 list-quality CLI | **`run-manifest` 硬接仍延期**（跨仓可选，非本仓必做） |
| **D 筹码/TR** | 算力与产品边界 | H11 inventory；H13 **MyQuant numba CYQ feeder** vs **本仓 Rust TR**；H14 profile；H15 `minute_chip_distribution` optional numba ~58× | inventory「later」：hybrid/`calc_curpdf` 等仍 leave；**禁止本仓复刻 MyQuant CYQ** |
| **E 数据契约/CI** | path-SSOT、无湖 gates | H6 numba assert；H10 path gates；H12 TR bridge gate | 需 F 湖的 chip/TR gates **不进** CI |
| **F 工程脸** | 文档/化石/贡献指南 | H1 fossils+CONTRIBUTING；plan 归档；H4 research 不 import backtrader | Cerebro **观察退役**、不物理删除 |

**G 禁区（全程）：** 改 6/8 卖点、重开 `--asof`、PortAna 定胜负、本仓复刻 LEBS/真栈、缺行 fail-closed→跳过、Cerebro 物理删除、CloudAgent、本仓复刻 MyQuant CYQ feeder。

---

## 已合 PR 索引（#34–#50）

| PR | 内容 |
|----|------|
| [#34](https://github.com/baiyibing/MyQuant-backtrader/pull/34) | hotpath plan、presets 跨仓快照、`csv_common` / `csv_simulate_loop`、plan 归档 |
| [#35](https://github.com/baiyibing/MyQuant-backtrader/pull/35)–[#41](https://github.com/baiyibing/MyQuant-backtrader/pull/41) | H1–H7 软卫生栈 |
| [#42](https://github.com/baiyibing/MyQuant-backtrader/pull/42)–[#46](https://github.com/baiyibing/MyQuant-backtrader/pull/46) | H8–H12（sell index、list-quality、CI gates、chip inventory、TR bridge CI） |
| [#47](https://github.com/baiyibing/MyQuant-backtrader/pull/47) | H13 CYQ vs Rust TR 边界 |
| [#48](https://github.com/baiyibing/MyQuant-backtrader/pull/48) | H14/D1 分钟筹码 profile |
| [#49](https://github.com/baiyibing/MyQuant-backtrader/pull/49) | H15/D2 minute chip optional numba |
| [#50](https://github.com/baiyibing/MyQuant-backtrader/pull/50) | H16/C soft+ list-quality 加深 |

`master` tip（刷新时）：见仓库默认分支；本文落盘时约 `62d3449`（#50 merge）。

---

## 关键边界（易混）

1. **赢筹 / CYQ（日频全市场）** → MyQuant `my_scripts/build_winner_ratio.py`（**numba**，非 Rust）。对拍见 sibling MyQuant `docs/winner-ratio-cyq-parity-2026-09-14.md`。  
2. **换手阻力 / canonical TR** → 本仓 `turnover-resist`（Rust）→ bridge → Store → 策略 10 / `tr_filter`。  
3. **分钟筹码分布** → 本仓 `oskh_factors.chip`；H15 起可选 numba（默认仍 Python）。  
4. **名单 CSV** → 本仓契约 [pool-csv-contract.md](pool-csv-contract.md)；质量工具 `scripts/research/report_pool_list_quality.py`。

盘点 SSOT：[chip/chip-slowpath-inventory-2026-09-15.md](chip/chip-slowpath-inventory-2026-09-15.md)。

---

## 下一步（若继续）

队列头：**run-manifest 硬接**（需产品点头，另开片）。  
其它可选项：A 分钟卖环微优化；E 湖门禁仍保持 host-only；inventory hybrid/curpdf later。  
默认：**先停在已合 master**，需要时再点名开片。
