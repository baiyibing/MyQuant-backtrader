# H1：考古 Backtrader 文档归档 + CONTRIBUTING

- 日期：2026-09-15
- 状态：待 Codex 实施 / Grok 核
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)

## 目标
降低开源脸噪音：把已标注为历史/考古的 Backtrader 文档挪进归档；用短 CONTRIBUTING 写清本仓是什么、不要做什么。

## 要搬（git mv）
从 `docs/backtest/` 根到 `docs/backtest/_archive/fossils/`：
- `backtrader-order-types.md`
- `延期买入误检查.md`
- `结合本系统讨论 Backtrader 订单的创建与执行流程.md`
- `订单生命周期详解.md`
- `资金管理实现逻辑（含回滚机制）.md`
- `部分成交处理逻辑分析.md`

保留不动：`engine-*.md`、`pool-csv-contract.md`、`README.md`、活报告、hotpath plan。

## 交付
1. `_archive/fossils/README.md` 说明这是观察退役框架考古，不是现用入口。
2. 更新 `docs/backtest/README.md`「文件（考古）」表链接。
3. 根目录 `CONTRIBUTING.md`（短）：研究脸 / 向量化入口 / F 湖只读 / 不要做清单（对齐 AGENTS + engine-positioning）/ PR 用 GitHub Actions / 本地 CLI 非 CloudAgent 可选一句。
4. `rg` 修断链。

## 不要
- 不删 Cerebro 代码
- 不改成交核 / 策略书
- 不扩 L2

## 完成定义
- 链接无 404；`CONTRIBUTING.md` 存在；Grok 复核无 🔴 语义/范围问题。
