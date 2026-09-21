<!-- agent=codex cmd-prefix=C:\nvm4w\nodejs\node.EXE C:\Users\Thinkpad\AppData\Roaming\nvm\v24.19.0\node_modules\@openai\codex\bin\codex.js exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】E:/PycharmProjects/MyQuant-backtrader/docs/backtest/plan-strategy12-jinrongyuan-2026-09-21.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-21\plan-strategy12-jinrongyuan/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本地 redis/数据库已就绪、国金 miniqmt 已登录；把握不准可读代码或做实验，以事实为准。

【裁决原则（重要）】
- 视自己与其他评审者为同行专家，**参考学习、互相验证、取长补短**：结论交叉核对、补彼此盲区，而非单纯挑错。
- **事实类断言**（函数位置 / SQL / 行为 / 数值等可验证项）→ **以代码与实验为准**：读代码取证，把握不准时跑最小实验，不靠票数下结论。
- **经验/取舍类断言**（该不该这样做、风险量级、更稳的写法）→ **以业内 A 股量化惯例与成熟开源实践为准**。
- **SSOT 一致性检查**：若方案涉及数据格式/符号规范/配置键/API 契约等，**必须对照仓库 SSOT 文档**（`docs/backtest/data/symbol-format-ssot.md`、`docs/SSOT.md`、`docs/operations/disclosure-data-source-ssot.md` 等）检查是否冲突。若方案与 SSOT 不一致，标记为 🔴 并指出具体 SSOT 文件及条目。
- **★ 安全阀/超时/并发类设计，必须跑最小实验验证行为**（不只读代码！）：timeout / budget / safety-valve / circuit-breaker / 并发锁 / 异步 / fallback / 重试——这些 bug 藏在 stdlib/框架行为里（如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效），**读代码看不出来**。实验格式：构造 slow fn + tight budget → 测调用方**何时返回**（`time.monotonic` 对比 budget_s vs 实际）。2026-07-04 实测：option-X budget docstring 宣称 "releases caller" 但实际 8s 才返（非 1s budget）——**docstring 不可信，实验为准**。**实验结论须附可复现脚本 + 完整原始输出**（含进程 pid/存活检查等），与官方文档/CPython 源码矛盾的结论标注「建议主持裁/下游复核」。2026-07-16 教训：r3 kimi 实验「subprocess.run(timeout) 不杀子进程」结论错，r4 qoder 引源码 + 主持裁亲自实验（child TERMINATED）才纠正——下游 incorporate 实验断言须亲自复现。

【输出格式】
按严重度分级，每条尽量带 file:line 证据：
- 🔴 必须修（事实错误 / 会误导实现 / 逻辑矛盾）
- 🟡 应修（设计缺口 / 风险）
- 🟢 可选（nice-to-have）
- ✅ 做对的地方（保留）
末尾给一句总评 + 是否可进实现。

【你的评审侧重】优先审**实现可操作性**：函数名/文件位置/调用链/API 契约——程序员能否照此编码？哪里会卡住？哪些 import 是私有的需 wrapper？ <prompt> -->
## 评审：`plan-strategy12-jinrongyuan-2026-09-21.md`（侧重实现可操作性 / 调用链 / API 契约）

**取证基线**：本仓 `HEAD=0d28ef2`，`git diff 599a894..HEAD -- backtest tests` 为空 → 计划头部锚点 `599a894` 与当前代码等价（只是落后若干 docs commit）。**并行交叉**：`_parallel/{claude,codex,kimi,cursor-auto}/*.md` 当前只有命令行 prompt 回显头，无已完成意见可核对，故本篇独立取证（未引用他人条目）。

---

### 🔴 R1 部分卖在默认路径会**静默丢股**（实验实证，必须写进切片 B 完成定义）

`_sell` 的减股动作被关在容量/除权分支里：

- `backtest/research/csv_ledger.py:400-411`
  ```
  400: if st.volume_cap is not None or st.exdiv_economics is not None:
  401:     pos.shares -= shares
  ...
  408: lots = st.positions.get(code) or []
  409: st.positions[code] = [p for p in lots if p is not pos]   # 整 lot 删除
  ```
- 日线引擎全程不设 `volume_cap`（赋值点只有 `backtest/research/csv_minute_backtest.py:585`；`csv_daily_backtest.py` 全文无 `volume_cap`）；`exdiv_economics` 仅在显式传入时才挂（`csv_daily_backtest.py:288-289`）。

实验（`python -B -`，stdin 直跑，未落盘任何文件）：

| 场景 | 结果 |
|---|---|
| `volume_cap=None, exdiv=None` | `cash=9990.00 pos.shares=1000 positions={}` |
| `volume_cap.clamp` 给 400 股（真实 `ashare_volume_cap.py:82 filled=min(wanted, remaining)` 语义） | `cash=3996.00 pos.shares=600 lots=[600]` |

即：**容量分支下部分卖已能工作**（实验 B，说明计划 §2「share 级部分卖结构上可表达」这一句只在 `volume_cap` 分支成立，措辞需改）；**默认分支下**只要程序员按计划「卖出路径加 `wanted_shares`」照做，就会得到「部分现金入账 + 整个 lot 被删」——剩余股数凭空消失且不抛异常（daily 全默认路径 + minute 未开容量 cap 时都命中）。切片 B 的 DoD 必须写明：`pos.shares -= shares` 提到条件外、非零余股保留 lot、空 lot 才删除，并补一条「部分卖后 `sum(lot.shares)` 与 cash 守恒」的 pin。

---

### 🔴 R2 书↔引擎契约未定，程序员无法照此编码

计划只在正文说「卖出路径可选 `wanted_shares`」「书侧状态机 + 买回」，但三个必需签名全部缺失：

- 现有消费面（事实）：`sell_gate(code, px, day, closes)`（`csv_daily_backtest.py:393`；`csv_minute_backtest.py:317,666`）、`buy_gate` 同签名（`csv_simulate_loop.py:173,289`）、`step_add(lots, px)`（`csv_simulate_loop.py:353`）。单一 str reason 无法表达「减仓 50% / 止损 / 买回哪条通道」三态。
- 买回是**第四个买因**：现有三因即 `run_pool_buys_day` / `run_chase_due_day` / `run_step_adds_day`（`csv_simulate_loop.py`），买回需要新函数，模板现成：`run_step_adds_day`（`csv_simulate_loop.py:322-395`，含涨跌停、`buy_gate`、`skip_cash`、`quota_used` 保存/还原、`execute_buy(reason="add:step20")`）。
- 注册表侧要同步：`apply_csv_strategy` 的 `hooks.setdefault(...)`（`csv_strategy_books.py:119-136`）新键不登记就会在默认 `None` 语义上漂移。

**请补三行签名草案**（否则至少产生三套自创实现）：`exit_plan(code, px, day, closes, lots) -> tuple[str, int] | None`、`buyback_plan(code, px, day, closes, lots) -> int`、`run_buybacks_day(...)`（照 `run_step_adds_day` 参数面），并点明日线/分钟两处调用点。

---

### 🔴 R3 复用 v8 wiring 会与均线卖出书冲突（涨停保留 → 整仓卖绕过 `sell_gate`）

- `strategy8_rules.py:36-37`：`RESERVE_LIMIT_UP = True`、`DEFER_LIMIT_UP = False`；`csv_strategy_books.py:582`：v8 `daily_same_bar_prefixes=("open_board",)`。
- 消费点 `csv_daily_backtest.py:384-396`：`reserved` 命中涨停 → `continue`；否则 `reason="open_board"` **整仓卖**；只有 `else` 分支才调 `sell_gate`。

计划 §0/§2/§6 说「买侧复用 v8 钩子（含其 wiring delta）」「P6 同 v8」，但 v12 的核心是部分减仓状态机：继承该位后，涨停保留路径会整仓清仓且**不进 reduced/stopped 记忆** → 买回状态机失步（卖了却不记得卖了多少）。方案须显式裁决 v12 的 `reserve_limit_up` / `defer_limit_up` / `daily_same_bar_prefixes` 三个取值，以及「非本书记账口径的整仓卖（open_board 等）」如何与双记忆交互。

---

### 🔴 R4 P9④ 的 per_name 上限会**饿死买回**（与 P2/P6/docx 规则 2 自相矛盾）

- `csv_simulate_loop.py:253-254` 仅 `not allow_add` 时挡持仓；v8 `ALLOW_ADD=True`（`strategy8_rules.py:17`）→ 名单再现即每天再加一整笔 100 万，持仓市值 ≫100 万 是常态。
- P9④ 建议「当日该码市值+在途买回 ≤100 万」→ 首次买满后该条件恒不成立 → 买回几乎永久 `skip` → docx 规则 5（减仓/止损买回）静默失效，而 R2「默认零 diff」的 pin 测不出这种语义死锁。

须改成可满足定义（按「累计投入笔数/金额上限」或「买回额 ≤ 记忆减仓股份等值」），并与 P6「名单再现加一整笔」同文自洽。

---

### 🔴 R5 MA 序列价格域未定：默认不复权 → 除权日**误触发减仓与止损**（SSOT 未引用）

- 日线默认 `dividend_type="none"`（`csv_daily_backtest.py:540`）；喂给 gate 的 `closes` 出自同一 raw df（`csv_common.py:22-40`；分钟 `csv_minute_backtest.py:626,669`）；引擎除权只做 `rescale_position` + `mapped_prev_close`（`csv_daily_backtest.py:317-326`），**不改历史 close 序列**。
- 算术示例（10 送 10 除权，前 4 日收 20、除权日≈10）：昨收 MA5=(20×4+10)/5=18>10 → 触发减仓；MA10≈19 → 10 < 19×0.9=17.1 → **触发整仓止损**，而真实涨跌为 0。
- SSOT：`docs/backtest/data/daily-adjusted-update-ssot.md` §1「QMT `front` 复权 = Ground truth」、§2 路径布局；湖里 `dividend_type=front` 分区**实测存在**（`F:\stock_data\stock\period=1d\dividend_type=front\symbol=000001_SZ`）；`csv_daily_backtest.py:600-604` 明示非 none 即跳过 E-R6 remap（二选一可执行）。
- 分钟侧无该开关：`load_daily_ohlc(..., dividend_type="none")` 默认（`ashare_bars.py:88`），调用处未传（`csv_minute_backtest.py:889-896`）——要么 `--daily-source qlib_day`（`csv_minute_backtest.py:1003`，$close 连续），要么新增参数。

要求：定一个价域（建议 front），写入 D 切片 runbook 命令、HELP_LOCK 与 data_gaps；v4（同为 MA 书，`strategy4_rules.py`）同源问题一并注明，别只在 v12 悄悄分叉。

---

### 🟡 R6 部分卖队列与 `pending_exit` 的跨日交互未定

日线：reason 不在 same_bar 前缀 → `pos.pending_exit=reason`（`csv_daily_backtest.py:416-423`）→ 次日开盘按 `pos` 整仓卖（`:344-349`）。P2-B 说「次日开盘成交（pending_exit 先例）」，切片 B 说「独立部分卖队列（不复用 pending_exit）」——两句并存即未定：日线部分卖是**当天收盘成交**还是**次日开盘成交**？同一码次日同时存在「整仓 pending_exit」与「部分 pending」时谁先、是否合并？请写死。

---

### 🟡 R7 台阶计数由「活着的 lot」推导 → 减仓/止损后 **+20% 台阶会重触发**

`strategy8_rules.py:67 n_steps = sum(1 for p in lots if p.is_step)`，而 P3 规定「is_step 先卖」→ 每次 MA5 减仓都清空 is_step，`allowed > n_steps` 立即再成立 → 同一价位段重复加仓，叠加买回形成换手循环（费用 + 仓位叠加）。建议台阶改为独立单调记忆（与 reduced/stopped 同处记账），并 pin「减仓后同一 +20% 段不重加」。

---

### 🟡 R8 「书侧 dict」与切片 A 的 `data-free 纯函数 pin` 冲突，且有跨 run 泄漏

本仓书模块全是纯函数（`strategy4_rules.py` 全文；`strategy8_rules.py` 同），状态归引擎（`SimState`，`csv_ledger.py:85-98`），每 run 唯一初始化点是 `init_sim_state`（`csv_simulate_loop.py:93-109`）。模块级 dict 会在同进程多次 run / pytest 间串味且不可重放。建议记忆挂 `st`（新字段或 `st.stats` 之外的专用槽），或沿用现成 out-param 先例 `reserve_state`（`csv_minute_backtest.py:648,677`）。

### 🟡 R9 `scan_held_day` 扩返回值会牵动 24 个调用点

真实调用点：`csv_minute_backtest.py` 2 处 + 测试 24 处（`tests/test_csv_minute_backtest.py` 13、`tests/test_csv_minute_backtest_v8.py` 10、`tests/test_scan_held_day_numba_parity.py` 1，均按 5-tuple 解包，如 `tests/test_csv_minute_backtest.py:84`）。若把 `wanted_shares` 塞进返回元组，R1「既有全量测试零变更」就要被解释成「只改解包不算放宽」——建议走 out-param，别动 5-tuple。

### 🟡 R10 前置依赖顺序：`ma_infra` 尚不存在

`backtest/research/ma_infra.py` 实测不存在（仅 `docs/backtest/plan-ma-infra-shared-2026-09-21.md`）；切片 A 的 DoD 依赖它，且 `sma_live` 只在 P2-B 才有消费者、P2 仍未裁（与 ma-infra 侧评审的同类担忧一致）。请在 §5 写「先裁 P2，再放行切片 A」，或把 `sma_live` 标注为 P2-B 预留、A 切片只引 `sma_asof`。

### 🟡 R11 金榕元同名双身份（v7 vs v12）未交代

`AGENTS.md:13` 的 v7 也是金榕元且 **`--pool-dir` 必填**、不注册进 BOOKS（`csv_minute_backtest_v7.py:618-625`），而 P8 让 v12 默认读可变 `stock_pool/`。请写明 v12 与 v7 的分工/入口差异，并确认 `AGENTS.md:11-12` 名单行与 §9「Research entries 增行」是同一处（现在两处描述不同）。

### 🟡 R12 送转日记忆缩放的取整与零头未定

`ashare_exdiv_economics.py:1-7`（整数 bonus 向下取整）+ `csv_ledger.py:174-182`（增股直接并入 lot，`rescale_position` 不动 shares `:152-156`）→ 缩放后的买回目标股数可非整百；P4「全额买回（取整百）」与 P9③「按 k 缩放」的取整方向和残股处理必须写死，否则买卖回长期留零头。

---

### 🟢 可选

- **R13** 锚点微错：`execute_buy` 无 shares 覆写的取证行落在 `_buy_size`（`csv_ledger.py:219-229`），函数本体在 `:232-248`；另 R1 的「现有全量 pytest（1399+）」在本仓 `^def test_` 仅 783 个，数字疑为跨仓/参数化口径，建议改「pytest 收集数」或删数字。
- **R14** 分钟引擎容量 cap 对卖出**不做整百**（`ashare_volume_cap.py:82-85`，`buy=False` 只 `min()`）→ 书侧「向下取整 100」后仍可能被压低到非整百、且非精确 50%。建议 HELP_LOCK 写「50% 为上限，实际以容量 cap 为准」。
- **R15** `ma12:` 会落到 `else → sell_pos_trail`（`csv_ledger.py:384-397`，我实验里 `stats keys {'sell_pos_trail': 1}` 复现）。R5 已要求补桶 ✅，但注册表里**已有** `ma_signal` 前缀（`:394`）→ 可直接用 `ma_signal:MA5-derisk` / `ma_signal:MA10-stop` 复用既有桶，避免两套前缀并存（择一即可）。

### ✅ 做对的地方（保留）

- 锚点表经逐条实测**基本可信**：`chase_decision :115-121`、`queue_limit_up_chase :124-130`、T 日拦截 `csv_simulate_loop.py:285-288`、日线 `sell_gate :393`/pending 次日开盘 `:344-349`、分钟喂数 `csv_minute_backtest.py:669`、`step_add_due :57-69`、`may_add`（`csv_strategy_books.py:573`）、v8 注册 `:1018-1031`（per_name + 1_000_000.0）、`Position` 字段 `:70-82`、`rescale_position` 不动 shares `:152-156`、`pending_exit` 字面 `:79`、`_sell` 的 T+1 只在 `volume_cap` 分支 `:347`、stats 分派 `:384-397`——全部与代码一致，勘误工作有效。
- **γ 方案方向正确**：最小引擎面 + 双 hook 默认 `None` + 用既有 pin 证明零 diff，且有 `run_step_adds_day` 这一现成买因模板可照抄；比「注册表级通用钩子」更小、更可测。
- 对抗层把 FIFO 改成「is_step 先卖、lot0 最后」抓住了 `strategy8_rules.py:61-64` 的锚不变量（但请同时处理 R7 的反面：清空 is_step 会重置台阶计数）。
- P7「以文档为准（无上证闸）」、R7「不占 version11」（与 `AGENTS.md:22` 一致）、R2「opt-in 默认关闭」这三条取舍清晰，符合本仓 research 面既有契约风格。
- SSOT 核对结论：符号格式/配置键/API 契约本期无新增（符号仍走 `to_partition_key`，`csv_daily_loader.py:63`；`docs/backtest/data/symbol-format-ssot.md` 本仓不存在、由 1.3 持有），**唯一冲突项即 R5 的复权价域**（`daily-adjusted-update-ssot.md` §1/§2 未被本计划引用）。

### 实验附录（可复现、未写盘）

```powershell
cd E:/PycharmProjects/MyQuant-backtrader   # PYTHONDONTWRITEBYTECODE=1，python -B，脚本经 stdin 送入
```
```python
from backtest.research.csv_ledger import SimState, Position, _sell
class FakeCap:               # 真实 VolumeCap.clamp 同语义: filled = min(wanted, remaining)
    def clamp(self,k,at,wanted,atomic=False): return min(wanted,400), ""
    def consume(self,k,s): pass
def mk(n):
    st=SimState(cash=0.0); p=Position("000001",n,10.0,0,10.0); st.positions["000001"]=[p]; return st,p
st,p=mk(1000); _sell(st,"000001",p,10.0,"20260921","ma12:derisk",day_i=1)
print("A no-cap:",st.cash,p.shares,st.positions)
st,p=mk(1000); st.volume_cap=FakeCap(); _sell(st,"000001",p,10.0,"20260921","ma12:derisk",day_i=1,bucket_id=None)
print("B capped:",st.cash,p.shares,[x.shares for x in st.positions["000001"]])
```
原始输出：
```
A no-cap  : cash=9990.00 pos.shares=1000 positions={}
B capped  : cash=3996.00 pos.shares=600 lots=[600]
stats keys {'sell_pos_trail': 1}
```
（本计划不含 timeout/并发/熔断类构造，故按同一纪律把最小实验用在「资金/股数不变量」上；结论与 CPython/框架行为无冲突。）

---

**总评**：买侧骨架与 γ 落点选得对，锚点可靠性经我逐条实测通过；但**卖出/买回的最小引擎面还停在口号层**——R1（默认路径丢股）与 R2/R3/R4（契约缺失、wiring 冲突、上限饿死买回）任何一条都会让实施者写出「跑得通但语义错」的代码，且现有 gate 抓不到。**是否可进实现：不可**——先把 R1/R2/R3/R4/R5 写成可编码契约（签名 + 位取值 + 价域 + 上限定义）回填 v0.5，再走 P2–P9 人裁，R6–R12 建议同轮消化，R13–R15 可并入修订。
