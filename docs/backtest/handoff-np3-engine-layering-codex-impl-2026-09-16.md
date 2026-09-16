# 交接 · NP3 引擎分层倒置 实施（Codex 接手）

> 日期：2026-09-16
> 状态：**✅ 已人裁 GO（2026-09-16，P1–P4 采纳评审裁决值）——本交接已生效**。分支 `feat/np3-engine-layering`。
> 评审链：[zcode-facts](../architecture/reviews/2026-09-16/plan-np3-engine-layering/zcode-facts.md) / [zcode-arch](../architecture/reviews/2026-09-16/plan-np3-engine-layering/zcode-arch.md) / [merge-consensus](../architecture/reviews/2026-09-16/plan-np3-engine-layering/merge-consensus.md)。
> 权威对象：[plan-np3-engine-layering-2026-09-16.md](plan-np3-engine-layering-2026-09-16.md)（v1.1）。
> 分支：从当时 master 开 `feat/np3-engine-layering`；A/B/C/D 各一个 commit。

## 0. 硬边界（勿越）

1. **纯机械搬移**：被搬函数/常量函数体零改动（N-R2）；两条卖环、`simulate()`、`csv_ledger.py` 记账体、CLI 参数、落盘路径、HELP_LOCK 文案**一行不碰**（N-R1/N-R7）。
2. **搬移闭包以 plan §1.1 为准**（N-R8）：发现 plan 未列的模块内依赖 → **停下回写 plan**，不得现场裁决。
3. **测试面保留清单**（N-R9）：daily 的 `_ = (...)` pin、`chase_explained` import、`_limit_prices` 别名**保留**——它们服务测试，不是转发病灶；别把「删转发」扩大化。
4. 每片 commit 后 `D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/` 全绿 + golden 绿才进下一片。
5. 新文件 UTF-8 无 BOM、NUL=0；验证命令一律 vanna312 全路径。

## 1. 切片 A · 改指真身（29 符号；minute import 块重写）

- `csv_minute_backtest.py:33-75` 按下表改指：
  - `csv_ledger`（14）：CHASE_HM, DEFAULT_TOTAL_CASH, PEAK_GAP_MIN, SimState, chase_decision, execute_buy, finish_pending_chase, queue_limit_up_chase, hit_limit_down, hit_limit_up, last_close_mark, peak_gap_blocks, `_sell`, `_ymd`
  - `csv_common`（3）：build_calendar, `_named_limits`, `_pool_names_asof`（**别从 daily 转发**）
  - `market_layer`：utc_ms_range；`csv_pool`：load_pool_names_by_day；`strategy6_rules`：POS_TRAIL, trail_hits
  - `csv_strategy_books`（8）：add_csv_backtest_common_args, apply_csv_strategy, csv_run_kwargs_from_args, engine_book, resolve_research_pool_dir, help_lock_all, help_lock_for（minute :1121 已显式传 shared，零行为）, normalize_csv_strategy
- **load_pool_days 直呼**（P3）：minute:1006 与 daily:510 改 `load_pool_day_map(pool_dir, start, end, key="ymd", empty_in_map=False)`；daily:214 wrapper 删除。
- **MINUTE_LAKE_END 留 minute**（P1）：在 minute 顶部自定义 `MINUTE_LAKE_END = "20260909"`，import 块中删除该项。
- 验收：minute→daily import 41→13；pytest 全绿；golden 绿。

## 2. 切片 B · 抽 `csv_artifacts.py`（6 符号，含两伴生）

- 搬：summarize（daily:562）、write_run_artifacts（:678）、maybe_compare_daily（:765）、**find_daily_equity_csv（:695）、format_equity_compare（:719）**——五函数互相引用闭包自洽；`_progress` **不进本模块**（改迁 csv_common）。
- 模块内 import：`pandas`、`pathlib`、`from backtest.research.csv_ledger import SimState, chase_explained`；本地复算 `REPO`（`Path(__file__).resolve().parents[2]` 同款）。
- docstring 契约句（必须）：「本模块按设计知晓两引擎工件命名约定（`csv_daily_{book}_{start}_{end}`）与对照语义；命名串是数据，不是对引擎代码的依赖。」
- daily/minute import 改指；测试改指：`test_csv_daily_backtest.py:217/:733/:752/:764`（summarize）、`:787`（write_run_artifacts）、`:801`（format_equity_compare）、`:814`（find_daily_equity_csv）、`test_csv_daily_backtest_v8.py:200`、`test_csv_strategy_books.py:352`。
- **新单测**（焊假绿通道）：① maybe_compare_daily——tmp_path 造对端 `csv_daily_v8_*` 净值 csv，断言对照行为与 caption；② summarize——合成 `SimState`（含 sizing/name_budget/skip_cash 等 stats），剔除非确定行（`耗时:` 等）后全文本 golden。
- 验收：minute→daily import →8；pytest 全绿（含新单测）。

## 3. 切片 C · 抽 `csv_daily_loader.py`（4 符号 + `_PERIOD_ENV_KEYS`）

- 搬：load_daily_bars（:262）、**`_read_one_daily`（:222，伴生）**、warmup_start（:188）、warn_stale_period_env（:192）、`_PERIOD_ENV_KEYS`（:140-146）；本地复算 REPO；模块 import：csv_common（WARMUP_DAYS/`_progress`）、market_layer（utc_ms_range）、oskh_data（to_partition_key）、csv_pool、common.infra。
- 3 常量 DEFAULT_DAILY_QUOTA / WARMUP_DAYS / STRATEGY4_CALENDAR_SLACK_DAYS → `csv_common.py`（daily/minute 改指）；daily 的 `to_partition_key` import 删除（唯一消费者已迁）。
- 测试改指：`test_csv_daily_backtest.py:86/:108/:963/:964/:1020`（`_read_one_daily`→loader）。
- **新单测**：warn_stale_period_env——monkeypatch OSKH_\* env 各键，断言告警文案与静默分支。
- 验收：minute→daily import →0；`grep -rn 'csv_daily_backtest import' backtest/ scripts/ tests/` 仅剩合法项（simulate/main/REPO 等非搬移符号）；pytest 全绿。

## 4. 切片 D · 围栏与文档

- 持久围栏：`tests/test_research_face_imports.py`（或新文件）加断言——`csv_minute_backtest` AST 无 `csv_daily_backtest` import 节点。
- 两新模块入 `_VECTORIZED_RESEARCH_FACE` 白名单。
- daily `_ = (...)` pin 注释（:107-131）改「仅测试」；README 引擎地图段更新（双入口 + 共享核：common/ledger/books/pool/market_layer/simulate_loop/artifacts/loader）；plan §状态回写。
- 新文件 NUL=0 复核；HELP_LOCK 不变。

## 5. 门禁（合并前）

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
# minute→daily import 归零（plan §6 AST 脚本）
# 宿主可选：重构前后 daily+minute 各一窗 trades.csv 逐字节对照（D 烟测窗）
```

- 完成后缺陷优先复核 diff（重点：函数体 diff 必须只有文件移动；确认无环），回写 plan 状态与本交接完成标记。
