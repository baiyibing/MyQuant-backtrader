# NP3 plan 事实锚点评审（host: zcode-facts）

> 评审对象：[plan-np3-engine-layering-2026-09-16.md](../../../../backtest/plan-np3-engine-layering-2026-09-16.md) v1.0 · 2026-09-16
> 角色：pattern-evidence / 事实锚点核查 · 结论：**READY-AFTER-FIXES**

41 符号主映射表基本准确（36/41 无误）、分层方向无环，但 plan 有 3 处硬伤：消费者清单漏了最大消费文件 `tests/test_csv_daily_backtest.py`、两个被抽函数的**伴生依赖未随迁**（会直接造成循环 import / N-R5 违例 / pytest 红）。修完下述 🔴 后即可 GO。

## 一、逐符号核验（§1 映射表）

41 符号清单已从 `backtest/research/csv_minute_backtest.py:33-75`（恰好 41 个名字，行号与 plan 一致）逐个对真身：

| plan 归属 | 核验结果 |
|---|---|
| `csv_ledger.py` 14 符号 | ✅ 全部在 `csv_ledger.py`（CHASE_HM:20, DEFAULT_TOTAL_CASH:17, PEAK_GAP_MIN:19, SimState:71, chase_decision:105, execute_buy:181, finish_pending_chase:121, queue_limit_up_chase:114, hit_limit_down:95, hit_limit_up:90, last_close_mark:162, peak_gap_blocks:100, `_sell`:229, `_ymd`:81） |
| `csv_common.py` 3 符号 | ✅ build_calendar:44, `_named_limits`:58, `_pool_names_asof`:62；daily 确为转发（daily:83-88） |
| `market_layer.py` utc_ms_range | ✅ :25 |
| `csv_pool.py` load_pool_names_by_day | ✅ :161，minute:1007 调用签名吻合，改指零行为 |
| `csv_strategy_books.py` 8 符号 | ✅ 7 个无保留（add_csv_backtest_common_args:202, apply_csv_strategy:91, csv_run_kwargs_from_args:288, engine_book:144, resolve_research_pool_dir:268, help_lock_all:152, normalize_csv_strategy:75）；**`help_lock_for` 有出入，见勘误表** |
| `strategy6_rules.py` 2 符号 | ✅ POS_TRAIL:19, trail_hits:34 |
| 新 `csv_artifacts.py` 4 符号 | ✅ 真身在 daily 且全树无别处同名（summarize:562, write_run_artifacts:678, `_progress`:201, maybe_compare_daily:765；v7 的 `summarize_v7`/`write_run_artifacts`:401 是独立同名不同签名，无冲突）——但 maybe_compare_daily 有**未列伴生依赖**（🔴-2） |
| 新 `csv_daily_loader.py` 4 符号 | ⚠️ load_daily_bars:262 ✅ 但有**未列伴生 `_read_one_daily`**（🔴-3）；warmup_start:188 / warn_stale_period_env:192 ✅ 但后者依赖未列常量 `_PERIOD_ENV_KEYS`（🟡-4）；**load_pool_days 真身 = daily:214 本地 wrapper，不是转发**（勘误表） |
| 4 常量 | ✅ DEFAULT_DAILY_QUOTA:135, WARMUP_DAYS:136, STRATEGY4_CALENDAR_SLACK_DAYS:137, MINUTE_LAKE_END:139，均为 daily 模块级赋值；MINUTE_LAKE_END 消费者仅 minute（:37,:998,:1000,:1082,:1084），daily 自身 main 用字面量 "20260909"（:794） |

计数核对：14+3+1+1+8+2=29 改指；4+4=8 抽出；3+1=4 常量；合计 41 ✅。

## 二、全树消费者清单（plan §1 漏项）

全树 grep `csv_daily_backtest` 实际消费者 13 处，plan 只列了 2 处：

| 文件 | 用法 | 受影响？ |
|---|---|---|
| `backtest/research/csv_minute_backtest.py:33` | 41 符号 import | 本 plan 主体 ✅ |
| **`tests/test_csv_daily_backtest.py:17`** | `import … as sim`；`sim._read_one_daily`×5（:86,:108,:963,:964,:1020）、`sim.summarize`×4（:217,:733,:752,:764）、`sim.load_pool_days`（:743）、`sim.write_run_artifacts`（:787）、`sim.format_equity_compare`（:801）、`sim.find_daily_equity_csv`（:814）、`sim.chase_explained`×9、`sim._limit_prices`（:590） | **🔴 plan 完全未提，13+ 处调用点** |
| **`tests/test_csv_minute_backtest.py:11`** | `from … import chase_explained` | **🔴 plan 未提** |
| **`tests/test_csv_minute_backtest_v8.py:11`** | `from … import chase_explained`（另 :175,:196 `sim.chase_explained`） | **🔴 plan 未提** |
| `tests/test_csv_daily_backtest_v8.py:10,200` | `sim.simulate`/`sim.chase_explained` + `import SimState, summarize` | plan 已列（但只列了 :200） |
| `tests/test_csv_strategy_books.py:352` | `from … import summarize` | plan 已列 ✅ |
| `tests/test_csv_daily_outdir.py:8`、`tests/test_strategy9_book.py:12,68`、`tests/test_strategy10_tr_pool.py:9` | `sim.main`/`sim.run`/`sim.REPO`/`sim.apply_csv_strategy` 等 | 不受影响 🟢 |
| `tests/fixtures/csv_engine_pre_er1/generate_snapshot.py:11` | `sim.simulate` | 不受影响 🟢 |

**bench 脚本审计**：`bench_minute_simulate_hotpath.py:91-98,:111` setattr 的 6 个目标全部是 minute 模块本地名或 `csv_simulate_loop` import 名，本 plan 不动该块，patch 继续生效；没有任何脚本 patch `csv_daily_backtest`。

## 三、模块态依赖核验（8 个待抽函数）

| 函数 | 模块级依赖 | 搬迁判定 |
|---|---|---|
| `_progress`（daily:201） | 无（纯 print） | ✅ 零行为 |
| `summarize`（daily:562） | `pd`、`chase_explained`（csv_ledger :624）、`SimState`（仅注解） | ✅ 零行为 |
| `write_run_artifacts`（daily:678） | `pd`/`Path` | ✅ 零行为 |
| `maybe_compare_daily`（daily:765） | **`find_daily_equity_csv`（daily:695）→ `REPO`；`format_equity_compare`（daily:719）** | 🔴 两伴生函数不在 plan 清单 |
| `load_daily_bars`（daily:262） | **`_read_one_daily`（daily:222）**、`resolve_period_root`（调用点读 env、无缓存）、`_progress`、`utc_ms_range`、`to_partition_key` | 🔴 `_read_one_daily` 不在清单 |
| `load_pool_days`（daily:214） | `REPO`（默认参数）、`csv_pool.load_pool_day_map` | ⚠️ 签名适配 wrapper 非转发；minute:1006 与 daily:510 均显式传 pool_dir，默认值双引擎都是死路径 |
| `warmup_start`（daily:188） | `WARMUP_DAYS` 默认参数（def 时绑定） | ✅ 常量进 common 后同值 import |
| `warn_stale_period_env`（daily:192） | **`_PERIOD_ENV_KEYS`（daily:140-146）**、os.environ 调用时读 | 🟡 元组必须随迁 |

`REPO`：新模块与 daily 同目录同公式重算，零行为；OSKH_\* env 全部调用时读，无 import 时序问题。

## 四、循环 import 检查

目标态依赖方向无环（既有四共享模块无指向新模块的边；`__init__.py` 空）。但若按 v1.0 字面实施（伴生函数留 daily）会出现两条成环边：csv_artifacts→daily、csv_daily_loader→daily，且 daily 顶部 import 新模块时命中半初始化模块 → 直接 ImportError。loader→artifacts（`_progress`）单向合法但属倒置边（arch 评审改判 `_progress`→csv_common）。

## 五、golden 与围栏

- byte-identical golden（`tests/test_csv_strategy_books.py:333`）：驱动 `generate_snapshot.py` → `sim.simulate`（注入 bars），对 version1/version6 断言 trades 逐字节相等；**不锁** summarize 文本、落盘、加载路径、env 告警。
- `tests/test_research_face_imports.py`：`_VECTORIZED_RESEARCH_FACE` 显式元组（:43-49）管子进程检查；`test_research_face_ast_no_backtrader`（:108-111）rglob 全 `backtest/research/*.py`，**新模块自动受 AST 围栏**；csv_pool/csv_ledger/market_layer 先例均未登记 → slice D「如需」判断正确。
- monkeypatch 审计：打在 daily 上的仅 `sim.run`/`sim.REPO`/`sim.apply_csv_strategy`——均非被搬符号，无需改 patch 目标。

## 六、其他实施即翻车点

- 🟢 无相对导入、无 `__all__`、新文件名无冲突、docstring 无仓内相对链接。
- 🟡 §6 验证脚本用裸 `python`——应写 vanna312 全路径。
- 🟡 daily:107-131 `_ = (...)` pin 块注释将过时；§7「删除转发」若被扩大解释到非下沉的测试面转发（chase_explained、`_limit_prices` 别名 daily:211、Position/_at_limit 等），立刻断 `tests/test_csv_daily_backtest.py` 20+ 处。N-R4 字面自洽但应加显式保留清单。
- 🟡 切片 A「41→12」仅在 P3 裁「改指」时成立；裁直呼则 A 后余 13。

## 发现分级汇总

- 🔴 R1 消费者清单错误（补 3 文件）；🔴 R2 maybe_compare_daily 伴生（find_daily_equity_csv/format_equity_compare 随迁）；🔴 R3 load_daily_bars 伴生（`_read_one_daily` 随迁）。
- 🟡 R4 `_PERIOD_ENV_KEYS` 随迁；R5 daily 的 `help_lock_for` wrapper 保留；R6 `load_pool_days` 是 wrapper 非转发（P3 写明）；R7 §6 python 路径；R8 §7 过度裁剪风险（保留清单）。

## 映射勘误表（仅列有出入者）

| 符号 | plan v1.0 | 核验真身 | 勘误 |
|---|---|---|---|
| `help_lock_for` | books 改指 | 两处：books:148（shared 必填）+ daily:184 wrapper | minute:1121 显式传 shared → 改指成立；daily wrapper 保留（daily:826 依赖默认值） |
| `load_pool_days` | loader 抽出/P3 | daily:214 本地 wrapper（内调 csv_pool.load_pool_day_map） | 非纯改指；推荐直呼 load_pool_day_map 或 wrapper 落 loader |
| `maybe_compare_daily` | artifacts 抽出 | 依赖 daily:695/:719 两伴生 | 两伴生必须同迁 artifacts |
| `load_daily_bars` | loader 抽出 | 依赖 daily:222 `_read_one_daily` | 伴生同迁 loader |
| `warn_stale_period_env` | loader 抽出 | 依赖 daily:140-146 `_PERIOD_ENV_KEYS` | 元组随迁 |
| （其余 36 符号 + 4 常量） | — | — | 无出入 |
