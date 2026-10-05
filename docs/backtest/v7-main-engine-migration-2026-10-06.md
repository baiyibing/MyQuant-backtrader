# v7 / APP 主分钟引擎迁移（2026-10-06）

六片迁移收口：`csv_minute_backtest.simulate` 拥有 version7 的状态、日历与日循环，
`minute_cash_order` 拥有 symbol-major 默认和 X02 chronological 两种调度。
`strategy7_engine` 保留输入转换、原生 Lot / Position / SimResult、聚合费用、
逐事件规则与分钟收盘估值；APP CLI / host 经 `simulate_native` 使用同一执行书。
version7 仅 minute-only 注册，未加入共享 CLI / 日线 BOOKS。

PR 6 基于 PR 5（rebase 后）`e95838f`：`simulate_v7` 保留原签名、默认值、未知参数拒绝与
SimResult，薄转发到 `simulate_native`。转换适配器按原 shim 顺序先执行
`validate_tail_options`，启用尾盘时再执行 `resolve_tail_volume_unit`（None → shares），保证
facade 无效请求仍在加载 main 前失败；main 保留自身校验。`rg` 确认旧
`_DayCursor` / `_run_chronological_day` 已在前片删除，无生产引用；本片移除
无引用的旧循环 imports。loaders / parser / CRLF writers 与研究所用重导出保留。

人裁全部 A：保留两种调度及默认 symbol-major；v7 / APP 资金不足 skip；
卖出涨跌停仅检查成交价；FeeSchedule 聚合、Lot T+1 / 加权成本、分钟收盘
mark + receivable 与原生 CLI / flags 保持。APP 独立 CLI 与 500m 默认保留；
version11 不动。没有新增公开成交配置或变更 help。

字节证据使用 `/tmp/pd3venv/bin/python`（pandas 3.0.6）：
`tests/test_v7_app_optin_baseline.py`、`tests/test_off_byte_baseline.py` 与
`tests/test_v7_minute_fold.py` 对照冻结结构、canonical、CSV / summary / audit /
config 原始产物；直接 main 与 shim 的默认、X02 / X04 等录制案例一致。
新增 guard 锁定无生产 for / while 调度、两种 flag 进入 main、相同 SimResult
类型、尾盘单位归一化与 shim / APP 异常类型及消息顺序。fixtures 未改、未重录。

PR 6 本机验收（全部用上述解释器，串行）：

- `-m pytest -q tests/test_v7_app_optin_baseline.py tests/test_off_byte_baseline.py`：
  289 passed，零 skip。
- `-m pytest -q tests/test_v7_app_optin_baseline.py tests/test_off_byte_baseline.py
  tests/test_v7_minute_fold.py tests/test_csv_minute_backtest_v7.py
  tests/test_v7_cash_chronology.py tests/test_v7_frame_calendar.py
  tests/test_tail_window_v7.py tests/test_tail_window_peak_audit_regressions.py
  tests/test_minute_bar_scan_host*.py tests/test_minute_host_simulate_route.py
  tests/test_topk_app_dropout.py
  tests/test_research_run_protocol*.py tests/test_fullstrat_research_hooks.py
  tests/test_minute_classification_guard.py`：1228 passed，零 skip。
- `-m pytest -q -m "not production and not benchmark"`：12 个 collection errors，
  解释器缺 `duckdb` / `numba`；全套未通过。离线缓存仅有 cp312 二进制，当前为
  Python 3.13，未安装依赖、未联网、未修改无关测试。
- `git diff --stat e95838f -- tests/fixtures` 为空；parser / shim 签名与 base
  AST 相同，触及文本 UTF-8 / 无 BOM / NUL=0。

研究路径继续隔离：fullstrat 默认 → v7 shim → main；非默认 clock / slip 仍走
`fullstrat_research_v7` 实验调度，未修改。fullstrat Book / Mode B、统一卖出
Mode B、joint-return、minute_orders 和本地 sensitivity replay 继续保持各自
显式研究合同。本次合成基线不构成真湖认证。

PR 6 拒绝后补充 import 审计（全仓，含 fullstrat / run_protocol / scripts / tests）：

```sh
rg -n --hidden -g '!.git/**' '\b(TailParent|VolumeCap|tail_quote|TAIL_MINUTES|TAIL_START|_in_session|dataclass|field|isfinite|audit_scope|record_fill|resolve_tail_volume_unit)\b' .
rg -n --hidden -g '!.git/**' 'csv_minute_backtest_v7|\bv7\.' backtest scripts tests
```

逐项交叉核对结果：上述 12 个删除的 import 名称均无从 v7 导入或通过 v7 属性
访问的消费者；Python AST 补查多行 `ImportFrom` / 星号导入，结果 `[]`。
`fullstrat_research_v7.py:9` 使用模块别名 v7；其全部属性引用仍有对应重导出
（输入转换、SimResult、费用、规则、经济权益与买卖 helpers），无需恢复上述 import。
