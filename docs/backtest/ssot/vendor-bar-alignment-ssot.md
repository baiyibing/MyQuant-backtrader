# Wind / 同花顺（THS）/ QMT 分钟与日线 bar 对齐 SSOT

## 1. 目的与边界

本表供 Human 比较 Wind、同花顺（THS）与 QMT 下载的分钟/日线行情时，统一说明区间、成交量单位、时间编码与缺根政策。2026-10-01 docs-only Human GO；基线 `f9ba3158b8e2bd82ac6eb5ab54668add224873c2`（#291）。2026-10-02 Human GO 采纳 P1 docs draft（H1=A / H2=A / H6=B）；基线 tip `a93b8112e74e99ba2577bc6fe044e848e072acc5`（#297 后）。表内 vendor 特征以本次只读证据为限，不把单批导出推广成所有接口的保证。

**本表是 bar 身份 / vendor 对齐 SSOT，不是第二套成交默认表。** 入口默认、opt-in、绿 R / 绿 S / 红混比继续 **只链** [minute-fill-policy-ssot.md](../minute-fill-policy-ssot.md)；本表只声明 `minute_label`×`unit`×`time_encoding`×`grid_policy`×`auction_policy` 及 PIN 门槛。复权/止损另见 [行业实践说明](../note-minute-bar-industry-practices-2026-09-26.md)。本表不改 MatchCore / Fees / `simulate` / VolumeCap·clamp·完成桶，不开启 δ5 certified 或 R4，也不授权改写湖。采集、外部下载与 vendor merge 仍属 OSkhQuant1.3，本仓只消费配置的湖。

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
| `unit`（或 volume unit） | lots / raw_shares_incremental，增量或累计；源 at-rest 与输出单位分列；**禁止由数值大小推断 lots/股** |
| `time_encoding` | 原始编码、时区语义、解码规则；是否 local_wall_as_utc_ms |
| `grid_policy` | `sparseA`（省略零量/缺根分钟，须 PIN + 缺根审计）或 `full`（满网断言）；未声明不得静默 fill-forward |
| `auction_policy` | 开盘/午休/收盘竞价行如何排除或纳入（例：`exclude_0930_1130_1500`）；与 `minute_label` 分列，不能凭标签推断 |
| source paths + `sha256` | 原始 vendor 文件与实际湖输入的路径/SHA-256、周期、标的、窗口；输出 artifact 路径/SHA-256；null/通配符不等于已完成逐文件 pin |
| `conversion_rule` / `transformations` | 标签、单位、日线派生、缺根处理的实际转换；源单位与 export/runtime 转换分别记录，不能用 runtime 空数组抹掉 export ×100 |
| `human_acceptance` | 放宽标签/网格时的 Human GO 日期、范围、证据链接；未放宽也显式说明 |
| coverage / cross-check | 样本 OHLCV 对照、竞价/会话、缺根/重复、价格域、异常清单与处置 |

身份勾选（P1-A；研究臂开工前）：`minute_label` × `unit` × `time_encoding` × `grid_policy(sparseA|full)` × `auction_policy` 五元组均已显式 PIN。缺任一字段 = fail-closed（文档合同；loader 码另 GO，见 §11 / [P1 Human defaults](../note-minute-engine-p1-human-defaults-2026-10-02.md)）。示例形状见 [vendor-market-overlay-pin.example.json](./vendor-market-overlay-pin.example.json)。

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

[三票 Phase2 PLAN](../vendor-three-symbol-lake-ingest-2026-10-01/PLAN.md) 与 [adapter CLI](../../../scripts/research/vendor_to_lake_adapter.py) 仅将已接受的 Wind START shares（可选 THS 1d）转换到独立 staging：sparse A、lots（//100 且审计余数）、按 2026-10-02 Human boundary GO 删除 START 09:30 竞价及 11:30/15:00 边界后连续 +1min，`excluded_start_boundary` 在 coverage/PIN/STATUS/REPORT 保留计数与封顶样本；其他越界及排除后无连续 bar 仍 FAIL，纯 xcheck 默认 fail-closed 不变。此 GO 不改变 §7 的 shares overlay，不代表真实三票验收；write-lake 仍需独立 Human GO，CLI 无写湖开关。≠δ5 ≠R4；勿合，等待 Human「合」。

## 10. Phase4 三票入湖 + Phase5 研究路径（lake END）

2026-10-02：三票 `002231.SZ` / `300379.SZ` / `600200.SH` 已按 Phase4 写入湖（`minute_label=END`；at-rest **lots**；sparse A；underscore hive `symbol={002231_SZ,...}`）。证据：`/workspace/handoffs/vendor_lake_adapter_host_20261001/`（写湖 RECEIPT / PIN；xcheck Wind START↔湖 END `volume_scale=100`）。

研究路径可改读 **湖 END+lots → market export ×100→shares**（顶层 PIN `minute_label=END`、`unit=raw_shares_incremental`、`transformations=[]`），其余宇宙 siblings 仍按历史湖导出。稀疏 A 使 tip `run_topk_cap_compare.py` 的 full-grid 门槛 INPUT_BLOCKED；本批用 **host-only lake-accept** 松弛（仅放宽满网断言，保留 END/shares/PIN），不改 tip MatchCore/Fees/`simulate`。

Phase5 宿主证据（box 镜像）：
- 方案：`/workspace/handoffs/vendor_lake_phase5_research_path_20261002/PLAN.md`
- 5.2 market：`D:\exports\vendor_lake_phase5_host_20261002\market_lake_end_20261002130705`（box：`/workspace/handoffs/vendor_lake_phase5_host_20261002/market_lake_end_20261002130705`）
- 5.3 两臂：`D:\exports\vendor_lake_phase5_host_20261002\compare_lake_end_accept_20261002131446`（cap_off ~1.88% / cap_on ~1.07%；`skip_volume_unavailable` cap_on=10）

**START→END 键位移 ⇒ 与 START-accept overlay 的 PnL/收益不可直接回归对比**；本条只记口径变更与指针，不宣称数值回归。≠δ5 certified ≠R4；docs-only；勿合，等待 Human「合」。

## 11. P1 身份合同与研究推荐路径（2026-10-02 Human defaults）

**性质**：P1-A/B docs 增补；**非**第二套 fill-policy SSOT；入口默认/混比继续只链 [minute-fill-policy-ssot.md](../minute-fill-policy-ssot.md)。Human 裁断记录见 [note-minute-engine-p1-human-defaults-2026-10-02.md](../note-minute-engine-p1-human-defaults-2026-10-02.md)。方案来源：`/workspace/handoffs/minute_engine_industry_plan_20261002/PLAN.md` §3.2 + R1/R2。

### 11.1 研究推荐路径（H1=A）

**推荐研究路径**：湖 at-rest **END + lots** → market export **×100 → `raw_shares_incremental`（股）**，顶层 PIN 声明 `minute_label=END`、`unit=raw_shares_incremental`、`time_encoding=…`、`grid_policy=sparseA`（或显式 `full`）、`auction_policy=…`、`transformations=[]`（export 侧 ×100 记入 `conversion_rule`，不得被 runtime 空数组抹掉）。证据指针见 §10 Phase5。

START+sparse overlay（§7）仍可作 **分列研究臂**，但须独立 PIN + `human_acceptance`；**禁止**与湖 END 臂无声明混比 PnL/收益（START→END 键位移）。

### 11.2 Sparse A 与满网（H2=A）

研究臂允许 **sparse A + host lake-accept 类松弛**，且必须 PIN：`grid_policy=sparseA`、缺根审计、Human acceptance 范围。松弛仅放宽满网断言，**不**改 MatchCore / Fees / `simulate` / VolumeCap 公式·clamp·完成桶定义。未 PIN 的静默 fill-forward **禁止**（对照 Lean FF Volume=0 边界见行业 COMPARISON；本仓不默示零量已观测）。

`full` 网格仍为更严门槛（例：tip `run_topk_cap_compare.py` 满网）；sparse 臂不得自称已通过 full-grid 验收。

### 11.3 PIN schema 合同（P1-B · docs；码另 GO）

将 §5 字段落成 fail-closed JSON 身份合同（示例：[vendor-market-overlay-pin.example.json](./vendor-market-overlay-pin.example.json)）：

- 缺 `minute_label` / `unit` / `time_encoding` / `grid_policy` / `auction_policy` / source sha / `conversion_rule`（或等价 transformations 记录）/ `human_acceptance` → **FAIL**（文档验收；实现 loader 另 GO）。
- **拒绝**「由数值大小推断 lots/股」。
- 不发明第二套成交默认，不新增 fill-policy 行号。

### 11.4 硬边界

- ≠δ5 certified ≠R4；不改 MatchCore / Fees / `simulate` / VolumeCap·clamp·完成桶。
- 不写湖；不跑 4090；不把 Phase5 PnL 写成对 START-accept 的回归证明。
- P2 外壳预检与 recipe：见 §12 与 [P2 adapters note](../note-minute-engine-p2-adapters-2026-10-02.md)（H3=B；≠ capacity certified）。

## 12. P2-A host recipe：湖 END+lots → export 股（2026-10-02）

**性质**：把 Phase5 宿主做法固化为可重复 recipe 指针；**不是**第二套 fill-policy；**不是**写湖授权。完整步骤与红线见 [P2 adapters note §2](../note-minute-engine-p2-adapters-2026-10-02.md)。

| 步 | 动作 | 验收 |
|---|---|---|
| 1 | 核对 Phase4 三票 underscore 湖 sha | 与 Phase4 RECEIPT 一致；拒 dotted hive |
| 2 | 新建 `market_lake_end_*` 根（勿覆盖 START overlay） | 独立 out-dir |
| 3 | 湖 lots → 整数 ×100 → `raw_shares_incremental`；键保持 END | PIN `conversion_rule.export` 记录 ×100 |
| 4 | PIN：五元组 + `source_lake_pins` 逐文件 sha + `human_acceptance.no_pnl_mix_with_START_overlay=true` | 示例 [vendor-market-overlay-pin.example.json](./vendor-market-overlay-pin.example.json) |
| 5 | （可选）两臂：`cap_off=None` / `cap_on=rate`；sparse 用 host lake-accept **仅**松弛满网 | tip 满网脚手架遇 sparse → INPUT_BLOCKED 为预期 |

**证据**：§10 Phase5 host `/workspace/handoffs/vendor_lake_phase5_host_20261002/`（`market_lake_end_20261002130705/PIN.json`、`RECEIPT.md`）。

**红线**：START→END 键位移 ⇒ **禁止**与 START-accept overlay 直接比 PnL/收益。≠δ5 certified ≠R4；不改 MatchCore/Fees/`simulate`/VolumeCap。
