# backtest/ 回测专题

本目录存放回测相关文档，包括 chip 因子、数据计划、Backtrader 概念分析等。

## 子目录

| 目录 | 说明 |
|------|------|
| [chip/](chip/) | Chip 因子与 cost-migration |
| [code-reviews/](code-reviews/) | Backtrader 代码审查报告（AI 专家分析） |
| [data/](data/) | 回测数据方案（含 unified-daily-bars-plan） |

## 文件

| 文件 | 说明 |
|------|------|
| [backtrader-order-types.md](backtrader-order-types.md) | Backtrader 订单类型、成交价与成交时间指南 |
| [部分成交处理逻辑分析.md](部分成交处理逻辑分析.md) | 部分成交处理逻辑分析 |
| [订单生命周期详解.md](订单生命周期详解.md) | Backtrader 订单生命周期 |
| [结合本系统讨论 Backtrader 订单的创建与执行流程.md](结合本系统讨论 Backtrader 订单的创建与执行流程.md) | 结合本系统的 Backtrader 订单流程 |
| [延期买入误检查.md](延期买入误检查.md) | 延期买入误检查分析 |
| [资金管理实现逻辑（含回滚机制）.md](资金管理实现逻辑（含回滚机制）.md) | 资金管理实现逻辑 |

## 重构规划

| 文件 | 说明 |
|------|------|
| [../engineering/plan-backtest-refactor-and-live-integration-2026-06-18.md](../engineering/plan-backtest-refactor-and-live-integration-2026-06-18.md) | 回测程序重构并与交易程序对接方案（P0–P4 分阶段） |
