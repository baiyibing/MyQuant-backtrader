<!-- agent=cursor:kimi-k3-high cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\index.js --model kimi-k3-high -p --output-format text --trust -f --mode ask --workspace E:\PycharmProjects\MyQuant-backtrader <prompt> -->
全部评审员已交卷，交叉核对材料齐备。我的实验（R0 窗口全量探测 + 分钟树探测 + 格式核验）已完成。以下为评审意见。

---

# 评审：plan-pool-pipeline-r0r1-2026-09-12.md（v1.1）

**评审员**：kimi（侧重：最小实验验证关键行为）。独立取证后读到 codex(root) / claude / cursor-auto 已完成意见，已逐条交叉核对。所有实验只读，未改任何文件。

## 实验摘要（详见文末附录，均附原始输出）

| # | 实验 | 结论 |
|---|------|------|
| E1 | F 湖日线 R0 窗（2026-03-02~23）全量 5584 只扫 `volume` | **121 只有 volume==0 行；0 只缺行（全部 16/16）→ 湖是「补占位」不是「省略停牌日」** |
| E2 | 抽查 001232/000711/300142 零量日 OHLC | 两种占位形态：平价（000711 停牌期 4.65 平推）与 **全零价**（001232 OHLC=0.0） |
| E3 | 分钟树 000711_SZ 停牌日 | 分钟 parquet **有 volume 列**，停牌日 241 根/日、sum=0 → 同样补占位 |
| E4 | `canonical_from_bare_code` / `_cell_to_bare` / `is_st_name` / `limit_pct` | 920014→`920014.BJ` ✓；`SZ300190`→`300190` ✓；WEST≠ST ✓；无名 920→30% ✓ |
| E5 | MyQuant `position_analysis.txt` 实测 | 16 天、03-02 `[]`、BJ920014 在 03-11/12、无名称列——plan §1 R0 描述逐字属实 |

## 🔴 必须修

### K1. P-R3「湖省略停牌日 = E-R4 已覆盖」的前提被实验推翻——C 应升为默认落地，不是文档降级

plan §0/§1/P-R3/§6 的降级推理链建立在「湖省略停牌日」上。实测（E1/E2，与 codex R1 的 000004_SZ/400 只探测互相独立、结论一致）：**R0 窗 16 个交易日里 5584 只全部满行，121 只带 volume==0 占位 K**。即停牌日以占位行存在，当前热路径把它当正常日：

- 平价占位（000711 03-13~19，open=close=4.65）：`pending_exit` 次日开卖会**在停牌期成交**（open 4.65 不触 `hit_limit_down`，`csv_daily_backtest.py:334-338` 直接 `_sell`）；追买 pop、`pos.peak` 更新照常。
- 全零占位（001232，OHLC=0.0）：买入靠 `execute_buy` 的 `px<=0` 兜底（`csv_ledger.py:182-183`）、卖出靠 `hit_limit_down(0,0)=True` 兜底（`csv_ledger.py:95-97`）——**靠两个巧合守卫才不出事，不是设计**；`_sell` 本身无 px 守卫（`csv_ledger.py:219-222`）。

P-R3 自己的判据是「仅当探测到 volume==0 日 K 才改循环」——探测 6 秒跑完，答案已经是「有」。按「激进一次到位」与 plan 自身决策规则，**C 应直接落地**（P-R3 已把 ≡缺K 语义写全，落地成本极低），而不是把一条已被证伪的假设写进 `engine-ashare-correctness.md` 当结论。**对 claude 总评「C 默认降级安全」与 cursor-auto ✅3「C 默认可降级」的交叉核对结论：误判**——二者只验证了「加载器不读 volume」（属实），未探测湖中是否存在零量行。

### K2. P-R4「只解析 `持仓标的列表:`」与自身产出矛盾——日期来源被锁死（endorse claude R1，已实测确认）

E5 实测文件结构：`日期: 2026-03-02 00:00:00` 行在前，`持仓标的列表:` 在后。转换器要产出 `YYYYMMDD.csv` 且 P-R5 ① 验收「03-02 无文件」，都必须解析 `日期:` 行；按 P-R4 字面「**只解析**列表」则无法编码。补一句即可：「日期取自每个 `持仓标的列表:` 之前最近的 `日期:` 行；列表是该日持仓唯一来源，不解析其下表格」。

### K3. C 落地时「≡缺K」的剔除点必须钉死在**加载侧丢行**（与 codex R4 / claude R3 / cursor-auto R2 四方收敛，已核实）

净值环 `eq += pos.shares * last_close_mark(df_c, day, pos.cost)`（`csv_daily_backtest.py:468-472`），而 `last_close_mark` 是「day 在 index 就用当日 close」（`csv_ledger.py:146-155`）。P-R1 禁改此公式，则「零量 close 不进净值」的唯一自洽实现是 **`_read_one_daily`/`_read_one_minute` 加载后丢弃 volume==0 行**——丢行后 E-R4 既有缺行路径自动满足 P-R3 全部语义（不评卖/pending 不成交/追买不 pop（`:402-406` 先判缺行再 pop，已核实）/不更新 peak/净值走昨收）。plan 现文「由调用方按缺行处理」未钉死剔除点，必须改写为「加载侧丢行，交易环与净值环同一谓词」。K1 若采纳（C 升默认），本条即为默认路径的一部分。

## 🟡 应修

### K4. P-R2 谓词记号 `max{name : ymd<=ds 且非空}` 有字典序歧义（endorse cursor-auto R1 / claude R2）
该谓词要原文进契约，须改写为 `name of (max ymd ≤ ds with nonempty name)` 或 `last_seen[code]` 操作句，防「对名字符串取 max」的实现事故。

### K5. 分钟侧机制：用实验结论直接定案——分钟树自带 volume 列，自检测即可，无需跨 period 依赖（纠正 claude Y3 的「（无 volume 列）」）
E3：分钟 parquet schema 含 volume，停牌日整日 sum=0。落地写法：分钟加载器多读 volume 列，按 `ymd` 聚合，整日 sum==0 → 整日丢行。与日线同谓词、零跨期耦合。claude Y3 括号内「分钟 parquet 无 volume 列」与事实不符（加载器不读 ≠ 列不存在），但其「机制须指明」的问题本身成立——现已有实验答案。codex R7 的「分钟 T+1/pending 与日线不同构」提醒保留：丢行方案下分钟侧无需动 `scan_held_day`，整日缺失自然跳过。

### K6. 「无该列 = 不冻」会被现有 blanket except 吞成「整 code 无数据」（endorse claude Y2，已核实）
`csv_daily_backtest.py:213-217`：`pq.read_table(columns=[...])` 包在 `except Exception: return None` 里。columns 加 `volume` 后，缺列 parquet 会让**整个 code 返回 None**（冻仓+净值 fallback），恰好违反 P-R3「无该列=不冻」。须写明：先读 schema 判列，或缺列时降级重读，不得落进 `return None`。

### K7. 双通道优先级未锁（endorse cursor-auto Y1 / claude Y1）
`pool_names_by_day is not None` → 只走 as-of、忽略扁平 `pool_names`；否则走扁平（测试冻结语义）。写进 P-R2 与契约。

### K8. 旧名前向黏滞（stale-forever）方向未被 §6 覆盖（部分 endorse codex R2，建议降 🟡）
`name_asof` 的 max-ymd 结构使**窗口内摘帽自修正**（新名覆盖旧名），codex R2 的「永久 5%」只在「离池后仍持仓」时成立——该情形正是切片 B 测试② 要的回退语义，属有意设计。但 §6 只写「fail-open 偏宽板」一个方向，与 `market_layer.py:63-64`（ST 名=5% 窄板）合成后存在反向失真（旧 *ST 名→跌停线抬高→`defer_sell_limit_down` 虚增、少卖）。建议：§6 补一句双向描述 + 一条「离池 N 日后名称失效回退板块档」的可选开关（默认不建履历库，与 P-R7 不冲突）。R0 窗无名称列，此条不阻塞 R0。

### K9. R0 转换器的「持仓=当日名单」语义须写进 docstring
E5 实测：Qlib 报表 D 日列表是 **D 日收盘后持仓**（含早前买入，`天数` 列可见），不是「D 日新买」。逐日全量持仓写成当日 pool 后，引擎对已持仓码走 `skip_held`——pool 实为「当日可持有宇宙」，R0 的成交集合 ≠ Qlib 成交集合。plan「只验收管道」成立，但 docstring 须写明该映射假设，防后人拿 R0 交易数对 Qlib 账。

## 🟢 可选

- 全零价占位（E2 的 001232 型）是 C 落地前的现存隐患：目前仅靠 `px<=0` 与 `hit_limit_down(0,0)` 两个巧合守卫兜住，建议在 `engine-ashare-correctness.md` 记一句。
- 名称 as-of 的窗口左缘：窗口首日持仓的名称观测在 `start` 之前时回退为板块档——与 §6 已接受的 lag 同类，写一句即可。
- `.gitignore` 用 `exports/r0_*/` 比笼统 `exports/` 窄（实测当前 `.gitignore` 无 exports 条目，切片 D 新增方向正确）。
- 加一个 `stats["pool_name_coverage"]`（有名称的 pool 日占比），把 K8 的 stale 风险量化，多轮评审不用打架。

## ✅ 做对的地方（保留）

1. **后日赢诊断逐字属实**：`load_pool_name_map` L68-89 later-wins（`csv_pool.py:87-88` `if name: names[code]=name`）、注入点日 `:518` / 分 `:805`、绿测 `tests/test_csv_pool.py:61-66` 正是后日赢——plan 行号全部精确。
2. **T+1 / 无未来 bar 链完整**：买入日 `n_days=0` 不可卖（`:332,341` 双重 `n_days>=1` 门）、止盈默认 `pending_exit` 次日开（`:383-392`）、`prev_rows = index < day`（`:322`）。P-R2 显式禁 `ymd>ds`，方向正确。
3. **复权/盈筹/包边界**：`dividend_type=none` 单一口径（`:237-238`）、P-R7「盈筹率不适用」、胶水禁 `qlib/chip_indicator/StockDataReader`、落点 `scripts/data/`（已存在，实测）。
4. **R0 数据依赖实证满足**：`920014_BJ` 分区存在且窗内 16 行无零量；`scripts/data/`、六个验收测试文件、兄弟仓源文件全部就位；`exports/` 未入 gitignore 与切片 D 的新增一致。
5. **validate 严格 / parse 宽松 / `run()` 不 SystemExit**：`_cell_to_bare("SZ300190")→"300190"`（E4）保住现网带后缀 CSV，严格门只卡胶水与单测——分层正确。
6. **范围纪律**：§2 禁改表与 E-R\* 锁、§5 落点表、§8 勘误与 `review-by-cursor.md` 1:1 对应；切片分 commit、B/C 不绑、C/D 不互验。

## 总评

骨架正确、事实密度高，B/D 切片已具备开写条件；但 **C 的默认方向建立在已被实验证伪的前提上（K1），且 P-R4 存在文字级自锁（K2）**——按 v1.1 原样实施会把「停牌日可成交」的系统性错误以「文档降级」形式固化。建议：采纳 K1（C 升默认落地 = 加载侧丢 volume==0 行，分钟自检测）+ K2/K3/K4 三处契约文字修订 + K7 优先级锁，之后**可进人裁「按 plan 实施」**。

---

## 附录：实验脚本与原始输出（可复现）

环境 `D:\anaconda3\envs\vanna312\python.exe`，全部只读。

**E1 — R0 窗全量零量探测**（核心证据）：

```python
import time, pyarrow.parquet as pq, pyarrow.compute as pc, datetime as dt
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
root = Path(r'F:\stock_data\stock\period=1d\dividend_type=none')  # 与 csv_daily_backtest.py:238 同路径
t0 = int(dt.datetime(2026,3,2,tzinfo=dt.timezone.utc).timestamp()*1000)
t1 = int(dt.datetime(2026,3,23,23,59,59,tzinfo=dt.timezone.utc).timestamp()*1000)
def probe(d):
    f = d/'data.parquet'
    if not f.is_file(): return None
    t = pq.read_table(f, columns=['time','volume'])
    t = t.filter((pc.field('time')>=t0)&(pc.field('time')<=t1))
    if t.num_rows==0: return (d.name,0,0)
    return (d.name, t.num_rows, int((t['volume'].to_numpy()==0).sum()))
# ThreadPoolExecutor(16) 扫全部 symbol=*
```

原始输出：

```text
elapsed 6.1s, symbols probed 5584
symbols with volume==0 rows in 2026-03-02..23: 121
   ('symbol=000711_SZ', 16, 7)  ('symbol=001232_SZ', 16, 16)  ('symbol=300142_SZ', 16, 2) ...
rows per symbol: min 16 max 16
symbols with <16 rows: 0
920014_BJ parquet exists: True / rows in window: 16 / zero-vol: 0
```

**E2 — 占位形态抽查**（`columns=['time','open','high','low','close','volume']`，2026-02-20~03-23）：

```text
001232_SZ: 02-24..03-23 全部 o=0.0 c=0.0 v=0            # 全零价占位
000711_SZ: 02-27..03-03 o=c=3.64 v=0; 03-13..03-19 o=c=4.65 v=0; 03-20 复牌 v=2963038   # 平价占位
300142_SZ: 03-17..03-18 o=c=12.28 v=0; 03-19 复牌 v=1010846
```

**E3 — 分钟树探测**（`resolve_period_root('1m')/dividend_type=none/symbol=000711_SZ`，读 `['time','volume','close']` 成功 → 列存在）：

```text
03-12  count=241 sum=81605
03-13..03-19  count=241 sum=0    # 停牌日分钟树同样补占位
03-20  count=241 sum=2963038
```

**E4 — 规范化/ST 判定**：

```text
920014 -> 920014.BJ ; 300190 -> 300190.SZ ; 600000 -> 600000.SH ; 689009 -> 689009.SH
cell SZ300190 -> '300190' ; cell 300190.SZ -> '300190'
is_st WEST -> False ; is_st *ST 浦发 -> True
limit 920014 noname -> 0.3 ; limit 600000 ST -> 0.05
```

**E5 — R0 源文件**：16 个 `日期:` 块（03-02~03-23），`持仓标的列表:` 16 行，03-02 为 `[]`，BJ920014 出现于 03-11/03-12，无名称列。
