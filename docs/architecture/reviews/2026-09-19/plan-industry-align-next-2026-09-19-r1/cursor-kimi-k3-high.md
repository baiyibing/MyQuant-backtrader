<!-- agent=cursor:kimi-k3-high cmd-prefix=/home/box/.local/share/cursor-agent/versions/2026.09.15-d2fe57e/node /home/box/.local/share/cursor-agent/versions/2026.09.15-d2fe57e/index.js --model kimi-k3-high -p --output-format text --trust -f --mode ask --workspace /workspace/wt-industry-align-impl <prompt> -->
取证完成。所有关键锚点已逐条核对，验收命令中可执行部分已跑最小实验。其他评审员（grok/codex/cursor-auto）的产出文件目前只有 prompt 头、尚无完成意见，故本评审独立完成。注：当前为 Ask 模式，我无法写入 `_parallel/cursor-kimi-k3-high/` 文件，评审意见直接输出于此。

---

# 评审意见：plan-industry-align-next-2026-09-19（v0.2）

## 取证与实验记录（先于结论）

**锚点核对（全部读码验证）**：

| Plan 断言 | 结果 |
|---|---|
| `csv_daily_backtest.py:321-323` limits=None→skip_unknown_board+continue，持仓循环 `:325` | ✅ 精确 |
| `csv_minute_backtest.py:600-603` 同上，循环 `:609` | ✅ 精确 |
| `csv_simulate_loop.py:155-157` / `:260-261` | ✅ 精确 |
| v7 `:390-391` priced is None→skip_unknown_board（首入 `hm==895` 即 14:55，`:381`） | ✅ 精确 |
| v7 持仓卖/加/计时退出 `:342-353`/`:367-373`/`:402-405` + 谓词 `ashare_session.py:73-78`（`limits is not None and …` → None 时不拦截） | ✅ 精确，fail-open 属实 |
| `_buy` skip_cash `:209-210`、`_sell_lots` 返 0 `:229-231`（F-R4 两层状态） | ✅ 精确 |
| `limits=None` 来源：`ashare_session.py:67-69`（previous None）+ `market_layer.py:77-79`（未知板块） | ✅ |
| IMPLEMENTATION_BASE `41f3d11…` | ✅ 实验：`cat-file -t`=commit；是 `origin/master` tip；`merge-base --is-ancestor` exit 0 |
| 板块档位 10/20/30 + ST 5% + 北交 920/430/83/87/88 | ✅ `market_layer.py:18-22,43-62` |

**实验 1（data-free gate 可执行性）**：裸 `python3`（本 VM 3.13.5，无 pandas）逐一跑 §7 step 2 四个脚本：

```
verify_oskh_data_contract        exit=0  "oskh_data contract: OK"
verify_data_path_ssot            exit=0  "violations=0"
verify_no_hardcoded_machine_paths exit=0 "OK: no executable machine-path hardcodes"
verify_tr_bridge_import_ssot     exit=0  "OK (shim→oskh_factors.bridge…)"
```

四个脚本均无第三方依赖、各 <1s、全部 exit 0 —— 与 CI 中「pip 之前跑 gate」的位置（`python-tests.yml:38-43` 先于 `:50` pip install）一致，"data-free" 声明属实。

**实验 2（pytest 步骤环境前提）**：同一裸 `python3` 跑 §7 step 1 → `No module named pytest`（pandas 也没有）。CI 里 pytest 在 pip install 之后（`python-tests.yml:54-55`），且 `-m "not production and not benchmark"` 与 plan 逐字一致、两个 marker 已在 `pytest.ini:5,8` 注册。结论：命令本身正确，但 §7 未写环境前提（见 🟡-3）。

## 🔴 必须修

**R1. §7 冻结检查清单与 §8 冻结表不一致（9 vs 12），可执行证明漏掉本船最核心的叶子文件。**
§8 冻结表 12 个文件；§7 step 3 `git diff --exit-code` 只列 9 个，**漏掉 `market_layer.py`、`csv_common.py`、`csv_daily_loader.py`**。其中 `market_layer.py` 正是 ST/板块/`limit_pct` 语义叶子（本船契约化的对象本身），`csv_common.py:73` 是 book 路径 `book_limit_prices` 本体。Slice C DoD 要求「freeze diff check is clean」，实现者照 §7 执行会得到一份不覆盖 gate 语义叶子的「冻结证明」——静默改动 `market_layer.py` 也能通过验收。修法：§7 清单与 §8 表逐字对齐（或由 §8 表机械生成）。

## 🟡 应修

**R2. 冻结闭包不对称：`exdiv_map.py` 与 `strategy7_rules.py` 在 gate/fill 路径上却未冻结。**
- `ashare_session.py:22` 与 book 两引擎均 `from backtest.research.exdiv_map import … mapped_prev_close`——昨收映射直接决定 `limit_prices` 输入，改它即改 gate 边界，影响不亚于已冻结的 `csv_daily_loader.py`。
- v7 的 `stop_decision / ladder_decision / timer_due / in_add_window` 来自 `strategy7_rules`（`csv_minute_backtest_v7.py:29`），本船 Slice A 要 pin 的「v7 持仓卖/加 fail-open」行为一半由该模块决定；而冻结表收了地位相当的 `strategy5_rules.py`（§8 末行）。
二选一：把两者补进冻结表，或在 §8 加一行明确的排除理由（如「策略层规则不属于 gate 契约，由 Slice A 测试间接锁定」）。当前状态是表内自相矛盾。

**R3. §2.3 测试锚点行号漂移。** 引用 `test_csv_daily_backtest.py:883/:901/:925/:950` 为 ST/board gating；实际 `def test` 在 `:880`（unknown_board）、`:887`（ST 5%）、`:909`（asof fallback）、`:934`（future ST PIT），另有北交 30% 用例 `:957` 未被引用。引用行落在测试体内，不是用例入口。测试行号天然易漂移，建议 §2.3 改用「测试名 + 近似行号」（如 `test_pool_name_asof_future_st_does_not_change_earlier_limit` ≈:934），源码锚点（§2.1/§2.2）本次核对全部精确、可保留行号。

**R4. §7 缺 Python 环境前提。** 实验 2：裸 Linux `python3`（3.13.5，无 pytest/pandas）下 step 1 立即失败。CI 顺序是 gate（pip 前）→ pip install → pytest。§7 应写明：「step 1 需在 `pip install -r requirements.txt` 之后、CI 等价 Python 3.12 环境执行；step 2 的四个 gate 无依赖、可在任意 python3 下先跑」（已实验证实）。否则实现者在干净 Linux VM 上会误判为 plan 命令错误。

## 🟢 可选

**R5.** §4 把 P1–P4 表述为待裁「Decision point + Default recommendation」，但源 plan 已记录「已裁 A/A/A/A、已人裁 GO」（`plan-industry-align-refactor-2026-09-18.md:126-134`）。建议改为「re-confirming prior cuts」，避免下游误读为重新开放裁口。

**R6.** Slice A 可按名显式纳入 ST PIT 回归用例 `test_pool_name_asof_future_st_does_not_change_earlier_limit`，与 F-R7「ST PIT 不改、只文档化」形成正面对锁。

**R7.** §7 用 `python3`，CI 用 `python`（setup-python 后）；Linux 下无碍，但 Windows 开发机无 `python3`。加一句「Windows 上用解析后的 vanna312 解释器」即可闭环。

## ✅ 做对的地方

- **§2.1/§2.2 全部源码锚点逐一核对精确**（含 v7 三个持仓路径与谓词 None-safe 语义），fail-open/fail-closed 分叉描述与代码事实一致。
- **F-R4（gate 未拦截 ≠ 成交）有代码实据**：`skip_cash`（`:209-210`）与 T+1 不可卖返 0（`:229-231`）——这是本船最有价值的契约化点。
- **Slice A 准确识别缺口**：现有 `test_none_limits_sell_side_records_existing_split`（`test_ashare_simulate_predicates.py:121-134`）只 pin 卖侧 fail-open，加侧确实是新断言，plan 没有虚报已有覆盖。
- **验收序列与 CI 同构且经实验证实可跑**：四 gate data-free、exit 0、无依赖（实验 1）；marker 过滤与 CI 逐字一致。
- **IMPLEMENTATION_BASE 经实验验证**为 `origin/master` tip 且是 HEAD 祖先；F-R10 的 40-char SHA 纪律正确。
- **必查盲区逐条过**：T+1（`t1_sellable` 严格次日，`test_ashare_session.py:15-18`；`pending_exit` 次日开 `:329-333`）、涨跌停档位/北交/ST、零量停牌冻结（`:990` 测试在）、无 cyqk/adjust_type/Cerebro/LEBS 越界（F-R1/F-R9 显式禁）。docs-only + F-R5/F-R6 与「零行为变化」主目标自洽。

## 总评

事实层质量高：所有源码锚点经独立核对无误，gate 脚本经实验证实 data-free 可跑，分叉语义描述与代码一致。**唯一硬伤是 R1**——可执行冻结证明漏掉 `market_layer.py` 等 3 个文件，不修则 Slice C 的「冻结证明」名实不符；R2 的冻结闭包不对称建议同轮补齐。**修掉 R1（并顺手处理 R2–R4）后可进实现**；在 R1 未修前，Slice C 的 DoD 不可判 GO。
