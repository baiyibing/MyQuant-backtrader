# merge-consensus · plan-ashare-engine-refactor v1.2 → v1.3（host 证据裁决）

> 日期：2026-09-18
> 席位：`cursor:auto` · `cursor:cursor-grok-4.6-xhigh-fast` · `cursor:composer-2.5-fast`（mixed 预设；classic 的 codex/claude CLI 本机未装，预检 fail-closed 拦下后降级到 mixed）。host = cursor-desktop（ZCode 主持，空槽另填）。
> 对象：plan **v1.2**（三路对抗回填后的版本；`_plan_version.txt` 有内容哈希）。
> 裁决原则：**事实看代码，取舍看 A 股回测惯例；不投票**。host 对全部新 🔴 已逐条亲验。

---

## 席位总裁决

| 席位 | 裁决 | 一句话 |
|---|---|---|
| auto | docs 可合；**编码不可 GO** | 阻塞：帧契约（R1）、handoff 双 SSOT（R2）、skip/defer 误用致 fail-open（R3）、围栏无锚（R4） |
| grok-4.6 | **不可进实现** | 阻塞：帧/compact/topk 共享加载/共享 cache 四件未钉（R1–R4）+ 谓词写进 execute_buy（R5）+ 围栏锚（R6） |
| composer | docs 可合；**编码仍不可 GO** | 阻塞：v7 帧 SSOT（R1）、handoff 同步（R2）、围栏测试 SSOT（R3） |

三席零分歧：**方向对、守界清、v1.2 对抗勘误该留的都留了；阻塞的全是「实施指令精度」，不是架构**。三席均确认编码闸本来就是人裁 P1–P5。

---

## 共识裁决表（MC-1..MC-9；host 已亲验全部 🔴）

| # | 来源 | 裁决 | 内容 | host 亲验 |
|---|---|---|---|---|
| MC-1 🔴 | auto R1 / composer R1 / grok R1（三席一致） | **采纳** | v7 帧契约未钉：`_day_frame_records` 按 `frame["date"]` 切片，书帧 `read_lake_minute_ohlc` 只有 DatetimeIndex+`ymd`/`hm` 无 `date` 列——按字面换 loader 即 `KeyError`（或空切片假绿）。§5-A 写死三选一 + DoD 非空 bar 计数 > 0 | ✅ `csv_minute_backtest_v7.py:258-264` vs `ashare_bars.py:322-366` |
| MC-2 🔴 | composer R2 / auto R2 | **采纳**（系 v1.2 回填遗漏） | handoff 双 SSOT：§2 标题仍「唯一 lot 日历」、§3 围栏无枚举、§6 清单旧文案——Codex 以 handoff 为准会误实施 | ✅ 已全量同步 handoff → v1.3 |
| MC-3 🔴 | grok R2 | **采纳** | plan 自相矛盾：§5-A「私有并保留」vs §7「compact 降级或删」 | ✅ §7 行已对齐「不删」 |
| MC-4 🔴 | grok R3 | **采纳** | topk 与 v7 **共用** `_load_cli_bars`，非独立链——改 v7 湖路径=改 topk 湖帧；§7「topk 不改」低估 | ✅ `csv_minute_backtest_topk_app_dropout.py:22-29` |
| MC-5 🔴 | grok R4 | **采纳** | 共享 cache 污染：`minute_cache_path` 键仅 `(start,end)`、`load_minute_ohlc` 默认 `use_cache=True`——v7 小名单先写 cache，1–10/Mode B 大名单命中即走「缺码整读合并」（= E-07 的 6.6GB 路径）。v7 湖路径 `use_cache=False` | ✅ `ashare_bars.py:551`（默认 True）、`:397-399`（键） |
| MC-6 🔴 | auto R3 / grok R5 / composer Y1 | **采纳（收窄表述）** | 谓词落点误置：`execute_buy`/`_sell` 是纯填单函数（无 T+1/涨跌停），谓词在 simulate 环调用点；照 v1.2 文字实施会改填单契约、还可能把书侧 `limits is None` 先拒（fail-closed）拧成 skip/defer 放行（fail-open）；`hit_limit_*` 的 reserve/open_board/forbid_all/qlib 带内用法不得替换 | ✅ `csv_ledger.py:194-239`（纯填单）；书侧先拒 `csv_simulate_loop.py:257-259` |
| MC-7 🔴 | composer R3 / auto R4 / grok R6+Y2 | **采纳** | 围栏无可执行锚：钉 `tests/test_ashare_simulate_import_fence.py` + `SIMULATE_HOT_PATH` 常量与 §5-C 清单字节级一致；围栏集合补传递一层（`csv_daily_loader`/`csv_pool`/`market_layer`/`exdiv_map`） | ✅ 现有围栏仅 rglob 禁 backtrader（`test_research_face_imports.py:110-119`） |
| MC-8 🟡→🔴级修正 | grok Y1 | **采纳** | limits=None 有**两支**：无昨收 + 未知板块（`session_limit_prices` 两因都返 None）；v1.2 E-04 只写「缺昨收」。None-limits 向量须两支全覆盖 | ✅ v7 `:382-384`（有昨收仍可 `skip_unknown_board`） |
| MC-9 🟡 批 | auto Y1/Y2/Y6、composer Y2/Y3/Y4/Y5、grok Y3/Y4/Y5/Y6/Y7 | **采纳为 v1.3 补句** | P2 旗名不得与 `--qlib-cost` 双 SSOT；内存门给 data-free fixture（非口头 6.6GB）；reason 词表落 tests dict；cache 无新鲜度=已知限制；Mode A 第三套持仓进 §4 非目标；§0 一句话补「第一船=谓词与加载 SSOT」；日线卖出时点两支（`open_board` 同 bar vs `pending_exit` 次日开）；加载线程池无 timeout=已知限制 | ✅ `csv_strategy_books.py:118`（`daily_same_bar_prefixes=("open_board",)`） |

**驳回**：无整条驳回。grok「docs 不可原样合」按事实采纳其半：#105 已合的是 v1.1，v1.2/v1.3 是后续 docs 修订流，§7 矛盾已在 v1.3 消除，不需要回改已合 PR。

**三席确认的 ✅（保留）**：三仓守界/包边界、T+1 买入日不可卖、日线止盈默认 pending_exit 次日开、无未来 bar、复权 none 未混 chip front、盈筹未进 1–8、涨跌停/北交/ST/未知 skip/缺 bar 冻仓、Mode B shares/=k 边界、v1.2 勘误回填与代码一致。

---

## host 亲验记录（新 🔴 全量）

- MC-1：`_day_frame_records`（v7:258-264）`frame.loc[frame["date"] == day]`；`read_lake_minute_ohlc`（ashare_bars:322-366）列 = open/high/low/close/ymd/hm(+DatetimeIndex)，**无 date**
- MC-4：topk:22-29 `from backtest.research.csv_minute_backtest_v7 import _load_cli_bars, ...`
- MC-5：`load_minute_ohlc(use_cache: bool = True)`（:551）；`minute_cache_path` 键 `(start,end)`（:397-399）
- MC-6：`execute_buy`（csv_ledger:194-239）= 整百股+force_min+佣金+记账，零谓词；`_sell` 同
- MC-8：v7:382-384 `priced = session_limit_prices(...); if priced is None: skip_unknown_board`（有昨收仍可 None）
- MC-9：`daily_same_bar_prefixes=("open_board",)`（csv_strategy_books:118）

---

## 第二轮裁定：**不开**

依据 2026-09-18 路由规则（用户已认可）：**仅当共识改动 R\* 或切片边界才开第二轮**。MC-1..MC-9 全部是切片内实施指令精度与 DoD 钉死——R1–R9 未动、切片 A–D 边界未动、P1–P5 选项实质未动；三席互相收敛且与对抗层互补，无事实互斥。再扫一遍同 scope 是烧额度。**人裁时可推翻本裁定**（要求重扫即重扫）。

---

## 下一步

1. plan 已回填 **v1.3**、handoff 已全量同步（MC-1..MC-9）。
2. **人裁 P1–P5**（唯一开工闸；建议默认 A/A/C/A/A，P1 按改述后文案「谓词统一、双账本保留」裁）。回写 plan §3 + 头部 ✅ 已人裁 GO（commit hash）。
3. 之后开 `feat/ashare-engine-refactor` 交 Codex（handoff 为施工图）。#104 已合（`a61b1ad`），闸只剩人裁一半。
