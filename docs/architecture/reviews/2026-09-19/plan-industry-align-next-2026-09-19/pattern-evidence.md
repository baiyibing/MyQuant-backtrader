# pattern-evidence 对抗评审

## 1. 元信息

- 角色：pattern-evidence；强制立场：怀疑过度类比。必查：OSS 是否被当行为证据；冻结表 / §7 bash 是否与真实路径漂移；是否重开 #108 / #112；是否误复用 `chip_indicator` / `StockDataReader`；包边界；文档漂移。
- 对象：`docs/backtest/plan-industry-align-next-2026-09-19.md`（Draft for human cut，docs-only）。
- 日期：2026-09-19。
- 工作目录：`/workspace/wt-industry-align-impl`。
- 实读规范：`docs/prompts/prompt-adversarial-subagent-review.md`。
- 证据基线（本机亲验）：branch `docs/industry-align-next`，`HEAD=eb5eb6ca2c1f333e36aaaa72af5f749b8c1da3cb`，`origin/master=41f3d11a34c665cc8a21b3e1d351b9e06b0466b5`。
- 约束：只写本文件；未改 plan / 业务 Python；未开 PR；未造 SHA；未把 OSS 类比当行为证据。本稿不计独立票。

---

## 2. 结论：BLOCKING

§2 分叉锚点、§4 默认 A、§9「analogy only」标题与 F-R9 禁令，经对照代码**没有把 OSS 当成交证据，也没有在文本里选中 #112 P1=B/C**。阻塞点是另一类过度类比：**§7 把别仓 / 别包的 contract-gates runbook 当成了本仓 CI 同构序列**。必跑入口 `scripts/run_common_package_contract_gates.py` 在本树不存在、历史从未存在，却替换了 #112 已经写对的四条 `scripts/gates/verify_*.py`。F-R5（plan:61）又禁止本船新建该脚本。按现文 Slice C / pass criteria 不可执行。

1 🔴 + 3 🟡。🔴 回填为真实 CI gates 并删掉幽灵脚本后，其余为 NITS。本结论不授权改 fail-open，不授权重开 fill-clock。

---

## 3. Findings（file:line）

### 🔴 P-E1｜§7 必跑脚本是跨包 runbook 类比，不是本仓真实路径

- **位置**：`docs/backtest/plan-industry-align-next-2026-09-19.md:135`（「aligned with CI intent and the contract-gates runbook sequence」）、`:152-153`（未注释必跑 `python3 scripts/run_common_package_contract_gates.py`，注释写 "runbook required"）、`:155-156`（注释中的 `scripts/run_stream_execution_contract_bundle.py`）、`:128` / `:172`（gates 必须过、每条已执行命令 exit 0）。
- **本仓事实**：
  - `ls` / `find scripts`：两个脚本都不存在。
  - `git log --all -- scripts/run_common_package_contract_gates.py scripts/run_stream_execution_contract_bundle.py`：空。
  - 本仓真实 data-free CI 在 `.github/workflows/python-tests.yml:38-43`：`scripts/gates/verify_oskh_data_contract.py`、`verify_data_path_ssot.py`、`verify_no_hardcoded_machine_paths.py`、`verify_tr_bridge_import_ssot.py`。`docs/backtest/README.md:76` 与此同构。
  - 上一船已验证序列在 `docs/backtest/plan-industry-align-refactor-2026-09-18.md:288-292`（同一组四条 gates），不是 `run_common_package_contract_gates.py`。
- **类比源（不得当本船证据）**：同名字符串只出现在别的包边界稿里，对象是 `common/integrations` + `StockDataReader` + live port，不是 fill-gate 分叉：
  - `docs/backtest/data/unified-daily-bars-plan.md:161`、`:203`、`:221`、`:247`（「验证 `common/integrations/` 新模块不违反导入边界」；该稿还要求延迟 import `StockDataReader`）。
  - `docs/backtest/chip/rfc-turnover-resistance-bands.md:574`（明确「该门禁主要覆盖 common/oskh_db/oskh_core 变更」，且写「不必默认跑」）。
- **为什么是 pattern-evidence BLOCKING**：这不是行号笔误。§7 用「runbook required」把**不存在、且属于另一包**的入口写成 Linux/CI 同构验收，同时把 #112 已经对齐过的真实 gates **整段换掉**。`run_stream_execution_contract_bundle.py` 全树只出现在本 plan `:156`，名称像执行栈 bundle，即使已注释，仍是跨栈 runbook 残留。F-R5 不允许本船为了让命令变绿去新建该脚本；若实施侧「补建」并按 unified-daily-bars 去接 `StockDataReader` / `common/integrations`，会直接打穿 F-R1 / F-R9 包边界。
- **建议回填（只改 plan 文本，不代改）**：§7 第 2 步改回 `python-tests.yml:38-43` 四条现存 gates；删除或明确「本仓无此入口、本船不跑」两条幽灵命令；Slice C DoD 与 pass criteria 跟着改。禁止为通过验收去创造 `run_common_package_contract_gates.py`。

### 🟡 P-E2｜冻结表相对 #112 工作清单与热路径真源漂移，挡不住表外类比改动

- **位置**：plan `:159-168`（§7 freeze bash）与 `:178-192`（§8 九文件表）自洽，但窄于上一船 `docs/backtest/plan-industry-align-refactor-2026-09-18.md:302-314`。
- **本仓事实**：
  - 九个表内生产文件全部存在；`git diff --exit-code 41f3d11a34c665cc8a21b3e1d351b9e06b0466b5 HEAD -- <九路径>` 退出 0。
  - #112 冻结而本船丢掉的现存文件：`backtest/research/csv_artifacts.py`、`csv_strategy_books.py`（`csv_artifacts.py` 写 trades/summary 产物契约）。
  - `limits is None` 的板型真源不在九文件内：`backtest/research/market_layer.py:73-79`（未知板块 `limit_prices` → `None`）；书侧封装在未冻结的 `backtest/research/csv_common.py:66-80`（含 `qlib_limit_prices` 这条已在树内的 Exchange 带宽类比，以及 `book_limit_prices`）。
  - 热路径枚举在 `tests/test_ashare_simulate_import_fence.py:13-29`，含 `csv_common`、`market_layer`、`csv_strategy_books`、`csv_pool`、`exdiv_map`；围栏拒绝 qlib / `trade_fee_policy` / `backtest.lebs` / `ashare_fill_clock`（`:45-48`）。§7 pytest 清单（plan `:145-150`）**没有**跑这个围栏文件，也没有 `tests/test_csv_minute_backtest.py`。
- **为什么要记**：九文件 diff 通过，不能证明「零行为」。改 `market_layer.limit_pct` 或 `csv_common.book_limit_prices`，分叉语义变了，§7 freeze 仍绿。丢掉 `csv_artifacts.py` 会给 #112 P2=B（给 `trades.csv` 加 `session_phase` / `price_rule` 列）留出表外通道——这不是 P1=B/C 成交时钟，但是同一组后置裁点的产物契约。不跑 import fence，则 F-R9「不要把 fill_clock / qlib / LEBS 接进热路径」在本船验收里没有机械门。
- **建议回填**：九文件作为 fill-gate 重点冻结可保留；另加 (a) base→HEAD 全量 changed-path 只允许 docs + 点名的 data-free tests；(b) 至少把 `market_layer.py`、`csv_common.py`、`csv_artifacts.py` 纳入 freeze 或纳入「表外生产文件也失败」；(c) §7 pytest 补 `tests/test_ashare_simulate_import_fence.py`。不要把 `qlib_limit_prices`（`csv_common.py:66-70`）借本船「对齐」成默认带宽。

### 🟡 P-E3｜§2.3 把 halt/zero-K freeze 锚到 mark 测试，属于文档漂移，不是行为证据

- **位置**：plan `:48` 引用 `tests/test_csv_daily_backtest.py:964` 与 `tests/test_daily_mark_cache.py:30-36` 作为「Halt / zero-K freeze semantics」。
- **本仓事实**：`:964-987` 是 `test_halt_day_equity_uses_last_close_not_cost`，断言净值用昨收不是成本（`:986-987`），**不断言禁买禁卖**。`tests/test_daily_mark_cache.py:27-38` 是 `market_close_mark` / `last_close_mark` parity。真正零量买卖冻结从 `tests/test_csv_daily_backtest.py:990` 起（无 SELL `:1050`、无 BUY `:1052`、`skip_no_bar==1` `:1055`）。
- **为什么要记**：这是锚点被误读，正是本船声称要防的事故。Slice A（plan `:96-107`）若按 §2.3 去「复用/扩展」`:964`，会把估值测试当成 freeze 契约。pattern-evidence 不把这条升级为重开 #108：E-R4 冻仓语义仍在 `engine-ashare-correctness.md:63`，只是本 plan 指错了测试。
- **建议回填**：halt 行改锚 `tests/test_csv_daily_backtest.py:990-1059`（及 chase pending `:1062`）；mark 单独一行。

### 🟡 P-E4｜§9 OSS 表本身是 analogy-only（该项通过）；session-phase 行是 #112 遗留类比，不是本船 fill-gate 证据

- **位置**：plan `:196-201`。Slice B DoD（`:114`）写「do not treat OSS references as behavior evidence」。F-R9（`:65`）禁止把 Cerebro / qlib PortAna/Exchange / 跨栈 import 当证据。
- **本仓事实**：§9 两行都有明确上限（「Analogy only」「Labels do not authorize changing fill policy」）。生产 `backtest/research/csv_*.py` 中 **零处** 引用 `session_phase` / `price_rule`；这两个名字只活在未接线叶子 `backtest/research/ashare_fill_clock.py:16-27`、`:30-36`。热路径围栏已拒绝 `ashare_fill_clock`（`tests/test_ashare_simulate_import_fence.py:48`）。plan 未提议复用 `chip_indicator` 或 `StockDataReader`。
- **残留风险**：session-phase 命名是 **#112 的主题**，不是本船 fill-gate 分叉。把它留在本 plan §9，实施侧可能把 Slice B 理解成继续加相位标签，或把 F-R4「gate pass ≠ fill」做成事件驱动订单状态机（OSS 第一行的 event-driven 类比）。上一船已写明不建 OMS / 事件总线（`plan-industry-align-refactor-2026-09-18.md:143`、`:260-266`）。本船 §5（`:84-87`）禁止 fill-clock 重开与新 14:57 政策，足以挡住 P1=B/C，但 §9 第二行仍是主题漂移。
- **建议回填**：§9 可保留「gate vs fill 分态」类比，但删掉或降级 session-phase 行，并写明「不得新增 trades 列、不得把标签接进扫描器、不得引入订单对象」。OSS 表继续不得进入 Slice A 断言。

### 核验为准确、无需勘误（留档）

- IMPLEMENTATION_BASE：plan 头部 `:5` 与 §7 `:139` 均为 `41f3d11a34c665cc8a21b3e1d351b9e06b0466b5`，等于本机 `origin/master`；`git cat-file -e` 与 `merge-base --is-ancestor` 退出 0。与 BOX_FACTS 一致。未 fetch，不声称远端 tip 实时核验。
- §2.1 书侧 `limits is None` early reject 属实：`csv_daily_backtest.py:321-323`（仓位循环 `:325`）、`csv_minute_backtest.py:601-603`（plan 写 `:600-603`，600 行只是 `book_limit_prices(...)` 收括号，拒绝本体是 601-603）、`csv_simulate_loop.py:155-157` / `:260-261`。
- §2.1 v7 首次进场 `priced is None` 属实：`csv_minute_backtest_v7.py:389-391`（plan 写 `:390-391`，389 是赋值）。held 路径先算 `session_limit_prices`（`:326`），再 `defer_sell_at_limit` / `skip_buy_at_limit`（`:342-353`、`:367-373`、`:402-405`）。谓词 `ashare_session.py:73-78` 在 `limits is None` 时返回 `False`（fail-open）。
- 已有分叉 pin：`tests/test_ashare_simulate_predicates.py:119-134` `test_none_limits_sell_side_records_existing_split`（v7 卖出；书侧冻结）。Slice A 不得把它写成「本船新发现」。
- §4 / F-R2 / F-R8 / §5 / §10：默认 P1–P4 = A keep deferred；**未选择 B/C**。生产扫描器在冻结表内，把 `session_phase` 接成 14:57 过滤器会碰到 `csv_minute_backtest.py` freeze。文本层面**没有**静默把 #112 P1=B/C 行为变化带回。
- §2.3 所引 T+1 / ST 测试文件行存在：`tests/test_ashare_session.py:15-18`；`test_ashare_simulate_predicates.py:87`；`test_csv_daily_backtest.py:883/:901/:925/:950`；`test_csv_minute_backtest_v7.py:199-205`（plan 写 `:202`）。
- 旧 plan 人裁记录存在：`docs/backtest/plan-industry-align-refactor-2026-09-18.md:125-135`（P1–P4 已裁 A/A/A/A）。本 plan `:49` 指向 `:129-132` 作为后置来源，行号落在选项表内，足够。
- F-R1 与 `docs/backtest/engine-positioning-ssot.md:11-16` 一致：本仓只做向量化研究引擎，不与 LEBS / 真栈合成。plan 未提议复用 `chip_indicator`。

---

## 4. 对 P1–P4 默认继续后置的独立立场（不计票）

前提：#108 / #112 已 MERGED（BOX_FACTS；本次未联网重查 PR）。#112 人裁已是 A/A/A/A。本 plan §4 是再确认，不是新的 B/C 菜单。pattern-evidence 反对的是验收路径类比，不是反对继续后置。

| 裁点 | 独立立场 | 理由 |
|---|---|---|
| **P1** | **支持继续 A** | B/C 会改 14:57 触价资格。本船没有新的交易所撮合证据；§9 session-phase 行只是类比。现有叶子 `ashare_fill_clock.py:21-27` 未接线，扫描器在冻结表内。Slice A 的 gate 测试**不授权**把 `closing_call` 写成 `continue`。不选 B/C。 |
| **P2** | **支持继续 A**；附冻结补洞 | 不加 `session_phase` / `price_rule` 列。可观测性用测试断言，不升级产物 schema。P-E2：把 `csv_artifacts.py` 补回 freeze，避免表外加列被当成「只改 docs/tests」。 |
| **P3** | **支持继续 A** | 不改费率、ST PIT、v7 `limits=None` fail-open。Slice B 只允许把分叉写成 as-built 契约，**不得写成已批准正确**；修复路径仍留在后置 P3。禁止借 OSS「行业惯例」把 fail-open 改成 fail-closed。 |
| **P4** | **支持继续 A** | 触价资格与标记价继续分开。P-E3 已说明 `:964` 是估值不是冻结；不能用 mark 测试去联动改成交。 |

§10.2（plan `:208`）「Human confirms P1-P4 remain deferred」应读作**再确认既裁 A**，不是重开选项窗口。实施侧若把这行当成可以改选 B/C，才是重开 #112。

---

## 5. 亲验清单

| 检查 | 结果 |
|---|---|
| cwd / HEAD / origin/master | `pwd` = `/workspace/wt-industry-align-impl`。`git rev-parse HEAD` = `eb5eb6ca2c1f333e36aaaa72af5f749b8c1da3cb`。`git rev-parse origin/master` = `41f3d11a34c665cc8a21b3e1d351b9e06b0466b5`。`git branch --show-current` = `docs/industry-align-next`。相对 master 已提交 diff 仅本 plan 一文件。工作区另有未跟踪的 `docs/architecture/reviews/2026-09-19/`（本评审产出）。未 fetch。 |
| IMPLEMENTATION_BASE | plan `:5` == §7 `:139` == 本机 `origin/master` == `41f3d11a34c665cc8a21b3e1d351b9e06b0466b5`。`git cat-file -e` 成功；`git merge-base --is-ancestor` 退出 0。SHA 三处一致，无伪造、无与 origin/master 漂移。 |
| §7 pytest 路径 | 五个文件均存在：`tests/test_ashare_session.py`、`test_ashare_simulate_predicates.py`、`test_csv_daily_backtest.py`、`test_csv_minute_backtest_v7.py`、`test_daily_mark_cache.py`。路径存在 ≠ 已跑过。相对 #112 序列，本清单未列 `tests/test_csv_minute_backtest.py`、`tests/test_ashare_simulate_import_fence.py`、`tests/test_ashare_fill_clock.py`（后两者均存在于树中）。 |
| §7 脚本真实存在性 | `scripts/run_common_package_contract_gates.py` **缺失**（必跑，P-E1）。`scripts/run_stream_execution_contract_bundle.py` **缺失**（已注释，当前不执行）。`git log --all` 无历史。真实 CI gates 在 `scripts/gates/verify_*.py`，本 §7 未引用。 |
| 冻结表 | §8 九个生产文件全部存在，与 §7 bash 清单一致。对 `IMPLEMENTATION_BASE..HEAD` 九路径 `git diff --exit-code` 退出 0、无输出。局限见 P-E2（漏 `market_layer.py` / `csv_common.py` / `csv_artifacts.py` 等）。 |
| book `limits is None` | `csv_daily_backtest.py:321-323`、`csv_minute_backtest.py:601-603`、`csv_simulate_loop.py:155-157` / `:260-261` 确为 early reject。 |
| v7 `limits is None` | 首次建仓 `csv_minute_backtest_v7.py:389-391`；held 路径 `:326` 然后 `:342-353` / `:367-373` / `:402-405`。谓词 `ashare_session.py:73-78` fail-open。 |
| 已有 fork pin | `tests/test_ashare_simulate_predicates.py:119-134` 已锁 v7 卖出 vs 书侧冻结。 |
| halt 锚点 | `test_csv_daily_backtest.py:964` = equity mark；零量买卖冻结从 `:990` 起。 |
| §9 OSS | 标题与两行上限均为 analogy-only；生产 csv 引擎未引用 OSS 名称，也未引用 `session_phase`。未把 OSS 当行为证据。session-phase 行是 #112 遗留类比（P-E4）。 |
| `chip_indicator` / `StockDataReader` | 本 plan 未提议复用。`StockDataReader` 出现在幽灵脚本的类比源 `unified-daily-bars-plan.md`，不得借 §7 补建带进来。 |
| 是否静默重开 #112 P1=B/C | **未发现。** §4 明确 A；F-R2 / F-R8 / §5 禁改 fill-clock。扫描器在冻结表内。#108 / #112 MERGED 采用 BOX_FACTS，未联网重查 PR。 |

---

## 6. 未验证项

- 未运行 pytest、未跑 `scripts/gates/verify_*.py`、未安装 CI 依赖；不声明任何测试已通过。
- 未执行回测、未读 F 湖、未用真实行情。
- 未联网查询 GitHub PR #108 / #112；合并状态采用用户 BOX_FACTS。
- 未 fetch `origin/master`；只核验本机 ref。
- 未证明 v7 全部输入适配路径与书侧 daily loader 对零量占位有同一处理；P-E3 只否定所引 `:964` 足够，不断言全仓无 freeze 测试。
- 未对 `common/` 全树做新的 import 边界扫描；P-E1 只证明 §7 引用的脚本不存在，且其文档出处属于另一包。
- 对抗草案不计票；本文件不代替 host 勘误表，也不改 plan。
