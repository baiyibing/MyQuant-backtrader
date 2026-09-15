# H9：名单质量 / pool 目录 tooling（主题 C 软切片）

- 日期：2026-09-15
- 状态：已完成（Grok 核无有效 🔴）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)（软扩展；H1–H8 已收口）
- 相关：[pool-csv-contract.md](pool-csv-contract.md)、[myquant-progress-sync-2026-09-13.md](myquant-progress-sync-2026-09-13.md)
- 主题：**C**（list-quality / pool tooling；**不是** MyQuant `run-manifest` 集成）

## 目标

给 `YYYYMMDD.csv` pool 目录加一个只读质量报告 CLI：天数、空日、代码数直方图、可选第二目录重叠、`validate_pool_dir` 错误。复用既有 `csv_pool` 校验 / 解析 helper；不写 F 湖、不接 run-manifest、不改成交语义。

## 安全目标（本切片采纳）

1. Plan 本文。
2. `scripts/research/report_pool_list_quality.py`：
   - `--pool-dir` 必填；可选 `--other-dir` 做日对齐重叠；
   - 输出：day count、empty days、code-count histogram、`validate_pool_dir` failures；
   - 可选重叠：共有日、仅 A / 仅 B、逐日交集大小与 Jaccard、均值摘要；
   - 用 `validate_pool_dir` / `parse_pool_csv`（及目录扫描约定）；无湖写入、无 `qlib`。
3. Pytest：`tests/test_report_pool_list_quality.py`（`tmp_path`）。
4. `pool-csv-contract.md`（或 README）短指针。
5. Backlog：H8 ✓（若未标）+ H9；注明主题 **A–F 仍开放**；**run-manifest 仍延期**（本仓暂不接 hard）。
6. Grok → `docs/architecture/reviews/2026-09-15/h9-list-quality/grok.md`；修有效 🔴；不 push。

## 明确不做

- 不改 simulate / 卖点 / 6/8 语义
- 不 `import qlib`；不写 F 湖；不接 `myquant.run-manifest/1`（单独开片）
- 不做全市场净值对照；不重开 `--asof`；无 Cursor CloudAgent

## 完成定义

- CLI 可对任意 pool-dir 打印质量摘要；双目录重叠可选
- pytest 绿；Grok 无有效 🔴；无 push
