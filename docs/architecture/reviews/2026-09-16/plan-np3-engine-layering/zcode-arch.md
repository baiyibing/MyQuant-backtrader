# NP3 plan 架构语义评审（host: zcode-arch）

> 评审对象：[plan-np3-engine-layering-2026-09-16.md](../../../../backtest/plan-np3-engine-layering-2026-09-16.md) v1.0 · 2026-09-16
> 角色：domain-safety + dissent-steelman · 结论：**READY-AFTER-FIXES**

方向与切线正确（双入口 + 单共享核、A→B→C→D 顺序、不留转发，均维持）；但**搬移闭包与消费者清单有 3 处阻断级缺口**，按现文实施会在 B/C 片产出「pytest 全绿 + golden 绿、真实 CLI 运行即 NameError」的假绿状态，或直接撞 N-R5 成环。

## 一、发现

### 🔴-1 csv_artifacts 搬移闭包缺 2 函数（maybe_compare_daily 的伴生）

`maybe_compare_daily`（daily:765-782）在 :776 调 `find_daily_equity_csv`（真身 :695-716）、:780 调 `format_equity_compare`（真身 :719-762）。按 4 符号表搬移：要么 artifacts→daily 反向 import（违 N-R5 + 真 import 环），要么运行期 NameError。**该路径零测试覆盖**（全 tests/ 无 maybe_compare_daily 引用）→ B 片「pytest 全绿 + golden 绿」照常达成，炸点留到真实 minute 运行且对端存在 csv_daily 净值时。修法：csv_artifacts 符号表 4 → **6**（两伴生随迁；二者只被 maybe_compare_daily 与 test_csv_daily_backtest.py:801,:814 消费，归 artifacts 名正言顺）。

### 🔴-2 csv_daily_loader 搬移闭包缺 `_read_one_daily` 与 `_PERIOD_ENV_KEYS`

`load_daily_bars`（:262-286）:272 调 `_read_one_daily`（真身 :222-259）；`warn_stale_period_env`（:192-198）:193 引用 `_PERIOD_ENV_KEYS`（:140-146）。照表搬移 → loader 内 NameError；`warn_stale_period_env` 全树零测试（两引擎 run() 第一行 :507 / minute:997 就调它），真实运行立即炸但 CI 全绿。连带：`tests/test_csv_daily_backtest.py:86,:108,:963-964,:1020` 五处直测 `sim._read_one_daily`——plan §7 完全没有该文件条目。另 `find_daily_equity_csv`/`load_pool_days` 用 `Path(REPO)`（:703/:218），新模块需本地复算同款 REPO（机械无行为差，须写进落点）。

### 🔴-3 消费者盘点失真

§1 声称「仅 2 个测试文件」，实为：另漏 `tests/test_csv_minute_backtest.py:11` 与 `tests/test_csv_minute_backtest_v8.py:11` 的 `from … import chase_explained`（真身 csv_ledger:126-137；daily 里唯一消费者是被搬走的 summarize :624）。B 片后 daily 若删不再自用的 `chase_explained` import（:73），两测试收集期 ImportError；若保留则转发病灶在未审计位置存活——两头都说明清单错误。

三 🔴 同根：v1.0 只做了「符号→真身」映射，没做**搬移闭包**（模块内依赖）与**消费者闭包**（from-import + 属性访问两轴）投影。

### 🟡-1 MINUTE_LAKE_END 归属错位

daily 函数体零使用（main 的 end_default 是硬编码 :794）；全仓消费者只有 minute（:998,:1082,:1084）。进 loader = 「daily 为 minute 持货」的病灶降级复刻。**改判：留 `csv_minute_backtest.py` 自定义自用**（零新增跨模块边）。

### 🟡-2 `_progress` 放 artifacts 制造倒置边

消费者 = `load_daily_bars`（daily:278）、minute 的 `write_minute_cache`（minute:255）与 `_load_minute_from_lake`（:369）——全是装载/缓存层。**改判：→ csv_common**（loader→common 与 WARMUP_DAYS 同向，自然）。

### 🟡-3 P3 默认路径会让 repo-无感的 csv_pool 沾上 REPO 默认

两引擎 run() 都先 `resolve_research_pool_dir` 再传入（:509-510 / minute:1005-1006），生产路径从不触发该默认。**改判：minute/daily 直呼 `load_pool_day_map(actual_pool_dir, start, end, key="ymd", empty_in_map=False)`**；要留薄包装则放 loader，不进 csv_pool。

### 🟡-4 N-R3 兜底弱于宣称：golden 只锁「daily simulate 注入路径 + 默认配给」

minute 引擎、summarize 文本、artifacts 落盘、两个零测试入口（maybe_compare_daily、warn_stale_period_env）全在锁外。**裁决（进 B/C 完成定义，非可选）**：补三个 data-free 单测——maybe_compare_daily（tmp_path 造对端 csv_daily_\* 目录）、warn_stale_period_env（monkeypatch env）、summarize 确定性全文本 golden（合成 st、剔非确定行如耗时）。运行时 summary.txt 字节锁不可行（:645-658 含耗时行）。

### 🟡-5 N-R6 是一次性人工脚本，无持久围栏

建议加廉价 pytest：断言 `csv_minute_backtest` 的 AST 无 `csv_daily_backtest` import 节点——把 N-R6 从验收指标升级为结构性回归锁。

### 🟡-6 新模块 docstring 须写成契约

csv_artifacts 需明示「本模块按设计知晓两引擎工件命名约定（csv_daily_{book}_{start}_{end}）与对照语义——命名串是数据，不是对引擎代码的依赖」；loader 需声明三职责（daily bars / pool 日装载 / env 卫生）。

### 🟢-1 常量归属逐个意见

| 常量 | 意见 |
|---|---|
| DEFAULT_DAILY_QUOTA | csv_common 可接受（备选 ledger 与 DEFAULT_TOTAL_CASH 同居；但 daily_quota 在 ledger 内零使用，放 ledger 稀释定位）——不应留在引擎文件 |
| WARMUP_DAYS | → csv_common ✓ |
| STRATEGY4_CALENDAR_SLACK_DAYS | → csv_common 可接受（远期 band-as-data 时代更自然的家是 strategy4_rules，本轮不动） |
| MINUTE_LAKE_END | 不进 loader，留 minute（🟡-1） |
| `_PERIOD_ENV_KEYS` | v1.0 漏列；随 warn_stale_period_env 进 loader |

四常量除两引擎外零消费者——搬移爆炸半径为零。

### 🟢-2 「参数化伪共享」steelman 大部分消解

summarize 参数行按 `st.stats["sell_book"]` 数据分支（:590-610）；HELP_LOCK 文案留各自引擎、经参数传入（:678 签名）。真正跨引擎语义只有对照三件套（目录名前缀、peer_label 默认、highlight="20251104" parity 日 :725）。**裁决：共享函数 + 两引擎薄壳（即 plan 做法）优于备选**；三件套进 artifacts + docstring 契约（🟡-6）是两害相权最优。

### 🟢-3 切片顺序 A→B→C→D 正确

A 先行 = 零代码移动纯 import 重写，立刻消灭最恶性叶子转发；C 先行反而需过渡转发，中间态更脏。验算 A 后剩余恰为 4 常量 + 4 artifacts + 4 loader。假绿通道来自清单缺口而非顺序——修清单 + 补单测（🟡-4）才是解。

### 🟢-4 围栏完备性

新模块自动受 AST 围栏（test_research_face_imports.py:108-117 rglob）；建议 D 片把两新模块加进 `_VECTORIZED_RESEARCH_FACE`（:43-49）获子进程检查。新文件 NUL=0 复核写进 D 片完成定义。

### 🟢-5 §8 bench 风险行指向错误

monkeypatch 目标全在 minute 命名空间（bench_minute_simulate_hotpath.py:29,:100-111 六目标），本次不受影响、无需动作。tests 侧 patch 目标（sim.run/sim.REPO/apply_csv_strategy）亦均非被搬符号。改一句表述即可。

### 🟢-6 收尾一致性

daily `_ = (...)` pin（:107-131）注释改为「仅测试」；pin 保留（为测试服务的转发不在 N-R4 打击面）。`to_partition_key`（:133）C 片后成为 daily unused import（唯一消费者 `_read_one_daily` 已迁），可删可 pin，写进落点防实施者犹豫。

## 二、N-R4 最终裁决：维持不留

爆炸半径修正（from-import 5 条 + 属性消费 7 文件）：补 3 文件改指（test_csv_daily_backtest.py 属性点 → loader/artifacts；test_csv_minute_backtest\*.py:11 chase_explained → csv_ledger）。「今后每次移动全树改」的顾虑不成立：破坏模式是响亮 ImportError 而非静默漂移；留转发等于白做。

## 三、为后续铺路的缺口登记（防过度宣称）

1. **version11**：NP3 必要不充分（还缺 strategy11_rules + register + 第三卖环 + 成交时点裁决 + HELP_LOCK）。
2. **band-as-data**：NP3 无直接交付（缺 tiers 闭包→数据通道、band 装载缝、scan_held_day trail_ratio 参数化、numba 核带查表）。
3. **compiled scan**：**NP3 对它几乎没有贡献**，「共同地基」宣称对这一支应降级为「文件卫生便利」。
4. run 出处戳（commit/参数/湖 root）未来落点在 csv_artifacts——NP3 只搬不建。

## 四、人裁点建议

| # | 建议 |
|---|---|
| P1 | 三常量 → csv_common 准；MINUTE_LAKE_END 改判留 minute；`_PERIOD_ENV_KEYS` 补列随 loader |
| P2 | 维持不留 re-export；§7 按 §二 修正消费者表；pin 保留改注释 |
| P3 | 改判直呼 load_pool_day_map（csv_pool 保持 repo-无感）；薄包装若留则放 loader |
| P4（新） | B/C 补三个 data-free 单测 + docstring 契约句（焊死假绿通道） |
| P5（新） | D 片持久围栏（minute AST 无 daily import 的 pytest）+ 新模块入白名单 |
| P6（=🔴修复） | artifacts 符号表定稿 6；loader 闭包定稿（+_read_one_daily/_PERIOD_ENV_KEYS/本地 REPO）；`_progress` 改判 csv_common |

**结论**：方向全维持；三 🔴 全是清单完整性而非结构判断问题——修文 + P4 后 READY。
