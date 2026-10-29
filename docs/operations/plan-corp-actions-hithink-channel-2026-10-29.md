# corp-actions 双通道取数方案（wind 保留 + hithink 新增）— 2026-10-29

状态：**提案待评审**（2026-10-29 评审修订 v4：复审三条收口，变更记录见 §9）。评审通过前不动实现代码。本 PR 只含方案文档 + 一份非本方案范围的 [hithink 湖补强 backlog](hithink-lake-supplement-backlog-2026-10-29.md)。

## 1. 背景

- corp-actions 增量（窗口 2026-10-07 → 2026-10-28，2774 码）被 kimi-datasource wind 后端间歇性 401 阻断，详见 [#523](https://github.com/baiyibing/MyQuant-backtrader/pull/523) 与 [状态文档](corp-actions-incremental-20261028-status.md)。换机实验已证伪本机因素，401 在服务端。
- 2026-10-29 对同花顺官方数据服务 **hithink-finance**（[HiThink-Tech/Financial-API](https://github.com/HiThink-Tech/Financial-API)，`fuyao.aicubes.cn`）做了真实 API Key 探针 + 与 wind 冻结 base（`bt_corp_actions_20261006`，21779 事件 / 2693 码）全量对拍，结论：**可作为 wind 的并行取数通道**（对拍证据见 §7）。

## 2. 目标 / 非目标

### 目标

1. `pull_corp_actions_incremental.py` 取数层引入**通道（channel）抽象**：`wind`（现有 LLM 会话驱动，原样保留）与 `hithink`（直连 REST 全量 dump，无 LLM）。
2. hithink 通道一次 dump 覆盖全 universe，替代逐码 LLM 会话的 463 任务模型；天然免疫 wind 401 与 LLM 会话抖动。
3. 已冻结的 wind run（`bt_corp_actions_incr_20261024` / `_20261028`）续跑能力**不受影响**，wind 恢复后可直接续跑并对 hithink 结果交叉验证。
4. hithink 已知缺口（退市码、重整转增）以**运行时事实分类 + 冻结事实键**形式钉死，fail-closed，不静默吞掉。

### 非目标

- 不删除或改动 wind 通道任何现有行为（prompt、任务拆分、attempt/quota 语义、assemble 证据链）。
- 不动湖 schema（`EVENT_SCHEMA` 10 列不变）、不动 `prepare-merge` 的"只出候选、永不 apply"语义。
- 不回填历史：hithink dump 含 1991 年以来深历史，本方案只取 run 窗口内事件；历史回填如需另行 GO。
- 不配股入湖：hithink dump 含配股（allotment），wind base 无对应列，本方案落 sidecar 不消费。
- 不实现日期回填机制（§4.8 定义路径与闸门，回填本身待 wind 恢复后另行小方案）。

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
3. 校验：pyarrow 可读、必需列齐全（`thscode, ex_date_ms, dividend_per_share, per_share_bonus, allotment_ratio, allotment_price`）。**按完整经济键（全部原始列）去重**：完全相同的重复行折叠为一行（实测 000601.SZ 1997-11-03 两条逐字节相同，属上游重复而非并行事件）；同 `(thscode, ex_date_ms)` 但经济内容不同的行保留为多行（实测 000812.SZ、603883.SH，为同日分红/送股分行）。去重计数与折叠明细记入状态，不设"人工阈值"。
4. 状态写 `work/hithink_state.json`：`dump_sha256`、`fetched_at`、`dump_rows`、`deduped_rows`、`universe_hits`（universe ∩ dump 且窗口内）、`codes_no_events`（dump 有该码但窗口内无事件）、`codes_vendor_unknown`（universe 中 dump 完全不存在的码）、`vendor_unknown_probes`（C 类目录探针证据，见 §4.3）。
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
| `record_date` / `pay_date` / `bonus_list_date` | — | 恒 None（hithink 不提供；下游语义见 §4.8） |
| `source` | 字面量 | `hithink:market-dumps/adjustment-factors` |
| `event_id` | 同 wind 规则 | `natural_key` + `_incr_` + sha20。**跨通道同事件不保证同 id**（见下），防重不依赖 id 相同 |

- 窗口过滤：`start ≤ ex_date ≤ end`；窗口外事件（含已宣告未除权的未来事件）不计入、不写 rejected（dump 是全量快照，下次 run 自然再捡到）。
- 配股行（`allotment_ratio > 0`）：不映射进 events，落 `assembled/hithink_allotments.csv` sidecar + 计数进 summary。
- 同日多行（分红/送股分行）：沿用现有 `natural_key` 合并语义；同键字段冲突照抛。同日多行不是新形态——wind base 本就有 42 例（event_id 带 `_1/_2` 后缀），hithink dump 实测 2 码 4 行同类（另有 000601.SZ 2 行完全重复，已在 §4.2 折叠），下游本就按 (code, ex_date) 日口径聚合。
- 跨通道防重复合并的真实机制是 **base 钉死 + 窗口序贯**，不是 event_id 相同：`verify_base` 的 base_sha256 使湖一更新旧 run 即失效；`validate_base` 强制 base 事件 `ex_date ≤ base_ask_end`，init 强制增量窗口从 `ask_end+1` 起 → base 与 delta 的 (code, ex_date) 不可能重叠。wind 送转分列 vs hithink 合并口径下，同事件 `natural_key`（含全部数值列）几乎必然不同 → event_id 必然不同，"同 id 防重"只在数值完全一致的窄情形成立，**不作为安全依据**。
- **显式加固（两通道通用）**：prepare_merge 在既有 event_id 碰撞检查之外，新增断言"delta 的 (code, ex_date) 与 base 无重叠"，把窗口序贯从构造性成立变为显式校验。
- 覆盖断言（prepare-merge 同款语义）：`universe_hits ∪ codes_no_events ∪ explained_vendor_unknown` 必须 == universe。`codes_vendor_unknown`（dump 查无的 universe 码）**逐码按 base 冻结事实分类，不用静态码表白名单**（事实源：listing.parquet 的 `delist_date` 与 base events.parquet，均被 base_sha256 钉死）：

  | 类 | 判定（均要求事实由 base 解释） | 处置 | 实测（2026-10-29 dump + base listing） |
  |---|---|---|---|
  | A `delisted_explained` | base 有该码事件 且 `delist_date` 非空 且 **`delist_date < run.start`** | 放行（历史事件由 wind base 承载；**整窗在退市之后**，退市后无新事件） | 4 码：002231.SZ / 002898.SZ / 300379.SZ / 600200.SH（delist 2025-12-31 ~ 2026-07-17，均 < start 2026-10-07） |
  | B `delisted_no_history` | base 无该码事件 且 `delist_date` 非空 且 **`delist_date < run.start`** | 放行（整窗在退市之后且双侧一致无事件） | 3 码：000004.SZ / 000638.SZ / 920305.BJ（delist 2026-06-03 ~ 2026-07-30，均 < start） |
  | C `trading_eventless` | base 无该码事件 且 `delist_date` 为空 | 仅在 **hithink 目录正向确认**后放行：pull 时逐码探 `GET /api/meta/tickers/search`（或逐码 adjustment-factors 端点），"目录认识该码 + 生涯零事件" = 在交易但无事件（dump 含已宣告未来事件，查无即真无）；探针证据（request_id、返回条目）写进 hithink_state。目录同样查无 → 归 D | 8 码：001239.SZ / 001330.SZ / 301292.SZ / 301565.SZ / 601399.SH / 688062.SH / 688221.SH / 688382.SH |
  | D `unexplained` | **不满足 A/B/C 的一切情形**：`delist_date ≥ run.start`（`== start`、窗口内、`== end`、`> end` 均算——退市发生在窗口内/之后时，start..delist 之间仍可能有除权，dump 查无不构成解释；无论 base 有无事件）；listing 缺该码行；C 类探针失败 | **fail-closed 阻断**；唯一放行路径是 §4.4 `manual_overrides` | 3 码：000016.SZ / 002731.SZ / 601198.SH（listing 无退市日期，§7 注 2）；实测 universe 无任何码 `delist_date ≥ start`；base listing 另缺 12 个 universe 码（见下注） |

  边界语义：`delist_date == run.start` 落 D（退市当日=窗口首日，此前仍有交易日可能除权）。实测补充（2026-10-29）：base listing 缺 12 个 universe 码（000777.SZ / 000778.SZ / 000779.SZ / 002374.SZ / 002375.SZ / 002376.SZ / 300948.SZ / 300950.SZ / 300952.SZ / 301119.SZ / 301122.SZ / 301123.SZ）——全部在 dump 有事件、不进 vendor_unknown 分类，但印证 base listing 覆盖本身有缺口；"listing 缺行 → D"为防御性规则。所有判定只取与当前 run universe 的交集；分类明细（每码落哪类、依据的 delist_date/事件计数）写进 summary.json。
- `summary.json` 增 `"channel": "hithink"`、`dump_sha256`、`hithink_allotment_rows`、`vendor_unknown_classification`、`manual_overrides_applied`；`coverage_is_vendor_query_only` 保留为 True（dump 同样是 vendor 口径快照）。

### 4.4 排除清单（人工例外 + 冻结事实键）

新文件 `config/corp_actions_hithink_exclusions.json`（用 JSON，不引 yaml 依赖）：

```json
{
  "manual_overrides": [
    {"code": "601198.SH", "classification": "delisted_explained",
     "reason": "被吸收合并退市（base listing 未记录）",
     "evidence": "<公告/新闻出处>", "approved_by": "<owner>",
     "approved_at": "YYYY-MM-DD", "review_after": "YYYY-MM-DD"}
  ],
  "known_discrepancies": [
    {"code": "600989.SH", "ex_date": "2026-04-28", "field": "cash",
     "wind_value": "0.882700", "hithink_value": "0.420000", "note": "特别分红合并口径"}
  ],
  "notes": "manual_overrides 是 D 类码的唯一放行路径；known_discrepancies 为 parity gate 的冻结期望差异集（PR-A 从 2026-10-29 探针产物生成全部 46 条：cash 10 键 + bonus 36 键），两者均不影响 assemble 的数值"
}
```

- **`manual_overrides`**：D 类码的唯一人工放行路径。生效条件（逐条校验，任一不满足即拒绝并阻断）：
  - 四元组（reason/evidence/approved_by/approved_at）齐全；`approved_at`/`review_after` 均为 `YYYY-MM-DD`，`approved_at ≤ review_after`，且 `approved_at` 不得晚于 assemble 当日（CST，禁未来时间戳）。
  - **`review_after` 是真正的日历过期**：assemble 时按**当日日期**（CST）判定——`today ≤ review_after` 有效，`today > review_after` 失效恢复阻断。**不与 run end 比较**：run end 在 init 后冻结，作基准会让同一 run 数周后再 assemble 仍"永不过期"（v3 缺陷，复审 P2）。
  - `classification` 必须为四类枚举之一（未知值拒绝）；且该码在当前 run 的实际分类**必须为 D**——对 A/B/C 类码的 override 视为过期/漂移条目，拒绝并告警（防止名单漂移后 override 退化为隐式白名单）。
  - 显式不设 `approved_at` 与 `fetched_at` 的大小约束：override 的标准工作流就是"首跑 D 阻断 → 人查事实 → 落 override → 同 dump 复跑"，`approved_at > fetched_at` 是常态（复审该项建议未采纳，理由如上）。
  - 每次使用逐条写入 summary.json 的 `manual_overrides_applied`（含 evaluated_at）与 manifest-patch-plan 的 review_requirements。首跑时 000016.SZ / 002731.SZ / 601198.SH 如无 override 则 run 阻断——这是设计行为（base 事实无法解释 dump 查无，先查清楚再放行，或修订 listing 后重跑）。
- **`known_discrepancies`**：完整事实键 `(code, ex_date, field, wind_value, hithink_value)`，不是码级名单——已解释差异精确到键，同码未来出现**新**差异键仍会触发 gate 报警。
- 两份名单均只取与当前 universe 的交集；universe 外的条目忽略并告警。

### 4.5 对拍 gate（手动，不进 CI）

`scripts/gates/verify_corp_actions_hithink_parity.py`（需网络 + Key，手动跑，非 CI data-free gate）：

- 输入：hithink dump + base `events.parquet` + 排除清单。
- **聚合口径（与 §7 对拍一致，转正自 `_tmp_hithink_probe/compare2.py`）**：按 `(code, ex_date)` groupby-**sum** 后比较；wind 侧 `bonus = bonus_ratio + transfer_ratio`（送转合并）。这是日口径比较，不是 assemble 的 per-event natural_key 口径——后者跨通道本就不同形（§4.3）。
- **断言改为集合恒等**：实测差异集（全部 |Δ|≥1e-4 的 `(code, ex_date, field, wind_value, hithink_value)` 键）必须**等于** `known_discrepancies` 冻结集——实测多出冻结外任一键（新漂移）或冻结键未复现（上游已修订/口径变化）均非零退出。不按码剔除、不设比率阈值（消除"整码进容差名单后新差异被掩盖"的 fail-open）。
- `仅 wind 有` 的键必须 ⊆ A/B 类（delisted）码 × 任意日期。
- 一致率（原始 99.95% / 99.83%）仅作观察指标随报告输出，不承担断言。
- 输出 markdown 报告；触发人工逐案核对（冻结集该扩、该改，还是数据该质疑，由人裁）。

### 4.6 manifest-patch-plan 增补

hithink 通道候选的 `review_requirements` 追加：

- "hithink 行 record_date/pay_date/bonus_list_date 为 NULL、transfer_ratio 并入 bonus_ratio；economics 消费受 §4.8 闸门约束——回填前这些事件逐事件显式缺席（blocked 明细进统计），进不了 economics。"
- "hithink 不覆盖 dump 查无的标的：按 §4.3 四类逐码判定（A/B 由 base 事实解释、C 经目录探针确认、D 阻断或 override）；本次 run 的 manual_overrides_applied 见 summary。"
- "重整/债务重组转增不在 hithink 口径；**窗口内新发生的重整转增对本通道不可见**（表现为该码窗口无事件，覆盖断言无法发现），发布 GO 前必须完成 §5.3 同窗 wind diff 或显式记录放弃。"

### 4.7 发布后 base 的前向兼容（validate_base 分通道期望）

现状 `validate_base` 要求 base 每行 `record_date` 非空（:554）。hithink 行 `record_date=None`——**一旦 hithink 候选发布进湖，任何后续增量 run（含 wind 恢复后的）都会在该检查报 "base has null required fields" 被阻断**。PR-A 必须同步把该校验改为按 `source` 前缀分通道设期望：`wind:` 行维持 record_date 非空与日期一致性检查；`hithink:` 行豁免 record_date/pay_date/bonus_list_date 非空要求（ex_date 非空、event_id 唯一、decimal 合法仍适用）。测试用例见 §5.1。

### 4.8 下游 economics 消费闸门（pay/bonus_list 日期为 NULL 的处理）

事实核查（2026-10-29，codex 评审指出并已核实）：

- `ExDivEvent.pay_date` 为必填 `str`（`backtest/research/ashare_exdiv_economics.py:24`）；`_date(None)` 抛错被吞为 `invalid_event`（:122, :132-134）——pay_date=NULL 的行现金**不成应收、永不到账**。
- `list_date` 缺省回退 ex_date（:123）——bonus_list_date=NULL 会让送转股**除权日即被当作可交易**。
- 现状 economics 消费路径**不读 corp_actions 湖**（`backtest/research/cash_div_events.py` 走 `ex_date_index.parquet` overlay + 官方 600036 硬编码表），corp_actions 湖是为 economics 级 SSOT 建的前置资产——所以这是前瞻语义问题，不是现存回归，但必须在数据进湖前钉死。

**决策（显式终态，不是待办）**：

1. **闸门语义 = 逐事件显式缺席（不是整批阻断）**：hithink 行进入共享 events.parquet；任何 corp_actions → ExDivEvent 的 loader 必须先过消费闸门。PR-A 新增 `backtest/research/corp_actions_econ_gate.py::gate_rows_for_economics(rows)` → 返回 `(accepted_rows, blocked_rows, reasons)`：`source` 以 `hithink:` 开头且 `pay_date` 为 NULL，或（`bonus_ratio`/`transfer_ratio` 非零且 `bonus_list_date` 为 NULL）→ 进 `blocked_rows`（**不 raise、不走 invalid_event 静默计数、不使用 :123 的 ex_date 回退**）；调用方只消费 `accepted_rows`，`blocked_rows` 明细（code/ex_date/缺失字段）写入运行统计。**批次级 raise 只用于身份/结构异常**：`source` 前缀既非 `wind:` 也非 `hithink:` → raise（不得当作 wind 或忽略）；wind 行维持现有校验。选择逐事件缺席而非整批阻断的理由：整批 raise 会让首个 hithink 窗口发布后 economics 整体不可用，与"其余事件照常消费"的研究需求冲突；且 NULL 的经济影响（现金不成应收、红股不可交易）本就是按事件粒度陈述的。闸门带 data-free 测试。
2. **闸门不是"约定"而是结构保证（防死代码）**：(a) PR-A 把读取与闸门合成**唯一认可入口** `corp_actions_econ_gate.py::load_corp_actions_for_economics()`（读 parquet + 过闸门一体）；(b) **静态 fence 测试进 CI（data-free）**：扫描 `backtest/`、`trade_decision/`、`scripts/`，除该模块外任何文件出现对 corp_actions 湖的直接读取（`resolve_source_parquet("corp_actions"`、corp_actions `events.parquet` 路径引用、对其 `pq.read_table`）即失败——把问题从"希望未来 loader 调闸门"反转为"任何 loader 不得绕过闸门"；(c) 现状 economics 不读 corp_actions 湖（见上），fence 从第一天就拦住未来第一条直读路径。
3. **NULL 不是可接受的最终状态**：发布 GO 检查项维持 §5.3——同窗 wind diff + 日期回填完成，或显式人裁放弃并记录理由。即使放弃回填，闸门保证 NULL 行进不了 economics：这些事件的现金/送转在回测中**显式缺席**（blocked 明细可监测、可追踪），而不是静默错算（现金不到账、红股提前可交易）。
4. **回填路径**：wind 恢复后由 owner 侧以新 revision 修订（del+add）回填 record/pay/bonus_list 日期；prepare-merge 维持纯追加（`updated_event_rows: 0`），修订流程待 wind 实际恢复后另行小方案、人裁，本方案不实现。

## 5. 实施步骤（评审通过后）

1. **PR-A（实现）**：
   - `pull_corp_actions_incremental.py`：`--channel` / hithink pull（含 §4.2 全经济键去重、C 类目录探针）/ assemble 分支 / §4.3 四类覆盖断言（事实源 = 钉死的 listing + base events）/ `manual_overrides` 过期校验 / delta↔base (code, ex_date) 重叠断言 / validate_base 分通道期望（§4.7）。
   - `config/corp_actions_hithink_exclusions.json`：manual_overrides 骨架（空列表起步）+ `known_discrepancies` 全量 46 条冻结键（从 2026-10-29 探针产物生成）。
   - `backtest/research/corp_actions_econ_gate.py`（§4.8）+ data-free 测试。
   - `tests/test_corp_actions_hithink_channel.py`（合成 dump 夹具，data-free）：字段映射、窗口过滤、全经济键去重（相同行折叠/冲突保留多行）、event_id 稳定、旧 wind run.json 无 channel 字段可加载、含 hithink 行（record_date=None）的 base 可通过 validate_base/prepare-merge、**四类覆盖断言逐类与边界（A/B 放行且要求 `delist_date < start`；`delist_date == start` / 窗口内 / `== end` / `> end`、listing 缺行均落 D；C 探针证据；D 阻断）**、**override 校验（日期格式、`approved_at ≤ review_after` 且非未来时间戳、`review_after` 日历过期即失效、未知 classification 拒绝、非 D 类码的 override 拒绝）**、delta↔base 重叠断言。
   - `backtest/research/corp_actions_econ_gate.py` 测试（data-free）：逐事件 accepted/blocked 拆分与 reasons、blocked 明细进统计、未知 `source` 前缀批次级 raise、wind 行维持校验；**静态 fence 测试**（§4.8：economics 路径直读 corp_actions 湖 → fence 失败）。
   - `scripts/gates/verify_corp_actions_hithink_parity.py`（§4.5 集合恒等口径）。
   - runbook `corp-actions-incremental-driver.md` 增补 hithink 章节（Key env、四类判定、override 流程、闸门语义）。
2. **首跑（人裁 GO 后）**：`init --channel hithink` 新 run-dir `D:\exports\bt_corp_actions_incr_20261028_hithink`（窗口 10-07→10-28，与 wind 冻结 run 同窗便于对照）→ `pull` → `assemble` → `prepare-merge`（不 apply）→ 人工审 `manifest-patch-plan.json`。预期首跑在 D 类 3 码（000016.SZ / 002731.SZ / 601198.SH）阻断，需先查清事实并落 override 或修订 listing——这是设计行为。
3. **交叉验证**：parity gate 重跑（集合恒等）；wind 恢复后同窗 wind run 续跑，两候选 diff——**diff 结果必须逐键落零或 ∈ `known_discrepancies` 冻结集**（§4.5）；hithink-only 键 ⊆ 深历史/窗口外可解释范围，wind-only 键 ⊆ A/B 类码。同窗 wind 结果同时承担两职：(a) 提供 hithink 行缺失的 pay/record/bonus_list 日期事实（回填数据源，机制见 §4.8）；(b) 探测窗口内重整转增盲区（§4.6）。发布 GO 检查项：同窗 diff 已完成，或显式记录放弃及理由。
4. **发布**：沿用既有"单独 Human GO + owner 侧 publisher"流程，本驱动永不 apply。

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| API Key 授权范围变化 / 服务限流 | pull 原子失败即整体失败，无部分状态；Key 走 env，轮换不落盘 |
| dump 是全量快照、历史可被上游修订 | 每次 dump 原始 parquet + sha256 留档进证据链；跨日 diff 由 parity gate 集合恒等盯 |
| 口径差异（送转合并、缺 record_date）污染下游 | source 列区分通道；review_requirements 显式声明；null_counts 进 summary |
| 静态白名单把真实缺口误判为"已退市"（v2 缺陷：7 码中 3 码 listing 无退市日期、11 码中 3 码实已退市） | §4.3 运行时按 base 冻结事实四类判定，D 类阻断；manual_overrides 带证据 + review_after 日历过期（assemble 当日判定，非 run end） |
| 退市发生在增量窗口内 / listing 缺行，被 A/B 类误放行 | §4.3 A/B 要求 `delist_date < run.start`；`delist_date ≥ start`（含 == start / == end / > end）与 listing 缺行一律 D，override 唯一放行路径 |
| hithink 行 NULL 日期进 economics 静默错算（现金不到账 / 红股提前可交易） | §4.8 消费闸门逐事件阻断（blocked 显式缺席、明细进统计），未知 source 前缀批次级 raise；发布 GO 检查项；回填路径显式化 |
| 闸门沦为死代码（未来 loader 不经闸门直读 corp_actions 湖） | §4.8 读取+闸门合一的唯一入口 `load_corp_actions_for_economics()` + 静态 fence 测试进 CI，绕过即失败 |
| 容差名单按码剔除掩盖同码新漂移（v2 缺陷） | §4.5 差异集合恒等断言，容差精确到 (code, ex_date, field, 双值) 事实键 |
| 跨通道重复合并 | base_sha256 钉死 + 窗口序贯（base ex_date ≤ ask_end < 增量窗口）；prepare-merge 既有 event_id 碰撞检查 + 新增 (code, ex_date) 重叠断言，双 fail-closed（event_id 跨通道不同形，不作为防重依据，见 §4.3） |
| hithink 行发布进湖后，validate_base 旧 record_date 非空要求阻断后续一切增量 run | 分通道期望（§4.7）；"含 hithink 行的 base"进 data-free 测试 |
| hithink 端点契约变更 | 必需列校验 fail-closed；契约以 `fuyao.aicubes.cn/llms-full.txt` 为准，runbook 注明 |

## 7. 对拍证据（2026-10-29 探针，真实 Key）

- dump：57,700 行 / 5,435 码，ex_date 1991-02 → 2026-11-05（含已宣告未除权）。重复行：000601.SZ 2 行逐字节相同（§4.2 折叠），000812.SZ / 603883.SH 同日经济内容不同分行（保留）。
- 覆盖：universe 2774 码中 2,756 码有事件；wind 有事件的 2,693 码中 hithink 覆盖 2,686，**查无 7 码**。
- 注 2（v3 修订，codex 评审纠正）：7 码"全部退市/被吸收合并"**事实未闭环**——base listing 中仅 002231.SZ / 002898.SZ / 300379.SZ / 600200.SH 有退市日期（A 类）；000016.SZ / 002731.SZ / 601198.SH 的 `delist_date` 为空（D 类，其中 601198.SH 在 base 有 13 条事件、最近除权 2026-07-28）。反向同样不闭环：v2 列入 no_event_history 的 000004.SZ / 000638.SZ / 920305.BJ 在 listing 中已有退市日期（应归 B 类）。这是 v2 静态名单被 §4.3 运行时事实分类取代的原因。
- 事件键（code, ex_date）：共同 21,709 / wind 21,758（99.77%）；仅 wind 有的 49 键全部属于上述 7 码。
- 字段一致率（共同键）：cash 21,699/21,709 = 99.95%（10 处不符，多为 600989 宝丰能源特别分红合并口径）；bonus 21,673/21,709 = 99.83%（36 处不符，几乎全是破产重整/债务重组转增，wind 记录而 hithink 口径不含）。
- 增量窗口 2026-10-07 → 10-28：hithink 已有 **162 事件 / 162 码**，被 wind 401 卡住的数据当前可得。
- hithink 额外多 11,887 键：wind base 窗口自 2014 起，hithink 深历史更早（本方案不消费）。
- 探针产物（本机未入库）：`_tmp_hithink_probe/`（dump parquet + 对拍脚本 + 输出）。

## 8. 评审关注点

1. 通道抽象与 run.json 冻结语义的兼容性（旧 run 零改动）是否成立。
2. §4.3 运行时事实分类是否消除了静态白名单的 fail-open（重点：C 类目录探针证据是否充分、D 类 + override 机制是否过严/过松）。
3. §4.8 消费闸门的语义（NULL 行显式缺席 economics）对研究侧是否可接受。
4. Key 管理与轮换流程是否合规。

## 9. 评审修订记录

### 2026-10-29 v4（复审收口，结论 Request changes（小幅）→ 三条全部落实）

复审核验：差异键复算属实（46 唯一事实键 = cash 10 + bonus 36，与本仓探针复算一致）；UTF-8 / 无 NUL / 相对链接 / `git diff --check` 通过。修订：

1. **四类判定覆盖"窗口内退市"**（§4.3）：A/B 放行条件从 `delist_date ≤ run end` 收紧为 `delist_date < run.start`（原条件只能证明退市后无事件，证明不了 start..delist 间无事件）；`delist_date ≥ start`（== start、窗口内、== end、> end，无论 base 有无事件）与 listing 缺行一律 D。实测核验：A 类 4 码 delist 2025-12-31~2026-07-17、B 类 3 码 delist 2026-06-03~07-30，均 < start 2026-10-07，四类计数不变；universe 无任何码 `delist_date ≥ start`；另发现 base listing 缺 12 个 universe 码（均在 dump 有事件、不进分类），已记入 §4.3 注——印证"listing 缺行 → D"的必要性。
2. **§4.8 闸门从"约定"变结构保证**（§4.8）：语义定为**逐事件显式缺席**——`gate_rows_for_economics()` 返回 `(accepted_rows, blocked_rows, reasons)`，blocked 明细进统计、调用方只消费 accepted；批次级 raise 仅限身份异常（未知 `source` 前缀）。防死代码三件套：读取+闸门合一唯一入口 `load_corp_actions_for_economics()`、静态 fence 测试进 CI（economics 路径直读 corp_actions 湖即失败）、未知前缀 fail-closed。未采纳复审"approved_at ≤ fetched_at"硬约束，理由已写入 §4.4（override 工作流本就是 D 阻断后补落、同 dump 复跑，approved_at 晚于 fetched_at 是常态）。
3. **review_after 改真日历过期**（§4.4）：assemble 按当日（CST）判定 `today ≤ review_after`，不再与冻结的 run end 比较（原规则下同一 run 数周后 assemble 仍永不过期）；补充校验与测试：日期格式、`approved_at ≤ review_after` 且非未来时间戳、未知 classification 拒绝、非 D 类码 override 拒绝。

### 2026-10-29 v3（codex 评审，结论 Request changes → 三条 P1 全部落实）

评审核验：codex 三条 P1 均经本地数据/代码复核**属实**——listing.csv 证实 7 个"delisted"码中 000016.SZ / 002731.SZ / 601198.SH 无退市日期、11 个"no_event_history"码中 000004.SZ / 000638.SZ / 920305.BJ 已有退市日期（两份名单非统一事实生成）；`ashare_exdiv_economics.py:24/:122-123` 证实 pay_date 必填与 list_date 回退语义；另查明现状 economics 消费路径不读 corp_actions 湖（走 `ex_date_index` overlay），P1-2 属前瞻语义而非现存回归。修订：

1. **覆盖断言去静态白名单**（§4.3/§4.4）：改为按 base 冻结事实（listing delist_date + base events）的运行时四类判定（A/B 放行、C 目录探针确认、D 阻断）；D 类唯一放行路径为带证据与 `review_after` 过期机制的 `manual_overrides`；所有名单只取与 universe 交集。
2. **economics 消费闸门**（新增 §4.8）：hithink 行可进共享湖，但 corp_actions→ExDivEvent loader 必须过 `gate_rows_for_economics()` fail-closed（pay_date NULL 或送转非零且 bonus_list_date NULL → raise）；明确 NULL 不是可接受终态——发布 GO 需同窗回填或人裁放弃，放弃时闸门保证显式缺席而非静默错算；回填路径显式化（本方案不实现）。
3. **容差改冻结事实键**（§4.4/§4.5）：`known_discrepancies` 精确到 `(code, ex_date, field, wind_value, hithink_value)`（46 条，PR-A 从探针产物生成）；gate 断言改为差异集合恒等（多一键、少一键都失败），废除按码剔除与比率阈值。
4. **P2 文档矛盾**：§5.3 "hithink ⊇ wind" 改为"diff 逐键落零或 ∈ 冻结集"；§4.2 去重改为完整经济键（000601.SZ 两行逐字节相同 → 折叠；不设人工阈值）。

### 2026-10-29 v2（claude 评审，三个 P0 已落实）

评审核验基础：§3 代码锚点逐一对过全部准确；`_tmp_hithink_probe/` 产物与 §7 数字逐项吻合；Key 卫生通过（探针目录与 git 全历史无 Key 值，轮换入口见 §4.2）。按评审意见修订如下（实现代码仍不动）：

1. **覆盖断言改三桶**（§4.3/§4.4）：原两桶设计按 §7 自身数字（vendor_unknown 18 码 vs 白名单 7 码）首跑即 fail-closed；新增 `no_event_history_codes` 桶（dump 查无且 wind base 无事件，实测 11 码），真实缺口仍报错。（v3 注：三桶静态名单已被四类运行时判定取代。）
2. **跨通道防重论证重写**（§4.3/§6）：原"event_id 同规则 → 同事件同 id → 天然防重"不成立（natural_key 含数值列，送转分列 vs 合并必然不同 id；对拍探针为 (code, ex_date) groupby-sum 口径，从未验证 id 级一致）；改为 base 钉死 + 窗口序贯，并新增 (code, ex_date) 重叠断言。
3. **validate_base 前向兼容**（新增 §4.7）：hithink 行发布进湖后，原 record_date 非空检查会阻断一切后续增量 run；PR-A 按 `source` 前缀分通道设期望。
4. 对拍 gate 聚合口径显式化（§4.5，groupby-sum + wind 送转合并）+ 原始/剔除容差双组一致率。（v3 注：双组比率已废，改集合恒等。）
5. pay/record 日期回填路径与窗口内重整盲区显式化为发布 GO 检查项（§4.6/§5.3）。
6. 排除清单占位符补全并与 §7 数字闭环（§4.4：cash 10 键=4 码、bonus 36 键=36 码、vendor_unknown 18=7+11）。

非本方案范围：hithink 其余数据集对湖的补强 backlog（交易日历 / 指数成分权重 / 复权审计 / 收盘校验 / 基础资料等）见 [hithink-lake-supplement-backlog-2026-10-29.md](hithink-lake-supplement-backlog-2026-10-29.md)。
