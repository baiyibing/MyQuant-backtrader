# minute_orders_research：L2-S5 注册到 L1

2026-09-29 · **L2-S5 / Human GO / synthetic research only** · 基线 `74e895e`（#254，L2-S4）。
Human：「下一默认刀是 L2-S5 注册到 L1===GO」。冻结记录：
`/workspace/handoffs/l1_l2_research_engine_l2s5_20260929/HUMAN_GO.md`；
计划：`/workspace/handoffs/l1_l2_research_engine_plan_20260928/PLAN_L1_L2_RESEARCH_ENGINE.md`
的「L2-S5 注册到 L1」切片。`production_C=frozen`。
PR 后交 Human/Grok review；**Do NOT merge without human「合」；不启用 auto-merge**。

后续 Track A（2026-09-29 Human「A GO」，基线 `6cd29e6`）已新增专用 CLI 与该脚本唯一一条 L1 `native_cli` 注册，见 [CLI 使用及退出合同](note-minute-orders-cli-2026-09-29.md)。下文“不注册 CLI / 无 CLI 产品化”记录 S5 当时切片边界；两条 API、synthetic-only 及比较权限保持。

## 显式身份与白名单

L1 family 新增 `minute_orders_research`，指向现有 backend `minute_orders_research_v1`。
这是独立研究家族；CSV / v7 / joint_return / grid_modeb 的原入口、writer、pins 与默认均保持。
`run(request)` 只按 `(family, entry_kind, native_entry)` 三元组精确匹配：

| family | entry_kind | native_entry（精确字符串） |
|---|---|---|
| `minute_orders_research` | `native_api` | `minute_orders_backend.runner.run_minute_orders_research` |
| `minute_orders_research` | `native_api` | `minute_orders_backend.runner.run_minute_orders_research_with_artifacts` |
| `minute_orders_research` | `native_cli` | `scripts/research/run_minute_orders_research.py` |

两条 API 仍委托 `backtest.research.minute_orders_backend.runner` 的对应函数。
不注册独立 writer 或短名别名；`native_cli` 仅注册表中脚本，未知组合仍抛 `UnregisteredEntryError`。
API / CLI 请求载体继续分型；能构造 CLI 请求不等于已登记 CLI 能力。
family 必填，无默认选择器，无旧家族失败转 L2，无插件发现或 fallback。
导入 `run_protocol`、facade registry、adapters 包乃至新 adapter 模块都不加载引擎；
只在选中 entry 并调用时导入 native runner，其他家族不随之加载。

## 调用与结果

```python
from backtest.research.run_protocol import NativeApiRequest, run

# run_input 是调用方显式提供的 S3 RunInput；不读取湖或生成策略订单。
result = run(NativeApiRequest(
    family="minute_orders_research",
    native_entry="minute_orders_backend.runner.run_minute_orders_research",
    args=(run_input,), kwargs={},
))
native_result = result.native_value

# 单独选择 S4 wrapper；parent、run_id、evidence_level 均由调用方提供。
written = run(NativeApiRequest(
    family="minute_orders_research",
    native_entry="minute_orders_backend.runner.run_minute_orders_research_with_artifacts",
    args=(run_input,),
    kwargs={"parent": parent, "run_id": "synthetic-l1", "evidence_level": "synthetic"},
))
```

每个请求只委托一次。原 args/kwargs 直接展开，内容保留引用；键省略、None、False、空值
不被归一化，不填原生默认，不复制 RunInput/RunResult，不切 cwd/env，不额外运行撮合。
两个 API 都返回 `ApiResult`，其 `native_value` 就是 native 返回的同一对象。

- 内存 entry：保留完整 RunResult；`native_artifact_refs=OMITTED`，不落盘、不扫描目录。
  原 engine 异常继续抛出，包括相同异常实例及 `SystemExit`；不转成 ApiExceptionResult。
- 磁盘 entry：保留 S4 `ArtifactWriteResult`，refs 仅为 native 返回的 `(value.root,)`。
  仅按显式参数创建 `<parent>/backtest_output/minute_orders_research_v1/<run_id>/`；
  缺少必填参数仍 TypeError，既有根仍 FileExistsError，不清空、不复用、不补 failure。
  `code_sha` 等可选 kwargs 原样透传；不把 L1 family 注入原生输入或工件。
- S4 wrapper 原本会将普通 engine Exception 归档为 `status=failed`，这项原生语义保持。
  L1 envelope 的 `status=returned` 仅表示函数返回；调用方须读 `native_value.status`，
  不能把 failed 归档当成功回测。writer 抛出的异常及 SystemExit 继续传播，不重试。

原生合同、artifact schema、成功 summary 最后发布与失败证据规则，分别见
[S3](note-l2-s3-clock-broker-runner-2026-09-29.md) 与
[S4](note-l2-s4-artifacts-isolation-2026-09-29.md)；本片不改这些实现。

## 合成验收与能力边界

[test_research_run_protocol_minute_orders.py](../../tests/test_research_run_protocol_minute_orders.py)：

| 验收面 | 证据范围 |
|---|---|
| 原生完整结果 | 复用 S3 共享容量/partial/expiry 与 S4 累计费/cancel 合成输入；完整 dataclass 深比较、返回引用、单次委托、输入/cwd/env 保持、内存无文件 |
| 原生失败 | 输入校验和首笔成交后 mark 失败；原异常实例、类别/参数继续传播；两 entry 均不吞 SystemExit |
| 显式磁盘 | success/failed 两路径，省略/None/显式 code_sha；两个 temp parent 下同 run_id 全部文件 bytes 一致，kwargs 值保留引用，refs 来自真实 root |
| 拒绝边界 | 必填输出参数不补默认；空目录或带文件的既有根不覆盖；错 family/entry、CLI、独立 writer 均不获注册 |
| 惰性导入 | 独立 `-I -S` 进程 import fence；注册和 adapter 导入不加载 backend，缺参 dispatch 才加载 runner，不加载旧引擎/数据层/writer；有效磁盘调用仍由 native wrapper 导入 writer |

types 测试把新 family 纳入 API/CLI 载体 round-trip；旧四家 adapter/views 测试与
S1–S4 原测试按原义回归，旧测试 pins 不修改。全部输入为合成数据，落盘仅临时目录。
本片定向回归 **616 passed**；四个既有 data-free contract/path/TR gates 均通过。

**绿P = 本 family 的 facade ↔ 相同 native entry 委托 parity；绿C 仍是 L2 新合同 oracle。**
注册不授予 SSOT **绿R/绿S**，不把绿C/绿P升级为收益或实盘资格。
工件 `comparison_status=no_ssot_compare_authorization` 保持；L2 NAV 不自动与
CSV / v7 / JR / grid 排名或混比，也不自动接入 L1 views 的 NAV 声明。
无湖验证、无真实数据接入、无 CLI 产品化、无 vendor、无 production_C/fees/exdiv/fill-gates 改动。
HELP_LOCK、CI、presets、golden 与四家原生引擎/writer 保持。

回滚只撤新 family、两条注册及新 adapter；L2 原生 API 仍独立可用，旧四家不受影响。
