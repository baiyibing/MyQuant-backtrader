# B8 lot rounding：零差异重构实施说明（2026-10-06）

**人裁：** 2026-10-06 07:31 CST，H-B8-01..12 全部采用推荐 A。只做共享取整 helper 的零差异重构；规则统一全部不做。方案与评审记录在 Bot VM `/workspace/b8-plan/`（plan-only，五席两轮，R2 5/5 approve_plan）。

## 交付

| PR | 内容 |
|---|---|
| #405 | 新增 `backtest/research/lot_rounding.py`；`csv_ledger._buy_size` / `execute_buy` override 整百 / STAR 200 常量 / 量帽后补额，`csv_simulate_loop.run_pool_buys_day` order_budget 迁入 helper；`tests/test_b8_lot_rounding.py` |
| #406 | `minute_cash_order.scale_out_exits`、`tail_window_buy`（容量、Decimal 父单、分片）、`strategy9_1_rules.unit_shares`、`strategy9_2_engine.plan_exit`、`strategy12_rules.scale_memory`、`strategy7_engine._buy`、`fullstrat_research_v7.simulate`、`unified_exit_modea._lot_shares` 迁入 helper |
| 本 PR | `tests/test_b8_lot_rounding_guard.py`（H-B8-10）与本说明 |

每个 helper 的 docstring 写明它复现的原表达式；浮点/Decimal 运算顺序逐处保留（截断除、float 整除、int 整除、`round(...,8)`、双整除各自独立，不互相合并）。`_buy_size` 符号与再导出保留。

## 未迁移（guard allowlist，按 文件 + 函数 + 表达式 + 理由）

- `ashare_volume_cap.VolumeCap.clamp`：冻结核心，`tests/test_minute_orders_cli_lake.py` 的 KNIFE_BASE 守卫要求该文件不变。
- `joint_return_replay`（含 `q % 100 == 0` LOT_ROUNDING 校验）、`minute_orders_backend/*`（L2 typed `lot_size`）：inventory-only 独立合同。
- `verify_chip_factor_consistency.main`：进度计数，非 sizing。
- `affordable_shares` 二分算法未改；v7 native ledger 语义（决定 A）、费用、T+1 不变。

## Guard（H-B8-10）

AST 扫描 `backtest/research/**`，helper 之外出现整百 floor / `% 100` 手数校验即失败；allowlist 条目失效也失败；锁定已迁移调用点必须调用对应 helper；扫描按文件而非书名，6.45–6.47 及以后的 6_* 自动覆盖；`lot_rounding.py` 只允许纯算术。

## 验收（对照 `.github/workflows/python-tests.yml` 的 pytest-and-gates）

本仓不存在 `docs/quality/contract-gates-runbook.md` 与两个 bundle 脚本，验收映射为 workflow 本身：四个 contract gates、`check_minute_classification.py`、pandas==3.0.6、ruff `bt_contract`、numba 可导入、`pytest -m "not production and not benchmark"`，以退出码判定。三层零差异：

1. `tests/fixtures/**` 与 `generate_off_byte_baseline.py` 相对 master 无 diff（含 #395、V6F v21、v22，未重录）。
2. 现行 owner baselines：`test_off_byte_baseline`（pandas 3.0.6，字节阶段未跳过）、`test_v7_app_optin_baseline` 等全量 pytest 通过。
3. 迁移前后原始输出：generator 全部 137 case × explicit_false 两种（274）用 `capture_case` 抓取，JSON 逐字节一致。

已知、未改：S8 price-add allowlist 不含 version8_2 / version8_6（按人裁保持）。`generate_off_byte_baseline.py --check` 在 master 上因 `capture_matrix` 的旧断言 `len(BOOK_NAMES) == 22` 失败（不在 CI 内，CI 用 pytest 路径），本票不改。
