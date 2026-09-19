<!-- agent=cursor:auto cmd-prefix=/home/box/.local/share/cursor-agent/versions/2026.09.15-d2fe57e/node /home/box/.local/share/cursor-agent/versions/2026.09.15-d2fe57e/index.js --model auto -p --output-format text --trust -f --mode ask --workspace /workspace/wt-industry-align-impl <prompt> -->
本轮未读到其他评审员的已完成意见（并行目录里只有 prompt），以下独立取证。本 plan 没有 timeout、budget、锁、重试或 fallback，不需要做 stdlib 行为实验。

## 盲区核对（与本船关系）

- **T+1**：买入日不能卖。日线卖出包在 `t1_sellable` 里（`csv_daily_backtest.py:329-336`）；`pending_exit` 走次日开盘（`:333`），不是当日收盘。分钟扫描另有 `n_days < 1`（`csv_minute_backtest.py:175`）。v7 `_sell_lots` 在无可卖 lot 时返回 0（`csv_minute_backtest_v7.py:229-231`）。本船不重开时点，锚点 `tests/test_ashare_session.py:15-18`、`tests/test_ashare_simulate_predicates.py:87` 指向的就是这两个测试。
- **复权**：日线加载默认 `dividend_type="none"`（`csv_daily_loader.py:96`）。E-R5 已锁 none（`engine-ashare-correctness.md:63`）。本船不改加载。验收里的 `verify_oskh_data_contract.py` 含 adjust 热路径检查（该脚本 `:323-324`）。
- **盈筹**：正文未把 `cyqk` 带进 1–8 书。不适用，保持这样。
- **涨跌停 / 停牌**：档位在 `market_layer.py:17-22`、`:57-65`（20% / 30% / 10% / ST 5% / 其余 None）。停牌是丢零量 K 后走冻仓，不是第二套状态机（日线 `csv_daily_loader.py:83-84`；分钟整日 `ashare_bars.py:369-371`）。
- **包边界**：F-R1 / F-R9 与 `engine-positioning-ssot.md:14-19` 一致。没有把 LEBS / MockQMT / Cerebro 写成实现。

## 🔴 必须修

**R1. §7 冻结命令与 §8 冻结表不是同一份清单。**  
§8 把涨跌停叶子和日线零量过滤算进冻结面：

```193:196:docs/backtest/plan-industry-align-next-2026-09-19.md
| `backtest/research/market_layer.py` | limit/ST leaf semantics used by gate computations |
| `backtest/research/csv_common.py` | shared `book_limit_prices` and calendar helpers on engine path |
| `backtest/research/csv_daily_loader.py` | zero-volume placeholder day filtering feeding freeze/no-trade behavior |
```

§7 的 `git diff --exit-code`（plan `:165-174`）没有这三份文件。按 §7 验收，改 `limit_pct` 把未知板块默认为 10%，或放宽日线 `volume != 0` 丢弃，diff 仍是 0。这正是本船要防的静默改口径。v0.2 changelog 写了「expanded frozen production table」，但验收命令没跟上。切片 C 的 DoD 必须改成：以 §8 全表做 `--exit-code`，禁止两份清单并存。

**R2. 切片 B 的目标文档里，E-R2 仍把 `skip_unknown_board` 写成全路径锁，和已写明的分叉矛盾。**  
正文已经记录分叉：

```36:37:docs/backtest/engine-ashare-correctness.md
已知分叉继续记录：书侧无昨收/未知板块先冻仓；v7 卖侧这两支 `limits=None` 仍放行，
加仓侧同样保留现状，ST 名称仍按窗末名平铺而非 PIT。
```

同一文件的现锁却是全称：

```60:60:docs/backtest/engine-ashare-correctness.md
| **E-R2** | ...其余 **`None` → `skip_unknown_board`，不默认 10%**。 |
```

代码上，谓词在 `limits is None` 时不拦截（`ashare_session.py:73-78`）；v7 持仓止损/加仓/计时卖会继续往下走（`csv_minute_backtest_v7.py:342`、`:367-372`、`:402-404`）。书侧则在解包前 `continue`（`csv_daily_backtest.py:321-323`，仓位循环从 `:325` 起；分钟 `:601-603`，循环 `:609`）。  
切片 B 只说「加上 fork matrix、保留 fail-open」（plan `:117-120`），没有要求改写 E-R2 那一格。实现者会把「现锁」当成要修的 bug，把 v7 收成 fail-closed，直接违反 F-R3。修订时应写明：只收窄「`skip_unknown_board` 仅书路径」；「不默认 10%」保留。这是文档对齐，不是重开撮合。

## 🟡 应修

**Y1. 「书路径 `limits is None` 就拒」不是全部已注册书。**  
`book_limit_prices` 在 `qlib_limit_pct is not None` 时走平带，永不返回 None（`csv_common.py:80-81`）。`topk_dropout` / `topk_score_exit` 注入 `0.095`（`strategy_topk_dropout_rules.py:22`，`csv_strategy_books.py:694`、`:943-955`）。这两本书不会进入 `skip_unknown_board`。  
另外，`csv_minute_backtest_topk_app_dropout.py:152` 调用的是 `simulate_v7`，跟的是 v7 分叉，不是书侧。矩阵里要写成三支，否则切片 A 用 `version6` 钉住的测试会被读成「所有书都 fail-closed」。本船仍然不要改平带，只钉住并排除在「书=拒」之外。`csv_strategy_books.py` 建议补进冻结表，否则有人会顺手删掉这个 hook。

**Y2. 追买的未知板块是先弹出再计数，不是冻着以后再评。**  
无报价才保留 pending（`csv_simulate_loop.py:141-143`）；有报价则先 `pop`（`:145`），然后才 `limits is None` → `skip_unknown_board`（`:155-157`）。池买路径（`:260-261`）没有 pending。plan §2.1 把两处都写成「rejected」，切片 A 若只断言计数，会漏掉「追买单已被丢掉」。测试要分开钉。

**Y3. 「闸门放过」和「没成交」的可观察信号不一样，DoD 没写清。**  
买失败会打 `skip_cash`（`csv_minute_backtest_v7.py:208-210`）。卖侧 T+1 不够时 `_sell_lots` 返回 0，不写事件（`:229-231`）。切片 A 若去找一个不存在的 skip reason，下一步就会改生产代码，违反 F-R5。断言应写成：买 = 有 `skip_cash` 且无 `buy`；卖 = 无 `sell` 事件且仓位仍在。

**Y4. ST 名称分叉的锚不在 §2，切片 B 容易写成空话。**  
书侧按日 `names_asof`（`csv_daily_backtest.py:291`，实现 `csv_common.py:85-106`）：未来 ST 不改更早的档（测试在 `tests/test_csv_daily_backtest.py:934-954`，plan 引的 `:950` 在这个函数体内）。v7 用窗内最后一次名字铺到全程（`ashare_session.py:81-85`、`:97`，CLI 在 `csv_minute_backtest_v7.py:546`）。F-R7 要求把这条记成现状，但 §2 没给这两处行号。矩阵应点名这两个函数，并声明本船不改 PIT。

## 🟢 可选

- plan 里 `:883`、`:901`、`:925`、`:950`、v7 `:202` 都落在对应测试函数内部，不是 `def` 行。函数名分别是 `test_unknown_board_skips_buy`（`:880`）、`test_st_name_uses_five_percent_limit_up`（`:887`）、`test_pool_name_asof_missing_held_code_falls_back_to_yesterday`（`:909`）、`test_pool_name_asof_future_st_does_not_change_earlier_limit`（`:934`）、`test_st_name_uses_five_percent_limit`（`:199`）。实现时按函数名钉，避免行号再漂。
- 验收写 `python3`，CI 用的是 `python`（`.github/workflows/python-tests.yml:40-43`、`:56`）。四个 `scripts/gates/verify_*.py` 与 CI 一致，且都是失败返回 1（例如 `verify_oskh_data_contract.py:336-337`）。本地仍应走 vanna312，不要用系统解释器。
- §7 注释写「only touched contract tests」，命令却跑整文件。可以接受（这些测试是合成数据），不必再缩范围。

## ✅ 做对的地方

- 生产锚点核对过，与当前代码一致：日线 `:321-325`、分钟 `:600-609`、追买/池 `:155-157` 与 `:260-261`、v7 首笔 `priced is None` → `skip_unknown_board`（`:390-391`，且在 `:386-387` 的 `skip_no_prev_close` 之后）、谓词 `:73-78`、`_buy` `:209-210`。
- 卖侧分叉已有测试，plan `:119-134` 正好覆盖 `test_none_limits_sell_side_records_existing_split`（函数在 `:121`）。切片 A 要求另钉加仓侧，这个缺口是真的：该测试只断言卖出。
- 停牌锚不再和零量测试缠在一起：缺 K 净值是 `tests/test_csv_daily_backtest.py:964`；零量不能买卖是 `:990`；标记助手是 `tests/test_daily_mark_cache.py:30-36`（函数从 `:27` 起）。
- 旧 plan 的 P1–P4 就在 `plan-industry-align-refactor-2026-09-18.md:129-132`，且已裁 A。本船默认继续后置，不重开 14:57，这是对的。
- F-R9、OSS 表只作类比、不把 Cerebro/qlib 当证据，与定位文档一致。
- 不在本船把 v7 fail-open 收成书侧 fail-closed。那会改 v7 净值。激进一次到位应落在契约钉死，而不是顺手改撮合。

**总评：** 方向对，零行为变更、只钉书/v7 闸门分叉，可以做。R1（冻结清单与验收命令不一致）和 R2（E-R2 全称与分叉并存）不改之前不要进实现；改完这两处并补上 Y1 的第三支口径后，可以按 A→B→C 做文档和 data-free 测试。
