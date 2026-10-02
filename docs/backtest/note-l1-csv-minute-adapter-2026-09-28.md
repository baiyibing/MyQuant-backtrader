# L1：csv_minute adapter

2026-09-28 · Human GO「开干 L1 CSV adapter」· 基线
`cc16e9d227ec9b1cce693f026af4db4059caeefd`（`cc16e9d`，#245）。
这是 [JR Mode B adapter](note-l1-jr-modeb-adapter-2026-09-28.md) 之后第二个 L1 adapter，
落实 PLAN §3.2–3.6 / L1-S1 CSV；`production_C=frozen` 不变。

## 精确注册

公共入口仍为 `from backtest.research.run_protocol import run` → `run(request)`。
下列三项加入静态白名单，**既有 JR 三项全部保留**；无插件扫描或动态发现。

| family | entry_kind | native_entry（精确字符串） | native target |
|---|---|---|---|
| `csv_minute` | `native_api` | `csv_minute_backtest.simulate` | `backtest.research.csv_minute_backtest.simulate` |
| `csv_minute` | `native_api` | `csv_minute_backtest.run` | `backtest.research.csv_minute_backtest.run` |
| `csv_minute` | `native_cli` | `backtest/research/csv_minute_backtest.py` | 原模块脚本 → `SystemExit(main())` |

包 / facade 导入均不加载 CSV、JR、v7、grid 引擎；API 选中后才导入对应引擎。
未知 family / transport / entry 组合在 native 调用前抛 `UnregisteredEntryError`。
每个接受的请求整次委托一次，不重试、不拆分、不调用其他 adapter。

## 原生边界

- `simulate` 吃显式 `minute_bars / daily_bars / pool_days`；`run` 保留原加载职责。
  两者返回原 `SimState` 对象，均不代表完整 CLI writer；artifact refs 保持 `OMITTED`。
  不扫目录、猜路径或伪造文件引用。
- 原 `args/kwargs` 对象直接展开，保留嵌套引用和 native mutation；不填默认。
  键省略 ≠ `None` ≠ `False` ≠ 空值。L1 不切 cwd、改 env / PYTHONPATH 或重设 RNG。
  原 CSV 模块自身导入时的 `sys.path` 行为保留，不由 L1 改写。
- 原 API 异常（含 `InsufficientCashError`、`SystemExit`）以同一实例继续 raise，
  不返回异常 envelope 冒充结果。策略、stop / topk / tail 校验仍由 native 决定。
- CLI 的 `request.argv` 仅为参数尾部。数组启动仓内原脚本绝对路径，不经 shell。
  `resolve_oskh_python()` 在父上下文选择解释器，缺失即失败，不回落系统 Python；
  相对解释器先锚定父 cwd，保留虚拟环境符号链接。
- CLI 默认继承 cwd/env；显式 `CliContext.cwd / env_overlay` 仅传子进程。
  返回原 exit status 和 stdout/stderr bytes；launch failure 直接传播，不伪造 native exit。
- 完整 summary、可选 manifest/audit 等 writer 仅走原 CLI。CSV 的非空输出目录拒绝规则保留；
  adapter 不 mkdir、清空或改名。CLI artifact refs 也保持 `OMITTED`，不代表无产物。

## 本片无数据验收

测试文件：[test_research_run_protocol_csv_minute.py](../../tests/test_research_run_protocol_csv_minute.py)。
复用既有 CSV `_day / _daily`，仅内存合成 bars；C1–C5 / X1–X2 已按 Human GO **收窄**。

| 范围 / 测试 ID | 本片证据 |
|---|---|
| C1-ish：`test_simulate_full_state_parity_and_reference_identity` | version6 省略 / close / hl；买入、止损及未平 lot，全部 SimState 字段深比较，交易/reason 顺序与返回对象身份 |
| 失败：`test_real_native_failure_is_same_instance_once` | version8 合成资金不足；simulate/run 拒绝 stop_fill=close；run 拒绝 tail 缺 X-02，原异常实例、单次调用、加载前拒绝 |
| X2：`test_api_omission_mutation_and_caller_context` | 两个 API 的引用、callable、audit_sink 省略/显式空值、native mutation、cwd/env/RNG/sys.path；此项 spy 不算 run loader 成功 |
| 白名单 / import：`test_unregistered_entry_cannot_reach_native`、`test_fresh_import_and_csv_dispatch_are_lazy` | 错组合拒绝；新 `-I` 进程证明惰性导入，选 CSV 后仅加载 CSV；既有 types/JR 测试原样回归 |
| X1-narrow：`test_cli_parser_exit_and_raw_bytes_without_lake` | 原 CLI 与 facade 的 help exit 0、缺参/非法参数 exit 2，固定 child cwd 下原始双流 bytes 一致，无 writer 产物 |
| CLI 边界：`test_cli_one_launch_literal_tokens_and_child_only_context` 等 | argv/负退出码/raw bytes、child-only cwd/env、缺解释器与 transport failure；启动 spy 不算实际 writer 通过 |

**绿P = delegation parity only**，不是 SSOT 绿R / 绿S NAV 比较资格，也不授予 L2 绿C。
没有 lake E2E，没有完整 C1–C5 认证。`run` 真实加载成功与 CLI 完整 writer 成功路径
**允许但联合效果未证实（allowed but joint effect unproven）**；help 成功不等于回测成功。
同样未证实完整 C2–C5：S8 多日身份 / 红股 / T+1、TopK 全 exec、hl / X-02 / X-04 /
qlib-cost / fen 全组合、s11/s12 专用接线全表面。未覆盖不会额外阻止 native 本来允许的参数。

范围外：v7 / grid adapters 或注册、views 投影、L2 MatchCore / minute_orders_backend、
湖 / 真实行情 / G8 / strategy12 研究 / JR clock pack 重生成、production_C 或其他默认翻转。
原引擎、fees/exdiv/fill-gates、HELP_LOCK、presets、golden、CI YAML 不改；
共享 CSV 不替换，Cerebro 禁令不变。

**勿合 / Do NOT merge without human「合」；等待 Human「合」，不启用 auto-merge。**
