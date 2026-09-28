# L1-Slast：可选只读 Order / Fill / Portfolio views

2026-09-29 · Human GO **「先做 L1 views」** · 基线 **`170bb39`**（#249 后）。
点名消费者：**joint_return / bt 离线研究编排**，读取已经取得的 JR 原生订单、成交与组合证据。
这是 PLAN §3.4 与 **L1-Slast views（可选）** 切片；`production_C=frozen`。
GO：`/workspace/handoffs/l1_l2_research_engine_l1_views_20260929/HUMAN_GO.md`；
PLAN：`/workspace/handoffs/l1_l2_research_engine_plan_20260928/PLAN_L1_L2_RESEARCH_ENGINE.md`。
这两条是本机 handoff 路径，不是仓内可移植链接。

## 调用与来源

实现：[`views.py`](../../backtest/research/run_protocol/views.py)。四个入口均 **opt-in、只读、只在内存**：

```python
from backtest.research.run_protocol import project_orders, project_fills, project_portfolio

# native 是已经取得的结果；source 是调用方提供的真实来源文件名，缺失时省略。
orders = project_orders("joint_return", native, run_id="my-run")
fills = project_fills("joint_return", native, run_id="my-run")
portfolio = project_portfolio("joint_return", native, run_id="my-run")
if fills.rows:
    quantity = fills.rows[0].quantity  # Evidence(value, provenance, unknown_reason, derived)
    fee = fills.rows[0].fee           # 缺失 → value=None + field_missing，不补 0
```

`family` 使用现有 `csv_minute / v7 / joint_return / grid_modeb` 标签。
输入为 native mapping/dataclass；订单、成交、JR daily NAV 也接受预先加载的 list/tuple 记录。
`ApiResult` 请显式取 `.native_value`；Path/CLI 结果不自动加载，JR `run_replay()` 返回目录也不扫描。
不接受 DataFrame 自动转换、数值字符串自动解析或任意 live 对象；不支持的值明确 TypeError。
调用方若加载 CSV/JSON，应自行保留嵌套结构和所需数值表示；views 不复原已丢失的精度。

返回 `Projection.rows` 为不可变 tuple；无集合时 `unknown_reason` 说明原因，
显式空集合与未知缺失分开；被排除的非成交行记在 `excluded`，带原行来源和原因。
每行保留 `provenance` 和冻结的 `native_fields`；通过 `.field("原字段", ...)` 取得字段证据。
例如 `.field("positions", 0, "sellable_quantity")` 保留持仓原位置，不按代码合并。

来源含 **family + run_id + source_file + path**。`path` 是原集合名、零基记录索引、字段/嵌套路径；
直接传记录列表时从索引开始；索引不是含表头的 CSV 物理行号。
字典 key（如 Mode B spec/instance）本身也是可反查的原生身份。
`source` 原样登记、不验证存在、不猜文件；一组记录应来自同一所指来源，跨文件请分别投影。
未提供文件或 run_id 时，`None` 搭配 `source_file_not_supplied / run_id_not_supplied`；
行内真实 `run_id` 优先补足行来源，与显式 run_id 冲突则 ValueError，集合级来源仍反映调用参数。
字段缺失为 `field_missing`，显式 None 为 `native_null`，真实 0/False/空容器保持原值。
**unknown ≠ 0，unknown ≠ OFF**；本片不生成观察 ID，真实 ID 的 `derived=False`。

## 家族边界

| 视图 | 已实现范围 / 禁止推导 |
|---|---|
| OrderView | 仅显式 `orders`；JR 原 order_id/status/数量/时钟/transitions 均保留原字段。其他家族无 orders 时空 rows + `family_has_no_order_lifecycle`；不从 trades/instances 补 submit/accepted |
| FillView | JR `fills` 使用 `executed_quantity`；CSV/v7 `trades` 使用 `shares`。仅原 BUY/SELL 正增量；JR 还需原 FILLED/PARTIAL 状态。保留数量/价格/lot/position/instance、reason 与逐行粒度，不差分累计成交 |
| 费用 | JR/v7 只读 `fee`；CSV 只读 `commission` 并保留该来源字段名，不声称含全部税费。v7 缺列不补 0；不从 cumulative_fee/费率反算，不二次扣钱 |
| AccountPortfolioView | JR 每条 `daily_nav` 各保留 arm_id/fill_id、NAV/cash/positions/sellable/mark 证据；CSV/v7 仅当前 cash/positions/equity_curve。保留 S8 同码多信号日与 lot，不重算可卖量 |
| GridInstancePortfolioView | Mode B `matrix[spec][instance]` 独立记录；`instances` 另保留原条目，未报告 instance_id 不拼接生成、spec 未绑定即 unknown |
| GridSpecPortfolioView | 仅保留 `ranked` 中原 spec 指标与顺序；不重新排序、不合成共享现金/NAV。grid 退出/mark 记录不自动变增量 fills |

SKIP / REJECT / EOD_MARK / MARK / mark_end 一律不能成为 fill。
JR Decimal 输入保持 Decimal 及精度，不转 float、不重算；CSV float 也不改 Decimal。
注意现有 JR 公共 `replay()` 自带 `plain()` 表示边界，已返回 float 时原样保留；
这不授权 views 修改 native 边界或从 float 反造 Decimal。

`project_time_evidence(family, native_record, *, run_id=None, source=None)` 分列
`schedule_parameters` 与 `effective_clocks`，每项均有 Evidence；也可传现有 view 以复用原行来源。
只读传入的平面参数/时钟字段，不解析 manifest/argv，不自动补默认；
`X-02=False` 不推断 legacy，open 价格不推断 booked_at，actual_fill_at 不代填 match_at。
缺少 quote/available/decision/submit/match/booked 等证据时保持 unknown，不借 mtime/ts_init 补 PIT。

## 不变性、验证与止步

结果递归冻结 mapping/list/dataclass；不持有可写 native 容器，不调用持仓属性来计算数量。
投影不改变输入对象的内容或身份，不 chdir、不触碰 os.environ，不运行引擎、不调用 writers。
包导入仍只加载既有 types；显式访问 view 导出才惰性加载 views，亦不加载 facade/adapters/engines。
**`run()` 与 adapters 完全不变，不调用 views 时 native artifacts 保持 byte-identical；无 sidecar。**

新测试 [`test_research_run_protocol_views.py`](../../tests/test_research_run_protocol_views.py)
用手写合成字典/列表/dataclass 验证来源、Decimal、unknown/零、标记过滤、实验分型、嵌套冻结与隔离 import。
同时回归原五个 run_protocol 测试文件，保留其 native 委托/工件一致性验证，不改旧测试或 golden。
**绿P 仍仅表示已钉范围 delegation parity；views 不授予绿R/绿S，不允许跨家族 NAV 加总、归一化或排名。**
范围外：**L2-S1、任何 L2 可执行实现、lake/真实 clock packs、writers/sidecars、adapter/白名单变更**，
以及 fees/exdiv/fill-gates、production_C、HELP_LOCK、presets、CI 和 golden 修改。
本 PR **Do NOT merge without human「合」／勿合**；L2 可执行代码仍须独立切片 GO。
