<!-- agent=codex cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.08-6caf4ff\node.EXE C:\Users\Thinkpad\AppData\Roaming\nvm\v24.19.0\node_modules\@openai\codex\bin\codex.js exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-strategy7-turtle-csv-minute-2026-09-11.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-11/plan-strategy7-turtle-csv-minute-2026-09-11/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓是 **Cerebro / path-SSOT 只读回测叉**：无实盘、无 QMT 下载、无 Redis 流。把握不准可读代码或做实验，以事实为准。

【本仓必查盲区（评审必须逐条核对）】
- **T+1 / 隔日成交**：买入信号能否在当日卖出？卖出是收盘价还是次日开盘？有无用到未来 bar？
- **复权口径**：均线与盈筹率是否同一套 `adjust_type`（本仓筹码默认 front）？
- **盈筹率尺度**：`cyqk_c` 是 0–1 还是 0–100？70% 阈值有无单位错误？
- **周均线定义**：20 周均线是周线 resample 后 SMA(20)，还是 100 日近似？
- **包边界**：算法走 `oskh_factors` / `qlib_cost`，Cerebro 包装走 `backtest/`，研究 CLI 走 `backtest/research/`。

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

【你的评审侧重】优先审**实现可操作性**：函数名/文件位置/调用链/API 契约——程序员能否照此编码？哪里会卡住？哪些 import 是私有的需 wrapper？ <prompt> -->
## 评审：`docs/backtest/plan-strategy7-turtle-csv-minute-2026-09-11.md`（v1.1）

**方式**：全文精读 + 仓内代码取证（`csv_daily_backtest` / `csv_minute_backtest` / `data_root` / `lake_kind` / `turtle/{buy,sell}.py` / `presets`）+ 3 个**只读**数据探针（`python -B`，`PYTHONDONTWRITEBYTECODE=1`，未建/改任何文件；故本轮意见只在本消息内输出，未落 `_parallel/<agent>/`）。并行目录里 claude / codex / cursor-auto / kimi 当前只有 prompt 回显、无已完成意见可交叉；`review-by-cursor.md` 是 v1 对抗综合（其条目已回填进 v1.1），我独立复核后与其**不冲突**，并已自行验证其引用的 `TURTLE_ADD_BANDS`（`trade_decision/turtle/buy.py:12` = `((0.04,0.3),(0.10,0.2))`，与 §4.2 一致）。

---

### 🔴 必须修

**R1 §4.1 与 §4.8-5 的「加仓时钟」互相矛盾——会直接改变结果**
`plan:116` 写「加仓/离场时钟 | 交易时段内逐分钟。触线只用当根 close」；`plan:218` 写「5. 加仓 / 新开（14:55 + 指数闸）」。
按 §4.4 的 3a/4 步（`plan:155-157`）加仓必须是盘中逐分钟触线（A1×1.04 / A1×1.10 不可能恰好落在 14:55），而 §4.8-5 的括号把「加仓」并进 14:55。两种读法在 20260804–20260909 上差异是数量级的。
修法：`plan:218` 改为「新开 = 14:55 + 指数闸；**加仓 = 逐分钟 close 触线**」，并补一条单测（10:31 触 A×1.04 必须成交），把口径钉死在测试里。

**R2 股票「昨收」预载窗口缺席；照抄策略 6 会**静默**丢掉首日全部开仓**
`plan:87` 禁 `warmup_start`（理由「日历日暖机不够 10 个交易日」），但 `plan:230` 只规定了**指数** preload ≥ start 前 10 个交易日，全篇没有规定 `load_daily_bars` 的窗口。
`csv_minute_backtest.py:589-591`：
```
prev_rows = ddf.loc[ddf.index < day]
if prev_rows.empty:
    st.stats["skip_no_bar"] += 1
```
若 v7 照 `csv_minute_backtest.py:691` 的 `load_pool_days(start, end)` 风格只传 `--start`，`_read_one_daily` 会把 `20260804` 当天日线也纳入，`index < day` 为空 → **20260804 的 4 成试错全部静默跳过**，且 §11「对照 1.3 名单天数」会看不出差别。
修法：显式写「股票日线预载窗口 = 指数交易日历上 `--start` 的前 ≥1 个交易日（推荐直接复用 §4.7 的 10 交易日 preload 日期）」，并加单测：首日名单票必须产生 `buy:trial`。

**R3 交替止盈的档位去重与「T+1 卖不完次日重评」互斥 → 残量静默丢失**
`plan:177`「`sell_band_seq` 已触发档不重复」，`plan:118`「残留次日 **重评同一规则**（价已离开触发线则不再卖，不是挂单扫尾）」。
在 v1 的 lots 模型下，「试错当日 4 成 T+0 不可卖 + 同日加仓 3 成」是常态：band 触发时只能卖出可卖腿 → 若档位只记「已触发」布尔/最高档，剩余份额**永远不会**再卖；若想「次日重评」，同一档必须能二次派发。
修法：把 `sell_band_seq` 定义从「已触发档」改成「**每档的目标股数 + 已卖出股数**」，`剩余 = 目标 − 已卖`，未卖完的档次日继续派发（回撤全清不受此限，天然可重评）。这条必须写进 §4.5 与 §6 状态字段。

**R4 `--pool-dir` 三条硬规则互斥；env 无人读；缺省会静默回落到策略 6 名单**
`plan:29/50/81` 说必填或 `OSKH_TURTLE_POOL_DIR`、缺则失败、**不要**回落 `stock_pool/`；`plan:299` 完成定义却是「空池能跑通」；`plan:231` 又要求不回落到 `stock_pool/`。
事实：`load_pool_days` 自己**不读任何 env**，且缺省是策略 6 的池：
```
csv_daily_backtest.py:331-333
def load_pool_days(start, end, pool_dir=None):
    root = Path(pool_dir) if pool_dir is not None else Path(REPO) / "stock_pool"
```
`csv_minute_backtest.py:691` 正是这么调的（`load_pool_days(start, end)`）。
修法：写明 ①v7 CLI 自己解析 `args.pool_dir or os.environ["OSKH_TURTLE_POOL_DIR"]`，都没有 → `SystemExit`；②「空池」定义区分「目录不存在/未指定 → 失败」与「目录存在但窗口内无 CSV → 正常跑出 0 笔」（`plan:299` 用后者、`plan:81` 用前者，二者不冲突，但要写清）；③禁止把 `pool_dir=None` 传给 `load_pool_days`。

---

### 🟡 应修

**R5 交易日历口径未落到 §6/§9**：`plan:104`、`plan:198` 都要求「缺池日仍走加仓/离场」「计时按交易日递增」，但 §6 状态机与 §9 切片没规定循环日历来源。若用 `pool_days` 当日历，缺 CSV 日整段跳过 → 止损/计时漏评。建议明确「日历 = 指数日线日期（§4.7 已加载）」，并加单测：缺 CSV 日持仓仍触发 `stop:*`。

**R6 `write_run_artifacts` 是隐式鸭子类型契约**：`csv_daily_backtest.py:766` 只做 `pd.DataFrame(st.trades)` / `st.equity_curve`，签名却标 `SimState`。既然 §3 禁 `SimState`，plan 必须写明 v7 状态对象**必须**暴露 `trades: list[dict]` 与 `equity_curve: list[tuple[str, float]]` 两个同名属性，且 `trades` 的 dict key 集合＝`trades.csv` 列（§7 的 `reason` 只是其中之一，`date/code/side/price/shares/notional/commission` 缺一不可）。

**R7 引擎必须暴露注入式入口，否则单测 7–10 写不出来**：§8 的单测要求「合成分钟路径（T+1、减试错、闸）」，但 §3/§6 只给了 CLI 文件名。请像策略 6 一样分层：`simulate_v7(minute_bars, daily_bars, pool_days, index_days, *, cash_total, per_stock_budget, commission, start, end)` 纯撮合 + `run_v7(...)` 负责加载。否则测试只能 monkeypatch 全仓 I/O。

**R8 两处成本/成交价快照未定义**：(a) `plan:182-188` 回撤公式里的 `cost` 是「满 9 成时冻结的均价」还是「当时移动均价」？与 §4.3「触及 9 成时冻结」应对齐，否则同一行情两种结果。(b) 交替档位 `plan:174`「当时加权成本」在部分卖出后是否重算（会移动 1.3/1.5/1.8/2.0 四个绝对价位），要写一句「按当分钟成交前的移动均价计算」。(c) `plan:194` 5 日计时「第 5 个交易日开盘起清」的**成交价**（首根 bar 的 open 还是该根 close）未定义 → 直接影响 `trades.csv`。

**R9 同分钟优先级仍有两处空洞**：`plan:119-127` 的 `jump_nine`（A×1.10 一次补 5 成）与「A×1.04 加 3 成 → A×1.10 加 2 成」在同分钟同时满足时谁优先未定（结合 `plan:158`「整腿 skip，不退化成 +3」可推断 jump 优先，请写明）；3a 因涨停/缺 14:55/现金不足被挡后「是否下一根继续试」未定（§4.2 只对 jump 写了）。

**R10 白名单缺 v7 必需的三个符号**：`build_day_spans`（`csv_minute_backtest.py:443`）、`_slice_day`（`:456`）不在 §3 允许清单，v7 得自写按日切片（更稳的做法：`load_minute_bars` 返回的帧已带 `ymd` 列，用 `df[df["ymd"]==ds]` 或一次性按 `ymd` 分组）；`MINUTE_LAKE_END`（`csv_daily_backtest.py:52`）也不在清单，`--end` 越湖守卫与 `:684` 的告警要自写，否则 `--end 20260911` 会静默少 2 天。请把三者显式归入「允许/自写」。

**R11 §6 状态字段缺 2 个**：`plan:241` 有 `sell_band_seq`，但缺 ①「9 成冻结止损线」②「各档目标/已卖股数」（R3 的落点）③「当日已清空可卖腿 → 禁再新开」的当日标记（R10-H 与 `plan:220` 需要）。补进状态清单，否则实现会把这些塞进临时变量，跨日就丢。

**R12 全程 `adjust_type=none` 的除权风险——本窗实测为 0，但请固化成跑前 guard**
`plan:112` 与 `plan:87`（H-R16 禁 front）让 4%/10%/0.96 这类价格线直接吃未复权价：真出现除权，4% 级的阶梯会误加仓/误止损。**只读实测**（名单 59 码 × 2026-07-20..09-11 日线，逐日按 `limit_pct` + HALF_UP 重算涨跌停，超出即判异常）：

```
$env:PYTHONDONTWRITEBYTECODE="1"
@'
import pathlib, pyarrow.parquet as pq, pandas as pd
from decimal import Decimal, ROUND_HALF_UP
pool = pathlib.Path(r"E:\PycharmProjects\OSkhQuant1.3\stock_pool_turtle")
codes = sorted({l.split(",")[0].strip() for p in pool.glob("*.csv") for l in p.read_text(encoding="utf-8-sig").splitlines() if l.strip()})
root = pathlib.Path(r"F:\stock_data\stock\period=1d\dividend_type=none")
lp = lambda c: 0.20 if c.startswith(("300","301","688")) else 0.10
bad = []; n = 0
for c in codes:
    key = (c + (".SH" if c[0] == "6" else ".SZ")).replace(".", "_")
    t = pq.read_table(root / f"symbol={key}" / "data.parquet", columns=["time","close"])
    df = pd.DataFrame({"t": pd.to_datetime(t["time"].to_numpy(), unit="ms", utc=True), "c": t["close"].to_numpy()})
    df = df[(df.t >= pd.Timestamp("2026-07-20", tz="UTC")) & (df.t <= pd.Timestamp("2026-09-11", tz="UTC"))].sort_values("t").reset_index(drop=True)
    n += len(df)
    pct = Decimal(str(lp(c)))
    for i in range(1, len(df)):
        prev = Decimal(str(df.c[i-1])); cur = float(df.c[i])
        up = float((prev*(1+pct)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        dn = float((prev*(1-pct)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        if cur > up + 1e-9 or cur < dn - 1e-9: bad.append((c, str(df.t[i].date()), float(df.c[i-1]), cur, up, dn))
print("daily rows scanned", n, "codes", len(codes))
print("beyond-limit overnight moves (= ex-right/split or data err):", len(bad))
for b in bad: print("  ", b)
'@ | & "D:\anaconda3\envs\vanna312\python.exe" -B -
```
原始输出：
```
daily rows scanned 2301 codes 59
beyond-limit overnight moves (= ex-right/split or data err): 0
```
结论：**本窗不存在除权/送转导致的越界跳空**，`none` 口径在 20260804–20260909 可用（这条建议据此降级为「加 guard」而非改口径）。建议把上面这段判定做成 v7 跑前 30 行 guard：任一越界 → 该票该日 skip + summary 记一行，避免将来换窗口时静默误判。（**证据 + 建议**，非误判；若后续换窗请重跑。）

**R13 涨跌幅判定只认 300/301/688**：`ma_chip_edge_backtest.py:82-86` 的 `limit_pct` 无 ST（5%）与北交所（30%）分支，`_limit_prices` 继承了它。实测名单 59 码无 ST、无 43/8x/9x 北交所码，故本窗正确；请加一条断言（名单出现 ST/BJ 码即退出）或直接在 §3 里写明「v1 名单约束：无 ST / 无北交所」。

---

### 🟢 可选

- `plan:290` 的 `vanna312 -m pytest`：AGENTS.md 要求走 `OSKH_MERGE_PYTHON`→`vanna312` 绝对路径（`plan:308` 已写对），测试命令建议统一成 `"$env:OSKH_MERGE_PYTHON" -m pytest ...` 或 `scripts/_script_bootstrap.resolve_oskh_python`（本仓已有该 helper，plan 未提）。
- `plan:85`「v7 自己的 cache 文件名」：`minute_cache_path(start,end,cache_dir)`（`csv_minute_backtest.py:177-179`）里 **cache_dir 只改目录**，文件名恒为 `minute_none_{start}_{end}.parquet`；要真换名得自写 path 函数。另注意 `:99` 的 `CACHE_ROOT` 在仓内 `backtest_output/bar_cache/`，与策略 6 同窗会共用一个文件（同数据，无害，但 plan 说「自己的文件名」需落地方式）。
- 自写 index loader 的索引必须复刻 `_read_one_daily` 的归一化（`pd.to_datetime(ms, unit="ms", utc=True).tz_localize(None).normalize()`，`csv_daily_backtest.py:367-370` 一带），否则 `day in idx` 静默失配 → 触发 H-R15 的「缺日抛错」，第一次跑就报错退出（好消息是 fail-visible）。
- 费用口径建议在 §4.1 补一句「0.1% 双边含/近似含印花税与过户费，约为真实零售成本 2–3 倍，偏保守」——与 `backtest_main_full.py:324` 的 `setcommission(0.001)` 同源，不必改数，但别让后人以为漏算了印花税。
- H-R9 表述小偏：`_eval_prototype_sell` 在**本仓** `trade_decision/turtle/sell.py:49`（不在 1.3 `stop.py`）。禁令本身正确，只是归属写串了，容易让实现者去 1.3 里找。
- §2 对照表「试错 成本×0.96 → **A×0.96**」在「仅试错」态下 `A == 加权成本`，该行是名义差；真正的偏离是 7 成（`A×0.99` 减试错）与 9 成（均价×1.01）两行。建议在 §2 加脚注，免得后续评审再当「未改回 Paper」争论一次。

---

### ✅ 做对的地方（保留）

- **H-R9 事实成立**：本仓 `trade_decision/turtle/` 只有 `__init__.py`/`buy.py`/`sell.py`，确无 `stop.py`（1.3 侧才有 `stop.py`/`stop_pct.py`/`capital.py`）。禁止 import 是正确的包边界。
- **§2 数字与 1.3 SSOT 一致**：`E:\...\OSkhQuant1.3\trade_decision\turtle\stop.py:38-56` — `add_count<=0 → avg×(1+pct)`（trial 默认 −4% = ×0.96）、`==1 → avg×1.01`、`else → avg×1.02`；plan 的「Paper 7 成 ×1.01 / 9 成 ×1.02 / 试错 ×0.96」对照准确，且 `trade_decision/turtle/sell.py:60` 也自述「试错−4% / 7成+1% / 9成+2%」。
- **H-R6 逐条可验证**：`oskh_data/lake_kind.py:36-58` 对 `000001.SH` → `index`、`000001.SZ` → `ashare`、裸 `000001` → `unknown`（fail-closed）；`daily_parquet_write.py:204-224` 证实指数树 **none-only** 且路径就是 `resolve_index_daily_root()/dividend_type=none/symbol=000001_SH/data.parquet`。禁止 `load_daily_bars` 读指数也对（它硬编码 `resolve_period_root("1d")` 股票树，`:387`，会静默返回空）。
- **H-R15 的 preload 在本机成立（实测）**：指数日线 2026-07-15..**2026-09-11** 连续 43 行，`--start 20260804` 前 10 个交易日（07-21 起）齐备；`--end` 侧 09-11 有值。
- **H-R11 的 `hm==895` 在本机成立（实测）**：301500/000739/002451 在 20260909、20260804 均为 **241 bar/day**，`hm ∈ [570, 900]`，含 895 与 900。湖时间按 CST 钟点标 UTC 的假设成立 → 禁止二次时区转换是对的。
- **H-R16 事实成立**：`docs/backtest/README.md` 的研究主入口写的是 `backtest/lebs/`（并与 `--strategy csv_vN` 并列），本仓 `backtest/` 下**没有** `lebs/`。以该文当选型 SSOT 确会误导。
- **前视/未来 bar 纪律干净**：`gate[T]=f(≤T-1)`、触线只用 close、峰值用 running max、禁「一 bar high 加仓 + low 止损」、`T+1` 用 lots 的 `buy_date < today` 而非仓位级 `can_sell`——这几条是 A 股分钟回测最容易翻车的地方，本稿是全篇最扎实的部分。
- **方向性规则与中国 A 股惯例一致**：涨停可卖不可买（不追板）、跌停不可卖（defer 重评）、100 股整手、卖出资金当日可用于买入（T+1 不挡买）、缺 14:55 根当日不开。
- **包边界选择正确**：不写 `ProfitStrategy.Strategy7`、不动 `presets.py`、研究 CLI 落 `backtest/research/`、算法留在纯函数 `strategy7_rules.py`——与 README 布局和「与 1.3 共享 SSOT」约束都合。

---

### 总评

设计骨架（T+1 lots、闸用 T-1、涨跌停方向、包边界、白/黑名单）我逐条取证后认为**站得住**，且比 v1 明显收敛；但作为「程序员能否照此编码」的检查，仍有 4 处硬伤会让人**写错或静默错**：加仓时钟自相矛盾（R1）、股票昨收预载未规定导致首日丢单（R2）、交替止盈档位去重吃掉 T+1 残量（R3）、`--pool-dir` 三条规则互斥且缺省会静默回落策略 6 名单（R4）。这四条都是「改几行文字 + 各加一条单测」量级的修订，不需要重新设计。另需补上引擎的注入式 `simulate_v7(...)` 契约（R7）与状态字段（R3/R11），否则 §8 的单测 7–10 无从落笔。

**结论：可进实现——但请先按 R1–R4 修订文档（建议同轮补 R5–R11 的文字），修订后我复核一遍即可开切 A 片。** 其中「复权 `none` 本窗无除权」与「`hm==895`/指数 preload 齐备」我已用可复现实验确认，故 R12/R13 只是 guard 建议，不构成阻塞。
