# 交接 · 研究成交时钟显式化（Codex 接手）

> 日期：2026-09-19。
> 状态：✅ **已人裁 GO（2026-09-19 · P1–P4 = A/A/A/A @ `746dbccd7f14a8c862f8bd6db407294ddca01732`）**；plan v0.6。用户原话「同意你的建议」= 采纳 r4 共识建议。可以按切片 A→B→C 实施；尚未实施。
> 权威 plan：[plan-industry-align-refactor-2026-09-18.md](plan-industry-align-refactor-2026-09-18.md)；评审依据：[r4 merge-consensus.md](../architecture/reviews/2026-09-18/plan-industry-align-refactor-2026-09-18-r4/merge-consensus.md)。
> **IMPLEMENTATION_BASE=c44da87b01ebcc6a68633307eba0fce48940f403**（2026-09-19 已 fetch 核对的 origin/master tip，commit 对象存在）。
> 实施分支：`feat/industry-align-refactor`；当前 `docs/industry-align-refactor-2026-09-18` 仅提交文档。
> **GO 不等于交易所撮合已建模**；`closing_call` 仅为当前扫描窗口标签，不表示集合竞价已建模或已正确。

## ⛔ 开工闸

**两闸已过（2026-09-19）**：人裁 GO（P1–P4=A/A/A/A）+ 上述 base commit 对象存在。未覆盖语义、行为漂移或冻结面需要变更 → **STOP 问人**，先新增 P* / 修订 plan，不自裁。

本 handoff **不含 Opus 实施前审核闸**：本 plan 已过四轮多模评审且无新红；若宿主后补 Opus 审核，有 🔴 再停，回写并解决后继续。

## 0. 硬边界

- 行为零变化：成交价、股数、reason 值及计数、NAV、summary 快照不变；不加 `trades.csv` 的 `session_phase` / `price_rule` 列。
- 不改扫描器、读取器、模拟环和既有取价；不把 phase 标签当过滤器或成交许可。15:00 触价资格与收盘标记分开，本轮两者都不改。
- 旧后置项与 v7 分叉继续后置；不把六个具名价格规则当全量选价器，不宣称覆盖 v7。plan F-R1–F-R14 全部继承。
- 冻结清单直接共用 **plan §7「A–C 共用冻结 diff 清单」**，不在此另造清单。围栏测试仅有 plan 规定的窄例外；`SIMULATE_HOT_PATH` 与 #108 字节一致，不扩大扫描范围。
- 禁止假 SHA、不可达对象、用 `git merge-base HEAD origin/master` 现算 base。先 `git cat-file -e "$IMPLEMENTATION_BASE^{commit}"`，再 `git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD`；后者仅作祖先校验。
- 依 plan §7 / §9，冻结生产文件直接两段式 diff `"$IMPLEMENTATION_BASE" HEAD`，同时检查相对 HEAD 的未暂存和已暂存 diff；禁止三点 diff 或自动前移 base。需 rebase 时 STOP，重核事实锚并记录新完整 base。
- 实施验证全部 data-free，不读湖、不跑真实回测；UTF-8 无 BOM，Markdown / Python 文件 NUL=0。

## 1. 切片 A · 纯叶子 fill clock

落点：`backtest/research/ashare_fill_clock.py`，唯一新增生产文件。按 plan §7.1 建立 `SessionPhase`、`session_phase(hm)`、六值 `FillPriceRule` 与 `POOL_FILE_DAY_RULE`；只允许标准库及从 `ashare_bars` 只读导入四个既有会话边界，禁止本地重定义。仅新增标签分界 `CLOSING_CALL_OPEN = 14 * 60 + 57`。

**DoD**：连续窗口返回 `continuous`，14:57–15:00（含端点）返回 `closing_call`；午休、盘外和开盘集合竞价分钟直接调用抛 `ValueError`。AST allowlist 及边界真源检查通过；没有调度、填单或状态修改 API；不接生产调用。切片 B 的 pytest 反向围栏必须拒绝热路径 import 新叶子，`rg` 只作补充。共用冻结面无 diff。

## 2. 切片 B · data-free 契约与黄项落点

落点：新建 `tests/test_ashare_fill_clock.py`；窄改 `tests/test_ashare_simulate_import_fence.py` 的 `forbidden_imports` 及对应断言。完整测试名和机械断言以 plan §7.2 表为准：会话边界、池买日线 / 分钟及缺 14:55 fallback、追买首日报价 / 缺报价延期、六个具名价格规则、正向与反向 import 围栏全部覆盖。

**DoD**：表内测试全绿；合成结果等于现有六规则语义，不改旧断言或 snapshot。`SIMULATE_HOT_PATH` 元组与 `test_hot_path_list_matches_plan_bytes` 的 #108 约束字节不动；不改生产 API；共用冻结面无 diff。

**r4 黄项（不挡开工，实施本片时落实）**：

- 追买夹具钉 `csv_ledger.chase_decision` / `csv_simulate_loop.run_chase_due_day` 与缺报价观察口：复用现有接口，通过测试侧 quotes 回调 / 状态观察证明 `quoted is None` 后当日 `pending_chase` 仍保留，不为测试改生产 API。夹具明确未持仓、指数门放行，联合日历保留 T+1；T+2 有报价且重评可买才成交，日线 close / 分钟 09:45 close（或既有 fallback），reason 仍为 `chase:T+1`。禁止删除整个 T+1 session 冒充缺报价延期。
- plan §9 与 CI 有小差：实施验证对齐 `.github/workflows/python-tests.yml`，四项 data-free gates 在安装依赖前；安装后明确验证 numba 可导入，parity 不得静默 skip；定向与全量 pytest 均排除 `production` / `benchmark`。保留 Linux 主合同，本次不改 plan §9 或 CI 文件、不执行命令。
- 湖 14:57 bar 探针仅 P1=B/C 才需要；本轮 P1=A，只用 data-free 合成夹具，不读湖。
- 枚举名与冻结表闭合按 plan §7 固定值 / 共用表落实；其余评审黄项只补测试说明，不扩大生产改动；越出 plan 即 STOP。

## 3. 切片 C · as-built 文档回写

落点：仅 `docs/backtest/engine-ashare-correctness.md`；按 plan §7.3 **重写基线第 36–37 行旧句**，不得只追加短表而保留旧摘要。替换为 F-R6 的四类日线具名规则：日线 `stop_loss:gap_open` = 触发当日 open；`daily_stop_touch_at_trigger` = 触发当日 trigger；命中 `daily_same_bar_prefixes` 且通过涨跌停门才按当日 close；只有确实写入 `pending_exit` 的 reason 才下一可卖日 open。

**DoD**：该 commit 只改此文档，模块表新增 `ashare_fill_clock.py`；短表若保留，六个枚举值与切片 B 逐字一致，注明「当前扫描窗口标签 / 非全量 / 不含 v7」。读取器、内核、双账本、E-R1–E-R6 与价格数字未变；不改 README / AGENTS / 旧 plan / HELP_LOCK，不加计数器或产物接线；共用冻结面无 diff。

## 4. 启动（未来实施会话；本次只记录）

从固定 `IMPLEMENTATION_BASE` 开 `feat/industry-align-refactor`，不用浮动 master 代替。先将本 docs 提交中的权威 plan 与 handoff 提供给实施会话（可用独立 docs 工作树的绝对路径），不把 docs 分支合入实施分支来改变 base。以下命令仅供实施会话执行：

```bash
IMPLEMENTATION_BASE=c44da87b01ebcc6a68633307eba0fce48940f403
git cat-file -e "$IMPLEMENTATION_BASE^{commit}"
git switch -c feat/industry-align-refactor "$IMPLEMENTATION_BASE"
git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD
# 先按下文模型规则设置 CODEX_IMPL_MODEL 为账号实际可用模型名。
codex exec --dangerously-bypass-approvals-and-sandbox \
  -m "$CODEX_IMPL_MODEL" \
  "按已提供的 industry-align plan v0.6 与实施 handoff 执行切片 A→B→C，分 commit；行为零变化；遇 STOP 问人，不自裁。"
```

模型：**账号最高 codex-max，若无则最高编码档并写明实际名**；开工记录与最终报告均写实际模型名，不把模板名当实际运行记录。

切片 A→B→C 各自提交；实施验收依 plan §9 和本 handoff 切片 B 的 CI 小差说明。任一冻结 diff、行为变化或未覆盖语义触发 STOP，问人后再继续。

## 5. 完成标记

- [x] 2026-09-19 人裁 GO：P1–P4=A/A/A/A。
- [x] IMPLEMENTATION_BASE 与 origin/master tip 一致，commit 对象存在。
- [ ] A · 纯叶子 fill clock。
- [ ] B · data-free 契约与围栏。
- [ ] C · as-built 旧句重写。

本次仅回写 GO 与交接文档，以上实施项尚未执行。
