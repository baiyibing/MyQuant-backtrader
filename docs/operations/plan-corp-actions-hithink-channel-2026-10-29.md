# corp-actions hithink 候选与 CNINFO 协作方案 — 2026-10-30

状态：**提案待评审**（2026-10-30 评审修订 v5：冻结四源核对与 CNINFO v10 协作合同，变更记录见 §9）。本 PR 保存方案、一次性研究证据和研究脚本原文，不实现生产取数分支、调度、消费切源或发布器。关联：[四源研究与独立扩样](note-corp-actions-four-source-study-2026-10-30.md)、非本方案范围的 [hithink 湖补强 backlog](hithink-lake-supplement-backlog-2026-10-29.md)。

## 1. 背景

- corp-actions 增量（窗口 2026-10-07 → 2026-10-28，2774 码）被 kimi-datasource wind 后端间歇性 401 阻断，详见 [#523](https://github.com/baiyibing/MyQuant-backtrader/pull/523) 与 [状态文档](corp-actions-incremental-20261028-status.md)。换机实验已证伪本机因素，401 在服务端。
- 2026-10-29 对 **hithink-finance**（[公开接口契约](https://fuyao.aicubes.cn/llms-full.txt)）做了真实 API Key 探针 + 与 wind 冻结 base（`bt_corp_actions_20261006`，21779 事件 / 2693 码）全量对拍，可提供并行的批量事件候选（证据见 §7）；其调整价格数值不自动等于经济权利金额。
- Wind 在线链路按不可用处置；既有 Wind 快照保留为离线基准，后续验证和经济日期补齐不以在线恢复为前提。CNINFO 已有独立的 v10 抽取与签收阶梯（OSkh [#1250](https://github.com/baiyibing/OSkhQuant1.3/pull/1250)、[#1251](https://github.com/baiyibing/OSkhQuant1.3/pull/1251)）；本方案与其按 §4.9 协作，不把 147 条 pre-adapter MATCH 当作 147 条可消费事件。

## 2. 目标 / 非目标

### 目标

1. `pull_corp_actions_incremental.py` 取数层引入**通道（channel）抽象**：`wind`（现有 LLM 会话驱动，原样保留）与 `hithink`（直连 REST 全量 dump，无 LLM）。
2. hithink 通道一次 dump 提供当前 universe 的批量事件候选；缺码、经济口径与可消费状态分别验证，不把有 dump 等同于覆盖完整。
3. 已冻结的 wind run（`bt_corp_actions_incr_20261024` / `_20261028`）保留原兼容性；如恢复，另验证其在线健康再续跑。离线 Wind 快照继续用于回归，不作为取得新日期的在线依赖。
4. hithink 已知缺口（退市码、重整转增）以**运行时事实分类 + 冻结事实键**形式钉死，fail-closed，不静默吞掉。

### 非目标

- 不删除或改动 wind 通道任何现有行为（prompt、任务拆分、attempt/quota 语义、assemble 证据链）。
- 不动湖 schema（`EVENT_SCHEMA` 10 列不变）、不动 `prepare-merge` 的"只出候选、永不 apply"语义。
- 不回填历史：hithink dump 含 1991 年以来深历史，本方案只取 run 窗口内事件；历史回填如需另行 GO。
- 不配股入湖：hithink dump 含配股（allotment），wind base 无对应列，本方案落 sidecar 不消费。
- 本 PR 不实现日期回填机制。CNINFO 完整公告事件或显式修订链提供经济事实候选，后续修订/发布另案；禁止只按代码和除权日拼接不同来源的字段（§4.9）。
- 不改 QMT 行情/复权权威，不把 hithink 接入 `OSKH_DAILY_DOWNLOAD_BACKEND`。既有 BT 离线候选驱动保留；新增通用采集与生产发布由 1.3 负责，本仓只保留研究核对和已授权的离线候选路径。

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
3. 校验：pyarrow 可读、必需列齐全（`thscode, ex_date_ms, dividend_per_share, per_share_bonus, allotment_ratio, allotment_price, currency`），代码、日期、非负有限数值及 `currency=CNY` 合法。实测数值列为 Arrow `double`：先 `Decimal(str(value))` 再走精度/scale 校验，不用 `Decimal(float)` 注入二进制尾差，也不静默截位。**按完整经济键（全部原始列）去重**：完全相同的重复行折叠为一行（实测 000601.SZ 1997-11-03 两条逐字节相同，属上游重复而非并行事件）；同 `(thscode, ex_date_ms)` 但经济内容不同的行保留为多行（实测 000812.SZ、603883.SH，为同日分红/送股分行）。去重计数与折叠明细记入状态，不设"人工阈值"。
4. 状态写 `work/hithink_state.json`：`dump_sha256`、`fetched_at`、`dump_rows`、`deduped_rows`、`universe_hits`（universe ∩ dump 且窗口内）、`codes_no_events`（dump 有该码但窗口内无事件）、`codes_vendor_unknown`（universe 中 dump 完全不存在的码）、`vendor_unknown_probes`（C 类目录探针证据，见 §4.3）。
5. 幂等/续跑：只在**完整提交标识、state、dump 均存在且哈希、schema、覆盖探针证据相符**时报告成功退出 0。最后写入的提交标识绑定全部产物哈希；只有 dump 或中断残留不得视为成功，非零退出并给出显式恢复指引。`--refresh` 仅在 `assemble` 未消费过旧 dump 前允许；重取、验证、state/提交标识写入须完整完成，不能复用旧探针或部分状态（已 assemble 的 dump sha256 被证据链钉住，换 dump 即失败）。
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

字段名映射不是经济口径认证。四源核对已确认 `301266.SZ` 的 2025-05-30 / 2026-05-22：hithink 现金 `0.0999998 / 0.1999990`、2026 送转合计 `0.2999985` 对应公告**按总股本摊薄计算除权参考价**的数值；CNINFO 经济候选分别为 `0.1 / 0.2 / 0.3`。这属于分母/用途差异，不应因为小于 `1e-4` 就当成同一经济字段。当前十列仅保存来源原值和 source，缺日期仍受闸门阻断；以后即使日期完整，也须有经济口径验收，不能仅因字段齐全就进入 entitlement 计算。详见[研究证据](note-corp-actions-four-source-study-2026-10-30.md)。

- 窗口过滤：`start ≤ ex_date ≤ end`；窗口外事件（含已宣告未除权的未来事件）不计入、不写 rejected（dump 是全量快照，下次 run 自然再捡到）。
- 纯配股行（`allotment_ratio > 0` 且现金/送转均为 0）：不映射进 events，落 `assembled/hithink_allotments.csv` sidecar + 计数进 summary。配股与现金/送转共存的复合行落同一 sidecar 并标记 `mixed_economics_requires_review`，窗口内出现即阻断自动候选，不能丢弃整行后仍宣称经济覆盖完整。实测全历史有 83 条此形态，均为 1992–2000 年，不涉及本次增量窗；不因此授权历史回填。
- 同日多行（分红/送股分行）：沿用现有 `natural_key` 合并语义；同键字段冲突照抛。同日多行不是新形态——wind base 本就有 42 例（event_id 带 `_1/_2` 后缀），hithink dump 实测 2 码 4 行同类（另有 000601.SZ 2 行完全重复，已在 §4.2 折叠），下游本就按 (code, ex_date) 日口径聚合。
- 跨通道防重复合并的真实机制是 **base 钉死 + 窗口序贯**，不是 event_id 相同：`verify_base` 的 base_sha256 使湖一更新旧 run 即失效；`validate_base` 强制 base 事件 `ex_date ≤ base_ask_end`，init 强制增量窗口从 `ask_end+1` 起 → base 与 delta 的 (code, ex_date) 不可能重叠。wind 送转分列 vs hithink 合并口径下，同事件 `natural_key`（含全部数值列）几乎必然不同 → event_id 必然不同，"同 id 防重"只在数值完全一致的窄情形成立，**不作为安全依据**。
- **显式加固（两通道通用）**：prepare_merge 在既有 event_id 碰撞检查之外，新增断言"delta 的 (code, ex_date) 与 base 无重叠"，把窗口序贯从构造性成立变为显式校验。
- 覆盖断言（prepare-merge 同款语义）：`universe_hits ∪ codes_no_events ∪ explained_vendor_unknown` 必须 == universe。`codes_vendor_unknown`（dump 查无的 universe 码）**逐码按 base 冻结事实分类，不用静态码表白名单**（事实源：listing.parquet 的 `delist_date` 与 base events.parquet，均被 base_sha256 钉死）：

  | 类 | 判定（均要求事实由 base 解释） | 处置 | 实测（2026-10-29 dump + base listing） |
  |---|---|---|---|
  | A `delisted_explained` | base 有该码事件 且 `delist_date` 非空 且 **`delist_date < run.start`** | 放行（历史事件由 wind base 承载；**整窗在退市之后**，退市后无新事件） | 4 码：002231.SZ / 002898.SZ / 300379.SZ / 600200.SH（delist 2025-12-31 ~ 2026-07-17，均 < start 2026-10-07） |
  | B `delisted_no_history` | base 无该码事件 且 `delist_date` 非空 且 **`delist_date < run.start`** | 放行（整窗在退市之后且双侧一致无事件） | 3 码：000004.SZ / 000638.SZ / 920305.BJ（delist 2026-06-03 ~ 2026-07-30，均 < start） |
  | C `trading_eventless` | base 无该码事件、listing 有该码且 `delist_date` 为空，并有明确的本查询范围无事件证据 | 目录精确命中只确认标的身份；还须事件端点成功返回有效空列表或经独立核实的等价覆盖证据。`3002` 的官方含义是“数据未就绪”，即使消息为 `No adjustment events` 也不能自动视作无事件；HTTP/业务错误、探针失败均归 D。证据须绑定请求参数、窗口、request_id、响应哈希，不声称“生涯零事件” | 旧 v4 的 8 码均返回 `3002`；本次没有可自动放行的 C 类证据，8 码转 D |
  | D `unexplained` | **不满足 A/B/C 的一切情形**：`delist_date ≥ run.start`（含相等、窗口内、end、未来）；listing 缺行；C 类未就绪/失败或证据不足；base 有事件但无退市解释 | **fail-closed 阻断**；唯一放行路径是 §4.4 `manual_overrides` | 本次已知为原 3 码 000016.SZ / 002731.SZ / 601198.SH 加旧 C 类 8 码，共 11 码；分类仍由实际输入和证据运行时计算 |

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
- `仅 wind 有` 的键须按最终有效分类及证据解释：A/B 事实或经审批、尚有效且有适用日期范围的 D 类例外。不得用未应用 override 前的 D 分类一边允许 assemble、一边令 parity 永久失败；也不得仅因码在 override 中就把数值差异放行。报告逐键保留缺席及解释依据。
- 四源研究另保留**全部精确数值差异**，包括小于 `1e-4` 的差异。上述历史 Wind 冻结集 gate 不等于经济金额验收；Wind 的 ROUND4/NULL-as-zero 比较政策不自动扩展至 hithink，也不把虚拟分派与实际派发当作同一字段。
- 一致率（原始 99.95% / 99.83%）仅作观察指标随报告输出，不承担断言。
- 输出 markdown 报告；触发人工逐案核对（冻结集该扩、该改，还是数据该质疑，由人裁）。

### 4.6 manifest-patch-plan 增补

hithink 通道候选的 `review_requirements` 追加：

- "hithink 行 record_date/pay_date/bonus_list_date 为 NULL、transfer_ratio 并入 bonus_ratio；economics 消费受 §4.8 闸门约束——回填前这些事件逐事件显式缺席（blocked 明细进统计），进不了 economics。"
- "hithink 不覆盖 dump 查无的标的：按 §4.3 四类逐码判定（A/B 由 base 事实解释、C 经目录探针确认、D 阻断或 override）；本次 run 的 manual_overrides_applied 见 summary。"
- "重整/债务重组转增不在 hithink 口径；窗口内新事件可能表现为该码无事件而逃过覆盖断言。须由独立公告查询、QMT 检测及逐项复核补充证据；不以 Wind 在线恢复为完成条件。"

### 4.7 发布后 base 的前向兼容（validate_base 分通道期望）

现状 `validate_base` 要求 base 每行 `record_date` 非空（:554）。hithink 行 `record_date=None`——**一旦 hithink 候选发布进湖，任何后续增量 run（含 wind 恢复后的）都会在该检查报 "base has null required fields" 被阻断**。PR-A 必须同步把该校验改为按 `source` 前缀分通道设期望：`wind:` 行维持 record_date 非空与日期一致性检查；`hithink:` 行豁免 record_date/pay_date/bonus_list_date 非空要求（ex_date 非空、event_id 唯一、decimal 合法仍适用）。测试用例见 §5.1。

### 4.8 下游 economics 消费闸门（pay/bonus_list 日期为 NULL 的处理）

事实核查（2026-10-29，codex 评审指出并已核实）：

- `ExDivEvent.pay_date` 为必填 `str`（`backtest/research/ashare_exdiv_economics.py:24`）；`_date(None)` 抛错被吞为 `invalid_event`（:122, :132-134）——pay_date=NULL 的行现金**不成应收、永不到账**。
- `list_date` 缺省回退 ex_date（:123）——bonus_list_date=NULL 会让送转股**除权日即被当作可交易**。
- 现状 economics 消费路径**不读 corp_actions 湖**（`backtest/research/cash_div_events.py` 走 `ex_date_index.parquet` overlay + 官方 600036 硬编码表），corp_actions 湖是为 economics 级 SSOT 建的前置资产——所以这是前瞻语义问题，不是现存回归，但必须在数据进湖前钉死。

**决策（显式终态，不是待办）**：

1. **闸门语义 = 逐事件显式缺席**：任何 corp_actions → ExDivEvent loader 必须先过 `gate_rows_for_economics(rows, *, evidence=None)`，返回 `(accepted_rows, blocked_rows, reasons)`。hithink 行 pay_date 为 NULL，或送转非零但上市日为 NULL，或缺少与本 revision/事件/字段数值哈希绑定的已审阅经济口径证据，均进 blocked；即使日期齐全，原始调整价格数值也不能直接进账。经济口径证据须指向已核验完整公告事件/修订链及适用政策，不能仅凭一个自填布尔值。调用方只消费 accepted，blocked 逐事件记录缺失字段/口径原因，不走 invalid_event 静默计数、不使用 ex_date 默认回退。身份/结构异常仍批次级 raise；当前 source 前缀仍仅接受 wind/hithink，不在本刀注册 CNINFO 消费。wind 行维持现有校验，闸门带 data-free 测试。
2. **闸门不是约定而是结构保证**：(a) 唯一认可入口 `load_corp_actions_for_economics()` 合并读取行、验证 revision/经济证据 sidecar、过闸门，缺证据按上款阻断；(b) data-free fence 检查 economics 消费路径直接读湖的绕过行为，扫描范围和显式豁免由测试固定。合法维护/研究读取必须豁免，至少包括现有 `pull_corp_actions_incremental.py`、离线 parity/四源研究驱动及闸门模块；豁免仅允许读数/准备候选，不授予 economics 消费资格。既测非法消费绕过失败，也测维护驱动不会误报；(c) 现状 economics 不读该湖，不为本 PR 接入消费者。
3. **可取候选不等于经济账完整**：分别报告 acquisition、evidence、economics-ready 状态；blocked 数量、代码/日期/原因及使用了哪些适配政策进入研究运行结果。含 blocked 事件的结果须明确 economics 不完整，不能因日志里有计数就宣称完整 NAV。发布前按 §4.9/§5 完成公告经济事实/修订候选审阅，或由 Human 显式接受对应缺席范围及其影响。
4. **修订路径**：由 owner 侧依据 CNINFO 完整公告事件或显式修订链提出新 revision（del+add）候选，保留原始事实与政策适配的区别；Wind 快照作为可用历史对照。prepare-merge 仍纯追加（`updated_event_rows: 0`），修订/回填发布另案，不等待 Wind 在线恢复，也不在此处实现。

### 4.9 QMT / hithink / CNINFO / Wind 协作合同

| 来源 | 本次职责与字段边界 |
|---|---|
| QMT | 行情与价格复权权威不变；`cumulative_adj_factor=front/none`。`get_divid_factors` 七字段已有下载面，但现有 `ex_date_index` 只保留日期/`dr`；本次只验日期，不反推金额、不写回因子。七字段留存如需实施，另在 1.3 小方案中完成。 |
| hithink | 批量事件发现与现金/送转核对；保留原始数值及 source。送转合并量不是送转分列事实；缺经济日期仍受 §4.8 阻断。 |
| CNINFO | 复用 1.3 `mvp-v10`、adapter 和修订链，提供可追溯公告经济事实。实际派发/调整后金额、原文日期与经 Human 批准的适配政策分别留证。 |
| Wind | #501 冻结快照为历史回归基准；在线状态为 unavailable，现有 run 保留兼容性，恢复后另取健康证据。 |

- 经济候选以同一公告事件或可追溯修订链为整体；`(code, ex_date)` 只用于候选关联，不是跨源字段拼接或修订身份。多公告、同日多事件、金额/日期冲突都进入复核。不得只把 CNINFO 日期填入 hithink 的调整价格现金上就宣布可消费。
- 现行 Human 政策继续遵守：空送转腿的条件适配为 0、Wind 比较的 ROUND4、缺失送转上市日按 ex_date、实施双口径优先调整后/实际派发。证据 sidecar 分别保存原始/抽取值、适配值、依据及版本；默认上市日不得标为“公告明示”。本方案不回退已批准政策，也不将其扩展到 hithink。
- hithink 名单可用于优先核对，但不是 CNINFO 唯一采集分母。独立公告查询还须揭示缺失、修订、取消、重整与范围外事件；无返回、业务未就绪和查询失败不得混同。
- 新候选只落独立研究目录。CNINFO C3、Owner 签收、合湖与主源切换仍是独立动作，本次研究与此方案均不代签、不启用。

### 4.10 湖根、快照与共同窗口

湖根以 `common.infra.data_root` 的实际解析结果为准；`.authority` 是配置位置标识，不证明各宿主数据同步。2026-10-30 本机为 `OSKH_SOURCE_PARQUET_ROOT=E:\stock_data` 且 marker 有效；F 是 75 物理机的路径，4090 不预设 F。原 PR 没有写死 F，不需要增加盘符探测。

记录宿主/运行标识、解析后根、marker 指纹、每源文件 SHA256、数据截止日、冻结宇宙及窗口。当前本机 QMT 索引/因子到 2026-10-15，不能把之后的 hithink 事件判成 QMT 漏数；当前湖未部署 `corp_actions/`，首用基线须显式重建/交接并验证 revision 和全部哈希。全历史对拍和 2024–2026 固定样本对拍分开报告，不能混用分母。

`fetched_at` 只表示取得文件的时刻；本次 dump 最大 ex_date 为未来的 2026-11-05，既不等于供应商已完成的覆盖水位，也不能证明所有已实施事件齐备。缺少供应商覆盖水位时明确记为未知，以独立公告/QMT 范围核对和 Human 窗口审阅决定是否可推进 ask_end，不能由最大 ex_date 推断。

## 5. 实施步骤（评审通过后）

1. **PR-A（实现）**：
   - `pull_corp_actions_incremental.py`：`--channel` / hithink pull（含 §4.2 全经济键去重、C 类目录探针）/ assemble 分支 / §4.3 四类覆盖断言（事实源 = 钉死的 listing + base events）/ `manual_overrides` 过期校验 / delta↔base (code, ex_date) 重叠断言 / validate_base 分通道期望（§4.7）。
   - `config/corp_actions_hithink_exclusions.json`：manual_overrides 骨架（空列表起步）+ `known_discrepancies` 全量 46 条冻结键（从 2026-10-29 探针产物生成）。
   - `backtest/research/corp_actions_econ_gate.py`（§4.8）+ data-free 测试。
   - `tests/test_corp_actions_hithink_channel.py`（合成 dump 夹具，data-free）：字段/单位/CNY/精度校验、窗口过滤、全经济键去重、event_id 稳定、旧 wind run 可加载、含 hithink 行的 base 前向兼容；覆盖 A/B/C/D 边界与 `3002` 不作空事件、override 日期/枚举/实际分类校验、delta↔base 重叠；补 dump 已落但 state/提交标识缺失、哈希漂移、refresh 中断、double→Decimal、复合配股事件阻断用例。
   - `backtest/research/corp_actions_econ_gate.py` 测试（data-free）：逐事件 accepted/blocked、blocked 明细、未知 source、wind 校验；日期齐全但经济口径未核验的 hithink 行仍阻断、证据 revision/数值哈希漂移拒绝；**静态 fence** 同时覆盖 economics 绕过失败与合法维护读取不误报。
   - `scripts/gates/verify_corp_actions_hithink_parity.py`（§4.5 集合恒等口径）。
   - runbook `corp-actions-incremental-driver.md` 增补 hithink 章节（Key env、四类判定、override 流程、闸门语义）。
2. **首跑（实现及人裁 GO 后）**：`init --channel hithink` 使用独立 run-dir 和冻结 10-07→10-28 窗口 → `pull` → `assemble` → `prepare-merge`（不 apply）→ 人工审 `manifest-patch-plan.json`。按已保存探针证据，原 D 类 3 码和旧 C 类 8 码共 11 码没有自动放行依据；须独立查清并落有效 override 或修订基线，不能把 `3002` 改成空事件。
3. **交叉验证与补齐候选**：先复用四源 38 码研究，再用冻结 v10/政策的独立扩样检验（见[研究合同](note-corp-actions-four-source-study-2026-10-30.md)）；历史 Wind gate 保留，新增量由 hithink、QMT 共同覆盖范围与独立 CNINFO 公告查询核对。缺日期通过 §4.9 完整公告事件/修订候选处理，冲突逐项复核；不以 Wind 在线恢复作为完成或发布前提。缺席范围、政策值和经济账完整性均须显式审阅。
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

### 2026-10-30 v5（四源研究与 CNINFO v10 协作）

冻结 38 码原样本、v10 及已批准政策，补入 hithink dump / 本机 QMT 索引核对；新样本用独立 QMT 抽样框与固定 seed，不用 hithink 有事件名单筛选。证据和统计口径见[研究合同](note-corp-actions-four-source-study-2026-10-30.md)。

1. Wind 在线不可用不再阻塞方案；CNINFO 完整经济事件/修订链与 hithink 批量发现协作，禁止按日键拼字段。
2. 147 个 pre-adapter MATCH、115 个窗口内 adapter-accepted MATCH 与 34 条复核分别报告；政策值与原文抽取值留证，不宣称全市场召回。
3. C 类不再由目录命中或 `3002` 自动放行；补齐成功提交标识/state/dump 的续跑合同、维护读取 fence 豁免与测试、double→Decimal 转换及复合配股阻断语义。
4. 以 resolver / marker / 哈希 / 数据截止日冻结宿主输入；QMT 行情与复权权威不变，backlog 接口须先证明能力。
5. 本次不实现生产采集、调度、消费者接线或发布；已批准适配政策及既有 Owner/C3/合湖边界保留。

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
