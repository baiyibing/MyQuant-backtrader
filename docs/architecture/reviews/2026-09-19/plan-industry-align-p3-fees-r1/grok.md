<!-- agent=grok cmd-prefix=/home/box/.local/bin/grok -p 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-industry-align-p3-fees-2026-09-19.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-19/plan-industry-align-p3-fees-r1/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓第一方回测是 **向量化 CSV**（日线/分钟）+ path-SSOT 只读行情。Cerebro / Rolling 已全局退场（2026-09-16，PR #58；禁止复活）。无实盘、无 QMT 下载、无 Redis 流。引擎分工见 `docs/backtest/engine-positioning-ssot.md`。把握不准可读代码或做实验，以事实为准。

【本仓必查盲区（评审必须逐条核对）】
- **T+1 / 隔日成交**：买入日 `n_days=0` 能否卖出？日线止盈是当日收盘还是 `pending_exit` 次日开？有无用到未来 bar？
- **复权口径**：向量化成交与均线必须同一套 `adjust_type=none`。禁止把筹码默认 front 套到 CSV 书上。
- **盈筹率尺度**：本仓筹码 `cyqk` 是 0–1。本 plan 若声明不适用，禁止把盈筹带进 1–8 书。
- **涨跌停 / 停牌**：涨停禁买可卖、跌停禁卖；`limit_pct` 档位与北交/ST 是否建模必须写清。
- **包边界**：研究 CLI 走 `backtest/research/`。不要把 LEBS / MockQMT / `presets.py` 当本仓向量化实现。Cerebro 仅考古。

【裁决原则（重要）】
- 视自己与其他评审者为同行专家，**参考学习、互相验证、取长补短**：结论交叉核对、补彼此盲区，而非单纯挑错。
- **事实类断言**（函数位置 / 行为 / 数值等可验证项）→ **以代码与实验为准**：读代码取证，把握不准时跑最小实验，不靠票数下结论。
- **经验/取舍类断言**（该不该这样做、风险量级、更稳的写法）→ **以业内 A 股量化惯例与成熟开源实践为准**（backtrader / 本仓 Cerebro）。
- **SSOT 一致性检查**：对照 `README.md` 布局、`common/infra/data_root.py` path-SSOT、`backtest/chip_indicator.py` 筹码包装。勿引用本仓不存在的实盘/LEBS 文档当硬 SSOT。
- **★ 安全阀/超时/并发类设计，必须跑最小实验验证行为**（不只读代码！）：timeout / budget / safety-valve / circuit-breaker / 并发锁 / 异步 / fallback / 重试——这些 bug 藏在 stdlib/框架行为里（如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效），**读代码看不出来**。实验格式：构造 slow fn + tight budget → 测调用方**何时返回**（`time.monotonic` 对比 budget_s vs 实际）。2026-07-04 实测：option-X budget docstring 宣称 "releases caller" 但实际 8s 才返（非 1s budget）——**docstring 不可信，实验为准**。**实验结论须附可复现脚本 + 完整原始输出**（含进程 pid/存活检查等），与官方文档/CPython 源码矛盾的结论标注「建议主持裁/下游复核」。2026-07-16 教训：r3 kimi 实验「subprocess.run(timeout) 不杀子进程」结论错，r4 qoder 引源码 + 主持裁亲自实验（child TERMINATED）才纠正——下游 incorporate 实验断言须亲自复现。

【输出格式】
按严重度分级，每条尽量带 file:line 证据：
- 🔴 必须修（事实错误 / 会误导实现 / 逻辑矛盾）
- 🟡 应修（设计缺口 / 风险）
- 🟢 可选（nice-to-have）
- ✅ 做对的地方（保留）
末尾给一句总评 + 是否可进实现。

【你的评审侧重】优先**实现 / 协议 / Linux-VM CLI**：核对实现是否可落地、协议/契约用词是否越界、Linux 侧 CLI 与编排是否可 headless 跑通。 --permission-mode bypassPermissions --always-approve <prompt> -->
先读设计稿全文，再对照仓内代码与文档取证；只出评审意见，不改任何文件。设计稿已读完。接着核对照锚代码、验收脚本和其他已完成评审意见。并行目录里已有其他评审员文件。先看它们是否已完成，同时继续核对照锚代码。其他评审员仍在写 prompt，我独立取证：核对行号锚点、CLI 脚本、日线/分钟/v7 费用路径和必查盲区。其他评审已完成。正在交叉核对他们的 🔴/🟡，并用代码验证，避免误判。# 评审：`plan-industry-align-p3-fees-2026-09-19.md`（v0.3.1 / δ1）

侧重：**实现可落地、契约用词、Linux-VM headless CLI**。只读取证，未改任何文件。  
并行交叉：已读完 **codex**、**cursor-auto**、**kimi** 成稿。超时/并发安全阀：本 plan 无此类设计，不构造假实验。

亲复现（pid `3555867`，仅 `ashare_fees`，无 pandas）：

```
DEFAULT_SCHEDULE is BILATERAL_10BP True
two-lot SELL 100sh@10 15bp min5 per-call 10.0 agg 5.0
book cash incr 1990.0 v7-one-call cash incr 1995.0
```

`IMPLEMENTATION_BASE=f548cc2ff808e7ecd5357e4d3786a62c76d8f8c5` 与当前 `origin/master` / `HEAD` 一致，且为祖先。

---

## 🔴 必须修

### R1 · §8 验收命令盖不住 Slice B，且与 E-r2-01 自相矛盾

§7 要求新增/扩展接线测试，并写明 **predicates 不得标成 fee-wiring 闭环**；§8 却把既有三文件标成「delta1 contract surface」，且 **没有** 把 Slice B 新测编进命令：

```183:186:docs/backtest/plan-industry-align-p3-fees-2026-09-19.md
python3 -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_fees.py \
  tests/test_ashare_simulate_import_fence.py \
  tests/test_ashare_simulate_predicates.py
```

现有 `tests/test_ashare_fees.py:10-24` 只钉公式/重导出，不经 `execute_buy` / `_sell` / `simulate`。  
`tests/test_ashare_simulate_predicates.py` 是涨跌停/T+1 门，不是费率接线。

若实现者把接线测放进 `test_csv_daily_backtest.py` / 新文件，§8 仍可全绿。这会让 E-r2-01 在验收层复活。

**改法（写进 plan，不要口头约定）：**

1. 指定唯一落点，例如只扩 `tests/test_ashare_fees.py`，或新建 `tests/test_ashare_fee_wiring.py` 并列入 §8。  
2. §8 拆两行：fee-wiring 文件 = 闭环；predicates + fence = 围栏/冻结旁证，**不叫** contract surface。  
3. F-R7「禁止回测」改成：**禁 CLI/湖回测；允许纯内存合成 `simulate`**（否则执行者会把 Slice B 退回静态 `is` 断言）。

交叉：同意 **codex R1**；**kimi** 标「零 🔴」漏了这条协议缺口（锚点行号对 ≠ 验收能跑到交付物）。

### R2 · §2.4 仍无「可锁定的 totals」，E-r2-02 未闭合

Host 要求 two-lot **numeric** example。现稿只有「两次 floor / 总量可不等」。Slice B 却写 *locks the documented as-built totals*——文档没有 totals，实现没有靶。

亲复现（与 **cursor-auto R1** / **codex R2** / adv-r2 pattern-evidence 同数）：两 lot、各 100 股、价 10、卖 15bp、min 5；须 T+1 可卖：

| 调用 | 佣金 | 现金增加 |
|---|---:|---:|
| 书 `_sell` ×2 | 10 | 1990 |
| v7 一次 `_sell_lots` | 5 | 1995 |
| v7 两次 `_sell_lots` | 10 | 1990 |

```242:244:backtest/research/csv_ledger.py
def _sell(...):
    notional = pos.shares * px
    comm = trade_commission(notional, st.sell_cost_rate, st.min_cost)
```

```240:242:backtest/research/csv_minute_backtest_v7.py
    sold = wanted - remaining
    position.lots = kept
    state.cash += fee.credit_sell(sold * price)
```

默认 `BILATERAL_10BP`（min=0）两路径都是 2 元，**钉默认费率测不出 floor 分叉**。Oracle 必须显式 `QLIB_PORTANA` / 等价 15bp+min5，并写清粒度是 **每次函数调用**，不是每标的/每天。

交叉：同意 **cursor-auto R1** 升 🔴；**codex R2** 同事实但标 🟡——「locks documented totals」而文档无 totals，实现会卡住，故维持 🔴。

---

## 🟡 应修

### Y1 · `DEFAULT_SCHEDULE is BILATERAL_10BP` 钉不住书引擎默认

书/分钟扣费走 `SimState` 三 float，**不**经 `FeeSchedule`：

```87:89:backtest/research/csv_ledger.py
    buy_cost_rate: float = COMMISSION
    sell_cost_rate: float = COMMISSION
    min_cost: float = 0.0
```

v7 才吃 `fee: FeeSchedule = DEFAULT_SCHEDULE`（`csv_minute_backtest_v7.py:204,225,279`，且内部 `fee=fee` 真传下去）。  
改 `DEFAULT_SCHEDULE` **不会**改日线/分钟默认。

Slice B 已有「minute inherits SimState defaults」，但未写并列钉：

- `DEFAULT_SCHEDULE is BILATERAL_10BP`（仅 v7/模块指针）  
- `SimState()` 三字段 `== (COMMISSION, COMMISSION, 0.0)`，且与 schedule **数值同构**  
- 禁止用替换模块级 `DEFAULT_SCHEDULE` 冒充 v7 参数透传

交叉：同意 **cursor-auto R2** 事实；严重度降为 🟡——§7 已点到 SimState，缺的是双指针写法，不是完全没写。

### Y2 · 书 `trades.csv` **已有** `commission`；§2.5 用词越界

P2 锁的是 `session_phase` / `price_rule`（refactor `:131`），不是佣金列。书路径 as-built：

```229:230:backtest/research/csv_ledger.py
            "commission": comm,
            "reason": reason,
```

`csv_artifacts.py:149-150` 整表落盘。夹具 `tests/fixtures/csv_engine_pre_er1/version6_trades.csv` 表头已含 `commission`。  
v7 `_event`（`:196-199`）无该列。

§2.5 应改成：书产物已有列，δ1 **不改 schema、不给 v7 补列**；内存 oracle 可对书 `trades[].commission` 断言。EOD_MARK 行 `commission: 0.0`（`csv_simulate_loop.py:337`）不得当卖出扣费。

交叉：同意 **cursor-auto Y3/Y4**。

### Y3 · Linux-VM §8 缺解释器/cwd 前提；不要抄 README 的 Windows `python.exe`

`AGENTS.md:27-30`：解析 `OSKH_MERGE_PYTHON` → `VANNA312_PYTHON`，禁止隐式系统 Python。  
`docs/backtest/README.md:14-24` 入口是 `D:\anaconda3\envs\vanna312\python.exe` + `^` 续行，**不是** Linux 验收命令。

本环境 `python3` 能 import `ashare_fees`，但 `csv_ledger` 因无 pandas 失败——裸 `python3 -m pytest` 在未装依赖的 VM 上会直接炸。  
§8 应写死：

- cwd = 仓根  
- 解释器 = 已解析项目环境（CI 靠 setup-python + pip；本地不要系统 python）  
- `git fetch` 无 timeout，离线/无网会挂；已有 `origin/master` 时可跳过 fetch，但仍做 40-char 相等与 ancestor 检查  
- 四个 gate 脚本路径真实且 data-free（同意 kimi 实验 2 的存在性结论；本次未重跑 gate）

交叉：同意 **kimi 🟡-2 / codex R4** 前半，按 Linux-VM 改写。

### Y4 · 费率是研究代理，不是 2023-08 后印花真值

`BILATERAL_10BP` = 双边 10bp 无 floor；`QLIB_PORTANA` = 买 5bp / 卖 15bp / min 5（`ashare_fees.py:17-20,53-55`）。  
`trade_fee_policy.py:13` 才是卖方印花 + 过户（热路径围栏禁止 import）。  
`backtest/research/engine.py:36-38` 另一套占位（佣 0.5bp + 印花 5bp），**不是** CSV 书引擎。

Slice A 必须一行写清：研究默认 ≠ 券商账单；`--qlib-cost` 是 qlib Exchange 保真，不是现行印花；以后若对齐实盘，禁止把印花再加一层（双重计入）。  
P3.2=A 不改热路径——正确，不必本轮做印花 booking。

交叉：同意 **kimi 🟡-1 的风险**；**不同意**把「15bp = 5 佣 + 10 旧印花」写成仓内已证事实——`ashare_fees.py` 没有该分解。经验类注解即可。

### Y5 · 消费面还有两条「像 SSOT、不是 δ1」的路径，须显式 park

- `unified_exit_modea.py:369-371`：`(1±COMMISSION)` 线性近似，**不走** `trade_commission` floor，也不在 freeze 十文件里。  
- `backtest/research/engine.py:21-24`：import `trade_fee_policy`（围栏是枚举热路径，不含此文件）。

δ1 写一句「非 CSV 书/v7 消费面，禁止当接线证据」即可，防后人扩围栏或改错模块。  
path-allowlist（仅 `docs/` + data-free `tests/` + freeze 集）建议升 **硬门**：`git diff --name-only` 一行。同意 **cursor-auto Y5/Y7**。

### Y6 · CLI 不对称是 as-built，测试入口要写到函数级

| 入口 | 费率旋钮 |
|---|---|
| `csv_daily_backtest.py:658-685` `--qlib-cost` | 三 float 打进 `simulate`（不传 `QLIB_PORTANA` 对象） |
| `csv_minute_backtest.py:493+` / CLI `:866-898` | **无** fee kwargs / **无** `--qlib-cost` |
| `csv_minute_backtest_v7.py` CLI `:507-518` | **无** fee 旗标；只有 Python `simulate_v7(..., fee=)` |

Slice B 调用链（同意 **codex R3**，压缩为硬约定）：

- daily：`simulate(..., buy_cost_rate=..., sell_cost_rate=..., min_cost=...)` 断言成交佣金与现金；CLI 用 argv 替身，**禁止**进湖加载。  
- minute：跑合成 `simulate`，断言买卖后 `st.buy_cost_rate` 仍为默认，且佣金按 10bp。  
- v7：`simulate_v7(..., fee=custom)` 买卖两端现金。  
- 现金门必测（不要 “where cheap”）：恰好够 vs 含费差 1 分；拒单后现金/仓/trades 不变。`execute_buy:212` 与 v7 `_buy:208` 都是 `cost > cash`。  
- 可复用合成夹具：`tests/test_csv_daily_backtest.py`、`test_csv_minute_backtest.py`、`test_csv_minute_backtest_v7.py`；`tests/test_qlib_bin_daily.py:129-135` 已钉 `execute_buy`+qlib 费率，扩展时引用，勿只测纯公式。

**kimi 🟡-3**（分钟 CLI 无 `--qlib-cost` 负向 pin）：本船 `csv_minute_backtest.py` 已在 freeze 集，加旗标会撞 §8 `git diff`。可做，非必须。

---

## 🟢 可选

- 围栏是静态 AST，动态 `importlib.import_module` / `__import__` 可逃（kimi 实验 4）。小团队 freeze + 枚举清单可接受；补 banned 文本扫描成本低。  
- 锚点 off-by-one：`trade_commission` def 在 `:23` 非 `:24`；`FeeSchedule` class `:35`；印花 docstring `:8-9`。Slice A 顺手改。  
- §1 称 refactor `:131-132` 记 P3/P4；该处是 **P2+P3**，P4 在 `:133`。  
- §8 tip 相等 fail-closed 是特性，加注释以免 master 前进后以为脚本坏了。

---

## ✅ 做对的地方（保留）

- 单船 δ1 + P1/P2/P4 停放；人裁 P3.1/2/3 = A/A/A 与 as-built 一致，不重开印花 booking。  
- 消费地图正确：日线可覆盖、分钟吃 `SimState` 默认、v7 显式 `FeeSchedule` 且 `fee=fee` 传到 `_buy/_sell_lots`。  
- F-R4/F-R5 + fence 禁 `trade_fee_policy` 进热路径；`ashare_fees` 已在枚举清单（`test_ashare_simulate_import_fence.py:23,46-48,70-76`）。  
- E-r2-03 收窄 freeze 证明力；三重 `git diff`（base..HEAD / worktree / cached）可 headless。  
- 四个 gate 脚本真实存在，无 ghost name。  
- 生产 freeze 含 `ashare_session` / `market_layer` / `csv_artifacts`，避免借费用船改 T+1、涨跌停、产物 schema。  
- OSS 表标明 analogy only，未把 Cerebro/qlib API 当行为证据。

---

## 必查盲区（本船核对，不改语义）

| 盲区 | 结论 |
|------|------|
| T+1 / `n_days=0` | `t1_sellable` = `buy_date < session`（`ashare_session.py:39-41`）。买入日不可卖。分钟 `(not can_sell) or n_days < 1`（`csv_minute_backtest.py:270`）。δ1 冻结 session，不改。 |
| 日线止盈时点 | **不是**一律次日开。`pending_exit` → 下一可卖日 open（`csv_daily_backtest.py:329-333`）；`daily_same_bar_prefixes` 通过涨跌停门才当日 close（`:398-401`）。无未来 bar。 |
| 复权 | 日线默认 `dividend_type=none`（`csv_daily_backtest.py:6-7,500`）。API 仍允许 front/back；费用夹具必须 none，禁止套筹码 front。 |
| 盈筹 `cyqk` | 本 plan 未引入，正确。`backtest/chip_indicator.py` **不存在**（现为 `backtest/chip_algorithm.py` + `research/chip/`）。不要把 chip 包装写进 1–8 书。 |
| 涨跌停 / 停牌 | 涨停禁买、跌停禁卖（`ashare_session.py:73-78`）。档位：主板 10 / 创科 20 / 北交 30 / 名称 ST 5 / 未知 `None`（`market_layer.py:43-65`，E-R2）。零量当无 K。v7 `limits=None` fail-open 分叉保持。本船只冻结，不建模完整交易所规则。 |
| 包边界 | 入口 `backtest/research/csv_*_backtest.py`。不要走 LEBS / MockQMT / `presets.py` / `backtest/research/engine.py`。Cerebro 仅考古（日线 docstring 仍有 `broker.setcommission`，不是 SSOT）。 |

---

## 总评

δ1 方向对、人裁不该翻、生产代码不必动；现有 API 足够做 docs+合成单测。卡住实现的是两件契约洞：**§8 可能漏跑接线测试**，以及 **floor 数值 oracle 仍未写进文档**。补上 R1/R2（Y1–Y5 顺手进 Slice A 文本）后可进 Slice A→B→C。  
**是否可进实现：有条件可以（先修订 🔴；docs+data-free tests；不改生产、不重开 P3.\*）。**
