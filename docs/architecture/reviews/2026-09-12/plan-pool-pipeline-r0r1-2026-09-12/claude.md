<!-- agent=claude cmd-prefix=C:\Users\Thinkpad\AppData\Local\Microsoft\WinGet\Links\claude.EXE -p --no-session-persistence --output-format text --permission-mode bypassPermissions 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-pool-pipeline-r0r1-2026-09-12.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-12/plan-pool-pipeline-r0r1-2026-09-12/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓第一方回测是 **向量化 CSV**（日线/分钟）+ path-SSOT 只读行情。Cerebro / Rolling 观察退役。无实盘、无 QMT 下载、无 Redis 流。引擎分工见 `docs/backtest/engine-positioning-ssot.md`。把握不准可读代码或做实验，以事实为准。

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

【你的评审侧重】优先**综合裁决 + 跨文档交叉验证**：检查方案内部自洽（不自相矛盾）、跨节引用一致、与关联 plan/SSOT 的衔接；对抗性复核其他评审员的断言（凭代码/实验驳回误判）。 <prompt> -->
取证完成。所有关键事实已亲自验证（包括一次只读 F 湖分区探测实验）。以下为评审意见。

---

# 评审：plan-pool-pipeline-r0r1-2026-09-12.md（v1.1）

**评审侧重**：综合裁决 + 跨文档交叉验证。所有行号断言均亲自读码核对；并行目录中 codex / kimi 仅 prompt 空壳，**只有 cursor-auto 有正文**，交叉核对以其为对象。

## 盲区核对

| 盲区 | 结论 |
|------|------|
| T+1 / 隔日成交 | 本 plan 不触卖核。现码买入日 `n_days=0` 不可卖、`pending_exit` 次日开盘成交（`csv_daily_backtest.py:333-338`，`n_days >= 1` 门）。`name_asof` 显式禁 `ymd>ds`，**无未来 bar 路径** |
| 复权 | P-R7 锁 `none`；日线加载 `dividend_type=none`（`csv_daily_backtest.py:237-238`），全 plan 无筹码 front 渗入点 |
| 盈筹率 | P-R7「不适用」，未进 1–8 书 ✅ |
| 涨跌停 / 停牌 | 档位表由 E-R2 锁（`engine-ashare-correctness.md` §2），本 plan 不动；`limit_pct(code, name)` 名称感知已存在（`market_layer.py:57`），B 切片改的正是喂给它的名称时效 |
| 包边界 | 落点全在 `backtest/research/` + `scripts/data/`；实测 **v7 不消费 pool_names/ST**（`csv_minute_backtest_v7.py` grep 零命中），无 v7 双 SSOT 残留 |

## 🔴 必须修

### R1（新发现）P-R4「只解析 `持仓标的列表:`」与自身产出/验收矛盾——日期来源被锁死了

`position_analysis.txt` 每块结构是 `日期:` 行在前、列表在后（`MyQuant/my_scripts/position_analysis.txt:10-14`）：

```text
日期: 2026-03-02 00:00:00
  总市值: 100000000.00
  ...
  持仓标的列表: []
```

P-R4 写「**只解析** `持仓标的列表:` 后的 Python list」，但转换器要产出 `YYYYMMDD.csv`、P-R5 ① 验收「03-02 无文件」——两者都**必须**知道每个列表属于哪天，而日期只在 `日期:` 行上。按 P-R 锁的字面读，「解析 `日期:` 行」违反「只解析」；不解析则只能按序号+交易日历猜日期（脆弱，断日即错位）。须补一句：「日期取自每个 `持仓标的列表:` 之前最近的 `日期:` 行；列表是该日持仓唯一来源，不解析其下标的表格」。

### R2（endorse cursor-auto R1，核实成立）P-R2 谓词记号 `max{name : ymd<=ds 且非空}` 会误读为字典序

plan L76 同行既有 `last_seen`/「禁止无上界 max」的正确操作句，又有集合记号 `max{name:…}`——按名字符串取 max 与按 argmax_ymd 取是两种实现，且前者能过「无上界」字面检查。该谓词要原文进契约（切片 A 交付物），记号必须在落契约前改成 cursor-auto 建议的二选一写法（`last_seen[code]` 或 `name of (max ymd ≤ ds …)`）。

### R3（endorse cursor-auto R2，**已亲自验证机制**）C 落地必须写死「加载侧丢弃 volume==0 行」

`csv_ledger.py:146-155`：

```python
def last_close_mark(df, day, fallback: float) -> float:
    if day in df.index:
        return float(df.loc[day]["close"])
```

P-R1 禁改此公式，则「零量 close 不进净值」的唯一自洽实现是让该行**不进 index**。P-R1 现文「volume=0 日由**调用方**按缺行处理」没钉死剔除点（run？simulate？loader？）——若只在交易环加判断、行留在 index，净值环照样吃零量 close。须改写为「加载后即丢弃 `volume==0` 行，交易环与净值环同一谓词」。仅约束 C 落地分支，但现在改一句话最便宜。

## 🟡 应修

### Y1（endorse cursor-auto Y1）双通道优先级未锁
`simulate` 已有扁平参数（日 `csv_daily_backtest.py:281`、分 `:565`），现有测试整窗喂 `*ST`（`tests/test_csv_daily_backtest.py:782-785`）。两者同传时未定义优先级，易出现「以为在测 as-of、实际整天一张表」。锁：`pool_names_by_day is not None` → 只走 as-of。

### Y2（新发现）C 落地的「无该列 = 不冻」会被现有 blanket except 吞成「整 code 无数据」
`csv_daily_backtest.py:213-217`（分钟同构 `:156-160`）：

```python
    try:
        table = pq.read_table(path, columns=["time", "open", "high", "low", "close"])
        ...
    except Exception:
        return None
```

columns 加 `volume` 后，缺列的 parquet 会抛异常→`return None`→整个 code 当无 K（冻仓+净值走 fallback），恰好违反 P-R3「无该列 = 不冻（保护现夹具）」。须写明：先读 schema 或异常后降级重读（去掉 volume 列），**不得**落进现有 `return None` 兜底。

### Y3（新发现）分钟「整日跟日线 volume」机制未指明
分钟引擎只读分钟 parquet（无 volume 列）。要「跟日线」要么跨期读日线湖、要么聚合当日分钟量判零——两种实现边界完全不同（前者引入跨 period 依赖）。C 默认降级时不阻塞，但落地分支须指定其一。

### Y4（endorse cursor-auto Y4）`last_seen` 推进键须写明
日历来自 bars 并集；应写「每个日历日开盘前先 ingest 当日池名」或「按 `sorted(by_day keys ≤ ds)`」，避免只在有持仓处理时才推进漏掉极端日。

### Y5（部分 endorse cursor-auto Y3/Y5，plan §6 已有大半）
① E-R4 文案补一句已知失真（§6 已写「湖若写 volume=0，热路径仍当正常日」，落进 `engine-ashare-correctness.md` 一句话即可）；② P-R5 注明「03-02 空列表故无 CSV、非漏跑」，防实施把 start 修回 0302。

### Y6 `--src` 兄弟仓探测规则未定义
「禁止把盘符写成唯一成功路径」只禁了坏例，没给正例（`Path(__file__)` 相对？repo 根 `../MyQuant`？环境变量？）。实施时自行发明易碎。

## 🟢 可选

- gitignore 用 `exports/r0_*/` 比笼统 `exports/` 窄（当前 `.gitignore` 无 exports 条目，plan §5 已列新增，方向正确）。
- §1 前缀速记 `600→10%，300/301/688→20%，920→30%` 与 E-R2 全表（含 `302/689/430/83/87/88/001/002/601/603/605`）不完全对齐；行为由 `board_limit_pct` 覆盖，仅 docstring/HELP 勿照抄速记（cursor-auto 🟢#3 同向，我补 001/002 侧）。
- 头部「PR #18」为悬空引用：`engine-ashare-correctness.md` 未提 PR 号，分支 `feat/engine-ashare-correctness` 尚未合并（最近合并为 #17）。§7 预告的 `merge-consensus.md` 尚不存在，属本 fan-out 待产出，非错误。
- §2 理由「`scripts/research/` 是筹码 / TR」不实——`scripts/data/` 同样放满筹码脚本（`full_market_chip_resist.py` 等）。真实依据是 CLAUDE.md「研究 CLI 走 `backtest/research/`」；结论（放 `scripts/data/`）不变，改理由防后续误引。

## ✅ 做对的地方

1. **后日赢诊断全对**：`load_pool_name_map` L68-89「later files win」、`test_load_pool_name_map_keeps_st_column`（`tests/test_csv_pool.py:61-66`）正是后日 `*ST` 赢、注入点日 `:518` / 分 `:805`——plan 行号与行为逐条吻合。
2. **「加载器不读 volume」属实**：日线 `:213` / 分钟 `:156` columns 均无 volume → C 默认文档降级的判断建立在事实上，而非臆测。
3. **P-R2 谓词方向正确**：`_named_limits` 在买卖三门共用（`:326/:413/:451`），按日 as-of 恰好同时修买门（`skip_limit_up`）与卖门（E-R1 defer 档位）；只加可选参数、扁平类型冻结，与 as-built 签名兼容。
4. **R0 数据依赖实证满足**（我跑的只读探测）：`F:\stock_data\stock\period=1d\dividend_type=none` 下 `920014_BJ`、`300190_SZ`、`688548_SH`、`600010_SH` 分区**全部存在**，§6 风险项当前不成立为障碍。
5. **范围纪律自洽**：§2 禁改表与 §5 落点表、E-R* 现锁、`engine-positioning-ssot.md` 无冲突；§8 三节与 `review-by-cursor.md` 逐条 1:1 对应；切片 A–D 分 commit、B/C 不绑、C 与 D 禁互验。
6. **`--pool-dir` / version6 / 验收测试文件**全部已存在（`:770`、v8 双测试、`test_market_layer.py`），验收命令可直接执行。
7. R0 无名 ST 按前缀分板、该窗不当 E-R2/净值验收、不编造名称列——失真明示而非隐藏。

---

## 总评

v1.1 是一份事实密度高、自洽性好的 plan：核心诊断（后日赢、加载器无 volume）全部经我独立复核成立，F 湖依赖也已实证满足。三个 🔴 都是**契约文字级**缺陷（日期来源被自己的解析锁锁死、谓词记号歧义、零量剔除点未钉死），各一句话可修，不动方案骨架。**修完 R1–R3 并采纳 Y1 后可进人裁「按 plan 实施」**；B/D 切片现在就具备开写条件，A 只需补谓词措辞，C 默认降级安全。
