# hithink（同花顺 Financial-API）湖补强 backlog — 2026-10-29

状态：**候选清单，未排期**。非 [corp-actions 双通道方案](plan-corp-actions-hithink-channel-2026-10-29.md) 范围；每项落地各自小方案 + 单独 Human GO。

来源：PR #531 评审补充——湖数据集清单（`common/infra/data_root.py`）× hithink 官方目录（`fuyao.aicubes.cn/llms-full.txt`）× [`docs/research/a-stock-data-reviews/SYNTHESIS.md`](../research/a-stock-data-reviews/SYNTHESIS.md) 已列补缺候选的交集。

## 候选项

| # | 湖内现状 / 缺口 | hithink 来源 | 价值与定位 | 优先级 |
|---|---|---|---|---|
| A | 交易日历无湖侧 SSOT，回测日历靠 pandas-market-calendars 推算（SYNTHESIS 下一步已排"2027 日历 diff"探针） | `holiday-calendar` dump（2000–2030） | 官方休市日历落湖侧 calendar 旁表，替代第三方推算；1 次调用 | 高（最小起点） |
| B | `index/period=1d` 只有价格、无成分/权重 | `index-cons` dump（沪深300/中证500/1000 + 28 扩展指数，含权重）+ mcp `index-weight` | SYNTHESIS 补缺候选"中证/国证当前成分权重"；池构建与指数对冲回测。**当前快照**，须带 `fetched_at` 钉住，PIT 变迁仍缺 | 高 |
| C | `adj_factor.parquet` / `ex_date_index`（QMT 价格侧权威）无第二独立审计源 | **corp-actions 双通道方案已拉的同一份 adjustment-factors dump，零新增取数成本** | `(thscode, ex_date)` 集合对 `ex_date_index` 做 diff，抓 QMT 日更漏日/错漏除权。SYNTHESIS 点 6：腾讯 qfq ≠ 新浪 ≠ QMT 因子互不一致，多源审计是既有需求 | 高（搭车） |
| D | `stock`/`index`/`etf` `period=1d` 收盘列质量无独立源 | `stock-close-values` / `index-close-values` / `etf-close-values` dumps（1990→ 全市场收盘序列，中量级） | 周期性全量收盘 diff，抓漏日/坏点。**审计源，非替换源**（仅收盘序列，无完整 OHLCV/量） | 中 |
| E | `float_shares` / `free_float_shares` 陈旧度未知 | `stock-basic-info` dump（总股本/流通股本/上市日期/状态，全市场） | float 审计旁表；快照性质同 B，带 `fetched_at` | 中 |
| F | —（新研究数据集） | `fund-flow-stocks` dump（个股资金流近 100 日全市场） | 窗口浅，研究旁表候选 | 低 |
| G | —（财报族因子） | mcp `stat-finance` 系（归母净利/营收/ROE/毛利率…，逐码查询） | **不做**：逐码调用 + 官方自警 429 / 按指数成分展开的调用放大——正是 corp-actions 双通道要摆脱的 463 任务模式的翻版 | 不做 |

## 明确补不了（继续走原渠道）

- 申万行业 **PIT 变迁史**（SYNTHESIS 最优先公开补缺项）：hithink 只有当前 swl1/概念板块归属，无历史变迁。
- L2 逐笔、研报/宏观/可转债条款、北向个股历史（`hgtmt` 仅实时大盘/板块级）。
- 实时行情（`realtime-quote`）：按既有原则仅监控用途，公开价绝不进 live/paper 决策价。

## 工程约定（复用 corp-actions 双通道已验证骨架）

- env Key（`HITHINK_FINANCE_API_KEY`）、原子写（tmp+rename）、dump sha256 + `fetched_at` 进 state 证据链、排除/容差清单 fail-closed、单独 Human GO。
- corp-actions PR-A 实现时把"dump 下载 → 必需列校验 → sha256/state 留证"抽成函数级公用件（不引新依赖）；A–E 每数据集一个薄 driver，不做巨脚本。
- 上游契约以 `fuyao.aicubes.cn/llms-full.txt` 为准并记版本/日期进 state，防上游静默改列（同 corp-actions 方案 §6 风险条目）。
