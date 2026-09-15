# H6：CI / numba 对齐

- 日期：2026-09-15
- 状态：已完成（Grok 核无有效 🔴）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)

## 目标

CI 安装的 `requirements.txt` 已含 `numba>=0.60`；parity 测试 `tests/test_scan_held_day_numba_parity.py` 在 numba 可用时应**必跑**（不再因缺包而 silent skip）。不把 numba 设为 `scan_held_day` / simulate 默认后端（Python 参考路径保持默认）。

## 现状

| 项 | 现状 |
|----|------|
| `requirements.txt` | `numba>=0.60` |
| `.github/workflows/python-tests.yml` | `pip install -r requirements.txt` 后跑 pytest；无显式 numba 存在性断言 |
| `test_scan_held_day_numba_parity.py` | `skipif(not _NUMBA_SCAN_AVAILABLE)` —— 缺 numba 时整文件 skip |
| `scan_held_day` | 默认 Python；`use_numba=True` 或 `CSV_SCAN_HELD_DAY_BACKEND=numba` 才走 JIT |

## 交付

1. 本 plan
2. Workflow：注释说明 requirements 含 numba / parity 依赖；`pip install` 后 `python -c 'import numba'` 失败即 loud fail
3. **不**改 simulate / `scan_held_day` 默认后端
4. backlog H6 ✓
5. Grok → `docs/architecture/reviews/2026-09-15/h6-ci-numba/grok.md`；修有效 🔴；不 push

## 明确不做

- 不强制 CI / 本地默认启用 numba 扫描
- 不改策略书、卖点、成交语义
- 不 push；无 Cursor CloudAgent

## 完成定义

- CI 步骤在缺 numba 时失败（而非 parity silent skip）
- Python 默认后端不变
- Grok 无有效 🔴
