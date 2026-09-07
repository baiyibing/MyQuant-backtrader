## 摘要

<!-- 简述本 PR 做什么、为何需要 -->

## 自检

- [ ] **动 P1 基建核见 engineering-notes §P1**（若本 PR 触及 `common/__init__.py`、`common/_pep562_package_exports.py`、[`common/infra/`](../common/infra/) 下 §P1 所列模块，或 [`docs/engineering/engineering-notes.md`](../docs/engineering/engineering-notes.md) §P1）：已对照 §4，并在描述中说明对 `from common import …` / `from common.infra…` 等调用方的影响（必要时附 grep 摘要）。
- [ ] **P2 持久化写路径**（若本 PR 新增或改动 **DB 写入、建表、迁移、旁路 SQL**）：默认经 [`oskh_db/db_gateway.py`](../oskh_db/db_gateway.py) `execute_sql` / 包内既有 Gateway 能力；**禁止**在业务包（尤其 [`trade_decision/`](../trade_decision/)）引入直连 `sqlite3` / `aiosqlite`（CI：`scripts/verify_trade_decision_no_direct_sqlite.py`）。叙事与 trace 约定见 [`docs/engineering/engineering-notes.md`](../docs/engineering/engineering-notes.md) **Part D**；合并前在描述中写明写路径或白名单依据。
