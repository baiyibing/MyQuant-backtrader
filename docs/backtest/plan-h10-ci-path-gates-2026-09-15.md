# H10：CI path-SSOT / contract gates（主题 E 软切片）

- 日期：2026-09-15
- 状态：已完成（Grok 核无有效 🔴）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)（软扩展；H1–H9 已收口）
- 主题：**E**（path-SSOT / contract gates 进 CI；**无 F 湖** / repo-only）

## 目标

扩大 GitHub Actions 在 **无 `F:\stock_data`** 时仍可跑的 path-SSOT / 契约门禁；清点 `scripts/gates/*.py` 哪些依赖湖、哪些纯仓库静态扫描。不改 simulate / 卖点。

## 现状（基线 `ec0d146`）

`.github/workflows/python-tests.yml` **Contract gates**（`pip` 前）已跑：

- `scripts/gates/verify_oskh_data_contract.py`
- `scripts/gates/verify_data_path_ssot.py`

`OSKH_DATA_ROOT=${{ github.workspace }}`；不挂 F 湖。

## 门禁清单（data-free vs 需湖）

| Gate | 类型 | 依赖 | CI？ |
|------|------|------|-----|
| `verify_oskh_data_contract.py` | data-free（AST / 包边界） | 仅仓库源码 | ✓ 已有 |
| `verify_data_path_ssot.py` | data-free（路径字面量扫描） | 仅仓库源码 | ✓ 已有；H10 扩扫 `common/` |
| `verify_no_hardcoded_machine_paths.py` | data-free（本机路径硬编码） | 仅仓库源码 | ✓ **H10 新增** |
| `verify_tr_bridge_import_ssot.py` | data-free（TR bridge import AST） | 仅仓库源码 | ✓ **H12 接线**（脚本 H11） |
| `verify_l2_manifest.py` | 需 L2 parquet / manifest | 无湖时 SKIP 退出 0；有湖才校验 | ✗ 不加（CI 无湖恒 SKIP，无增益） |
| `verify_mvp_min.py` | 需湖 | parquet / `StockDataReader` | ✗ |
| `verify_minute_chip.py` | 需湖 | 同上 | ✗ |
| `verify_adj_minute_chip.py` | 需湖 | 同上 | ✗ |
| `verify_chip_factor_consistency.py` | 需湖 | 同上 | ✗ |
| `verify_chip_pool_enhancement.py` | 需湖 | 同上 | ✗ |
| `verify_float_shares_time_dimension_baseline.py` | 需湖 | float_shares parquet | ✗ |
| `verify_turnover_resistance_alignment.py` | 需湖；Python canonical vs research ops（非 Rust Store SSOT 验收） | parquet / reader；CSV + 摘要；退出码 0=非空样本两项全通过、1=输入/零有效样本、2=任一项不对齐 | ✗ |
| `verify_single_stock_turnover_resist.py` | 需湖 | duckdb + parquet | ✗ |

**规则：** 只把 **data-free**（无湖不失败）的 gate 加进 CI；禁止加入缺 `F:\stock_data` 就红的脚本。

## 交付

1. 本 plan（含上表清单）
2. 扩 `verify_data_path_ssot.py`：`_SCAN_DIRS` 含 `common`；`data_root.py` / `qmt_utils_adv.py` 入 allowlist
3. 新增 `scripts/gates/verify_no_hardcoded_machine_paths.py`（本叉包集合；docstring/`#` 忽略；`_script_bootstrap` allowlist）；修 `backtest/tools/read_app_data.py` `__main__` 示例硬编码
4. Workflow Contract gates 增加上述新 gate；注释标明 CI 跑哪些 / 为何不加湖门禁
5. `docs/backtest/README.md` + `AGENTS.md` 短指针：CI 跑哪些 data-free gates
6. Backlog：H9 ✓ + H10；主题 **A–F 仍开放**；**run-manifest 仍延期**
7. Grok → `docs/architecture/reviews/2026-09-15/h10-ci-path-gates/grok.md`；修有效 🔴；不 push

## 明确不做

- 不改 simulate / 卖点 / 6/8 语义
- 不把需湖 chip / TR / L2 门禁塞进 CI
- 不接 MyQuant `run-manifest`；无 Cursor CloudAgent；不 push

## 完成定义

- 清单文档化；CI Contract gates 仅 data-free；本地三 gate 绿；Grok 无有效 🔴；无 push
