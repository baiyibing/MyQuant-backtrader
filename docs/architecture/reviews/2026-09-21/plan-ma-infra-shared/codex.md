<!-- agent=codex cmd-prefix=C:\nvm4w\nodejs\node.EXE C:\Users\Thinkpad\AppData\Roaming\nvm\v24.19.0\node_modules\@openai\codex\bin\codex.js exec --ephemeral 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】E:/PycharmProjects/MyQuant-backtrader/docs/backtest/plan-ma-infra-shared-2026-09-21.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `E:\PycharmProjects\MyQuant-backtrader\docs\architecture\reviews\2026-09-21\plan-ma-infra-shared/_parallel/<agent>/<agent>.md`。
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
评审完成，全程只读（未修改/创建/删除任何文件）。

**取证基线**：HEAD `4adad96`（plan 自称 `40f660d`，差异仅 docs 合入；`strategy4_rules.py`/`weekly_macd_divergence.py` 行号已复核未漂移）。实验在 `D:\anaconda3\envs\vanna312\python.exe`(3.12.13, ruff 0.12.0, pytest 9.0.3) 单进程内跑，无写盘。并行目录中 kimi/claude/codex/cursor-auto 的 `<agent>.md` 我读到时**只含 prompt 头、无实质意见**，故本轮独立完成，未引用他评条目。

---

## 🔴 必须修

**R1 §1「布林带无存活实现」是事实错误，且会造成 σ 口径静默分叉**

```
oskh_factors/price_bb.py:11  def bb_position(close, period=20, nbdev=2.0) -> float:
oskh_factors/price_bb.py:16      std = np.std(close[-period:])     # np.std 默认 ddof=0
backtest/chip_algorithm.py:29  from oskh_factors.price_bb import bb_position
turnover-resist/src/bollinger.rs:10  //! 与 Python `backtest/chip_algorithm.py:bb_position` 行为一致。
turnover-resist/src/cli.rs:35-38     默认 1，对齐 pandas rolling(...).std() 默认行为
```

- 存活证据链：`oskh_factors/__init__.py:6` 导出 → 消费者 `backtest/research/chip/filter_chip_stocks.py:37`、`scripts/data/full_market_equal_weight_resist_v2.py:33`。plan §1:20「**无存活实现**（随 Cerebro 退场删除）」不成立。
- ddof=1 本身**是对的**（我方实验：`pandas rolling(20).std() == pandas std(ddof=1)` True；`np.std(ddof=1)/np.std(ddof=0)=1.025978`；Rust TR 默认也是 1），但"无存活实现"会让实现者/后续评审看不见**本仓已有同名不同 σ 的价格布林**。
- 要求：§1 改成"已知重复清单：`oskh_factors.price_bb`（ddof=0、只回 position）存活，**故意不采用**"；§2 注明 σ 参考系 = pandas rolling.std + Rust TR 默认；测试 pin 两者差异，防后续有人"改齐"。

**R2 `daily_to_weekly`/`weekly_sma_asof` 缺两条锁定口径（asof 键 / 末端未完成周）——照此实现会出未来函数或错停一周**

实验（可复现，pandas 3 周合成日线，末日 2026-09-16 周三）：

```python
python -B -c "import pandas as pd;d=pd.to_datetime(['2026-09-07','2026-09-08','2026-09-09','2026-09-10','2026-09-11','2026-09-14','2026-09-15','2026-09-16']);df=pd.DataFrame({'close':[12.5,13,13.5,14,14.5,15,15.5,16.0]},index=d);df['_last_day']=df.index;print(df.resample('W-FRI').agg({'close':'last','_last_day':'max'}).dropna().to_string())"
```

原始输出：

```
            close  _last_day
2026-09-11   14.5 2026-09-11
2026-09-18   16.0 2026-09-16     # 标签在 _last_day 之后（未来日期）
```

若调用方按 `label <= asof` 过滤 → 丢掉末端周（`['2026-09-04','2026-09-11']`）；若不过滤 → 用一个**未来日 09-18** 作键。归档锁定口径是三条（`docs/backtest/_archive/plans/plan-ma-chip-edge-strategy-2026-09-07.md:34`）：`asof 键 = _last_day，只 backward 到 D …序列末端未完成周若 _last_day<=D 可参与`，v11 亦沿用（`plan-version11-machip-csv-2026-09-21.md:66` P7）。plan §2:32 的 `list[tuple[date, float]]` 没说 `date` 是 W-FRI 标签还是 `_last_day` → 必须写死 **`date = _last_day`（该周最后交易日）**；`weekly_sma_asof(..., n)` 的 `n` 是"周"建议改名 `n_weeks`。

**R3 非有限值（NaN）/ `n<2` 边界未定义，而两下游 plan 的 DoD 依赖它**

```
backtest/research/csv_common.py:44      closes = df["close"].iloc[:pos].astype(float).tolist()
backtest/research/csv_daily_loader.py:96 out = out.loc[out["_volume"] != 0]      # 只剔零量，不过滤 close
backtest/research/strategy4_rules.py:27  return sum(float(x) for x in closes[-n:]) / n   # NaN 直接传播
```

- 若窗口含 NaN：买侧 `px >= nan` → False（像 fail-closed），卖侧 `px < nan` → False → **静默不止损（fail-open）**。R5:44 只 pin "不足 n 根 → None（非 0 非 NaN）"，没覆盖非有限输入。
- 实测 `bb_asof(..., n=1)`、ddof=1 → `ZeroDivisionError: float division by zero`（分母 `n-1`）。
- 要求：二选一并 pin —— ①窗口含非有限 → 返回 `None`；②传播 NaN + docstring 强制调用方 `math.isfinite` 检查。并 pin `n<2` 的 BB 语义。下游已把它当 DoD：v11 `:52/:79`（NaN≠边缘、非有限→假）、v12 `:83`（px≤0 → None）。

**R4 复权域（价格域）未写——20 周线 / 20 日布林在除权日是错值**

```
backtest/research/csv_daily_loader.py:108   dividend_type: str = "none"    # 引擎默认不复权
scripts/gates/verify_chip_factor_consistency.py:43   DAILY_DIR = .../"dividend_type=front"
docs/backtest/data/daily-adjusted-update-ssot.md:16  QMT front 复权 = Ground truth
docs/architecture/reviews/2026-09-16/plan-exdiv-refprice/zcode-arch.md:111  v4 SMA 门除权日换域 → 声明残留另开微片
```

v11 的三条件全是**价格水平比较**（MA20/MA60/20 周线/布林上轨，`plan-version11-machip-csv-2026-09-21.md:18`），同窗跨除权即失效；而同源 cyqk 走 front 面 → 域混用。要求：ma_infra 作为"口径 SSOT"必须写域契约（建议 front），并指定 v11 导出器 `dividend_type="front"`；若人裁判定域归 v11 plan，本 plan 至少留一行指针——不能两处都不写。

---

## 🟡 应修

**R5 批件缺口让 v11 R8「导出器不自写均线」无法兑现（已实测量级）**

5000 只 × 1200 日、纯 Python、随机合成（脚本：A 逐日 `sma(weekly_close(dates[:i],closes[:i]),20)`；B 先聚合周序列再前缀和；C 增量 `s1=Σc,s2=Σc² → var=(s2-s1²/20)/19`）原始输出：

```
A) 逐日 weekly_asof 重算:  682 s = 0.19 h          # 全市场导出 ≈11 分钟
B) 周序列 + 增量 SMA:        1.56 s
C) 增量 bb_upper (ddof=1):   9.34 s   | 逐日调 bb_asof（切片 20 窗）: 55.7 s
   sma_series 前缀和: 0.44 s / 1500 只 ≈ 293 µs/只（P2 结论成立）
```

plan 只有标量 `bb_asof` + 一个 `sma_series`，而 v11 导出器需要**逐日** SMA20/60、布林上轨、逐日周线 MA → 要么 682s 级逐日调标量，要么自己 rolling（违反 v11 `:54` R8）。建议一次到位：slice A 出 `bb_series`、`weekly_sma_series`（列表增量实现即可，无需 pandas），且 `*_asof` = 序列件 `[-1]` 薄封装 → 标量/批量永远同口径。

**R6 §6 切片 B 内部自相矛盾 + 相对导入字面写错**

- `:66` 同时写"调用点改向"与 DoD"`git diff` 仅 import 行"，与 P3 `:52`"gate 逻辑不动"冲突。二者留一个。
- `from ...ma_infra import sma_asof`（`:66`）在 `backtest.research.strategy4_rules` 中是**超出顶层包** → ImportError。本仓惯例绝对导入（`csv_strategy_books.py:14-30`）。请写唯一字面：`from backtest.research.ma_infra import sma_asof as sma_asof`（冗余别名消 F401 这一招本身 ✅）。

**R7 R2 的「import fence 现状不动」实际含义是「当前没有 gate」，应写明**

```
tests/test_ashare_simulate_import_fence.py:17-33   SIMULATE_HOT_PATH = (15 个固定模块名，无 ma_infra)
tests/test_ashare_simulate_import_fence.py:51-57   只禁 qlib / trade_fee_policy / backtest.lebs / ashare_fill_clock
tests/test_ashare_simulate_import_fence.py:61-66   与 plan-ashare-engine-refactor §5-C 表字节比对
```

pandas 无任何门禁。要么明说"本刀靠约定"，要么加定向测试并同步改 §5-C 表（字节锁）。

**R8 R3 双副本无 drift guard；端口契约需补齐**

源实现契约在 `oskh_factors/weekly_macd_divergence.py:88-104`（非 DatetimeIndex 抛 TypeError、`resample(WEEK_RULE)` 5 列聚合、末尾 `dropna()`）；`(dates, closes)` 新签名丢掉了"多列/丢 NaN 周/乱序"三件事，必须明确（乱序时 resample 会抛；NaN 周丢或留会**位移 MA 窗口**）。最省 guard：一条测试同时喂合成 5 列 DataFrame 给两边，断言 weekly close + `_last_day` 相等（含一个 NaN 周、一个假期缩短周）；注意 `import oskh_factors.weekly_macd_divergence` 会执行 `oskh_factors/__init__.py:4-7`（chip 栈），别参数化放大它。

**R9 §7 验证命令与 CI 口径不一致 + HEAD 引用过期**

本仓 CI 口径是 `python -m pytest -q -m "not production and not benchmark"`（`.github/workflows/python-tests.yml:56`）；§7:72 裸 `pytest -q tests/` 会把 `tests/test_oskh_data_integration.py:11`（`pytestmark = pytest.mark.production`）纳进来，实施者可能把环境红误判成"R1 破了"。另 §1 标 `HEAD 40f660d`，当前 `4adad96`。

**R10「全仓唯一 MA 实现」不实 + 上线同源留钩**

`backtest/research/strategy7_rules.py:171-173`（上证 MA10 手写逐点）、`oskh_factors/chip/bands.py:47-48`（TR 序列 rolling mean，同名不同物）；决策侧 MA10 另有来源（本仓 `trade_decision/turtle/sell.py:89-104`；1.3 `trade_decision/wiring.py:381-406` 用 `bar_policy="prior_completed_session"` + `adj_factor` 同域比较 + `data_ok` 降级）。建议 §1 表补"已知未迁移/同名不同物"行，§2 留一句"上线同源（⑥）前须与 1.3 ma provider 做口径 pin"。

---

## 🟢 可选

- 口径常量集中到 ma_infra：MA5/10/20/60 与 `BB(20, 2.0, ddof=1)`，否则 v11/v12 各自写死 → 口径再次分散；`bb_asof` 若回 `NamedTuple(mid,upper,lower,std,position,width)` 可一次覆盖 chip/TR 面（YAGNI 也成立，记录取舍即可）。
- §7 切片 B 目标命令补 `tests/test_strategy4_rules.py`；类型风格统一（plan 混用 `Optional[...]`/`list[...]`）。

## ✅ 做对的

- 种子采纳 + `as sma_asof` re-export（F401 正解）；爆炸半径确实小：全仓 `rg sma_asof` 只命中 `strategy4_rules.py` 与 `tests/test_strategy4_rules.py:4-6`，`csv_strategy_books.py:483-484` 属性访问不受影响。
- R3 用"移植副本 + 出处注释"而非 import 私有 `_daily_to_weekly` ✅（不跨模块依赖私有符号）。
- R5 的 None 语义优于仓内其它口径（`price_bb` 不足→0.5、Rust 不足→NaN），`is None` 判定链清晰。
- P2 纯 Python 前缀和实测 293 µs/只（1200 日）→ 够用，YAGNI 判断成立。
- R4"截止权在调用方"与归档"禁止在 T 用含 T 的 sma 判 T-1"一致（建议把该例句写进 docstring，别让读者把 v4 的"不含当日"当模块属性）。
- 切片粒度/DoD/验证命令结构清晰，"风险低"对**重构**部分成立。

## 过程备注（非 plan 缺陷）

`_parallel/cursor-auto/cursor-auto.md` 的 cmd-prefix 是 `--workspace E:\PycharmProjects\OSkhQuant1.3 --mode plan`，而待审文档在 `MyQuant-backtrader` —— 若按该 workspace 跑会读不到目标文档，建议主持复核该席产出。

## 总评

方向对、重构爆炸半径实小，但作为"全仓均线 SSOT"还缺三类必须写死的口径：**周的 asof 键与末端未完成周、非有限值/边界语义、复权域**；另有一处事实错误（漏掉 `oskh_factors.price_bb`，σ 分叉会静默存在）和一个会让 v11 无法兑现 R8 的批件缺口（实测 682s vs 1.56s）。全部可在 plan 文本层一次改清，不动架构。**结论：不可直接进实现**；补 R1–R4 口径 + R5/R6 API 与导入字面 + R7/R9 gate/命令后即可 GO（不建议分两轮，五处改动都很便宜）。
