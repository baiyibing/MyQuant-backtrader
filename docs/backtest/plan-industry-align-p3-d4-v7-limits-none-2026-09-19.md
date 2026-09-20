# Plan: industry-align P3 δ4 v7 limits=None contract (2026-09-19)

> **状态交叉引用（2026-09-20）**：Human GO P2=B 仅授权书 trades 的 `session_phase` / `price_rule` 两列，覆盖本文历史 P2 延后记录；P1 已 closed as A，P4 仍 deferred，本文 δ 合同不重开。见 [schema SSOT](engine-ashare-correctness.md#p2-trades-标签列human-go-b2026-09-20)。
> **Status**: **v0.4 · production fail-closed landed · Slice A→B→C 已通过（§8.4） · Human GO C/B/A（2026-09-19，Asia/Shanghai）**。仅 v7 held stop/add/timer 新增 None 早拒；共享门函数、书侧、首开及其它生产路径冻结。实现与验收完成；feat commit `0975e572d2d35f5bc92d1f5db5ccf433c80dd65f` 已落地（host 补提交），由 host 推送/开 PR。
> **Main ship / 单行范围**: `limits=None`（无昨收 / 未知板块）时拒绝所有交易尝试；复用 source reason，不冻结 peak / last_prices / mark / 除权参考价缩放。
> **IMPLEMENTATION_BASE**: `073538d4486a07a71f561631c3f274ffa06eeecb`（#128 merge tip，post δ6 docs；本 feat 起点已由 `git rev-parse HEAD` 核实）。历史 A 基线与验收见 changelog，不用于本轮冻结证明。
> **Human GO recorded**: **P3δ4.1=C、P3δ4.2=B、P3δ4.3=A**；仅本刀覆盖旧 A/A/A freeze，授权独立 fail-closed 生产行为 PR；不授权显式 policy / schema。P1/P2/P4 继续挂起；δ5/δ6 生产未启动。
> **前序**: [δ1 fees](plan-industry-align-p3-fees-2026-09-19.md)、[δ2 exdiv](plan-industry-align-p3-d2-exdiv-2026-09-19.md)、[next fill gates](plan-industry-align-next-2026-09-19.md)、[engine SSOT](engine-ashare-correctness.md)；[四刀索引](plan-industry-align-p3-d345-econ-index-2026-09-19.md)。

---

## 0) One-line scope

将 `limits=None` 的来源、分支位置、拦截结果与最终成交分开验收；v7 held stop/add/timer 在真实交易分支显式拒绝 None，保留实档位的 Decimal 涨跌停、T+1、现金与费用行为。

## 1) Why now

#126 的 A/A/A 已钉住首开拒绝 / held stop-add-timer fail-open。新的 Human GO C/B/A 只重开这三处交易尝试：没有有效档位时，先记既有 skip 原因，再拒绝买卖；不调用 `_buy` / `_sell_lots`，不改全局 limit-hit predicate。δ2 映射与 δ3 名称语义不变。

## 2) Verified as-built anchors（本 C cut 编辑后的 file:line）

### 2.1 None 来源与门函数

| 合同项 | 当前事实 | 锚点 |
|---|---|---|
| 无昨收 | 找 today 之前最近 close；没有则 previous=None，session 档位返回 None | `backtest/research/ashare_session.py:44-70` |
| 未知板块 | 非 ST 名称下未知前缀可得 None；ST 名先返回 5%，故“未知代码”不总等于 None | `backtest/research/market_layer.py:43-65`、`:73-84` |
| buy/sell predicate | `skip_buy_at_limit` 与 `defer_sell_at_limit` 遇 None 都返回 False；只表示未命中涨跌停，v7 调用点先拒绝 None | `backtest/research/ashare_session.py:73-78` |
| v7 context | 缩放已有参考价后，按 flat name、mapped previous 算 limits，再进入扫描 | `backtest/research/csv_minute_backtest_v7.py:316-340` |
| 真实现金约束 | v7 买入按预算整百股；无股/含费现金不足产生 `skip_cash`，不建新 lot | `backtest/research/csv_minute_backtest_v7.py:205-223` |
| 真实可卖约束 | `_sell_lots` 仅取 T+1 且匹配 kind 的 lot；wanted<=0 返回 0，无卖单/现金变更 | `backtest/research/csv_minute_backtest_v7.py:226-251` |

None 是“没有可用档位”，不是已证明该标的依法无涨跌幅限制。无昨收和未知板块必须分项。NaN/Inf、零/负昨收不在此处被统一分类为 None，本刀不借输入清洗扩大语义。

### 2.2 路径真值表（足够 bars、可到达该分支为前提）

| 路径 | as-built 的 None 处理 | 后续结果 / 锚点 |
|---|---|---|
| 书 daily held（**默认 named-band**：`qlib_limit_pct is None`、非 ST） | 无昨收在 helper 前置条件冻结；**仅当算得 `limits is None`** 时，未知板块在 lots 卖出循环前 `skip_unknown_board` + continue | `backtest/research/csv_common.py:22-45`、`:73-82`；`backtest/research/csv_daily_backtest.py:300-327` |
| 书 minute held（同默认 named-band 前提） | 缺日线/分钟/昨收先 continue；有昨收但 **`limits is None`** 再 `skip_unknown_board` | `backtest/research/csv_minute_backtest.py:586-618` |
| 书固定 band 例外（不进本刀 None 早拒） | 显式 `qlib_limit_pct` 走固定比例档位，绕过 named/板块判断；未知非 ST 前缀仍可有档位，**不**进入 `skip_unknown_board`。本刀书侧 pins 断言真实 hooks 的 `qlib_limit_pct is None`（public simulate 无同名参数）；不改 topk/BOOKS | `backtest/research/csv_common.py:80-82`；消费点 `csv_daily_backtest.py:320-321`、`csv_minute_backtest.py:612-614`；hooks 默认 `csv_strategy_books.py:127`，固定 band 接线 `:713`、`:788` |
| 书 chase/pool/step | 档位 None 时早拒；不能只列 pool 代表全部加仓 | `backtest/research/csv_simulate_loop.py:150-160`、`:257-267`、`:341-350` |
| v7 14:55 首开仓 | index gate 更早；无昨收 `skip_no_prev_close`；priced=None `skip_unknown_board`；正常档位还过上下限与现金门 | `backtest/research/csv_minute_backtest_v7.py:390-406` |
| v7 held stop | 策略 stop 满足后，None 显式 skip；不调用 `_sell_lots`，可卖/T0 均无卖单、现金/lot 不因尝试改变 | `backtest/research/csv_minute_backtest_v7.py:341-360` |
| v7 held add | 时窗/ladder 满足后，None 显式 skip；不调用 `_buy`，无论现金多少，stage/lot/cash/last_add_date 不因尝试改变 | `backtest/research/csv_minute_backtest_v7.py:364-389` |
| v7 timer exit | 最后一根 record、timer_due 成立后，None 显式 skip；不调用 `_sell_lots`，可卖/T0 均不卖 | `backtest/research/csv_minute_backtest_v7.py:407-418` |
| v7 无 records | 在档位处理前 continue；池内代码可记 `skip_no_1455` | `backtest/research/csv_minute_backtest_v7.py:316-321`；不虚构 bar |

“书侧早拒”只描述该持仓成交循环：有昨收的事件日可能**先**缩放参考价，再遇未知板块拒绝；会话末仍可 mark。它不保证整个状态完全不变。无昨收/无 bar 的 continue 在缩放之前。v7 在三个 held 交易点均按 `previous is None` 记 `skip_no_prev_close`，否则记 `skip_unknown_board`；side=skip、shares=0，不误记 `skip_limit_up` / `defer_limit_down`。只在 stop/ladder/timer 条件成立时记录拒绝；不做整日 continue。peak/last_prices/mark 与除权参考价缩放仍可更新，不是成交现金流。

### 2.3 已关 / 仍钉 / deferred

| 面 | 状态与现有证据 | δ4 边界 |
|---|---|---|
| sell None 双来源拒绝 | `tests/test_ashare_simulate_predicates.py` 的 `test_none_limits_sell_side_rejects_trade_attempts` | 双来源 × daily/minute/v7 × T+1 可卖/不可卖均拒绝；v7 改为 fail-closed，书侧不变，见 B2 |
| 书买/chase 拒绝 | 同文件 `test_none_limits_buy_side_records_unknown_board_in_book_paths` / `test_none_limits_chase_path_rejects_unknown_board_in_shared_loop` | 原有覆盖复用；step 独立补在 daily 真实入口，见 B5 |
| v7 held add | 同文件 `test_v7_held_add_none_limits_rejects_regardless_of_cash` | 双来源 × 精确现金/少一分钱均拒绝；另有真实档位的现金边界对照，见 B3 |
| v7 首开仓 | `tests/test_csv_minute_backtest_v7.py` 的 `test_first_entry_none_limits_rejects_trial_buy` | 扩展旧 unknown-board 首开 pin，补缺昨收并隔离 index gate，见 B4 |
| timer、T+1 无可卖、无 records | 同文件 `test_d4_timer_none_limits_respects_t1_and_records` | 双来源 × 可卖/T0/无 records；末 record 拒绝，None 在门前短路，见 B4；受测为构造 held 状态，不证明自然首开可达 |
| fail-closed / 显式运行策略 | fail-closed 已实施；显式 policy 未授权 | Human GO C/B/A 仅使用既有事件与 reason，无参数/schema 改动 |

## 3) Delta roadmap

| 刀 | 当前地位 | 与 δ4 的关系 |
|---|---|---|
| δ1 fees | 基线已含合同/pins；生产冻结 | pass→现金不足或成交的断言仍按原 FeeSchedule |
| δ2 exdiv reference | 基线已含；只参考价 | 不改 previous 映射、事件落日、经济账 |
| [δ3 ST PIT](plan-industry-align-p3-d3-st-pit-2026-09-19.md) | post #125 基线已含契约/pins；生产冻结 | 名称/ST 能改变 None 来源；禁止连带统一 |
| **δ4 limits-none** | **本文件：Human GO C/B/A，production fail-closed landed** | 仅 v7 held stop/add/timer；δ5/δ6 生产未启动 |
| [δ5 volume-cap](plan-industry-align-p3-d5-volume-cap-2026-09-19.md) | 后续设计 | 无容量 ≠ 无档位，不复用 None 当通用放行符 |
| [δ6 economics](plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md) | Human GO A 残留+oracle，账本可选 B docs | 不借 gate 修复增股/入账或宣称 NAV 正确 |

## 4) F-R* hard locks

| ID | 硬锁 |
|---|---|
| **F-R1** | 仅 §8.1 白名单；生产只允许 v7 三处 None 拒绝（session 仅可加极小 reason helper，本次未改）；其它生产零 diff。 |
| **F-R2** | None 双来源分别验收；首开仓保持拒绝，held stop/add/timer 改为 fail-closed，不调用买卖 helper。 |
| **F-R3** | gate 未拦截 / 交易尝试 / 真正 fill 三层分别断言；不把 absence of skip 当作成交证据。 |
| **F-R4** | 按 C/B/A 复用 skip_no_prev_close / skip_unknown_board；不新增 CLI / policy / 序列化开关或 schema。 |
| **F-R5** | 真实档位的 T+1、现金门、fee floor、lot/stage/clear-today 不变；None 拒绝仅阻断成交变更，bar 缺失/mark/参考价缩放不变。 |
| **F-R6** | 不把 `limits=None` 定义为可合法无限价交易；不虚构未建模来源。 |
| **F-R7** | P1/P2/P4 挂起；δ1/δ2 与 δ3 名称语义冻结；本刀不改变全局 predicate 影响其它引擎。 |
| **F-R8** | 仅合成内存/tmp_path pins，无 CLI 回测/湖/网络；复用既有 data-free tests，不加 skip/xfail。 |
| **F-R9** | §9 除明确允许的 v7/session 外均对固定 base 零 diff；全路径白名单另审，import fence 不扩目录。 |
| **F-R10** | 向量化研究定位不变，不复活 LEBS/live/Cerebro/PortAnaRecord。 |

## 5) P* human cuts（Human GO C/B/A 已录入）

> **Human GO recorded 2026-09-19 (Asia/Shanghai):** **P3δ4.1=C、P3δ4.2=B、P3δ4.3=A**。本刀独立生产 fail-closed 已授权，覆盖旧 A/A/A 冻结；旧记录保留于 changelog。此授权不延伸至 δ5/δ6。

| ID / 决策 | A | B | C | 本轮人裁 |
|---|---|---|---|---|
| **P3δ4.1：交付层级** ✅ Human GO 2026-09-19 | 只合同化 as-built + pins | 设计显式 policy 与迁移真值表，生产不变 | 批准独立生产行为改造 PR | **C** |
| **P3δ4.2：None 政策** ✅ Human GO 2026-09-19 | 保留现有首开/held 分叉 | fail-closed：无有效档位的交易尝试均拒绝 | 显式策略：逐来源/路径给出开关、默认及序列化合同 | **B**；不实施 C 开关 |
| **P3δ4.3：可观测性** ✅ Human GO 2026-09-19 | 复用现有 counters/events + 内存断言 | 文档设计更细原因分类，不改输出 | 批准改事件/产物 schema；若涉及 P2 必须同时明确重开 P2 | **A** |

`.1=C` + `.2=B` 授权无有效档位时拒绝交易尝试；T0/现金不足也先记 None 来源，无 BUY/SELL、无成交导致的现金/lot/stage 变更。无 records 保持 `skip_no_1455`；peak / last_prices / equity mark / exdiv rescale 仍可更新，不是整天所有字段冻结。部署迁移范围仅 v7 held stop/add/timer；实档位、书侧、首开保持原行为。回滚本 cut 的提交即恢复 #126 的 held fail-open pins，无 schema/data 迁移。P1/P2/P4 继续 deferred。

## 6) Non-goals

- 不增加 policy 参数/CLI flag，不重写共享 predicate，不统一书与 v7 账本。
- 不修 ST PIT、无效价格输入、真实无涨跌幅标的规则，不引入容量上限。
- 不改首次 14:55、held 首 bar open、末 bar timer 或 14:57 时点，不增加 trades 列。
- 不运行历史收益比较，不把拦截更多等同于更真实/更盈利，不关闭除权经济残留。

## 7) Slices A → B → C（本 feat 实施范围）

§5 Human GO C/B/A 授权 docs、v7 显式 None 拒绝、data-free pins 及验收；生产选项 C 的授权来源是人裁，不是验收 Slice C。

### Slice A：GO 与 as-built 真值表收口

§2 与 [engine SSOT §2.3](engine-ashare-correctness.md#23-p3-δ4-v7-limitsnone-contracthuman-go-cba)、README 同步 C/B/A 与生产 fail-closed。保留双来源、no-records、ST 优先、named-band / 固定 qlib band 的边界，更新生产 allowlist。

### Slice B：生产与 data-free pins（仅既有文件落点）

生产只改 `csv_minute_backtest_v7.py` 的 stop/add/timer 三个分支，均先检查 None，再调用既有涨跌停门；session/helper 未改。

| Pin | 真实文件 / 函数名 | 本轮改动 / 复用 |
|---|---|---|
| B1 门函数 | `tests/test_ashare_session.py`：`test_skip_buy_and_defer_sell_use_shared_hits` | 原样复用 1 例：Decimal HALF_UP 1.65→1.82/1.49、到达/越界、None 双门 False。其余来源/ST/映射 pins 随完整文件回归；v7 显式拒绝由 B2–B4 证明 |
| B2 sell 与非成交状态 | `tests/test_ashare_simulate_predicates.py`：`test_none_limits_sell_side_rejects_trade_attempts`；`test_d4_v7_none_limits_rescale_and_mark_are_not_fills`；原 `test_d4_book_none_limits_reference_and_mark_are_not_fills` | sell 旧 `test_none_limits_sell_side_records_existing_split` 改名翻转 v7 预期，共 12 例：双来源 × 三入口 × T1/T0 全拒绝；书侧保持。新增 v7 双来源 rescale/mark 2 例，参考价可缩放、股数/现金不变；复用书侧 4 例 |
| B3 held add | 同文件：`test_v7_held_add_none_limits_rejects_regardless_of_cash`；`test_v7_held_add_real_limits_cash_controls_fill` | 旧 `test_v7_held_add_none_limits_cash_controls_fill` 改名翻转 4 例：双来源 × 197797.60/197797.59 均 skip 来源，现金/lot/stage/日期不变、peak/mark 更新。新增实档位 2 例：1900 股 × 104，精确现金可成交、少一分钱 skip_cash |
| B4 首开与 timer | `tests/test_csv_minute_backtest_v7.py`：`test_first_entry_none_limits_rejects_trial_buy`；`test_d4_timer_none_limits_respects_t1_and_records` | 首开 2 例原样复用；timer 6 例更新为双来源 × 可卖/T0/无 records 均不成交。真实 timer_due 透传；None 在 limit-down 门前拒绝，末 bar 15:00/101 元仅 skip，peak/mark 可变；无 records 只记 skip_no_1455。真实档位 timer/reopen、涨跌停及 T+1 原有 pins 回归 |
| B5 书 step 与共有约束 | `tests/test_csv_daily_backtest.py`：`test_d4_step_none_limits_rejects_before_floor_cash_gate` | 原样复用 6 例，缺昨收/未知板块/已知板块 × 1205/1204.99；book 行为、fee floor、现金边界不变。分钟入口与 δ1 fee wiring 一并回归 |

本 C cut **5 个新增/更新函数，26 例**：2 个改名更新（16 例）、1 个原名更新（6 例）、2 个新增（4 例）；相对固定 base **净增 4 例**。B1–B5 共 39 例含复用，包含于 §8.4 完整 suite，不重复计数。生产新行为均由公开 `simulate_v7` 进入，不增加生产 API，不直接调用私有买卖 helper；spy 透传真实函数，不 mock gate 为常量。

held 初态由测试注入，不宣称未知板块自然首开可达；timer T0 是旧 last_add_date 配同日 lot 的构造向量。无 records 即使有日线 close，也只保持成本估值，不冒充分钟成交。缺 bar / rescale / mark 与 fill 分层验收。

### Slice C：验收与冻结

执行 §8、逐项核对 §9，确认仅 v7 三处 None 交易尝试拒绝改变生产；记录 C/B/A、计数、编码、冻结结果并提交到指定 feat 分支，不推送/开 PR。δ5 volume-cap wiring、δ6 production economics、P1/P2/P4 未启动。

## 8) Linux/CI isomorphic acceptance（本次真实命令）

### 8.1 基线、全路径白名单、编码与 whitespace

从仓库根目录用 Bash 执行。`IMPLEMENTATION_BASE` 是本 feat worktree 起点的 `git rev-parse HEAD` 实测值；以下重新解析同一固定 commit，不跟随移动的 master、不推算 merge-base。历史 A/A/A 基线见 changelog，不用于本轮冻结。

```bash
set -euo pipefail
IMPLEMENTATION_BASE="$(git rev-parse --verify '073538d4486a07a71f561631c3f274ffa06eeecb^{commit}')"
[[ "$IMPLEMENTATION_BASE" =~ ^[0-9a-f]{40}$ ]]
git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD
P3_FILES=(
  backtest/research/csv_minute_backtest_v7.py
  backtest/research/ashare_session.py
  docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md
  docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md
  docs/backtest/engine-ashare-correctness.md
  docs/backtest/README.md
  tests/test_ashare_session.py
  tests/test_ashare_simulate_predicates.py
  tests/test_csv_minute_backtest_v7.py
  tests/test_csv_daily_backtest.py
)
P3_AUDIT_DIR="$(mktemp -d)"
trap 'rm -rf -- "$P3_AUDIT_DIR"' EXIT
git diff --name-only "$IMPLEMENTATION_BASE" HEAD > "$P3_AUDIT_DIR/head"
git diff --name-only > "$P3_AUDIT_DIR/worktree"
git diff --cached --name-only > "$P3_AUDIT_DIR/index"
git ls-files --others --exclude-standard > "$P3_AUDIT_DIR/untracked"
sort -u "$P3_AUDIT_DIR/head" "$P3_AUDIT_DIR/worktree" \
  "$P3_AUDIT_DIR/index" "$P3_AUDIT_DIR/untracked" > "$P3_AUDIT_DIR/paths"
while IFS= read -r path; do
  p3_allowed=false
  for allowed_path in "${P3_FILES[@]}"; do
    if [[ "$path" == "$allowed_path" ]]; then p3_allowed=true; break; fi
  done
  if [[ "$p3_allowed" != true ]]; then
    printf 'OUT OF SCOPE: %s\n' "$path"; exit 1
  fi
done < "$P3_AUDIT_DIR/paths"
for path in "${P3_FILES[@]}"; do
  test -f "$path"
  perl -MEncode=decode,FB_CROAK -e '
    local $/; open my $fh, "<:raw", $ARGV[0] or die $!;
    my $raw = <$fh>; die "BOM\n" if substr($raw,0,3) eq "\xEF\xBB\xBF";
    my $nul = () = $raw =~ /\x00/g; die "NUL=$nul\n" if $nul;
    decode("UTF-8", $raw, FB_CROAK);
    print "$ARGV[0]: UTF-8 OK; BOM=0; NUL=0\n";
  ' "$path"
done
git diff --check "$IMPLEMENTATION_BASE" HEAD
git diff --check
git diff --cached --check
for path in "${P3_FILES[@]}"; do
  p3_ws_rc=0
  git diff --no-index --check /dev/null "$path" > "$P3_AUDIT_DIR/whitespace" || p3_ws_rc=$?
  if [[ "$p3_ws_rc" -gt 1 || -s "$P3_AUDIT_DIR/whitespace" ]]; then
    cat "$P3_AUDIT_DIR/whitespace"; exit 1
  fi
done
```

最后的循环覆盖完整文件；no-index 正常内容差异可返回 1，故同时要求 rc≤1 且 whitespace 诊断为空，不能忽略所有非零退出码。全路径审计覆盖 base→HEAD、staged、unstaged、untracked，不靠有限冻结表推断其它路径安全。授权白名单是 **v7 + session（仅 tiny reason helper）+ 四 docs + 四 tests**；本次实际只改 v7 + 四 docs + 两 tests，session 未改，index 仅 δ4 状态行。`tests/test_csv_minute_backtest.py` 只回归、不修改。任何其它生产/测试/CI/数据路径修改均不在本 feat 内；`test_ashare_session.py` 与 `test_csv_daily_backtest.py` 本次也只回归、不修改。

### 8.2 Slice B/C：真实 data-free tests / gates

本次按 Human GO 执行下列命令，结果单列 §8.4。CI 同构依据为 `.github/workflows/python-tests.yml:27-43`、`:49-56` 的受控 Python 3.12、四个 repo-only gates 与 pytest marker；这是定向合同验收，不代表全量 CI 或宿主回测。

本轮使用人指定的 `/tmp/industry-align-venv/bin/python`（3.12），不回落系统 python/pip，不探测盘符、不安装依赖。

```bash
set -euo pipefail
P3_CONTRACT_PYTHON=/tmp/industry-align-venv/bin/python
[[ -x "$P3_CONTRACT_PYTHON" ]]
"$P3_CONTRACT_PYTHON" -c 'import sys, pytest, pandas, numpy, pyarrow; assert sys.version_info[:2] == (3, 12); print(sys.executable)'
"$P3_CONTRACT_PYTHON" scripts/gates/verify_oskh_data_contract.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_data_path_ssot.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_no_hardcoded_machine_paths.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_tr_bridge_import_ssot.py

# §7 两个更新文件 + 未修改的 session/daily/minute 回归。
"$P3_CONTRACT_PYTHON" -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_session.py \
  tests/test_ashare_simulate_predicates.py \
  tests/test_csv_minute_backtest_v7.py \
  tests/test_csv_daily_backtest.py \
  tests/test_csv_minute_backtest.py

# 固定热路径边界与 δ1 回归，不能单独替代本刀 pins。
"$P3_CONTRACT_PYTHON" -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_simulate_import_fence.py \
  tests/test_ashare_fees.py \
  tests/test_ashare_fee_wiring.py
```

所有 gate/test 路径在本基线真实存在；无新增仓库验收脚本。仅合成内存 `simulate` / `simulate_v7` 单元向量或显式 tmp_path/I/O stub；既有 empty-pool main 单元测试仅写 tmp_path 文本，不是 CLI 行情回测。无 CLI/宿主回测、湖或网络访问。缺依赖记阻塞；必需 pin 被 skip 不算通过；只跑旧测试不能替代 §7 新组合。

### 8.3 C cut 生产 allowlist 与其它文件冻结

先执行 §8.1 设置固定 base。§9 仍列 22 个生产文件，其中 v7/session 是本 C cut 的严格例外；其它 **20** 个与下面冻结数组逐项同序。session 本次未改，因此实际 21 个零 diff；这不改变旧 plan 的历史冻结结论。

```bash
FROZEN_PRODUCTION_FILES=(
  backtest/research/ashare_fees.py
  backtest/research/csv_ledger.py
  backtest/research/csv_simulate_loop.py
  backtest/research/csv_daily_backtest.py
  backtest/research/csv_minute_backtest.py
  backtest/research/market_layer.py
  backtest/research/csv_common.py
  backtest/research/csv_artifacts.py
  backtest/research/exdiv_map.py
  backtest/research/exdiv_hold_hits.py
  backtest/research/ashare_bars.py
  backtest/research/csv_daily_loader.py
  backtest/research/ashare_fill_clock.py
  backtest/research/qlib_bin_daily.py
  backtest/research/qlib_bin_1min.py
  backtest/research/csv_pool.py
  backtest/research/csv_strategy_books.py
  backtest/research/strategy5_rules.py
  backtest/research/unified_exit_modea.py
  backtest/research/unified_exit_modeb.py
)
for path in "${FROZEN_PRODUCTION_FILES[@]}"; do test -f "$path"; done
git diff --exit-code "$IMPLEMENTATION_BASE" -- backtest/research/ \
  ':(exclude)backtest/research/csv_minute_backtest_v7.py' \
  ':(exclude)backtest/research/ashare_session.py'
git diff --exit-code "$IMPLEMENTATION_BASE" -- '*.py' ':(exclude)tests/**' \
  ':(exclude)backtest/research/csv_minute_backtest_v7.py' \
  ':(exclude)backtest/research/ashare_session.py'
git diff --exit-code "$IMPLEMENTATION_BASE" -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code "$IMPLEMENTATION_BASE" HEAD -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --cached --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
```

### 8.4 本次运行记录与验收范围

Human GO **P3δ4.1=C / P3δ4.2=B / P3δ4.3=A**；固定 IMPLEMENTATION_BASE / 初始 HEAD 均为 `073538d4486a07a71f561631c3f274ffa06eeecb`。2026-09-19（Asia/Shanghai），在 `/workspace/wt-p3-d4-failclosed-feat`、分支 `feat/industry-align-p3-d4-limits-none-failclosed`，使用 `/tmp/industry-align-venv/bin/python` / CPython **3.12.13** 验收。仅内存/tmp_path，无依赖安装、CLI 回测、湖或网络。

| 命令 / 检查 | 本次结果 | exit |
|---|---|---|
| §8.2 指定五文件 pytest，`-m 'not production and not benchmark'` | **195 passed / 0 skipped**；较 base 净增 4 例 | 0 |
| §8.2 import fence / fees / fee wiring | **38 passed / 0 skipped** | 0 |
| §8.2 四个 repo-only gates | 全部 PASS；path SSOT 7 hits / 0 violations，TR bridge 2 consumers | 0 |
| §8.1 全路径白名单、UTF-8/BOM/NUL、whitespace | PASS；仅 v7 + 四 docs + 两 tests；UTF-8、BOM=0、NUL=0 | 0 |
| §8.3 production allowlist / §9 冻结 / 全仓其它生产 Python | **PROD_ALLOWLIST_OK**；生产仅 v7 三处 None 检查；20 个冻结文件四种 diff 为空，session 也零 diff；§9 非例外行原文/顺序不变 | 0 |
| `git add <七个变更文件> && git commit -m 'feat(p3-d4): limits=None fail-closed production (Human GO C/B/A)'` | **PASS（host）**：清除 stale `index.lock` 后提交成功；Feat SHA `0975e572d2d35f5bc92d1f5db5ccf433c80dd65f` | 0 |

两组 suite 合计 **233 passed**（195+38），5 个新增/更新函数的 26 例包含其中，不重复计数。五文件 suite 有 2 条既有 `ashare_bars.py:503` pandas copy 参数弃用 warning；未改生产压警告。未新增 skip/xfail，未用常量 gate 替代真实门，也不以 mark/peak 代替 fill 断言。结果只覆盖定向 data-free 验收，不代表全量 CI 或历史收益回测。

本 C cut 仅改 v7 held stop/add/timer 的 None 交易尝试，使用既有 skip 事件区分无昨收 / 未知板块。首开、书侧、Decimal limit-hit helper、费用、除权经济语义不变；**δ5/δ6 production NOT started**，P1/P2/P4 继续 deferred。Host 已提交 Feat SHA `0975e572d2d35f5bc92d1f5db5ccf433c80dd65f`；由 host 推送并开 PR。

## 9) Production file table（C cut 两个授权例外；其它零 diff）

| File | 冻结理由 / 来源 |
|---|---|
| `backtest/research/ashare_fees.py` | δ1 费率/default/asymmetry/floor 不漂移 |
| `backtest/research/csv_ledger.py` | δ1/δ2 双向现金、整股、lot、参考价 rescale |
| `backtest/research/csv_simulate_loop.py` | δ1/δ2 chase/pool/step、资金门与 raw mark |
| `backtest/research/csv_daily_backtest.py` | δ1/δ2 daily 名称/档位/缩放顺序/入口域与费率 |
| `backtest/research/csv_minute_backtest.py` | δ1/δ2 minute 扫描/前置数据/门/入口域 |
| `backtest/research/csv_minute_backtest_v7.py` | **本 C cut 允许**：仅 held stop/add/timer 显式 None 拒绝 + 既有 source reason；其它 lot/费用/时点/经济逻辑冻结 |
| `backtest/research/ashare_session.py` | **仅允许 tiny None-reject reason helper（本次未改）**；ST/context、昨收、limit-hit predicates、T+1 冻结 |
| `backtest/research/market_layer.py` | δ1 ST 优先/板块/Decimal 档位 |
| `backtest/research/csv_common.py` | δ1/δ2 书 as-of、named band、bar/昨收前置条件 |
| `backtest/research/csv_artifacts.py` | δ1 产物 schema；P2 挂起 |
| `backtest/research/exdiv_map.py` | δ2 事件门/LAG/阈值/k/缺失行为，不改成权益源 |
| `backtest/research/exdiv_hold_hits.py` | δ2 引用的日期 normalize 与既有探针冻结 |
| `backtest/research/ashare_bars.py` | δ2 分钟帧/源域/缺 bar 与 volume 丢列行为 |
| `backtest/research/csv_daily_loader.py` | δ2 域/零量过滤与输出列 |
| `backtest/research/ashare_fill_clock.py` | δ2 已列；P1 时钟命名冻结 |
| `backtest/research/qlib_bin_daily.py` | δ2 qlib_day 域声明/读取不变 |
| `backtest/research/qlib_bin_1min.py` | δ2 qlib_1min 域/输出帧不变 |
| `backtest/research/csv_pool.py` | 新扩展：名称第二列/by-day/窗口/空名合同 |
| `backtest/research/csv_strategy_books.py` | 新扩展：BOOKS/hooks/卖出策略/P4 边界 |
| `backtest/research/strategy5_rules.py` | 新扩展：既有 force-sell 时点，不为 cap/None 改写 |
| `backtest/research/unified_exit_modea.py` | 新扩展：独立研究网格合同，不统一到 CSV 账本 |
| `backtest/research/unified_exit_modeb.py` | 新扩展：fractional-shares 近似保持独立，不借用作经济闭环 |

本表剔除 v7/session 两个授权例外后，与 §8.3 冻结数组路径/顺序一致；其它 20 行对固定 base 必须零 diff。§8.3 还查整个 research 与全仓其它生产 Python；§8.1 全路径白名单禁止其它生产、测试、CI 或数据修改。不能以本表未列出为理由改生产；不扩大固定热路径 import-fence 的扫描面。


## 10) Changelog

- **v0.4 (2026-09-19，Asia/Shanghai)**：新 Human GO **C/B/A** 覆盖旧 A/A/A 的本刀生产冻结；固定 base 刷新为 #128 merge `073538d4486a07a71f561631c3f274ffa06eeecb`。v7 held stop/add/timer 对 None 显式 fail-closed，复用无昨收/未知板块 skip reason；共享门不变，参考价/peak/mark 可更新。更新 3 个旧测试函数、新增 2 个函数，共 26 例、净增 4；实际命令与冻结结果见 §8.4。四 docs 同步，实现已验收；host 补提交 Feat SHA `0975e572d2d35f5bc92d1f5db5ccf433c80dd65f`；δ5/δ6 生产未启动，P1/P2/P4 deferred。

- **v0.3 (2026-09-19，Asia/Shanghai)**：按 Human GO A/A/A 完成 Slice A→B→C；基线刷新为 post #125 `844919481f12a220fdf3c411d9be09583b2d7984`，保留历史 proposal 基线。engine SSOT §2.3 / README 记录 None 双来源、首开/held stop-add-timer 分叉与 MC-1 named-band 前提；四个既有测试文件新增/增强 7 函数、35 定向例（净增 26），B1–B5 映射见 §7。§8.4 记录 191+38 passed、四 gates、七路径白名单、编码与 22 文件/全 research/全仓生产 Python 零 diff。保留 §9 原表与未提交交付，未实施 fail-closed 或显式 policy。
- **v0.2 (2026-09-19，Asia/Shanghai)**：录入 Human GO P3δ4.1/4.2/4.3=A/A/A，授权后续 Slice A→B→C 契约+data-free pins；fail-closed/显式 policy 改造另裁，生产冻结，P1/P2/P4 继续挂起。保留 MC-1 勘误；本次未实施 slices、未新增/执行测试，基线、白名单、冻结表与 §8 命令不变。
- **v0.1.1 (2026-09-19)**：r1 勘误——§2 书侧未知板块早拒收窄为默认 named-band；增固定 `qlib_limit_pct` 对照行（见 reviews `plan-industry-align-p3-d345-econ-r1` MC-1）。
- **v0.1 (2026-09-19)**：post #123 逐行核实 None 双来源及首开/held stop/add/timer 分叉，复用真实已有 pins；提出待人裁政策设计与未来验收，默认生产冻结。仅文档，无生产/测试修改、无回测/湖，未实施 fail-closed 或显式策略。
