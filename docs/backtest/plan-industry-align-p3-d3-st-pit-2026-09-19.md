# Plan: industry-align P3 δ3 ST PIT contract (2026-09-19)

> **Status**: **v0.3 · Slice A→B→C 已通过（§8.4） · Human GO A/A/A（2026-09-19，Asia/Shanghai）**。本 feat 仅三份 docs + §7 六个既有 data-free 测试文件；生产 Python 对 IMPLEMENTATION_BASE 零 diff，保留未提交工作区交付。
> **Main ship / 单行范围**: 契约化书侧按名单日期 as-of 与 v7 窗口末次名称平铺的 ST 分叉；本 feat 只做 docs + data-free pins，生产零行为变更。
> **IMPLEMENTATION_BASE**: `cce17f319ead5c64a202632c3665b4eeb3e3e7a5`（本 feat worktree 起点，已由 `git rev-parse HEAD` 核实；post #124，含 δ1/δ2 与 δ3 Human GO）。历史 proposal 基线 `1049b904bdd818dbb79f51f1830a008c8f83b141` 仅保留沿革，不用于本 feat 冻结证明。
> **Human GO recorded**: **P3δ3.1=A、P3δ3.2=A、P3δ3.3=A**；契约 + data-free pins，不改生产，不授权 v7 ST PIT 改造。既有 P1/P2/P4 继续挂起。
> **前序**: [δ1 fee contract](plan-industry-align-p3-fees-2026-09-19.md)、[δ2 exdiv contract](plan-industry-align-p3-d2-exdiv-2026-09-19.md)、[fill-gates next](plan-industry-align-next-2026-09-19.md)、[engine SSOT](engine-ashare-correctness.md)；[四刀索引](plan-industry-align-p3-d345-econ-index-2026-09-19.md)。

---

## 0) One-line scope

把 ST 名称的输入时间、缺名继承、档位消费和真实成交影响分别钉住，保留书/v7 当前分叉；不把日期 as-of 升格为外部名称数据已满足决策时刻 PIT 的证明。

## 1) Why now

δ1 已锁费率，δ2 已锁 E-R6 参考价与经济残留；两刀都没有修复 v7 ST 时间语义。[next plan](plan-industry-align-next-2026-09-19.md) §6 和 engine SSOT 已记录分叉，基线也已有跨日测试。δ3 的价值是补齐证据边界与未来决策表，防止后续 δ4 把“有无档位”与“名称取自哪个日期”混为一事，或以统一 helper 为名改变历史成交。

## 2) Verified as-built anchors（本 IMPLEMENTATION_BASE 的 file:line）

以下行号重新核过当前源码，不照抄旧 plan 中已漂移的行号；均为仓内事实，不是交易所规则认证。

| 合同项 | 已核实行为 | 锚点 |
|---|---|---|
| 名称来源 | CSV 第二列；同文件代码去重保留首次；按窗口日期加载，只保留非空名。不是完整 ST 状态历史表 | `backtest/research/csv_pool.py:53-68`、`:161-182` |
| 书 resolver | `pool_names_by_day is None` 才用 flat map；否则从空 `last_seen` 起步，排序更新日期，消费 `date <= ds` 的非空名，缺名继承 | `backtest/research/csv_common.py:85-108` |
| resolver 接线 | shared loop 建立 resolver；daily/minute 每个会话调用 | `backtest/research/csv_simulate_loop.py:96-109`；`backtest/research/csv_daily_backtest.py:291-293`；`backtest/research/csv_minute_backtest.py:577-579` |
| 书入口 | 两个 `run()` 加载 by-day 名单，传入模拟器 | `backtest/research/csv_daily_backtest.py:537`、`:617`；`backtest/research/csv_minute_backtest.py:821`、`:913` |
| v7 平铺 | `flatten_pool_names` 依日期排序后 `dict.update`；context 对 start/end 窗口加载结果平铺，返回一个名称字典 | `backtest/research/ashare_session.py:81-100` |
| v7 消费 | `simulate_v7(names=...)` 无 by-day 参数；每会话取同一 flat map 名，算档位；CLI 经 context 传入 | `backtest/research/csv_minute_backtest_v7.py:277-282`、`:327-329`、`:571`、`:583-584` |
| ST 与板块 | 正则识别 ST / *ST；名称命中优先返回 5%，否则按代码板块；未知非 ST 可得 None；Decimal 半分向上到分 | `backtest/research/market_layer.py:15`、`:34-36`、`:57-84` |
| 书档位例外 | 显式 `qlib_limit_pct` 走固定 band，绕过 named limits。ST pins 必须使用默认 named-band 路径 | `backtest/research/csv_common.py:73-82` |
| 已有书侧 pins（当前测试行号） | 日期/非空名 loader；daily 缺名继承与未来 ST 不改早日；minute by-day 优先于 flat | `tests/test_csv_pool.py:97`；`tests/test_csv_daily_backtest.py:944`、`:969`；`tests/test_csv_minute_backtest.py:521` |
| 已有 v7 pins | 5% 门、窗口末名反向影响早日首开仓 | `tests/test_csv_minute_backtest_v7.py:254`、`:276` |

### 2.1 时间合同与最小反例

“窗末名”精确指**该代码在输入窗口内最后一次出现的名称**，不要求末日有该代码。名单 loader 不读 start 之前的历史；无可用名的已知主板代码回落板块档位。书 resolver 的游标只向前：它适用于现有递增会话循环，既不是任意日期可回查服务，也不保证返回的可变字典快照独立。`pool_names_by_day={}` 仍优先于 flat map，不能解释为空时自动 fallback。

正常 loader 已过滤空名，故窗口内空白行不会清除旧名；直接给 `flatten_pool_names` 注入含空字符串的字典时，`dict.update` 会覆盖为 `""`。§7.1 pins 分别覆盖真实 loader 输入合同和 helper 直传边界，保持两者实现不变。

| 合成夹具（主板 `600000.SH`、昨收 100、早日 14:55 close 105） | 书默认 named-band | v7 |
|---|---|---|
| D1 普通名，D2 改 *ST | D1 as-of 普通名，档位 110/90；其它门均满足才可买 | 平铺后 D1 也是 *ST，档位 105/95；首开仓 `skip_limit_up` |
| D1 *ST，D2 摘帽普通名 | D1 仍为 105/95；首买被拦 | 平铺后 D1 为 110/90；其它门均满足才可买 |
| D2 未列该代码/名称为空 | 继承 D1 已知非空名 | 经真实 loader 平铺后也保留该代码最后非空名 |

这是日期语义分叉，不是收益改善证据。书侧使用 D1 文件中的名称，不证明该文件在 D1 决策前已发布；当前输入没有 `available_at` / 修订版本过滤。v7 的窗口伸长可改变早日名称；书侧在相同初始条件、同一输入前缀下追加未来名称不应改变早日决策。二者都不能证明供应方历史版本 PIT。δ2 的因子可得性问题独立保留，不能由 ST 契约替它关闭。

### 2.2 已关 / 仍钉 / deferred

| 面 | 当前状态 | δ3 处理 |
|---|---|---|
| ST 识别、Decimal 档位与书/v7 入口分叉 | 已有代码与若干 pins | 复用，不重复实施 |
| 两种改名方向、缺名、空 by-day、窗口前缀敏感性、held 档位消费 | 既有覆盖复用；新增组合见 §7.1 | 本 feat 契约与 data-free pins；验收见 §8.4 |
| v7 改为逐日取名 | deferred，可能改变买卖与 NAV | 需 P3δ3.1=C，另开生产实施案 |
| 权威名称事件流、可得时间/修订 PIT、窗口前预载规则 | 未证 / deferred | B 可设计，不能写“PIT 已修好” |
| 14:57、产物列、touch↔mark | 既有 P1/P2/P4 挂起 | 本刀不重开 |

## 3) Delta roadmap（相对 δ1–δ2 与其它 δ）

| 刀 | 基线状态 / 本轮位置 | δ3 依赖与交接 |
|---|---|---|
| δ1 fees | post #123 基线已含合同/pins，生产费率冻结 | ST 变化不能掩盖现金门与 floor 差异 |
| δ2 exdiv reference | 合同/pins 已含；仅参考价 | 保留 mapped prev_close、因子 PIT/经济残留 |
| **δ3 ST PIT** | **本文件：Human GO A，契约+data-free pins** | 先判明名字→档位，再讨论 δ4 |
| [δ4 limits-none](plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md) | 独立决策 | 不把 ST 未知名等同于 `limits=None` |
| [δ5 volume-cap](plan-industry-align-p3-d5-volume-cap-2026-09-19.md) | 设计/契约 | 不借容量门改 ST 或交易时点 |
| [δ6 economics](plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md) | Human GO A 残留+oracle，账本可选 B docs | 与 ST 证据分离；生产需该刀另裁显式 C，本轮不授权 |

## 4) F-R* hard locks

| ID | 硬锁 |
|---|---|
| **F-R1** | 本 feat 仅 §8.1 白名单三份 Markdown + 六个既有测试文件。生产 Python、配置/依赖/CI 均不改；价格/reason/shares/cash/NAV/CLI 零变更。 |
| **F-R2** | 书 by-day 优先、单调游标、缺名继承、v7 窗口平铺保持原样；不得自动统一。 |
| **F-R3** | 日期 as-of ≠ 决策时刻可得性证明；窗口末名 ≠ 全历史最新名称。 |
| **F-R4** | pin 分清名字、档位、拦截、真实成交四层；资金/T+1/其它门仍决定是否成交。 |
| **F-R5** | ST 优先于板块的 as-built 与 qlib band 例外照实记录；不重新解释真实交易所政策。 |
| **F-R6** | δ1/δ2 保持；P1/P2/P4 挂起；δ4–δ6 不随 δ3 默认获批。 |
| **F-R7** | 所有新增夹具用内存或 tmp_path；不跑 CLI/宿主回测，不读湖，不下载/采集名称数据。 |
| **F-R8** | 固定 §8/§9 生产冻结超集；热路径 import fence 仍为既有枚举，不扩成目录扫描。 |
| **F-R9** | 不引入 LEBS/MockQMT/live、Cerebro、PortAnaRecord；只属于本仓向量化研究。 |
| **F-R10** | C 只在新的人裁记录、明确生产差异与独立实施 PR 后生效；本 plan 发布不构成 C。 |

## 5) P* human cuts（Human GO A/A/A 已录入）

> **Human GO recorded 2026-09-19 (Asia/Shanghai):** P3δ3.1=A、P3δ3.2=A、P3δ3.3=A — δ3=A：契约 + data-free pins，不改生产。本 feat 实施 Slice A→B→C docs/tests；B/C 人裁选项未采纳，生产保持冻结。

本表 ID 是 δ3 局部编号，不能覆盖 next plan 的 P1/P2/P4；“Slice C 验收”也不是“人裁选项 C”。

| ID / 决策 | A | B | C | 本轮人裁 |
|---|---|---|---|---|
| **P3δ3.1：交付层级** ✅ Human GO 2026-09-19 | 记录分叉 + data-free pins；生产零行为变更 | 设计 v7 as-of 输入/迁移合同，仍不改生产 | 单独批准 v7 ST PIT 生产改造；明确历史结果可变 | **A** |
| **P3δ3.2：输入时间证据** ✅ Human GO 2026-09-19 | 声明仅名单日期 as-of，可得性未证 | 设计 effective date / available_at / revision 及上游证据要求 | 有真实证据后批准新数据合同与消费接线 | **A** |
| **P3δ3.3：缺名/窗口初态** ✅ Human GO 2026-09-19 | 保留非空名继承、窗口内输入与 helper 差异 | 设计缺名 unknown/前置快照等候选规则 | 批准改变缺名/预载/回退行为并列受影响入口 | **A** |

任何 C 都须先核实 B 级输入合同、列出迁移前后真值表与生产路径，再另开人裁/实施案。只选 B 不授权采集外部数据、增加参数或替换名称 resolver。本轮在 post #124 固定基线上按 A/A/A 实施 δ3 契约/pins。

## 6) Non-goals

- 不修 v7 非 PIT 分叉，不给书侧颁发完整 PIT 认证，不回填/生成真实名称历史。
- 不修改 ST 正则、板块档位、Decimal、缺昨收/未知板块政策、买卖时钟或交易产物 schema。
- 不改 pool 1–10 BOOKS 注册、不改 v7 池来源、不接 L2，不跑收益对比。
- 不借本刀关闭 δ2 因子恢复日错域、可得性、噪声带、v4 SMA 或 δ6 经济残留。

## 7) Slices A → B → C（本 feat：契约、pins、验收）

§5 Human GO A/A/A 已授权本节 docs + data-free pins 及验收；所有生产冻结。设计 B 分支仅为未采纳的候选，不随本次 A 获授权。

### Slice A：证据合同与输入矩阵

复核 §2，按人裁结果把“名单日期”和“决策可得时刻”拆开写入 [engine SSOT §2.2](engine-ashare-correctness.md#22-p3-δ3-st-name-as-of--v7-flatten-forkhuman-go-aaa)，README 链接同一合同。DoD：两种改名方向、缺名、直传/loader、窗口起点、单调游标、qlib band 例外齐全；状态准确标注，所有生产冻结。

### Slice B：data-free pins（复用既有文件；实际新增映射见 §7.1）

| Pin | 既有落点 / 复用证据 | 本次验收断言 |
|---|---|---|
| B1 输入时间 | `tests/test_csv_pool.py`，现有 `test_load_pool_names_by_day_keeps_dates_and_non_empty_names` | 双日期/空名/窗口边界；缺名不产生摘帽事件；显式 tmp_path |
| B2 书 as-of | `tests/test_csv_daily_backtest.py`、`tests/test_csv_minute_backtest.py`；§2 列出的已有 tests | 双向改名、缺名继承、空 by-day 优先、追加未来名的前缀一致性；用 public simulate 观察档位及真实买卖，不仅 helper |
| B3 v7 retained fork | `tests/test_csv_minute_backtest_v7.py`，现有 `test_v7_names_flatten_uses_window_end_name_for_earlier_day` | 增补摘帽方向与窗长变化；105 对应 5%/10% 两态；保留资金充足/T+1 控制条件 |
| B4 held 与边界 | `tests/test_ashare_session.py`、`tests/test_ashare_simulate_predicates.py` | 同一名称链作用于持仓 sell/add 档位；名字未知、板块未知、ST 命中独立设例；拦截与 fill 分断言 |

DoD：复用已覆盖项，仅补真缺口；返回可变字典需拍快照后比较。本次新增测试仅公开 `load_pool_names_by_day` / `flatten_pool_names` / `session_limit_prices` / `simulate` / `simulate_v7` 的合成调用；没有 CLI context 回测。held fixture 沿用既有 `seed` 注入少量持仓，observer 调真实档位函数并保存名称值，不持有 resolver 可变字典引用。

### Slice C：验收与冻结证明

实际执行 §8 的 data-free 命令并记录命令、exit、覆盖 pin；§9 零 diff。完成仅表示分叉合同验收，不表示 ST PIT 生产修复。若需要 C 级生产改造，须提交独立人裁/实施计划。

### 7.1 实际 pins 与覆盖映射

新增 **11 个测试函数 / 29 个参数化用例**；以下均为完整真实函数名，位于 B1–B4 指定的六个既有测试文件。其余 **145** 个既有用例保留并同批回归，不复制日线缺名继承、普通名→ST 或基础 v7 5% 门的已有断言。

| Pin / 文件 | 新增测试函数 | 用例数 / 验收含义 |
|---|---|---|
| B1 / `tests/test_csv_pool.py` | `test_d3_loader_window_and_empty_name_do_not_emit_unst` | 1；闭区间双日期、字符串/date 窗口、空名不发清空事件、窗口前不预载、窗口后摘帽不流入、末日缺代码仍保留旧名 |
| B2 / `tests/test_csv_daily_backtest.py` | `test_d3_daily_name_prefix_consistency_both_rename_directions`、`test_d3_daily_empty_by_day_beats_flat_st_name` | 2+1；两方向追加未来名，真实早日成交/权益前缀一致；`{}` 优先于 flat ST，而 None 才 fallback |
| B2 / `tests/test_csv_minute_backtest.py` | `test_d3_minute_name_prefix_consistency_both_rename_directions`、`test_d3_minute_empty_by_day_beats_flat_st_name`、`test_d3_minute_missing_name_inherits_through_real_loader` | 2+1+2；对应分钟入口；tmp_path 真实 loader 的缺行/空白名均继承 ST，105/100 门阻止首次买入 |
| B3 / `tests/test_csv_minute_backtest_v7.py` | `test_d3_v7_unst_window_extension_changes_earlier_fill` | 1；真实 loader 短窗 ST→长窗普通名，且末日缺该代码；早日价格 105 从 skip 变成真实 trial fill，档位/股数/现金分别断言 |
| B4 / `tests/test_ashare_session.py` | `test_d3_name_and_board_boundaries`、`test_d3_direct_flatten_empty_name_clears_unlike_loader` | 6+1；缺名主板、未知板块普通名、ST 优先未知/20%/30% 板块、WEST 不命中；直传空名覆盖与 loader 合同分开 |
| B4 / `tests/test_ashare_simulate_predicates.py` | `test_d3_held_name_chain_sell_and_add_bands`、`test_d3_unknown_board_st_reaches_limit_gate_and_fill` | 6+6；三引擎 × held sell/add 共用“普通→ST→缺名→普通”名称链；真实档位 spy、gate 与 fill 独立断言。未知板块 ST 在 105 拦截、104 真实买入 |

所有新增书侧用例使用默认 named-band，资金充足；held 卖出 lot 在决策前已持有，满足 T+1；书加仓用 `monkeypatch` 临时启用既有 `allow_add` 路径，测试后恢复。minute 扫描器内拦截不保证外层 `defer_sell_limit_down` 增加，沿用现有分叉，不为计数改生产。前缀一致性比较 BUY/SELL 与早日权益，末窗 `EOD_MARK` 不算成交。旧 daily `test_pool_name_asof_missing_held_code_falls_back_to_yesterday`、minute `test_pool_name_asof_normal_then_st_and_by_day_beats_flat_map`、v7 `test_v7_names_flatten_uses_window_end_name_for_earlier_day` 继续作为复用证据。

这些 pins 只固定合成日期合同，不证明数据发布时刻/历史修订 PIT；v7 日期分叉、P1/P2/P4、δ2 因子可得性与经济残留仍 deferred。qlib 固定 band 例外通过 §2 源码合同记录，本次不改该路径。

## 8) Linux/CI isomorphic acceptance（本 feat 的真实命令）

### 8.1 基线、九路径白名单、编码与 whitespace

从仓库根目录用 Bash 执行。`IMPLEMENTATION_BASE` 是本 feat worktree 起点的 `git rev-parse HEAD` 实测值；以下重新解析同一固定 commit，不跟随移动的 master、不推算 merge-base。proposal 历史锚点见页首，不用于本轮冻结。

```bash
set -euo pipefail
IMPLEMENTATION_BASE="$(git rev-parse --verify 'cce17f319ead5c64a202632c3665b4eeb3e3e7a5^{commit}')"
[[ "$IMPLEMENTATION_BASE" =~ ^[0-9a-f]{40}$ ]]
git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD
P3_ALLOWED=(
  docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md
  docs/backtest/engine-ashare-correctness.md
  docs/backtest/README.md
  tests/test_csv_pool.py
  tests/test_csv_daily_backtest.py
  tests/test_csv_minute_backtest.py
  tests/test_csv_minute_backtest_v7.py
  tests/test_ashare_session.py
  tests/test_ashare_simulate_predicates.py
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
  for allowed_path in "${P3_ALLOWED[@]}"; do
    if [[ "$path" == "$allowed_path" ]]; then p3_allowed=true; break; fi
  done
  if [[ "$p3_allowed" != true ]]; then
    printf 'OUT OF SCOPE: %s\n' "$path"; exit 1
  fi
done < "$P3_AUDIT_DIR/paths"
for path in "${P3_ALLOWED[@]}"; do
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
for path in "${P3_ALLOWED[@]}"; do
  p3_ws_rc=0
  git diff --no-index --check /dev/null "$path" > "$P3_AUDIT_DIR/whitespace" || p3_ws_rc=$?
  if [[ "$p3_ws_rc" -gt 1 || -s "$P3_AUDIT_DIR/whitespace" ]]; then
    cat "$P3_AUDIT_DIR/whitespace"; exit 1
  fi
done
```

最后的循环也覆盖未跟踪文本；no-index 正常内容差异可返回 1，故同时要求 rc≤1 且 whitespace 诊断为空，不能简单忽略所有非零退出码。全路径审计覆盖 base→HEAD、staged、unstaged、untracked，不靠一张有限冻结表推断其它路径安全。本次 Human GO 与实施指令仅允许上述三份 docs + 六个既有 tests，**不允许任何生产 Python 或其它路径修改**。

### 8.2 Slice B/C：真实 data-free tests / gates

本次按 Human GO 执行下列命令，结果单列 §8.4。CI 同构依据为 `.github/workflows/python-tests.yml:27-43`、`:49-56` 的受控 Python 3.12、四个 repo-only gates 与 pytest marker；这是定向合同验收，不代表全量 CI 或宿主回测。

实施指令显式指定 Linux 已准备好的 `/tmp/industry-align-venv/bin/python`（3.12）；本轮不回落系统 python/pip、不安装依赖、不探测数据路径。

```bash
set -euo pipefail
P3_CONTRACT_PYTHON=/tmp/industry-align-venv/bin/python
[[ -x "$P3_CONTRACT_PYTHON" ]]
"$P3_CONTRACT_PYTHON" -c 'import sys, pytest, pandas, numpy, pyarrow; assert sys.version_info[:2] == (3, 12); print(sys.executable)'
"$P3_CONTRACT_PYTHON" scripts/gates/verify_oskh_data_contract.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_data_path_ssot.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_no_hardcoded_machine_paths.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_tr_bridge_import_ssot.py

# §7 实际既有落点文件；完整执行，包含新增 pins 与既有回归。
"$P3_CONTRACT_PYTHON" -m pytest -q -m "not production and not benchmark" \
  tests/test_csv_pool.py \
  tests/test_csv_daily_backtest.py \
  tests/test_csv_minute_backtest.py \
  tests/test_csv_minute_backtest_v7.py \
  tests/test_ashare_session.py \
  tests/test_ashare_simulate_predicates.py

# 固定热路径边界与 δ1 回归，不能单独替代本刀 pins。
"$P3_CONTRACT_PYTHON" -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_simulate_import_fence.py \
  tests/test_ashare_fees.py \
  tests/test_ashare_fee_wiring.py
```

所有 gate/test 路径在本基线真实存在；无新造仓内验收脚本。新增测试只使用合成内存 `simulate` / `simulate_v7` 单元向量或显式 tmp_path；既有 CLI 空池测试仅 pytest 内 stub I/O。没有 CLI/宿主回测、湖访问或真实行情输出验收。缺环境依赖记阻塞；必需 pin 被 skip 不算通过；只跑旧测试不能声称 §7 新组合已覆盖。

### 8.3 默认生产冻结（本次及未来 A/B；数组与 §9 逐项相同）

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

验证 HEAD / 固定 IMPLEMENTATION_BASE 均为 `cce17f319ead5c64a202632c3665b4eeb3e3e7a5`；受测代码为本 feat 的**未提交工作区**，没有虚构实现 commit。2026-09-19（Asia/Shanghai），在 `/workspace/wt-p3-d3-st-pit-feat`、Linux / CPython **3.12.13** 上执行；显式解释器 `/tmp/industry-align-venv/bin/python`，没有依赖安装、网络或湖访问。

| 命令 / 检查 | 本次结果 | exit |
|---|---|---|
| §8.1 固定基线祖先、九路径白名单（HEAD/index/worktree/untracked）、编码、whitespace | PASS；仅三份 docs + 六个既有 tests；UTF-8、BOM=0、NUL=0 | 0 |
| §8.2 `"$P3_CONTRACT_PYTHON" -c 'import sys, pytest, pandas, numpy, pyarrow; assert sys.version_info[:2] == (3, 12); print(sys.executable)'`（实跑同时打印版本） | CPython 3.12.13；依赖导入成功 | 0 |
| `/tmp/industry-align-venv/bin/python scripts/gates/verify_oskh_data_contract.py` | OK | 0 |
| `/tmp/industry-align-venv/bin/python scripts/gates/verify_data_path_ssot.py` | 7 hits、0 violations | 0 |
| `/tmp/industry-align-venv/bin/python scripts/gates/verify_no_hardcoded_machine_paths.py` | OK | 0 |
| `/tmp/industry-align-venv/bin/python scripts/gates/verify_tr_bridge_import_ssot.py` | OK，2 consumers | 0 |
| §8.2 `/tmp/industry-align-venv/bin/python -m pytest -q -m 'not production and not benchmark'` + 六个完整测试文件（路径逐项如上） | **174 passed / 0 skipped**；新增 **11 函数 / 29 用例**，既有 145 用例；B1=1、B2=8、B3=1、B4=19 | 0 |
| §8.2 同一 pytest 命令 + `test_ashare_simulate_import_fence.py` / `test_ashare_fees.py` / `test_ashare_fee_wiring.py` | **38 passed / 0 skipped** | 0 |
| §8.3 `git diff --exit-code "$IMPLEMENTATION_BASE" -- backtest/research/` | **PASS：全部 research 生产文件零 diff** | 0 |
| §8.3 `git diff --exit-code "$IMPLEMENTATION_BASE" -- '*.py' ':(exclude)tests/**'` | **PASS：全仓测试目录外 Python 零 diff** | 0 |
| §8.3 四种冻结 diff（base→worktree、base→HEAD、unstaged、staged） | **22 冻结文件零 diff** | 0 |
| §8.3 数组 / §9 表逐项与顺序核对；原表行对基线比对；§7.1 函数名与 AST 核对 | PASS；22 路径一致、原冻结表行保持原文、11 个真实新增函数均已映射 | 0 |

定向验收共 **212 passed**，不代表全量 CI 或宿主回测。六文件 suite 的 2 条 warning 来自既有 `ashare_bars.py:503` pandas `copy` 参数弃用，不改生产压警告。首轮仅新增 pins 试跑为 27 passed / 2 failed：短窗多一条末日 `EOD_MARK` 导致前缀比较失败；修正夹具断言为真实 BUY/SELL + 早日权益后，完整六文件 174 passed。没有生产修复、skip/xfail 或以门放行冒充真实成交。

Slice A→B→C 验收完成只表示分叉合同与 data-free pins 通过：Human GO A/A/A、全部生产 Python 零 diff。决策时刻可得性 PIT 未证、v7 日期分叉保持，P1/P2/P4 及 δ4–δ6 的独立授权边界不变；本轮不提交、推送或开/合 PR。

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

本表与 §8.3 数组的路径/顺序必须一致。表内零 diff 只证明这些文件；§8.3 另查全部 `backtest/research/`，§8.1 全路径白名单禁止九路径以外的生产、测试、CI 或数据修改。不能以本表未列出为理由改生产；不扩大固定热路径 import-fence 测试的扫描面。


## 10) Changelog

- **v0.3 (2026-09-19，Asia/Shanghai)**：按 Human GO A/A/A 实施 Slice A→B→C；实施基线刷新为 post #124 `cce17f319ead5c64a202632c3665b4eeb3e3e7a5`，proposal 基线留作历史。engine SSOT §2.2 / README 落 ST 日期 as-of 与 v7 窗末平铺合同，六个既有测试文件新增 11 函数 / 29 用例，B1–B4 映射见 §7.1。§8.4 记录 174+38 passed、四 gates、九路径白名单、编码与 22 文件/全 research/全仓生产 Python 零 diff；§9 原冻结表不改。保留未提交交付，不改生产、不把日期顺序宣称为完整 PIT。
- **v0.2 (2026-09-19，Asia/Shanghai)**：录入 Human GO P3δ3.1/3.2/3.3=A/A/A，授权后续 Slice A→B→C 契约+data-free pins；生产冻结，P1/P2/P4 继续挂起。仅更新 GO 记录，未实施 slices、未新增/执行测试，未改 `IMPLEMENTATION_BASE`、白名单、冻结表或 §8 命令。
- **v0.1 (2026-09-19)**：从 post #123 基线重核 ST 真实接线与既有测试；提出 δ3 A/B/C、人裁默认 A、未来 slices 与冻结超集。只新增 plan，未实施生产/测试变化，未执行回测/湖或宣称 PIT 已关闭。
