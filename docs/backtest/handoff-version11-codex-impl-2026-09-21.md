# Handoff：version11 ma_chip CSV 移植 → Codex 无头实施（2026-09-21）

- **Plan**：[plan-version11-machip-csv-2026-09-21.md](plan-version11-machip-csv-2026-09-21.md) **v1.0 已人裁 GO**（master `d75f9c9`）
- **评审链**：对抗层 F1–F8 → 四稿 [consensus V1–V17](../architecture/reviews/2026-09-21/plan-version11-machip-csv/merge-consensus.md) → 人裁全按建议
- **前置**：**ma_infra 已合入（PR #150）是切片 A 开工门槛**；实施 PR 基于 master `d75f9c9`

## 续作状态（2026-09-21）

- docs-first 两裁决：`4729628`；A 纯规则 / 两段 FSM：`e560a44`；B 稳定化与 volume A 文档：`9133ca8`（已先提交并推送）；**A–C ✅ 已实施（本 PR），D 未跑**。
- 导出产物布局：`--out-dir/pool/YYYYMMDD.csv`，引擎应传 `--pool-dir <out-dir>/pool`；`rejected.csv` 与 `manifest.json` 放 `out-dir`，不混进严格只允许日期 CSV 的池目录。已有非空池拒绝覆盖，避免重跑残留旧日期信号。
- **C 已完成注册 / 双引擎接线**：[显式人裁 A](https://github.com/baiyibing/MyQuant-backtrader/pull/152#issuecomment-5756590614) 覆盖此前 STOP。保留 [δ5 §2.2](plan-industry-align-p3-d5-volume-cap-2026-09-19.md) 严格可得性：开盘 `attempt_at=569`、`bucket=570`，`VolumeCap.clamp` 要求 `bucket <= at`；09:30 桶未完成则买 skip / pending 卖 defer。`execute_buy(at=None)` 默认仍按 bucket 收盘，v11 显式传 569；`_sell` 沿用已有 at 参数。未改 cap 实现 / 默认，也未授权同分钟完整量近似。
- B 稳定化门禁：规则 / 导出器 / ma_infra / 注册表合计 **106 passed**；A/B touched Python ruff 全绿。解释器显式使用 `/workspace/vanna312/bin/python3`。
- `apply()` 原始返回显式 `limit_up_chase=False`，两引擎实测涨停买被跳过后实际 chase dict 为空；EOD 钩子在买循环之后，SMA5 含 T，当日只写 pending，T+1 才可卖；sold-today 过滤阻止卖出日重入。日线沿既有 pending 开盘；分钟只取精确 09:30 首根 open，缺开盘 bar 不借后续分钟，跌停 / 零量 / cap 未完成均保持 pending 到次日。
- **数据接线坑**：旧分钟 loader / cache 会丢 volume。v11 显式 `include_volume=True` 从配置湖读取，保留零量行供计数、绕过旧无量缓存；缺文件或量列即失败。当前 qlib_1min frame 不含 volume，v11 拒用；其他书的加载 / 缓存默认保持原样。
- **容量结果解释**：按 A，启用 participation cap 时精确 09:30 open 无法使用同桶完成量，因此该买尝试会被消耗、已有 pending 卖继续等待；不能把零成交解释为无信号，也不能偷偷改到 09:31 / 收盘补成交。未启用 cap 时，正量开盘按原可选容量合同成交。
- `tests/test_strategy11_engine.py` 已 pin 未完成桶买 skip / 卖 defer（查量回调不调用，现金 / 股数 / cap.used 不变）、两钟成交价、EOD 买日时序、两段 FSM、涨停 / 一字 / 零量 / 缺开盘、跌停 defer、sold-today、三别名与池篱笆。既有 cap-off 字节快照仍绿；HELP_LOCK 旧书未改。
- **最终门禁**（显式 `/workspace/vanna312/bin/python3`）：指定四文件 **84 passed**；全量 `-m "not production and not benchmark" tests/` **1480 passed, 2 skipped, 24 deselected**（1 条既有非 canonical TR window 警告）；全部 touched Python Ruff 全绿；四个 data-free 路径/桥接门禁全绿；导出器及双引擎 `--strategy 11 --help` 冒烟通过；UTF-8 无 BOM、NUL=0。
- AGENTS.md 已回写 A–C 移植状态。**未跑宿主湖 / Rust pyd / seed-30 静态档案与全市场敏感性（D）**，不宣称收益 / parity 已验收；不合并 PR。

## §0 硬边界（人裁已定，勿越）

### 2026-09-21 续作人裁（优先于 plan 旧措辞）

- **契约日**：D 是原信号日；T 是该股**严格晚于 D** 的首个有 bar 交易日（不是 on/after D），且 D→T ≤4 自然日。stale 始终从原 D 起算；超限不写池，`rejected.csv` 记 `skip_buy(stale)` 与原 D。信号仅使用 ≤T−1 数据，文件名为 T，不能采用 export9 的 ≤T 口径。
- **周线 = A / prefix-equivalent**：每个 D 的结果等价于先截断至 D，再重算周线。`ma_infra` 必须提供**显式 opt-in**（参数或独立 helper）；默认 series 的全历史 backward alignment 保持不变，禁止把逐日 asof 偷藏进默认 API。data-free pin 同时证明默认行为不变、opt-in 等价于 truncate-then-call。下文“序列件、禁逐日 *_asof”指调用导出器时仍用 series；周线必须显式选择 prefix 路径。
- **硬坑仍有效**：`apply()` 返回 dict 显式包含 `limit_up_chase=False`；回归同时 pin flag=False 与 chase pending 为空，防止调用方 `hooks.setdefault("limit_up_chase", True)` 开启追买。
- **volume / 09:30 = A**：沿用 `bucket <= at`；开盘未完成桶买 skip / pending 卖 defer，禁止同分钟完成量近似开盘成交；不改 cap 或既有书默认。无 cap 时沿原可选容量合同成交。
- 对 plan 的覆盖见其“2026-09-21 续作覆盖”：严格晚于 D 覆盖任何 on/after 措辞；prefix 周线覆盖将整段历史默认 backward alignment 当成逐 D 信号的解释。本轮先提交本文档与 plan，再实施 A/B/C。

1. **信号价域 = front**（V1）：导出器 `dividend_type="front"` 装载信号序列；执行侧引擎现行（none + `mapped_prev_close`）；manifest 记 adjust_type。
2. **契约日 T**（V2）：= 该股 D 后**首根有 bar** 的交易日且 D→T ≤4 自然日；超限不写池，`rejected.csv` 记 `skip_buy(stale)` + 原信号日 D；**导出器按 ≤T-1 计算写入 T**（勿照搬 export9 的 ≤T 买即用）。
3. **cyqk 一律 `turnover_resist.compute_cyqk_series(window=200)` 现算**：两层失败契约（窗内坏日→该窗 NaN→该日该码 skip；长度不等→`PyValueError`→按码捕获 skip+计数）；**网格预检** `窗口内 (max(high)-min(low))/step > 250k` → skip+计数；**禁读 store `cyqk_t`/store 布林**（window=1000 世界）；不换算法、不复活 Cerebro。
4. **asof 股本**（V7）：`free_float_shares.parquet.circulating_capital` 逐日 backward asof；在 `oskh_factors/bridge/turnover_resist` 加 public 薄壳；**禁 `date=None` 快照（前视）**。
5. **MA/布林/周线一律 ma_infra 序列件**（`sma_series`/`bb_series`/`weekly_sma_series`，禁逐日 `*_asof`）；周线显式 opt-in prefix-equivalent，默认 series 不变（2026-09-21 续作人裁）；`_daily_to_weekly` 不外露。
6. **R9**：`apply()` 返回值必须含 `"limit_up_chase": False`（setdefault 默认 True 会 T+2 追买且 pending 30 天不过期——实验实锤）；`take_profit/record_params` 必返（缺则 RuntimeError）。
7. **全市场模式滤 ST + 排 688**（V9；无名称列时 ST 按前缀错走 10% 档）；seed-30 模式沿归档不做 ST。板块：沪 60 排 688 / 深 000-003 / 创 300-301。
8. 导出器前置剔 volume==0 bar（export9 `:126` 先例）；统计窗（2024-01-01）前 edge 置假在导出器层。
9. 卖出侧（P2）：日线 `pending_exit` 原样（t1_sellable 次日开盘，**无旁路**）；分钟侧新消费=09:30 首根成交、跌停 defer 留 pending 次日再评。
10. 池 CSV 契约：`YYYYMMDD.csv`、无表头裸六位码、LF、UTF-8 NUL=0、`validate_pool_dir` 冒烟、拒绝 `stock_pool/`（`FORBIDDEN_DEFAULT_STOCK_POOL` 增 `version11`）。
11. `--help` 必须印：P0 定位（「cyqk>0.70 仓内文档为抛压区，本版=框架验证非已验证多头」）、契约日口径、stale/网格 skip 计数器名、pyd `__file__` 进 manifest。
12. 禁改 1–10/8.x/12 书与 Mode A/B；全量 pytest 绿不放宽；新文件 ruff 零告警。

## 切片 A：strategy11_rules.py 纯函数（前置：#150 已合入）

**步骤**：`edge_condition(closes, high, high_series, bb_upper_series, cyqk_series, weekly_ma_series)`（四条件 + 边缘：D 真且 D-1 假且**两边有限**）；`exit_signal(t_close, prev_close, sma5)` 两段 FSM（收阴≤→次日卖；收阳→持有至 close<SMA5，**含买入日当评**）+ hold_mode 状态；record/HELP_LOCK。
**测试**：`tests/test_strategy11_rules.py`——边缘/D-1 NaN≠边缘/等号 fail-closed（≤）/买入日禁卖/hold_mode 两段/SMA5 含否 T 收盘（pin 写死所选口径）。

## 切片 B：export_strategy11_pool.py

**锚点**：`scripts/data/export_strategy9_pool.py:2-4,62-63,126`（契约日语义/拒写/剔零量先例）；`oskh_factors/bridge/turnover_resist.py:40-63`（bridge 探针）。
**步骤**：front 装载 → ma_infra 序列件 → cyqk（网格预检+两层失败按码捕获）→ asof 股本薄壳 → 契约日 T 定位与 stale → 统计窗置假 → `--sample seed=20240907/--universe` → `rejected.csv` + manifest（adjust_type/pyd 路径版本/各 skip 计数/耗时）。
**测试**：`tests/test_export_strategy11_pool.py` data-free（合成 OHLC+股本）——契约日（首根 bar/停牌 4 日内/超 4 日 stale）、网格超限 skip、ST/688 过滤、池契约冒烟。

## 切片 C：引擎接线 + 注册

**步骤**：P1 双跑——a=日线保持契约收盘（不造新钟）；b=分钟 09:30 开盘买钟（`_open_quote_for` 首根 open + 开盘 volume 桶 + 涨停/一字拦截计数）+ 09:30 pending 卖（跌停 defer）；EOD 评估钩子（**当日买循环之后**、T 收盘写 pending_exit）；**sold-today 集合买侧过滤**（卖出日不重入）；`version11` 注册（别名 `11/v11/version11`、tag `v11`、`FORBIDDEN_DEFAULT_STOCK_POOL` 增项、apply() 三键）；AGENTS.md 预留句改「已移植（本 PR）」+ Research entries 增行。
**测试**：`tests/test_strategy11_engine.py`——D+1 成交、skip FSM 映射、**chase pending 为空回归 pin**、卖出日不重入、买入日禁卖、EOD 时序（T 买入当日评估→pending_exit→T+1 开盘成交）。`--strategy 11 --help` 双 CLI 冒烟。

## 切片 D：对照冒烟

seed-30 同 universe vs 7 份静态档案（`backtest_output/ma_chip_edge_*`，含 cyqk80/90_nobb/nocyqk/nobb 消融轴）——**按消融轴对照**；差异清单三分类（成交价/费用/skip 语义）+ sanity bounds（信号数/笔数数量级）；全市场一跑敏感性。数字不入库（exports 约定除外）。

## 门禁 + 回写

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_strategy11_rules.py tests/test_export_strategy11_pool.py tests/test_strategy11_engine.py tests/test_csv_strategy_books.py
D:\anaconda3\envs\vanna312\python.exe -m pytest -q -m "not production and not benchmark" tests/
D:\anaconda3\envs\vanna312\python.exe scripts/data/export_strategy11_pool.py --help
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py --strategy 11 --help
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest.py --strategy 11 --help
```

完成后：plan 头部回写「✅ 已实施（本 PR）」；遇语义分叉（尤其契约日边界、cyqk 失败捕获粒度）**停下来在 PR 评论列明，不自裁**。
