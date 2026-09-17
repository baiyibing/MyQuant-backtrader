# Codex 交接：Mode A 性能票 + plateau r3 nit

> **日期**：2026-09-17
> **状态**：✅ 可实施（宿主切片 D 短记已开 PR #91；本交接不依赖 #91 合入，锚 master `835cc63`）
> **权威**：[`unified-exit-modea-host-note-2026-09-17.md`](https://github.com/baiyibing/MyQuant-backtrader/blob/docs/unified-exit-modea-host-note/docs/backtest/unified-exit-modea-host-note-2026-09-17.md) §4（PR #91）· `backtest/research/unified_exit_modea.py`
> **分支**：`feat/unified-exit-modea-perf`（本工作树）
> **目标**：Mode B 前置——日线网格从 ~72min 单核压到分钟级量级；顺手修 plateau 漏 r3。

## §0 硬边界

1. **只动** `backtest/research/unified_exit_modea.py` + 对应 `tests/test_unified_exit_modea_*.py`（必要时 CLI 零改）。
2. **禁止**改成交核 / `csv_*` 引擎 / 策略书 / 湖路径 / Mode B 分钟逻辑（本票不做 Mode B）。
3. **语义不变**：同一合成 fixture 下 ranking / total_return / max_drawdown / plateau 布尔（修 r3 后期望变准）位级一致；仅允许 plateau 对 r3 标签从「跳过」变为正确邻域检查。
4. 遇语义分叉停下来报告，不自裁。不 merge。

## 切片 A — plateau 覆盖 r3（小 nit）

**锚点**：`neighborhood_plateau_flags`（约 L805+）；宿主短记：top20 #17 `r3_y10_n10` 未被解析。

步骤：
1. 扩展标签解析：`r1_n*` / `r2_x*_y*_n*` / `r3_y*_n*`（及现有 x/y/n 邻域规则）。
2. 单测：构造含 r3 的 top20 ranked，断言该行有 plateau 字段且不抛；r2 既有断言不回归。
3. 一 commit。

## 切片 B — 向量化日期/收盘缓存（性能）

**锚点**：`date_to_ymd`（L39）、`_bar_close_map`（L123）、多处每策略×每日×每股热循环；py-spy：纯 Python 日期转换。

步骤：
1. 预计算：每个 bar DataFrame → `dict[str,float]` **一次**（或 `index.strftime("%Y%m%d")` / 整数 yyyymmdd 数组），全网格复用；禁止在内层循环反复 `date_to_ymd(idx)`。
2. 若 half-window 稳健性重复扫全窗净值：复用主聚合增量或缓存，避免整表重算。
3. 单测：既有 Mode A assemble/exit/aggregate 全绿；可加「同输入两次 close_map 相等」探针。
4. 不要求本环境跑真湖 72min；合成路径墙钟可附注释量级。
5. 一 commit。文档：在 handoff 或短注一行写「性能票落地、Mode B 仍另开」。

## 门禁

```
uv run --with pytest --with pandas --with pyarrow pytest -q \
  tests/test_unified_exit_modea_assemble.py \
  tests/test_unified_exit_modea_exit.py \
  tests/test_unified_exit_modea_aggregate.py
```

UTF-8 无 BOM。开 PR 指向 master；回写本交接状态表。遇阻停下。
