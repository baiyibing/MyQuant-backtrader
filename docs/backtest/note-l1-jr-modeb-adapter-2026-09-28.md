# L1：joint_return Mode B adapter

2026-09-28 · Human GO「开干 L1 joint_return Mode B adapter」· 基线
`61020f96d53a792f22a299464f435e3f012527e4`（`61020f9`，L1-S0 #244）· `production_C=frozen`。

Human Q1 钉定 **joint_return Mode B 入口 = JR 的 M-REF / M-LAG**，
覆盖 native 允许的 `all`；覆盖原 PLAN 的 CSV 首片顺序。
本片落实 PLAN §3.3–3.6，承接 [S0 类型合同](note-l1-s0-run-protocol-types-2026-09-28.md)
及 [P0 产品边界](note-l1-l2-research-engine-boundary-2026-09-28.md)。
这里的 Mode B 与 `unified_exit_modeb` 卖出网格不同；**`grid_modeb` 未注册**。

## 精确入口

公共调用：`from backtest.research.run_protocol import run`，然后 `run(request)`。
静态白名单只含下表三项；未知 family、transport 或 entry 抛 `UnregisteredEntryError`
（位于 `run_protocol.facade`），在加载 adapter / 调用 native 之前失败。

| family | entry_kind | native_entry（精确字符串） | native target |
|---|---|---|---|
| `joint_return` | `native_api` | `joint_return_replay.replay` | `backtest.research.joint_return_replay.replay` |
| `joint_return` | `native_api` | `joint_return_replay.run_replay` | `backtest.research.joint_return_replay.run_replay` |
| `joint_return` | `native_cli` | `scripts/research/run_joint_return_replay.py` | 原脚本 → `joint_return_replay.main` → `SystemExit(main())` |

CLI 的 `request.argv` **仅为参数尾部**，不含解释器、`-m` 或脚本名。
adapter 以数组启动白名单脚本的仓内绝对路径，不用 shell、不解析或改写 tokens。
解释器由 `resolve_oskh_python()` 在父进程上下文选择：优先
`OSKH_MERGE_PYTHON → VANNA312_PYTHON → VANNA311_PYTHON`，其余遵循既有 helper；
缺失即失败，不回落系统 Python。相对解释器路径先锚定父 cwd，保留虚拟环境符号链接。
cwd/env 默认继承；显式 `CliContext.cwd/env_overlay` 仅传给子进程。

## 保持原生合同

- 包仅在访问 `run` 时加载 facade；包 / facade 导入均不加载 adapter 或四家引擎。
  API 选中 JR 后才导入 JR；CLI 的 JR 导入发生在原脚本子进程。
- 每请求整次委托一次；不重试、不并发拆分，不把 `arm=all` / `fill_mode=all` 拆成 facade 调用。
- API 直接展开原 `args/kwargs`，不复制其中对象、不补默认；键省略与 None / False / 空值保持。
  不切 cwd、不改全局 env / PYTHONPATH、不重设 RNG；原生 mutation 仍可见。
- `ApiResult.native_value` 保持 native 返回对象引用；Decimal 不由 L1 转换或重算。
  注意 JR 自己的 `plain()` 会把输出 Decimal 转成 float；L1 保留这一本来就有的表示。
- 原 API 异常（含 `ReplayError`、`SystemExit`）直接传播，同一实例，不返回异常 envelope 代替 raise。
  CLI 返回原 exit status 和 stdout/stderr bytes；启动失败直接传播，不冒充 native exit。
- `run_replay` 成功后仅报告 native 返回的完成目录引用，不扫描文件、不推测 profiling sidecar；
  `replay` / CLI 的 artifact refs 保持 `OMITTED`（未知/未报告，并非无产物）。
- arm / fill_mode 必填、v1 默认 / 显式 v2 均交原 validator；输出目录 basename=MQ run_id、
  已存在目录（包括空目录）拒绝、四工件及 `summary.json` 最后写均交原 writer。

## 无湖验收范围

[`test_research_run_protocol_joint_return.py`](../../tests/test_research_run_protocol_joint_return.py)
复用既有 `bundle/minute_bars/seal/write_bundle` 与 `frozen_bundle/frozen_marks/write_frozen_bundle`。
`frozen_marks` 的 `source_kind=lake_bar` 是既有**合成证据标签**，并未访问湖或验证真实来源。

| 验收 | 本片证据 |
|---|---|
| API parity | 合成 / frozen 合成包，P-BASE × M-REF/M-LAG/all，默认 v1、显式 v1/v2；完整返回 dict 深比较与原对象身份 |
| 原生展开 | 合成包 arm=all / fill_mode=all 只调用一次 native replay；原生负责分臂 |
| writer parity | 合成 / frozen 包，三种 fill 选择，默认 v1 / 显式 v2；隔离输出目录，四文件集合及 bytes 全同，完成标志最后写 |
| CLI parity | 两类包的三种 fill 选择成功 exit 0；缺 bars 原生 INPUT_BLOCKED exit 2；parser stderr bytes、相同参数流与 child cwd |
| 失败 / 上下文 | 原异常实例与 cause/context、原生目录拒绝、缺解释器 / launch failure、字面 tokens、child env overlay、负进程状态 |
| import / 边界 | 新 `-I -S` 进程验证惰性导入与选中才加载 JR；未知入口拒绝；省略/Decimal 引用及 caller cwd/env/RNG/sys.path 保持 |

profiling 保持 OFF，四工件没有需豁免的时间字段；CLI 对照使用相同相对输出名、不同 child cwd，
因此 stdout 路径也可逐字节比较。没有重录 golden，S0 测试原样保留。
上述是 **绿P = delegation parity only**；不是 SSOT 绿R / 绿S NAV 比较资格，也不是 L2 绿C。
未覆盖的 native 允许组合仍可原样转发，但 **allowed but joint effect unproven（允许但联合效果未证实）**；
不宣称所有 JR arm、pack 格式、公司行动 / 容量组合、profiling 或真实数据路径均已认证。

本片范围外：CSV / v7 / grid adapters、views 投影、L2 / MatchCore / minute_orders_backend、
lake / G8 / strategy12 / JR clock pack 重生成、production_C 或其他默认翻转。
旧引擎、HELP_LOCK、fees / exdiv / fill-gates、presets、golden 和 CI 配置不改；共享 CSV 不替换，Cerebro 禁令不变。

**勿合 / Do NOT merge without human「合」；等待 Human「合」，不启用 auto-merge。**
