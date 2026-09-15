# MyQuant-backtrader hygiene backlog（头脑风暴续）

- 日期：2026-09-15
- 状态：**软扩展 + D1/D2 chip 收口**（H1–H15 ✓；CYQ/TR 边界已写清；D1 profile + D2 numba minute 已交付；主题 **A–F** 重活仍开放；run-manifest hard 仍延期；不扩 L2；不删 Cerebro）
- 前置：PR #34（hotpath / presets 快照 / simulate 骨架 / plan 归档）
- 禁区（不动）：改 6/8 卖点、重开 `--asof`、PortAna 定胜负、本仓复刻 LEBS/真栈、缺行 fail-closed→跳过、Cerebro 物理删除、Cursor CloudAgent

## 队列（可改）

| ID | 项 | 完成定义 |
|----|----|----------|
| **H1** ✓ | 考古 Backtrader 文档归档 + 短 CONTRIBUTING（含不要做） | `docs/backtest/` 根下订单/资金等考古 md 进 `_archive/fossils/`；根 `CONTRIBUTING.md`；链接修好；Grok 核无 🔴 |
| **H2** ✓ | 日/分钟 CLI 共用 argparse | `add_csv_backtest_common_args`；daily/minute `main` 去重；pytest 绿 |
| **H3** ✓ | L2 范围篱笆 | AGENTS/README 写明 L2 只读实验、不扩交易核；`run_l2_*` 不接新策略书 |
| **H4** ✓ | research 入口防误 import Cerebro | `test_research_face_imports`：向量化五模块可导入且不拉 backtrader；chip 对照仍可 bt |
| **H5** ✓ | 日线 mark 按 code 缓存 + microbench | plan + `market_close_mark` / `append_equity` 缓存；`bench_daily_mark.py`；pytest；Grok 核无 🔴 |
| **H6** ✓ | CI 备注：numba 在 requirements，parity 必跑 | workflow 注释 + `import numba` 断言；Python 默认后端不变；Grok 核无 🔴 |
| **H7** ✓ | `stock_pool/` vs `exports/` 生命周期一句 SSOT | pool-csv-contract SSOT + README 指针；无 Python 行为变更；Grok 核无 🔴 |
| **H8** ✓ | 日线卖出环 searchsorted / 缓存索引（主题 A） | plan + `day_bar_and_prev_closes`；sell/chase/pool 共用；`bench_daily_sell_index.py`；golden 绿；Grok 核无 🔴 |
| **H9** ✓ | 名单质量 / pool 目录 tooling（主题 C 软切片） | plan + `report_pool_list_quality` / `pool_list_quality`；day/empty/histogram/overlap/`validate_pool_dir`；pytest；Grok 核无 🔴；**非** run-manifest |
| **H10** ✓ | CI path-SSOT / contract gates（主题 E 软切片） | plan + 门禁清单；扩 `verify_data_path_ssot`→`common/`；`verify_no_hardcoded_machine_paths`；workflow Contract gates；README/AGENTS 指针；Grok 核无 🔴；无湖门禁 |
| **H11** ✓ | Chip / TR slow-path inventory（主题 D 软切片） | plan + [chip/chip-slowpath-inventory-2026-09-15.md](chip/chip-slowpath-inventory-2026-09-15.md)；四桶表 leave/later offload/fossil；`verify_tr_bridge_import_ssot` + pytest；README chip 指针；Grok 核无 🔴；无算法/卖点变更；无 L2 扩张；无 Cerebro 删除 |
| **H12** ✓ | CI wire TR bridge import gate（主题 E 续） | `verify_tr_bridge_import_ssot.py` 进 workflow Contract gates（与 H10 data-free 同组）；plan + README/AGENTS 门禁列表；Grok 核无 🔴；无算法变更；无湖门禁；无 push |
| **H13** ✓ | CYQ / TR 产品边界（MyQuant numba feeder vs 本仓 Rust） | plan + inventory 边界节；README/chip/AGENTS 指针；CONTRIBUTING don’t-do；Grok 核无 🔴；**push + PR → master**；无算法 / 无 Rust rewrite；不迁 MyQuant feeder |
| **H14** ✓ | D1 profile minute/hybrid chip hotpath（本仓） | plan + `bench_minute_chip_hotpath.py` + results 注记；D2=numba minute优先；inventory/README/backlog/next-heavy；Grok 核无 🔴；**push + PR → master**；无算法语义变更；无湖；非 MyQuant feeder |
| **H15** ✓ | D2 numba/向量化 `minute_chip_distribution`（本仓） | plan + optional numba gate（`use_numba` / `MINUTE_CHIP_BACKEND`）；parity tests；bench python vs numba；inventory/README/backlog/next-heavy；Grok 核无 🔴；**push + PR → master**；Python 默认；hybrid/curpdf/cumpdf leave；非 Rust / 非 MyQuant feeder |

已合不重复：csv_common、csv_simulate_loop、presets 快照、plan `_archive/plans/`、numba trail 可选。

**队列收口（2026-09-15）**：H1–H7 全部交付并经 Grok 核。

**软扩展（2026-09-15）**：在 H1–H7 收口之上续 **H8**（主题 A）、**H9**（主题 C 软：list-quality）、**H10**（主题 E 软：CI path-SSOT / contract gates，无 F 湖）、**H11**（主题 D 软：chip/TR slow-path inventory，非 full Rust rewrite）、**H12**（主题 E 续：TR bridge import gate 进 CI）、**H13**（主题 D 边界：MyQuant numba CYQ feeder vs 本仓 Rust TR；文档 only）。头脑风暴主题 **A–F 仍开放**（未逐项排入 Hx 的项不视为关闭）。**不扩 L2**；**不物理删除 Cerebro**。**MyQuant run-manifest 本仓暂不接**（硬集成仍延期；见 progress-sync）。

**软 A–F 卫生切片（H1–H13）+ 重活 D1/D2（H14/H15）**：软卫生已覆盖；D1 profile + D2 numba minute 已交付（见 [plan-h14-d1-minute-chip-profile-2026-09-15.md](plan-h14-d1-minute-chip-profile-2026-09-15.md) · [plan-h15-d2-minute-chip-numba-2026-09-15.md](plan-h15-d2-minute-chip-numba-2026-09-15.md)）。

**Next heavy（刷新 · 2026-09-15；详见 [plan-brainstorm-next-heavy-2026-09-15.md](plan-brainstorm-next-heavy-2026-09-15.md)）：**
1. **C soft+**：加深 list-quality（非 run-manifest hard）
2. **run-manifest hard**：仍延期（本仓暂不接）
3. Inventory §D 其它 later offload（hybrid/curpdf 等仍 leave）
