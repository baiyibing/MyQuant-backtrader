<!-- agent=cursor:composer-2.5-fast cmd-prefix=C:\Users\wangc\AppData\Local\cursor-agent\versions\2026.09.15-d2fe57e\node.exe C:\Users\wangc\AppData\Local\cursor-agent\versions\2026.09.15-d2fe57e\index.js --model composer-2.5-fast -p --output-format text --trust -f --mode ask --workspace D:\PycharmProjects\MyQuant-backtrader <prompt> -->
# 评审意见 · `plan-ashare-engine-refactor-2026-09-18.md` v1.2

**侧重**：SSOT 一致性 + 行级精确性（对照 `engine-positioning-ssot.md`、`engine-ashare-correctness.md`、§1 锚点表所列模块取证）。并行目录其他评审员产出尚未完成，独立评审。

---

## 🔴 必须修

### R1 · 切片 A 未钉 v7 帧契约，按字面实施会静默空跑

Plan §5-A 要求 v7 默认湖路径改走 `load_minute_ohlc`，但 v7 帧分支按 **`date` 列**切片，与书引擎 DatetimeIndex + `ymd/hm` 帧不兼容：

```258:264:backtest/research/csv_minute_backtest_v7.py
def _day_frame_records(frame: Any, day: date) -> list[dict[str, Any]]:
    ...
    sl = frame.loc[frame["date"] == day]
```

```322:361:backtest/research/ashare_bars.py
def read_lake_minute_ohlc(...):
    """Book-engine lake frame: DatetimeIndex + open/high/low/close/ymd/hm."""
    ...
    # 无 date 列
```

对照：compact 湖路径显式产出 `date` 列（`ashare_bars.py:150-168` `_compact_minute_frame`）；1–10 分钟链用 `_slice_day` + DatetimeIndex（`csv_minute_backtest.py:451-460`），**v7 未复用该路径**。

**要求**：§5-A / §7 补「v7 湖路径帧 SSOT」三选一写死——(a) 复用 1–10 的 `_slice_day`/span 切片；(b) 改 `_day_frame_records` 接受 `ymd`/DatetimeIndex；(c) 薄适配层 `book_frame → v7 records`。DoD 加「改造后 v7 合成窗非空 bar 计数 > 0」防 KeyError/空切片假绿。

---

### R2 · 交接稿 handoff 与 plan v1.2 术语/围栏不同步（Codex 双 SSOT 风险）

Plan v1.2（E-01）已改 P1=A 为「谓词统一、双账本保留」；handoff 仍为旧文案：

```62:63:docs/backtest/handoff-ashare-engine-refactor-codex-impl-2026-09-18.md
## 2. 切片 B · 唯一 lot 日历（仅 P1=A 且已 GO）
```

Plan §5-C 已钉 **11 文件枚举围栏** + `engine.py` 另开卫生票；handoff §3 仍泛称「simulate 热路径 AST」，**未列枚举清单**（`handoff-ashare-engine-refactor-codex-impl-2026-09-18.md:81-85`）。完成清单 §6 仍写「B · 唯一 lot 日历」（`:110`）。

Plan 头部引用 handoff 为实施入口（`:8`）。**主 plan 可 GO 前须同步 handoff 至 v1.2**，否则 Codex 按 handoff 会误解 P1 交付物并漏做枚举围栏。

---

### R3 · 切片 C「围栏测绿」无可执行测试锚点

Plan §5-C DoD：「围栏测绿（按枚举清单）」。仓内现状：

- `tests/test_research_face_imports.py:110-119` 仅 rglob 禁 **backtrader**，不含 `trade_fee_policy`；
- `backtest/research/engine.py:21-24` 仍 import `trade_fee_policy`（host 已在 adversarial-errata S2 亲验）。

Plan 正确改枚举（E-05），但 **未指定新测文件名/函数名/11 文件常量表落点**。DoD 应写死例如 `tests/test_ashare_simulate_import_fence.py` + `SIMULATE_HOT_PATH_MODULES` 与 plan §5-C 列表字节级一致，否则「测绿」不可验收。

---

## 🟡 应修

### Y1 · 切片 B「涨跌停只调 ashare_session」表述过宽

Plan §5-B 写 `execute_buy`/`_sell`/v7 买卖「**只调** `ashare_session`」。现状 1–10 日线 simulate 大量直调 `hit_limit_up`/`hit_limit_down`（涨停保留、`forbid_all_trade_at_limit`、`reserve_limit_up` 等，`csv_daily_backtest.py:328-393`）；`csv_ledger.chase_decision` 亦直调 `hit_limit_up`（`:108`）。

**建议收窄**：本切片统一的是 **T+1 谓词 + 买卖 gate 的 skip/defer 包装**（`skip_buy_at_limit` / `defer_sell_at_limit` / `t1_sellable`），**不**要求替换 reserve/open_board/qlib 9.5% 带内所有 `hit_limit_*` 调用。避免 Codex 过度重构引入 NAV 漂移。

---

### Y2 · 切片 A 缺码路径内存门缺可复现验收脚本

Plan §5-A / E-07 引用 modeb 实测 6.6–6.7GB（`ashare_bars.py:572-575` 整读 cache 合并）。DoD 写「不得整仓物化」但未给：

- 触发条件 fixture（N codes、cache hit + missing subset）；
- 峰值上限或相对基线阈值；
- data-free 近似测法（mock parquet 行数）。

建议 handoff §1 附最小脚本或 pytest marker，否则 OOM 门再次靠口头。

---

### Y3 · 切片 D reason 桶映射仍缺机器可读 SSOT

E-03 已要求两套词表（1–10 前缀计数 vs v7 自由字符串；未知前缀落 `sell_pos_trail`，`csv_ledger.py:271-272`）。Plan §5-D 仍只有原则。**建议** §5-D 或 handoff §4 增 `docs/backtest/fixtures/ashare-reason-bucket-map.yaml`（或 tests 内 dict）示例行，否则 D 步骤不可重复。

---

### Y4 · `minute_cache_path` 无新鲜度守卫（切片 A 挂 v7 后风险放大）

Plan changelog E-15 记录在案；§5-A 未写处置。`ashare_bars.py:397-399` 仅 `(start,end)` 键。v7 挂同一 cache 后，湖增量更新可能长期命中 stale cache。**建议** §5-A 加一句：本船不改守卫则 DoD 须 document「已知限制」；或 `--rebuild-minute-cache` 进 v7 CLI 文档。

---

### Y5 · 第三套持仓跟踪未入主文

adversarial-errata E-01 提到 `unified_exit_modea.Instance` 第三套跟踪；plan v1.2 正文 §5-B 仅写双账本。**建议** §2 非目标或 §5-B 脚注一句「Mode A 网格持仓不进本船」，防 implementer 误以为「全仓唯一 lot 日历」。

---

## 🟢 可选

- **P5=A「薄包装」**：无 CLI 面/HELP_LOCK  diff 边界（adversarial 亦 abstain）；若 GO 后做 wrapper，补 1 段「允许改哪些 argv/exit code」。
- **切片 C 是否纳入 `market_layer.py`**：热路径经 `ashare_session`/`ashare_bars` 间接 import，单文件 AST 围栏可不含；若要坚持「谓词 SSOT 零分叉」，可纳入只读名单。
- **激进一次到位**：主程序未上线，P3/C（E-R5 改股、ST PIT）仍后置合理；若团队愿承担 golden 作废，可在人裁表增 P3=B 选项说明，非本 plan 阻塞项。

---

## ✅ 做对的地方（保留）

### 三仓守界 + 包边界

§0.2–§0.3 与 `engine-positioning-ssot.md` 同构：LEBS 只在 1.3、本仓无 `backtest/lebs/`、策略 7 ≠ LEBS turtle、Cerebro 禁止复活（`:34`、R2）。研究 CLI 锚在 `backtest/research/`（§7），未把 LEBS/MockQMT/`presets.py` 当向量化实现。

### 必查盲区（代码亲验）

| 项 | 结论 | 证据 |
|---|---|---|
| **T+1 / n_days=0** | 买入日不可卖 | 日线 `n_days>=1`（`csv_daily_backtest.py:327,334`）；分钟 `can_sell=(n_days>=1)`（`:618`）；v7 `t1_sellable(buy_date, day)`（`csv_minute_backtest_v7.py:228`） |
| **日线止盈时点** | 非 same_bar → `pending_exit`，次日开盘卖 | `csv_daily_backtest.py:396-399`；`Position.pending_exit` 注释（`csv_ledger.py:74`） |
| **未来 bar** | 持仓评估用 `day_bar_and_prev_closes` 截至当日/前收，未见前瞻 close | `csv_daily_backtest.py:300-312` |
| **复权口径** | 向量化链默认 `dividend_type=none` / E-R5；未把 front 套进 CSV 书引擎 | `csv_daily_backtest.py:6-7`；`engine-ashare-correctness.md` E-R5 |
| **盈筹率** | Plan 未把 cyqk 接入 1–8 书；仓内 cyqk 验证脚本尺度 0–1（`verify_minute_chip.py:139`） | Plan 仅 §8 名单管道提及 chip，范围正确 |
| **涨跌停 / 停牌** | E-R1/E-R2/E-R4 与 plan R5 一致；北交 30%/ST 5%/未知 skip | `market_layer.py:43-65`；缺 bar 冻仓（日线 `got is None` continue `:301-302`） |
| **Mode B 边界** | `shares/=k` 仅 modeb；`rescale_position` 不动 shares | errata E-08 亲验路径 |

### v1.2 对抗勘误回填质量

E-01 双账本、E-02 `n_days` 联合日历口径、E-04 v7 None-limits fail-open 留存、E-06 六差异 + 价格列 DoD、E-09 compact/qlib_1min 链保留——与代码事实一致，**应保留**。

### 基线与模块锚点

§1 表 #104 已合 `a61b1ad`、`load_minute_bars = load_minute_ohlc`（`ashare_bars.py:591`）、§7 补 `csv_simulate_loop`/`csv_common`/`csv_strategy_books`（E-16）——符号级锚点可用。

---

## 总评

**v1.2 方向正确、守界清晰、对抗勘误回填到位**；三仓 SSOT、T+1/复权/涨跌停必查项与代码一致。阻塞实现的主因是 **切片 A v7 帧契约未写死（R1）**、**handoff 未跟 v1.2 同步（R2）**、**围栏测无测试 SSOT（R3）**。

**是否可进实现**：**本 docs PR 可合；编码仍不可 GO**——须 (1) 人裁 P1–P5 + 头部 ✅；(2) 修 R1–R3（至少 plan+handoff 同步）；(3) 切片 A 补 v7 帧 SSOT 后再交 Codex。修完 R1–R3 后，按 P1=A 做 A–C 切片风险可控，默认不改 1–10/v7 NAV 的目标与代码现状匹配。
