# L1-S0：run_protocol 类型合同

2026-09-28 · Human「开干 L1-S0 types-only」· 基线 `d2b5a39547eb11fe5a0b0bfdf871446a03c3c68d`（#243）· `production_C=frozen`。

本片落实外部 PLAN §3 与 L1-S0 行，只交付类型、契约测试和本说明；
[P0 产品边界](note-l1-l2-research-engine-boundary-2026-09-28.md) 的其他门禁继续有效。
外部计划：`/workspace/handoffs/l1_l2_research_engine_plan_20260928/PLAN_L1_L2_RESEARCH_ENGINE.md`（本机 handoff，非仓内可移植链接）。

## Q1 与认证范围

Human Q1 点名的首个消费者 / 首版认证范围是 **「joint_return Mode B 入口」**。
后续首个 adapter 切片优先 `joint_return` 家族的 Mode B 相关 native 入口；
`grid_modeb` 继续单列，以免与 JR 的 M-REF/M-LAG 混名。
具体 native symbol(s) 及是否包含相邻 grid Mode B 路径，由首个 adapter GO 钉定。
本片没有注册可运行入口，也没有完成任何家族的委托认证。

## 冻结的形状

公共类型见 [`run_protocol/types.py`](../../backtest/research/run_protocol/types.py)，
包入口仅重导出这些类型；所有 dataclass 都是 `frozen=True` 的浅层 envelope。

| 项目 | 合同 |
|---|---|
| `Family` | `csv_minute / v7 / joint_return / grid_modeb`；标签存在不等于已注册、可用或已认证 |
| `EntryKind` | 仅 `native_api / native_cli`；两种 request 各有不可在构造时改写的固定 tag |
| `NativeApiRequest` | `family + native_entry + args + kwargs`；原容器、原对象按引用保留，无复制、转换或补默认 |
| `NativeCliRequest` | `family + native_entry + argv + context`；argv 是 list/tuple token 数组，保存原脚本/模块的参数尾部，不含解释器与 launcher，顺序、重复、空 token 和路径字面量保持 |
| `native_entry` | 尚未解析的入口标识；S0 不做注册/动态 import，后续 adapter 必须用静态白名单并分别钉 API / CLI 接缝 |
| `CallerContext` | API 固定继承调用方 cwd/env，不提供覆盖字段或构造时替换 context |
| `CliContext` | 可显式给 cwd/env_overlay，未来只供子进程；省略则继承，overlay 值只允许字符串（含空串），不定义删除变量 |
| `NotRunResult` | `request + status=not_run`，没有 native 返回值或退出码，不能冒充一次运行 |
| `ApiResult` | `request + 必填 native_value + status=returned`，允许原生显式返回 None/False/空对象，不推断业务成功 |
| `ApiExceptionResult` | `request + 必填 native_exception + status=raised`，保存同一 BaseException 对象，包括 SystemExit |
| `CliResult` | `request + 必填 native_exit_status/stdout_bytes/stderr_bytes + status=exited`，保留非零、负状态与原 bytes，不设 success 布尔值 |

`NativeRunRequest` / `NativeRunResult` 是上述分型的 union；result 引用原 request，保留家族与入口身份。
Literal 是静态类型合同，dataclass 不提前校验 native 参数；S0 无可执行 dispatcher。
冻结只限制 envelope 字段重绑；args/kwargs/argv、返回值和异常内部仍属调用方/native，允许原生既有 mutation。

## 省略、上下文与失败

原生 API 参数采用 **kwargs 键存在性**：`{}` 表示没传，`{"x": None}`、`{"x": False}`、
`{"x": ""}`、`{"x": []}` 分别是显式值；不以 truthiness 回填参数，不向 native kwargs 塞 sentinel。
CLI 不解析 token 来合成 API kwargs，也不从 API 参数生成 flags。

协议元数据用 enum 单例 `OMITTED` 表示未提供，与 None/False/空容器不同；
CLI cwd/env_overlay 的合法显式值由类型限定，不接受 None 作为第二种“继承”标记。
`ApiResult` / `CliResult` 的 `native_artifact_refs=OMITTED` 表示未知/未报告，
显式 `()` 才表示报告无工件；引用只能来自真实 writer 或显式输出请求，不扫描或猜文件。
类型构造和 import 不读湖、不切 cwd、不修改全局 environ，不选择/启动解释器，不采集完整环境到工件。

异常 envelope 仅作观察载体，**不允许未来 API adapter 吞异常并返回它代替 raise**。
下一片必须证明整次请求只委托一次、原异常同一实例重抛及其副作用保持，不 wrap/retry；
CLI 启动失败也不能填一个 native exit 冒充完成。
S0 不提供运行函数或空成功 stub，类型测试不能证明一次委托已经实现。

## 验证与止步位置

[`test_research_run_protocol_types.py`](../../tests/test_research_run_protocol_types.py) 锁定省略与显式空值、
四家/双入口 tag 往返、原生对象/Decimal 引用、CLI token/context、未运行与真实返回的分型、
异常身份/链及 CLI 原状态/bytes；隔离新进程分别测包导入和 types 导入的 `sys.modules` 增量，
只允许 stdlib 与协议包及空父包，禁止加载四引擎或 loader。

该新进程只验证 import，不运行原生 CLI；测试不调用 JR/Mode B runners，不跑湖。
本片没有 facade/adapters/views、L2 代码、NAV 对照或绿P/绿C 声明；
旧入口、HELP_LOCK、fees/exdiv/fill-gates、presets、golden 与 CI 均不改。
后续切片另获 GO；本 PR **Do NOT merge without human「合」**。
