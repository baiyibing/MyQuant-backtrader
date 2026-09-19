<!-- agent=grok cmd-prefix=/home/box/.local/bin/grok -p 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】docs/backtest/plan-industry-align-next-2026-09-19.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `docs/architecture/reviews/2026-09-19/plan-industry-align-next-2026-09-19-r1/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本仓第一方回测是 **向量化 CSV**（日线/分钟）+ path-SSOT 只读行情。Cerebro / Rolling 已全局退场（2026-09-16，PR #58；禁止复活）。无实盘、无 QMT 下载、无 Redis 流。引擎分工见 `docs/backtest/engine-positioning-ssot.md`。把握不准可读代码或做实验，以事实为准。

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

【你的评审侧重】优先**实现 / 协议 / Linux-VM CLI**：核对实现是否可落地、协议/契约用词是否越界、Linux 侧 CLI 与编排是否可 headless 跑通。 --permission-mode bypassPermissions --always-approve <prompt> -->
先读设计稿全文，再按本仓必查盲区对照代码取证。设计稿已读完。接下来核对锚点代码、门禁脚本和其他评审员已完成意见。其他评审员尚未完成，先独立取证：核对锚点、门禁脚本、冻结表与相关契约文档。# 评审：`plan-industry-align-next-2026-09-19.md` v0.2

**侧重**：实现可落地性 / 协议用词 / Linux-VM headless CLI。  
**本轮交叉**：`_parallel/{codex,cursor-auto,cursor-kimi-k3-high,grok}` 仅有 prompt 头、无已完成意见，故独立完成。对照 v0.1 三路勘误：E-01/E-02/E-03/E-05 已闭合；**E-04 只改了 §8 表、未改 §7 可执行 freeze**（本轮 🔴）。  
**实验纪律**：本船无 timeout/budget/并发安全阀设计，不做该类实验。未跑 pytest（`pytest.ini:15` `--basetemp=artifacts/pytest_tmp` 会写盘）。只读核验：四条 `scripts/gates/*` 均 exit 0；`skip_buy_at_limit`/`defer_sell_at_limit` 对 `limits=None` 返回 `False`；`IMPLEMENTATION_BASE` cat-file + ancestor 通过。

---

## 必查盲区

| 项 | 结论 |
|---|---|
| **T+1** | `t1_sellable` 为 `buy_date < session`，买入日 `n_days=0` 不可卖。书侧 eligibility 与卖点 `n_days` 分离。日线 `pending_exit` 次日开属 #112 P4，本船后置正确。未发现用未来 bar。 |
| **复权** | 本船不改成交域。§7 整文件 pytest 会扫到 loader 的 `dividend_type="front"` 单测，不是把 front 套进 1–8 书。 |
| **盈筹** | 正文未引入 `cyqk`。保持。 |
| **涨跌停/停牌** | 主板 10 / 创科 20 / 北交 30 / ST 5 / 未知 `None` 已在 `market_layer` 建模。零量在 loader 丢 K。v7 持仓无 bar 的冻仓未钉。 |
| **包边界** | F-R1/F-R9 正确；未引 LEBS / MockQMT / `presets.py` / Cerebro。 |

---

## 🔴 必须修

### G1｜§8 冻结表与 §7 freeze 命令不一致（E-04 回填未完成）

v0.2 按 host E-04 把 `market_layer.py` / `csv_common.py` / `csv_daily_loader.py` 写入 §8，但 §7 可执行 `git diff` **仍是旧九文件**。实施者按 §7 跑，改这三文件 freeze 仍绿，而它们正是 `limits is None` 与零量冻仓的真源。

```73:84:backtest/research/market_layer.py
def limit_prices(
    code: str, prev_close: float, name: str = ""
) -> Optional[tuple[float, float]]:
    """昨收 × (1±档) 先 Decimal 再 HALF_UP 到分。未知板块返回 None。"""
    pct = limit_pct(code, name)
    if pct is None:
        return None
```

```73:82:backtest/research/csv_common.py
def book_limit_prices(..., *, qlib_limit_pct: Optional[float] = None):
    if qlib_limit_pct is not None:
        return qlib_limit_prices(prev_close, float(qlib_limit_pct))
    return _named_limits(code, prev_close, names)
```

```83:84:backtest/research/csv_daily_loader.py
    if has_volume:
        out = out.loc[out["_volume"] != 0].drop(columns="_volume")
```

§7 现列（`:165-174`）：`ashare_session` / 三日线分钟 v7 / `csv_simulate_loop` / `csv_ledger` / `strategy5_rules` / `ashare_bars` / `ashare_fees`。  
§8 现列（`:196-198`）多出上述三文件。Pass criteria `:180`「no production-file diff」按 §7 无法覆盖 §8。

**回填**：§7 数组与 §8 **同一份**列表（建议 `FROZEN_PRODUCTION_FILES=(...)` 一处定义、两处引用）。另加「base→HEAD 全量 changed-path 只允许 docs + 点名 tests」（v0.1 dissent F5 仍开）。上一船已有工作区门，本船丢掉了：

```319:321:docs/backtest/plan-industry-align-refactor-2026-09-18.md
git diff --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --cached --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
```

CI 是干净 checkout，本地脏树改生产文件时，只比 `BASE..HEAD` 会假绿。

---

## 🟡 应修

### G2｜Slice A 仍不够让程序员直接编码（gate≠fill 可观测性）

DoD 要求钉 v7 held **add** 的 `limits=None` 放行 + post-gate 非成交（F-R4），但没写：**测哪个文件、怎样构造、断言什么**。

现成卖侧 pin 不能当加仓闭环：

```119:134:tests/test_ashare_simulate_predicates.py
def test_none_limits_sell_side_records_existing_split(engine, cause, monkeypatch):
    ...
    if engine == "v7":
        assert [(t["reason"], t["price"]) for t in sells(state)] == [("stop:trial_a090", 89)]
```

加仓路径要 `in_add_window`（14:45–14:55）且 `ladder_decision != none`，规则在未冻结的 `strategy7_rules.py`：

```24:30:backtest/research/strategy7_rules.py
ADD_HM_START = 14 * 60 + 45  # 14:45
ADD_HM_END = 14 * 60 + 55    # 14:55 inclusive
def in_add_window(hm: int) -> bool:
    return ADD_HM_START <= int(hm) <= ADD_HM_END
```

更关键：`_sell_lots` 在 T+1 全锁时 **静默 return 0、不写 event**；`_buy` 现金不足才有 `skip_cash`。只断言「无 sell」分不清 gate 拦截 vs 账本拒绝。

```229:231:backtest/research/csv_minute_backtest_v7.py
    wanted = sum(...)
    if wanted <= 0:
        return 0
```

**回填最小矩阵**（仍 data-free，不改生产）：

| 用例 | 断言 |
|---|---|
| v7 未知板块首次进场 | `skip_unknown_board`，无仓 |
| v7 无昨收首次进场 | `skip_no_prev_close`（`:386-387`），勿与上条合并 |
| v7 held 卖 `limits=None` | 复用现 pin（不是本船新发现） |
| v7 held 加 `limits=None` + 现金不足 | 无 `skip_limit_up`；有 `skip_cash`；stage 不变 |
| v7 held 卖 gate 放行但 T+1 锁 | 无 `defer_limit_down`；shares 不变；**允许无 event** |
| 书侧 `limits=None` | `skip_unknown_board`，仓冻结 |

测试落点写死：`tests/test_ashare_simulate_predicates.py` + `tests/test_csv_minute_backtest_v7.py`（二者已在 §7 pytest 列表）。禁止把新测写进 `tests/test_csv_minute_backtest.py` 却不改 §7。

### G3｜标题含 ST name，§2.1 分叉表仍只有 `limits=None`（v0.1 domain-safety N2 未闭合）

书侧按日 as-of：

```264:291:backtest/research/csv_daily_backtest.py
    st, pending_chase, names_asof = init_sim_state(...)
    ...
        names = names_asof(ds)
```

v7 CLI 窗末平铺：`load_limit_context` → `flatten_pool_names`（`csv_minute_backtest_v7.py:546`，`ashare_session.py:81-85`）。  
§2.3 的 ST 测试是 **5% 带宽**，不是 PIT vs 平铺。Slice B 若只按 §2.1 造矩阵，标题里的 ST fork 仍可被沉默归一。  
**回填**：§2.1 加一行 ST-name fork；Slice B DoD 强制含该行。文案必须写 **as-built ≠ approved**（修复仍留 P3）。

### G4｜chase 在 `limits is None` 之前已 `pop` pending（v0.1 dissent F3）

```140:157:backtest/research/csv_simulate_loop.py
        if quoted is None:
            continue          # 保留 pending
        ...
        pending_chase.pop(code)
        ...
        if limits is None:
            st.stats["skip_unknown_board"] += 1
            continue          # pending 已丢
```

§2.1 写成「unknown board rejected」会让实施者测成「冻结可次日重试」，测试失败后再把 `pop` 挪到门后——这是 **禁止的行为变更**。  
**回填**：分叉表加 pending 生命周期；合成两日用例锁「无报价保留 / 有报价+未知板块丢 pending」。本船不改顺序。

### G5｜书引擎还有第三条门：`qlib_limit_pct` 使未知板块不再 `None`

默认 v6/v8 `qlib_limit_pct is None`，§2.1 的 early reject 成立。topk 书打开该钩子后，`book_limit_prices` **恒返回带宽、永不 `skip_unknown_board`**。`csv_strategy_books.py` 不在冻结表。Slice B 若写「书侧未知板块一律 fail-closed」为假。  
**回填**：fork 矩阵加「默认书 / topk `qlib_limit_pct` / v7」三列；冻结或显式排除 `csv_strategy_books.py` 并说明不把 `qlib_limit_prices` 提升为默认。

### G6｜§7 Linux 编排与 CI 不同构，裸 VM 跑不通

亲验：

- 四条 gates：**全部 exit 0**（无需第三方库）。
- `from backtest.research.csv_common import book_limit_prices` → `ModuleNotFoundError: No module named 'pandas'`。
- `skip_buy_at_limit(11.0, None) is False`；`defer_sell_at_limit(9.0, None) is False`。

CI（`.github/workflows/python-tests.yml:38-56`）顺序是：gates → `pip install -r requirements.txt` → **全量** `pytest -m "not production and not benchmark"`，且 `OSKH_DATA_ROOT=$GITHUB_WORKSPACE`、`PYTHONUTF8=1`。本 §7：无 install、pytest 在 gates 前、只跑 5 个文件、无 `set -euo pipefail`、用 `[[`（必须 bash）。  
上一船定向列表含 `tests/test_csv_minute_backtest.py` 与 `tests/test_ashare_simulate_import_fence.py`（`:283`）；本船丢掉围栏。围栏热路径含 `csv_common` / `market_layer` / `csv_daily_loader`（`tests/test_ashare_simulate_import_fence.py:13-28`），正是 G1 那三文件。

**回填命令骨架**（headless）：

```bash
set -euo pipefail
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8 OSKH_DATA_ROOT="$PWD"
# SHA 三连（已写对）
python3 scripts/gates/verify_oskh_data_contract.py
python3 scripts/gates/verify_data_path_ssot.py
python3 scripts/gates/verify_no_hardcoded_machine_paths.py
python3 scripts/gates/verify_tr_bridge_import_ssot.py
python3 -m pip install -r requirements.txt
python3 -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_session.py \
  tests/test_ashare_simulate_predicates.py \
  tests/test_csv_daily_backtest.py \
  tests/test_csv_minute_backtest.py \
  tests/test_csv_minute_backtest_v7.py \
  tests/test_daily_mark_cache.py \
  tests/test_ashare_simulate_import_fence.py
# freeze：同一数组 + worktree + changed-path allowlist
```

注明：四条 gates 是 path/import 卫生门，**不是** fill-gate 契约证明；契约只在 pytest。Slice C 点名交接路径 `docs/backtest/handoff-industry-align-next-codex-impl-2026-09-19.md`（`workflow-codex-handoff.md` 七步），不要只写「run record」。

### G7｜v7 持仓无分钟 bar 的冻仓未登记

无 records 时只对 **池内**记 `skip_no_1455`（`:315-318`）；已持仓无 bar 则当日不进卖循环，估值靠 `last_prices` 残留（`:413-415`）。与书侧「缺 K = 冻仓 + last_close_mark」不是同一条证明链。零量测试 `:990+` 只覆盖书 loader。  
**回填**：Slice A 一行 as-built pin，或 §2.3 显式「未覆盖、禁止用日线测试外推 v7」。

---

## 🟢 可选

- §9 session-phase 行是 #112 主题，易把 Slice B 理解成继续贴标签。可删，只留「gate pass ≠ fill」类比，并写「不得新建订单对象/事件总线」。
- `strategy7_rules.py` / `csv_pool.py` / `csv_artifacts.py` 纳入冻结或 changed-path 黑名单（产物列、加仓窗口）。
- `python3` vs CI `python`：写清「受控环境解释器；Windows 用 vanna312 别名」。

---

## ✅ 做对的地方（保留）

- 主旨正确：契约化已有 fork，默认零行为；不重开 #108/#112 fill-clock。
- §2.1 书侧 early reject、v7 首次进场 `priced is None`、held 谓词 fail-open，行号属实。本机：`limits=None` 时两谓词均为 `False`。
- F-R4 门过 ≠ 成交，买 `skip_cash` / 卖 T+1 返回 0 锚点属实。
- F-R1/F-R5/F-R6/F-R9 包边界、docs+tests、data-free、禁 Cerebro/qlib PortAna，与 `engine-positioning-ssot.md` 一致。
- E-01 幽灵脚本已换成真实四 gates，本机四条 exit 0，与 `python-tests.yml:38-43` 同构。
- E-02 halt 主锚改到 `:990+`；`:964` 降为 mark-only。正确。
- E-03/E-05 复用卖侧 pin、Slice A 点名 add-side。方向对，深度不够（见 G2）。
- P1–P4 默认 A 与 2026-09-19 既裁一致。§10「Human confirms」应标明是 **再确认既裁 A**，不是新开 B/C 窗口。
- `IMPLEMENTATION_BASE=41f3d11a34c665cc8a21b3e1d351b9e06b0466b5` 等于本机 `origin/master`，对象存在且为 HEAD 祖先。F-R10 禁止 merge-base 现算，正确。
- 未把 OSS 当行为证据。

---

## 人裁建议（P1–P4）

全部 **继续 A**。本船要激进的是 **契约一次钉死**（G1–G6 仍是 docs+tests），不是改 14:57、加 trades 列、或把 v7 fail-open 改成 fail-closed。禁止借「行业惯例」在本船改 fail-open。

---

## 总评

v0.2 已把 v0.1 的幽灵门禁和 halt 锚点修对，方向可实施；但 **§7 可执行 freeze 与 §8 表自相矛盾（G1）**，按现文验收会假绿。补齐 G1（同一冻结列表 + changed-path allowlist + worktree 门）以及 G2/G3/G4/G6 的测试落点与 CI 同构命令后，**可以进人裁 GO → 实现**。按现文 **不可进实现**。
