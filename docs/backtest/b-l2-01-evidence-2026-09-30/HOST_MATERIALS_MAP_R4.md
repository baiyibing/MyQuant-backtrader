# B-L2-01 R4 证据材料地图（host-assist 采集，2026-09-30）

采集人：ZCode（应 host 要求协助）；采集机：本机（newtest_4090，湖 `E:\stock_data` 本地可见，
`vanna312` = R3 探针同一解释器 3.12.13）。**本目录所有 `raw_*` 均为原材料/行式摘录草稿
（`bl2_raw_excerpt_draft_v0_host_review`），不是 `bl2_proof_v1`；host 逐行审核后才能进 proof
的 `source_refs`。** 生成脚本：`_gen_raw_materials.py`（可重跑核验）。

## 0. 版本指纹

| 项 | 值 |
|---|---|
| 本仓 HEAD | `a268e11bc682cd1ae5a6672ab89091cea1abe937`（= R3 `tip_expected` ✓） |
| OSkhQuant1.3 HEAD | `47afc2447fa4df5b37af1400ec1aea419ed7fda1` |
| MyQuant HEAD | `910abd38652b523cae07dd7a64032f0f71a06ff0` |
| xtquant | `250516.1.1`（`D:\anaconda3\envs\vanna312\Lib\site-packages\xtquant`） |
| 湖分钟分区 | `E:\stock_data\stock\period=1m\dividend_type=none\symbol=603196_SH\data.parquet`（sha256 见 census 包） |

## 1. 本次已采集/核验的事实（全部在本机可复算）

### 1.1 时间语义（§3.1 门，材料已够）
- `time:int64` = **上海墙钟按 UTC epoch 毫秒编码**（1761211800000 → 上海墙钟 2025-10-23 09:30，
  R3 探针同解读）。**不是真 UTC**。
- 分钟 bar 为 **END 标签**：标签 t 覆盖 [t−1min, t)。每日 241 行 = 09:30 集合竞价条 + 09:31–11:30 +
  13:01–15:00；合同可交易网格（END 标签 09:31–11:30 + 13:01–14:57 = 237 格/日）**2133/2133 全有行、
  零缺格、零重复**；每日另有 09:30/14:58/14:59/15:00 四条网格外行（15:00 行可作 mark，§7）。
- xtdata.py docstring：`fill_data=True` 对齐时缺失分钟 amount、volume 填 0、价格以前条 close 填充
  （1.3 下载即 fill_data=True）→ 零量行可能是 vendor 填充行。

### 1.2 状态网格（status 门）
- 窗口 9 个交易日全有 bar；46 格零量（明细在 census 包），其中 40/46 close=前值（填充/无成交特征）。
- 2087 格 volume>0：**该分钟有成交本身即"未停牌"的积极证据**（proof 行可引 census/湖 parquet 行号）。
- 46 格零量 + 全部格子的日级停牌结论仍需**独立 explicit 停牌事实源**（见 §3 剩余项 R4-A）。

### 1.3 instrument 前置事实
- 603196.SH 在 `vendor_wind_st_status/st_daily.parquet` **全表零命中 = 非 ST** → 主板 ±10% 档。
- `ex_date_index.parquet` 2025-09-01..2025-12-31 **零除权事件**（与 R2/R3 探针一致；覆盖完整性仍按
  §3.2 另证）。
- 窗口前后日线（2025-10-20..11-05）已存包：reference 价可用「湖 raw 前一交易日 close」，但须经
  approved_derivation 规则显式批准该映射（交易所规则本身即以"前收盘价"为基准，见规则引用包）。

### 1.4 规则与实现旁证
- 交易所公式（2023 修订交易规则）：**涨跌幅价格 = 前收盘价 ×（1±比例），四舍五入至最小变动单位
  （A 股 0.01 元）**；主板 ±10%。窗口（2025-10）适用；**2026-04-24 沪深北交易所修订交易规则、
  2026-07-06 起主板 ST 5%→10%**——窗口早于该变更且 603196 非 ST，不受影响，但 rule_version 材料
  应同时钉两份以显式划界。
- 1.3 实现：`oskh_core/board_limit.py`（板块率 SSOT）+ `qmt_xtdata_mock.py::_get_limit_rate/
  _limit_prices`（前收盘×(1±率) round 0.01；live 侧柜台真实涨跌停价兜底）。
- 本仓实现：`backtest/research/ashare_session.py`（档位/涨跌停命中，Decimal 链见
  docs/backtest/engine-ashare-correctness.md）。
- 湖→qlib 旁证（**NON-ATTESTATION**，§9.2 明禁作 proof）：MyQuant `stage_1min_from_lake.py`
  以 `vol*100` 作 vwap 分母 = 消费侧按「手」假设；R2 的 amount/(close×vol)≈100 同类启发式。

## 2. 已落盘材料（evidence/raw_materials/，均含原件 SHA-256）

| 文件 | sha256（摘录包本身） | 用途 |
|---|---|---|
| raw_excerpt_xtquant_docs.json | 3884f478…bc8a12 | vendor 字段语义行式摘录（K线表/填充语义/委托量单位/instrument detail） |
| raw_excerpt_cross_repo_rules.json | 96c1476e…40a524 | 1.3/本仓规则实现 + MyQuant ×100 旁证（明确 NON-ATTESTATION） |
| raw_lake_daily_603196SH_20251020_20251105.json | 773eadfc…467a8cee | reference/limits 推导输入（湖日线原行） |
| raw_lake_minute_census_603196SH_20251023_20251104.json | b4ee473b…632b7188 | 2169 行逐格 census（row_idx/END 标签/零量清单/网格映射） |
| raw_st_membership_603196SH.json | 9353e3e0…4b022c9a | 非 ST 证明材料 |
| raw_corporate_actions_603196SH_window.json | fd8311f5…b2257015 | 窗口零公司行动材料 |
| web_rule_references_20260930.md | （见文件内） | 交易所规则公式/2026 ST 新政的公开来源 URL + 检索日期 |

## 3. 三门剩余缺口与 R4 前动作清单

### R4-A（停牌事实源，status 门的唯一硬缺口）
本机 xtquant 无运行中的 QMT 客户端，`preClose/suspendFlag` 未落湖。**在装国金 miniQMT 的运维机跑一次
全字段回补**（603196.SH，20251020–20251105，1d + 1m，字段含 time/close/volume/preClose/suspendFlag），
输出 JSON 落本目录。一次拉取同时解决：
- `suspendFlag`（0 正常/1 停牌/-1 当日起复牌）→ 全部 2133 格 + 46 零量格的 explicit 停牌事实；
- vendor `preClose` → instruments 门 reference_price 的 **source_fact** 路线（优于推导路线）。
脚本骨架：
```python
from xtquant import xtdata
xtdata.download_history_data2(['603196.SH'], '1d', '20251020', '20251105')   # 同理 '1m'
d = xtdata.get_market_data_ex(['time','close','volume','preClose','suspendFlag'],
    ['603196.SH'], period='1d', start_time='20251020', end_time='20251105',
    count=-1, dividend_type='none', fill_data=False)
# 逐行 dump JSON（含原始字段值），不经任何换算
```
若无法开机：备选是巨潮/交易所停牌公告检索 + 日级 vendor 表，但「无公告」属负面证明，合同大概率不认。

### R4-B（量单位声明，units 门的唯一硬缺口）
已排除：xtquant 包内 doc/xtdata.md/xtdata.py docstring（K线 volume **无单位注记**，摘录可证）；
l2quote 委买卖量「单位是手」与 xttrader 委托量「股」都**不是** K线 volume 的声明。
剩余选项（按优先级）：
1. host 浏览器打开迅投官方文档站 `dict.thtrader.com/nativeApi/xtquant.html`（本机 DNS 解析失败）
   找 K线 volume 单位句，存档 HTML + 行式摘录；
2. 国金 miniQMT 客户端内置帮助/字段说明（运维机截图或导出）；
3. 国金服务渠道的书面字段口径；
4. 都拿不到 → units 门保持 BLOCKED（合同禁止以任何比率/换算启发式签
   `incremental_volume_units_verified`）。
（用户提的「湖 vs qlib 对比」已有：MyQuant ×100 属旁证材料，只能放 limitations/佐证，不能当声明。）

### R4-C（instruments 门，两条路线择一）
- **source_fact 路线（推荐，依赖 R4-A）**：vendor preClose + `get_instrument_detail`
  （UpStopPrice/DownStopPrice/PriceTick/InstrumentStatus，当日语义，对窗口日不适用——只可作
  今日 sanity，不可作历史事实）→ 历史 reference/limits 仍走推导，见下。
- **approved_derivation 路线（本机已可成包）**：inputs = 湖日线前收（raw 包）+ 规则文本
  （web_rule_references，host 钉全文存档）；rule = 前收×(1±0.10) 四舍五入至 0.01；双 issuer
  （host + 4090bot）两份 proof 全引 inputs；独立核验内容：每日 high≤limit_up、low≥limit_down
  （日线包可复算）。tick=0.01、lot=100 需规则文本中的最小变动单位/申报单位条款支撑
  （当前 web 摘要有公式与 0.01，**lot 100 的条款原文还没钉**——host 存档规则全文时一并取）。

### R4-D（host 审核）
- 逐行审核 raw_* 六包 + 规则引用；确认 issuer 身份与「两 issuer」人选；
- 按 §9.5 顺序：先 pin 原始来源，再 pin proof/消费包，加入 recipe.sources，
  `bl2_source_transform_v3`，重算 `attestation_scope(recipe)` 后冻结；
- R4 发车本身仍需另一条具名 Human GO（§9.5 第 7 条），本地图不构成 GO。

## 4. 与 R3 探针的差异说明
- R3 的 `window_first.index="2025-10-23 09:30:00"` 与本地图时间语义一致（naive Shanghai）；
- R3 报「2169 行」本地图复算一致（241×9）；
- R2 的「比率≈100」在本地图中**降级为 NON-ATTESTATION 旁证**，不进任何 proof 的正面依据。
