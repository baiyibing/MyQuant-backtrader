# L2-S0 来源 / LICENSE 决定（Q4）

2026-09-29 · **research contract v0（L2-S0）/ docs-only** · 基线 `7bdc7f7`。

**Human Q4 冻结：按[新合同](note-l2-s0-minute-orders-contract-2026-09-29.md)自行实现，只参考机制分责。** 本片不写实现、不移植源码、不复制 LICENSE；没有任何 vendor 运行依赖。此决定不授权 L2-S1，也不表示任何 vendor 树已取得法律或分发许可清理。

依据：工作站 `/workspace/handoffs/l1_l2_research_engine_l2s0_20260929/HUMAN_FREEZE_Q2_Q4.md`；外部 PLAN §4.4、§7.1、§9 Q4。完整 PLAN 不搬入本仓。

## 只读参考与具体机制

以下均为 **OSkhQuant1.3 工作站本地路径**，不是本仓文件、依赖或可移植运行路径；本次只静态阅读，没有 import/build/install vendor。文件行号对照1.3 HEAD `f6096df9b2ec8f459abd2a4940b5cba6e9079bda`；upstream pins 沿用其 [vendor README](/workspace/OSkhQuant1.3/vendor/README.md:1) 的本地登记，不等同于本次上游认证。

| 只读证据（path:line） | 仅借机制形状 | 不带入本合同 |
|---|---|---|
| LEAN [`Security.cs:220`](/workspace/OSkhQuant1.3/vendor/lean/Common/Securities/Security.cs:220)，上游记录 `23b735d99a` | Security 持有 Fill/Fee/BuyingPower/Portfolio/Settlement model ports；分清候选、费提案、资源与经济状态 | .NET Engine/Universe/Alpha/线程、broker、美股规则或默认 |
| LEAN [`SecurityPortfolioManager.cs:767`](/workspace/OSkhQuant1.3/vendor/lean/Common/Securities/SecurityPortfolioManager.cs:767) | `ProcessFills` 将 fill 交对应 Security 的 PortfolioModel 处理；学习成交回报与账本处理的分责 | 不声称其锁/批处理已满足本合同的容量+预留原子性；不搬实现 |
| Nautilus [`matching_core.rs:531`](/workspace/OSkhQuant1.3/vendor/nautilus_trader/crates/execution/src/matching_core.rs:531)，上游记录 `2114cf6f76` | `OrderMatchingCore::iterate` 返回 `MatchAction`；动作核与外层 fill 数量/费用/现金副作用分开 | **bid-first ≠ 本合同 sell-before-buy key**；每侧 limits-before-stops、价层树/stop 及外层 OHLC 合成路径均不移植 |
| vn.py Alpha [`backtesting.py:638`](/workspace/OSkhQuant1.3/vendor/vnpy/vnpy/alpha/strategy/backtesting.py:638)，上游记录 `fa5206fe` | 仅用于核实不能照搬的反例 | **固定 10% band 不采纳**；不用其 H/L/open 路径替代 completed-bucket close |

已核本地 vendor 子树对象：LEAN `7ebdd06f5004aa1627a9831790e70c4fc1fab6fa`；Nautilus `7f9b3aaf4f550a3eba854875ff5eaeb05c6b6b99`；vn.py `abbfeda978b392dd7b78496c2c8ea2d8690f3ef7`。树或行号变化时须重新核对；这些 pin 是来源定位，不是复制授权。本文不含 vendor 代码摘录。

## LICENSE 门与实施边界

- 禁止 import `lean` / `nautilus_trader` / `vnpy` / `backtrader` runtime；不加 `PYTHONPATH`、不安装、不接入构建/测试。Cerebro / BackBroker 宿主继续禁止复活。
- 本 PR 无 source transplant，也无 LICENSE 文件复制；**不宣称 legal clearance**。vendor README 的许可证标签和本地可读性均不构成授权。
- 未来若改为源码/算法文本逐段移植，须另获 Human pin：具体树版本、文件与段落、目标文件、借思想或移植的性质，以及 LICENSE / copyright / notice / 修改标记 / 分发范围与责任。未裁不得复制，换语言近似转写也不能冒称完全自研。
- 未来实现片应从冻结合同与独立手算 expected 推导最小机制；源码来源须可追溯。若需超出此路线，另提切片，不借本 Q4 自动获准。

本次只完成来源选择与参考定位，未运行 vendor、未验证其本机 runtime、全 A 股或实盘适用性；不因此获得绿C、绿P 或 SSOT 绿R/绿S。
