# Plan：名单管道 R2/R5（pred TopN → 契约 CSV → version6）

> **落盘**：2026-09-12。
> **状态**：📄 **v1.0 · 人裁「出实施方案，交 Codex 落地」**。本 PR 合入即授权按切片实施。
> **风险档**：**L1**（pred 导出胶水 + R0 真窗残留修 + 本仓消费闭环；不重写引擎 / 不改卖点 / 不做 R3）。
> **范围**：两仓。MyQuant 出 R2 导出；本仓修 R0 残留并跑 R5。1.3 只读对照。
> **定位 SSOT**：[engine-positioning-ssot.md](engine-positioning-ssot.md)。成交核现锁：[engine-ashare-correctness.md](engine-ashare-correctness.md)（E-R1–E-R4）。名单契约：[pool-csv-contract.md](pool-csv-contract.md)。R0/R1 已合 [#21](https://github.com/baiyibing/MyQuant-backtrader/pull/21)。
> **上游**：MyQuant `docs/plan-three-repo-roadmap-2026-09-12.md` §2.4、§3 R2/R5、§3.1、§6、§8。人裁「先收 R0 真窗，再做 MyQuant R2 导出 + 本仓 R5 闭环；**同一轮不做 R3**」。
> **前序 plan**：[plan-pool-pipeline-r0r1-2026-09-12.md](plan-pool-pipeline-r0r1-2026-09-12.md)（P-R* 仍管 R0 胶水与名称 as-of；其中「不碰 R2/R5」已被本文件取代）。

---

## 0. 一句话

R0 已证明「契约 CSV → `validate_pool_dir` → 日线 version6」能通。本轮把 **Qlib pred 的当日 TopN**（不是持仓）写成同一契约，再跑同一窗 version6。只验收管道，不看赚亏，不当 M5。

```text
MyQuant 预测结果.csv / pred.pkl
        ↓  切片 B 先锁定 pred 日 → 买入日 T
        ↓  my_scripts/export_daily_pool.py   （R2，住 MyQuant）
exports/r2_pred_topn_*（不入库，不写 stock_pool/）
        ↓  本仓 validate_pool_dir
csv_daily --strategy version6 --pool-dir <r2 out>
        ↓
summary.txt   只验收管道；禁止复用 exports/r0_*
```

---

## 1. 现状（禁止重做已落地项）

已落地，本轮 **禁止重开**：

| 已落地 | 锁 |
|--------|----|
| 成交核档位 / 跌停 defer / Decimal 涨跌停价 / 停牌净值 | E-R1–E-R4；PR #18 |
| ST 名称按日 `name_asof`（`ymd<=ds`） | P-R2；PR #21 |
| 加载侧丢 `volume==0` 占位 K | P-R3；PR #21 |
| R0 持仓胶水 + R1 契约 / `validate_pool_dir` | P-R4–P-R6；PR #21 |
| 本仓 README `--pool-dir` 例 | 切片 E；PR #21 |

本机已用真 `position_analysis.txt` 跑通 R0 窗（15 个 CSV，version6 `summary.txt` 落地）。那是 **已实现持仓**，不是 pred TopN。R5 必须另目录。

真报告第 6 行是 `日期范围: 2026-03-02 … 至 …`。已合入的 converter 用 `startswith("日期")`，随后 `_DATE_LABEL_RE.fullmatch` 会炸。切片 A 修这个。产物与 `exports/` 仍不入库。

现成 pred 输入（本机已有，**不要重训**）：

| 文件 | 事实 |
|------|------|
| MyQuant `my_scripts/预测结果.csv` | `datetime,instrument,score`；2026-03-02..03-23 共 **16** 个交易日；约 5479 行/日 |
| MyQuant `my_scripts/预测结果和真实标签.csv` | 另有 `label` 列，供切片 B 对照 |
| `pred.pkl` | 树上未找到；mlruns 被 gitignore。R2 **不**把扫 mlruns 当默认路径 |
| `custom_train_backtest.py` | `topk: 10`；`test_start=2026-03-01`（周日）→ 首个交易日与 pred 首日均为 2026-03-02 |
| `custom_handler.py` `get_label_config` | 复用 Alpha158；注释写 `Ref($close, -2) / $close - 1`（B 必须打印 **函数返回的公式**，不信注释） |

R0 窗 2026-03-02..03-23 无中国大陆节假日，只有周末（03-07/08、03-14/15、03-21/22）。pred 日期集合已跳过这些周末。

---

## 2. 非目标 / 禁改

| 不做 | 原因 |
|------|------|
| R3：改 `custom_train_backtest.py` 过滤器 / processor / 训练走查 | 人裁本轮不做 |
| 再拆 `csv_daily` / `csv_minute` / 改 `execute_buy` / `_sell` / 1–8 卖点 / `register(version7)` / 改 `presets.py` | Q2-R1 |
| 本仓第二份 pred 导出，或本仓 `import qlib` / `chip_indicator` / `StockDataReader` | 导出 SSOT 住 MyQuant；本仓只消费 CSV |
| 把 R0 `exports/r0_*` 当 R5 输入 | 持仓 ≠ 当日 TopN；路线图 M5 |
| 写两仓 `stock_pool/` | 隔夜短线池，不是 Qlib 信号 |
| 喂策略 7 / 先上分钟 / 用 Qlib PortAnaRecord 或 Cerebro 净值验收 | P-R5 / 第四套引擎禁令 |
| 用 R5 窗净值或涨跌停桶判断模型 / 档位 | 路线图 §3.1 / M5 |
| 为 pred 名单编造名称列 | 源没有名称；无名 ST 按前缀档，不当 E-R2 |
| TopkDropout 的 `n_drop` / `hold_thresh` 持仓回放 | 那是 R0；R2 只做当日 score TopN |
| `qlib.data.D.calendar` 当三仓交易日 SSOT | 路线图 §6 |
| 改 `docs/architecture/reviews/**` 历史评审 | 考古 |
| 本仓完成定义包含改 MyQuant / 1.3 README 或路线图 §8 | 外仓债；不阻塞 |
| 复活 `engine.py` / 拷 LEBS·MockQMT | 第四套引擎禁令 |

---

## 3. 现锁（Q2-R*）

| ID | 锁 |
|----|----|
| **Q2-R1** | 只做：A 修 R0 `日期范围:`；B 实测 pred as-of；C MyQuant 导出；D 本仓 R5 消费；E 本仓文档。禁止 R3。禁止重写引擎、改卖点、改 `presets.py`、`register(version7)`、Qlib/Cerebro 净值对照。 |
| **Q2-R2** | **产品锁**（路线图 §2.4 + [pool-csv-contract.md](pool-csv-contract.md)）：文件名 = 买入日 T。**映射假设 H0**：`file[T] = TopN(pred[prev(T)])`，即内容来自 pred(T−1)。`prev` / `next` **只**用该 pred 文件里已出现的日期集合，禁止 `D.calendar`，禁止 `weekday+1` 猜假期。实现：对每个 pred 日 `D` 写 `next(D).csv`，内容 = TopN(pred[D])；**最后一个 pred 日没有 next → 不写文件**。切片 **B 先于 C 锁默认 `--asof`**。B 结论只能是 `pred_minus_one`（H0）或 `identity`（`file[T]=TopN(pred[T])`）。若实测 pred 索引日已经是买入/成交日，必须用 `identity`，**禁止再套一层 T−1**，并先改本条再写 C。仍歧义则默认 H0，把残余风险写进 B 笔记。C 的 CLI **必须同时**实现 `--asof pred_minus_one` 与 `--asof identity`；默认值 = B 锁定值，写进 docstring。契约「文件名=买入日」不改；改的只是 pred 哪一行写入那天。 |
| **Q2-R3** | R2 路径：MyQuant `my_scripts/export_daily_pool.py`。单测：`my_tests/test_export_daily_pool.py`。禁止放进本仓 `scripts/research/` 或本仓第二份导出。禁止 MyQuant 导出脚本 import 本仓包。方言在导出侧完成：`SZ300190` / `SH600000` / `BJ920014` → 裸六位。 |
| **Q2-R4** | 输出：utf-8 **无 BOM**；**无表头**；**无名称列**；每行恰好六位数字。无法匹配 `^(?:SH|SZ|BJ)?(\d{6})$` 的 instrument 丢弃，stderr 计数。该日无有效 TopN → 不写文件。禁止写两仓 `stock_pool/`。MyQuant 默认 `--out-dir exports/r2_pred_topn_20260302_20260323/`。本仓 `/exports/` 已 gitignore；MyQuant 已 ignore `*.csv`，仍须写进 `exports/` 而不是 `my_scripts/`。 |
| **Q2-R5** | TopN 默认 **10**（对齐训练脚本 `topk: 10`）。排序：`score` 降序，并列按 **instrument 原字符串**升序，再转裸码；去重保序。不是持仓回放。R5 **禁止** `--pool-dir exports/r0_*`。 |
| **Q2-R6** | `--pred` 必填。支持：(1) CSV 列 `datetime,instrument,score`（本机现成 `my_scripts/预测结果.csv`）；(2) pickle：MultiIndex `(datetime, instrument)` + `score` 列。文件不存在 → SystemExit，文案带路径。禁止把「扫描 mlruns 最新 pred.pkl」写成默认。不要为跑 R2 重训模型。 |
| **Q2-R7** | R5 验收：① MyQuant 导出单测绿；② 本仓 `validate_pool_dir(<r2 out>)` 返回 `[]`；③ `csv_daily_backtest.py --strategy version6 --pool-dir <r2 out> --start <导出后最早文件名> --end <导出后最晚文件名>` 写出 `summary.txt`。`--start/--end` **跟文件走**，不要盲写 `20260302`（H0 下可能没有该文件）。产物不入库。失败只报管道。禁止把该窗净值或涨跌停桶当模型/档位结论。HELP/docstring 写明无名 ST 按前缀档。version8 可选。不喂 7。只用日线。 |
| **Q2-R8** | R0 残留：`scripts/data/r0_positions_to_pool.py` 对 `日期范围` 开头的行返回 `None`，不要当 `日期:`。其它 P-R4 解析不变。单测锁真实头一行。 |
| **Q2-R9** | 本仓完成定义 **不含** 改 MyQuant / 1.3 README。docs PR [#19](https://github.com/baiyibing/MyQuant-backtrader/pull/19) 在本 plan 合入后关闭（实现已走 #21）。不改 `docs/architecture/reviews/**`。 |

---

## 4. 切片（本 PR 合入后 Codex 做）

两仓、两条实施分支。**不要**在本 docs 分支上改业务代码。

| 切片 | 仓 | 做什么 | 完成定义 |
|------|----|--------|----------|
| **A · R0 残留** | 本仓 | `日期范围:` 不当日；补单测 | `tests/test_r0_positions_to_pool.py` 含该头；converter 单测绿。不提交 `exports/` |
| **B · as-of 门** | MyQuant | 只读实测 pred 日 vs 买入日 T；落笔记 | `my_docs/pred_asof_r2_2026-09-12.md` 写明 `--asof` 取值与一句理由。不改训练脚本。若结论不是 H0，先改本文 Q2-R2 再开 C |
| **C · R2 导出** | MyQuant | `export_daily_pool.py` + 最小 fixture 单测 | 裸码；文件名=买入日；两种 `--asof`；并列稳定；非法码丢弃；空日无文件。禁止写 `stock_pool/` |
| **D · R5 闭环** | 两仓 | 现成 pred CSV → 导出 → validate → version6 | validate 空列表；`summary.txt` 落地；目录不是 `exports/r0_*`。产物不入库。可选：抽 ≥3 个有文件日，R2 全日集合不得与 R0 全日集合全等（碰巧一天相同可以） |
| **E · 本仓文档** | 本仓 | README 补 R5 `--pool-dir` 例；关 #19 | 本仓入口不漂。**不含**改外仓 |

顺序：**B 合入默认 `--asof` 之前不得把 C 当完成。** A 可与 B 并行。本仓 A 与 E 分 commit。MyQuant B 与 C 分 commit。禁止把 R0 持仓 CSV 拷进 R2 目录充数。

本仓实施验收：

```text
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_r0_positions_to_pool.py
```

MyQuant 实施验收（解释器跟该仓现用 qlib 环境；不要把 qlib 装进本仓）：

```text
python -m pytest -q my_tests/test_export_daily_pool.py
```

R5 本机命令（路径按导出后的首末文件改；H0 示例）：

```text
# MyQuant
python my_scripts/export_daily_pool.py --pred my_scripts/预测结果.csv --topk 10 --asof <B锁定> --out-dir exports/r2_pred_topn_20260302_20260323

# 本仓（pool-dir 用绝对路径指向上面的 out-dir）
D:\anaconda3\envs\vanna312\python.exe -c "from pathlib import Path; from backtest.research.csv_pool import validate_pool_dir; err=validate_pool_dir(Path(r'<r2 out>')); assert err==[], err"
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py --strategy version6 --start <first> --end <last> --pool-dir <r2 out>
```

有 `F:\stock_data\.authority` 时不要残留 `OSKH_PERIOD_*`（否则湖可能不跟 F）。缺 2026-03 日线分区 = 管道失败，不是模型失败。

---

## 5. 代码落点

### 5.1 本仓（A / D 消费 / E）

| 文件 | 动作 |
|------|------|
| `scripts/data/r0_positions_to_pool.py` | A：`日期范围` 行忽略 |
| `tests/test_r0_positions_to_pool.py` | A：锁真实报告头 |
| `docs/backtest/README.md` / `README.md` | E：R2/R5 例 + 链本 plan |
| `docs/backtest/plan-pool-pipeline-r0r1-2026-09-12.md` | 文首一句指向本文（已在本 PR） |

禁止改：`csv_ledger.py` 成交公式、`market_layer.limit_pct`、`csv_minute_backtest_v7.py`、`csv_strategy_books.py`、`presets.py`、`csv_pool.py` 契约语义、`docs/architecture/reviews/**`。D 不新增本仓导出脚本。

### 5.2 MyQuant（B / C）

| 文件 | 动作 |
|------|------|
| `my_docs/pred_asof_r2_2026-09-12.md` | **新建** B 笔记 |
| `my_scripts/export_daily_pool.py` | **新建** R2 |
| `my_tests/test_export_daily_pool.py` | **新建**；仓内最小 utf-8 fixture，不要提交 8 万行 pred |
| `.gitignore` | 若 `exports/` 未忽略，补上（`*.csv` 已忽略仍建议目录化） |

禁止改：`custom_train_backtest.py`（R3）、`custom_handler.py` 标签公式、Qlib 策略 `n_drop` 逻辑。

---

## 6. 风险 / 已知失真

- R2/R5 无名称列 → 真 ST 按板块档（10/20/30），不是 5%。与 R0 相同。写进导出 docstring；该窗不当 E-R2。
- H0 会少一天买入文件：16 个 pred 日 → 15 个 CSV（末日无 next）。`--start/--end` 必须跟文件。identity 则 16 个文件，含 `20260302.csv`。
- `预测结果.csv` / `*.pkl` 被 MyQuant gitignore，路径只存在于本机。CI 只跑 fixture，不跑真窗。
- 本机若残留 `OSKH_PERIOD_*`，F 湖权威文件可能被绕过。
- R5 净值不是名单质量。R0 与 R5 净值不可比（持仓回放 vs 当日 TopN）。
- 切片 B 若偷懒套 H0、而 pred 索引已是买入日，会把名单整体平移一天。这是本轮唯一允许停下来改 plan 的点。

---

## 7. 修订程序

改 Q2-R* 须改本文。改成交核须改 [engine-ashare-correctness.md](engine-ashare-correctness.md) 的 E-R*。改名单文件名语义须改 [pool-csv-contract.md](pool-csv-contract.md)。B 若推翻 H0，先改 Q2-R2 再写 C。

---

## 8. Codex 工作方式

1. 从 **当前 master**（PR #21 / `dac140e` 之后）开实施分支，例如 `feat/pool-pipeline-r2r5`。MyQuant 另开兄弟分支。不要从本 docs 分支改代码。
2. 按 A（本仓）∥ B（MyQuant）→ C → D → E。B 未写出 `--asof` 不得宣称 C 完成。
3. 每个切片单独 commit。提交说明写切片字母。
4. 不要提交 `exports/`、`backtest_output/`、真 pred、R0/R5 CSV、`summary.txt`。
5. 本仓 Python：`D:\anaconda3\envs\vanna312\python.exe`。MyQuant 用其现有 qlib 环境；不要把 qlib 加进本仓 `requirements.txt`。
6. 文本文件 UTF-8 无 BOM。写完 `.py` / `.md` 后 NUL 字节必须为 0。
7. 关闭 [#19](https://github.com/baiyibing/MyQuant-backtrader/pull/19)。[#20](https://github.com/baiyibing/MyQuant-backtrader/pull/20)（survey9）无关，不要并进本轮。
