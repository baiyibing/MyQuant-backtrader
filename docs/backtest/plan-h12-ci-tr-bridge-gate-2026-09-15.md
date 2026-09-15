# H12：CI wire TR bridge import gate（主题 E 续）

- 日期：2026-09-15
- 状态：已完成（Grok 核无有效 🔴）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)（软扩展；H1–H11 已收口）
- 主题：**E**（path-SSOT / contract gates 进 CI；**无 F 湖** / repo-only）
- 前置：H11 已交付 data-free `scripts/gates/verify_tr_bridge_import_ssot.py` + pytest；本切片仅 **接线进 CI**

## 目标

把 H11 的 TR bridge import SSOT 门禁挂进 `.github/workflows/python-tests.yml` **Contract gates**（与 H10 其它 data-free gates 同组、`pip` 前），保证无 `F:\stock_data` 的 PR/CI 也能拦住 bridge 漂移。不改算法 / 卖点。

## 交付

1. 本 plan
2. Workflow Contract gates 增加一行：`python scripts/gates/verify_tr_bridge_import_ssot.py`；注释指向本 plan + H10 清单
3. 更新枚举 CI gates 的文档：`docs/backtest/README.md`、`AGENTS.md`；backlog **H12 ✓**
4. Backlog 短注：软 A–F 卫生切片 H1–H12 大体覆盖；更重 follow-up（run-manifest 硬集成、chip inventory「later」offload）仍开放
5. Grok → `docs/architecture/reviews/2026-09-15/h12-ci-tr-bridge-gate/grok.md`；修有效 🔴；**不 push**

## 明确不做

- 不改 simulate / 卖点 / 6/8 / chip / TR 算法
- 不把需湖 chip / TR / L2 门禁塞进 CI
- 不接 MyQuant `run-manifest`；无 Cursor CloudAgent；不 push

## 完成定义

- Contract gates 含四条 data-free 脚本（含 TR bridge）；本地 gate 绿；文档列表同步；Grok 无有效 🔴；无 push
