# hithink（同花顺 Financial-API）湖补强 backlog — 2026-10-29

状态：**候选清单，未排期**。非 [corp-actions 双通道方案](plan-corp-actions-hithink-channel-2026-10-29.md) 范围；每项落地各自小方案 + 单独 Human GO。

来源：PR #531 评审补充，2026-10-30 按本机湖与接口探针修订。既有候选来自湖清单与 SYNTHESIS；**候选名称不等于已证实的 API 能力**。公开 `llms-full.txt` 未列出下表所称 `holiday-calendar/index-cons/stock-basic-info/stock-close-values` dump；按 `GET /api/dump/market-dumps/<name>/download-url` 模式实测均为 404，只说明这些测试路径不可用，不能据此断言服务无对应数据。落地前须补真实端点、schema、授权范围和快照证据，不能承诺“一次 dump 即可”。

## 候选项

| # | 湖内现状 / 缺口 | hithink 来源 | 价值与定位 | 优先级 |
|---|---|---|---|---|
| A | 本机无独立湖日历旁表，但 1.3 已有 `TradeCalendarPort`、PMC/QMT/本地日历解析链 | `holiday-calendar` 为待证实的 dump 候选；公开交易日历接口按其实际范围核实 | 先做离线 diff，再考虑旁表；不在 #531 替换现有日历端口或生产来源，不预设 2000–2030 范围 | 待端点验证 |
| B | `index/period=1d` 有价格，当前成分/权重与 PIT 历史须分别核实 | `index-cons` dump 名称待证实；已公开成分接口可另做能力探针 | 当前快照带 `fetched_at` 与适用日，不充当 PIT 变迁；先证明权重/范围字段 | 待端点验证 |
| C | QMT `adj_factor` / `ex_date_index` 已有权威链，需要独立审计 | 已取得并冻结 SHA256 的 `adjustment-factors` dump；与 CNINFO v10 / Wind 离线快照协作 | [四源研究](note-corp-actions-four-source-study-2026-10-30.md)先验日期与经济口径；共同窗口和宇宙一致。QMT 七字段留存另在 1.3 规划，不用 `dr` 或 hithink 数值重写 front/因子 | 优先，已有证据 |
| D | QMT 股票/指数/ETF 各自分树、raw/front 含义固定 | `stock-close-values` 等 dump 名称、范围待证实 | 单独按资产、复权方式、交易日、停牌/填充语义对拍；仅审计，不混写 QMT 行情 | 待端点验证 |
| E | 本机 `float_shares` 快照 2026-09-26；`free_float_shares` 最大记录日 2026-05-30，后者不等于采集时间 | `stock-basic-info` dump 名称待证实；需确认单位、流通/自由流通定义和时间字段 | 当前基本资料不能替代历史自由流通股本；先补新鲜度与历史可知性元数据，再做同口径快照核对 | 中，先核查现有 QMT |
| F | —（新研究数据集） | `fund-flow-stocks` dump（个股资金流近 100 日全市场） | 窗口浅，研究旁表候选 | 低 |
| G | —（财报族因子） | mcp `stat-finance` 系（归母净利/营收/ROE/毛利率…，逐码查询） | **不做**：逐码调用 + 官方自警 429 / 按指数成分展开的调用放大——正是 corp-actions 双通道要摆脱的 463 任务模式的翻版 | 不做 |

## 明确补不了（继续走原渠道）

- 申万行业 **PIT 变迁史**（SYNTHESIS 最优先公开补缺项）：hithink 只有当前 swl1/概念板块归属，无历史变迁。
- L2 逐笔、研报/宏观/可转债条款、北向个股历史（`hgtmt` 仅实时大盘/板块级）。
- 实时行情（`realtime-quote`）：按既有原则仅监控用途，公开价绝不进 live/paper 决策价。

## 工程约定（复用 corp-actions 双通道已验证骨架）

- env Key（`HITHINK_FINANCE_API_KEY`）、原子写（tmp+rename）、dump sha256 + `fetched_at` 进 state 证据链、排除/容差清单 fail-closed、单独 Human GO。
- 不因候选清单提前抽象 A–E 通用采集平台。既有 BT 离线候选授权保留，新增通用采集/生产发布归 1.3；确认真实第二个数据集契约后再决定是否提取最小公用函数。
- 上游契约以 `fuyao.aicubes.cn/llms-full.txt` 为准并记版本/日期进 state，防上游静默改列（同 corp-actions 方案 §6 风险条目）。
- 湖根只经 resolver，`.authority` 与输入哈希留证：本机 E、75 物理机 F，4090 以自身配置为准；不把物理盘符当作跨宿主契约。
