# H4：research 入口防误 import Cerebro

- 日期：2026-09-15
- 状态：已完成（Grok 核无有效 🔴）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)

## 目标
向量化 research 主路径（日/分钟 CSV 回测面）导入时不强制、不顺带拉入 `backtrader` / Cerebro。chip 对照脚本仍可 import bt；Cerebro 模块保留化石闸门，不物理删除。

## 篱笆范围（vectorized face）
| 模块 | 角色 |
|------|------|
| `backtest.research.csv_daily_backtest` | 日线主入口 |
| `backtest.research.csv_minute_backtest` | 分钟主入口 |
| `backtest.research.csv_simulate_loop` | 共用 simulate 骨架 |
| `backtest.research.csv_common` | 日历 / name-asof 等共用 |
| `backtest.research.csv_strategy_books` | 策略书注册表 |

**允许仍 import bt：** `chip_backtest` / `ma_chip_edge_backtest` / `verify_cerebro_chip` 等对照化石。

## 交付
1. 本 plan。
2. 加强 `tests/test_research_face_imports.py`：上述五模块可导入，且子进程断言 `sys.modules` 无 `backtrader`；可选 AST 禁直接 `import backtrader`。
3. 优先 pytest；无必要不新加 `scripts/gates`。
4. `plan-hygiene-backlog` 标 H4 ✓。
5. pytest：`test_research_face_imports` + `test_csv_strategy_books`。
6. Grok 核 → `docs/architecture/reviews/2026-09-15/h4-research-cerebro-import/grok.md`；修有效 🔴；不 push。

## 不要
- 不删 Cerebro / ProfitStrategy / chip 对照模块
- 不改成交语义、卖点、策略书行为
- 不用 Cursor CloudAgent；不 push

## 完成定义
- 五模块无 bt 依赖可测；化石对照仍可存在；Grok 无有效 🔴。
