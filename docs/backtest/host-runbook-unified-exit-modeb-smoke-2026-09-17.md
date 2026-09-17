# 模式 B · 宿主分钟数据就绪 runbook（smoke；无需 Mode B 代码）

> **日期**：2026-09-17
> **状态**：✅ **宿主数据就绪已完成 2026-09-17**（短记：[unified-exit-modeb-minute-ready-2026-09-17.md](unified-exit-modeb-minute-ready-2026-09-17.md)；cache key 偏差见短记 §2）。可与 Mode B **编码并行**——本 runbook **只做数据就绪**，**不是** Mode B 网格结果。
> **权威**：提案 §9.1–9.2（分钟 none / `MINUTE_LAKE_END` / `bar_cache`）；plan [plan-unified-exit-modeb-2026-09-17.md](plan-unified-exit-modeb-2026-09-17.md) P5。
> **前置**：宿主能解析 F 湖（`F:\stock_data\.authority` 等，以本机 AGENTS 为准）；仓库 tip ≥ Mode A 合入（`e018924`+）。

## 0. 硬边界

- **不跑** Mode B 业务网格；不写 `unified_exit_modeb.py`。
- 不改湖数据；不改策略书 / 成交核。
- 产物：`backtest_output/bar_cache/minute_none_20251023_20260909.parquet`（及 `.json` meta）——可大，**不入库**。
- 明确区分：本 smoke = cache + 覆盖率 + 墙钟；Mode B 排名短记 = GO + 实现之后另开。

## 1. 宿主现在就能做的四步

### 1.1 确认分钟湖可达

```powershell
D:\anaconda3\envs\vanna312\python.exe -c "from pathlib import Path; from common.infra.data_root import resolve_period_root; p=resolve_period_root('1m')/'dividend_type=none'; print(p); print('exists', p.is_dir())"
```

期望：路径指向 F 湖 `period=1m/dividend_type=none`，`exists True`。上界常量见 `csv_minute_backtest.MINUTE_LAKE_END == "20260909"`。

### 1.2 构建 / 刷新 bar_cache（窗口 20251023–20260909）

现成入口：任意会调用 `load_minute_bars(..., use_cache=True)` 的分钟 CLI（如策略分钟回测）在同窗首次加载时会写入：

`backtest_output/bar_cache/minute_none_20251023_20260909.parquet`

或在 vanna312 里直接调用（示例；码集可先用 Mode A 实开并集，或名单并集 2322）：

```powershell
D:\anaconda3\envs\vanna312\python.exe -c @"
from pathlib import Path
from backtest.research.csv_minute_backtest import load_minute_bars, minute_cache_path, MINUTE_LAKE_END
# TODO: codes = 从 Mode A 明细 / stock_pool 并集解析出的 set[str]
codes = set()  # 填入后再跑
assert MINUTE_LAKE_END == '20260909'
status = {}
bars = load_minute_bars(codes, '20251023', '20260909', workers=16, use_cache=True, status=status)
print('cache', status, 'loaded', len(bars), 'path', minute_cache_path('20251023', '20260909'))
"@
```

- `--rebuild-cache` 语义：对应 API `rebuild_cache=True`。
- 全窗量级参考提案：约 **1.26 亿行**；必须走 parquet cache，勿反复全湖扫。

### 1.3 覆盖率：Mode A 实开码 ∩ 分钟可得

Mode A 宿主短记：实开 **4167**（封板 795 + 超幅度 99 跳过）。建议：

1. 从 `backtest_output/unified_exit_modea/` 实例明细读 `opened` 码集（或等价导出）。
2. 与 cache / `load_minute_bars` 返回键做交集。
3. 记录：命中数 / 缺失数 / 缺失样例；注明 `MINUTE_LAKE_END=20260909` 与窗口末日对齐。

缺码原因常见：停牌全日无 1m、代码退市中断、cache 子集未含该码——记入短记，**不在本 smoke 改名单**。

### 1.4 墙钟：一次全宇宙（或 4167 码）cache 加载

在 cache 已热时，对目标码集再跑一次 `load_minute_bars(..., use_cache=True)`，记录：

- wall-clock（秒）
- `status["cache"]`（期望 `hit`）
- 进程峰值内存（若方便）

冷构建（miss/rebuild）与热加载分开记，避免误判 Mode B 网格成本。

## 2. 完成定义（本 smoke）

| 项 | 完成 |
|----|------|
| `period=1m/dividend_type=none` 可达 | ✅/❌ |
| `minute_none_20251023_20260909.parquet` 存在且 meta 合理 | ✅/❌ |
| 覆盖率数字（相对 4167 或并集）落入短记 | ✅/❌ |
| 热加载墙钟 | ✅/❌ |
| **Mode B 网格排名** | ❌ **不在本 runbook 范围** |

短记建议文件名：`docs/backtest/unified-exit-modeb-minute-ready-YYYY-MM-DD.md`（可选；数字大文件仍不入库）。

## 3. 与 Mode B 网格的关系

```text
现在（可做）     : 分钟湖可达 + bar_cache + 覆盖率 + 墙钟
人裁 GO          : plan 头部 ✅
实现 PR 合入     : unified_exit_modeb A–D
之后才做         : Mode B P1=A 窄网格 + 研究短记（A–D 已合 #95；E 待跑，见下方业务 runbook）
```

**之后才做**：[Mode B 切片 E 业务 runbook](host-runbook-unified-exit-modeb-2026-09-17.md)。分钟 smoke 已完成，GO + A–D 实现已合 #95；业务 E 尚未执行，缓存沿用短记确认的 `minute_none_20251013_20260909`，不重建本篇旧示例的字面 `20251023` key。
