# L1：grid_modeb / 网格退出 Mode B adapter

2026-09-28 · Human GO「开干 L1 grid Mode B adapter」· 基线
`e9a96b174b8e1cdce0c10ecb77a83bc11a2e078e`（`e9a96b1`，#247）。
这是 [JR](note-l1-jr-modeb-adapter-2026-09-28.md)、
[CSV](note-l1-csv-minute-adapter-2026-09-28.md)、
[v7](note-l1-v7-adapter-2026-09-28.md) 之后第四个 L1 adapter，落实 PLAN §3.2–3.6 / L1-S4。

## 精确注册与身份

公共入口仍为 `from backtest.research.run_protocol import run` → `run(request)`。
下列两项加入静态白名单；**既有 JR 三项、CSV 三项、v7 两项全部保留**。
无插件扫描、动态发现或新通用 CLI；family 使用 types 已冻结的 `grid_modeb`。

| family | entry_kind | native_entry（精确字符串） | native target |
|---|---|---|---|
| `grid_modeb` | `native_api` | `unified_exit_modeb.run_modeb` | `backtest.research.unified_exit_modeb.run_modeb` |
| `grid_modeb` | `native_cli` | `scripts/research/run_unified_exit_modeb.py` | 原脚本 → `unified_exit_modeb.main` → `SystemExit(main())` |

**grid_modeb ≠ JR Mode B**：前者是 unified_exit / fullstrat 网格退出实验；
后者是 `joint_return` 同冻结包的 M-REF / M-LAG fill-mode 对照。
L1 此处只委托 baseline `unified_exit_modeb.run_modeb`，
不走带 clock/slip 研究臂的 `fullstrat_research_hooks.run_modeb`，不发明 JR Mode A。

## 原生边界

- 包 / facade 导入不加载 CSV、v7、JR、grid 引擎；选中 `grid_modeb` handler 后
  才导入 adapter 及其绑定的原生入口。未知三元组先抛 `UnregisteredEntryError`。
- 每次请求整次委托一次；不 retry、不 fan-out、不拆 specs。
  assemble→matrix→aggregate→reports、`iter_grid` 窄网格、Livermore L1/L2/L3、
  SSE MA10 overlay、oracle / delist_zero / anchor_hold_end 全留原主干。
- 保留每实例 / 每 spec 权益口径；adapter 不建立共享现金账户、不另聚合跨实例组合。
  原 `cash_pool` 等参数继续由 native 使用；不统一 CSV/JR/v7 账本。
- `args/kwargs` 原样展开，嵌套引用与 native mutation 保留；省略 ≠ None ≠ False ≠ 空值。
  pool / sessions / bars / minute_bars / exdiv / index_block / cash_pool / tol / workers
  由 native validator 决定，facade 不补默认、不 chdir、不改 env / PYTHONPATH、不 reseed RNG。
- API 返回 dict 及 ranked / anchors / robustness / instances / matrix / sessions 原引用。
  报告是 native 写入 `out_dir` 的副作用；dict 不返回路径，artifact refs 保持 `OMITTED`，
  不扫描目录猜路径。原生拒绝 `unified_exit_modea` 输出目录的验证保留；adapter 不 mkdir、清空或改名。
- API 原异常（含 ValueError / SystemExit）同一实例继续 raise，不包成成功或异常返回 envelope。
- CLI `argv` 仅为参数尾部；数组启动白名单脚本绝对路径，不经 shell。
  `resolve_oskh_python()` 在父上下文选解释器，缺失即失败；不回落系统 Python。
  相对解释器锚定父 cwd，保留虚拟环境符号链接。默认继承 cwd/env，显式覆盖只给子进程。
  返回原 exit status 与 stdout/stderr bytes；启动失败直接传播，不冒充 native exit。
  CLI artifact refs 同样保持 `OMITTED`。

## 本片无数据验收（B1 / X1 收窄）

测试：[test_research_run_protocol_grid_modeb.py](../../tests/test_research_run_protocol_grid_modeb.py)。
复用既有 aggregate 测试形状：两次同码入池、五个合成 session、固定价日线/分钟，
显式 `exdiv={}` / `index_block={}`；只读临时池 CSV，不读湖或真实行情。

| 测试 ID / 范围 | 证据 |
|---|---|
| `test_full_pipeline_parity_identity_and_one_shot` | 原生 vs facade 独立 out_dir 完整 run；六个 dict 键深比较与返回引用；23 ranked、全部 spec/实例矩阵、四 anchors、half-window top20 与稳健性；一次委托不拆 specs |
| 同上 writer | 本合成输入的 summary.json / ranking.csv / instance_detail_top.csv 集合及 bytes 一致，无路径/耗时 scrub；确认 native meta mode B / Q38=A / minute coverage 与 sell_hm |
| `test_real_native_failure_is_same_instance_once` | 真实 out_dir 原生 ValueError，同实例、原消息、一次调用、无预建目录 |
| `test_api_system_exit_is_raised_once_not_returned` | 边界注入 SystemExit/cause 原样 raise |
| `test_api_omission_mutation_and_caller_context` | tol 省略/None/False/空值、嵌套引用与 mutation、cwd/env/RNG/sys.path；spy 不认证这些值的经济效果 |
| `test_unregistered_entry_cannot_reach_native` / `test_fresh_import_and_grid_modeb_dispatch_are_lazy` | 错 family/transport/entry、局部核/研究 hooks 拒绝；新 `-I` 进程仅在 dispatch 后加载 grid 引擎，不加载 JR/CSV/v7 |
| `test_cli_parser_exit_and_raw_bytes_without_lake` | 原 CLI vs facade：help exit 0、非法 workers / 禁止输出目录 exit 2；同 child cwd/env 双流 bytes 一致，无 writer 产物 |
| CLI 其余边界测试 | 单次启动、字面 argv、负退出码/raw bytes、child-only cwd/env、缺解释器与 transport failure |

既有 types / JR / CSV / v7 测试原样回归，另跑四项 CI data-free gates。
**绿P = delegation parity only**；不是 SSOT 绿R / 绿S，不授予跨引擎 NAV 比较或 L2 绿C。
没有 lake E2E；help 成功不等于完整 CLI writer 成功。

以下原生允许路径均为**允许但联合效果未证实（allowed but joint effect unproven）**：

- 真实湖 CLI 加载至完整 writer / 默认日期窗口 E2E 与其字节 parity。
- 本合成路径之外的 Livermore / index-overlay / exdiv、缺根/到期/shares-k 等全部组合。

范围外：跨引擎 NAV 比较；注册或认证 `evaluate_exit_modeb(impl=fast|ref)` 为 L1 入口
（它只是局部核验接缝，也不是 `run_modeb` 的 impl 参数）；L2 / views；湖、G8、
JR clock pack 重生成、production_C 或默认翻转、完整组合认证。
原引擎、fees/exdiv/fill-gates、HELP_LOCK、presets、golden、CI YAML 不改；
共享 CSV 不替换，Cerebro 禁令不变，`production_C=frozen`。

**勿合 / Do NOT merge without human「合」；等待 Human「合」，不启用 auto-merge。**
