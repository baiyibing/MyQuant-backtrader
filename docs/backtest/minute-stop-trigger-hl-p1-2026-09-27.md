# 分钟 H/L 止损触发 P1 实现冻结（2026-09-27）

冻结时状态：P1 在 PR，待人工「合」；现已合并 #228，不翻默认。合同见
[计划 §1 / §4](plan-minute-stop-and-exdiv-fix-2026-09-26.md)。P2 `--exdiv-ref-fen`
和 P3 在冻结时未实施；后续真湖归档见文末。

- 共享分钟入口新增 `--minute-stop-trigger {hl,close}`，默认 `close`。
  省略 / 显式 close 保留原扫描、成交价、输出；仅 hl 在 stats 写入模式。
- S1 普通扫描及独立持仓 cursor、S2 `--fix-minute-cash-order` 均接入。
  hl 用 low ≤ stop，bar 内按 stop 成交；开盘穿越按 open。
  固定目标止盈用 high ≥ target，按 target 成交，开盘越过按 open。
  同 bar 止损优先（包括开盘越过目标但 low 同时触止损）。
- 固定目标来自现有书记录的 `profit_target`（3 / 5 / 8.4 / 8.5），并由原
  take_profit 回调确认。固定目标触价不被本 bar 新高的 peak-gap 阻挡；
  利润回撤 / trail、MA、强制退出及涨停保留 / 延迟规则保持各书原语义。
  扫描 API 的固定目标参数为 `take_profit_pct`，hl 必须提供对齐的 low。
- 跌停封死 bar 不发成交候选，继续扫描后续可成交 bar；原开盘跌停禁售检查保留。
  T+0 不扫描、不更新峰值，T+1 及红股锁定继续使用原可卖股数规则。
- S2 仍按 open / close 两阶段：止损跳空在 open；H/L 触价在该 bar close
  观察并结算。固定目标也在 close 阶段评估，跳空时成交价取 open；
  不据此宣称有 tick 级先后路径。stop-before-tp 是保守 OHLC 假设。
- hl 使用 Python 路径，即使请求 numba；close 的现有 numba 快路径不变。
  止损触价审计 `price_rule=minute_stop_price`，close 保留原标签。
- hl 拒绝 version12（含别名）和 `--fix-s11-exit-domain`，CLI 在读数据前报错；
  run / simulate 同样验证。v7 仅补 HELP 声明，未注册参数，hl / close 都由
  argparse 拒绝。日线未注册参数，v7 止损实现未改。

兼容矩阵的现有边界：P1 没有针对 `--fix-s12-price-domain` 新增互斥；但是
该开关当前只允许 version12，而合同禁止 version12 + hl，所以实际组合仍拒绝。
显式 close / 默认 close 下原价格域功能不变。本刀不放宽 version12 或价格域范围。

验证使用显式解释器 `/tmp/pr206-venv/bin/python`（通过 `OSKH_MERGE_PYTHON` 指定）。
合成测试覆盖 low 触及后反弹、high 触及、止损 / 止盈跳空、跌停锁定和后续 bar、
同 bar 双触发、T+1、S1/S2 端到端、CLI/API 拒绝及默认字节一致性。
另对基线 ed80e03 的主引擎进行 12 本书 × 2 个现金模式 × 3 组价格路径比较：
72 组完整序列化 state 与当前省略参数 / 显式 close 逐字节一致。

本地回归：755 passed，2 条既有 pandas 弃用警告；四项数据无关 CI 门禁通过。

```bash
OSKH_MERGE_PYTHON=/tmp/pr206-venv/bin/python /tmp/pr206-venv/bin/python -m pytest \
  tests/test_minute_stop_trigger.py tests/test_csv_minute_backtest.py \
  tests/test_csv_minute_backtest_v7.py tests/test_csv_minute_backtest_v8.py \
  tests/test_minute_cash_*.py tests/test_scan_held_day_numba_parity.py \
  tests/test_topk_minute_exec.py tests/test_s12_price_domain.py \
  tests/test_s11_exit_domain*.py tests/test_ashare_simulate_import_fence.py -q
```

2026-09-27 后续：[P3 4090 真湖 A/B 记录](stop-exdiv-p3-ab-2026-09-27.md)（`20260927e`）已归档。
s8 hl 较 close 止损增至 348（原 334），收益略差、maxDD 相同；两个 hl 格跌停顺延各 **1**。
s12 hl 按 P1 合同 SKIP；默认仍 **close**，本记录不是默认切换 GO。
