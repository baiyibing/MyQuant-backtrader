# PR #94 统一卖出规则网格 · 模式 B 分钟数据就绪短记（P5 smoke）— Grok 核评审

> 日期：2026-09-17
> 角色：MyQuant-backtrader Grok 核（独立 grok CLI；只审不合入）
> 对象：[PR #94](https://github.com/baiyibing/MyQuant-backtrader/pull/94) `docs/unified-exit-modeb-minute-ready`（tip `256994a` vs `origin/master`）
> 权威：[host-runbook-unified-exit-modeb-smoke-2026-09-17.md](../../../../backtest/host-runbook-unified-exit-modeb-smoke-2026-09-17.md) · [plan-unified-exit-modeb-2026-09-17.md](../../../../backtest/plan-unified-exit-modeb-2026-09-17.md) P5 · 提案 §9.1–9.2 · [PR #93 Grok 复核](../pr-93-unified-exit-modeb-plan/grok-review.md)（`0608e62` **GO-WITH-NITS**，已合）
> HEAD：`256994a216e776838fc1453441f2742676a3730f`
> parent / merge-base：`55bfe4a3cb3219c11baa95d9c314206fad52ecd2`（= `origin/master` = PR #93 merge）
> GitHub：`MERGEABLE` / `CLEAN` / `pytest-and-gates` **SUCCESS**（[run 35195641540](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35195641540)）
> 工作树：`/workspace/MyQuant-backtrader-pr94`（detached @ `256994a`）
> 本核 **未 merge**。本结论 **不是** Mode B 网格完成，也 **不是** 实现 PR 合入门。

---

## 结论

**GO-WITH-NITS**（**docs PR 可合**；nits 不阻断合入，不写 Mode B Python、不改引擎、不跑业务网格。本核不 merge）。

这是合格的 P5 数据就绪回收：相对已合 PR #93 只动 runbook 状态行 + 新短记 41 行，零 Python / 零成交核。smoke 完成表把 Mode B 网格排名钉成 ❌；覆盖率写的是 **2080 distinct 码**（4167 实例去重）∩ cache = 100%，不是「4167 码网格跑完」。cache key 用 `20251013`（`WARMUP_DAYS=10`）而非字面 `20251023`，§2 记了超集关系并把重建/复用留给实现侧拍板。墙钟 27.4s / 28.9s 与 6.6–6.7GB RSS 和 1.75GB parquet / 1.128 亿行对得上。剩余是成本推论里冠军族「~24」与 plan P1 的 18 组不完全同构、以及 `date_to_ymd` 性能票其实已在 #92 落地——不挡合入。

---

## 对象与切片

| 项 | 值 |
|----|----|
| PR | [#94 docs(modeb): minute data ready note - host smoke complete](https://github.com/baiyibing/MyQuant-backtrader/pull/94) |
| 比较 | `55bfe4a..256994a`（2 files, +42 / −1） |
| 前置 | PR #93 **MERGED** @ `55bfe4a`（plan 已人裁 GO：P1=A / P2=A / P3=A；P4/P5 锁） |
| P5 | 本 PR：runbook 状态行 → ✅ 宿主数据就绪已完成；新短记 `unified-exit-modeb-minute-ready-2026-09-17.md` |
| 代码 | **零**。无 `.py` / `.rs` / CI YAML。树内仍无 `unified_exit_modeb.py` / `run_unified_exit_modeb.py` |

`git diff --name-status 55bfe4a..256994a`：

```
M  docs/backtest/host-runbook-unified-exit-modeb-smoke-2026-09-17.md
A  docs/backtest/unified-exit-modeb-minute-ready-2026-09-17.md
```

禁区文件不在列。GitHub PR files 与 tip 一致。CI [`35195641540`](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/35195641540) SUCCESS @ `256994a`。`backtest_output/` 被 `.gitignore:103` 整树忽略；bar_cache 未入库。

---

## 证据表

| 锁 / 裁点 | 结果 | 证据 |
|-----------|------|------|
| **1 范围** 仅短记 + runbook 状态；无 Python / 引擎 | **PASS** | 2 文件 +42/−1。runbook 只改页眉状态一行（链到短记 + 「cache key 偏差见短记 §2」）。plan / handoff / 提案 / AGENTS / README / `csv_minute_backtest.py` / `csv_ledger.py` / `*_rules.py` **未动**。`unified_exit_modeb.py` 仍不存在。 |
| **2 smoke ≠ 网格完成** Mode B 排名不在本票 | **PASS** | 短记标题「smoke，非网格结果」；页眉「Mode B 网格排名不在本短记」；完成表末行 ❌；§5「未跑 Mode B 业务网格；未写 `unified_exit_modeb.py`」。runbook 完成表仍钉「Mode B 网格排名 ❌ 不在本 runbook 范围」。符合 plan P5 / runbook §0 / §3。 |
| **2 覆盖率** 2080 码 ∩ cache = 100% | **PASS** | 见下节。4167 是实例（Mode A 短记 / plan 注）；本票改写成 distinct 码 2080，并声明装配层 13s 复现 opened=4167。cache 2322 = 名单全并集（本核复算 `stock_pool/` 窗口并集 **2322**、实例 **5061**）。2080 ⊆ 2322，缺 0。 |
| **2 墙钟 / 内存自洽** | **PASS** | 见下节。1.259 亿行 × 2080/2322 ≈ **1.128 亿**；1.75GB parquet → 6.6–6.7GB RSS（×3.8，pandas 解压量级合理）；冷 27.4s / 官方热路径 28.9s + `status={'cache': 'hit'}`；宿主 39.9GB，余量 ~33GB。 |
| **3 warmup cache key** `20251013` vs 字面 `20251023`；决策留给实现 | **PASS** | `WARMUP_DAYS=10` → `warmup_start("20251023") = "20251013"`（本核手算）。`csv_minute_backtest.simulate` 把 `load_start` 传进 `load_minute_bars`，故现成文件名是 `minute_none_20251013_20260909.parquet`。`load_minute_bars` 按 `(start,end)` **精确 key** 找 cache——§2 写明：实现若沿用 warmup 起点（推荐）则复用 1.75GB；若坚持业务起点须确认人拍板后重建。覆盖率/墙钟声明不受 key 选择影响。 |
| **4 UTF-8 无 BOM** | **PASS** | 短记 3194 B、runbook 4463 B：BOM=false、NUL=0、CR=0、UTF-8、LF 结尾。`git diff --check` 空。 |
| **硬边界** 不改湖 / 策略书 / 成交核；产物不入库 | **PASS** | diff 无业务代码。§5 与 `.gitignore` `/backtest_output/` 一致。 |

本核 **未**重跑 F 湖分钟装载（无湖环境，与 #90/#91 同）。数字核验走文档自洽 + 对照 runbook / plan P5 / 提案 §9.1–9.2 / 现成 `warmup_start`，不冒充宿主复跑。

### 覆盖率与行数（本核手算）

提案 §9.7 / 本核 `stock_pool/`：窗口 215 文件、并集 **2322 码**、解析 **5061** 实例；缺 `20260525` / `20260605`。Mode A 宿主短记：实开 **4167 实例**（5061 − 795 − 99）。

| 式 | 值 |
|----|----|
| 名单并集 | 2322 码（= cache 声称码集） |
| 实开实例 | 4167 |
| 实开 distinct 码 | **2080**（短记；4167/2080 ≈ 2.00 笔/码，与「同码多日上名单再开」同构） |
| 从未实开 | 2322 − 2080 = **242** 码（封板/超幅度跳过的码不必 = 894 笔，一码可多日被跳） |
| 覆盖 | 2080 ∩ 2322 = **2080/2080，缺 0** |
| cache 全窗行 | 1.259 亿（提案 §9.2「约 1.26 亿行」） |
| 2080 码应有行 | 1.259e8 × 2080/2322 = **1.1278e8 ≈ 1.128 亿**（短记 §3） |
| 每码行数 | 2322 口径 54221；2080 口径 54231（差 ~10 行/码，过滤噪声） |

runbook §1.3 允许「相对 4167 **或**并集」。本短记同时给了实例 4167 与 distinct 码 2080，并纠正了 handoff A.3 / runbook §1.4 把 4167 写成「码」的口径（#93 nit-1）。完成定义按 **码 ∩ cache** 计，不是按 4167 实例当码。

### 墙钟 / 内存

| 口径 | 短记 | 本核对照 |
|------|------|----------|
| 冷读 `read_minute_cache` | 27.4s / 6.7GB | 1.75GB / 27.4s ≈ 64 MB/s 顺序解码，量级合理 |
| `load_minute_bars(use_cache=True)` 第二遍 | 28.9s / 6.6GB，`cache=hit` | 符合 runbook §1.4「热加载 + status hit」；第二遍不更快 → 短记归因解析（2080 row-group），不是假 hit |
| RSS vs parquet | 6.6–6.7 / 1.75 ≈ **3.8×** | pandas 物化 OHLC + ymd/hm 的典型膨胀 |
| 宿主 | 39.9GB，余量充足 | 6.7 ≪ 39.9；未触顶 |
| 与 Mode B 网格成本 | 装配一次 28s 固定底座；触判向量化则窄网格分钟级 | 推论，不是跑数。P1=A 窄船仍等实现 PR |

冷/热几乎同墙钟且热路径略慢，短记没有把「cache hit」吹成数量级加速——这是诚实记录，不是自相矛盾。

### warmup key（相对引擎）

```text
WARMUP_DAYS = 10
warmup_start("20251023") = "20251013"
simulate(): load_start = warmup_start(start) → load_minute_bars(..., load_start, end)
minute_cache_path(start, end) = minute_none_{start}_{end}.parquet
```

因此现成产物 `minute_none_20251013_20260909.parquet` 是 **引擎默认 warmup 口径**，不是宿主写错文件名。窗口 `20251013–20260909` ⊇ 业务窗 `20251023–20260909`；码集 2322 ⊇ 实开 2080。runbook §1.2 字面 `20251023` key **未重建**，理由（全湖重扫 + 再写 1.75GB、无信息增益）成立。

实现侧若调用 `load_minute_bars(codes, "20251023", "20260909")` 会 **miss** 现成文件（精确 key）。短记把「沿用 warmup 起点 / 坚持业务起点」写成确认人拍板项，**没有在本 docs 票里改 `minute_cache_path` 或引擎**——符合 P5「决策留给实现」。

时间线（plan P5 + 本票）：

```text
已做（本 PR） : 湖可达 + 现成 bar_cache 复用 + 2080/2080 覆盖 + 墙钟
已裁（#93 后）: plan 头部 ✅；P1=A / P2=A / P3=A
尚未           : feat/unified-exit-modeb A–D（合入门）
更后           : 切片 E 窄/全网格 + 业务短记（非合入门）
```

---

## 违规 / 风险

无 🔴。无合入阻断。硬边界未破。Mode B **未**实现、也未声称网格已跑。

### nit-1（口径）成本推论「冠军族 ~24 组」与 plan P1 的 18 组不完全同构

plan P1=A 点名：`r2` × X∈{5,7,10} × Y∈{5,10,∞} × N∈{8,10} = **3×3×2 = 18**，另加四锚线 → 合计 22 个求值单元。短记 §4 写「冠军族 ~24 组 + 4 锚线」。

若把 Top 5 文案里的止盈 5–7% 理解成再加 Y=7：`3×4×2 = 24`——那是另一族，不是已裁 P1。成本推论用 ~ 可以，但实现/4090 估时应以 **18+4** 为准。**不挡合入**；不要为本句改 plan 或开 Python。

### nit-2（过期指针）`date_to_ymd` 性能票已在 #92 落地

短记 §4「先落 `date_to_ymd` 向量化性能票」沿用 Mode A 宿主短记 §4。该票已合 PR #92（`_PreparedBars` / `_bar_close_map` 一次 `strftime`，`date_to_ymd` 离开价格热循环）。Mode B 分钟路径仍应避免在 ×240 热循环里做 Python 日期转换，但「先落」易读成票还开着。合入后改成「Mode A 侧已向量化；Mode B 求值器不要把日期转换做回逐元素」即可。**不要为改这一句重切引擎。**

### 观察（不升格）

| 项 | 说明 |
|----|------|
| runbook 正文仍是清单模板 | 本票按核重点 1 **只翻页眉**，§1.4「4167 码」、§2 表仍 ✅/❌、§3「现在就可以做 / 人裁 GO」未改。与 #91 同类卫生债；短记才是填好的完成表。不要求本 PR 扩 scope。 |
| README SSOT 仍写 ⏳ 待人裁 GO | 人裁已在 `0ce1db5`。本票未动 README（正确）。确认人另票回写入口注释 + 链到本短记。 |
| 「可与 Mode B 编码并行」 | #93 nit-4 当时偏早；**现在** plan 已 GO，这句话反而对了。状态行同时钉「只做数据就绪，不是网格结果」，不冲突。 |
| 6.6GB「显存/内存」 | pandas RSS 在主机内存；4090 24GB 显存与本 smoke 无关（plan 非目标：不引入 CuPy）。方向「迁 4090 轻松」仍成立。 |
| cache 建于 2026-09-11 | 湖末日 `MINUTE_LAKE_END=20260909`；09-11 建的全窗 cache 覆盖到湖上界。本核无湖，不能核 meta json 字段，短记称「meta json 完整」。 |
| 装配 13s 复现 4167 | 无 Mode A 明细 CSV 入仓（正确，gitignored）。13s 是日线装配，与分钟 28s 不是同一路径。 |

---

## 建议动作（是否可合）

**可以合。** 不要为 nit-1/2 改引擎，也不要在本票写 `unified_exit_modeb.py` 或勾选切片 E。

合入后（另票 / 实现侧，非本 PR）：

1. Mode B 实现选 cache key：默认沿用 `csv_minute_backtest` warmup 起点 `20251013` 复用 1.75GB；只有确认人要字面 `20251023` 时才重建。
2. 窄网格单元数按 plan P1 **18+4**，不要按短记「~24」估时。
3. （可选）短记 §4 把 `date_to_ymd` 改成「#92 已做；分钟求值器勿回退到逐元素日期转换」。
4. README / runbook §3 时态：人裁已 GO、smoke 已完成，另票回写。

本核 **未 merge、未改业务代码**；仅落本评审文件。

---

## 核验命令（本核已跑）

```text
git fetch origin
git rev-parse HEAD
# = 256994a216e776838fc1453441f2742676a3730f
git merge-base origin/master HEAD
# = 55bfe4a3cb3219c11baa95d9c314206fad52ecd2  (= origin/master = PR #93 merge)
git diff --name-status origin/master...HEAD
# M host-runbook-unified-exit-modeb-smoke-2026-09-17.md
# A unified-exit-modeb-minute-ready-2026-09-17.md
# 无 .py / .rs / YAML
gh pr view 94 --json mergeable,mergeStateStatus,headRefOid,statusCheckRollup
# MERGEABLE / CLEAN / head = 256994a / pytest-and-gates SUCCESS
gh run view 35195641540
# SUCCESS @ 256994a
# UTF-8：两 md BOM=false NUL=0 CR=0
# warmup_start(20251023, days=10) = 20251013
# stock_pool 窗口：215 文件、并集 2322、实例 5061
# 1.259e8 × 2080/2322 = 1.1278e8 ≈ 1.128e8
# git check-ignore backtest_output/ → .gitignore:103
# unified_exit_modeb.py：不存在
```

Mode B Python / 真湖分钟网格 **未**跑（本 PR 无实现；非合入门复验项）。
