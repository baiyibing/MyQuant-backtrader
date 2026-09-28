# S2-D：TopK topk_minute_exec 边界冻结（2026-09-28）

Human GO：**「批 D」**。基线 `290c4dffd56cd6088ac00d1b2e079f4d98b1e603`（`290c4df`，master after #240）。本批仅文档 / module docstring 澄清，无逻辑、签名或 HELP_LOCK 字符串变化；**勿合，等待 Human「合」**。

## 模块职责与调用边界

[`topk_minute_exec.py`](../../backtest/research/topk_minute_exec.py) **已经拥有 TopK 买侧执行合同**，本批核查未发现值得抽取的同合同重复调用实现，因此只冻结现有边界：

- `validate_topk_exec` / `parse_topk_exec`：校验执行模式及现有策略 / walkdown / limit-rule 组合；共享入口的 CLI、`run`、`simulate` 已复用该校验。多层校验是入口防线，不是另建共享成交 helper 的理由。
- `TOPK_EXEC_HELP_LOCK`、`CLOSE_BUY_HM` / `CLOSE_FALLBACK_START`、`VWAP_SLICE_CLOCKS`：持有既有帮助合同和买侧时钟常量；本批不改字符串或常量值。
- `TopkMinuteBuys`：按原 planned 席位 / 分母冻结预算，承担已有非 close 或 walkdown 买侧分派、原票重试、整份额度移交及六片事件记录；实际买入仍委托 `run_pool_buys_day` / 原账本。
- `write_topk_exec_audit`：写既有 opt-in `topk_execution.json`；不接管通用产物、卖出审计或 manifest writer。

[`csv_minute_backtest.py`](../../backtest/research/csv_minute_backtest.py) 负责入口接线、有效调度选择、`real` 的本次运行 hook 与审计落盘条件；[`minute_cash_order.run_chronological_day`](../../backtest/research/minute_cash_order.py) 在原分钟 / open-close 相位推进买侧 dispatcher。**默认 close + walkdown OFF 不构造 `TopkMinuteBuys`**，14:55 买价及缺根回退仍走调用方已有 `_buy_px` / 池买路径。本模块记录该合同，不表示所有 close 买入都已搬到本模块。

**卖出规则仍在 book / simulate 路径**，卖出扫描、止损 / dropout 谓词、持仓 / 现金 / 费用记账不由本模块接管。`real` 的既有限价参考适用于本次运行的买卖门，不能将“买侧模块”误读成 real 只影响买入；卖出策略规则与时钟不因此重写。边界沿用 [P4](topk-exec-p4-2026-09-27.md) 与 [S2-C](s2c-x02-cash-order-boundary-2026-09-28.md)。

## 既有合同与默认锁

默认 **`--topk-exec close`（省略 ≡ 显式 close）、walkdown OFF、`--topk-limit-rule qlib`** 保持。默认 close 取 14:55 close，缺该根才取 [14:30,14:55] 最后 close，空窗不买；qlib 0.095 浮点带与 close 的旧 epsilon 保持。默认产物不新增 TopK 字段，也不重录 [master-close golden](../../tests/fixtures/topk_exec_master_close/README.md)。默认与比较资格统一见 [成交假设 SSOT T0–T4 / §4](minute-fill-policy-ssot.md)，本页不另建成交假设总表。

`open` / `intraday` / `vwap`、`--limit-walkdown`、`--topk-limit-rule real` 均仅限 **topk_dropout opt-in**；`topk_score_exit` 拒绝这些非默认组合，`vwap × walkdown` 继续硬拒绝。open 只用精确 09:30 open，缺根不借后行；intraday 在 session 内用首次符合上限条件的 open，walkdown OFF 时涨停只重试原票，其他失败按既有规则终止。walkdown ON 在首次涨停阻拦时移交原席位整份额度，不重分预算、不让原票当日复活；细节分别沿用 [P1](topk-exec-p1-2026-09-27.md) / [P3](topk-exec-p3-2026-09-27.md)。

名为 **vwap** 的 [P2](topk-exec-p2-2026-09-27.md) 是等名义预算的 **TWAP-style 固定时钟分片**：`VWAP_SLICE_CLOCKS` 为 09:35、10:30、11:30、13:00、14:00、14:55，各片取精确 bar **open**、预算 q/6，缺根不借、余款不滚。它不是成交量 VWAP，不按 amount/volume 取价，也不是 [X-04 尾盘首买](x04-tail-window-buy-2026-09-26.md)；不能因命名相似合并分片 helper 或混排收益。

三个 `close` 必须分开：TopK `--topk-exec close` 是 **买侧 14:55 分钟 close**；`--minute-stop-trigger close` 是 **分钟止损触发域**；日线 `--stop-fill close` 是 **日线 EOD 止损**，共享分钟明确拒绝后者。H/L 的小 helper / 扫描分工仍见 [S2-B](s2b-hl-helper-boundary-2026-09-28.md)，本批不搬卖出循环。

通过现有校验的 **非 close 或 walkdown 自动进入 chronological cash-order**，无需另开 X-02；`close + walkdown OFF` 不自动切换，单独 real 也不切换。同 hm open 卖款可供随后 open 买，close 卖款不能倒供该 hm open 买；close + walkdown 在 14:55 close 买调度冻结预算，沿用该相位卖先买后。原始 flag 与实际生效调度须分开记录，不能用 CLI X-02 OFF 推断 legacy。调度职责与相位合同见 [SSOT X2](minute-fill-policy-ssot.md)、[S2-C](s2c-x02-cash-order-boundary-2026-09-28.md) 和 [X-02](x02-minute-cash-order-2026-09-25.md)，本批不重写 buy dispatch。

独立 APP 入口 [`csv_minute_backtest_topk_app_dropout.py`](../../backtest/research/csv_minute_backtest_topk_app_dropout.py) **不通过其 CLI 暴露 `--topk-exec` / `--limit-walkdown` / `--topk-limit-rule`**。它的 `--topk` 是名单参数，不是共享 TopK 买侧执行 selector；本批不扩 APP 接线。

## 既有买侧审计

非默认 exec / walkdown / real 才由共享入口写 `topk_execution.json`。字段沿用 P1–P4，无新增 schema：

- 顶层 `topk_exec`、`topk_limit_rule`、`limit_retry_fills` / `limit_retry_expired`、`events`；walkdown ON 才增加 `limit_walkdown`、`walkdown_fills` / `walkdown_exhausted`。retry 计数仍表示 walkdown OFF 的 intraday 原票重试，walkdown 计数表示候补成交 / 耗尽。
- 席位事件沿用 `date`、`code`、`seat`、`original_code`、`selection_hm` / `decision_hm` / `quote_hm` / `execution_hm`、`quota`、`allocation_cash`、`denominator`、`reason`、`price`、`phase`；walkdown 记录 `substitute_code`，报价钟与决策 / 成交钟不混同。
- vwap 的逐片事件增加 `slice_index`、`slice_hm`、`slice_budget`；15:00 席位汇总不含 `slice_budget`，不重复计预算。缺报价及未成交字段的既有空值含义沿用 P2。

**仅 real + close + walkdown OFF 仍写规则审计，但 `events` 为空**；它没有借 P4 构造买侧 dispatcher。启用 manifest 时既有配置 hash / `run-metadata.json` 保留规则身份。默认 close / qlib / OFF 不新增审计字段，HELP_LOCK 字符串逐字节保持。

## 审批门与本批验收

成交假设基础设施计划的 **S0 / S1 / S2 是审批门**：S0 为 #238 已入仓的 SSOT；S1 只读目录仍需独立 GO；S2 为逐边界 / helper 单独 GO。[S2-B #239](s2b-hl-helper-boundary-2026-09-28.md) 与 [S2-C #240](s2c-x02-cash-order-boundary-2026-09-28.md) 已在本基线，本次 **「批 D」只授权 S2-D 边界文档化**，不授权 S1 catalog、S2-E 或统一分钟成交引擎。

历史 TopK **P1–P4 是实现切片**：P1 close/open/intraday，P2 六片 vwap，P3 walkdown，P4 real 限价接线。它们已实现，不等于计划 S0/S1/S2 的新授权；旧 P1/P2/P3 文档中的“尚未实现”按各自历史切片理解，当前合同联合查 P1–P4 与 SSOT，不由本批重开实现。

本批仅新增本页、加强 SSOT T0–T4 / §4 指针、扩写 `topk_minute_exec.py` 的 **module docstring**。验收核对三文件 allowlist、移除 module docstring 后源码逐字节 / AST 一致、HELP_LOCK 原文一致、链接有效与 UTF-8 无 BOM / NUL=0；相关无湖测试及检查结果记外部回执。不抽取 mega helper、不改逻辑 / 默认 / 卖出规则，不读写湖、不提供新 NAV、不合并。
