# 回测交易规则站位原则 SSOT

- 日期：2026-10-06
- 状态：standing / Human locked
- 权威来源：Baiyibing 于 2026-10-06 16:06 / 16:08（Asia/Shanghai）口述原则；仅写入本 SSOT。

## 1. P1 交易规则跟行业惯例

交易规则问题遵循 **INDUSTRY PRACTICE（行业惯例）**。

## 2. P2 本仓是回测系统，不是交易系统

本仓是 **BACKTEST system（回测系统）**，不是 trading system（交易系统）。
这里的「行业惯例」是主流回测器对 A 股规则的建模方式（backtrader、qlib、
vn.py backtest、JoinQuant / RiceQuant 类平台），不是交易所撮合引擎，也不是
券商 OMS / 柜台要求。

## 已决定的推论

- 快路径成交采用 bar-scan fill-or-skip；研究热路径不虚构 resting / limit order book。
- 不把研究规则压缩成交易所级撮合或券商 OMS 细节。
- 任何改变结果的规则变更都须建立新的 opt-in baseline；旧 baseline 永不刷新或覆盖；实施前由用户确认变更清单。

## 相关 SSOT

- 引擎分工：[engine-positioning-ssot.md](../engine-positioning-ssot.md)。
- A 股成交核 as-built：[engine-ashare-correctness.md](../engine-ashare-correctness.md)。
- 分钟成交假设：[minute-fill-policy-ssot.md](../minute-fill-policy-ssot.md)。
- 当前实施索引：[RB-06 as-built SSOT index](../rb06-as-built-ssot-index-2026-10-06.md)。
