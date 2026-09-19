# domain-safety 对抗评审：plan-industry-align-next-2026-09-19.md

- 评审对象：`docs/backtest/plan-industry-align-next-2026-09-19.md`（Draft for human cut，docs-only）
- 评审角色：domain-safety（强制立场 fail-closed；必查 T+1、涨跌停/停牌、ST、`limits=None` 分叉、gate≠fill）
- 评审依据：`docs/prompts/prompt-adversarial-subagent-review.md`
- 证据基线（本机亲验）：branch `docs/industry-align-next`，`HEAD=eb5eb6ca2c1f333e36aaaa72af5f749b8c1da3cb`，`origin/master=41f3d11a34c665cc8a21b3e1d351b9e06b0466b5`，工作区 clean；plan header IMPLEMENTATION_BASE（plan:5）与 §7（plan:139）一致且等于 origin/master。
- 约束遵守：只写本文件；未改 plan / 业务 Python；未开 PR；未运行回测；未以 OSS 类比当行为证据。

---

## 结论：BLOCKING

语义内核（§2 fork 事实表、F-R3/F-R4/F-R7 锁、P1–P4 默认后置）经逐行核验**准确**，方向也是 fail-closed 友好的。但 §7 验收序列含一条**指向不存在脚本且本船无权补建**的必跑命令，pass criteria（plan:172 "exit code 0 for every executed command"）按现文不可满足。按 fail-closed 立场，human cut 前必须回填勘误，故整体判 **BLOCKING**（1 🔴 + 3 🟡；🔴 修复后其余均为 NITS 级）。

---

## Findings（file:line）

### 🔴 B1｜§7 必跑命令引用不存在的脚本，且 F-R5 使其无法自愈

- 位置：`docs/backtest/plan-industry-align-next-2026-09-19.md:153`（`python3 scripts/run_common_package_contract_gates.py`，注释标注 "runbook required"，未注释、非条件执行）。
- 事实：`scripts/run_common_package_contract_gates.py` 在当前树中不存在（`find scripts -name` 无命中）；`git log --all -- scripts/run_common_package_contract_gates.py` 为空 → 该脚本在本仓历史中从未存在过。同段 `run_stream_execution_contract_bundle.py`（plan:156）同样不存在，但已注释、标 conditional，风险低。
- 为什么 BLOCKING：§7 pass criteria 要求每条执行命令 exit 0（plan:171-174）；而 F-R5（plan:61）把本船变更范围限死为 "docs + data-free contract tests only"，实施 PR **不能创建该脚本**来让命令通过。验收序列按现文必然失败或必然被"顺手跳过"——后者更危险（形成一条可被沉默绕过的门禁）。
- 修复建议（供勘误表，不代改）：删除该步，或改为"仅当本船触达 `common/`、`oskh_core/` 时运行 `scripts/gates/verify_oskh_data_contract.py`（现存）"；本船冻结面（plan:159-168）只触 `backtest/research/*` 与 tests，common 包门禁本就无对象。

### 🟡 N1｜「停牌/零量 freeze」被锚到 mark 测试，freeze 证明锚点缺失

- 位置：`docs/backtest/plan-industry-align-next-2026-09-19.md:48`（Halt / zero-K freeze semantics 行，引 `tests/test_csv_daily_backtest.py:964` 与 `tests/test_daily_mark_cache.py:30-36`）。
- 事实：`tests/test_csv_daily_backtest.py:964` 是 `test_halt_day_equity_uses_last_close_not_cost`（:964-987），断言对象是 equity curve 取值（:986-987），**不断言禁买禁卖**；`tests/test_daily_mark_cache.py:27-38` 是 mark 函数 parity。真正的 freeze 证明在 `tests/test_csv_daily_backtest.py:990-1059`（`test_zero_volume_placeholder_day_cannot_sell_or_buy_and_marks_last_close`：无 SELL :1050、无 BUY :1052、`skip_no_bar==1` :1055）与 `:1062` 起（chase 保持 pending）。
- 风险：Slice A（plan:96-107）若按 §2.3 去扩展 :964 这个 mark 测试，会误以为 freeze 语义已被钉住——恰好复制 plan 自己要防的"锚点被误读"事故。
- 修复建议：§2.3 该行锚点改为 `tests/test_csv_daily_backtest.py:990-1059`（freeze + last-close mark）与 `:1062`（chase pending），mark 单独一行引 :964-987 / mark-cache :27-38。

### 🟡 N2｜ST-name fork 在标题范围内（plan:4），但 §2 无 as-built 锚点行

- 事实（两路真实分叉，本机核验）：
  - 书侧日线按日 as-of 取名：`backtest/research/csv_daily_backtest.py:291`（`names = names_asof(ds)`，来自 :264-270 `init_sim_state(..., pool_names_by_day=...)`）；已有测试钉住 as-of 回退（`tests/test_csv_daily_backtest.py:909-931`）与"未来 ST 不回溯"（:934-954）。
  - v7 用静态扁平映射：`backtest/research/csv_minute_backtest_v7.py:324`（`name = (names or {}).get(symbol, "")`），无日期维度 → 非 PIT。
- 冲突点：F-R7（plan:63）要求 "document as current fork"，Slice B（plan:111-119）要产出 fork matrix，但 §2.1 只覆盖 `limits=None` 分叉。若 Slice B 只按 §2.1 造表，ST fork（书侧 PIT vs v7 非 PIT）将继续无锚点，违背 §0 "future edits cannot silently normalize them" 的立项目标。
- 修复建议：§2 增加一行 ST-name fork 锚点（上列 file:line），并在 Slice B DoD 明确矩阵必须含该行；注意这是**文档补锚**，不是改行为，不违反 F-R7。

### 🟡 N3｜v7 held-path **加仓侧** fail-open 无既有 pin，Slice A 清单也未点名

- 事实：§2.1 第 5 行（plan:33）描述 "sell/add paths" 是准确的——`backtest/research/ashare_session.py:73-78` 两个谓词在 `limits is None` 时返回 `False`（不拦截），落到 `backtest/research/csv_minute_backtest_v7.py:342`（止损卖 defer 失效→允许卖）、`:367-372`（加仓 `skip_buy_at_limit` 失效→允许买）、`:402-404`（timer 卖 defer 失效）。但唯一既有分叉 pin 只覆盖**卖侧**：`tests/test_ashare_simulate_predicates.py:119-134`（两种 None 成因参数化，断言 v7 卖出、书侧冻结）。加仓侧（:367-372）无任何测试。
- 冲突点：Slice A 三个 bullet（plan:99-102）含 book early reject、v7 first-entry reject、"gate pass != guaranteed fill"，**未点名 held-add fail-open pin**。不补的话，fork 的买半边仍是可被沉默归一化的裸区。
- 附带（gate≠fill 的可观测性陷阱）：`_sell_lots` 在 T+1 全锁时静默返回 0、**不产生任何 trade event**（`backtest/research/csv_minute_backtest_v7.py:226-231`）。Slice A 若要证 "gate pass 但未成交"，仅断言"无 sell event"不足以区分"gate 拦截"与"T+1 拦截"；测试须同时断言：无 `defer_limit_down` event、且 lot 份额不变。
- 修复建议：Slice A 增加第四个 bullet：v7 held-add 在 `limits=None` 下 fail-open（允许尝试加仓）+ 与书侧 `skip_unknown_board` 的 split pin；T+1 静默零成交测试按上述双断言写。

### 核验为准确的部分（无需勘误，留档）

- §2.1 书侧 early reject 全部属实：`backtest/research/csv_daily_backtest.py:321-323`（仓位循环 :325 起）、`csv_minute_backtest.py:601-603`（:609 起）、`csv_simulate_loop.py:155-157` 与 `:260-261`。语义是 fail-closed：未知板块当日对该标的**整体跳过**（含持仓卖出），非仅拦截单笔。
- §2.1 v7 首次进场 reject 属实：`csv_minute_backtest_v7.py:389-391`（`priced is None` → `skip_unknown_board`，无进场）；另有 `previous is None` → `skip_no_prev_close`（:386-387）分支未列，但与谓词测试参数化（`tests/test_ashare_simulate_predicates.py:119-125`）一致，无碍。
- §2.2 gate pass ≠ fill 属实：买侧 `_buy` 现金/份额不足返回 `None` 并记 `skip_cash`（`csv_minute_backtest_v7.py:208-210`）；卖侧 `_sell_lots` 无 T+1 可卖 lot 返回 `0`（:226-231）。F-R4（plan:60）"Never collapse them" 是正确的域安全锁。
- T+1 基元：`ashare_session.py:39-41`（`buy_date < session`），书侧 `csv_daily_backtest.py:329/:336`、v7 lot 级 `csv_minute_backtest_v7.py:226-229` 均走同一 SSOT，无重复实现。测试锚点 `tests/test_ashare_session.py:15-18`、`tests/test_ashare_simulate_predicates.py:87` 属实。
- 涨跌停档位/ST 5%/未知前缀 fail-closed：`backtest/research/market_layer.py:57-84`（`limit_pct` ST 优先 5%，未知板块无名 → `None`；Decimal HALF_UP 到分）。§2.3 ST/board 测试锚点 :883/:901/:925/:950 与 `tests/test_csv_minute_backtest_v7.py:199-205` 均属实。
- ST PIT 不改已写清：F-R7（plan:63）+ §5 非目标（plan:88）+ P3 默认后置（plan:76）三层互锁，无歧义。
- §8 冻结表 9 个生产文件全部存在；§7 pytest 5 个路径全部存在（本机 ls 验证）。

---

## 对 P1–P4 默认继续后置的独立立场（fail-closed）

前提事实：#112 已合并，且旧 plan 已记录 2026-09-19 人裁 A/A/A/A（`docs/backtest/plan-industry-align-refactor-2026-09-18.md:125-134`）。本 plan §4（plan:70-79）的"默认 A"实质是对已裁事项的再确认，方向安全（宁可重确认也不默认继承）。

- **P1 = A（后置）：同意。** B/C 会改 14:57 触价成交资格，直接违反 F-R2（plan:58，不重开 fill-clock）与 F-R5（plan:61）；在零行为变更船上任何成交时钟改动都应 STOP。
- **P2 = A（后置）：同意。** `trades.csv` 加列是产物契约漂移，超出 docs+data-free tests 范围，须独立 schema 裁决。
- **P3 = A（后置）：同意，附一条红线。** 费率/改股/ST PIT/成交量上限均为数值与估值语义变更，本船禁止。红线：Slice B 把 v7 `limits=None` fail-open 及 v7 ST 非 PIT 写成 "intentional as-built contract" 时，**不得同时把它们表述为"已认可/正确"**——契约化只是"记录现状、防沉默归一"，后置的修复选项必须保持打开。建议 Slice B 文案显式带一句 "as-built ≠ approved; fix path stays deferred under P3"。
- **P4 = A（后置）：同意。** 触价资格与收盘/标记价解耦裁决，任何联动改动都会同时动成交与估值两套语义，与本船 F-R4 的状态分离精神相悖。
- 独立补充：鉴于 P1–P4 已在 #112 人裁过 A，本 plan §10.2（plan:208）的 "Human confirms" 应在勘误中注明是**再确认既裁**而非重开裁决窗口，避免实施侧误以为存在新一轮 B/C 选项征询。

---

## 亲验清单（本机实际执行/读取）

1. `git rev-parse HEAD origin/master`、`git branch --show-current`、`git status --porcelain`：与 BOX 基线一致，工作区 clean。
2. 逐行读取 §2/§7 全部代码锚点：`csv_daily_backtest.py:300-359`、`csv_minute_backtest.py:580-649`、`csv_simulate_loop.py:130-290`、`csv_minute_backtest_v7.py:180-439`、`ashare_session.py`（全文）、`market_layer.py:34-84`。
3. 逐行读取 §2.3 测试锚点：`test_ashare_session.py:15-40`、`test_ashare_simulate_predicates.py:70-149`、`test_csv_daily_backtest.py:870-1090`、`test_csv_minute_backtest_v7.py:185-219`、`test_daily_mark_cache.py:1-60`。
4. `find scripts -name "run_common_package_contract_gates*" -o -name "run_stream_execution_contract_bundle*"`：零命中；`git log --all -- scripts/run_common_package_contract_gates.py`：零历史。`ls scripts/gates scripts/run` 确认现存门禁脚本名单。
5. `ls` 验证 §8 冻结表 9 文件与 §7 pytest 5 路径全部存在。
6. 读取 `docs/backtest/plan-industry-align-refactor-2026-09-18.md:110-149` 核对 P1–P4 既裁记录与 F-R13/F-R14 后置锁。

## 未验证项

- 未运行任何 pytest（docs-only 评审，且本角色无授权触发测试执行）；§7 步骤 1 的 `-m "not production and not benchmark"` 过滤与 `pytest.ini` marker 注册的相容性未核对。
- v7 持仓标的**当日无分钟记录**（分钟侧停牌）时的行为与估值未验证：代码显示仅池内标的记 `skip_no_1455`（`csv_minute_backtest_v7.py:315-317`、`409-411`，测试 `tests/test_csv_minute_backtest_v7.py:113`），持仓无 bar 则当日无任何卖出尝试、估值依赖 `last_prices` 跨日残留（:334、:413）；其与书侧 `last_close_mark`（`tests/test_daily_mark_cache.py:36-38`）的 parity 无测试、plan 亦未主张——记为相邻未覆盖语义，不构成本船 Finding。
- `session_limit_prices` 与书侧 `book_limit_prices` 在同输入下的数值等价性未逐分支比对（两者最终都落 `market_layer.limit_prices`，SSOT 单源，风险低）。
- OSS 类比表（§9）未做外部核验；按角色纪律仅视为类比，不作为行为证据采信。
