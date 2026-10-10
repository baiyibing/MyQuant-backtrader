DONE

# MyQuant-backtrader 回测性能头脑风暴 · Cursor 独立意见（2026-10-10）

| 字段 | 值 |
|---|---|
| 作者 | Cursor 成员（只读研究，未改代码，未开 PR） |
| 仓库 | `/workspace/MyQuant-backtrader`（已 `git fetch`） |
| master tip | `96927c5`（"Merge branch 'feat/v6-50-53-parking-skim-index' (#450)"） |
| 被评 PR | [#456](https://github.com/baiyibing/MyQuant-backtrader/pull/456) · `perf/v653-numba-resume` · `7ca63b5` · +439/−109 |
| 参考配方 | `--strategy version6_53 --start 20251023 --end 20260909 --cash-total 27000000 --name-budget 10000 --rule-profile industry` |
| 已读文档 | `docs/backtest/note-v653-host-perf-summary-2026-10-10.md`、`docs/backtest/note-independent-ladder-numba-2026-10-09.md` |

**执行限制（必须先说明）**：本沙箱是 Linux 容器，没有 `numba`（`ModuleNotFoundError: No module named 'numba'`），也没有数据湖。所以本报告的一切时间判断都是**代码阅读 + 文档里的已测数字 + 复杂度推演**，没有一条是我本机实测的。所有"预期收益"都标了推演口径，落地前必须按 §5 的方法复测。

---

## 1. 现状：热路径与瓶颈假设

### 1.1 时间现在在哪（口径来自 `profile_sim.json`）

按 `note-v653-host-perf-summary-2026-10-10.md` §3 的两次全窗（产品 `run()`，`PYTHONHASHSEED=0`）：

| 项 | `industry_baseline_h0`（冷缓存） | `industry_resume_h0`（文件缓存命中） |
|---|---:|---:|
| 分钟装载 | 725.7s（写缓存） | **14.9s** |
| 模拟 | 46.1s | **16.6s** |
| └ held_scan | 30.4s (62%) | **8.8s (49%)** |
| └ pool_buy | 6.7s | 3.4s |
| └ post_group | 0.4s | **0.9s（变慢）** |
| 墙钟 | 786.8s | 36.1s |

结论口径：**热缓存下，单次新进程的墙钟 36.1s 里，装载 14.9s > 模拟 16.6s ≈ 同量级**；模拟内部 held_scan 仍是第一名，但 `held_eval_bars` 已从 542,018 压到 16,270，也就是说**剩下的 8.8s 已经不是"扫安静 bar"，而是"每次进/出 Numba 的 Python 包装 + 每个持仓-日的 pandas 取数 + 真动作 bar 的账本"**。

这个转折很关键：上一代优化的靶子（安静 bar 的 Python 循环）已经打掉了，继续在核内部做文章收益有限，**下一刀的靶子应该是"每个 (持仓, 日) 窗口的固定开销"和"装载"**。

### 1.2 分钟日循环的结构性开销（`backtest/research/csv_minute_backtest.py`）

`simulate()` 的 `held_scan` 段（master `:1360-1635`）对每个 `(code, day)` 做一遍：

```1379:1416:backtest/research/csv_minute_backtest.py
                prev_rows = _previous_rows(ddf, day)
                if prev_rows.empty:
                    continue
                ...
                prev_close, did_map = mapped_prev_close(
                    exdiv, code, ds, float(prev_rows.iloc[-1]["close"]), ...
                )
                ...
                prev_closes = prev_rows["close"].astype(float).tolist()
```

三处可疑点，按我读代码的判断排序：

1. **`_previous_rows`（`:913`）是全列布尔掩码**：`df.loc[df.index < day]`，每个持仓-日都新建一个 DataFrame。仓库里**已经有**更快的同义实现 `backtest/research/csv_common.py:22 day_bar_and_prev_closes()`，它用 `idx.searchsorted(day)`，docstring 明确写了"Semantics match: `prev = df.loc[df.index < day]`"。日线引擎 (`csv_daily_backtest.py:633`) 和分钟 `_pool_quote_for` 都用了它，**只有 held_scan 这条最热的路还在用掩码版**。
2. **`prev_rows.iloc[-1]["close"]`** 每次构造一个临时 Series 再取标量；`searchsorted` 版本直接 `close[pos-1]`。
3. **`prev_closes = prev_rows["close"].astype(float).tolist()`** 把全部历史收盘装箱成 Python list。它只喂给 `cursor.daily_closes_ending_yesterday`，而 6.53 走 Numba 核的前提恰恰是 `sell_gate is None`（见 `minute_cash_order.py:391 _independent_skip_supported`，`callable(cursor.sell_gate)` 直接 fail closed）。换句话说**在 6.53 这条默认路径上，这个 list 建出来基本没人读**。

量级推演（不是实测）：`held_codes=20113`，日线窗 ~220 根。pandas 布尔切片 + `.iloc[-1]` + `.tolist()` 这一组，经验上每次 50–150 µs，20113 次 ≈ **1–3s**。在 8.8s 的 held_scan 里是大头之一。

4. **每个持仓-日 4–5 次 `to_numpy` 拷贝**：

```1406:1415:backtest/research/csv_minute_backtest.py
                o = day_m["open"].to_numpy(np.float64)
                h = day_m["high"].to_numpy(np.float64)
                c = day_m["close"].to_numpy(np.float64)
                hm = day_m["hm"].to_numpy(np.int64)
                ...
                low_arr = day_m["low"].to_numpy(np.float64) if need_low else None
```

`day_m` 是 `_slice_day` 的 `iloc` 视图，`to_numpy(np.float64)`（没有 `copy=False`）每次复制 ~240 个元素 + pandas 调用开销。对比 `_pool_quote_for`（`:1853`）已经用了 `mdf["hm"].to_numpy(np.int64, copy=False)[lo:hi]` 的零拷贝写法——同一个文件里两种写法并存。

### 1.3 Numba ladder 热路径（PR 后）

核本身 `_scan_independent_ladder_first`（PR blob `:342-433`）是干净的 `nopython` 数值循环，没问题。问题全在 Python 包装上，**每进一次核**要付：

```472:529:backtest/research/csv_minute_backtest.py
    costs = np.asarray(step_costs, dtype=np.float64)
    idx, peak, peak_hm = _scan_independent_ladder_first(
        np.asarray(cursor.o, dtype=np.float64),
        np.asarray(cursor.h, dtype=np.float64),
        np.asarray(cursor.c, dtype=np.float64),
        np.asarray(cursor.hm, dtype=np.int64),
        float(cursor.cost), float(cursor.peak), int(cursor.n_days), ...
```

- 5 次 `np.asarray` + ~28 次标量装箱 + numba dispatcher 的 29 参数类型匹配；
- `_independent_numba_prefix`（`:532`）里每次**重扫 `st.positions[code]` 重建 `step_costs`**，以及 `scale_anchor` 的 lot 列表推导 + 两次 `sum()`；
- `_independent_numba_blocked`（`:615`）每次读 `os.environ.get("OSKH_INDEPENDENT_NUMBA")` 并重算 `_ladder_numba_params(st)`（4 次 dict 取值 + float 转换）；
- **而且 `_independent_numba_prefix` 内部又调了一次 `_independent_numba_blocked`**，调用方（`_drive_independent_window` `:770`）刚刚才调过——每次 resume 付两遍 env 读 + 两遍 `_ladder_numba_params`。

PR 把"每窗 1 次"变成了"每动作 bar 1 次"。按 `held_eval_bars=16270` + ~20k+ 窗口起始，调用数约 **3.6 万次**；若单次包装 20–40 µs，总计 **0.7–1.5s**。这与文档里 `post_group 0.4s → 0.9s` 的方向一致。

### 1.4 `_drive_independent_window` 里两个纯 Python 的 O(bars) 扫描（PR 新增）

这是我这轮读代码的**最大发现**，也是 `post_group` 变慢最可能的直接原因：

```671:686:backtest/research/csv_minute_backtest.py
    def first_from(idx):
        while idx < n and int(hm[idx]) < hm_lo:
            idx += 1
        if idx >= n or int(hm[idx]) > hm_hi:
            return n
        return idx

    def count_quiet(lo_idx, hi_idx):
        total = 0
        stop = n if hi_idx is None else hi_idx
        for bar_idx in range(lo_idx, stop):
            if int(hm[bar_idx]) > hm_hi:
                break
            if in_window(bar_idx):
                total += 1
        return total
```

两点：

- **`first_from(0)` 在 `post_group` 里是 ~237 次 Python 迭代**（`hm_lo = BUY_HM+1 = 896`，A 股一天 ~242 根，14:55 之后只剩 ~5 根）。而且它在**知道这一窗有没有动作之前**就跑了。旧代码的 `for bar_idx, at_hm in enumerate(cursor.hm)` 虽然也从 0 开始 `continue`，但循环体第一句是 `if python_from < 0 ... break`——**没有动作时旧代码在第 0 根就 break，一根都不走**。新代码反过来，无动作的窗口也要先走 237 步。按 ~2 万个 post_group 窗口算就是 ~500 万次 Python 迭代，≈ **0.5s**，与 `0.4s → 0.9s` 几乎逐字对上。
- **`count_quiet` 是纯埋点**（只喂 `held_numba_prefix_bars` / `held_numba_resume_bars`），却要在 Python 里逐根走过那些"本来就是为了不在 Python 里走"的安静 bar，每根还做两次 `int(hm[...])`（`in_window` 里再取一次）。按 `held_numba_resume_bars=525763` 的量级，这是 **0.3–1s 的纯计数税**。

而 `hm` 在日内是**升序**的（`ashare_bars.read_lake_minute_ohlc:420` 对 DatetimeIndex `sort_index()`，`_frame_from_cache_group:621` 非单调时兜底排序，`_slice_day` 按 ymd 连续 span 切片），窗口 `[hm_lo, hm_hi]` 是连续区间——**两处都可以换成 `np.searchsorted` + 下标减法，结果完全相同**。

### 1.5 bar_store / lake 缓存 / 装载

- 进程内 `bar_store`（`backtest/research/bar_store.py`）已经解决"同进程第二次 `run()`"；跨进程仍是 1.67 GB / 125,781,274 行的 parquet 文件缓存，热读 14.9s。
- `read_minute_cache`（`ashare_bars.py:626`）逐 row group `read_row_group(i)` → `table.to_pandas()` → `_frame_from_cache_group`。**单线程**。pyarrow 的 parquet 解码会放 GIL，这里有现成的并行空间。
- **`ymd` 列是 `pa.string()`**（`_cache_schema`，`ashare_bars.py:520`），`to_pandas()` 后是 **object dtype**。125,781,274 行 × 一个 Python `str` 对象 ≈ 数 GB 的堆对象 + 1 GB 指针。这不只是内存：**几千万到上亿个 GC 可追踪对象会让 CPython 的 gen2 full collection 变得极慢**，而整个日循环期间 GC 会被反复触发。仓库里目前没有任何 `gc.freeze()` / `gc.disable()`（全仓只有 `tests/test_independent_held_order.py` 里的 3 处 `gc.collect()`）。
- 而 `ymd` 在有 `day_spans` sidecar 之后，运行期几乎只被 `build_day_spans`（`bar_store.py:80`）和 `_slice_day` 的无 span 兜底 `_day_arrays`（`:896`）用到。
- 日线侧 `csv_daily_loader.load_daily_bars` 对命中缓存的帧做了**两次** `_normalize_daily_index`（`read_daily_cache:290` 一次，`load_daily_bars:379` 又一次），每次都是 `.copy()` + `.astype(np.float64)`。小钱，但是白给的。

### 1.6 ST / exdiv

两者现在都**不是瓶颈**，这点要明说，免得下一刀打错靶：

- **ST**：`st_status.py` 的表是 `lru_cache` 一次性装载成 `{ymd: frozenset(code)}`，闸门只在 `execute_buy`（`csv_ledger.py:984`）里查一次。单次成本是 `canonical_from_bare_code()` 的字符串处理 + 两次 dict/set 查找。`pool_buy` 热缓存下总共 3.4s，ST 占其中很小一块。
- **exdiv**：6.53 默认 `exdiv_economics=None`，`apply_exdiv_economics`（`csv_ledger.py:727`）第一行就 `return`。`k_for` / `mapped_prev_close`（`exdiv_map.py:82,105`）是两层 dict 取值。`dec3a0b` 已经把除权图按列下推。**这一块我认为不该再动**，任何改动的风险收益比都不划算。

---

## 2. 对 #456 的评价

### 2.1 它做了什么

把 `simulate()` 里两段重复的"前缀 + Python 尾巴"内联循环（morning `:1657-1721` 与 post_group `:1970-1988`）抽成 `_drive_independent_window`，默认在每根 Python 动作 bar 结算后**带 `bar_start` 重新进同一个核**，只把下一根动作 bar 交回 Python。核函数新增 `start` 形参，从 `begin = start if start > 0 else 0` 起扫。

### 2.2 收益

- **算法收益是真的**：`held_eval_bars` 542,018 → 16,270（33×），`held_numba_resume_bars=525763`。这不受缓存热度影响，是纯算法量。
- **结果字节不变**：`trades.csv` / `daily_equity.csv` / `pending_sells.csv` 与基线逐字节相同（文档 §3）。
- **有回退开关**：`OSKH_INDEPENDENT_RESUME=0` 回到"一次前缀 + Python 尾巴"，`OSKH_INDEPENDENT_NUMBA=0` 回到全 Python。两条退路都有测试覆盖。
- **去重**：morning / post_group 两段几乎一样的 60 行循环合并成一个函数，这本身就值。

### 2.3 风险

按我的判断从高到低：

1. **`post_group` 实测变慢（0.4s → 0.9s）**，PR 自己承认了但归因为"重新进核的调用开销"。我认为**主因更可能是 §1.4 的 `first_from(0)` 237 步扫描**，不是 numba dispatch。这个区别很重要：如果归因对了，一行 `np.searchsorted` 就能修；如果归因错了，就会去削不该削的东西。**建议合并前或紧随其后修掉，否则这是一次"局部变慢换全局变快"的净改动，账不干净。**
2. **循环改成了"升序假设 + break"**。旧 morning 循环对窗口外的 bar 用 `continue`（顺序无关），新 `python_tail` / `count_quiet` 用 `break`（依赖 `hm` 升序）。我查下来升序是成立的（§1.4），但这是一条**新引入的隐式不变量，代码里没有断言也没有注释**。建议至少在 `_drive_independent_window` 的 docstring 里写明"requires hm ascending within the slice"，或在 `build_day_spans` 已有的单调性检查旁边补一个对应说明。
3. **`-2` 哨兵语义不对称**：`_independent_numba_prefix` 在 `len(step_costs) > 32` 时返回 `-2 if bar_start else 0`。`bar_start == 0` 时返回 `0`（= "从第 0 根起走 Python"），但在 post_group 下 `start_idx ≈ 237`，靠调用方的 `if python_from < start_idx: python_tail(start_idx)` 兜住。能跑通，但三种返回值（`-2` / `-1` / `>=0`）+ 一个 `0` 的双重含义，读起来很容易出错。建议改成显式的 `(status, idx)` 或具名常量。
4. **每窗 6 个闭包**（`in_window` / `first_from` / `count_quiet` / `dump` / `exec_bar` / `python_tail`）。每个 `(持仓, 日)` 窗口都要新建 6 个函数对象并捕获 cell，~2 万+ 窗口 × 2 段 = 20+ 万次分配。既是时间也是 GC 压力。
5. **`dump()` 只在每窗第一次生效**（`dumped` 标志）。`OSKH_DUMP_CODE` 诊断现在只能看到第一段前缀，后续 resume 段看不到。这是可调试性的小倒退，排查下一次"宿主 DIFF"时会不方便。
6. **正确性侧我没找到真问题**。三道回 Python 的闸（核被关、pending / `side_pending`、`first_exit_attempted`）在每轮循环开头重新判，`position_is_open` 也在每轮判；`pos.group.scale_steps` / `peak_dd_start` / `pos.cost` 都在每次进核前重读。`first_exit_attempted` 之后整段留 Python，避免把动作 bar 之后的高点写进已冻结的峰值——这一条是对的，而且有 `test_resume_freezes_peak_after_deferred_exit` 覆盖。

### 2.4 CI

`pytest-and-gates` **FAILURE**，但这是**继承的红**，不是这个 PR 引入的：

| | 失败 | 通过 |
|---|---:|---:|
| master `96927c5`（run 38015123464） | 328 | 8807 |
| PR #456（run 38020252589） | **328** | **8810** |

失败数一模一样，通过数 +3（正好是 PR 新增的三个测试）。红的内容是 `skip_st` 进了 stats golden、`bar_store` 让 cache status 从 `hit` 变 `mem` 这类**上游已落地改动的 golden 漂移**（`test_off_byte_baseline`、`test_topk_minute_exec`、`test_unified_exit_modeb_load` 等）。

**这条本身是个更大的问题**：master 长期 328 红，意味着"合并门"已经失效了——任何新 PR 都无法用 CI 绿来证明自己无害，只能靠人工比对失败数。建议另开一刀把 golden 批量重录（那是 off-byte 授权问题，不是性能问题，不在本报告范围）。

### 2.5 是否值得合

**值得合，但建议带条件。**

理由：算法收益实打实（Python 评估 bar 降 33×），输出字节不变，有双层回退开关，有新测试，不引入新 CI 红，而且顺带消掉了两段重复代码。

条件（按优先级）：

- **A（强烈建议，合并前或立刻跟进）**：把 `first_from` / `count_quiet` 换成 `np.searchsorted` + 下标减法，让 `post_group` 回到 ≤0.4s。否则这次改动在 profile 上留下一个"说不清的变慢"。
- **B（建议）**：补一个 `held_numba_resume_calls` 计数（进核次数）。现在只有"覆盖了多少 bar"，没有"进了多少次核"，下一刀想分离"核内时间"和"包装开销"时无从下手。
- **C（建议）**：补 docstring 说明 `hm` 升序前提。
- **D（可选）**：`-2` 换成具名常量。

### 2.6 测量建议（对 #456 现有数字的意见）

**现有的 baseline / resume 对比不是干净的 A/B，不能直接当作这刀的成绩**，PR 文档自己也标了"不是锁定比分"，但还可以更严：

- `industry_baseline_h0` 是**冷缓存**那次（分钟装载 725.7s，期间在写 1.67 GB 缓存），`industry_resume_h0` 是**文件缓存命中**那次（14.9s）。这两次的页缓存状态、堆上对象数量、GC 代际都完全不同。文档已经承认 `pool_buy 6.7s → 3.4s` 是缓存热度而非本刀——那么 **`held_scan 30.4s → 8.8s` 里也必然掺了同一份热度红利**，3.5× 这个数偏乐观。
- **干净 A/B 的做法**：同一个进程、同一份文件缓存、同一个 `PYTHONHASHSEED=0`，用 `OSKH_INDEPENDENT_RESUME=0` 和 `=1` 各跑一窗（先跑一次丢弃，让 `bar_store` 和页缓存都热）。只比 `profile_sim.json` 的 `held_scan` / `post_group` / `held_eval_bars`，不比墙钟。两次的 `trades.csv` / `daily_equity.csv` / `pending_sells.csv` 必须逐字节相同。
- **算法量是可信的**：`held_eval_bars 542018 → 16270` 和 `held_numba_resume_bars=525763` 不受缓存影响，建议把这两个数（而不是秒数）写成这刀的主指标。
- **覆盖面**：现在只在 6.53 + `industry` 上验过。`per_name` 独立持仓梯子族还有 6.1 / 8.x / 其他 6.x，`_ladder_numba_params` 对它们同样会返回非 None。建议至少再挑一本（比如 8.3，它多一条 `_session_confirm_peak` 路径）做一次字节对照，确认 resume 不是只在 6.53 的参数组合下恰好对齐。

---

## 3. 下一刀清单

每条给：改哪里 / 预期收益（推演口径）/ 风险 / 是否改结果字节 / 怎么测。

### P0-1 · `first_from` / `count_quiet` 改 `np.searchsorted`

- **改哪里**：`csv_minute_backtest.py` `_drive_independent_window`（PR blob `:671-686`）。`lo = np.searchsorted(hm, hm_lo, side="left")`、`hi = np.searchsorted(hm, hm_hi, side="right")`，窗口内连续，于是 `count_quiet(a, b) == b - a`，`first_from(i) == max(i, lo)`（且 `>= hi` 即结束）。两个边界每窗算一次即可。
- **预期收益**：`post_group` 0.9s → ≤0.4s（回到回归前）；`held_scan` 再省 0.3–1s。全窗模拟 16.6s → **~15s 量级**。推演口径：~2 万窗口 × ~237 步 + ~53 万根 resume bar 的计数循环。
- **风险**：低。唯一前提是 `hm` 日内升序——这是 `_slice_day` + `sort_index()` 已经保证的，且 `build_day_spans`（`bar_store.py:81`）本来就拒绝非单调的 `ymd`。建议同时加一个便宜的调试断言（只在 `OSKH_*` 调试开关下生效）。
- **改结果字节**：**否**。只改计数与下标定位，不改任何谓词。
- **怎么测**：同进程 A/B（改前 / 改后），`trades.csv` / `daily_equity.csv` / `pending_sells.csv` 逐字节相同，且 `held_numba_prefix_bars` / `held_numba_resume_bars` / `held_eval_bars` 三个计数完全一致（这是比字节更敏感的回归闸）。

### P0-2 · held_scan 换用 `day_bar_and_prev_closes`，并把 `prev_closes` 改懒算

- **改哪里**：`csv_minute_backtest.py:1379-1416`。用 `csv_common.py:22 day_bar_and_prev_closes()`（searchsorted，语义已在 docstring 里对齐）替代 `_previous_rows` + `.iloc[-1]["close"]`；`prev_closes` 只在 `sell_gate`/`take_profit` 真的会读时才 `.tolist()`（6.53 这条路 `sell_gate is None`，整个 list 可以不建）。`:1666-1669` 的 `_chase_quotes_for` 同理。
- **预期收益**：held_scan 省 **1–3s**（8.8s 的 15–30%）。推演口径：20113 次 × (布尔掩码切片 + 临时 Series + 全量 tolist) ≈ 50–150 µs/次。
- **风险**：中低。`prev_rows.empty → continue` 这条**跳过条件**必须原样保留（`pos == 0` 等价）；`day_bar_and_prev_closes` 还额外要求 `day` 在 index 里（上面已有 `day not in ddf.index: continue`，等价）。懒算要确保所有消费方（`sell_gate` / `buy_gate` / `take_profit` / v9 plan）都走同一个入口。
- **改结果字节**：**否**（前提是跳过条件和 `prev_close` 取值逐一对齐）。
- **怎么测**：先对 6.53 做字节对照；再跑一本 `sell_gate` 非 None 的书（例如策略 4，`strategy4_rules.py:25 buy_gate` 会读 `daily_closes_ending_yesterday`）确认懒算路径没少喂数据。`tests/test_off_byte_baseline.py` 的那一批（虽然当前红，但失败数必须不变）。

### P0-3 · 装载后 `gc.freeze()`

- **改哪里**：`run()` 在 `load_minute_bars` / `load_daily_ohlc` 之后、`simulate()` 之前，插 `gc.freeze()`（把已有的上亿个对象移进 permanent generation，之后的 full collection 不再遍历它们）。可用 `OSKH_GC_FREEZE=0` 关。
- **预期收益**：这条我**最没把握也最可能最大**。堆上有 ~1.26 亿个 `ymd` 字符串对象（§1.5），CPython 的 gen2 full collection 要遍历全部可追踪对象。日循环期间会触发多次，单次可能是**秒级**。如果真触发了，这是一行代码换几秒。如果 pyarrow 对短字符串做了某种复用导致对象数远低于估计，收益可能接近 0。
- **风险**：低。`gc.freeze()` 不改语义，只改 GC 的扫描集。注意**不要**用 `gc.disable()`（会漏掉循环引用，长跑可能涨内存）。
- **改结果字节**：**否**。
- **怎么测**：先**不改代码**测量——用 `gc.callbacks` 或 `py-spy dump` / `py-spy record` 对一窗采样，看 `collect` 在火焰图里占多少。确认有料再改。改后同进程 A/B，比 `wall_s` 与 `day_loop`。

### P1-1 · `_independent_numba_prefix` 包装瘦身

- **改哪里**：`csv_minute_backtest.py:532-603` + `:615`。四件事：
  1. 去掉 `_independent_numba_prefix` 内部对 `_independent_numba_blocked` 的**重复调用**（调用方刚调过）；
  2. 环境开关（`OSKH_INDEPENDENT_NUMBA` / `OSKH_INDEPENDENT_RESUME` / `OSKH_DUMP_*`）在 run 启动时读一次缓存成模块级/状态级常量，别每 bar `os.environ.get`；
  3. `_ladder_numba_params(st)` 每 run 算一次（`st.stats` 在 run 内不变）；
  4. `step_costs` / `scale_anchor` / `scale_steps` 在同一窗内缓存，只在"本窗发生了成交"时失效重算——现在是每次 resume 都重扫 `st.positions[code]`。
- **预期收益**：模拟再省 **0.5–1.5s**。推演口径：~3.6 万次进核 × 省 15–30 µs/次。
- **风险**：中。第 4 点要小心：`scale_steps` 在 `scale_out_exits` 成交后会变，`peak_dd_start` 在 `peak_dd_clear_exits` 里会被改成 `None` 或 `day_i`，`pos.cost` 在加仓后会变（加仓在 `pool_buy` 阶段，不在 held_scan 窗口内，但 post_group 窗口在 `pool_buy` 之后）。**保守做法：只缓存"本窗无成交"时的值，一有 `_sell` 就全部重算。**
- **改结果字节**：**否**。
- **怎么测**：字节对照 + 三个计数一致；另外加一条单测，构造"resume 之间发生 scale_out → `scale_steps` 必须被重读"的场景（PR 里的 `test_resume_matches_python_across_quiet_scale_gaps` 已有雏形，断言 `group.scale_steps == 2`）。

### P1-2 · 核一次返回多个候选动作 bar

- **改哪里**：`_scan_independent_ladder_first` 增加一个输出数组，单次扫描返回最多 K（比如 32）个**候选**动作 bar 下标 + 各自的前缀峰值；`_drive_independent_window` 依次交给 Python，只在某根 bar **真的改了状态**（成交 / 闩锁变更 / `first_exit_attempted`）时才重新进核，否则直接用下一个候选。
- **预期收益**：把 §1.3 的包装开销摊薄到 1/K。模拟再省 **0.5–1s**。
- **风险**：中高。必须严格论证"候选 bar 未改状态 ⇒ 后续候选与重扫等价"。`peak_dd` 的闩锁（`dd <= 0` 清零、`dd >= peak_dd` 置位）本身就是状态变更，核已经把这几种情况都当作"交回 Python"，所以大部分候选都会改状态——**K 的实际收益可能远低于理论值**。
- **改结果字节**：**否**（如果论证成立）。
- **怎么测**：先加 P1-1 的 `held_numba_resume_calls` 埋点，统计"连续两个候选之间没有成交"的占比。**如果这个占比 < 30%，这刀不值得做，直接放弃。** 这是一条"先测后做"的建议，不是直接动手。

### P1-3 · 每码分钟数据改列式 numpy 常驻，日切片变零拷贝视图

- **改哪里**：装载后为每个 code 建一份连续的 `open/high/low/close` `float64` 和 `hm` `int64` numpy（`np.ascontiguousarray`），放进 `bar_store`。`_slice_day` 的消费方（held_scan `:1406-1415`、`_pool_quote_for`、`_chase_quotes_for`、`_volume_bucket_for`）改成 `arr[lo:hi]` 视图。
- **预期收益**：held_scan 省 **0.5–1.5s**（消掉 20113 × 4–5 次 `to_numpy` 拷贝）；`independent_ladder_first_bar` 里的 `np.asarray` 变成真正的零成本；`pool_buy` 也顺带受益。另外**省内存**：DataFrame 的 BlockManager + object `ymd` 可以在建完 numpy 和 spans 之后释放。
- **风险**：中高。`_slice_day` 现在返回 DataFrame，被 `_chase_quotes` / `_open_quote_for` / `run_chronological_day` 的 `slice_day` lambda（`:1543`）/ v11 / v12 / tail-window 等多处用 `.loc` 消费。这是一次**接口面改动**，必须一次性改干净，否则两套表示会漂。建议按消费方分片推进，先只改 held_scan 这一条最热的路，`_slice_day` 保持不变。
- **改结果字节**：**否**（数值完全相同，只是避免拷贝）。注意 pandas 多列 float64 block 的列视图是 strided 的，喂 numba 前要确认是 C 连续，否则 njit 会退化到 A-layout 签名——这也是建议**预先 `ascontiguousarray` 一份**而不是直接用 `to_numpy(copy=False)` 的原因。
- **怎么测**：字节对照；另外用 `arr.flags['C_CONTIGUOUS']` 断言，并确认 numba 没有为新签名重新编译（`_scan_independent_ladder_first.signatures` 长度不变）。

### P1-4 · `read_minute_cache` 并行 row group + 不再把 `ymd` 变成 Python 字符串

- **改哪里**：`ashare_bars.py:626 read_minute_cache`。两件事：
  1. 用 `ThreadPoolExecutor` 并行 `read_row_group(i)` + 转换（pyarrow 解码放 GIL；写 `out` dict 时加锁或按序归并，**归并顺序必须确定**）；
  2. `ymd` 不要走 object dtype：要么 `to_pandas(strings_to_categorical=True)`，要么直接从 arrow 列算出 `int32` 的 ymd，要么在 `resolve_day_spans` 建完 spans 之后就把这一列丢掉。
- **预期收益**：分钟装载 14.9s → **5–8s**（跨进程每次新 `run()` 都省）。内存降几个 GB，并与 P0-3 叠加（对象数掉几个数量级后，GC 问题自动消失）。
- **风险**：中。`ymd` 还有 `_day_arrays` 兜底（`:896`）、`csv_minute_volume.py:35`、`strategy7_engine.py:464` 三个消费方；丢列前必须保证 spans 一定存在，否则 `_slice_day` 会静默返回 `None`（**这是一条危险的静默失败路径**，丢列方案必须改成 fail-closed）。并行归并顺序必须确定，否则 `out` 的插入序会变（虽然下游用 `held_codes(st)` 排序遍历，但不要赌）。
- **改结果字节**：**否**。但注意：如果改 `_cache_schema`，`minute_cache_identity` 的 `schema` 哈希会变 → 缓存指纹变 → **会触发一次 ~725s 的全量重建**。所以**优先选"读时处理"方案（`strings_to_categorical` / 读后丢列），不要改 schema**。
- **怎么测**：对同一份 1.67 GB 缓存，改前后各读一次，比 `len(out)`、每码 `len(frame)`、`resolve_day_spans` 结果字典完全相同；再跑一窗全窗比字节。

### P2-1 · `load_daily_bars` 去掉重复 `_normalize_daily_index`

- **改哪里**：`csv_daily_loader.py:290` 与 `:379`，命中缓存的帧被 `.copy()` + `.astype(np.float64)` 两遍。
- **预期收益**：日线装载省零点几秒。小。
- **风险**：低。注意从湖直读（非缓存）的分支仍需要归一化。
- **改结果字节**：否。
- **怎么测**：装载计时 + 帧 `.equals()` 对照。

### P2-2 · `_drive_independent_window` 的闭包改成模块级函数 / 小类

- **改哪里**：PR blob `:634-803`。6 个闭包改成接受显式参数的模块级函数，或一个可复用的轻量对象（每日循环复用一个实例）。
- **预期收益**：~20 万次函数对象分配省掉，**0.1–0.3s** + 少一点 GC 压力。小，但和 P0-1 / P1-1 在同一个函数里，可以一刀带走。
- **风险**：低，纯重构。
- **改结果字节**：否。
- **怎么测**：字节对照 + 计数一致。

### P2-3 · ST 闸查表走已规范化的 code

- **改哪里**：`st_status.py:71 is_st_on` 每次调 `canonical_from_bare_code(str(code))`。`execute_buy` 传进来的 `code` 在引擎里已经是 canonical 形式了，可以加一条"已规范化"的快路径（先直接查，miss 再规范化重查），或给 `canonical_from_bare_code` 加 `lru_cache`。
- **预期收益**：`pool_buy` 省零点几秒。小。
- **风险**：低。但**不要把"规范化"这个语义本身去掉**——ST 表的 code 来自 Wind，格式不保证。只能加快路径，不能改口径。
- **改结果字节**：否。
- **怎么测**：`tests/test_st_status.py` 全绿 + `skip_st` 计数不变。

### P2-4 · 已被人裁否决、本报告不再提的方向

为了避免下一个 agent 重复踩：**安静 bar 启发式跳过**（`c8d3021` 已删，全窗成交漂移）、**把账本 / `execute_buy` 编进 Numba**、**GPU / 4090**、**现有 parquet 改 mmap**、**"改用 Arrow 就比 DataFrame 快"**——这五条 `note-v653-host-perf-summary-2026-10-10.md` §4 已经结过账，不要再开。

### 优先级汇总

| | 项 | 预期收益（推演） | 风险 | 改字节 |
|---|---|---|---|---|
| P0-1 | searchsorted 替掉两个 Python 扫描 | post_group −0.5s，held_scan −0.3~1s | 低 | 否 |
| P0-2 | `day_bar_and_prev_closes` + 懒算 prev_closes | held_scan −1~3s | 中低 | 否 |
| P0-3 | 装载后 `gc.freeze()` | 未知，可能秒级；先测后做 | 低 | 否 |
| P1-1 | 进核包装瘦身 | 模拟 −0.5~1.5s | 中 | 否 |
| P1-2 | 核一次返回多候选 | 模拟 −0.5~1s；**先测占比再决定** | 中高 | 否 |
| P1-3 | 每码列式 numpy + 零拷贝切片 | held_scan −0.5~1.5s + 省内存 | 中高 | 否 |
| P1-4 | 并行 row group + ymd 不落 object | 装载 14.9s → 5~8s | 中 | 否 |
| P2-1 | 日线缓存去重复归一化 | 小 | 低 | 否 |
| P2-2 | 闭包改模块级 | 0.1~0.3s | 低 | 否 |
| P2-3 | ST 查表快路径 | 小 | 低 | 否 |

**建议的落地顺序**：P0-1 + P2-2（同一个函数，一刀）→ P0-2 → 先做 P0-3 的测量 → P1-1 → P1-4 → (看数据决定 P1-2 / P1-3)。**不要把"模拟"刀和"装载"刀放进同一个改动**（文档 §5 已经明说，我同意）。

---

## 4. 绝不动

### 4.1 正确性 / 行业规则 / 决策价

- **成交核与档位**：`docs/backtest/engine-ashare-correctness.md` 的档位、全卖因跌停、Decimal 涨跌停价。`ashare_session` 的 `LIMIT_EPS` / `hit_limit_down` / `hit_limit_up` 不碰。
- **T+1（含红股锁定）**：`t1_sellable`、`_locked_bonus`（`csv_ledger.py:751`）、`|t1_deferred` 追加语义。
- **跌停顺延 / `defer_sell_limit_down`**：`defer_sell_open_or_fill` / `record_limit` 的调用时机与计数口径。`79de799` 刚修完的"开盘跌停不再让 Numba 丢掉收盘计数"不要回退。
- **决策价与报价时点**：14:55 买价的 exact/fallback 规则（`_buy_px_from_arrays` `:1113`，先找 `hm == BUY_HM`，否则取 14:30–14:55 的最后一根 close，**绝不借后面的 bar**）；`minute_open` 的 09:30 精确开盘（`_open_quote_for` `:1149`，"a missing opening bar never borrows a later row"）；`_chase_quotes` 的 09:45 规则。`docs/backtest/minute-fill-policy-ssot.md` 是 SSOT。
- **一手取整 / 零股 / 费用 / 科创板申报量**：`lot_rounding`、`ashare_fees`、`star_lot_declare_check`。
- **`first_exit_attempted` 之后峰值冻结**：`HeldMinuteCursor.advance`（`minute_held_scan_core.py:145`）首句 `if self.first_exit_attempted: return None`。resume 必须在这之后整段留 Python。

### 4.2 决定性 / 遍历序（这是上一刀用血换来的）

- `held_codes(st)` 按代码排序（`csv_ledger.py:438`，"Cash-competing loops must not use insert order"）、`s8_open_groups` 按 `position_id`、指数买回按 `position_id`、抽离按 `(code, entry_idx, lot_id)`。
- **对象身份不得回退到 `id(pos)`**：`lot_identity(pos)`（`csv_ledger.py:495`，"Not CPython's recycled `id(pos)`"）、`held_fill_key`、停泊登记、`ExDivEconomics` 的 `peek_locks` / `locks_for` / `pop_locks`。任何性能优化**不许**为了做 dict key 而换回整数地址。
- 现金竞争顺序（谁先拿到现金）。任何"把循环换成向量化/并行"的想法，**凡是涉及现金或名额竞争的循环一律不动**。

### 4.3 范围 / 流程

- **不开新策略版本号**（`.cursor/rules/strategy-version-approval.mdc`）。性能刀落在当前这本上。
- **6.53 仍在 `PENDING_BOOK_NAMES`**，不录 golden，不用这些 NAV 覆盖 `_opt` / `_prof`。
- **HELP_LOCK / CLI `main()` 字节冻结**。埋点只走 `run()` + `OSKH_PROFILE_SIM`。
- **默认经济除权保持关**（`exdiv_economics=None`）。
- **热路径固定清单**由 `tests/test_ashare_simulate_import_fence.py` 锁定，不许扩成 research 全目录扫描。
- **不碰 L2 篱笆**（`l2_analytics/` 只做离线研究 ETL），不碰 LEBS / MockQMT（那在 1.3）。
- **本仓对行情只读**，新代码走 resolver（`resolve_period_root` 等），不写死盘符，缺数据就报错不返回空表。

---

## 5. 复跑与验收清单（给下一刀）

```text
set PYTHONHASHSEED=0
D:\anaconda3\envs\vanna312\python.exe -u backtest/research/csv_minute_backtest.py ^
  --strategy version6_53 --start 20251023 --end 20260909 ^
  --cash-total 27000000 --name-budget 10000 --rule-profile industry ^
  --out-dir backtest_output\csv_minute_v6_53_20251023_20260909_industry_<stamp>
```

验收四条，缺一不可：

1. **字节**：`trades.csv` / `daily_equity.csv` / `pending_sells.csv` 与对照逐字节相同。
2. **计数**：`profile_sim.json` 的 `held_eval_bars` / `held_numba_prefix_bars` / `held_numba_resume_bars` / `held_numba_slices` / `held_codes` / `defer_sell_limit_down` / `skip_st` 全部相同。**这比字节更敏感**，能抓到"成交碰巧没变但扫描路径变了"。
3. **分相**：只比 `profile_sim.json` 的 `phases_s`，**不比墙钟**。对照必须是**同一进程或同一份热文件缓存**下的两次（`OSKH_*` 开关 A/B），不能拿冷缓存那次当 baseline。
4. **开关**：每刀都要有 env 回退开关，且回退路径有测试覆盖（照 `OSKH_INDEPENDENT_RESUME` / `OSKH_BAR_MEM` / `OSKH_INDEPENDENT_NUMBA` 的样子）。

另外两条流程意见：

- **CI 现在 328 红**（master 与 PR 同数）。在把 golden 重录干净之前，每个 PR 的 CI 结论只能是"失败数与 master 相同 + 通过数 ≥ master"。建议把这条写进 PR 模板，否则迟早有人把真红混进继承红里。
- **测量之前先采样**：P0-3（GC）和 P1-2（多候选）都是"先测后做"。`py-spy record --native` 对一窗采样不需要改代码，比继续靠 `clock.begin/end` 加分相更快找到真正的叶子。

---

## 附：本报告引用的事实锚点

| 事实 | 出处 |
|---|---|
| PR 内容、`bar_start` / `-2` / `OSKH_INDEPENDENT_RESUME` | `git show 7ca63b5 -- backtest/research/csv_minute_backtest.py` |
| `_drive_independent_window` 及 6 个闭包 | PR blob `csv_minute_backtest.py:634-803` |
| `first_from` / `count_quiet` 的 Python 扫描 | PR blob `csv_minute_backtest.py:671-686` |
| 核函数 `_scan_independent_ladder_first` | PR blob `csv_minute_backtest.py:342-433` |
| 进核包装 `independent_ladder_first_bar` / `_independent_numba_prefix` | PR blob `csv_minute_backtest.py:472-603` |
| 回 Python 的三道闸 | `minute_cash_order.py:391 _independent_skip_supported`；`csv_minute_backtest.py:615 _independent_numba_blocked` |
| 峰值冻结 | `minute_held_scan_core.py:113,145,160` |
| held_scan 的 `_previous_rows` / `tolist` | master `csv_minute_backtest.py:913,1379,1393,1416` |
| 已有的 searchsorted 同义实现 | `csv_common.py:22 day_bar_and_prev_closes` |
| 每持仓-日 `to_numpy` 拷贝 | master `csv_minute_backtest.py:1406-1415` |
| 零拷贝写法的对照 | master `csv_minute_backtest.py:1853` |
| 分钟缓存读与 `ymd` string schema | `ashare_bars.py:520,614,626` |
| day spans sidecar / 进程内 store | `bar_store.py:76,111,162` |
| 日线缓存重复归一化 | `csv_daily_loader.py:290,379` |
| ST 闸 | `st_status.py:57,71,112`；`csv_ledger.py:984` |
| exdiv | `exdiv_map.py:82,105`；`csv_ledger.py:727` |
| 遍历序 / 对象身份 | `csv_ledger.py:438,495` |
| 已测分相数字 | `docs/backtest/note-v653-host-perf-summary-2026-10-10.md` §3 |
| 已否决方向 | 同上 §4 |
| CI 失败数 master 328/8807 vs PR 328/8810 | GH Actions run `38015123464` / `38020252589` |
