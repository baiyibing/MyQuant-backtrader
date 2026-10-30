# corp-actions 四源冻结核对与独立扩样 — 2026-10-30

本研究检验 hithink 批量事件与 CNINFO v10 经济事实能否协作，在 Wind 在线不可用时推进离线研究。QMT 行情/价格复权权威保持不变，Wind #501 只作冻结历史对照。研究不接入消费者、不启用 C3、不代签 Owner、不合湖或切主源。

38 码固定样本已完成四源核对；另冻结 240 个独立样本进行一次性抓取验证。CNINFO v10 与已批准政策在本轮保持冻结，新增失败进入复核，不利用本轮盲测结果调规则后回写同一轮分数。

## 1. 冻结输入与职责

| 来源 | 冻结对象 | 本次可核对内容 |
|---|---|---|
| CNINFO | 实现 `f00c75708f92d93db3ce7583e59b6cadc615c84b`，证据 `ce30b8bf456fdaf7639b61650e339671482eaf09`（OSkh #1250/#1251） | 152 个已归档事件、原始抽取值、118 个 adapter-accepted 事件及 34 条复核；来源 URL/PDF/text 哈希 |
| Wind | #501 `584538beff822c12b46079fc237a1771453ff25a`，21779 行 / 2693 个有事件代码 | 冻结历史值，不发在线 Wind 请求 |
| hithink | 2026-10-29 取得的原始 dump，57700 行、完全重复折叠后 57699 行 / 5435 码 | 现金/送转原始数值及日期键；没有 record/pay/list 日期 |
| QMT | 本机 resolver → `E:\stock_data`，有效 `.authority`，`ex_date_index.parquet` 截至 2026-10-15 | 只核对除权日期；该索引未保留七字段中的金额/送转，不从 `dr` 推导金额 |

完整输入和原始文件 SHA256 见 [inputs_manifest.json](evidence/corp-actions-four-source-2026-10-30/inputs_manifest.json)，QMT/hithink 指纹见 [report.json](evidence/corp-actions-four-source-2026-10-30/report.json)。本机 E、75 物理机 F 属不同宿主路径；marker 不证明同步状态或数据新鲜度。

固定样本沿用 C2-wide 的 38 码，事件窗口 **2024-01-01—2026-10-06**。它是用于调试过规则的固定回归样本，不是新盲测集；不据此估算全市场召回率。QMT 金额的第三方核对如需实施，另在 1.3 留存既有七字段后执行。

## 2. 38 码四源结果

| 项目 | 本次结果 |
|---|---:|
| 比较窗口内 CNINFO 事件 | 147 |
| hithink / QMT / Wind 中存在相应日期键 | 各 147 |
| CNINFO 全部 adapter-accepted / review | 118 / 34（152 事件总量） |
| 比较窗内 adapter-accepted / 未接受 | 115 / 32 |
| hithink ↔ Wind 现金：精确相同 / 不同 / 一侧未知 | 139 / 5 / 3 |
| hithink ↔ CNINFO 原始现金：精确相同 / 不同 / 一侧未知 | 142 / 2 / 3 |
| hithink ↔ CNINFO 原始送转合计：相同 / 不同 / 原始分腿未知 | 73 / 1 / 73 |
| hithink ↔ CNINFO 已接受事件的适配送转合计 | 114 相同 / 1 不同；另 32 条未接受，不参与此项 |

逐事件记录见 [four_source_events.csv](evidence/corp-actions-four-source-2026-10-30/four_source_events.csv)，数值差异见 [four_source_differences.csv](evidence/corp-actions-four-source-2026-10-30/four_source_differences.csv)。同日多行只可作为显式的日口径诊断，不能由 groupby 消除公告身份或替代修订链。

OSkh #1251 的 Run B 是 **147 MATCH / 0 FIELD_DIFF 的 pre-adapter 复核集**，不撤销拒绝。Run A 才是窗口内 **115 MATCH / 32 WIND_ONLY**；32 是接受集缺席，不是召回缺口。原报告中 Run A 的 MATCH 子类型为 54 exact、59 NULL-as-zero、1 ROUND4、1 两者兼有；本研究保留这些已批准政策，不把它们改名为原始字段精确相同。

### 2.1 已核实的金额用途差异

`301266.SZ` 两份公告原文（来自冻结 fixture，text SHA256 与 C2 来源记录一致）明确把 hithink 对应数值用于**按总股本摊薄计算除权参考价**：

| 除权日 | CNINFO 经济候选现金 | hithink 现金 | CNINFO 送转合计 | hithink 送转合计 |
|---|---:|---:|---:|---:|
| 2025-05-30 | 0.1 | 0.0999998 | 0 | 0 |
| 2026-05-22 | 0.2 | 0.1999990 | 0.3 | 0.2999985 |

这不是仅靠舍入即可消除的经济语义差异。以按 lot 向下取整的 1000 股为例，`0.3` 与 `0.2999985` 分别算出 300 和 299 股。原值、用途及公告证据见 [semantic_findings.json](evidence/corp-actions-four-source-2026-10-30/semantic_findings.json)。不能仅补齐日期、放宽阈值或沿用 Wind 比较容差，就把 hithink 调整价格数值用于 entitlement。

两份冻结文本另做了观测式重放：调用原 v10 函数并断言字段/状态与归档一致，分别记录原文候选值、选择结果与上市日缺省前值。该两例的现金（及 2026 年转增）由已批准的 ROUND4 多值合并得到；它们是经济候选的**政策选择结果**，不能把原文多种分母数值抹成“原文只有一个金额”。见 [semantic_policy_trace.json](evidence/corp-actions-four-source-2026-10-30/semantic_policy_trace.json)。

另外三笔 hithink↔Wind 现金差异是 `000858/2026-07-16`、`300171/2024-07-12`、`600519/2026-06-26`：hithink 与 CNINFO 保存的数值相同，Wind 为四位小数。现行 CNINFO↔Wind ROUND4 政策照常保留，但不自动成为 hithink 接湖或消费的容差。

### 2.2 原文抽取和政策适配分别记录

窗口内 62 个已接受事件涉及空送转腿适配，计 116 个字段；另有 10 个上市日字段在 v8 尚空、v10 按缺省政策成为 ex_date。本研究通过冻结 v8/v10 差分标记上市日，未重新下载/回放全部 152 份原 PDF；不能把这项标记称为独立 PDF 签收。

相应记录见 [policy_derived_events.csv](evidence/corp-actions-four-source-2026-10-30/policy_derived_events.csv)。公告明示值、缺失原值、适配值、政策依据/版本应在 evidence sidecar 中分别留存；保持现有十列湖 schema 不变，也不能抹去原始未知状态。

## 3. 独立 240 码验证合同

固定 seed **20261030**，抽样框为本机 QMT 索引中自 2024 年起有除权记录的代码；不按 hithink 或 Wind 是否有值筛选。剔除原 38 码和既有 MVP/预检代码 `000001.SZ / 000002.SZ`。各层内对规范化代码排序后固定抽样，清单及 SHA256 在任何新样本查询前冻结。

| 层 | 码数 |
|---|---:|
| 沪市主板 | 60 |
| 深市主板 | 60 |
| 创业板 | 60 |
| 科创板 | 40 |
| 北交所 | 20 |
| 合计 | 240 |

清单见 [holdout_240.csv](evidence/corp-actions-four-source-2026-10-30/holdout_240.csv)，版本/范围合同见 [holdout_manifest.json](evidence/corp-actions-four-source-2026-10-30/holdout_manifest.json)。这是按板块分层的正事件抽样框，既不是全 A 随机样本，也没有验证从未分红标的；样本权重不能当成市场权重。

- 公告查询窗：**2023-12-01—2026-10-28**，冻结四关键词、现有标题规则、issuer orgId、每查询最多 10 页；原始查询、排除标题和分页结果全部留证。
- 历史 ex_date 窗：**2024-01-01—2026-10-06**，可用 Wind 历史对照；增量 ex_date 窗：**2026-10-07—2026-10-28**，不等待 Wind 在线，超出本机 QMT 2026-10-15 截止点的事件标记为超出快照窗口。
- 正向预检：已知 `600519.SH` 公告查询返回 9 条，防止把访问故障/结构变化造成的伪空当作“没有事件”。此码不在盲测清单。
- 一次性串行研究抓取，至少 1.5 秒间隔，失败限次退避；401/403/429 停止。缓存须校验哈希，缺失/错误/截断均进覆盖报告，不当作空数据，不推进湖水位。
- 原始 PDF/txt 只在本机隔离研究目录保留，不上传到本 PR。原文 URL、PDF/text 哈希、公告时间、fetch_at、抽取/适配版本随结果保存。公告原文事实和政策结果分别核对，当前研究不声明 PIT/消费者就绪。
- 完成冻结的样本运行后，分别报告查询完成、PDF 可用、抽取正确性、adapter 接受率、复核原因、跨源差异及域外事件；不能用“MATCH 接近零差异”代替这些分母。
- hithink 的原 2774 码/162 条增量清单仅用于优先核对和对照，不构成公告采集分母；独立样本上的公告查询保留来源外事件、修订与失败情况。

## 4. 后续接入边界

经济候选应来自完整公告事件或已解析的修订链，hithink 提供发现与交叉核对。`(code, ex_date)` 是关联键，不授权拼接字段或修改事件身份；多公告/同日多事件、金额分母差异及不完整事件进入复核。

正式消费前仍需 Owner 独立签收原文事实/适配政策、覆盖与 PIT、修订身份、BT/qlib 接口。此次研究不签 OWNER_SIGNOFF，不启动 C3，不发布湖数据，不改变 live/paper 或 QMT 价格权威。生产采集和发布归 1.3，本仓保留研究证据与既有离线候选路径。
