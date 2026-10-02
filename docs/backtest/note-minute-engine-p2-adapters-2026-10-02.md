# 分钟引擎 P2 · Research adapters（recipe / 预检 / L2 边界）· 2026-10-02

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip base | `4a38a6459da6e715c231b2761e9b7a9554d52322`（master · #298 P1 合入后） |
| Human GO | P2-A + P2-B + P2-C；H1=A / H2=A / H3=B / H4=A / H5=A / H6=B |
| 方案 | `/workspace/handoffs/minute_engine_industry_plan_20261002/PLAN.md` §3.3 + G2 |
| 硬约束 | **不改** MatchCore / Fees / `simulate` / VolumeCap 公式·clamp·完成桶定义；≠δ5 certified ≠R4；无写湖；无 4090；**勿合，等待 Human「合」** |

> **本 note ≠ 第二套成交默认表。** 入口默认 / 绿 R·S / 红混比继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。Bar 身份继续只链 [vendor-bar-alignment-ssot.md](ssot/vendor-bar-alignment-ssot.md)。P1 Human defaults：[note-minute-engine-p1-human-defaults-2026-10-02.md](note-minute-engine-p1-human-defaults-2026-10-02.md)。

## 1. 范围

| 刀 | 本 PR | 明确不做 |
|---|---|---|
| **P2-A** | 湖 END+lots → export 股 的可重复 host recipe（§2；vendor-bar §12） | 不写湖；不把 PnL 与 START-accept 回归对比 |
| **P2-B** | 单位 + 完成桶外壳预检产品化（§3；`participation_rate_precheck.py`） | 不改 `simulate` / MatchCore / Fees / VolumeCap·clamp·桶定义；≠ capacity certified |
| **P2-C** | L2 `source_loader` ↔ 共享湖读取边界对照表（§4） | 不把 MatchCore 研究后端接成默认 CSV 替换 |
| P2-D | （可选）跳过 | δ6 事件 loader |
| P3 / G3 | 不做 | 科创板申报数量（H5=A）；竞价模型 |

## 2. P2-A — 湖 END+lots → export shares host recipe

**推荐研究路径（H1=A）**：湖 at-rest `minute_label=END` + volume **lots** → market overlay export **整数 ×100** → `unit=raw_shares_incremental`（股）。顶层 PIN 必须声明身份五元组 + `conversion_rule`（export ×100 不得被 runtime `transformations=[]` 抹掉）。

### 2.1 可重复步骤（host；tip 码不写湖）

1. **核对 Phase4 湖 sha**（underscore hive）：三票 `002231_SZ` / `300379_SZ` / `600200_SH` 的 `period={1m,1d}` `data.parquet` 与 Phase4 RECEIPT 一致。
2. **新建 export 根**（勿覆盖旧 START overlay）：例如 `market_lake_end_<yyyymmddHHMMSS>/`。
3. **导出**：三票及 siblings 湖 lots → `volume_shares = lake_lots * 100`（整数）；时间键保持湖 END（`local_wall_as_utc_ms`）；sparse A **不造根**。
4. **写 PIN**：形状见 [vendor-market-overlay-pin.example.json](ssot/vendor-market-overlay-pin.example.json)；必含 `minute_label=END`、`unit=raw_shares_incremental`、`grid_policy`、`conversion_rule`、`source_lake_pins`（逐文件 path+sha，禁止通配 null）、`human_acceptance.no_pnl_mix_with_START_overlay=true`。
5. **跑两臂**（可选）：`run_topk_cap_compare` 满网门槛遇 sparse 会 `INPUT_BLOCKED`；Phase5 用 **host-only lake-accept** 仅松弛满网断言，保留 END/shares/PIN。`cap_off`=`participation_rate=None`；`cap_on`=显式 rate。

### 2.2 证据指针（Phase5）

| 项 | 路径 |
|---|---|
| 方案 | `/workspace/handoffs/vendor_lake_phase5_research_path_20261002/PLAN.md` |
| Host RECEIPT | `/workspace/handoffs/vendor_lake_phase5_host_20261002/RECEIPT.md` |
| Market export 镜像 | `/workspace/handoffs/vendor_lake_phase5_host_20261002/market_lake_end_20261002130705/`（含 `PIN.json`） |
| 两臂对照 | `…/compare_lake_end_accept_20261002131446` |
| 仓内摘要 | [vendor-three-symbol PLAN Phase5](vendor-three-symbol-lake-ingest-2026-10-01/PLAN.md)；[vendor-bar §10/§12](ssot/vendor-bar-alignment-ssot.md) |

### 2.3 红线

**START→END 键位移 ⇒ 禁止把本 recipe 的 PnL/收益与 START-accept overlay 直接回归对比。** 两臂只作并列口径，不作数值回归证明。≠δ5 certified ≠R4。

## 3. P2-B — 单位 + 完成桶外壳预检（H3=B）

模块：[`backtest/research/participation_rate_precheck.py`](../../backtest/research/participation_rate_precheck.py)

| 入口 | 调用 | 行为 |
|---|---|---|
| 共享 CLI `csv_minute_backtest.main` | `precheck_cli_participation_rate`（parse 后） | rate=None → **no-op**；rate 设定时 fail-closed 校验 lake/shares 域 |
| 共享 `run()` facade | 同上 + loader 出口 `precheck_completed_bucket_samples` | 不进入 `simulate` 热路径改语义 |
| `run_topk_cap_compare.read_bars` | `precheck_source_pin_unit` + `precheck_completed_bucket_samples` | PIN unit；完成桶 hm/unit 断言 |

### 3.1 做什么 / 不做什么

| 做 | 不做 |
|---|---|
| 校验 rate∈[0,1]；cap-on 要求 raw lake shares（禁 qlib_1min / front / tail lots） | 改 VolumeCap 公式 / `clamp` 整手 / 完成桶 hm 定义 |
| 断言 PIN `unit=raw_shares_incremental` 且 `transformations=[]` | 改 MatchCore / Fees / `simulate` |
| 断言 samples 仅落在连续完成桶 hm，且 `BucketVolume.unit` 正确 | 发明缺根；静默 fill-forward |
| 刀文 / help：**≠δ5 certified ≠R4**；禁读成 capacity certified | 开启 δ5 certified / R4 / 真实量认证 |

**省略 `participation_rate=None` = 旧臂字节合同保持**（本层 no-op；共享 CLI 仍不把 rate 键传入 `run`）。

验收标签：**≠δ5 certified ≠R4**。

## 4. P2-C — L2 `source_loader` ↔ 共享湖读取边界

详见 [L1/L2 边界 note §6](note-l1-l2-research-engine-boundary-2026-09-28.md#6-p2-c-l2-sourceloader--共享湖读取边界对照2026-10-02)。摘要：

| 面 | 共享 CSV / lake export 路径 | L2 `minute_orders` `source_loader` |
|---|---|---|
| 角色 | 主研究路径；`csv_minute_backtest` / TopK scaffold | **永 opt-in** 对照后端（H4=A）；显式 recipe+attestation |
| 读取 | host market parquet 或 `ashare_bars` 湖读 → shares PIN | `load_minute_orders_source(recipe)` → `RunInput`；独立 provenance |
| 撮合 | 共享 `simulate` + 可选 VolumeCap | L2 MatchCore（研究合同）；**不是**默认 CSV 替换 |
| 同 PIN 不同后端 | — | **红混比**（不得绿 R NAV 并排） |

同 facade 返回类型 ≠ 可绿 R。MatchCore 研究后端 **禁止**被误读成默认 CSV / 共享湖 loader 的替换品。

## 5. 冻结清单（合入前自检）

- [ ] 无 MatchCore / Fees / `simulate` / VolumeCap·clamp·完成桶定义 diff
- [ ] `participation_rate=None` 省略臂行为未变
- [ ] 刀文 / PR / help 含 **≠δ5 certified ≠R4**；无「capacity certified」
- [ ] 无写湖；无 4090 跑数；无 G3 科创板申报表
- [ ] 无第二套 fill-policy SSOT
- [ ] Draft PR；**勿合，等待 Human「合」**
