# Plan: industry-align P3 δ4 v7 limits=None contract (2026-09-19)

> **Status**: **v0.3 · Slice A→B→C 已通过（§8.4） · Human GO A/A/A（2026-09-19，Asia/Shanghai）**。本 feat 仅三份 docs + 四个既有 data-free 测试文件；生产 Python 对 IMPLEMENTATION_BASE 零 diff；fail-closed 未实施、未获授权，保留未提交工作区交付。
> **Main ship / 单行范围**: 先契约化 v7 `limits=None` 的 held sell/add fail-open 与首开仓拒绝分叉；改 fail-closed 或引入显式策略必须另行人裁。
> **IMPLEMENTATION_BASE**: `844919481f12a220fdf3c411d9be09583b2d7984`（本 feat worktree 起点，已由 `git rev-parse HEAD` 核实；post #125，含 δ1/δ2/δ3）。历史 proposal 基线 `1049b904bdd818dbb79f51f1830a008c8f83b141` 仅保留沿革，不用于本 feat 冻结证明。
> **Human GO recorded**: **P3δ4.1=A、P3δ4.2=A、P3δ4.3=A**；先契约化，fail-closed/显式 policy 生产改造均须另裁，不在本次 GO 内。P1/P2/P4 继续挂起。
> **前序**: [δ1 fees](plan-industry-align-p3-fees-2026-09-19.md)、[δ2 exdiv](plan-industry-align-p3-d2-exdiv-2026-09-19.md)、[next fill gates](plan-industry-align-next-2026-09-19.md)、[engine SSOT](engine-ashare-correctness.md)；[四刀索引](plan-industry-align-p3-d345-econ-index-2026-09-19.md)。

---

## 0) One-line scope

将 `limits=None` 的来源、分支位置、拦截结果与最终成交分开验收；保留当前研究行为，不以修复 helper 或统一政策为名 silently 改成交。

## 1) Why now

next plan 已选择保留分叉，post #123 基线已有 sell-side 分叉与 held-add `skip_cash` pins。δ4 不重做已落地工作，而是补全 timer/首开仓/held 多分支的合同以及未来政策选择入口。δ3 名称会影响“能否算出档位”；δ2 会影响 mapped prev_close，但都没有给 δ4 授权。只有先固定现状，后续 fail-closed 提案才有可审查的前后差异。

## 2) Verified as-built anchors（本 IMPLEMENTATION_BASE 的 file:line）

### 2.1 None 来源与门函数

| 合同项 | 当前事实 | 锚点 |
|---|---|---|
| 无昨收 | 找 today 之前最近 close；没有则 previous=None，session 档位返回 None | `backtest/research/ashare_session.py:44-70` |
| 未知板块 | 非 ST 名称下未知前缀可得 None；ST 名先返回 5%，故“未知代码”不总等于 None | `backtest/research/market_layer.py:43-65`、`:73-84` |
| buy/sell predicate | `skip_buy_at_limit` 与 `defer_sell_at_limit` 遇 None 都返回 False；意思是此门不拦截 | `backtest/research/ashare_session.py:73-78` |
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
| v7 14:55 首开仓 | index gate 更早；无昨收 `skip_no_prev_close`；priced=None `skip_unknown_board`；正常档位还过上下限与现金门 | `backtest/research/csv_minute_backtest_v7.py:384-400` |
| v7 held stop | 先满足策略 stop；None 不触发 defer，继续 `_sell_lots` | `backtest/research/csv_minute_backtest_v7.py:341-357`；仍受 T+1 限制 |
| v7 held add | 先满足时窗/ladder；None 时 buy/sell 两门均不拦，继续 `_buy` | `backtest/research/csv_minute_backtest_v7.py:361-383`；有现金可加，无现金 skip；stage 仅买成后变 |
| v7 timer exit | 最后一根 record、timer_due 成立后；None 不 defer，尝试 T+1 sell | `backtest/research/csv_minute_backtest_v7.py:401-409` |
| v7 无 records | 在档位处理前 continue；池内代码可记 `skip_no_1455` | `backtest/research/csv_minute_backtest_v7.py:316-321`；None fail-open 不会造出 bar |

“书侧早拒”只描述该持仓成交循环：有昨收的事件日可能**先**缩放参考价，再遇未知板块拒绝；会话末仍可 mark。它不保证整个状态完全不变。无昨收/无 bar 的 continue 在缩放之前。v7 gate-pass 同样不等于必有成交，peak/last_prices/mark 也不等于成交现金流。

### 2.3 已关 / 仍钉 / deferred

| 面 | 状态与现有证据 | δ4 边界 |
|---|---|---|
| sell None 双来源分叉 | `tests/test_ashare_simulate_predicates.py` 的 `test_none_limits_sell_side_records_existing_split` | 原名增强为双来源 × daily/minute/v7 × T+1 可卖/不可卖，真实现金/lot/mark 断言；另补参考价与 mark 独立变化，见 B2 |
| 书买/chase 拒绝 | 同文件 `test_none_limits_buy_side_records_unknown_board_in_book_paths` / `test_none_limits_chase_path_rejects_unknown_board_in_shared_loop` | 原有覆盖复用；step 独立补在 daily 真实入口，见 B5 |
| v7 held add | 同文件 `test_v7_held_add_none_limits_cash_controls_fill` | 扩展旧 `test_v7_held_add_none_limits_gate_passes_then_cash_skip`，双来源 × 精确现金/少一分钱；真正买入和 skip 不变性，见 B3 |
| v7 首开仓 | `tests/test_csv_minute_backtest_v7.py` 的 `test_first_entry_none_limits_rejects_trial_buy` | 扩展旧 unknown-board 首开 pin，补缺昨收并隔离 index gate，见 B4 |
| timer、T+1 无可卖、无 records | 同文件 `test_d4_timer_none_limits_respects_t1_and_records` | 双来源 × 三结果；真实 timer/gate 透传，最终 record 成交，见 B4；受测为构造 held 状态，不证明自然首开可达 |
| 改 fail-closed / 显式运行策略 | deferred | 必须 P3δ4.1=C + 其它适用人裁；本 PR 不实施 |

## 3) Delta roadmap

| 刀 | 当前地位 | 与 δ4 的关系 |
|---|---|---|
| δ1 fees | 基线已含合同/pins；生产冻结 | pass→现金不足或成交的断言仍按原 FeeSchedule |
| δ2 exdiv reference | 基线已含；只参考价 | 不改 previous 映射、事件落日、经济账 |
| [δ3 ST PIT](plan-industry-align-p3-d3-st-pit-2026-09-19.md) | post #125 基线已含契约/pins；生产冻结 | 名称/ST 能改变 None 来源；禁止连带统一 |
| **δ4 limits-none** | **本文件：Human GO A，契约/pins** | 政策改造须另裁独立 C，本轮不授权 |
| [δ5 volume-cap](plan-industry-align-p3-d5-volume-cap-2026-09-19.md) | 后续设计 | 无容量 ≠ 无档位，不复用 None 当通用放行符 |
| [δ6 economics](plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md) | Human GO A 残留+oracle，账本可选 B docs | 不借 gate 修复增股/入账或宣称 NAV 正确 |

## 4) F-R* hard locks

| ID | 硬锁 |
|---|---|
| **F-R1** | 本 feat 仅 §8.1 三份 docs + 四个 tests；全部生产 Python 零 diff。不得修改 `limits=None` 引起的生产成交/现金/NAV。 |
| **F-R2** | None 双来源分别验收；首开仓拒绝、held stop/add/timer 不拦截均保留。 |
| **F-R3** | gate 未拦截 / 交易尝试 / 真正 fill 三层分别断言；不把 absence of skip 当作成交证据。 |
| **F-R4** | fail-closed、显式 policy 参数、改变 reason/默认值都须另行人裁，不能以“保持默认”夹带新生产接口。 |
| **F-R5** | 已有 T+1、现金门、fee floor、lot/stage/clear-today、bar 缺失与 mark 分叉不变。 |
| **F-R6** | 不把 `limits=None` 定义为可合法无限价交易；不虚构未建模来源。 |
| **F-R7** | P1/P2/P4 挂起；δ1/δ2 与 δ3 名称语义冻结；本刀不改变全局 predicate 影响其它引擎。 |
| **F-R8** | 仅合成内存/tmp_path pins，无 CLI 回测/湖/网络；复用既有 data-free tests，不加 skip/xfail。 |
| **F-R9** | §9 为 δ1/δ2 冻结超集，全部生产仍受七路径白名单约束；import fence 不扩目录。 |
| **F-R10** | 向量化研究定位不变，不复活 LEBS/live/Cerebro/PortAnaRecord。 |

## 5) P* human cuts（Human GO A/A/A 已录入）

> **Human GO recorded 2026-09-19 (Asia/Shanghai):** P3δ4.1=A、P3δ4.2=A、P3δ4.3=A — δ4=A：先契约化；fail-closed 另裁。本 feat 实施 Slice A→B→C docs + data-free pins；保留首开/held 分叉，生产冻结，fail-closed/显式 policy 不在本次 GO 内。

| ID / 决策 | A | B | C | 本轮人裁 |
|---|---|---|---|---|
| **P3δ4.1：交付层级** ✅ Human GO 2026-09-19 | 只合同化 as-built + pins | 设计显式 policy 与迁移真值表，生产不变 | 批准独立生产行为改造 PR | **A** |
| **P3δ4.2：未来 None 政策** ✅ Human GO 2026-09-19 | 保留现有首开/held 分叉 | 候选 fail-closed：无有效档位的交易尝试均拒绝；先设计状态/reason | 候选显式策略：逐来源/路径给出开关、默认及序列化合同 | **A**；B/C 未采纳，须另有 .1=C 才可生产实施 |
| **P3δ4.3：可观测性** ✅ Human GO 2026-09-19 | 复用现有 counters/events + 内存断言 | 文档设计更细原因分类，不改输出 | 批准改事件/产物 schema；若涉及 P2 必须同时明确重开 P2 | **A** |

`.2=B/C` 不是运行参数现已存在，也不是独立的生产授权。若选 `.1=C`，仍须写清各来源、stop/add/timer 的结果、T+1/资金失败时状态、缺 bar 标记、默认值与迁移/回滚范围；不得把 fail-closed 定义为“整天所有字段完全冻结”。P1/P2/P4 的旧 A 是继续延后，不是对新接口的授权。

## 6) Non-goals

- 不增加 policy 参数/CLI flag，不换默认、不重写共享 predicate，不统一书与 v7 账本。
- 不修 ST PIT、无效价格输入、真实无涨跌幅标的规则，不引入容量上限。
- 不改首次 14:55、held 首 bar open、末 bar timer 或 14:57 时点，不增加 trades 列。
- 不运行历史收益比较，不把拦截更多等同于更真实/更盈利，不关闭除权经济残留。

## 7) Slices A → B → C（本 feat 实施范围）

§5 Human GO A/A/A 已授权本节契约+data-free pins 及验收，生产冻结；设计 B 和生产 C 均未采纳。验收 Slice C 不构成 fail-closed 授权。

### Slice A：as-built 真值表收口

复核 §2 分支顺序并写入 [engine SSOT §2.3](engine-ashare-correctness.md#23-p3-δ4-v7-limitsnone-contracthuman-go-aaa)，README 链接同一合同；标明 seed 持仓与自然首开可达性的区别。DoD：未知板块与无昨收、无 records、ST 优先、named-band / 固定 qlib band、首开/held stop-add-timer 均已列明。

### Slice B：实际 data-free pins（仅既有文件落点）

| Pin | 真实文件 / 函数名 | 本轮新增或增强 / 复用 |
|---|---|---|
| B1 门函数 | `tests/test_ashare_session.py`：`test_skip_buy_and_defer_sell_use_shared_hits` | 原名增强 **1** 例；真实 Decimal HALF_UP 1.65→1.82/1.49，双门到达/越界拦截、None 双门 False。双来源复用 `test_d2_no_previous_close_retains_none_policy`、`test_d3_name_and_board_boundaries`；舍入复用 `test_d2_mapped_return_flows_into_decimal_limits`，不复制相同覆盖 |
| B2 书与 v7 sell 分叉 | `tests/test_ashare_simulate_predicates.py`：`test_none_limits_sell_side_records_existing_split`；新增 `test_d4_book_none_limits_reference_and_mark_are_not_fills` | 原 6→**12** 例：双来源 × 三入口 × 可卖/不可卖；None 分叉下 v7 真卖 100 股并入现金，T+1 不足则 lot/现金不变；书早拒并 mark。另 **4** 例：双来源 × daily/minute，k=1.2 下未知板块先缩放再拒绝，缺昨收在缩放前退，参考价/mark 不是 fill |
| B3 held add | 同文件：`test_v7_held_add_none_limits_cash_controls_fill`（旧 `test_v7_held_add_none_limits_gate_passes_then_cash_skip` 改名扩展） | 原 1→**4** 例；双来源 × 197797.60/197797.59 现金。真实 public simulate 买 1900 股 × 104，含费后现金为零、stage=four、lot/均价/日期更新；少一分钱只有 skip_cash，lot/stage/现金不变，peak 可变 |
| B4 首开与 timer | `tests/test_csv_minute_backtest_v7.py`：`test_first_entry_none_limits_rejects_trial_buy`（旧 `test_first_entry_unknown_board_rejects_trial_buy` 改名扩展）；新增 `test_d4_timer_none_limits_respects_t1_and_records` | 首开原 1→**2** 例，None 双来源分别拒绝；timer **6** 例，双来源 × 可卖/T0/无 records。真实 timer_due=True，末 bar 15:00、101 元成交；不可卖现金/lot 不变，无 records 不进入 timer；session list 隔离 index，价格避开 stop/add。原 timer/reopen pin 保留 |
| B5 书 step 与共有约束 | `tests/test_csv_daily_backtest.py`：新增 `test_d4_step_none_limits_rejects_before_floor_cash_gate` | **6** 例：缺昨收/未知板块/已知板块 × 1205/1204.99 现金；真实 daily version8 入口，空 pool/chase、真实 step hooks；未知板块 held→step 拒绝计数 1→2，缺昨收使报价返回 None，未到档位门；已知板块 100 股 × 12 + 5 元 floor 精确成交 / 少一分钱 skip。共享 δ1 floor/现金覆盖复用 `tests/test_ashare_fee_wiring.py`，分钟原有入口测试一并回归，不改该文件 |

本轮共 **7 个新增/增强函数，35 个定向用例**：3 个全新函数（16 例）、2 个改名扩展函数（6 例）、2 个原名增强函数（13 例）；对应旧覆盖 9 例，**净增 26 例**。B1=1、B2=16、B3=4、B4=8、B5=6；上述原有复用覆盖另在完整文件 suite 中执行。新增 API 调用仅公开 helper / `simulate` / `simulate_v7`；spy 透传真实函数，未 mock gate 为常量，未直接调用私有买卖 helper。

held 由测试注入初态，不宣称未知板块自然首开可达；timer T0 向量特意独立设置旧 last_add_date 与同日 lot。无 records 向量即使提供日线 close，也只保留成本估值，不冒充分钟成交。DoD：reason、股数、lot/stage、现金、mark 分层，真实默认 named-band 断言；未扩生产接口。完整执行见 §8.4。

### Slice C：验收、默认冻结与另案出口

执行 §8、核对 §9、记录各 pin 是否实际执行；默认验收只证明现状分叉可回归。新增失败若暴露需改成交的问题，写入 P3δ4 人裁与独立生产案，不改预期把它掩盖。验收 Slice C 不等于批准生产的选项 C。

## 8) Linux/CI isomorphic acceptance（本次真实命令）

### 8.1 基线、全路径白名单、编码与 whitespace

从仓库根目录用 Bash 执行。`IMPLEMENTATION_BASE` 是本 feat worktree 起点的 `git rev-parse HEAD` 实测值；以下重新解析同一固定 commit，不跟随移动的 master、不推算 merge-base。proposal 历史锚点见页首，不用于本轮冻结。

```bash
set -euo pipefail
IMPLEMENTATION_BASE="$(git rev-parse --verify '844919481f12a220fdf3c411d9be09583b2d7984^{commit}')"
[[ "$IMPLEMENTATION_BASE" =~ ^[0-9a-f]{40}$ ]]
git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD
P3_FILES=(
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

最后的循环覆盖完整文件；no-index 正常内容差异可返回 1，故同时要求 rc≤1 且 whitespace 诊断为空，不能忽略所有非零退出码。全路径审计覆盖 base→HEAD、staged、unstaged、untracked，不靠有限冻结表推断其它路径安全。白名单收窄为实际触及的 **三 docs + 四 tests**；`tests/test_csv_minute_backtest.py` 只回归、不修改。任何其它生产/测试/CI/数据路径修改均不在本 feat 内。

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

# §7 四个实际落点文件 + 未修改的 minute 入口回归。
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

### 8.3 默认生产冻结（数组与 §9 逐项相同）

先执行 §8.1 设置固定 base。保留 δ1 十文件、δ2 十七文件全部项目，再扩展名称/策略/Mode A/B 边界，共 **22** 个；这不改变旧 plan 的历史冻结结论。

```bash
FROZEN_PRODUCTION_FILES=(
  backtest/research/ashare_fees.py
  backtest/research/csv_ledger.py
  backtest/research/csv_simulate_loop.py
  backtest/research/csv_daily_backtest.py
  backtest/research/csv_minute_backtest.py
  backtest/research/csv_minute_backtest_v7.py
  backtest/research/ashare_session.py
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
git diff --exit-code "$IMPLEMENTATION_BASE" -- backtest/research/
git diff --exit-code "$IMPLEMENTATION_BASE" -- '*.py' ':(exclude)tests/**'
git diff --exit-code "$IMPLEMENTATION_BASE" -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code "$IMPLEMENTATION_BASE" HEAD -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --cached --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
```

### 8.4 本次运行记录与验收范围

验证 HEAD / 固定 IMPLEMENTATION_BASE 均为 `844919481f12a220fdf3c411d9be09583b2d7984`；受测代码为本 feat 的**未提交工作区**，没有实现 commit。2026-09-19（Asia/Shanghai），在 `/workspace/wt-p3-d4-limits-none-feat`、Linux / CPython **3.12.13** 上执行，显式解释器 `/tmp/industry-align-venv/bin/python`；没有依赖安装、网络或湖访问。

| 命令 / 检查 | 本次结果 | exit |
|---|---|---|
| §8.1 基线祖先、七路径白名单（HEAD/index/worktree/untracked）、编码、whitespace | PASS；仅三 docs + 四 tests；UTF-8、BOM=0、NUL=0；本地 Markdown 目标与 §2.3 链接片段有效 | 0 |
| §8.2 `"$P3_CONTRACT_PYTHON" -c 'import sys, pytest, pandas, numpy, pyarrow; assert sys.version_info[:2] == (3, 12); print(sys.executable)'`（实跑同时打印版本） | CPython 3.12.13；依赖导入成功 | 0 |
| `/tmp/industry-align-venv/bin/python scripts/gates/verify_oskh_data_contract.py` | OK | 0 |
| `/tmp/industry-align-venv/bin/python scripts/gates/verify_data_path_ssot.py` | 7 hits、0 violations | 0 |
| `/tmp/industry-align-venv/bin/python scripts/gates/verify_no_hardcoded_machine_paths.py` | OK | 0 |
| `/tmp/industry-align-venv/bin/python scripts/gates/verify_tr_bridge_import_ssot.py` | OK，2 consumers | 0 |
| §8.2 pytest 四个触及文件，`-k 'test_skip_buy_and_defer_sell_use_shared_hits or test_none_limits_sell_side_records_existing_split or test_d4 or test_v7_held_add_none_limits_cash_controls_fill or test_first_entry_none_limits_rejects_trial_buy'` | **35 passed / 120 deselected / 0 skipped**；B1=1、B2=16、B3=4、B4=8、B5=6；净增 26 例 | 0 |
| §8.2 `/tmp/industry-align-venv/bin/python -m pytest -q -m 'not production and not benchmark'` + 五个完整测试文件（路径逐项如上） | **191 passed / 0 skipped**；四个触及文件 155 例，未改 minute 文件 36 例；相对冻结基线净增 26 例 | 0 |
| §8.2 同一 pytest 命令 + `test_ashare_simulate_import_fence.py` / `test_ashare_fees.py` / `test_ashare_fee_wiring.py` | **38 passed / 0 skipped** | 0 |
| `git diff --exit-code 844919481f12a220fdf3c411d9be09583b2d7984 -- backtest/research/` | **PASS：全部 research 生产文件零 diff** | 0 |
| §8.3 `git diff --exit-code "$IMPLEMENTATION_BASE" -- '*.py' ':(exclude)tests/**'` | **PASS：全仓测试目录外 Python 零 diff** | 0 |
| §8.3 四种冻结 diff；数组 / §9 表逐项与顺序、表行对基线、§7 函数名与 AST 核对 | PASS；22 文件四种 diff 均为空，表行与基线原文一致；3 新增 + 2 改名扩展 + 2 原名增强函数均已映射 | 0 |

完整 suite 合计 **229 passed**（191+38，定向 35 例是子集，不重复累加），不代表全量 CI 或宿主回测。五文件 suite 的 2 条 warning 来自既有 `ashare_bars.py:503` pandas `copy` 参数弃用，未改生产压警告。首轮定向 35 例即全部通过；未增加 skip/xfail，未用恒定 gate 或门放行冒充真实成交。

Slice A→B→C 验收完成：Human GO A/A/A 的现状分叉与 data-free pins 已通过；全部生产 Python 零 diff，fail-closed / 显式 policy **未实施、未获授权**，政策变更须另立 P3δ4.1=C。P1/P2/P4 与 δ1/δ2/δ3、其它 δ 的独立边界不变；本轮不提交、推送或开 PR。

## 9) Frozen production file table（δ1/δ2 超集；默认零 diff）

| File | 冻结理由 / 来源 |
|---|---|
| `backtest/research/ashare_fees.py` | δ1 费率/default/asymmetry/floor 不漂移 |
| `backtest/research/csv_ledger.py` | δ1/δ2 双向现金、整股、lot、参考价 rescale |
| `backtest/research/csv_simulate_loop.py` | δ1/δ2 chase/pool/step、资金门与 raw mark |
| `backtest/research/csv_daily_backtest.py` | δ1/δ2 daily 名称/档位/缩放顺序/入口域与费率 |
| `backtest/research/csv_minute_backtest.py` | δ1/δ2 minute 扫描/前置数据/门/入口域 |
| `backtest/research/csv_minute_backtest_v7.py` | δ1/δ2 v7 独立 lot/股数/现金/stage/时点 |
| `backtest/research/ashare_session.py` | δ1/δ2 ST/context、昨收、None predicates、T+1 |
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

本表与 §8.3 数组的路径/顺序必须一致。表内零 diff 只证明这些文件；§8.3 另查全部 `backtest/research/` 与全仓生产 Python，§8.1 全路径白名单禁止七路径以外的生产、测试、CI 或数据修改。不能以本表未列出为理由改生产；不扩大固定热路径 import-fence 测试的扫描面。


## 10) Changelog

- **v0.3 (2026-09-19，Asia/Shanghai)**：按 Human GO A/A/A 完成 Slice A→B→C；基线刷新为 post #125 `844919481f12a220fdf3c411d9be09583b2d7984`，保留历史 proposal 基线。engine SSOT §2.3 / README 记录 None 双来源、首开/held stop-add-timer 分叉与 MC-1 named-band 前提；四个既有测试文件新增/增强 7 函数、35 定向例（净增 26），B1–B5 映射见 §7。§8.4 记录 191+38 passed、四 gates、七路径白名单、编码与 22 文件/全 research/全仓生产 Python 零 diff。保留 §9 原表与未提交交付，未实施 fail-closed 或显式 policy。
- **v0.2 (2026-09-19，Asia/Shanghai)**：录入 Human GO P3δ4.1/4.2/4.3=A/A/A，授权后续 Slice A→B→C 契约+data-free pins；fail-closed/显式 policy 改造另裁，生产冻结，P1/P2/P4 继续挂起。保留 MC-1 勘误；本次未实施 slices、未新增/执行测试，基线、白名单、冻结表与 §8 命令不变。
- **v0.1.1 (2026-09-19)**：r1 勘误——§2 书侧未知板块早拒收窄为默认 named-band；增固定 `qlib_limit_pct` 对照行（见 reviews `plan-industry-align-p3-d345-econ-r1` MC-1）。
- **v0.1 (2026-09-19)**：post #123 逐行核实 None 双来源及首开/held stop/add/timer 分叉，复用真实已有 pins；提出待人裁政策设计与未来验收，默认生产冻结。仅文档，无生产/测试修改、无回测/湖，未实施 fail-closed 或显式策略。
