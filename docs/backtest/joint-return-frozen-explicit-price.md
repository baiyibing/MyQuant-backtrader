# Joint-return research replay: two explicit input paths

Synthetic green ≠ real return. The original synthetic path and its 10/3,
P-BASE/P-CHASE, M-REF/M-LAG semantics stay unchanged. Its contract pin remains
`dfa020d2c01e6cfe6612f09be2d569294ff94d82fd1ede5cea61a41d74a81737`.

Frozen control-only 50/5 packs use the separate pin
`9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41`.
Manifest and metadata must match that pin; explicit price metadata must also
carry it. BT checks artifact bytes/content, intent identities, reference chains
and plan bindings without changing quantities or reference prices. CSV accepts
one additional JSON quoting layer, then verifies decoded content hashes.
`--intents` accepts intents.csv, its directory, or adjacent manifest.json.
The adjacent constraints.csv and pref_check.json remain mandatory.

This minimal adapter implements **`--bars` only**, not a Qlib reader.
Frozen prices use the existing minute JSON schema in the module docstring,
with `kind=frozen_explicit`, `metadata.contract_hash` set to the frozen pin,
nonempty `metadata.source` provenance and `content_sha256` equal to SHA256 of
canonical JSON excluding that field (UTF-8, sorted keys, compact separators).
Include explicit raw open/close, price limits, suspension, executable capacity,
session endpoints, initial lot marks/acquisition evidence and complete corporate
actions. Hashes bind the supplied evidence; they do not certify source truth.
No source URI is dereferenced. There is no lake search or bar fabrication.

Frozen replay permits **P-BASE / M-LAG**, plus **P-BASE / M-REF** only with the
explicit mark evidence below. P-CHASE and weak stay INPUT_BLOCKED.
Missing explicit prices or any missing symbol/minute in the declared calendar
for the intent/initial universe fails closed; the coverage error reports
expected, observed and missing symbol-minute counts. This conservative coverage
rule also requires explicit suspension evidence and may block a sparse host
export. Do not fill those gaps with fabricated bars.

## Mode B / M-REF（用户裁 2026-09-23）

Mode B = **同一冻结包、同一宇宙/存活窗、同一显式 bars 的 M-REF vs M-LAG**。
可用 `--arm P-BASE --fill-mode all` 一次产出两种成交模式；或分别指定
`M-REF` / `M-LAG`，写入不同父目录下的同名 run_id。未扩 P-CHASE / weak。

M-REF 必须在 `kind=frozen_explicit` 的 bars JSON 中另供
`metadata.reference_marks`，键集合严格等于全部冻结 `intent_id`。每条示意：

```json
{
  "instrument": "SH600000",
  "execution_symbol": "600000.SH",
  "mark_price": 10.25,
  "mark_at": "2025-01-02T15:00:00+08:00",
  "price_domain": "none",
  "source_kind": "lake_bar",
  "source": "显式导出的真实湖价来源及字段定位",
  "source_sha256": "源证据原始字节的64位小写SHA256"
}
```

导出方必须用真实湖价（可为 plan mark 对应的湖价），提供源证据定位与哈希；
不能仅给 sessions 改标签。适配器校验每条标的/执行代码与 intent 相同、
`mark_at` 严格等于 `reference_price_at`（因此不晚于 decision），
raw 域 `none`、来源种类/非空定位/哈希格式及有限正数价格。
mark 可早于成交日历；这支持前一交易日收盘参考，不拿次日 open 回填旧时点。
完整 mark 映射由 bars 的 `content_sha256` 绑定，并原样记入 summary 便于审计。
此处验证的是证据合同及内容完整性，**不联网核验源字节，不证明湖价真实性或 PIT**；
真实来源仍需 4090 导出/回执验收。

**禁止 sessions `reference_price=1.0` 充当市价或真实 mark。** 缺少独立 mark、
覆盖不全、时点/标的/价格域错配均 INPUT_BLOCKED；独立 mark 为 1.0 也保守阻断
（包括真实价格恰为 1.0 的情形，本刀不另开豁免）。只有 bars open/close、
只有 plan marks 或非 1.0 的 intent reference_price，都不足以放行。
M-LAG 不要求也不使用此映射，继续取合法分钟 open。

原 intent / plan / 数量 / 身份哈希不改。冻结 M-REF 的研究成交价改取独立 mark，
沿用原 `reference_price_at` 单位时期及显式公司行为换算；输出仍保留原始
`reference_price`，实际成交价看 `price`，证据看 summary 的 `reference_marks`。
M-REF 仍是假设参考价、理想流动性的敏感度对照，保留既有 T+1、停牌及方向涨跌停门，
不是该参考时点的可执行收益。CLI 仍只吃显式 `--bars`，不读 `QLIB_1MIN_ROOT`，
不造 bar，不改生产 fill kernel / CSV 引擎 / scanner / ledger。

data-free fixture 只证明合同门和 M-LAG 回归，不证明真数；4475 fills 的既有
P-BASE/M-LAG 真数仍为交接基线，本刀不派 4090、不宣称已完成真湖 Mode B 对照。

4090 Windows cmd recipe (the price JSON must first be supplied on that host):

```bat
set "HANDOFF=D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922"
set "PRICES=D:\path\to\verified-frozen-explicit-bars.json"
"%OSKH_MERGE_PYTHON%" scripts\research\run_joint_return_replay.py ^
  --intents "%HANDOFF%\portfolio_joint-return-control-only-50-5\intents.csv" ^
  --bars "%PRICES%" --arm P-BASE --fill-mode M-LAG ^
  --out backtest_output\joint-return-v1\joint-return-control-only-50-5
```

Use the configured interpreter (or the explicit vanna312 interpreter).
The pack has about 2470 intents, window 2025-01-02..2025-12-31,
price_domain=none and valuation=research-none-mark-v1. These host facts do not
replace validation. The authorized host source is `QLIB_1MIN_ROOT`, for example
`C:\Users\wangc\.qlib\qlib_data\my_data_1min`; preparing a verified JSON export
from it is a remaining host task. This CLI does not read that environment variable.
No explicit price → INPUT_BLOCKED. Real 4090 files are not needed by CI.

Outputs retain orders.csv, fills.csv, daily_nav.csv and summary.json under the
specified run directory; an existing directory is never overwritten. Frozen
success is BT_RESEARCH_REPLAY_PASS / RESEARCH_RUN, preserves MQ's INPUT_BLOCKED
provenance status, and leaves real_execution_status=INPUT_BLOCKED and
return_status=待实测. The fixture tests prove adapter behavior, not real returns,
raw-source verification, PIT, full trading costs or corporate-action economics.
Production_C and all production paths remain frozen. Do not merge without
bt/human review: CI green first, then bt merges.

## Research-only 阶段计时（2026-09-23）

在原回放命令追加 `--profile-timings` 即开启；默认关闭，不读计时时钟、
不增加日志或产物。Python 入口对应 `run_replay(..., profile_timings=True)`。
仅用于 joint-return / Mode B 的「先测再加速」研究决策，不改变成交语义、
时钟边界、容量切片、fees 或 Decimal 结果；未引入 orjson / Rust / 并行。

成功回放后 stderr 输出一行 `research phase timings (seconds): {…}`，
JSON 数值均为单调墙钟 `perf_counter` 秒数，保留六位小数：

- `bundle_load`：manifest、intents 及伴随文件装载与原有校验。
- `bars_read`：显式 bars 文件字节读取。
- `bars_json_parse`：UTF-8 解码、stdlib JSON 解析及原有重复键检查。
- `validate_bars`：bars 合同/内容/覆盖校验。
- `validate_reference_marks`：仅 frozen M-REF（含 `all`）记录独立 mark 校验。
- `replay_<fill_mode>_<arm>`：各次 `_Replay(...)` 构造（含索引）与 `.run()`；
  例如 `replay_M-REF_P-BASE`、`replay_M-LAG_P-BASE`。`--fill-mode all`
  分别记账；仅选 P-CHASE 时仍记录实际执行的 P-BASE 基准，基准复用不重复计时。
- `write_artifacts`：CSV/summary 序列化、产物与输入审计哈希、建目录及写出，
  包括最后的 summary.json 写入。
- `total_seconds`：从 `run_replay` 入口到全部产物写完的总耗时；包含上述不重叠阶段，
  以及阶段间 manifest 复核、汇总等开销。不包含 CLI 参数解析、末尾读取 summary
  与打印回执/计时行，因此不要求等于各阶段之和。

不写 timings.json，也不向 summary 注入计时字段。四份产物、stdout 成功回执
及既有合同不变，summary.json 仍最后写、仍是完成标记。失败沿用原错误路径，
不输出成功计时摘要。data-free 测试只验证计时覆盖与产物一致性，不代表真湖耗时。
