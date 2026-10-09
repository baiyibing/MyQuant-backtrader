# 04 分红 schema 缺口与两处实证错误

结论：`dividend_history` 不能直接替换 Wind corp-actions 或构造 BT ExDivEvent。除了缺日期/身份/来源，**现金单位大10倍、转增字段读取错误**已用真实 HTTP 响应及原函数回放复现。

来源：a-stock-data `SKILL.md:3113`、旧 helper `:785`；BT `backtest/research/ashare_exdiv_economics.py:19`；本地 `data/corp_actions/bt_corp_actions_20261006/{README.md,corp_actions.csv}`。本轮只读现成 Wind/Kimi 数据文件，没有调用 Kimi；README 的历史产地写 4090 不表示此次访问该机器。

## 实证

- 贵州茅台 2026-06-26：东财 `PRETAX_BONUS_RMB=280.2423`，同记录 `IMPL_PLAN_PROFILE="10派280.2423元(含税)"`。原函数输出 `bonus_rmb=280.2423` 并宣称每股，实际每股应为 **28.02423** 元。另两条 2025-12-19 / 2025-06-26 的方案文本同样支持每10股口径。证据来自同一原始响应和方案文本，不是假称该票在本地 Wind 集内完成交叉验证。
- 平安银行 2016-06-16：`IT_RATIO=2`、方案 `10转2.00派1.53元`；真实响应无 TRANSFER_RATIO。原函数返回 transfer_ratio=0，丢失每股0.2的转增；现金1.53也应先除10。2015-04-13 和2014-06-12重复同问题。
- 东财“无送股”的 BONUS_RATIO 常为 JSON null。`row.get('BONUS_RATIO',0)` 不会把存在的 null 变0，原函数可能输出 None。
- 600519默认20条的响应 `result.pages=2`，旧helper不翻页；因此“history”默认不保证全历史。

HTTP URL、状态、时间与哈希在 `04-dividend-http.json` / `04-dividend-000001-http.json`，原响应 `raw/dividend-eastmoney*.json`。`dividend_replay.py` 将真实返回作为旧 helper 的结果注入，调用原 `dividend_history`，回放明细见 `04-dividend-replay.csv/.json`。没有执行任何供应商客户端或联网导入两个业务仓。

## 字段对照

| 维度 | a-stock-data dividend_history | Wind/Kimi本地产物 | BT ExDivEvent | 缺口/适配要求 |
| --- | --- | --- | --- | --- |
| 证券标识 | 未返回；只有输入 code | code（Wind 后缀） | lookup 外层 (symbol,ds) | 必须补 code、交易所及规范化 |
| 事件身份 | 缺失 | event_id | event_id（跨代码全局唯一） | 建立稳定去重/修订策略，不仅以日期去重 |
| 除权除息日 | date ← EX_DIVIDEND_DATE（截前10字符） | ex_date | ex_date，YYYYMMDD | 严格验证日期；排除未实施/缺日期方案 |
| 登记日 | 缺失；原响应有 EQUITY_RECORD_DATE | record_date | 模型未直接包含 | 保留以供资格审核；当前 BT 明确不处理登记日资格 |
| 派息日 | 缺失 | pay_date（178空） | pay_date 必填 | 不能自动假设等于除息日；补缺或拒绝事件 |
| 税前现金 | bonus_rmb 原样 PRETAX_BONUS_RMB，文档错称每股 | cash_div_per_share，元/股 | cash_div_per_share，有限非负 | 已复现：东财每10股，需要除10；不能直接映射 |
| 送股比例 | bonus_ratio ← BONUS_RATIO，每10股 | bonus_ratio，每股 | bonus_ratio，新增股/原股 | 东财除10；Wind已有每股口径不再除10 |
| 转增比例 | transfer_ratio ← TRANSFER_RATIO，缺键默认0 | transfer_ratio，每股 | 没有独立字段 | 已复现真实键为 IT_RATIO；当前会丢转增；确认单位后与送股合并 |
| 红股上市日 | 缺失 | bonus_list_date | list_date，可选、缺省退为ex_date | 有送转时需真实可售日；不能依赖缺省制造提前可售 |
| 实施状态 | plan ← ASSIGN_PROGRESS，仅返回未过滤 | CSV未保留；README称筛实施完毕 | 无状态字段 | 适配层过滤已实施；保留原始状态用于追溯 |
| 公告/可得时间 | 缺失；原响应有 NOTICE_DATE/PLAN_NOTICE_DATE | CSV未含（raw可能有） | 无字段 | 严格PIT接入另建 available_at，不能用ex_date充当可知日 |
| 来源版本 | 缺失 | source | 无字段 | 保留URL/抓取时间/哈希/原事件修订版本 |
| 分页/完整性 | 默认20条；旧helper仅第1页 | 本地产物部分覆盖 | 由caller提供lookup | 显式翻页及核对总数；不能把未覆盖当无分红 |
| 空/坏值 | get默认仅处理缺键，显式null仍为None | 多字段空白 | 金额有限非负；日期严格 | 区分无事件/未知/真实0；不静默填0 |
| 其他公司行动 | 无配股等独立语义 | 此CSV亦非完整行动全集 | 仅现金与新增股权益 | 不能标注为完整corp-actions替代品 |

## 本地 Wind 文件完整性

本次实读 9096 行、1078 个代码，event_id 无重复；ex_date 为 2015-01-26 至 2026-09-30。pay_date 和 cash_div_per_share 各缺178行；有送/转比例的1229行中，1行缺 bonus_list_date。完整字段空值统计与 SHA256 见 `04-corp-actions-stats.json`。

原 README 声明目标宇宙2774只、已确认事件覆盖1083只（其中5只无事件）、1529只仍未抓取、174只代码存在失败；这批文件本身也是部分数据，不能作为全市场完备真值。现成 README 复制到 `raw/corp-actions-README.md`；样本 `04-wind-samples.csv` 只包含本地真正命中的代码，不保证探针三票都有记录。

BT 要求日期 YYYYMMDD，pay_date/list_date 不早于 ex_date，金额与比例有限非负；list_date 缺省回 ex_date 是现有行为，不应被适配层当作可售日证据。经验证的每股送股+每股转增可合为 BT bonus_ratio，但现金缺失、派息/上市日缺失、未实施、重复修订等应先形成拒绝/待补列表。此轮没有产出可直接喂给 BT 的事件文件，也未修改交易/回测代码。
