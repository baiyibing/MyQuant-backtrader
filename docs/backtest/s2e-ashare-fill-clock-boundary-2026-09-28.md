# S2-E：ashare_fill_clock 命名边界冻结（2026-09-28）

Human GO：**「继续S2-E」= 批 E**。基线 `04c5b9ca1cf5349e94956bbcee30446382d90b55`（`04c5b9c`，master after #241）。本批仅 docs / module docstring 边界文档化，无逻辑、签名或默认变化；**勿合，等待 Human「合」**。

## 命名叶子拥有的范围

[`ashare_fill_clock.py`](../../backtest/research/ashare_fill_clock.py) 是 **naming leaf（命名叶子）**，现有职责仅为：

- `SessionPhase` / `session_phase(hm)`：对当前扫描窗口内的分钟标 `continuous` / `closing_call`，窗口外抛 `ValueError`。`CLOSING_CALL_OPEN` 保持 14:57，四个 AM/PM 会话边界仍只读导入自 `ashare_bars`。这是标签分类，不是扫描器、成交过滤器或真实收盘集合竞价撮合。
- `FillPriceRule`：给已有 book-engine 路径命名，非穷尽、不是全量选价器、不覆盖 v7。名称不能反向决定取价、成交资格或费用。
- `POOL_FILE_DAY_RULE`：命名现有文件名日作为决策 / 买入日的约定，不证明信号当时已可得，也不调度池买或追买。

既有标签写入仍由 [`csv_ledger`](../../backtest/research/csv_ledger.py) 等原写入点承担；叶子不写 trades / audit / manifest。未知或不适用标签的既有空值含义保持，不能据标签判定未成交。唯一成交假设总表及默认 / 混比合同仍见 [SSOT §3–§6](minute-fill-policy-ssot.md)，本页不复制第二张表。

## 扫描、成交与调度各归原调用方

- **hl scan/fill**：小校验 / 谓词归 `minute_stop_trigger`，扫描推进归 `csv_minute_backtest.scan_held_day_python` 与 `minute_cash_order.HeldMinuteCursor.advance` / `_close`，成交记账归外围 simulate / 账本。沿用 [S2-B #239](s2b-hl-helper-boundary-2026-09-28.md)，不搬入命名叶子。
- **X-02 cash-order**：共享账户的 chronological 调度及 cursor 边界归 `minute_cash_order` 和原调用方；v7 的调度及买后 timer 留在独立入口。沿用 [S2-C #240](s2c-x02-cash-order-boundary-2026-09-28.md)，标签不决定 open/close 现金顺序。
- **TopK buy dispatch**：既有校验、时钟常量、opt-in dispatcher / audit 归 `topk_minute_exec`，默认 close / walkdown OFF 仍走调用方原池买路径。沿用 [S2-D #241](s2d-topk-exec-boundary-2026-09-28.md)，不向叶子收拢买侧或卖侧规则。
- **JR / Mode B / v7**：JR Mode B 的 M-REF/M-LAG 合同与 replay 留在 [JR 原入口](../../backtest/research/joint_return_replay.py)，不与 [网格 Mode B Q39](../../backtest/research/unified_exit_modeb.py) 合并；[v7 首根 gap / 末根 timer](../../backtest/research/csv_minute_backtest_v7.py) 仍归独立仓位机。命名相似不构成共用成交引擎。

scan / touch / NAV mark 继续分开：`closing_call` 只标窗口，不改变 14:57–15:00 的既有成交资格，也不联动排除 close / mark。现行合同见 [成交核 P1/P2/P4](engine-ashare-correctness.md)。

## 审批门与历史时钟文档

成交假设基础设施计划的 **S0 / S1 / S2 是审批门**（见 [SSOT §7](minute-fill-policy-ssot.md)）：S0 为 #238 的 SSOT；S1 catalog 需独立 GO；S2 逐边界 / helper 单独 GO。本基线已含 S2-B/C/D；本次 **S2-E 只授权命名边界文档化**，不授权真实 fill engine、统一分钟引擎或新 helper 抽取。

历史 [fill-clock plan §5](plan-industry-align-refactor-2026-09-18.md) 的 **P1=A、P2=B、P4=A** 是既有时钟 / schema 裁决：P1 保持扫描窗口与成交资格，P2 仅在原写入点增加标签，P4 保持 touch / mark 两轴独立。历史切片与旧“不接 trades / 热路径全部禁叶子”措辞须连同后续 P2=B 窄例外理解；本次 S2-E 不重开、撤销或扩大这些裁决，也不重开 [JR 时钟重生成](handoff-joint-return-clock-regen-2026-09-24.md)。

## 本批范围与验收

本批仅新增本页、加强 SSOT §4 并加链接、扩写 `ashare_fill_clock.py` 的 **module docstring**。现有 enum / 常量 / 函数及公开签名均不变；不翻默认、不建 S1 catalog、不读写湖、不提供新 NAV、不合并。

[`test_ashare_simulate_import_fence.py`](../../tests/test_ashare_simulate_import_fence.py) 及固定 `SIMULATE_HOT_PATH` **逐字节保持，不扩容、不扩大扫描范围**。固定热路径内只有 `csv_ledger` 可为写入标签导入命名叶子的现行例外保持；扫描器不获 import / 相位过滤权限，本刀不改围栏。

验收核对三文件 allowlist、移除 module docstring 后全部源码逐字节 / AST 一致、SSOT 原表及 S2-B/C/D 内容保持、链接与 UTF-8 无 BOM / NUL=0。仅运行相关既有无湖测试及 data-free gates，结果记外部回执；不新增测试或重录 golden，不把本次文档验证称为真湖 / 收益验证。
