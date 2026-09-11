<!-- agent=cursor:auto cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\index.js --model auto -p --output-format text --trust -f --mode ask --workspace E:\PycharmProjects\MyQuant-backtrader <prompt> -->
# 策略 7 plan v1.1 评审（SSOT + 行级取证）

并行目录仅有 prompt 壳，无其他评审员已完成正文；以下独立取证。方案无 timeout/budget/safety-valve 宣称 → 免做并发超时实验。

---

## 本仓盲区核对

| 盲区 | 结论 |
|------|------|
| T+1 / 隔日成交 | ✅ `lot.buy_date < today`；触线 close（开盘已破且非跌停→open）；闸/峰值均无读未来日 |
| 复权口径 | ✅ 成交/涨跌停/指数闸一律 `dividend_type=none`；禁 chip/front（与筹码轨解耦正确） |
| 盈筹率 `cyqk_c` | N/A（v1 不用）；代码侧为 **0–1**（`get_winner` 归一化累加） |
| 周均线 | N/A（本 plan 是上证 **日线 MA10** 新开闸，非 20 周线） |
| 包边界 | ✅ 规则+CLI 落 `backtest/research/`；不进 `ProfitStrategy`/Cerebro；算法不误塞 `oskh_factors` |

---

## 🔴 必须修

**R1. 「同分钟穿越多档按 SDD 级联合并」无公式，却禁止抄 `sell.py` → 实现必漂移**

plan §4.5 只写「级联合并」，§3 又禁 `trade_decision.turtle.sell` / `_eval_prototype_sell`。仓内唯一可执行定义在：

```160:166:trade_decision/turtle/sell.py
    frac = 1.0
    for idx in range(seq, target + 1):
        frac *= 1.0 - ratios[idx]
    frac = round(1.0 - frac, 4)
    return SellPresetDecision(
```

须把 `frac = 1−Π(1−r)`、`seq` 语义、reason 取最高档写进 `strategy7_rules` 契约；否则 coder 会加总 30+20+… 或非法 import。

**R2. 交替止盈 / 回撤止盈在 T+1 可卖不足时的「seq 是否推进」未锁**

§4.5 对回撤写了「卖不完次日重评」，交替档没有。若 `sellable < floor(剩余×frac)` 却推进 `sell_band_seq`，会永久少卖；不推进则可能同价反复磨。须锁：**按可卖股部分成交 + seq 仅在该档目标量完全满足（或明确「尽力即推进」）后更新**，并配单测 8 同类。

**R3. 白名单允许 `write_run_artifacts`，签名却绑定策略 6 `SimState`（与 H-R3 禁 `SimState` 字面冲突）**

```766:774:backtest/research/csv_daily_backtest.py
def write_run_artifacts(out_dir: Path, st: SimState, text: str, help_lock: str) -> Path:
    """三件套：summary.txt / daily_equity.csv / trades.csv。"""
    ...
    pd.DataFrame(st.trades).to_csv(
```

实际只需 `.trades` / `.equity_curve`。plan 应改成：v7 自写 3 行落盘，或写明「duck-type，禁止构造/import `SimState`」。

---

## 🟡 应修

**Y1. `load_pool_days` 默认可静默回落 `stock_pool/`（与 H-R8 对抗）**

```331:335:backtest/research/csv_daily_backtest.py
def load_pool_days(
    start: str, end: str, pool_dir: Optional[Path] = None
) -> dict[str, list[str]]:
    root = Path(pool_dir) if pool_dir is not None else Path(REPO) / "stock_pool"
```

CLI 须在调用前解析 `--pool-dir`/`OSKH_TURTLE_POOL_DIR` 并 fail-closed；单测覆盖「未传 → 非空退出码」，勿依赖调用习惯。

**Y2. 允许 import `TURTLE_ADD_BANDS` 与 §4.6「禁止 `TURTLE_ADD_BANDS[units]` 作下一档」并存，脚枪**

```12:12:trade_decision/turtle/buy.py
TURTLE_ADD_BANDS: Tuple[Tuple[float, float], ...] = ((0.04, 0.3), (0.10, 0.2))
```

`sell.py` 计时正是 `hold_days>=5` + `TURTLE_ADD_BANDS[_band_idx]`（L119–128）。chop 后下一档是 **A1×1.04**，不在该元组。建议：只把 `0.04/0.10` 写成 rules 常量，或注释「仅文档对照，计时/chop 禁索引」。

**Y3. 单票预算 B 的「占用」在减试错再上车后欠一句**

§4.4：卖 4 成后再加 4 成 → 生涯买入名义可 >0.9B，持仓目标仍按成数。须明确：**B 约束的是当前目标仓位名义，不是累计买入**；否则实现成「已用额度」会卡死 3a。

**Y4. 满 9 成后交替止盈减仓，回撤止盈是否仍启用**

§4.5「仅已满 9 成」vs §6 `stage==nine`。须写死：**以 stage/曾达 9 成为准，不以当前股数==0.9B**（否则卖过 30% 后回撤止盈静默失效）。

**Y5. `docs/backtest/README.md` 仍把 LEBS/「Cerebro 已拆」当主入口——H-R16 正确，但实现文档索引会误导**

```5:14:docs/backtest/README.md
## 研究主入口（LEBS）
...
Cerebro 旧壳已拆除。`vendor/backtrader` 只读、不 import。
```

与根 `README.md` / `AGENTS.md`（Cerebro + path-SSOT 研究叉、无 lebs 包）冲突。plan 已禁以其选型；建议在 §3 再钉一句「入口以本 plan + `csv_minute_backtest_v7.py` 为准」。

**Y6. 指数闸 loader 的符号 API 形状**

`classify_daily_lake_kind("000001.SH")=="index"`，`"000001"→unknown`，`"000001.SZ"→ashare`（`tests/test_hive_lake_kind_and_roots.py` L52–74；`oskh_data/lake_kind.py` L36–58）。路径须 `to_partition_key`→`symbol=000001_SH`。plan 已对，实现签名建议只收 canonical `.SH`，内部转 partition。

---

## 🟢 可选

- 印花税：与策略 6 一样只双边 0.1%、无印花——研究对齐可接受；若要「激进一次到位」可加卖出 0.05% 并与 s6 对照开关。
- `csv_minute_backtest.py` HELP 仍写湖末日 2026-05-25，常量已是 `MINUTE_LAKE_END="20260909"`（`csv_daily_backtest.py` L51–52）——v7 勿抄旧 HELP。
- reason `EOD_MARK` 是否进 `trades.csv` 可与 s6 净值曲线口径统一说明。

---

## ✅ 做对的地方

- **H-R1**：7 成试错仍在时禁用综合成本 ×0.99，避免先于 A×0.99 全清（对抗回填正确）。
- **T+1 lots / 禁仓位级 can_sell**：相对策略 6 单 `Position`+`entry_idx`（`csv_daily_backtest.py` L90–96, L455）是正确升级。
- **禁 `_buy_px` 14:30 回退**：该回退仍在 `csv_minute_backtest.py` L468–475；plan 强制 `hm==895`（=`BUY_HM`）缺根 skip —— 正确。
- **指数走 `resolve_index_daily_root()`，禁 `load_daily_bars` 读上证**：`load_daily_bars` 根是 `resolve_period_root("1d")`→**stock** 树（L387）；`resolve_index_daily_root` 永不读 `OSKH_PERIOD_1D_ROOT`（`data_root.py` L241–260）—— SSOT 对齐。
- **`gate[T]=f(≤T-1)` + 收复日当天 14:55 仍拒**：无未来函数。
- **禁 `warmup_start`**：其实测为日历减 10 天（`20260804→20260725`），不够 10 个交易日。
- **本仓无 `turtle/stop.py`、无 `backtest/lebs/`**：glob 为空；禁 import 1.3 stop / 不以过期 README 选型 —— 正确。
- **包边界**：纯规则 + 研究 CLI 在 `backtest/research/`，不污染 `presets.py` / Cerebro —— 符合本叉布局。

---

## 总评

v1.1 在 T+1、涨跌停、指数三树、禁策略 6 撮合、人裁止损与 §4.4 自洽上已经可编码；**卡住实现的是交替止盈合并公式与 T+1 部分成交时 seq 语义（R1–R2），外加落盘 API 与禁 `SimState` 的字面矛盾（R3）**。修完 R1–R3 并补对应单测后可进切片 A；当前 **不可直接进实现**。
