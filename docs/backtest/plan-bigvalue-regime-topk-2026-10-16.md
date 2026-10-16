# Plan: 联合 TopK 全市场大单净量 regime（2026-10-16）

> **状态**：**v0.1 草案**。待 Claude review。**不是 impl GO**。本 PR 只加文档。
> **日期**：2026-10-16
> **基线**：`master` `217682671a368455e2592dc2e2788547bede2fa2`
> **风险档**：本 PR 无行为风险。将来若单独 GO 实施，挡新开是低风险闸（默认关）；强平会改持仓，默认关，且比挡新开狠得多。
> **消费书**：只动联合书 `topk_dropout` 的开关。不复制 `strategy_topk_dropout_rules.py`。
> **依赖**：开着的 [#475](https://github.com/baiyibing/MyQuant-backtrader/pull/475) `feat/bigdata-ma-cross`（`scripts/data/bigdata_ma_cross.py`）。该 PR 当前 CI 红，见 §12。实施前必须先去掉盘符默认。
> **账本**：[topk-joint-research-tracker-2026-09-22.md](topk-joint-research-tracker-2026-09-22.md) 新增 **Q12 仍开 / 待裁**。**Q8 仍开**，本计划不关它。
> **行业站位**：[ssot/backtest-rule-principles-ssot.md](ssot/backtest-rule-principles-ssot.md)。本仓是回测，不是交易系统。

---

## 0. 一句话

用全市场日频 **大单净量 `bigvalue`** 的均线状态，给 `topk_dropout` 加一道 **领先的风险开关**（risk-on / risk-off）。信号在信号日收盘后才算数，**下一交易日**才作用于全市场新开或（可选、默认关）减仓。它像 `--index-ma5-gate`，是一根序列挡所有票。它不是 `--buy-state-file` 那种逐票买点旁路。

```text
bigdata.csv  date,bigvalue          #475 脚本（先修 path-SSOT）
        │  剔除表尾连续 0
        ▼
parquet  date, bigvalue, ma*, cross_*
        │  决策日 T 只读 date ≤ T−1 且已定稿的行
        ▼
topk_dropout 开关（默认全关，缺日 fail-closed）
  死叉态 → 挡新开
  死叉态 → 强平          （默认关，更狠）
  金叉态 → 资金倍数      （默认关；不突破 risk_degree 的现金上限）
```

默认标签是 **连续状态**（死叉态 = 快均线 < 慢均线，金叉态 = 快均线 > 慢均线），窗草案 5×10。`cross_5_10 = ±1` 只是可选边沿。状态每个定稿日都有标签，边沿只在穿越日跳一下。要的是 **最密且稳** 的那一种（densest-stable）：用状态，不用脉冲。

---

## 1. 问题与动机

联合 TopK 已经有两类「闸」，都解决不了这件事：

| 现闸 | 粒度 | 它回答的问题 | 为什么不够 |
|---|---|---|---|
| `--buy-state-file` | 逐票 | 这只票今天的价和盈筹过不过买点 | 选股条件。不是市场风险开关 |
| `--index-ma5-gate` | 全市场一根 | 上证收盘是否低于自身 MA5，是则 **次日** 不新开 | 同形态，但是价格趋势，不是资金流 |

大单净量是全市场聚合成交的资金流，一天一个数，没有代码列。研究问题是：这根流的快慢均线处在金叉态还是死叉态时，50/5 这本书是该少开、清掉，还是把留存现金铺上去。它不负责从截面里挑票。挑票仍是 pred 分和既有买闸。

动机只到这一步。本计划不声称大单净量已经证明有超额，也不改线上 10/3。

### 1.1 现码锚（kin，已在 master）

上证闸是要抄的形态，不是要改的行为。

| 锚 | 位置 | 口径 |
|---|---|---|
| CLI | `csv_strategy_books.py` `--index-ma5-gate`，`store_true`，默认关 | HELP_LOCK：全市场只看 `000001.SH` |
| 帮助锁 | `strategy_topk_dropout_rules.py` `HELP_LOCK` | 信号日 = 买入日前一根交易日。该日收盘 < 含当日的 5 日均线 → **下一交易日**所有新开不买。收盘 = 均线不挡。缺前史或不给正收盘 → 不买。不因此强卖已持仓 |
| 切日 | `topk_dropout_eligibility.index_ma5_buy_days` | 信号日 S = 买入日的前一根正收盘。`close[S] < mean(S 往前 window 根)` 则挡住买入日。窗不够 → 该买入日进入 blocked（fail-closed） |
| 接线 | `_run_kwargs_topk_dropout` → `make_eligible_buy(..., index_ma5_gate=True)` 的 `seat_ok` | 日线、分钟共用这本书的 kwargs。挡住的是新开席位。不强制卖 |
| 同文件另一函数 | `with_ma5_gate` | **不是** 上证闸。只在 `--buy-state-rule above-ma5-ma20-week20` 时由两个入口套上。逐票：买入日收盘 > 该票自己的 5 日均线。缺历史则该席位空着，不强制卖 |

大单净量闸对齐的是 **上证闸**：全市场一根序列、信号日收盘定标签、下一交易日才挡新开。不要接进 `with_ma5_gate`。那个函数是逐票、用买入日自己的收盘，和「领先、次日」不是同一条时钟。

资金侧现锁，实施时不得改默认：

- `strategy_topk_dropout_rules.QLIB_CASH_DEPLOY = 0.95`（qlib `risk_degree`）。
- HELP_LOCK：新买额度 = `min(日额度, 现金) * 0.95 / n_buy`。
- `csv_simulate_loop`：`cash_deploy_frac` 必须落在 `(0, 1]`，否则 `ValueError`。
- 书族默认日额度 = `--cash-total`（不传 `--daily-quota` 即是）。显式 `--daily-quota` 仍覆盖。

同日卖出现锁（Q6，不改）：日线先评止损（`stop_loss:gap_open` / `touch` / `--stop-fill close` → `stop_loss:close`），再评 `sell_gate` / dropout。同日只出一笔卖，reason 记止损。见 tracker §7 第 11 条、§8 Q6。

---

## R. 硬锁（R\*）

实施 PR 也不得破。本计划文件本身不授权实施。

| ID | 硬锁 |
|---|---|
| **R1** | **只做领先**。信号在信号日收盘之后才成立。效果在 **下一交易日**。决策日 T 的查找只用 **已经定稿** 且 `date ≤ T−1` 的行。禁止用 T 当日的 `bigvalue` / `ma*` / `cross_*` 决定 T 当日的新开、强平或加仓。禁止未来函数。 |
| **R2** | 表尾连续 `bigvalue == 0` 是盘中占位，必须剔除。口径与 #475 默认 `drop_trailing_zeros` 相同（`--keep-zeros` 的反面）。回测 **加载时再剔一次**，不信任上游已经剔过。只剔表尾那一串 0。中间的 0 是数据，留着。 |
| **R3** | 全市场聚合。一天一行 `date, bigvalue`，没有代码列。闸的形态是 `--index-ma5-gate`。**不是** `--buy-state-file`。禁止把大单净量拆成逐票 sidecar，禁止拿它改 pred 排序。 |
| **R4** | **一书加开关**。只扩展 `topk_dropout`。禁止复制 `strategy_topk_dropout_rules.py`。禁止新 `strategyN_rules.py`、禁止新 `version*` 注册、禁止写进 1–10 BOOKS。将来改 HELP_LOCK、本 tracker、data-free 测试三处一起改。 |
| **R5** | 行为开关 **全部默认关**。开了任一行为开关却缺文件、缺列、日期重复：直接失败退出。不得把缺行当成金叉，不得用缺行去强平，不得造一行填洞。缺信号日是「挡新开」还是「整次退出」见 P7，两边都禁止照常买卖。 |
| **R6** | 默认标签是连续状态，不是脉冲。死叉态：`ma_fast < ma_slow`。金叉态：`ma_fast > ma_slow`。草案窗 5 与 10，可配。`cross_{fast}_{slow} = +1/−1` 只是可选边沿。默认不看它。 |
| **R7** | 不改 Q6。止损先于 dropout。强平默认关。同日同一持仓只卖一次。T+1（含红股锁定）挡住的仓，强平也卖不掉，走现有延期，不新写一套 T+1。 |
| **R8** | `risk_degree = 0.95` 的默认不改。金叉倍数 **不得** 把 `cash_deploy_frac` 送到 `> 1`。现金账户不加杠杆、不融资。倍数的精确定义见 P3，未裁前不得实施加仓臂。 |
| **R9** | 源码里禁止默认盘符。禁止 `E:/stock_data`、`F:/stock_data`，禁止探测盘符，禁止缺路径时返回空表假装没数据。路径只来自显式 CLI，或仓内已有 resolver。#475 的 `DEFAULT_CSV = E:/stock_data/bigdata.csv` 未删除前，本功能 **不得** 合入实现。 |
| **R10** | **Q8 仍开**。本计划不叠 ST、年龄、5 日涨幅 >15% 挡。不改线上 10/3。不用 PortAna NAV 当胜负。不改 `--stop-fill` 默认 `touch`。 |
| **R11** | 开关全关时，现有 `topk_dropout` 默认路径行为不变。既有 data-free 测试不放宽、不改 golden 去消差异。 |
| **R12** | `--index-ma5-gate` 与任一 bigvalue 行为开关同时打开：P1 未裁前 **拒绝运行**。禁止实施者私自选 AND、独立或互斥。 |
| **R13** | 本文是计划。draft PR、Claude review、人裁 P\* 之前，没有 impl GO。 |

遇本文没写死的语义分叉：停下来问人。不自裁。这与 overlay 任务书 R-10、tracker §8 的规矩相同。

---

## 2. 非目标

- 不在本 PR 改 `.py`、测试、HELP_LOCK、CI、#475 的脚本。
- 不把 #475 合并进本分支。不在本计划里重写大单净量的采集。采集仍在仓外；本仓只读 parquet。
- 不新开策略书，不把闸接到 version1–12、`topk_app_dropout`，也不接到 Mode A/B。
- 不用大单净量做选股、改 `n_drop`、改 50/5、改止损阈值或止损价域。
- 不把金叉做成两倍净值或融资。见 P3。
- 不关 Q8，不把年化 A 格的 5 日涨幅 >15% 挡写进默认。
- 不复活 Cerebro / PortAna / LEBS。不在热路径 `import qlib`。
- 不改 `csv_simulate_loop` 的默认买入公式。将来强平若要碰卖出环，必须旗标关着时字节级走原路径（R11）。
- 不为烟测把 parquet 或 CSV 提交进 git。

---

## 3. 数据契约

### 3.1 两段，不要混

| 段 | 谁 | 输入 | 输出 |
|---|---|---|---|
| 构建 | #475 `scripts/data/bigdata_ma_cross.py` | CSV，两列 `date,bigvalue`（`--value-col` 可改名） | parquet |
| 消费 | 将来的 `topk_dropout` 加载器 | **只读 parquet** | 每个买入日一个 regime 标签 |

策略书不读 vendor CSV。CSV 的路径不得写进回测默认值。

### 3.2 列（以 #475 当前脚本为准）

脚本在 `feat/bigdata-ma-cross`，commit `659c796c8b6bda25da2c97dc633a178351434550`。未合并。列以该文件为准，合并后若列名变了，先改本计划再写加载器。

| 列 | 类型 | 含义 |
|---|---|---|
| `date` | int `YYYYMMDD` | 一行一个日期。重复日期：脚本 `SystemExit` |
| `bigvalue` | float | 全市场大单净量。无代码列 |
| `ma{w}` | float | `rolling(window=w, min_periods=w).mean()`。窗不满为 NaN。与 `oskh_factors/chip/bands.py` 的 `min_periods=window` 同方向 |
| `cross_{f}_{s}` | Int8，可空 | 快减慢的 **穿越**：前一日 diff≤0 且当日 diff>0 → `+1`；前一日 diff≥0 且当日 diff<0 → `−1`。脚本 docstring 写「其余 0、暖机 NA」。`add_cross` 的现码是非穿越日（含暖机）都留 `NA`；`0` 只在打印前 `fillna(0)`，**不进 parquet**。加载器把 `NA` 和将来若写出的 `0` 都当成「这一天没有 ±1」。暖机还是「无穿越」靠旁边的 `ma*` 是否为 NaN 来分，不靠这一列单独分 |

#475 默认 `--ma-windows 3 5 10`，`--cross-pairs` 缺省则窗口两两全配。因此默认产物 **含** `ma5`、`ma10`、`cross_5_10`。研究默认只用 5×10。3 日不进研究默认（P6）。

状态（本计划默认，**不是** #475 的 `cross_*` 列）：

| 标签 | 条件 | 说明 |
|---|---|---|
| 死叉态 | `ma_fast < ma_slow` | 连续。死叉日没发生也可以是死叉态 |
| 金叉态 | `ma_fast > ma_slow` | 连续 |
| 等号 | `ma_fast == ma_slow` | 既不触发死，也不触发金。见 P8 |
| 暖机 | 任一均为 NaN | 窗不满。不是金叉。见 P9 |

`cross_5_10 = −1` 只说明 **这一天发生了向下穿越**。下一日若仍是 `ma5 < ma10`，而 `cross_5_10` 不再是 −1（parquet 里这一列回到空，打印时才被填成 0），状态机仍处在死叉态。这就是 densest-stable：状态覆盖穿越之后的每一天；脉冲只覆盖穿越日的下一天。

### 3.3 表尾 0

#475 文档与实现：从末尾向前，连续 `value == 0.0` 的行删掉。`--keep-zeros` 才留。盘中拉取常把未收盘日写成 0，写进均线窗口会把 **这一行自己的** MA 拉偏。

消费侧规则：

1. 读 parquet 后按 `date` 排序。
2. 再跑一遍与 #475 相同的表尾剔除（连续尾部 `bigvalue == 0`）。
3. 剔除之后的最后一行，才是「目前最后一根已定稿日」。
4. 决策不用被剔除的行，也不用 `date` 晚于 T−1 的行。

只剔表尾。历史中间的 0 若是真值，留在窗口里。禁止把「所有 0」都删掉再重算均线。

预计算的 `ma*` 是向后看的滚动。表尾多出来的 0 **不会改写更早行的 MA**。危险的是把 0 这一行自己当成信号日。所以剔除的是「不许选这行」，不是「重算全部历史」。加载器 **禁止** 在回测里用另一套 `min_periods` 重算 MA（P14 草案）。缺 `ma{fast}` / `ma{slow}` 列就失败。

### 3.4 路径

| 角色 | 规则 |
|---|---|
| 构建脚本 `--csv` | 实施依赖落地前，必须改成 **无默认盘符**。见 §12 |
| 构建脚本 `--out` | 显式路径。默认同名 `.parquet` 可以留，但不得夹带 `E:` / `F:` |
| 回测 `--bigvalue-regime-file` | 无默认。行为开关打开时必填。文件不存在 → 失败，不是当成关 |

禁止：写死 `E:/stock_data/bigdata.csv`；启动时扫描 E:、F:；环境变量没设就空表返回。与 `AGENTS.md` 数据盘规矩、`scripts/gates/verify_no_hardcoded_machine_paths.py` 一致。该 gate 的模式含 `[EF]:[/\\]+stock_data`，扫 `scripts/**/*.py` 的可执行代码（docstring 与 `#` 注释不算）。

### 3.5 日历

信号日取 **这本书已经在用的交易日历** 上、买入日 T 的前一根交易日，记为 S。要求剔除表尾 0 之后的 parquet **有且仅使用** 这一行 `date == S` 的标签。

- parquet 没有 S → 缺日（P7），禁止改用「parquet 里更早的最后一行」偷偷顶上。
- S 的 `ma*` 为 NaN → 暖机（P9），不是金叉。
- parquet 在用到的区间里出现这本书日历不认识的日期（例如把周末写进行）→ 失败退出。不跳过、不重算。避免构建端的行集合和回测日历悄悄岔开，均线却还沿用 parquet 里的数。

---

## 4. CLI 草案

全部 **拟**。未进 HELP_LOCK，未进 argparse。名字先钉住，避免实施时再发明一套。

公共解析将来放在 `add_topk_dropout_args`（与 `--index-ma5-gate` 相邻）。日线入口和分钟入口都能看见旗。消费只在 `topk_dropout`。其它书：见 P13。

| 旗 | 草案默认 | 打开之后 |
|---|---|---|
| `--bigvalue-regime-file PATH` | 无 | parquet 路径。无盘符默认 |
| `--bigvalue-block-new` | 关 | 信号日 S 为 **已确认死叉态** → 买入日 T **所有新开不买**。不卖已有仓 |
| `--bigvalue-flatten` | 关 | 信号日 S 为 **已确认死叉态** → 买入日 T 对可卖持仓发强平。比挡新开狠。见 §7、P10–P12 |
| `--bigvalue-golden-mult M` | 不传 = 关 | 信号日 S 为 **已确认金叉态** 时，把部署系数相对 0.95 放大。M 为浮点。见 P3。不传则系数仍是 0.95 |
| `--bigvalue-ma-fast` | `5` | 快线窗。列名 `ma{fast}` |
| `--bigvalue-ma-slow` | `10` | 慢线窗。必须大于 fast |
| `--bigvalue-confirm-days` | 草案 `2`（P4 未裁） | 同一标签要在 S 往前连续 N 个 **已定稿交易日** 都成立，S 当日才算确认。N=1 等于不额外防抖 |
| `--bigvalue-signal` | 草案 `state`（P5 未裁） | `state` / `edge` / `state-and-edge` |

行为开关指：`--bigvalue-block-new`、`--bigvalue-flatten`、以及「传了 `--bigvalue-golden-mult`」。三个都关，就是今天的书。

校验（将来，fail-closed）：

- 任一行为开关打开，但没有 `--bigvalue-regime-file` → 退出。
- 给了文件，三个行为开关都关 → 退出。避免「文件白加载、人以为闸开了」。
- `fast >= slow`、`confirm-days < 1`、`signal` 不在三选一里、`golden-mult` 非有限正数 → 退出。
- 与 `--index-ma5-gate` 同时出现 → P1 未裁前退出（R12）。
- `topk_score_exit` 收到任一这些旗 → 草案是拒绝（P13），与它拒绝 `--buy-state-file` 同一方向。

### 4.1 三个行为开关彼此不隐含

| 组合 | 死叉态已确认的那些买入日 |
|---|---|
| 只挡新开 | 不新开。旧仓仍走止损和 dropout |
| 只强平 | 可卖的仓卖掉。**次日**若仍是死叉态且没开挡新开，dropout **会再买**。同一天被 `sold_today` 挡住，不会当天买回。持续死叉态会变成「卖了又买」 |
| 挡新开 + 强平 | 卖掉，并且死叉态持续期间不补 |
| 只金叉倍数 | 死叉态不加仓、也不挡。金叉态才动系数 |
| 金叉倍数 + 死叉挡新开 | 一天只有一个状态。死叉日只走挡，金叉日只走倍数，等号日两边都不触发 |

禁止在实现里写「开了强平就自动打开挡新开」。两臂要分开才能看见换手。矩阵见 §8。

### 4.2 confirm-days

例：N=2，只看死叉态。

| S−2 | S−1 | S | S 是否已确认死叉 | 下一交易日 T |
|---|---|---|---|---|
| 金 | 死 | 死 | 是（S 与 S−1 连续两日） | 挡新开 / 或强平，看旗 |
| 死 | 金 | 死 | 否（到 S 只有 1 日） | 不按死叉动作 |
| 死 | 死 | 等号 | 否 | 等号不是死叉态。连续计数在等号日断开 |
| 暖机 | 死 | 死 | 否 | 暖机日不能凑进 N |

N 的草案是 2，用来压住均线贴在一起时的来回翻。P4 未裁，实施前可以改成 1 或 3。旗的存在是人已点名要的；**默认数字仍是切点**。

### 4.3 `state` / `edge` / `state-and-edge`

| 取值 | 死叉在 S 成立的条件 | 密度 |
|---|---|---|
| `state`（草案） | `ma_fast < ma_slow`，再叠加 confirm-days | 穿越之后每个定稿日都有标签。最密、最稳 |
| `edge` | `cross_{fast}_{slow} == −1`（金叉看 `+1`）。脉冲 **没有**「持续死叉态」。confirm-days 对脉冲的含义见下 | 只在穿越日的下一交易日动作 |
| `state-and-edge` | 状态已是死叉态，且在以 S 为尾的 confirm 窗口内 **至少出现过** 一次 `cross == −1` | 比纯状态稀。边沿用来确认，不单独当 regime |

`edge` 且 `confirm-days > 1`：草案是「以 S 为尾的 N 日里出现过该方向的 cross，且 S 当日 cross 不必再为 ±1」。这和 `state-and-edge` 仍不同：`edge` 不要求 S 的均线仍处在那一侧。P5 未裁前，实现只许按当时裁下来的一个取值写测试，不许三个都做成默默都能跑的生产默认。

金叉侧对称：`state` 用 `>`；`edge` 用 `cross == +1`。

### 4.4 金叉倍数与 `risk_degree`（草案公式，P3 未裁前不编码）

现公式，开关关着时一个字不改：

```text
per = min(日额度, 现金基数) * 0.95 / n_buy
```

`0.95` 是 `QLIB_CASH_DEPLOY`。引擎拒绝 `cash_deploy_frac > 1`。

草案在 **金叉态已确认且传了 M** 时：

```text
eff = min(1.0, 0.95 * M)
per = min(日额度, 现金基数) * eff / n_buy
```

M=2 时 `0.95 * 2 = 1.90`，`eff = 1.0`。多出来的是原本留下的约 5% 现金，**不是两倍名义本金**。总支出仍不超过现金，不融资。

死叉态、等号、未确认、缺日：系数回到 `0.95`，且缺日按 P7 还可能直接不新开。倍数 **叠加在** `risk_degree` 之上，不替换 HELP_LOCK 里的 0.95 默认句。关旗时 HELP_LOCK 那句仍是唯一公式。

显式 `--daily-quota` 仍是上限的一部分（`min` 的左边）。倍数不放大配额越过这个 `min`。

若人要的「双倍」是 1.9 倍现金或两倍净值：本现金账户做不到。那要另立保证金模型，**不在本计划**。

### 4.5 HELP_LOCK 将来要写进去的话（拟，本 PR 不改文件）

实施时把下面的意思追加进 `strategy_topk_dropout_rules.py` 的 `HELP_LOCK`，并在 `tests` 里 pin 住关键字。此处只是草稿：

```text
--bigvalue-regime-file  全市场大单净量 parquet（date, bigvalue, ma*, cross_*）。
  无默认路径。与 --bigvalue-block-new / --bigvalue-flatten / --bigvalue-golden-mult
  任一同时才读。缺文件、缺列、重复日、信号日缺失：fail-closed。
  决策日只用前一交易日及更早的已定稿行。表尾连续 bigvalue=0 剔除后再取。
  默认状态：ma5 < ma10 死叉态，ma5 > ma10 金叉态。等号不触发。
  --bigvalue-block-new     默认关。死叉态确认 → 次日全部新开不买。不卖旧仓。
  --bigvalue-flatten       默认关。死叉态确认 → 次日强平可卖仓。比挡新开狠。
  --bigvalue-golden-mult   默认不传。金叉态确认才把 0.95 放大，结果仍 ≤ 1，不加杠杆。
  --bigvalue-confirm-days  连续确认天数。--bigvalue-signal state|edge|state-and-edge。
  与 --index-ma5-gate 的组合在人裁前拒绝同时打开。
  这不是 --buy-state-file。不改 risk_degree 默认 0.95。Q8 的 ST/年龄/15% 挡不在这里。
```

---

## 5. Asof / 时序

时间轴只有一条。和上证闸、和 pred 的 `pred_minus_one` 是同一类「昨天定、今天用」，不是同一份数据。

```text
信号日 S 收盘  →  bigvalue[S] 定稿  →  ma*[S]、cross_*[S] 可算
下一交易日 T   →  新开 / 强平 / 倍数 使用 S 的标签
T 的行情       →  只用于成交价、止损、dropout，不回写 S 的标签
```

查找：

1. 定买入日 T（日线收盘买，或分钟入口当天的买钟，都用 **这一个交易日** 当 T）。
2. S = 这本书日历上 T 的前一交易日。
3. 在「已剔除表尾 0」的表里取 `date == S`。没有就按 P7。
4. 该行的 `ma*` 只用 S 及更早的 `bigvalue`（构建端 rolling 已经是这样）。消费端不再读 `date >= T` 的任何列来修改这个标签。
5. confirm-days 的窗口是 `S, S−1, …` 这些 **交易日**，每一天都要在表里有定稿行。中间缺一天就不是连续，不能跨过洞去数。

例：

| 买入日 T | 允许使用的最后一行 | 禁止 |
|---|---|---|
| 20261014 | `date == 20261013` 的状态 | 读 `20261014` 的 bigvalue，哪怕文件里已经有收盘后的数 |
| 20261014，且文件末行是 `20261014, bigvalue=0` | 先丢掉末行。信号仍只看 `20261013`。若 `20261013` 不在了，算缺日 | 用 0 这一行的 MA 当 20261014 或 20261015 的信号 |

分钟：regime 仍是 **日频**。T 当天 09:30 到 15:00 的分钟线不许更新「今天用的标签」。标签在昨天收盘已经封死。这和分钟书仍按 14:55 成交不矛盾：成交钟是执行，标签是昨日状态。

强平若裁成「次日开盘卖」（P10 草案），信息集在开盘前已经齐。这是领先指标的成交，不是盘中追出来的信号。

---

## 6. 与 `--index-ma5-gate`、`--buy-state-file` 的边界

| | `--buy-state-file` | `--index-ma5-gate` | bigvalue regime（本计划） |
|---|---|---|---|
| 问题 | 这只票过不过买点 | 上证跌破 MA5 时停新开 | 全市场资金流处于哪一态 |
| 行键 | `(code, trade_date)` | 一根指数 | 一根 `date` |
| 数据 | MyQuant 旁路 close / MA20 / MA60 / `$winratio` | 湖 `index/period=1d` `000001.SH` | #475 parquet |
| 作用 | 只滤新开 | 只滤新开，不卖 | 挡新开；另两旗才强平或改系数 |
| 时序 | 买日查买日行（旁路自己的 asof 在导出端） | 前一交易日收盘 → 次日 | 前一交易日定稿 → 次日 |
| 缺数据 | 该票该日不买 | 窗不够则该日不买 | fail-closed（P7） |
| 默认 | 不传 = 不滤 | 关 | 关 |

三道可以在研究上同时存在，**代码上 P1 未裁前不允许 index 闸和 bigvalue 行为开关一起开**（R12）。`--buy-state-file` 是另一轴，草案允许和 bigvalue 同时开：一个滤票，一个滤市场。它不参与 P1 的三选一。

P1 的三个词，写在这里以免实施时各写各的。**未裁，三选一都还不是决议。**

| 选项 | 含义 |
|---|---|
| **AND** | 两道都开时，新开必须同时过上证闸 **和** bigvalue 挡新开。任一道挡住就不买。强平与金叉倍数仍只看 bigvalue，上证闸继续「不因此强卖」 |
| **独立** | 各管各的。上证闸只挡它的新开；bigvalue 按自己的三旗做事。同一天可以「上证允许、bigvalue 强平」 |
| **互斥** | CLI 层只许开其中一道。两道一起出现就退出（比 R12 的「未裁前拒绝」更进一步，裁了之后仍拒绝组合） |

R12 是未裁前的临时拒绝，不是已经选了「互斥」。

上证闸的等号规矩（收盘 = MA5 不挡）只约束上证闸。bigvalue 的等号见 P8，不自动抄成「死叉」。

`--keep-buy-vacancy`：bigvalue 挡住的是 **整天的新开**，没有「换下一只」可走。该日分数补位用不上。ST / 年龄 / 15% 仍是名单轴，和本闸无关；本计划不打开它们（R10，Q8）。

---

## 7. 同日卖出优先级（对齐 Q6）

Q6 已裁，保持：**先止损，再 dropout**。同日一只票只卖一次，reason 走先发生的那一笔。

强平是插在中间的 **拟** 路径，默认关。草案顺序（P12 未裁，未裁前不得编码强平）：

| 顺序 | 谁 | 条件 | reason |
|---|---|---|---|
| 1 | 已有 pending、T+1、跌停延期 | 现引擎 | 原样 |
| 2 | 止损 | 书的 `--stop-pct` / `--stop-fill`。Q6 | `stop_loss:gap_open` / `stop_loss:touch` / `stop_loss:close` |
| 3 | bigvalue 强平 | 旗打开，且 S 为已确认死叉态，且这只仓 T+1 可卖，且第 2 步没卖掉 | 拟 `regime_flat:bigvalue_death` |
| 4 | dropout | 第 2、3 步都没卖 | `topk_drop:bottom` 现前缀 |

同一持仓走到第 2 步卖掉，就不再发强平，也不再发 dropout。走到第 3 步卖掉，就不再发 dropout。禁止两笔卖、禁止两个 reason 叠在同一 lot 上。

强平 **不是** dropout。它不看分数、不看 `n_drop`。它是市场状态把仓清掉。dropout 在强平旗关掉时完全照旧。

和止损的差别：止损是这只票自己的成本。强平是全市场状态，一天要么对所有可卖仓成立，要么都不成立。

T+1：买入日当天的新仓，下一天才能卖。强平碰到卖不掉的 lot，记延期，沿用引擎已有的跌停 / T+1 延期，**不** 新写「强平可以破 T+1」。

跌停：Q7（收盘恰跌停仍按收盘价成交）**只**约束 `--stop-fill close`。强平不借用 Q7。草案走引擎现有的拒单 / defer（P11）。

当日买回：现核 `sold_today` 会让当天卖掉的代码离开当日买单。强平卖掉的代码同一天不买回。这个行为是现成的，不是新规则。**下一个**交易日买不买，看那天的信号日是不是仍是死叉态，以及挡新开旗开没开（§4.1）。

挡新开不产生卖出 reason。它只让 `eligible_buy` / 计划买名单为空，或让整日新开被拒。拟计数：`skip_bigvalue_block`（名字实施时再 pin）。不要记成 `skip_held`。

分钟书的 dropout 卖在扫描到的那根 close 上。强平的成交钟 **不要** 悄悄改成那个钟。成交钟是 P10。在 P10 裁下来之前，没有强平实现。

---

## 8. 实验矩阵

对照锚与 tracker 已裁的尺子对齐，不新开一把尺子：

- 书：`topk_dropout`，50/5。止损默认该开还是 `--stop-pct 0`，各臂 **同一选择**，写进实验记录。本计划不指定改止损。
- 日线价域：qlib `$close` 日线后复权 bin（`--qlib-data-root`，常配 `--qlib-cost`）。Q5。
- pred：`8a061ea4`。窗：`20260106–20260914`。Q9。`c5f4bccd` 仍只是烟测。
- 本金：`--cash-total 100000000`。Q10。CLI 默认 2100 万不拿来对这张表。
- **Q8 仍开**：这些臂 **不** 开 `--st-daily-file` / `--age-map-file` / `--return-threshold-filter`，除非人另下指令。本计划不把它们塞进「顺便」。
- 分钟臂若要跑：价域仍是 `none`，禁止和日线 bin 净值合成一张表当同一把尺子。
- 禁止用 PortAna NAV 宣布哪一臂赢。

臂（全部 opt-in；臂 0 必须是开关全关）：

| 臂 | 挡新开 | 强平 | 金叉倍数 | 信号 | confirm | 上证闸 | 要回答的问题 |
|---|---|---|---|---|---|---|---|
| 0 基线 | 关 | 关 | 关 | — | — | 关 | 与现 master 默认路径一致。R11 的对照 |
| B1 | 开 | 关 | 关 | state | 1 | 关 | 纯状态、不防抖，少开多少 |
| B2 | 开 | 关 | 关 | state | 2 | 关 | 草案防抖。和 B1 比翻动 |
| F | 关 | 开 | 关 | state | 2 | 关 | 只强平、不挡。量「卖了又买」的换手。P2/P10 未裁前 **不跑实盘数据**，只留格子 |
| FB | 开 | 开 | 关 | state | 2 | 关 | 强平且不补。比 F 少一轮回补 |
| G | 关 | 关 | 2 | state | 2 | 关 | 金叉日 `eff=1.0` 相对 0.95 的差额。不是两倍 NAV |
| E | 开 | 关 | 关 | edge | 1 | 关 | 脉冲有多稀。和 B1 比密度。P5 未裁前不跑 |
| I-AND / I-IND / I-EX | 开 | 关 | 关 | state | 2 | 开 | 共存三选一。**P1 未裁前禁止跑**（R12 会拒绝 CLI） |

每臂记录，而不是只留一个净值：

- 被挡住的买入日天数、`skip_bigvalue_block` 次数
- 强平笔数、reason 计数（必须能和 `stop_loss:*`、`topk_drop:*` 分开）
- 金叉日天数、当日 `eff`（应只见 0.95 或 P3 裁下来的那个数）
- 缺日 / 暖机天数。缺日若是整次退出，这一臂没有净值，记录失败原因
- 成交笔数。F 臂若笔数远高于 B2，就是换手，不是「更安全」的自动结论

产物目录沿用现有 `csv_daily_topk_dropout_*` / `csv_minute_topk_dropout_*`，用旗区分。不新造策略名目录来冒充新书。数字不入库 git。

---

## 9. 切点（P\*，全部未裁）

人裁之前，实施 PR 不得把草案列写成已经发生的默认。本表 **不自裁、不关闭**。

| ID | 问题 | 草案（只是草案） | 人裁 |
|---|---|---|---|
| **P1** | 与 `--index-ma5-gate` 共存 | 三选一：AND / 独立 / 互斥。未裁前两旗同开就拒绝（R12）。草案 **不** 预选其中一项 | **未裁** |
| **P2** | 强平进不进第一轮实现 | 旗保留、默认关。第一轮代码可以只有挡新开。强平等 P10、P11、P12 一起裁了再写 | **未裁** |
| **P3** | 金叉倍数相对 `risk_degree=0.95` | `eff = min(1.0, 0.95 * M)`。M=2 → eff=1.0，只释放约 5% 现金。禁止 `cash_deploy_frac > 1`。真·两倍敞口不在本计划 | **未裁** |
| **P4** | `confirm-days` | 草案 2。备选 1（不防抖）或 3 | **未裁** |
| **P5** | 状态 vs 边沿 | 草案 `state`（densest-stable）。备选 `edge` 脉冲，或 `state-and-edge` 用穿越做确认 | **未裁** |
| **P6** | 均线窗 | 草案快 5、慢 10，CLI 可改。3 日不作为研究默认 | **未裁** |
| **P7** | 信号日缺失 | 草案：行为开关已开则 **整次退出**。备选：该日不新开、不强平、不加倍，运行继续，并计数 | **未裁** |
| **P8** | `ma_fast == ma_slow` | 草案：不触发死、也不触发金。等号日打断 confirm 的连续计数。上证闸的「等于不挡」不自动套过来 | **未裁** |
| **P9** | 暖机 / 未满 confirm | 草案：不加倍、不强平。挡新开旗若开着，这些日子不新开。备选：沿用上一次已确认标签（要另写「没有上一次」时的失败） | **未裁** |
| **P10** | 强平成交钟 | 草案：次日开盘（日线下一根日线 open；分钟 09:30 open）。备选：跟书现有卖钟（日线 dropout 收盘 / 分钟扫描那根 close） | **未裁** |
| **P11** | 强平遇跌停 | 草案：引擎现有 defer / 拒单。不套用 Q7 | **未裁** |
| **P12** | 强平插在哪 | 草案：止损之后、dropout 之前。同日一笔。reason `regime_flat:bigvalue_death` | **未裁** |
| **P13** | `topk_score_exit` 看见这些旗 | 草案：拒绝退出。禁止静默忽略，禁止悄悄套上 | **未裁** |
| **P14** | 均线在谁那里算 | 草案：只读 parquet 里的 `ma{fast}` / `ma{slow}` / 需要时的 `cross_*`。缺列失败。回测进程里不第二套 rolling | **未裁** |
| **P15** | 日线与分钟是不是同一刀 | 草案：挡新开两边都接，接线方式跟上证闸。强平的分钟成交钟等 P10。不单独造分钟版指标 | **未裁** |

---

## 10. 验收 / DoD

### 10.1 本 PR（docs-only）

- 只有 `docs/backtest/plan-bigvalue-regime-topk-2026-10-16.md` 与 tracker 的追加。
- tracker：**Q12 仍开 / 待裁**；§12 有 2026-10-16 行；§9 若出现新旗，标成 **拟**，不是 as-built。
- **Q8 仍开**。正文没有把 Q8 改成已裁。
- 正文写明：待 Claude review；**不是 impl GO**。
- UTF-8 无 BOM，无 NUL。
- 不改策略、测试、CI、HELP_LOCK。

### 10.2 将来的实现门（现在不跑，这里只登记）

另一次人裁写明 impl GO 之后才做。本列表不是那次 GO。

| 门 | 内容 |
|---|---|
| 路径 | `verify_no_hardcoded_machine_paths.py` 绿。新代码与 #475 修复后的构建脚本都没有 `E:/stock_data` |
| 帮助锁 | HELP_LOCK 含 §4.5 的旗与「默认关 / 次日 / 剔除表尾 0 / 不是 buy-state」。单测 pin 子串 |
| 默认关 | 不传新旗的既有 `tests/test_topk_dropout_*.py` 与书测试保持绿，不改期望去消 diff |
| 时序 | 合成表：T 的决策不读 `date == T`；表尾 0 被剔除；S 缺失时按 **当时已裁的 P7** 失败 |
| 状态 | 手算 5×10：死叉态、金叉态、等号、暖机 NaN 四行与 §3.2 一致。`cross_*` 只在 P5 裁了 edge 之后才 pin |
| confirm | §4.2 那张四行表 |
| 优先级 | 合成一日：止损与死叉态同时成立 → reason 为止损，没有第二笔。只强平时 reason 为 `regime_flat:bigvalue_death`，同日不再 `topk_drop`。买入当日的仓不被强平 |
| 倍数 | 传 M=2 且金叉态：eff=1.0，且调用引擎的 frac ≤ 1。死叉态 frac 仍 0.95。关旗时期望与现在一致 |
| 组合拒绝 | P1 未裁时，bigvalue 行为开关加上 `--index-ma5-gate` → 非 0 退出 |
| 其它书 | P13 草案方向：`topk_score_exit` 收到旗 → 非 0 退出 |
| 静态 | ruff 对改动的 `.py` 零告警。data-free，不读 F 湖、不读 `E:/stock_data` |

实现落点（登记，本 PR 不建文件）：

| 处 | 将来 |
|---|---|
| 旗 | `backtest/research/csv_strategy_books.py` `add_topk_dropout_args` |
| 帮助锁 | `backtest/research/strategy_topk_dropout_rules.py` 原地改 `HELP_LOCK`。不复制文件 |
| 加载 / 标签 | 新的小模块，或 `topk_dropout_eligibility.py` 旁。挡新开走与 `index_ma5_gate` 同类的 eligibility，不塞进成交核公式 |
| 强平 | 书侧或日线卖出环上的 **可选** 钩子。默认不设置。禁止改无旗时的止损 / dropout 顺序 |
| 测试 | `tests/test_bigvalue_regime.py`，data-free |
| 构建 | #475 的脚本。path 修复可以是 #475 上的后续提交，不必塞进策略 PR |

---

## 11. 行业惯例

站位见 [回测规则原则](ssot/backtest-rule-principles-ssot.md)：行业惯例指主流 **回测器** 怎么做研究开关，不是交易所撮合，也不是券商柜台。

**全市场资金流是 risk-on / risk-off，不是选股器。** 指数滤网、波动目标、风险预算，都是用 **一条** 市场序列缩放或开关整个组合的风险。个股 alpha 仍在组合内部排。大单净量一天一个数，没有截面。拿它去改 TopK 排序，是把温度计当成选票。`--buy-state-file` 继续负责选票这一侧。

**领先滤网，次日才生效。** 日频信号在收盘才完整。用收盘算出来的标签去成交 **同一个收盘**，是把还没走完的信息当成已经知道。回测里对应的做法是：标签用 T−1 及更早，T 才允许下单。本仓 pred 的 `pred_minus_one`、上证 `--index-ma5-gate`（`index_ma5_buy_days`：前一根收盘决定下一根买不买）已经是这个时钟。大单净量沿用它。盘中写成 0 的占位行还没收盘，连「领先的昨日」都算不上，所以要丢掉，不能进窗口。

**默认关，用 A/B 说话。** 已发布的 50/5 路径是对照臂。新滤网默认关，开着才是实验臂。两臂同窗、同 pred、同本金、同价域（§8）。关旗跑出不一样的成交，就是回归失败，不是「顺手优化」。原则页也要求：会改变结果的规则用新的 opt-in 基线，旧基线不覆盖。

**状态机优于脉冲。** 穿越日是事件研究的样本点，一年没几个，回答「穿越之后几天的冲击」。持仓问的是「这些天是不是一直处在风险关的那一侧」。后者每个定稿日都要有标签，所以用 `ma5 ? ma10` 的连续状态。`confirm-days` 是状态机上的滞回，避免贴线来回翻，不是再把状态变回脉冲。`cross_*` 留作可选确认。密度更高、标签更稳的那一个当默认，就是 densest-stable。

**强平比挡新开狠得多，所以默认关。** 挡新开让已经持有的 alpha 仓自己走完止损和 dropout，只是不再加风险。强平是主动把风险砍掉：冲击成本、费用、跌停卖不掉、T+1 残留都出来了。只强平、不挡新开时，状态若停在死叉，书还会把仓买回来，换手叠上去。行业上的 de-gross 通常连「不许加回」一起做；在人没裁 P2 之前，这个更狠的旗保持关闭，矩阵里单独成臂，不写进默认。

金叉「加倍」在多头现金账户里，行业上是把目标仓位从留有现金缓冲抬到接近满仓，区间仍在 0 和 1 之间。本仓缓冲就是 `risk_degree=0.95`。把它抬到 1.0 是小一档的风险开。把它说成两倍净值，越过了没有保证金模型的回测账户。P3 把这句话留在未裁。

---

## 12. 对 #475 的依赖，以及 path-SSOT

### 12.1 依赖什么

| 项 | 值 |
|---|---|
| PR | https://github.com/baiyibing/MyQuant-backtrader/pull/475 |
| 分支 | `feat/bigdata-ma-cross` |
| 头 | `659c796c8b6bda25da2c97dc633a178351434550`（查计划时的 PR 头，合并时以 GitHub 为准） |
| 文件 | `scripts/data/bigdata_ma_cross.py` |
| 提供 | CSV → parquet；`ma{w}`；`cross_{f}_{s}`；默认剔除表尾 0；重复日 / 空表失败；可重跑 |

本计划的加载器假定这些列和「表尾 0」的定义还在。#475 若改列名或改成 `min_periods < window`，先改 §3 再写消费端。

#475 **未合并**。本计划不把它视为已经在 master 的 API。

### 12.2 CI 为什么是红的

GitHub Actions `python-tests` / job `pytest-and-gates` / run [`38876229084`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/38876229084)：

```text
python scripts/gates/verify_no_hardcoded_machine_paths.py
ERROR: hardcoded machine paths in executable code:
  scripts/data/bigdata_ma_cross.py:24: DEFAULT_CSV = Path("E:/stock_data/bigdata.csv")
```

这正是 `verify_no_hardcoded_machine_paths.py` 要拦的数据容器盘符（该 gate 的说明写明 `E:/stock_data`、`F:/stock_data` 应走 resolver）。gate 不扫 docstring 和 `#` 注释；**这一行默认参数是可执行代码**，所以被扫到。

### 12.3 实施前必须先满足的路径修复

落在 #475 那条分支上即可，不必和策略开关挤在同一个 PR。未满足则 §10.2 的实现 PR 不得开、不得合。

1. 删除 `DEFAULT_CSV = Path("E:/stock_data/bigdata.csv")`。`--csv` 改为必填，或只接受调用者传入的完整路径。
2. 源码中不出现 `E:/stock_data`、`F:/stock_data`，也不要为了「本机方便」探测 E: 或 F:。
3. 没给路径就非 0 退出，说明缺的是参数。不要写空 parquet 冒充成功。
4. 本地与 CI 都跑过 `python scripts/gates/verify_no_hardcoded_machine_paths.py`，结果是 OK。
5. 回测侧 `--bigvalue-regime-file` 同样无默认盘符（R9）。构建脚本修了、回测又写死一个 `E:`，仍算没过。

修复之前，#475 可以继续当作 **列契约的草稿** 被本文引用。它不能当作 CI 绿的依赖，也不能被策略 PR `import` 进默认路径。

---

## 13. 修订

| 版本 | 日期 | 内容 |
|---|---|---|
| v0.1 | 2026-10-16 | 首稿。docs-only。P1–P15 全部未裁。Q12 打开。Q8 保持打开。无 impl GO。 |
