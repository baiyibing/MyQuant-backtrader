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

`SCAN_ROOTS` 精确为 `backtest/research` 和 `strategies`；递归读取两树内所有 `.py`，仅排除 `backtest/research/lot_rounding.py`。真实文件覆盖来自 `repository_hits()`，不按注册书名过滤；每书名合成测试只验证 detector 不按名称过滤，不代表读取真实书文件。未来文件发现另有临时目录合成测试。

检测的 AST 形状（lot 为数值字面量 `100` / `100.0`、`lot_size` / 属性 `.lot_size`，或当前函数/类直接赋值且各次均为 literal 100 的局部别名）：

- 两侧任一侧为 lot 的乘法，另一侧沿 `/`、`//` 左操作数链或 `int` / `round` / `floor` / `trunc` / `Decimal`、`math.floor` / `math.trunc`、`.to_integral_value` / `.quantize` 包装追踪到除 lot（也包括分母 `price * lot`）。覆盖 `x // 100 * 100`、`100 * (x // 100)`、`floor(x / 100) * 100`、`Decimal(x / 100).to_integral_value(...) * 100`、除 lot 后 quantize 再乘回。
- 同一 AST 操作数的余数扣除 `x - x % lot`。
- `% lot == 0` / `% lot != 0`（含零在左侧）；`if` / `while` / 条件表达式 / `assert`、`bool(...)`、`not`、布尔组合中的余数真值检查。
- `divmod(x, lot)`。
- `.quantize(Decimal("1E2"))` 等 Decimal 字面量 exponent=2 的直接百位量化。`Decimal("100")` 的 exponent=0，不按百位量化处理。

单独 `x / 100`、`shares < 100`、价格分位 round / quantize、`floor(price * 100) / 100` 等有非 sizing 合成测试。此 guard 是 **best-effort AST pattern guard，不是证明**：不做类型/数据流分析，不展开任意别名、包装函数或跨语句运算；同形状的非 sizing 表达式仍可能命中，应逐条审计并给出诚实理由。allowlist 精确锁定 文件 + 函数 + canonical expression，条目失效也失败。已迁移调用点测试仅检查对应 helper import/call 和局部 rebinding，不证明参数、运算顺序或零差异。

Purity 测试的静态范围：helper 全 AST 限制 import 为 `decimal` / `typing` / `__future__`，call 为裸名 `int` / `float` / `str` / `max` / `round` / `Decimal`；禁止 `global` / `nonlocal` / `with`、`For`（含 async）/ `While` / `Try`（含 TryStar）/ `Lambda` / 所有 comprehension 及一切属性访问（Decimal 构造结果的方法也禁止）。模块顶层仅允许 docstring、常量赋值、函数定义和 import。允许 `If` 算术早返 guard（不分析其用途）；当前 helper 函数体无 `if`。这是语法约束，不是完整无副作用证明。

本次扩展重扫：10 个 hits，均为既有 allowlist；新增 allowlist 0，新增未迁移 sizing 0。

## 验收（对照 `.github/workflows/python-tests.yml` 的 pytest-and-gates）

本仓不存在 `docs/quality/contract-gates-runbook.md` 与两个 bundle 脚本，验收映射为 workflow 本身：四个 contract gates、`check_minute_classification.py`、pandas==3.0.6、ruff `bt_contract`、numba 可导入、`pytest -m "not production and not benchmark"`，以退出码判定。三层零差异：

1. `tests/fixtures/**` 与 `generate_off_byte_baseline.py` 相对 master 无 diff（含 #395、V6F v21、v22，未重录）。
2. 现行 owner baselines：`test_off_byte_baseline`（pandas 3.0.6，字节阶段未跳过）、`test_v7_app_optin_baseline` 等全量 pytest 通过。
3. 迁移前后原始输出：generator 全部 137 case × explicit_false 两种（274）用 `capture_case` 抓取，JSON 逐字节一致。

已知、未改：S8 price-add allowlist 不含 version8_2 / version8_6（按人裁保持）。`generate_off_byte_baseline.py --check` 在 master 上因 `capture_matrix` 的旧断言 `len(BOOK_NAMES) == 22` 失败（不在 CI 内，CI 用 pytest 路径），本票不改。
