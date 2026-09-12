# Plan：Qlib 训练厂 R3（processors + filter_pipe；不做 M5）

> **落盘**：2026-09-12。
> **状态**：📄 **v1.0 · 人裁「R3 / M5 另开一轮」→ 本轮只做 R3**。本 PR 合入即授权按切片实施。
> **风险档**：**L1**（MyQuant handler / 训练入口接线；不重训作合入门、不重写引擎、不做名单归因）。
> **范围**：实施几乎全在 **MyQuant**。本仓只存 plan 与入口链。1.3 只读。
> **上游走查**：MyQuant `my_docs/qlib_backtest_walkthrough_results.md` §1.1、§1.2、§1.3、§2。
> **前序**：R2/R5 已合（本仓 [#24](https://github.com/baiyibing/MyQuant-backtrader/pull/24)，MyQuant [#2](https://github.com/baiyibing/MyQuant/pull/2)）。`--asof=pred_minus_one` 已锁，**不再重开**走查里的 pred/成交日项。
> **为何不是 M5**：M5 要「严格导出的 Qlib 名单 vs 手工名单」同一 6/8 书对照。本仓 `stock_pool/` 已覆盖 2026-03 窗，对照名单有了；但现成 `预测结果.csv` 来自 **processors 可能没进父类、生产 handler 未接 filter** 的工厂。先修厂再重导，下一轮才做 M5。禁止用 R0 `exports/r0_*` 或当前脏 pred 当 M5。

---

## 0. 一句话

走查还剩两处 Critical 没修：处理器没传进 `DataHandlerLP`，过滤器没接到股票池。本轮只把这两处接到训练入口，外加一句基准名实相符。不重开成交核，不把 Qlib `PortAnaRecord` 当产品。

```text
data_handler_config.infer/learn_processors
        ↓  super().__init__(..., infer_processors=, learn_processors=)
DataHandlerLP 真正建链路

exclude_filter + UnifiedLimitUpFilter($zhangting)
        ↓  D.instruments(market="all", filter_pipe=[...])
handler["instruments"] = 该对象     ← 不要在 handler 字典上挂死 filter_pipe 键
```

---

## 1. 现状（禁止重做已落地项）

| 已落地 | 不要重开 |
|--------|----------|
| 文件名 = 买入日 T；`file[T]=TopN(pred[prev(T)])` | Q2-R2；`my_docs/pred_asof_r2_2026-09-12.md` |
| `export_daily_pool.py` + 本仓 version6 消费 | MyQuant #2 / 本仓 #24 |
| 成交核 E-R1–E-R4、名称 as-of、volume==0 | 本仓 #18 / #21 |

代码仍与走查一致：

1. `Alpha158CostKDJ.__init__` 把 `infer_processors` / `learn_processors` 收成实例字段后 `super().__init__(*args, **kwargs)`，**父类收不到**（显式参数不会进 `kwargs`）。`my_scripts/custom_handler.py` 约 L99–111。
2. 生产 `data_handler_config` 的 `filter_pipe` 被注释；`instruments: "all"`。旁边建了 `handler_no_limit_filter`（只挂 `exclude_filter`），`verify_limit_up_filter(...)` 整段注释。`dynamic_filter`（五日跌超 10%）被构造但从未入管。
3. 走查建议「在 handler 字典上恢复 `filter_pipe`」**与 Qlib 用法不符**。本仓旧脚本与 `qlib_scripts/custom_train_backtest.py` 的活路径是 `D.instruments(..., filter_pipe=...)`，再把返回值赋给 `instruments`。handler 顶层 `filter_pipe` 键加了也不会进 `D.instruments`。
4. `benchmark = "SH601727"` 注释却写「沪深300」。601727 是上海电气。Qlib 相对指标会偏，但本轮仍不把 PortAna 净值当完成定义。

`verify_limit_up_filter` 要 `LIMIT_STATUS`（`include_lz=True` + `$zhangting`），并对 train/valid/test 做 `handler.fetch`。现脚本在生产路径上无条件 `handler_init` 两次，每次走查约 900s。不得把第二次 handler 变成默认必跑。

---

## 2. 非目标 / 禁改

| 不做 | 原因 |
|------|------|
| M5 名单归因（pred TopN vs `stock_pool/` vs R0） | 工厂未修；R0 不是严格信号 |
| 改走查 pred/成交日；改 `--asof` 默认 | R2 已锁 |
| 把 `dynamic_filter` 塞进 `filter_pipe` | 本轮只接走查点名的 exclude + 涨停 |
| 改 `exclude_stocks` 名单内容 | 只接线，不扩宇宙政策 |
| 涨停改用 `$close` × 0.095 价格模式当默认 | 创/科/北交不是 9.5%；本仓板是 10/20/30 |
| 改 Qlib `limit_threshold` / `forbid_all_trade_at_limit` | 走查 §3 口径统一，下轮；且 PortAna 不是产品 |
| 改 Alpha158 标签公式 / COST·KDJ 特征式 | 不是 R3 |
| 重写本仓 `csv_daily` / 卖点 / `presets.py` / 策略 7 | 工厂轮 |
| 用 PortAna / Cerebro 净值验收；把 qlib 加进本仓 | 第四套引擎禁令 |
| 合入门 = 全量重训 + 重导 R5 | handler_init 太重；重训是合入后本机跟跑 |
| 改 `docs/architecture/reviews/**` | 考古 |

---

## 3. 现锁（Q3-R*）

| ID | 锁 |
|----|----|
| **Q3-R1** | 本轮只修 MyQuant 训练厂：processors 传入父类、股票池 `filter_pipe` 接到 `D.instruments`、基准名实相符。禁止 M5。禁止改本仓成交核。禁止把 PortAna 当产品或验收。 |
| **Q3-R2** | `Alpha158CostKDJ.__init__` 必须 `super().__init__(*args, infer_processors=infer_processors, learn_processors=learn_processors, **kwargs)`。禁止只 `self.infer_processors = ...` 然后空 `super`。调用方传入的 list 覆盖类默认 `_DEFAULT_*`。单测用 monkeypatch 截获 `Alpha158.__init__` 的 kwargs，不断真实 qlib 数据。 |
| **Q3-R3** | 生产入口：`instruments = D.instruments(market="all", start_time=..., end_time=..., filter_pipe=[exclude_filter, limit_up_filter])`，写入 `data_handler_config["instruments"]`。禁止 `instruments: "all"` 同时在 handler 字典挂 `filter_pipe`（死键）。`exclude_stocks` / `NameDFilter` 正则保持原列表。本轮不接入 `dynamic_filter`。 |
| **Q3-R4** | `UnifiedLimitUpFilter(use_field="$zhangting", keep=False)`。缺 `$zhangting` 时 verify 失败并带字段名，禁止暗降到 0.095 价格模式。`verify_limit_up_filter` 仅 `--verify-filters`（或等价环境变量）才跑；默认 **不要** 建 `handler_no_limit_filter`。CI 只测过滤器表达式与 `build_*instruments*` 辅助函数，不 `fetch` 全市场。 |
| **Q3-R5** | pred 日 → 买入日 T 维持 `pred_minus_one`。不改 `export_daily_pool.py` 默认。不把 pred vs `report_normal_1day` 对齐写成完成定义。 |
| **Q3-R6** | `benchmark = "SH000300"`，注释改为沪深300 / CSI300。不据此验收 IR。 |
| **Q3-R7** | 单测住 MyQuant `my_tests/`，解释器用该仓 qlib 环境。禁止把 qlib 写进本仓 `requirements.txt`。禁止合入门全量 `custom_train_backtest.py`。 |
| **Q3-R8** | 合入后本机才重训 → `预测结果.csv` → 已有 R2 导出 → 需要时再跑 version6。旧 pred / 旧 `exports/r2_*` 标为 pre-R3，**不得**当 M5 输入。产物不入库。 |

---

## 4. 切片（本 PR 合入后 Codex 做）

实施分支：**MyQuant** `feat/qlib-train-r3`（从该仓当前 master / #2 之后）。不要在本 docs 分支改 MyQuant 业务代码。本仓无需实施分支（E 已随本 PR）。

| 切片 | 仓 | 做什么 | 完成定义 |
|------|----|--------|----------|
| **A · processors** | MyQuant | `super().__init__` 传入 infer/learn | monkeypatch 单测：传入的 processors 出现在父类 kwargs |
| **B · instruments** | MyQuant | `D.instruments` + 两过滤器；删死键；默认不建第二 handler | 辅助函数单测：`filter_pipe` 长度为 2，顺序 exclude → limit_up；生产 config 的 `instruments` 不是裸 `"all"` |
| **C · verify 可选** | MyQuant | `--verify-filters` 才跑 `verify_limit_up_filter`；`UnifiedLimitUpFilter` 规则单测 | 默认 CLI 不 fetch 对照 handler；`$zhangting==0` 规则锁住；缺字段文案含 `$zhangting` |
| **D · benchmark** | MyQuant | `SH000300` + 注释 | 名实一致；不跑 PortAna |
| **E · 本仓索引** | 本仓 | README / R2/R5 plan 指向本文 | 随本 PR 已做 |

顺序：A → B → C；D 可与 C 并行。A/B 分 commit。禁止把 M5 对照表写进本轮。

MyQuant 验收：

```text
python -m pytest -q my_tests/test_custom_handler_processors.py my_tests/test_train_filter_pipe.py
```

（文件名实施时可合并，但 processors 与 filter 断言必须都在。）

合入后本机跟跑（不是合入门）：

```text
# MyQuant，qlib 环境；确认 --verify-filters 可关
python my_scripts/custom_train_backtest.py
# 新 pred 再走已有 R2 CLI；不要覆盖解读旧 R5 NAV
```

---

## 5. 代码落点

### 5.1 MyQuant

| 文件 | 动作 |
|------|------|
| `my_scripts/custom_handler.py` | A：processors 传入 `super` |
| `my_scripts/custom_train_backtest.py` | B/C/D：`D.instruments`；默认单 handler；`--verify-filters`；`SH000300` |
| `my_scripts/custom_filter.py` | 原则上不改公式；C 只加单测能 import 的规则断言 |
| `my_tests/test_*.py` | **新建** A/B/C |
| `my_docs/pred_asof_r2_2026-09-12.md` | 不改锁定值；可加一句「R3 不重开 as-of」 |

禁止改：标签 `get_label_config`、R2 导出默认、`export_daily_pool.py` 映射、Qlib Exchange 费率。

### 5.2 本仓

| 文件 | 动作 |
|------|------|
| 本文 | SSOT |
| `docs/backtest/README.md` | E：SSOT 表一行 |
| `docs/backtest/plan-pool-pipeline-r2r5-2026-09-12.md` | 文首指向本文 |

禁止改：`csv_*.py`、`presets.py`、`docs/architecture/reviews/**`。

---

## 6. 风险 / 已知失真

- 接上 `$zhangting` 过滤后，若 qlib bin 没有该字段，verify 与过滤会失败——这是数据缺口，不要改成 0.095 价格模式蒙混。
- `exclude_stocks` 是手写黑名单，不是 ST 履历库。接线后宇宙会变，旧 pred 不可比。
- 默认不跑 verify 时，过滤器是否「真从 bin 剔行」仍依赖合入后本机跟跑。CI 只锁接线。
- Qlib `forbid_all_trade_at_limit` 与样本过滤仍可能双口径；本轮不收口，且 PortAna 不是下游。
- 现成 R5 真窗 −0.90% 是 pre-R3 工厂，不能当模型或 M5 结论。

---

## 7. 修订程序

改 Q3-R* 须改本文。改 pred 文件名语义须改 [plan-pool-pipeline-r2r5-2026-09-12.md](plan-pool-pipeline-r2r5-2026-09-12.md) 与 [pool-csv-contract.md](pool-csv-contract.md)。M5 另开 plan，输入必须是 **R3 之后** 重训并经 R2 导出的名单。

---

## 8. Codex 工作方式

1. MyQuant 从当前 master（#2 / `aed5c9d` 之后）开 `feat/qlib-train-r3`。本仓不要为 R3 再开业务分支。
2. 按 A → B → C（D 可并行）。每个切片单独 commit。
3. 不要提交 pred、`mlruns/`、`exports/`、timing json、本仓 `backtest_output/`。
4. 文本 UTF-8 无 BOM，写完 NUL=0。
5. 单测用 MyQuant 现有 qlib 环境；不要把 qlib 装进本仓。
6. 不要做 M5，不要改 `--asof`，不要重训当 CI。
