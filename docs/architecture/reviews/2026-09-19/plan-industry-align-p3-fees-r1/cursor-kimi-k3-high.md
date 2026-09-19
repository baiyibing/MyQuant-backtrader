<!-- agent=cursor:kimi-k3-high cmd-prefix=/home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/node /home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/index.js --model kimi-k3-high -p --output-format text --trust -f --mode ask --workspace /workspace/wt-p3-fees-review <prompt> -->
取证完成。所有关键锚点已对照代码/实验验证，其他三位评审员（grok/codex/cursor-auto）的槽位目前只有 prompt 头、无已完成意见，本评审独立产出。

---

# 评审意见：plan-industry-align-p3-fees-2026-09-19（v0.3.1, delta1 费率契约）

**评审侧重**：实验验证关键行为。并行交叉核对：`_parallel/` 下 grok/codex/cursor-auto 均只有 prompt 头（无完成意见），无条目可引用，独立取证。

## 实验记录（可复现）

**实验 1 · §2.4 两笔 floor 计费单元**（验证 plan "Two lots can pay floor twice"）：

```python
from backtest.research.ashare_fees import QLIB_PORTANA, BILATERAL_10BP, DEFAULT_SCHEDULE, trade_commission
per_call = QLIB_PORTANA.buy_fee(1000) + QLIB_PORTANA.buy_fee(1000)
agg = trade_commission(2000, QLIB_PORTANA.buy_rate, QLIB_PORTANA.min_cost)
```

原始输出：`identity DEFAULT_SCHEDULE is BILATERAL_10BP: True` / `two-lot per-call floor total: 10.0  aggregate-if-merged: 5.0` / `floor doubled: True` / `zero notional: 0.0 neg rate: 0.0`。→ §2.4 断言**属实**；且 v7 卖出按事件聚合（`csv_minute_backtest_v7.py:240-242` 多 lot 合并成一次 `fee.credit_sell(sold * price)`），与账本按 lot 收 floor（`csv_ledger.py:243`）口径不同——plan §2.4 "Same rates may not match book total" 表述准确。

**实验 2 · §8 四个 gate 脚本真实可跑、stdlib-only、data-free**（F-R7）：

```
verify_oskh_data_contract rc=0 / verify_data_path_ssot rc=0
verify_no_hardcoded_machine_paths rc=0 / verify_tr_bridge_import_ssot rc=0
```

（bare python3 3.13，无 pandas/pytest，全部 rc=0）。

**实验 3 · §8 冻结证明命令**：`git diff --exit-code $BASE HEAD -- <10 files>` / worktree / cached 三条全部 rc=0；`git merge-base --is-ancestor` 通过；`origin/master == f548cc2…` 与 `IMPLEMENTATION_BASE` 一致。✓

**实验 4 · import 围栏逃逸面**（P3.3=A "strict fence" 的实际强度，stub pytest 后直接调 `forbidden_imports`）：

```
'import trade_fee_policy' -> [(1, 'trade_fee_policy')]
'from trade_fee_policy import stamp_tax' -> [(1, ...), (1, 'trade_fee_policy.stamp_tax')]
'import trade_decision.trade_fee_policy as f' -> [(1, 'trade_decision.trade_fee_policy')]
"importlib.import_module('trade_fee_policy')" -> []      # 漏
"m = __import__('trade_fee_policy')" -> []               # 漏
```

静态 AST 围栏对一切静态形态（含别名/相对/from）有效，**对动态 import 无效**。

**实验 5 · §8 字面 `python3 -m pytest` 在裸 Linux 环境失败**：本机 `python3 -m pytest` → `No module named pytest`（无 pandas/pytest）。CI 靠 setup-python + pip install 成立（`.github/workflows/python-tests.yml:50-56`），但 §8 未写明此前提。

## 🔴 必须修

无。全部事实锚点（`ashare_fees.py:24/34/53-55`、`csv_ledger.py:15-20/211/243-244`、`csv_daily_backtest.py:230-232/272-280/658-660/683-685`、`csv_minute_backtest.py:549` 无费率覆盖旋钮（grep 零命中）、v7 `:24/204/225/279`、fence 测试 `:46-48/70-76`、§1 两处 cross-plan 引用、SHA）经逐一核对**全部属实**；E-r2-01 断言（predicates 测试无费率断言，grep 仅 2 处无关 `cost`）属实。

## 🟡 应修

1. **QLIB_PORTANA 的 15bp 卖出成本内嵌的是 qlib 历史印花假设（2023-08-28 前的 10bp），当前 A 股印花为卖方单边 5bp**。Slice A 契约表必须加一行注解：15bp = qlib 保真口径（5bp 佣金 + 10bp 旧印花），非当前政策真值；`BILATERAL_10BP` 双边 10bp 是「佣金+印花+过户」的混合代理而非纯佣金。不写明，未来对齐实盘费率时会双重计入印花——这正是小团队「会亏大钱」的校准点。证据：`ashare_fees.py:17-20`（`QLIB_CLOSE_COST = 0.0015`）、`engine-ashare-correctness.md:13` 只写 "5/15bp+最低5" 无分解。
2. **§8 验收脚本缺解释器前提**。仓规（AGENTS.md/python-env）禁止裸系统 python；实验 5 证明裸 `python3` 直接失败。建议 §8 加一行：「本地用解析后的项目解释器（`OSKH_MERGE_PYTHON`/`VANNA312_PYTHON`）；`python3` 仅在 CI setup-python + pip install 后成立」。否则下游照抄命令会卡住。
3. **Slice B 缺一条「分钟 CLI 无 `--qlib-cost` 旋钮」的负向 pin**。F-R3 要求锁定 daily/minute 不对称现状，但 Slice B 只测了 daily 覆盖到达、minute 继承默认值；没有测试防止有人将来给分钟 CLI 悄悄加上同名旋钮（静默改变不对称契约）。一行 `assert "qlib_cost" not in vars(parser.parse_args([]))` 级别的 pin 即可。

## 🟢 可选

4. 围栏为纯静态 AST，动态 import 可逃逸（实验 4）。小团队可接受，但可在 fence 测试里追加 banned-pattern 文本扫描（`import_module(` / `__import__`）补洞，成本极低。
5. 锚点 off-by-one 三处：`ashare_fees.py:9-10`（印花措辞实际在 :8-9）、`csv_ledger.py:244`（卖出佣金计算在 :243，:244 是入账）、`tests/test_ashare_fees.py:10-24`（文件末行 ~:23）。不影响语义，Slice A 落契约表时顺手校正。
6. §8 的 `CURRENT_MASTER != IMPLEMENTATION_BASE → exit 1` 使验收在 master 前进后不可重跑（须先人工记录 drift）。是有意设计，建议脚本注释里点明「fail-hard 是特性」。

## ✅ 做对的地方

- **E-r2-01..06 回写质量高**：§2.4 floor 单元（实验 1 证实）、§2.5 cash-gate 只断言内存 oracle 不动 schema（与 F-R6/P2 锁自洽）、§9 freeze-claim 收窄（E-r2-03）都是教科书级的「文档即 as-built、不夸大证明力」。
- **零行为变更默认 + 三重冻结 diff**（base..HEAD / worktree / cached）覆盖完整，实验 3 证实命令本身正确。
- **F-R8 SHA 纪律**：`f548cc2…` 与 fetched `origin/master` 逐字符一致，且是 HEAD 祖先。
- Slice B 测试清单（default identity / 双边 parity / daily two-state / minute 继承 / v7 pass-through / 两笔 floor oracle）与代码消费面一一对应，无幽灵入口；§8 四个 gate 脚本全部真实存在且 stdlib-only 可跑（实验 2）。
- 必查盲区逐条核对：T+1/涨跌停（`ashare_session.py`/`market_layer.py` 入冻结集、不动语义）✓；复权口径、盈筹率——本 plan 不触碰、无冲突声明 ✓；包边界 F-R5 有真实围栏测试兜底 ✓。

## 总评

事实层零错误、锁与切片自洽、实验可复现，是一份可以照做的 docs-only 契约 plan；唯二实质缺口是 QLIB_PORTANA 印花口径注解（🟡-1）与 §8 解释器前提（🟡-2），均在 Slice A 文档层面即可闭合，不需要 reopen 任何 P3.\*。**结论：修订 🟡 三条后可进实现（Slice A→B→C）。**
