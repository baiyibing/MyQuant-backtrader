# corp-actions 双通道取数方案（wind 保留 + hithink 新增）— 2026-10-29

状态：**提案待评审**。评审通过前不动实现代码。本 PR 只含本文档。

## 1. 背景

- corp-actions 增量（窗口 2026-10-07 → 2026-10-28，2774 码）被 kimi-datasource wind 后端间歇性 401 阻断，详见 [#523](https://github.com/baiyibing/MyQuant-backtrader/pull/523) 与 [状态文档](corp-actions-incremental-20261028-status.md)。换机实验已证伪本机因素，401 在服务端。
- 2026-10-29 对同花顺官方数据服务 **hithink-finance**（[HiThink-Tech/Financial-API](https://github.com/HiThink-Tech/Financial-API)，`fuyao.aicubes.cn`）做了真实 API Key 探针 + 与 wind 冻结 base（`bt_corp_actions_20261006`，21779 事件 / 2693 码）全量对拍，结论：**可作为 wind 的并行取数通道**（对拍证据见 §7）。

## 2. 目标 / 非目标

### 目标

1. `pull_corp_actions_incremental.py` 取数层引入**通道（channel）抽象**：`wind`（现有 LLM 会话驱动，原样保留）与 `hithink`（直连 REST 全量 dump，无 LLM）。
2. hithink 通道一次 dump 覆盖全 universe，替代逐码 LLM 会话的 463 任务模型；天然免疫 wind 401 与 LLM 会话抖动。
3. 已冻结的 wind run（`bt_corp_actions_incr_20261024` / `_20261028`）续跑能力**不受影响**，wind 恢复后可直接续跑并对 hithink 结果交叉验证。
4. hithink 已知缺口（退市码、重整转增）以**显式排除清单**形式冻结，fail-closed，不静默吞掉。

### 非目标

- 不删除或改动 wind 通道任何现有行为（prompt、任务拆分、attempt/quota 语义、assemble 证据链）。
- 不动湖 schema（`EVENT_SCHEMA` 10 列不变）、不动 `prepare-merge` 的"只出候选、永不 apply"语义。
- 不回填历史：hithink dump 含 1991 年以来深历史，本方案只取 run 窗口内事件；历史回填如需另行 GO。
- 不配股入湖：hithink dump 含配股（allotment），wind base 无对应列，本方案落 sidecar 不消费。

## 3. 现状架构锚点

`scripts/data/pull_corp_actions_incremental.py`（670 行，单文件）：

- `initialize()`（:185）：冻结 `run.json`（out/lake/universe sha256、窗口、`model`、codes、protected_roots）；任务 = 6 码一组的 `ev_NNNN`。
- `pull()`（:371）：kimi CLI 会话循环；`prompt_for()` 限定只用 kimi-datasource wind（:236）；`accept_result()` 校验行数/拆分/no-data（:320）；attempt 分 quota/infra/skipped/error（:356）。
- `assemble()`（:484）：走 accepted 证据链（raw sha256 + 会话日志 sha256），`normalize_event()` 要求 `progress=="实施完毕"` 且 `record_date` 非空（:449），`natural_key` 去重，event_id = `{code}_{yyyymmdd}_incr_{sha20}`（:525）。
- `prepare_merge()`（:561）：base 校验 + event_id 碰撞检查 + 候选落 `merge-prep/` + `manifest-patch-plan.json`；**无 apply 命令**，发布须单独 Human GO。
- `Run.__init__`（:132）：校验 `config["model"] in MODELS`、out_dir 未移动。

## 4. 设计

### 4.1 通道抽象

- `run.json` 新增冻结字段 `channel: "wind" | "hithink"`，init 时经 `--channel` 指定，**缺省/缺字段 = `wind`**（旧 run.json 无此字段，向后兼容，已冻结 run 零改动）。
- `Run.__init__`：`channel` 缺省视为 wind；wind 通道维持 `model in MODELS` 校验；hithink 通道不要求 `model`（init 时 `--model` 与 `--channel hithink` 同传即报错）。
- `main()` 的 init-only 参数冻结检查（:646）把 `channel` 一并纳入"只能在 init 设置"。

### 4.2 hithink 通道取数（pull）

无 LLM、无任务拆分、无 attempt/quota 概念。一次 `pull` 是**原子单发**：

1. `GET /api/dump/market-dumps/adjustment-factors/download-url`（Header `X-api-key`）→ 取 S3 预签名 URL（约 5 分钟有效，拿到立刻下载）。
2. 下载全市场复权事件 Parquet（约 5.2 万行 / 5435 码 / <1 MB）→ `raw_events/hithink_dump.parquet`（原子写，沿用 `Run.write` 的 tmp+rename）。
3. 校验：pyarrow 可读、必需列齐全（`thscode, ex_date_ms, dividend_per_share, per_share_bonus, allotment_ratio, allotment_price`）、`(thscode, ex_date_ms)` 重复行 ≤ 人工阈值并记入状态（实测全市场仅 3 码 6 行重复，为同日分红+送股并行，合法）。
4. 状态写 `work/hithink_state.json`：`dump_sha256`、`fetched_at`、`dump_rows`、`universe_hits`（universe ∩ dump 且窗口内）、`codes_no_events`（dump 有该码但窗口内无事件）、`codes_vendor_unknown`（universe 中 dump 完全不存在的码）。
5. 幂等/续跑：已存在 dump 且无 `--refresh` 时 `pull` 直接报告现状退出 0；`--refresh` 仅在 `assemble` 未消费过旧 dump 前允许（已 assemble 的 dump sha256 被证据链钉住，换 dump 即校验失败，fail-closed）。
- HTTP 走 stdlib `urllib`，不引新依赖。失败（HTTP 非 200 / `code != 0` / 下载或 parquet 校验失败）= 整体失败，退出码 2，无部分状态。

**API Key**：仅从环境变量 `HITHINK_FINANCE_API_KEY` 读取；缺失即报错。禁止写入 run.json / tasks / 日志 / 文档 / git。runbook 中注明 Key 轮换入口在 `fuyao.aicubes.cn/admin`。

### 4.3 hithink 通道 assemble

`assemble()` 按 `config["channel"]` 分支；wind 分支原样。hithink 分支：

- 证据 = dump parquet 本身（sha256 钉在 hithink_state 与 summary 里），无会话日志链。
- 字段映射（→ `EVENT_SCHEMA`）：

| 湖列 | hithink 来源 | 说明 |
|---|---|---|
| `code` | `thscode` | 过 `wind_code()` 同一校验 |
| `ex_date` | `ex_date_ms` | Asia/Shanghai 零点 → date32 |
| `cash_div_per_share` | `dividend_per_share` | decimal128(24,12)，过 `decimal_value()` |
| `bonus_ratio` | `per_share_bonus` | **送转合并口径**：hithink 不分列送/转 |
| `transfer_ratio` | — | 恒 None（口径差异写入 review_requirements） |
| `record_date` / `pay_date` / `bonus_list_date` | — | 恒 None（hithink 不提供） |
| `source` | 字面量 | `hithink:market-dumps/adjustment-factors` |
| `event_id` | 同 wind 规则 | `natural_key` + `_incr_` + sha20，跨通道同事件同 id |

- 窗口过滤：`start ≤ ex_date ≤ end`；窗口外事件（含已宣告未除权的未来事件）不计入、不写 rejected（dump 是全量快照，下次 run 自然再捡到）。
- 配股行（`allotment_ratio > 0`）：不映射进 events，落 `assembled/hithink_allotments.csv` sidecar + 计数进 summary。
- 同日多行（分红/送股分行）：沿用现有 `natural_key` 合并语义；同键字段冲突照抛。
- 覆盖断言（prepare-merge 同款语义）：`universe_hits ∪ codes_no_events ∪ exclusion.delisted_codes` 必须 == universe；`codes_vendor_unknown` 中有不在排除清单的码 → **fail-closed 报错**。
- `summary.json` 增 `"channel": "hithink"`、`dump_sha256`、`hithink_allotment_rows`；`coverage_is_vendor_query_only` 保留为 True（dump 同样是 vendor 口径快照）。

### 4.4 排除清单（缺口冻结，人工维护）

新文件 `config/corp_actions_hithink_exclusions.json`（用 JSON，不引 yaml 依赖）：

```json
{
  "delisted_codes": ["000016.SZ", "002231.SZ", "002731.SZ", "002898.SZ", "300379.SZ", "600200.SH", "601198.SH"],
  "known_restructuring_transfer_gap": ["601777.SH", "002251.SZ", "002321.SZ", "..."],
  "known_cash_discrepancy": ["600989.SH", "600025.SH", "600900.SH", "301057.SZ"],
  "notes": "hithink 代码表只收在交易标的；重整/债务重组转增不在其分红送转口径；现金不符见 §7 对拍"
}
```

- `delisted_codes`：hithink 通道允许 `codes_vendor_unknown` 的唯一白名单；这些码的事件**继续由 wind base 存量承载**，wind 恢复后可对这 7 码走 wind 通道单独增量。
- 后两组只用于对拍 gate 的容差名单与人工核对追踪，不影响 assemble。

### 4.5 对拍 gate（手动，不进 CI）

`scripts/gates/verify_corp_actions_hithink_parity.py`（需网络 + Key，手动跑，非 CI data-free gate）：

- 输入：hithink dump + base `events.parquet` + 排除清单。
- 断言（阈值随首跑实测值冻结）：共同 (code, ex_date) 键 cash 一致率 ≥ 99.9%、bonus 一致率 ≥ 99.8%；`仅 wind 有` 的键 ⊆ `delisted_codes` × 任意日期。
- 输出 markdown 报告；阈值破坏即非零退出，触发人工逐案核对（清单该扩容还是数据该质疑，由人裁）。

### 4.6 manifest-patch-plan 增补

hithink 通道候选的 `review_requirements` 追加：

- "hithink 行 record_date/pay_date/bonus_list_date 为 NULL、transfer_ratio 并入 bonus_ratio；下游消费前确认容忍。"
- "hithink 不覆盖已退市标的；delisted_codes 内事件仍来自 wind base 存量。"
- "重整/债务重组转增不在 hithink 口径；见 exclusions 清单。"

## 5. 实施步骤（评审通过后）

1. **PR-A（实现）**：`pull_corp_actions_incremental.py` 加 `--channel` / hithink pull / assemble 分支 / 覆盖断言；`config/corp_actions_hithink_exclusions.json`；`tests/test_corp_actions_hithink_channel.py`（合成 dump 夹具，data-free：字段映射、窗口过滤、同日多行合并、event_id 稳定、未知码 fail-closed、旧 wind run.json 无 channel 字段可加载）；`scripts/gates/verify_corp_actions_hithink_parity.py`；runbook `corp-actions-incremental-driver.md` 增补 hithink 章节。
2. **首跑（人裁 GO 后）**：`init --channel hithink` 新 run-dir `D:\exports\bt_corp_actions_incr_20261028_hithink`（窗口 10-07→10-28，与 wind 冻结 run 同窗便于对照）→ `pull` → `assemble` → `prepare-merge`（不 apply）→ 人工审 `manifest-patch-plan.json`。
3. **交叉验证**：parity gate 重跑；wind 恢复后同窗 wind run 续跑，两候选 diff（expect：hithink ⊇ wind，差异 ⊆ 排除清单解释范围）。
4. **发布**：沿用既有"单独 Human GO + owner 侧 publisher"流程，本驱动永不 apply。

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| API Key 授权范围变化 / 服务限流 | pull 原子失败即整体失败，无部分状态；Key 走 env，轮换不落盘 |
| dump 是全量快照、历史可被上游修订 | 每次 dump 原始 parquet + sha256 留档进证据链；跨日 diff 由 parity gate 盯 |
| 口径差异（送转合并、缺 record_date）污染下游 | source 列区分通道；review_requirements 显式声明；null_counts 进 summary |
| 跨通道重复合并 | event_id 同规则 + prepare-merge 既有碰撞检查 fail-closed |
| hithink 端点契约变更 | 必需列校验 fail-closed；契约以 `fuyao.aicubes.cn/llms-full.txt` 为准，runbook 注明 |

## 7. 对拍证据（2026-10-29 探针，真实 Key）

- dump：57,700 行 / 5,435 码，ex_date 1991-02 → 2026-11-05（含已宣告未除权）。
- 覆盖：universe 2774 码中 2,756 码有事件；wind 有事件的 2,693 码中 hithink 覆盖 2,686，**缺 7 码**（全部查无 thscode = 退市/被吸收合并，hithink 代码表只收在交易标的）。
- 事件键（code, ex_date）：共同 21,709 / wind 21,758（99.77%）；仅 wind 有的 49 键全部属于上述 7 码。
- 字段一致率（共同键）：cash 21,699/21,709 = 99.95%（10 处不符，多为 600989 宝丰能源特别分红合并口径）；bonus 21,673/21,709 = 99.83%（36 处不符，几乎全是破产重整/债务重组转增，wind 记录而 hithink 口径不含）。
- 增量窗口 2026-10-07 → 10-28：hithink 已有 **162 事件 / 162 码**，被 wind 401 卡住的数据当前可得。
- hithink 额外多 11,887 键：wind base 窗口自 2014 起，hithink 深历史更早（本方案不消费）。
- 探针产物（本机未入库）：`_tmp_hithink_probe/`（dump parquet + 对拍脚本 + 输出）。

## 8. 评审关注点

1. 通道抽象与 run.json 冻结语义的兼容性（旧 run 零改动）是否成立。
2. 排除清单 fail-closed 边界是否够严（`codes_vendor_unknown` 只允许白名单）。
3. 送转合并口径 / record_date 置空对下游消费方（复权计算、回测 economics 路径）的影响是否可接受。
4. Key 管理与轮换流程是否合规。
