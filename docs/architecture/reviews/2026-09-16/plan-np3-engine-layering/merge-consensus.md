# Merge Consensus：plan-np3-engine-layering 评审裁决（2026-09-16）

## 评审方

| Host | 角色 | 结论 | 发现 |
|------|------|------|------|
| zcode-facts | 事实锚点核查（41 符号逐一对真身 + 全树消费者 + 模块态 + 环检查 + golden/围栏/monkeypatch 审计） | READY-AFTER-FIXES | 3🔴 / 5🟡 / 多🟢；映射 36/41 无误 |
| zcode-arch | 架构语义（steelman 切线/常量归属/顺序/N-R4 半径/后续铺路充分性） | READY-AFTER-FIXES | 3🔴 / 6🟡 / 6🟢；方向全维持 |

## 双方一致（裁决采纳）

1. **方向维持**：双入口 + 单共享核；A→B→C→D 顺序正确无需重排；N-R4 不留 re-export 维持（转发正是病灶）。
2. **三 🔴 同根**：v1.0 只做了「符号→真身」映射，没做**搬移闭包**与**消费者闭包**投影。修复：
   - csv_artifacts 符号 4 → **6**（+`find_daily_equity_csv`、`format_equity_compare`，否则成环/NameError）；
   - csv_daily_loader 补 **`_read_one_daily`** 与 **`_PERIOD_ENV_KEYS`**（+ 本地复算 REPO）；
   - 消费者补 3 文件：`tests/test_csv_daily_backtest.py`（`sim._read_one_daily`×5、`sim.summarize`×4、`sim.load_pool_days`、`sim.write_run_artifacts`、`sim.format_equity_compare`、`sim.find_daily_equity_csv`）、`tests/test_csv_minute_backtest.py:11`、`tests/test_csv_minute_backtest_v8.py:11`（`chase_explained` → 改指 csv_ledger）。
3. **假绿通道焊死**（arch 🟡-4 采纳为完成定义）：B/C 片各补 data-free 单测——`maybe_compare_daily`（tmp_path 对端目录）、`warn_stale_period_env`（monkeypatch env）、`summarize` 确定性全文本 golden（合成 st、剔非确定行）。运行时 summary.txt 字节锁不可行（含耗时行）。
4. **持久围栏**（arch 🟡-5）：pytest 断言 minute AST 无 daily import 节点（N-R6 升级为回归锁）；新模块入 `_VECTORIZED_RESEARCH_FACE`。

## 分歧与改判（arch 提、facts 无异议）

| 项 | v1.0 | 改判 |
|----|------|------|
| `MINUTE_LAKE_END` | → loader | **留 `csv_minute_backtest` 自定义自用**（daily 零自用、minute 唯一消费者；进 loader = 病灶降级复刻） |
| `_progress` | → artifacts | **→ csv_common**（消费者全是装载/缓存层；loader→artifacts 是倒置边） |
| `load_pool_days`（P3） | wrapper 落 csv_pool 正身 | **直呼 `csv_pool.load_pool_day_map(actual_pool_dir, ..., key="ymd", empty_in_map=False)`**（csv_pool 保持 repo-无感；两处调用点显式 kwargs） |
| `help_lock_for` | 改指 | minute 改指成立（:1121 显式传 shared）；**daily wrapper（:184 绑 daily HELP_LOCK 默认）保留** |

## 其他采纳

- 🟡 facts-R7：§6 验证命令改 vanna312 全路径 python。
- 🟡 facts-R8：§7 加「测试面保留清单」（daily 为测试 pin 的 `chase_explained`/`_limit_prices` 别名等不属 N-R4 打击面，防过度裁剪）；`_ = (...)` pin 保留、注释改为「仅测试」。
- 🟢 arch：bench monkeypatch 风险行改写（patch 目标全在 minute 命名空间，本次不受影响，无需动作）。
- 🟢 arch §三：**「共同地基」宣称降级**——对 version11 必要不充分（还缺 rules/register/第三卖环/时点裁决）；对 band-as-data 无直接交付；对 compiled scan 几乎无贡献。写进 plan §9 防过度宣称。

## 结论

- plan v1.1 已按裁决回写 → **READY，待人裁 GO（P1–P4）**。
- 人裁 GO 后按 [Codex 交接工作流](../../../../backtest/workflow-codex-handoff.md) 开 `feat/np3-engine-layering`。
