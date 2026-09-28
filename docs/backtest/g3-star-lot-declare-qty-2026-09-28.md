# G3 · 科创板普通买入申报量 opt-in（2026-09-28）

Human sequential GO：本刀仅 G3。默认 **OFF**，不改变旧整百基线；**勿合，未经 Human「合」不得合并**。G4–G8 未启动，另刀另行 GO。

## 证据与 B1 引用精度

沿用[索引 §3 B1](industry-state-acceptance-index-2026-09-28.md#3-b1-修正说明g3-引用精度--索引内勘误)措辞：**「上交所 2026 修订规则（链接为发布通知页；科创板 200 股起申报的条文号未在本次抓取中直接核验，仓内 D23 X-10 独立记录同一规则）」**。

[上交所链接](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)是发布通知页，不是仓内已核验的 §6.7 条文。本刀引用仓内 [D23 X-10 / §4 跟进计划第 6 项](../reviews/2026-09-25-minute-engine-review/README.md)：**科创板 200 股起、1 股递增**。不声称本次重新核验外部附件，不补造全板块、订单类别或历史生效日规则表。[基线 G3](industry-gaps-bt-2026-09-28.md)只读保留，引用时一并看 B1。

基线审计中的「§6.7」措辞属于冻结基线、只读保留；B1 勘误指针为索引 §3，并非重新抓取上交所条文。

## 冻结：申报 vs fill vs 残量

| 层 | 含义 | G3 范围 |
| --- | --- | --- |
| 申报（declare / new order） | 引擎新提交买/卖订单的数量 | 仅 STAR 普通买入入口：按 D23 X-10 最少 200 股，之后 1 股递增。开关关闭仍 floor-100。 |
| fill（成交） | 已接受订单的部分/全部执行，或持仓退出 | volume-cap / 现金限制若缩小成交量，本身不是新申报量违规。本刀不改既有现金拒绝/异常规则，也不添加现金缩量机制。 |
| 残量（residual） | 部分成交后的余量或零股持仓 | 不得重新提交不足 200 股的 STAR 买入申报；已有持仓的卖出余量仍可作为持仓退出成交。不扩展全板块卖出规则表。 |

## API 与边界

- `SimState(star_lot_declare_check=True)`，或共享日线 / 分钟 `simulate(..., star_lot_declare_check=True)`；默认均为 `False`。本刀不新增 CLI 参数，HELP_LOCK 不变，独立 v7 入口不扩展。
- 在 `csv_ledger.execute_buy` 使用已有 `market_layer._digit_prefix` 提取代码数字，识别 688/689；不把同属 20% 涨跌幅的创业板当作 STAR。
- ON 且 STAR：额度路径先取 `int(per / px)` 整数股，不做 100 股补充资金兜底；不足 200 拒绝。`shares_override` 保留整数原值，201/250 可申报，199/100/零/负数 fail closed，不向上补量、不向下取整百。非整数和 bool 仍抛原有 `ValueError`。
- 校验在现金检查和 volume-cap **之前**；拒绝返回 `False`，按需增加 `stats["skip_star_buy_declare_qty"]`，开启 audit 时记录同名拒绝；不写成交，不动现金、持仓、额度、volume budget。
- 每次 `execute_buy` 均视为新的买入申报，包括追买、加仓和 `merge_lot` 重试；本刀不建立跨调用挂单/续单模型。合法 201 股申报可被现有 cap 限成 100 股成交，剩余 101 股若另次调用买入则拒绝。δ5 的买入 fill 整百近似保留，开 cap 时合法 201/250 申报不保证全量成交。
- `_sell` 完全不改：例如 T+1 已持有 101 股可全部退出，这不是新增 101 股买入申报。卖出仍受原有 T+1/锁定/容量等条件约束。
- OFF 或非 STAR：原 `_buy_size` 整百/100 股补充资金逻辑、`shares_override // 100 * 100`、费用、成交与统计输出不变；关闭时不新增统计键。

## 合成测试矩阵（无湖）

`tests/test_g3_star_lot_declare_qty.py` 使用合成 `SimState` / frames 和 `tmp_path`，不读湖、不跑 4090。

| 反例 | 预期 |
| --- | --- |
| 688 / 689，额度和 override 0/1/100/199，ON | 拒绝且 audit/counter 可观测，资金与持仓不变 |
| 恰 200，ON | 允许 |
| 201 / 250，ON，无 cap | 原数成交，证明不是仅把 100 常数改成 200 |
| 201 申报、cap 100，随后重报余量 101 | 首次允许部分成交，重报拒绝；含 merge_lot |
| 持仓零股 1/101/199/201 卖出 | 可退出，不套买入申报规则 |
| 非 STAR，ON | 继续旧整百行为 |
| OFF（省略参数或显式 False） | STAR 仍可买 100；加载固定 base `3f1586f77e94a31ba0c4b86d5c03ff13f332d382` ledger 比较序列化账本字节 |
| 共享日线/分钟 API，ON/OFF | 开关传入实际买入路径 |

相关回归覆盖现有 volume-cap、exdiv economics、S8 ledger 与固定热路径 import fence。G2 缓存身份、#135 P1/P4、R3/R4、δ1/δ2/δ5/δ6 deferred 均不重开；不改变 TopK、hl/fen、X-* 默认，不复活 Cerebro / PortAna。
