# minute_orders 专用研究 CLI：Track A

2026-09-29 · Human「A GO」· 基线 `6cd29e6` · `production_C=frozen`。
冻结：`/workspace/handoffs/l2_cli_a_20260929/HUMAN_GO.md`；
规格：`/workspace/handoffs/next_tracks_abcde_order_20260929/ORDER_EVAL.md` §4、§10。
本片只产品化 synthetic 输入、S4 工件与 L1 CLI transport；PR 待 Human「合」，不自动合并。

## 原生调用

使用显式解释器，在仓库根运行（Linux 验收解释器如下；其他宿主按 AGENTS 配置）：

```bash
/tmp/l2s2-ledger-venv/bin/python scripts/research/run_minute_orders_research.py \
  --input tests/fixtures/minute_orders/partial_cancel_expiry_v1.json \
  --parent /tmp/minute-orders-example \
  --run-id synthetic-example-01 \
  --evidence-level synthetic
```

四个参数全部必填；样例里的费率、资金、参与率和 mark 均不是参数默认。
脚本身份固定为 `minute_orders_research_v1`，不提供 family/backend 默认选择器。
输入为 UTF-8 无 BOM 的本地 JSON 文件，不接受 Python 模块、pickle、用户工厂或湖路径加载。
`--code-sha <40位小写SHA>` 可显式覆盖 provenance；省略沿用 S4 的 git HEAD/dirty 记录。
该覆盖值是调用方声明，不能证明代码清洁或真实数据来源。

输出根：`<parent>/backtest_output/minute_orders_research_v1/<run-id>/`。
相对 input/parent 按调用 cwd 解释；run-id 只允许单个安全 ASCII 路径段。
已有根（含空目录、文件、符号链接）拒绝覆写；失败后保留证据，必须由调用方选择新 run-id。
只调用一次现有 `run_minute_orders_research_with_artifacts`，不 retry/recover。
工件/哈希/失败归档仍由 [S4](note-l2-s4-artifacts-isolation-2026-09-29.md) 所有。

## v1 JSON codec

[完整可运行样例](../../tests/fixtures/minute_orders/partial_cancel_expiry_v1.json)；
[codec](../../backtest/research/minute_orders_backend/input_codec.py) 提供
`decode_run_input` / `encode_run_input`（对象）、`loads_run_input` / `dumps_run_input`（文本）、
`load_run_input`（文件）。封套必须恰好包含：

```json
{"schema_version": "minute_orders_run_input_v1", "timezone": "Asia/Shanghai", "data": {}}
```

上面的空 data 仅展示封套，不能运行。data 与所有嵌套记录字段均必填：

| data 字段 | 表达 |
|---|---|
| `start_at`, `end_at` | ISO 日期时间，含秒与显式偏移，最多六位小数秒 |
| `commands` | submit/cancel 数组；用 `kind` 区分，其他字段对应原生 SubmitOrder/CancelOrder；submit 的 `order_type` 必填 |
| `calendar` | `trading_dates` 日期数组、`session_buckets`、`company_actions_covered`、`company_actions` |
| `buckets` | 显式 symbol/bucket_id/start/end/close/volume_shares/missing/halted |
| `instruments` | symbol/trade_date/board/price_domain/tick_size/lot_size/reference_price/limit_down/limit_up |
| `initial_cash`, `initial_lots` | Decimal 字符串、LotPosition 数组（含显式 `reserved_qty`） |
| `buy_fees`, `sell_fees` | 各自完整 rate/min_fee/rounding，不继承生产费率 |
| `participation_rate` | Decimal 字符串 |
| `marks`, `requires_marks` | 完整 MarkEvent/MarkPrice 数组与显式 bool 策略 |

所有 Decimal（金额、价格、费率、参与率）必须为有限十进制字符串，不先过 float、不量化。
qty/sequence/volume/lot_size/reserved_qty 必须为 JSON 整数，bool 和字符串不能冒充整数。
日期格式 `YYYY-MM-DD`；例如 `2026-09-28T09:30:00+08:00` 会恢复为具名
`ZoneInfo("Asia/Shanghai")`，偏移/本地钟不一致或无时区即拒绝，不静默换算 UTC 输入。
所有层级拒绝多余字段、重复 JSON keys、非整数 JSON 数字和 NaN/Infinity。
空数组必须显式写 `[]`；missing bucket 的 close/volume 必须显式写 null，再由原生验证组合。

codec 只管版本、结构、类型和时区；经济与覆盖规则仍由原生 runner 校验并归档失败。
例如整手约束、费率/rounding、raw/main、LIMIT、continuous session、mark 完整性不被放宽。
公司行动覆盖必须显式提供；v0 只接受 covered=true 且 actions=[]。
非空公司行动纯数据可解码保留，但原生必定失败归档，不实现任何公司行动经济处理。

## 退出与完成判据

| exit | 含义 | 输出 |
|---|---|---|
| 0 | native status=success 且已发布有效 summary | stdout 一行 JSON，含 root/summary；正常业务 Rejected 也可成功 |
| 2 | 参数、文件读取或 JSON/wire 解析失败 | stderr 诊断；不调用 wrapper、不建工件根 |
| 3 | 原生引擎失败并完成 S4 失败归档 | stderr `engine_failed` 与 failure 路径；无成功 summary |
| 4 | writer/目录失败或完成标记校验失败 | stderr `output_error`；保留已有证据，不补造成功、不重跑 |

参数错误沿用 argparse 文本；其他诊断为单行 JSON。
成功检查 summary/manifest 的 native hashes、身份、synthetic、固定比较状态、summary 哈希引用及基本结构；
summary 缺失、损坏、身份冲突或同时存在 failure 都不能 exit 0。CLI 校验本身不修改工件。
`--help` 按 CLI 惯例 exit 0，只表示帮助显示；不产生 run。进程中断/SystemExit 不伪装成功归档。

## L1 精确 transport

设置 `OSKH_MERGE_PYTHON` 为已配置解释器后：

```python
from backtest.research.run_protocol import NativeCliRequest, run

result = run(NativeCliRequest(
    family="minute_orders_research",
    native_entry="scripts/research/run_minute_orders_research.py",
    argv=["--input", "input.json", "--parent", "output", "--run-id", "synthetic-01",
          "--evidence-level", "synthetic"],
))
assert result.native_exit_status == 0  # 此例是 run argv，不是 --help
```

仅增加这一条 `native_cli` 白名单；[S5 两个 API](note-l2-s5-l1-register-2026-09-29.md) 保持。
解释器按现有 resolver；CliContext 仅对子进程施加 cwd/env_overlay。
argv 原样、单次启动、exit 与 stdout/stderr 原始 bytes 原样返回；L1 不解析 JSON 或扫描工件。
API envelope `returned` 与 CLI envelope `exited` 都不等于研究成功。

验收覆盖手算 partial/cancel/expiry、累计费/预留、sell 初始 lot、missing/halt、mark 中途失败、
非法输入、业务拒单、writer 注入失败和拒覆写；受控 cwd/相对路径/code_sha 下，
native API/S4 与 native CLI/L1 CLI 全工件逐字节一致，两个 CLI 的退出及原始流一致，不 scrub。
这只证明 synthetic 产品闭环及本家族委托 parity；无湖验证、无跨后端收益比较。
`evidence_level=lake` 拒绝；`comparison_status=no_ssot_compare_authorization` 保持。
未改 Clock/Broker/Match/Ledger/Fees、旧家族、HELP_LOCK、presets、golden 或任何 SSOT 绿R/绿S。

后续 [B-L2-01 lake source ingress 合同](note-l2-lake-source-ingress-b-l2-01-2026-09-29.md)
仅冻结具名单元与 resolver→RunInput 来源映射；loader/evidence 扩展和 4090 真湖验收各待具名 GO。
本 CLI 仍为 synthetic-only；该合同不构成 L2 lake PASS 或 SSOT 比较授权。
