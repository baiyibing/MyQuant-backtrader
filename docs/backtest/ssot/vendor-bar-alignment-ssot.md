# Wind / 同花顺（THS）/ QMT 分钟与日线 bar 对齐 SSOT

## 1. 目的与边界

本表供 Human 比较 Wind、同花顺（THS）与 QMT 下载的分钟/日线行情时，统一说明区间、成交量单位、时间编码与缺根政策。2026-10-01 docs-only Human GO；基线 `f9ba3158b8e2bd82ac6eb5ab54668add224873c2`（#291）。表内 vendor 特征以本次只读证据为限，不把单批导出推广成所有接口的保证。

成交假设另见 [minute-fill-policy-ssot.md](../minute-fill-policy-ssot.md)；复权/止损另见 [行业实践说明](../note-minute-bar-industry-practices-2026-09-26.md)。本表不改 MatchCore / Fees / engine，不开启 δ5 certified 或 R4，也不授权改写湖。采集、外部下载与 vendor merge 仍属 OSkhQuant1.3，本仓只消费配置的湖。

## 2. Canonical target：区间与单位分开声明

**QMT 湖 ingest 对齐目标为 `minute_label=END`。** 对连续交易的一分钟区间 `[t, t+1)`，START 以 t 标记，END 以 t+1 标记；这是区间身份约定，不等于成交价、决策时点或整根 OHLCV 的信息可得时点。

成交量必须在 PIN 显式声明 `lots` 或 `raw_shares_incremental`（股、逐桶增量），不能由数值大小推断。历史 lake siblings 为 lots，本次 export 侧 ×100 后进入 shares overlay；vendor 股数不再 ×100，也不 //100。新 shares 树直读及 `transformations=[]` 的范围见 [shares-global S2](../note-shares-raw-tree-loader-s2-2026-10-01.md)，不能把历史 lots 结论覆盖到新树。

时间编码同样独立：本例 prepare / market PIN 均为 `time_encoding=local_wall_as_utc_ms`，即上海墙上时钟按 UTC 毫秒编码；不能当成真实 UTC 再加八小时。其他来源须声明实际编码及解码规则，不能照抄本例。

## 3. Vendor matrix（已知事实与待证项）

| 来源 / 周期 | typical minute_label | 成交量单位注意事项 | 集合竞价 / 午休边界 | 稀疏网格行为 |
|---|---|---|---|---|
| Wind 1m | 常见 START；本例已接受 START | 本例 vendor shares；其他接口/批次仍须 PIN 核对增量或累计、单位 | 本例真实 13:00 存在；09:30 是否含竞价须逐源核对，不能凭标签认定 | 本例接受省略零量分钟的 sparse；缺根原因仍须审计，不默认全是零量 |
| Wind 1d | 不适用（交易日键）；本例无 Wind 日线验证 | **未证实 / needs Human**：不能沿用 Wind 1m 的单位推断 | 竞价是否纳入日线汇总未证实；不做分钟 +1min | 停牌/缺日/零量行政策未证实 |
| THS 1d | 不适用（交易日键） | 本例 Human 接受 shares；不 //100，其他批次需声明 | 竞价纳入方式未证实，日线按交易日核对 | 本例不证明通用停牌/缺日政策 |
| THS 1m | **未证实 / needs Human** | 单位、增量/累计均未证实 | 开盘、竞价与 13:00/13:01 未证实 | 未证实；禁止借用 Wind 网格结论 |
| QMT / xtdata download / 历史 lake siblings 1m | 湖对齐目标 END；历史 siblings 有 13:01、无 13:00；不同下载版本仍须核验 | 历史湖 lots，export ×100→shares；新 shares 树另按其 PIN | prepare 声明 `END; 09:30 auction excluded`；不证明所有 QMT 下载均排除竞价 | prepare scaffold 要求 full grid，不证明所有原始下载均完整；须核对缺根 |
| QMT / xtdata / lake 1d | 不适用（交易日键） | 本例历史湖 export lots→shares；其他树按 PIN | 与分钟聚合的竞价范围须一致后再比较 | 本例有日线 OHLC 全零例外，见 §7；不能普遍用空表/零行掩盖缺数 |

## 4. 对齐规则：先核区间，再转换标签

1. 按同标的、交易日、价格域及区间身份 `[t, t+1)` 对齐，不能直接用时间戳字符串相等判定两根相同。
2. **START→END 仅在样本标的 OHLCV cross-check 通过后执行**，记录样本、窗口、差异与转换规则。不能仅凭“有 13:00”对整表盲加一分钟。连续交易样本应核对 13:00 START ↔ 13:01 END、09:30 START ↔ 09:31 END；09:30 竞价行必须先单独识别，不能机械移为连续交易 bar。
3. 午休不能跨会话造根；上午尾根、下午首根、收盘竞价/尾根都须核对区间与聚合范围。边界不一致即保留差异，等待 Human，不用平移掩盖。
4. 日线按交易日对齐；同价域、同竞价范围后核对日线 OHLCV 与分钟聚合。日线不应用分钟 +1min 规则。
5. 缺根不等于已证明零量。**PIN 未显式声明 zero-fill 时禁止补造零 bar**；即使声明，也须说明依据、适用区间、OHLC 处理与 Human 授权，不能把缺数变成“已观测”。

## 5. vendor fill / market overlay 必备 PIN

以下是文档要求，不是新增 CLI/schema 实现：

| 字段 | 必须说明 |
|---|---|
| `minute_label` | START / END、竞价排除或纳入；纯日线明确不适用。混合来源须逐 source/symbol 声明，不能仅靠顶层标签 |
| `unit`（或 volume unit） | lots / raw_shares_incremental，增量或累计；源 at-rest 与输出单位分列 |
| `time_encoding` | 原始编码、时区语义、解码规则；是否 local_wall_as_utc_ms |
| source paths + `sha256` | 原始 vendor 文件与实际湖输入的路径/SHA-256、周期、标的、窗口；输出 artifact 路径/SHA-256；null/通配符不等于已完成逐文件 pin |
| `conversion_rule` / `transformations` | 标签、单位、日线派生、缺根处理的实际转换；源单位与 export/runtime 转换分别记录，不能用 runtime 空数组抹掉 export ×100 |
| `human_acceptance` | 放宽标签/网格时的 Human GO 日期、范围、证据链接；未放宽也显式说明 |
| coverage / cross-check | 样本 OHLCV 对照、竞价/会话、缺根/重复、价格域、异常清单与处置 |

## 6. 写湖前 checklist（未来写入方的门槛）

- [ ] 独立 Human 写湖 GO、写入仓与目标树明确；本表不提供该授权，本仓不写 market bars。
- [ ] 原始输入/输出路径与 SHA-256 完整，标的、周期、窗口、版本可追溯；源单位不靠猜。
- [ ] minute END、单位、时间解码、价格域与日线交易日键明确；START 转换已完成样本 OHLCV 核对并留下证据。
- [ ] 抽样覆盖开盘、午休两侧、收盘及稀疏/异常标的；竞价范围一致；OHLC、volume（必要时 amount）差异逐项解释，容差须预先声明。
- [ ] 排序、重复键、缺根、零量与停牌分开核查；无未声明 zero-fill；日线与分钟聚合在相同范围内核对。
- [ ] 未解差异 fail closed，记录 **未证实 / needs Human**；研究 overlay 的局部接受不作为 ingest 验收。

## 7. Overlay 与写湖政策；2026-10-01 worked example

研究 market overlay 可在 PIN 与 Human acceptance 明确后保留 vendor 原生 START+sparse；适用范围仅该研究刀。写湖则须 END + 声明单位 + cross-check，并取得独立写湖 GO，禁止盲重标。

只读实例：[host RECEIPT](/workspace/handoffs/topk_s1_cap_cli_host_20261001/RECEIPT.md)、[market PIN](/workspace/handoffs/topk_s1_cap_cli_host_20261001/market_PIN.json)、[GAPS](/workspace/handoffs/topk_s1_cap_cli_host_20261001/GAPS.json)、[prepare PIN](/workspace/handoffs/topk_s1_cap_cli_host_20261001/prepare/PIN.json)（box 本地证据，非仓内附件）。

该刀为 002231.SZ / 300379.SZ / 600200.SH 使用 THS 1d shares 与 Wind 1m START shares；Human 于 2026-10-01 接受 START+sparse，不重标、不造根，三个 vendor 标的 **lake_written=false**。prepare 保持 `END; 09:30 auction excluded`；market 顶层为 `unit=raw_shares_incremental`、`minute_label=START`、`time_encoding=local_wall_as_utc_ms`。其 conversion_rule 同时注明其余历史湖 siblings 为 END、export lots×100；因此该 overlay 不能被描述为全部来源已统一 START，更不能作为统一 ingest 证明。

本例 PIN 的历史湖来源含通配路径及 `sha256=null`，不满足未来写湖的逐文件 pin 门槛。另有 000638.SZ 日线 OHLC 全零，以已有 1m 聚合派生日线并记录 conversion_rule；这是特定异常处理，不是补造行情或通用修复授权。研究运行 OK 不证明跨 vendor 全量 OHLCV 已对齐。

**本 SSOT ≠ δ5 certified ≠ R4；docs-only；勿合，等待 Human「合」。** 后续 vendor→lake adapter CLI 须另行 Human GO。

## 8. 只读样本核对 scaffold

[2026-10-01 PLAN](../vendor-bar-xcheck-2026-10-01/PLAN.md) 与 [只读 CLI](../../../scripts/research/vendor_bar_xcheck.py) 提供交集 OHLCV 核对、边界及单位疑点报告；不写湖、不重标源表。START→END 实际转换仍须先取得样本证据；此 scaffold ≠δ5 ≠R4，物理湖核对待独立 Human GO。

## 9. Phase2 adapter staging（独立 Human GO）

[三票 Phase2 PLAN](../vendor-three-symbol-lake-ingest-2026-10-01/PLAN.md) 与 [adapter CLI](../../../scripts/research/vendor_to_lake_adapter.py) 仅将已接受的 Wind START shares（可选 THS 1d）转换到独立 staging：sparse A、lots（//100 且审计余数）、删除 START 09:30 竞价后连续 +1min。此 GO 不改变 §7 的 shares overlay，不代表真实三票验收；write-lake 仍需独立 Human GO，CLI 无写湖开关。≠δ5 ≠R4；勿合，等待 Human「合」。
