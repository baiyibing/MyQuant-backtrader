# B-L2-01：R3 BLOCKED 后的证据采集（host-assist）与 R4 材料地图

2026-09-30 · **docs-only**（证据登记，不改代码/模板/默认值）· 基线 `a268e11`（#270 后）。
关联：[#266 合同](note-l2-lake-source-ingress-b-l2-01-2026-09-29.md)（§9/§9.5）、
[#268 loader](note-l2-lake-source-ingress-b-l2-01-2026-09-29.md#7-item-3-实现接口与证据版本2026-09-30)、
[#269 schema-adapt](note-l2-lake-source-ingress-b-l2-01-2026-09-29.md#8-schema-adapt与事实-sidecar2026-09-30)、
[#270 模板](../tests/fixtures/minute_orders_source_attestation/README.md)。
**本片不解除 R3 `BLOCKED/NOT_RUN`，不填任何模板，不构成 host certification / lake PASS /
SSOT 结论；R4 发车仍需具名 Human GO（§9.5 第 7 条）。PR 不自动合并。**

## 1. 来龙去脉（时间线）

1. **R2**（`47abe4d`，2026-09-30 早）：4090 live 首探 `BLOCKED/NOT_RUN`——三门缺材料
   （量单位声明 / instrument tick·lot·reference·limit 事实 / halt·missing 分钟网格）。
2. **#270**（`a268e11`）：仓内登记三门 host-fillable 空模板 + basis/binding 收紧
   （`bl2_proof_v1` 六字段；units=`source_declaration`、instruments=`source_fact|approved_derivation`、
   status=`explicit_status`）；模板原样加载必须失败。
3. **R3**（2026-09-30 10:57 +08:00，newtest_4090，tip `a268e11`，transform
   `bl2_source_transform_v3`）：重跑仍 `BLOCKED/NOT_RUN`，与 R2 同三缺。收据
   [b-l2-01-evidence-2026-09-30/HOST_B_L2_01_R3.md](b-l2-01-evidence-2026-09-30/HOST_B_L2_01_R3.md)；
   宿主根 `D:\exports\b_l2_01_4090_r3_20260930\`，box 镜像
   `/workspace/handoffs/b_l2_4090_live_r3_20260930/`。
4. **宿主对话**：R3 后结论是「不是改代码，也不是再扫一遍湖；要补湖外权威原材料」。
   Human 决定「我补证据，再开 R4」，但不知道去哪补；随后给出采集指针：
   兄弟仓（MyQuant / OSkhQuant1.3）、湖↔qlib 对比、QMT 下载规范（湖数据源自 QMT）、
   1.3 涨跌停实现、互联网规则新政。
5. **本片（host-assist 采集，2026-09-30 下午）**：在 4090 宿主机（湖本地可见）上对
   1.3 / MyQuant / 本仓 / xtquant 安装包（`250516.1.1`）/ 湖本体 / 公开网络做一轮只读取证，
   六包原材料 + 材料地图落盘；**Human 指示证据全部入库**（不再只放仓外），即
   [b-l2-01-evidence-2026-09-30/](b-l2-01-evidence-2026-09-30/)（逐字节副本，hash 见该目录 README）。
6. **PR #272 评审跟进（2026-09-30 午）**：评审 agent 用两个**独立公开行情源**
   （腾讯 ifzq / 新浪 K线 API，湖外、非 QMT 链路）对湖日线做交叉核对，结论封成第七包
   `raw_excerpt_crossvendor_daily_603196SH.json`（附离线自检器
   `check_crossvendor_daily.py`），Human 指示补进本 PR。仍是 NON-ATTESTATION 旁证（§9.2）。

## 2. 三门的取证结果

### 2.1 量单位（units）——仍缺声明，但「缺失」本身已有证据

- xtquant `250516.1.1` 包内官方文档逐字段核验：**K线（1m/5m/1d）字段表对 `volume`
  无单位注记**（只写「成交量」）；有单位注记的是别的域——l2quote 委买卖量「单位是手」、
  xttrader 委托量「股票以股为单位」、发行类字段「单位：股」。行式摘录（原件 sha256 一并 pin）：
  `raw_materials/raw_excerpt_xtquant_docs.json`。
- 1.3 写湖链路（`oskh_data/download_transport.py` L468–486）：`get_market_data_ex` 仅取
  7 列、`fill_data=True`、**无任何单位换算**——湖 volume 即 QMT 原值。
- 湖↔qlib 旁证：MyQuant `qlib_scripts/stage_1min_from_lake.py` L96 以 `vol*100` 作 vwap
  分母（消费侧按「手」假设）；R3 探针比率 mean=99.98。**两者均按 §9.2 定性
  NON-ATTESTATION，只能进 limitations/佐证，不能当 source_declaration。**
- 跨 vendor 旁证（第七包）：湖日线 volume 与腾讯 ifzq（手口径）**13/13 天完全相等**；
  新浪（股口径）÷ 湖 = 恰好 100 的有 12/13 天，唯一例外 2025-10-23 差 −41 股（**零股**）——
  R3 探针比率 mean≈99.98 而非 100 由此得到实质解释（真实成交含零股，「手」口径聚合取整，
  不是数据错误）。分钟级三源均不可回溯（1m 历史只留近期），此观察仅限日线。
  东财交互查询曾三方一致（含 amount、preKPrice=23.04），但补包重抓被服务端断连，
  未 pin 原件，不纳入。仍 NON-ATTESTATION。
- 剩余路径（材料地图 R4-B）：① host 浏览器取迅投官方文档站
  `dict.thtrader.com/nativeApi/xtquant.html`（本机 DNS EAI_AGAIN）；
  ② 国金 miniQMT 客户端内置帮助；③ 国金书面口径；④ 都拿不到则 units 门保持 BLOCKED。

### 2.2 涨跌停 / lot（instruments）——approved_derivation 材料已可成包

- 规则（公开来源已确认公式原文）：**涨跌幅价格 = 前收盘价 ×（1±比例），四舍五入至最小
  变动单位 0.01 元**；主板 ±10%。窗口（2025-10）适用 2023 修订版；**2026-04-24 沪深北
  修订交易规则、2026-07-06 起主板 ST 5%→10%**，窗口早于新政且 603196.SH 非 ST，不受影响
  （见 `raw_materials/web_rule_references_20260930.md`；host 需存档规则全文并补
  「0.01 最小变动」「lot 100 申报单位」条款原文）。
- 1.3 实现（旁证）：`oskh_core/board_limit.py`（板块率 SSOT：主板 0.10 / 创业·科创 0.20 /
  北交 0.30）+ `qmt_xtdata_mock.py::_get_limit_rate/_limit_prices`（前收盘×(1±率) round 0.01；
  live 侧由柜台真实涨跌停价兜底）。
- 本仓对应：[`backtest/research/ashare_session.py`](../../backtest/research/ashare_session.py)。
- 推导输入（湖日线原行，`raw_lake_daily_603196SH_20251020_20251105.json`）+ 前置事实
  （非 ST + 窗口零除权，两包 raw 材料）已齐；独立核验内容：每日 high≤limit_up、
  low≥limit_down 可由日线复算。**双 issuer（host + 独立核验者）人选与规则版本批准
  仍是 host 责任**。更强的 source_fact 路线（vendor `preClose`）见 §2.3 的 R4-A。
- 规则复算旁证（第七包）：以腾讯 2025-10-17 收盘为前收锚点，按「×(1±10%) 四舍五入至
  0.01」逐日（13 天）复算 limit_up/limit_down，湖日线 high/low **零违例**——经验层面
  corroborate approved_derivation 的规则公式与窗口适用性，但不替代规则全文存档与
  双 issuer 批准。

### 2.3 halt / missing（status）——网格事实已定，缺一格 vendor 停牌事实源

对湖 `stock/period=1m/dividend_type=none/symbol=603196_SH/data.parquet` 窗口全量复算
（`raw_lake_minute_census_603196SH_20251023_20251104.json`，2169 行逐格含 row_idx）：

- **时间语义（§3.1 材料）**：`time:int64` = 上海墙钟按 UTC epoch 毫秒编码
  （`1761211800000` → 上海墙钟 2025-10-23 09:30；R3 探针同解读）；bar 为 **END 标签**
  （标签 t 覆盖 [t−1min, t)）；每日 241 行 = 09:30 集合竞价条 + 09:31–11:30 + 13:01–15:00。
- **网格**：合同可交易网格（END 标签 09:31–11:30 + 13:01–14:57 = 237 格/日 × 9 日）
  **2133/2133 全有行、零缺格、零重复**——`missing=false` 逐格可证（proof 行可引湖 parquet
  row_idx）；每日 4 条网格外行（09:30/14:58/14:59/15:00），15:00 行可作 mark（§7）。
- **零量格 46 个**（40/46 close=前值，符合 vendor `fill_data` 对齐填充或真实无成交特征）；
  其余 2087 格 volume>0——当分钟有成交即「未停牌」的积极证据。
  仍缺：覆盖 9 个交易日的 **vendor 显式停牌事实**（`suspendFlag`）。xtquant K线字段表含
  `suspendFlag`（0 正常/1 停牌/-1 当日起复牌）与 `preClose`，但 1.3 落湖只取 7 列未包含。
- **R4-A（一次 QMT 全字段回补，最划算）**：在装有国金 miniQMT 的机器对 603196.SH
  20251020–20251105 跑 `download_history_data2` + `get_market_data_ex`（字段
  time/close/volume/preClose/suspendFlag，1d+1m），一次同时补齐 status 门 vendor 停牌标记
  与 instruments 门 vendor 前收价（source_fact 路线）。脚本骨架见
  [b-l2-01-evidence-2026-09-30/HOST_MATERIALS_MAP_R4.md](b-l2-01-evidence-2026-09-30/HOST_MATERIALS_MAP_R4.md) §3。

## 3. 文档关联（跨文档索引）

| 节点 | 位置 | 本片动作 |
|---|---|---|
| ingress 合同 §9/§9.5 | [note-l2-lake-source-ingress-b-l2-01-2026-09-29.md](note-l2-lake-source-ingress-b-l2-01-2026-09-29.md) | 追加 §10 指针指回本片 |
| #270 模板 README | [tests/fixtures/minute_orders_source_attestation/README.md](../tests/fixtures/minute_orders_source_attestation/README.md) | 加一行指向证据包 |
| R3 收据（仓外原件） | `D:\exports\b_l2_01_4090_r3_20260930\HOST_B_L2_01_R3.md` · box `/workspace/handoffs/b_l2_4090_live_r3_20260930/` | 逐字节入库 `b-l2-01-evidence-2026-09-30/` |
| R3 探针摘要/驱动/ hashes | 同上宿主根 `probe_summary.json` · `_run_b_l2_01_r3.py` · `artifact_hashes.json` | 同上 |
| R4 材料地图 | `b-l2-01-evidence-2026-09-30/HOST_MATERIALS_MAP_R4.md`（宿主 `evidence\` 同名原件） | 入库；行动清单 R4-A/B/C/D |
| 六包原材料 | `b-l2-01-evidence-2026-09-30/raw_materials/` | 入库；封套 `bl2_raw_excerpt_draft_v0_host_review` |
| 第七包（评审跟进） | `raw_materials/raw_excerpt_crossvendor_daily_603196SH.json` + `check_crossvendor_daily.py` | 湖日线 vs 腾讯/新浪双源对照、涨跌停复算零违例、零股解释；NON-ATTESTATION |
| 生成器 | `b-l2-01-evidence-2026-09-30/gen_raw_materials.py` | 入库（含宿主路径，故置 docs/ 不进代码树） |
| 1.3 锚点 | `OSkhQuant1.3@47afc24`：`oskh_core/board_limit.py` · `common/integrations/qmt_xtdata_mock.py`（`_get_limit_rate`/`_limit_prices`）· `oskh_data/download_transport.py` | 跨仓引用（非本仓文件），摘录已 pin |
| MyQuant 锚点 | `MyQuant@910abd3`：`qlib_scripts/stage_1min_from_lake.py` | 跨仓引用；NON-ATTESTATION 旁证 |
| xtquant 包 | `250516.1.1`（vanna312 site-packages），`doc/xtdata.md` · `xtdata.py` · `doc/xttrader.md` | 行式摘录 + 原件 sha256 已 pin |
| 规则公开来源 | `raw_materials/web_rule_references_20260930.md` | host 存档全文后升级为 rule 材料 |

## 4. 其他机器 agent 的核对清单（复算命令）

以下在本仓根、湖可达（`OSKH_SOURCE_PARQUET_ROOT=E:\stock_data` 或等价）时可复算；
输出应与 `raw_lake_minute_census_…json` 一致（该包 `source.sha256` 为湖分区原文件 hash）：

```bash
# 门禁（data-free，与 CI 相同）
python scripts/gates/verify_oskh_data_contract.py
python scripts/gates/verify_data_path_ssot.py
python scripts/gates/verify_no_hardcoded_machine_paths.py
python scripts/gates/verify_tr_bridge_import_ssot.py

# 证据包自检（逐字节重生成 → sha256 对 README 表）
python docs/backtest/b-l2-01-evidence-2026-09-30/gen_raw_materials.py

# 第七包离线自检（无网络，重算三源对照/涨跌停/零股）
python docs/backtest/b-l2-01-evidence-2026-09-30/check_crossvendor_daily.py
```

核对要点：① census 的 `grid_cells=2133 / grid_missing=0 / zero_volume_grid_cells=46`；
② `raw_excerpt_xtquant_docs.json` 中 K线字段表原文确无 volume 单位注记；
③ 跨仓摘录与所引 HEAD 的文件 hash 一致；④ R3 收据 verdict 仍为 `BLOCKED/NOT_RUN`；
⑤ 第七包：13 天 × (OHLC 三源一致 + 湖==腾讯 volume)、涨跌停复算 0 违例、
新浪=100×湖 12/13 天且 2025-10-23 零股 −41 股。

## 5. 非声明与边界

- 本片是**材料登记**：六包 raw 是草稿摘录，不是 `bl2_proof_v1`；没有 issuer 签发、
  没有规则版本批准、没有双 issuer 推导核验。
- R3 `BLOCKED/NOT_RUN` 原样；freeze / native↔L1 / oracles 未跑；湖 / SSOT / δ5 / JR G 未动。
- units 门：**没有任何新证据支持把手启发式升级为声明**；第七包的跨 vendor 一致性
  （湖=腾讯=新浪）同样是经验旁证而非 xtquant 官方 source_declaration；若 R4-B 三条路径都取不到，
  units 保持 BLOCKED，不硬开 R4。
- `gen_raw_materials.py` 含宿主绝对路径，属 pinned provenance，刻意不入代码树；
  生产代码仍必须走 resolver（AGENTS 数据盘纪律不变）。
- R4 发车 = 另一条具名 Human GO；本 PR 打开后待 Human「合」，不自动合并。
