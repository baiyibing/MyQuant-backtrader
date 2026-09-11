<!-- agent=cursor:kimi-k3-high cmd-prefix=C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\node.exe C:\Users\Thinkpad\AppData\Local\cursor-agent\versions\2026.09.10-fd3934a\index.js --model kimi-k3-high -p --output-format text --trust -f --mode ask --workspace E:\PycharmProjects\MyQuant-backtrader <prompt> -->
证据收集完毕。以下为评审意见。

---

# 评审：plan-strategy7-turtle-csv-minute-2026-09-11（v1.1）

**评审员**：kimi（侧重：实验验证安全阀/fallback 类设计）
**交叉核对**：`_parallel/` 下 claude / codex / cursor-auto / cursor-kimi-k3-high 四份目前仅有 prompt 头、无完成意见，本轮独立完成。

## 实验声明（我的侧重条款的适用性）

本 plan 是纯单进程向量化回测：**无 timeout / budget / circuit-breaker / 并发锁 / 异步 / 重试设计**。唯一并发是复用的 `load_minute_bars` 内部 `ThreadPoolExecutor`（csv_minute_backtest.py:324，纯 IO map，无超时宣称，v7 不新增并发语义）。故「安全阀必须跑实验」条款**无适用对象**；实验火力转向 plan 依赖的 **fallback/失败路径与数据可行性**（缺数抛错、缺 bar skip、闸 preload），全部只读、可复现：

| 实验 | 结论（pid/输出见下） |
|---|---|
| E1 指数日线 `000001_SH` none | 存在，2004-10-13→2026-09-11 共 5328 行；start 前 5299 个交易日（preload 充足）；窗口 20260804–20260909 共 27 天；**窗口内 10 天 close<MA10 且有连续 2 日** → 闸会触发，验收第 2 条可达成（pid 13528, elapsed 1.8s） |
| E2 指数脏数据分布 | **close≤0 共 2485 行，全部在 2004-10-13–2014-12-31**；2026 年 0 行；近 43 行 min close=3764（pid 16800） |
| E3 `classify_daily_lake_kind` | `000001.SH→index`、裸 `000001→unknown`、`000001.SZ→ashare`（不抛错！） |
| E4 分钟湖 14:55 bar | 名单 59 票抽样 8 票 × 27 交易日，hm==895 **零缺失**、无 NO FILE（pid 21264） |
| E5 名单目录 | `E:\PycharmProjects\OSkhQuant1.3\stock_pool_turtle` 存在，20 个 CSV 正好覆盖 20260804–20260909 |

## 🔴 必须修

**R1. §4.4 步 2 与 3b 止损线数学倒挂，「减试错再上车」在单边下跌中退化为延迟 1 分钟的全清，且触发语义未锁定。**
A1 ≥ A×1.04（§4.4 步 1 成交条件）→ A1×0.96 ≥ A×0.9984 **> A×0.99**，恒成立。价格从 A1 阴跌：先穿 A1×0.96（此时状态「7 成+试错在」，唯一止损是 A×0.99，不触发 ✅ 符合 H-R1），再穿 A×0.99 触发减试错；减试错成交后价格**已在 A1×0.96 之下**，按 §4.1「触线只用当根 close」的状态语义，下一根分钟 close ≤ A1×0.96 立即触发 3b 全清（§4.8-2「同一分钟止损桶只执行一条」只挡住当分钟级联，挡不住次分钟）。后果：人裁 18:23–19:03 锁的「留 3 成 → 3a 再上车」机制，仅在减试错后价格快速反弹 ≥+0.85% 站上 A1×0.96 时才可达；而 plan 花大量篇幅锁 3a/4/H-R12（3a 后无新止损），§8 单测 2 也只测「1→2→3a」理想路径，**没有测「步 2 后次分钟立即 3b」这一数学上最高频的级联**。两种修法请主持裁二选一：(a) 确认意图即如此，在 §4.4 写明级联语义并补单测「减试错后未反弹 → 次分钟 3b 全清」；(b) 3b 改为「进入 three_after_chop 后**重新穿越** A1×0.96 才触发」（穿越事件语义）。不澄清则实现者两种写法都「符合 plan」，回测结果分叉。

## 🟡 应修

**R2. H-R15/§4.7「close≤0 → 抛错退出」未限定校验范围。** E2 实测：指数日线 2004–2014 有 2485 行 close≤0（占全量 47%）。若实现者对 loader 全量数据校验 close≤0，首跑必炸。plan 上下文隐含「preload 段 + 回测窗口内」，§4.7 的「窗内缺日」有范围词而 close≤0 没有。建议明文：「校验范围 = preload 10 交易日 ∪ [--start, --end]」。

**R3. §4.6 五日计时清仓的成交价未锁定。** 「第 5 个交易日**开盘起**清可卖腿」——09:30 open 成交？还是开盘起逐分钟 close？§4.3 止损有「开盘已破线且非跌停 → open 成交」的明文，计时清仓没有。实现者自由发挥会导致与止损口径不一致。建议锁定：开盘首根 open 成交（跌停 defer 同止损）。

**R4. 五日计时对交替止盈的压制未声明。** §4.5「未满仓也可触发」交替止盈档 = 成本 ×1.3/1.5/1.8/2.0，但 §4.6 规定未满 9 成第 5 个交易日开盘清仓——5 个交易日内 +30% 才够到第一档。即「未满仓交替止盈」实践中近乎死规则（唯一活路是 5 日内连续加仓刷新锚）。规则组合本身自洽（不清仓的满仓路径才走止盈），但建议在 §4.5 加一句「未满仓时本表通常被 §4.6 压制，仅连续加仓刷新锚时可达」，免得后续评审/实现者当 bug 报。

**R5. 多票同分钟现金竞争顺序未定义。** §4.1「多票并行，受现金与 B 同时约束」+ §4.8-5「卖出回收现金可用于同分钟加仓」——多票同一分钟抢现金时按什么顺序分配？策略 6 按 pool CSV 名单顺序（csv_minute_backtest.py:606-607）。v7 应锁定确定性顺序（如名单序），否则同输入多次运行结果不可复现，trades.csv 无法对账。

**R6. `classify_daily_lake_kind` 本身不抛错。** E3 实测裸码返回 `unknown`、`.SZ` 返回 `ashare`（oskh_data/lake_kind.py:36）。plan §4.7「裸 000001 / .SZ → 失败」要求 v7 **自己**对非 `index` 结果 raise——plan 有此意但 §3 允许清单未注明模块路径（在 `oskh_data.lake_kind`，不在 `common.infra.data_root`），实现者可能找错位置或误以为 classify 会拒绝。

## 🟢 可选

- R7. `csv_minute_backtest.py:90` HELP_LOCK 仍写「分钟湖目前到 2026-05-25」（过期注释；常量 `MINUTE_LAKE_END="20260909"` csv_daily_backtest.py:52 已更新且注释注明 2026-09-11 实测）。v7 文档别抄这句。
- R8. `load_pool_days` 的 `pool_dir=None` 默认**静默回落** `REPO/stock_pool`（csv_daily_backtest.py:331-336）。H-R8「缺则失败」必须由 v7 在调用前自行校验，不能指望 load_pool_days 抛错。
- R9. §7 reason 最低集缺 `skip_no_1455`（缺 14:55 bar 当日不开新仓）。E4 实测零缺失属低频，但缺审计 reason 时无法区分「名单无此票」与「有票但缺 bar」。
- R10. 工作区在途 diff（feat/strategy6-rolling-csv，+278/-103）改了 `STOP_PCT`/`TIERS`/`CHASE_HM` 并移动了 `COMMISSION`/`_buy_size` 的 import 位置；v7 白名单符号（`round_fen`/`hit_limit_up`/`load_minute_bars`/cache 三件套等）在 diff 后均仍在，但建议 v7 动手前先 merge 策略 6 在途改动，避免 import 漂移。
- R11. 佣金 0.1% 双边无最低、无印花税——策略 7 分批买卖频次高于策略 6（减试错再上车 + 交替 4 档），成本敏感度更高；与策略 6 对齐可接受，建议 summary.txt 注明「未含印花税/过户费」。

## ✅ 做对的地方（保留）

- **T+1 lot 级** `buy_date < today`、禁仓位级 `can_sell`（H-R5）——比策略 6 的 `n_days>=1` 更细，部分卖场景正确。
- **闸无未来函数**：`gate[T]=f(≤T-1)`（§4.7）✅；E1 实测 preload 充足（start 前 5299 个交易日）、窗口内确有连续 2 日破 MA10，验收第 2 条可达成。
- **峰值 = 已走过分钟 high 的 running max、满 9 成才评回撤**（H-R7）✅ 无未来 bar。
- **禁 `_buy_px` 14:30 回退**（H-R11）✅；E4 实测 14:55 bar 零缺失，「缺根 skip」是低频兜底而非主路径。湖时间「中国钟点标成 UTC」与 csv_minute_backtest.py:79 一致，`BUY_HM=895=14:55`（:72）✅。
- **禁 chip_indicator**（H-R16）✅ 规避复权口径混用（chip_indicator.py:148 默认 `front`，本策略全程 none）。必查盲区中「复权口径 / 盈筹率尺度 / 周均线」三条对本 plan **不适用**（无 chip、无 cyqk_c、无周均线；MA10 为指数日线 none，自洽）。
- **包边界正确**：rules/CLI 落 `backtest/research/`，复用 `oskh_data`/`common.infra` path-SSOT。`backtest/lebs` 本仓**不存在**（Glob 0 结果），docs/backtest/README.md:5-14 的 LEBS 叙述确已过期——H-R16 判断正确。
- **`TURTLE_ADD_BANDS` 只读复用有据**：trade_decision/turtle/buy.py:12 = `((0.04,0.3),(0.10,0.2))`，与 §4.2 一致；H-R14 警告有据（sell.py:121 确有 `hold_days>=5`+BANDS 逻辑，不可照抄）。
- **数据可行性全部实测通过**：名单 20 CSV 覆盖窗口、59 票分钟数据齐、指数日线到 2026-09-11。

## 总评

方案与仓内事实高度对齐，H-R1~R16 对抗回填质量高，数据可行性经 5 组只读实验全部验证通过；**唯一硬阻塞是 R1**（§4.4 止损线倒挂导致的级联语义未锁定，属人裁意图确认而非实现纠错）。**结论：R1 澄清 + R2/R3 补一句话后可进实现**；R4–R6 建议同轮修掉，🟢 可留到切片 A 之前。
