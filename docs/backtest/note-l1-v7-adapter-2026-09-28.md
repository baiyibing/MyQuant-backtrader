# L1：v7 adapter

2026-09-28 · Human GO「开干 L1 v7 adapter」· 基线
`4b66acadd3ed18c426ff57df8e32391c5651debf`（`4b66aca`，#246）。
这是 [JR Mode B](note-l1-jr-modeb-adapter-2026-09-28.md) 与
[CSV](note-l1-csv-minute-adapter-2026-09-28.md) 之后第三个 L1 adapter，
落实 PLAN §3.2–3.6 / L1-S2 v7；`production_C=frozen` 不变。

## 精确注册

公共入口仍为 `from backtest.research.run_protocol import run` → `run(request)`。
下列两项加入静态白名单，**既有 JR 三项、CSV 三项全部保留**；无插件扫描或动态发现。
family 使用 types 已冻结的 `v7`，不使用计划早期示意的 `v7_native`。

| family | entry_kind | native_entry（精确字符串） | native target |
|---|---|---|---|
| `v7` | `native_api` | `csv_minute_backtest_v7.simulate_v7` | `backtest.research.csv_minute_backtest_v7.simulate_v7` |
| `v7` | `native_cli` | `backtest/research/csv_minute_backtest_v7.py` | 原模块脚本 → `SystemExit(main())` |

包 / facade 导入不加载 CSV、v7、JR、grid 引擎；选中 v7 API 才导入 v7 引擎。
未知 family / transport / entry 组合在 native 调用前抛 `UnregisteredEntryError`。
每个接受的请求整次委托一次，不重试、不拆分、不调用其他 adapter。

## 原生边界

- `simulate_v7` 收显式 bars，返回原 `SimResult`（现金、阶段、lots、交易、权益）引用。
  v7 没有 CSV 式加载后返回状态的独立 `run` API；不虚构该入口，
  不把 `write_run_artifacts` 注册成完整 run。API artifact refs 保持 `OMITTED`，不扫目录猜路径。
- 原 `args/kwargs` 直接展开，保留嵌套引用与 native mutation；不填默认。
  键省略 ≠ `None` ≠ `False` ≠ 空值；API 不切 cwd、改 env / PYTHONPATH 或重设 RNG。
  tail / X-02 / fee / cap / economics 等参数继续由 native validator 决定。
- API 原异常（含 `ValueError` / `SystemExit`）以同一实例继续 raise，不转成返回 envelope。
  v7 资金不足仍为 `skip_cash` 事件，**skip_cash ≠ raise**；首根 gap、买后 timer 和阶段机不改。
- CLI 池继续取 `--pool-dir` 或 `OSKH_TURTLE_POOL_DIR`，不回落 `stock_pool/`；
  API 不伪造必填池目录。完整加载、`write_run_artifacts`、run-config / audit 属于原 `main`。
- `request.argv` 仅为参数尾部；数组启动仓内原脚本绝对路径，不经 shell。
  `resolve_oskh_python()` 在父上下文选解释器，缺失即失败，不回落系统 Python；
  相对解释器先锚定父 cwd，保留虚拟环境符号链接。
- CLI 默认继承 cwd/env；显式 `CliContext.cwd / env_overlay` 仅传子进程。
  返回原 exit status 与 stdout/stderr bytes；启动失败直接传播，不冒充 native exit。
- v7 writer 原 `exist_ok=True`、可覆写语义保留，不套 CSV/JR 输出目录规则；
  adapter 不 mkdir、清空或改名。CLI artifact refs 也保持 `OMITTED`，不代表无产物。

## 本片无数据验收

测试文件：[test_research_run_protocol_v7.py](../../tests/test_research_run_protocol_v7.py)。
复用既有 v7 的 `bar / daily / index_closes / reasons`，仅合成内存数据；
V1 / X1 按 Human GO **收窄**，不是完整 V1 认证。

| 范围 / 测试 ID | 本片证据 |
|---|---|
| V1-ish：`test_simulate_full_state_parity_and_reference_identity` | symbol-frame 14:55 首买、低现金 skip、trial→four→six 加仓；默认省略 / 显式 X-02 OFF；全部 SimResult 字段深比较，交易/reason 顺序、现金、阶段/lots/权益与返回引用 |
| 失败：`test_real_native_failure_is_same_instance_once` | 短 index warmup、tail 缺 X-02 的真实 ValueError；原实例、消息与一次调用。`test_api_system_exit_is_raised_once_not_returned` 另用边界注入验证 SystemExit/cause |
| X2：`test_api_omission_mutation_and_caller_context` | 可选参数省略/None/False/空值、callable、审计 sink、native mutation、cwd/env/RNG/sys.path；spy 不算各参数组合经济效果认证 |
| 白名单 / import：`test_unregistered_entry_cannot_reach_native`、`test_fresh_import_and_v7_dispatch_are_lazy` | 错组合、虚构 run/writer 入口拒绝；新 `-I` 进程证明选中后仅加载 v7；既有 types/JR/CSV 测试原样回归 |
| X1-narrow：`test_cli_parser_exit_and_raw_bytes_without_lake` | 原 CLI 与 facade 的 help exit 0、缺参/非法参数 exit 2、缺池 exit 1；同 child cwd/env 下双流 bytes 一致，无 writer 产物 |
| CLI 边界：`test_cli_one_launch_literal_tokens_and_child_only_context` 等 | argv、负退出码、raw bytes、child-only cwd/env、缺解释器、transport failure；启动 spy 不算 writer 成功 |

**绿P = delegation parity only**，不是 SSOT 绿R / 绿S NAV 比较资格，也不授予 L2 绿C。
没有 lake E2E，没有真实行情跑数；help 成功不等于回测成功。
下列原生已允许路径均为**允许但联合效果未证实（allowed but joint effect unproven）**：

- 完整 V1 组合：X-02 chronological ON、tail ON 全表面、fee/cap/economics 组合、
  首根 gap 与买后末根 timer 的穷举、APP flags。
- CLI 加载成功至完整 writer 的真实湖字节 parity、run-config / audit 全表面，
  空池成功、输出覆盖的动态对照；本片只保留原生接线，不以静态阅读冒充验收。

`grid_modeb` 不注册、未验收；CSV↔v7 等跨引擎 NAV 混比仍不获授权。
范围外：grid adapter、views 投影、L2 MatchCore / minute_orders_backend、湖 / G8 /
strategy12 研究 / JR clock pack 重生成、production_C 或其他默认翻转、完整 V1 认证。
原引擎、fees/exdiv/fill-gates、HELP_LOCK、presets、golden、CI YAML 不改；
共享 CSV 不替换，Cerebro 禁令不变。

**勿合 / Do NOT merge without human「合」；等待 Human「合」，不启用 auto-merge。**
