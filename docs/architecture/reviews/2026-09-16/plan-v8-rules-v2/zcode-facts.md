# v8 规则 v2 plan 事实锚点评审（host: zcode-facts）

> 评审对象：plan-v8-rules-v2-2026-09-16.md v1.0 · 结论 **READY-AFTER-FIXES**
> 代码事实类声称（V-R2 唯一缝合点 / peak 现状 / 加仓锁单点 / numba 不可达）**全部证真**；2 处 🔴 规格缺口（px≥cost 前置、reason 契约）+ 断言翻转清单如下。

## 1. V-R2 缝合点 — 证真

- `strategy8_rules.py:65-70` `take_profit_reason(px, cost, peak, n_days=1)`，:75 `del n_days` ✓
- v8 止盈路径全量追查（均过 rules 函数，无旁路）：日线 `csv_daily_backtest.py:411-415`（TP 唯一调用点）→ `:416-426` pending_exit 生成；分钟 `csv_minute_backtest.py:593-594`（Python 路径）；分钟内置 `trail_hits` 回退 `:597-598` 仅 `take_profit is None` 可达（v8 不可达）；numba `:641-648` 要求 take_profit None 且 v8 恒注入 callable（`csv_strategy_books.py:115-116` 缺则 raise）→ **不可达证真**。止损两引擎内联（日线 :376-399 / 分钟 :564-568）不经 rules，符合"不动"。
- 两引擎 n_days 口径一致（买入日=0：日线 :367 / 分钟 :859）→ 门语义正确。
- 🟡 前提：`n_days: int = 1` 默认值与 4 参位置调用契约**保持不变**（3 参旧测试面靠它翻转为 None）。

## 2. peak 从 T+1 累计 — 证真

分钟 `:552-554`（T+0 整日不计，注释原文「峰值从 T+1 起算」；`BUY_HM=14:55` :89）；日线 `:401` 在 `n_days>=1` 块内（:376），买入于收盘（:448-455）。**T+1 当日 high 计入 peak、T+1 TP 被 n_days 门挡、T+2 评估用含 T+1 的 peak** —— 与裁决吻合。锚点测试：`test_csv_daily_backtest_v8.py:148-159`、`test_csv_minute_backtest.py:554-585`。

## 3. V-R3 加仓放开 — 证真（2 处措辞）

- 覆写点：`csv_strategy_books.py:104-106`（`hooks["allow_add"]=book.allow_add` + `if book.sizing=="per_name": hooks["allow_add"]=False`）——registry 唯一 per_name 书是 version8（:628-641），删两行只影响 v8。
- 🟡 `strategy8_rules.py:14` 已是 `ALLOW_ADD=True`（no-op；`test_csv_strategy_books.py:41` 已断言 True）——真锁只有覆写两行。
- 池买放开：`csv_simulate_loop.py:184-186`（唯一拦截）；per_name 分支 :209-219 每笔用满预算；`execute_buy`（`csv_ledger.py:205-207`）lot_id 递增、独立 cost/peak/entry_idx；逐 lot 卖出评估（日线 :366 / 分钟 :858）；`_sell` 精确摘单 lot（:260-263）。
- chase 遇已持：`:118-122` 唯一拦截，放开后按新 lot 追买。skip_cash 兜底：池买 :212-215 + `execute_buy` :199-200；chase 失败 `chase_buy_fail_cash/shares` :148-152。
- 追买三句不变：`chase_decision`（`csv_ledger.py:105-111`）+ `csv_simulate_loop.py:123-141`（pop 在判定前=弃）。plan 引 :131-139 行号略偏。
- 🟡 敞口口径：同码同日 chase(9:45,:917-926 先跑)+池买(14:55,:945-961 后跑) 可各 +100 万 → **200 万/码/日上界**。
- 统计语义：放开后 v8 `skip_held`/`chase_skip_held` 恒 0，`add_lots` 每 lot_id>0 自增（:222-223）。

## 4. 断言翻转清单（切片 B 直接消费）

**4a `tests/test_strategy8_rules.py` — 整文件重写**：:8-13 import 符号（band_floor/peak_drawdown_hits 随新表重定义）；:16-31 band 边界（新档 6/15/50/100 + 新开闭约定）；:40-58 三参调用全 None（n_days=1）→ n_days≥2 按新档重算；:65-66 px<cost → None **保留**；:69-81 peak_dd/120% arm 概念取消。

**4b `tests/test_csv_daily_backtest_v8.py`**：:40-56/:59-75 止损两例**不变**；:88-93 → T+1 不评、T+2 触发、卖日 20251106@11.80；:106-111 → 卖日 20251106@10.10；:124-129 → 卖日 20251107@10.02；:143-145 → g=15% 落三档 `sell_trail==1` 卖日 20251106@11.30（边界活例证）；:148-159 **不变**；:162-196 chase **不变**；:207-211 summarize 文案换新；:227-233 → lots==[0,1]、add_lots==1、skip_held==0（「无卖出」在保留 px≥cost 守卫时仍成立）；:235-238 v6 对照**不变**。

**4c `tests/test_csv_minute_backtest_v8.py`**：:15-58 止损/T+0 **不变**；:79-81/:102-104/:125-127/:148-150 → `idx==-1`（T+1 豁免）；:179-237 chase **不变**；:256-260 → lots==[0,1]、add_lots==1、skip_held==0。

**4d `tests/test_csv_strategy_books.py`**：:273-280 → `allow_add is True`、skip_held==0、add_lots==1、len(positions)==2（用例名改）；:319-322 chase held → `chase_skip_held==0, add_lots==1`；:299-318/:248-270/:332-348/:351-358/:361-373 **不变**（golden 只含 v1/v6）；:168-171 保留「策略 8」字头。

**4e `tests/test_csv_daily_backtest.py`**：:324 `hooks["allow_add"] is False` → `is True`（**易漏**）；:1045-1050 pre_er1 存在性**不变**；:206 假书**不变**。

**4f `tests/test_csv_minute_backtest.py`**：:522-548/:554-585 **全部存活**。

## 5. band 数学

§0/§1 自洽 ✓；g=15% 衔接 max(1.15,1.09)=1.15 ✓；g=25% 交点 ✓；🟡 现状 `band_floor` 是 lo 开 hi 闭（:38），新表开闭混杂须显式换约定 + 精确边界单测；🔴 **缺 px≥cost 前置**（现状守卫 :78-79 保留，否则亏损价抢跑止损）；🟡 touch 成交语义：日线触发价 / **分钟当根 close**（:567-568）——§1 措辞勘误；🟢 g≤0 与止损关系成立。

## 6. 其他翻车点

🔴 **reason 契约未定义**（共识已裁 `trail:band:1..5`）；🟡 summarize v8 行直接下标 `profit_base/peak_dd_arm/peak_dd_pct`（`csv_daily_backtest.py:590-598`，分钟 :70 复用）——键删改即双引擎 KeyError，落点表必补；🟡 stale 文案三处（`strategy8_rules.py:92-96`、`csv_minute_backtest.py:99/108/110`、`README.md:53`）；🟢 pre_er1 涉 v8 仅存在性断言（generate_snapshot.py:62 会过期但无害）——**禁再生成**；🟢 v7 隔离；🟢 `chase_explained==skip_limit_up` 类断言存活。

## 勘误表（v1.1 已采纳）

px≥cost 前置 / reason 契约 / V-R3 措辞 / summarize 落点 / minute HELP 落点 / touch 语义措辞 / 200 万每码每日上界 / chase 行号 :123-141 / g=15% 脚注改写 / n_days 默认值锁 / 断言清单 §4 / pre_er1 禁再生成。
