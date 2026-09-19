# Plan: industry-align P3 δ3 ST PIT contract (2026-09-19)

> **Status**: **v0.2 · docs-only · Human GO A/A/A recorded 2026-09-19（Asia/Shanghai）**：P3δ3.1/3.2/3.3=A；授权后续 Slice A→B→C docs + data-free pins，生产冻结。本次仅录入 GO，未实施本 plan 的未来 slices，未新增/执行测试。
> **Main ship / 单行范围**: 契约化书侧按名单日期 as-of 与 v7 窗口末次名称平铺的 ST 分叉；默认未来只做 docs + data-free pins，生产零行为变更。
> **IMPLEMENTATION_BASE**: `1049b904bdd818dbb79f51f1830a008c8f83b141`（本 worktree 起点，已由 `git rev-parse HEAD` 核实全 40 字符；post #123，含 δ1 + δ2）。
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
| 已有书侧 pins | 日期/非空名 loader；daily 缺名继承与未来 ST 不改早日；minute by-day 优先于 flat | `tests/test_csv_pool.py:96`；`tests/test_csv_daily_backtest.py:944`、`:969`；`tests/test_csv_minute_backtest.py:521` |
| 已有 v7 pins | 5% 门、窗口末名反向影响早日首开仓 | `tests/test_csv_minute_backtest_v7.py:254`、`:276` |

### 2.1 时间合同与最小反例

“窗末名”精确指**该代码在输入窗口内最后一次出现的名称**，不要求末日有该代码。名单 loader 不读 start 之前的历史；无可用名的已知主板代码回落板块档位。书 resolver 的游标只向前：它适用于现有递增会话循环，既不是任意日期可回查服务，也不保证返回的可变字典快照独立。`pool_names_by_day={}` 仍优先于 flat map，不能解释为空时自动 fallback。

正常 loader 已过滤空名，故窗口内空白行不会清除旧名；直接给 `flatten_pool_names` 注入含空字符串的字典时，`dict.update` 会覆盖为 `""`。未来 pin 必须区分真实 loader 输入合同和 helper 直传边界，不能为统一二者偷偷改实现。

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
| 两种改名方向、缺名、空 by-day、窗口前缀敏感性、held 档位消费 | 现状可解释；专门组合覆盖仍需盘点/补 pin | 默认仅契约与未来 data-free pins |
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
| **F-R1** | 本 PR 仅五份 Markdown；默认未来 docs + data-free pins。生产价格/reason/shares/cash/NAV/CLI 均零变更。 |
| **F-R2** | 书 by-day 优先、单调游标、缺名继承、v7 窗口平铺保持原样；不得自动统一。 |
| **F-R3** | 日期 as-of ≠ 决策时刻可得性证明；窗口末名 ≠ 全历史最新名称。 |
| **F-R4** | pin 分清名字、档位、拦截、真实成交四层；资金/T+1/其它门仍决定是否成交。 |
| **F-R5** | ST 优先于板块的 as-built 与 qlib band 例外照实记录；不重新解释真实交易所政策。 |
| **F-R6** | δ1/δ2 保持；P1/P2/P4 挂起；δ4–δ6 不随 δ3 默认获批。 |
| **F-R7** | 所有未来夹具用内存或 tmp_path；不跑 CLI/宿主回测，不读湖，不下载/采集名称数据。 |
| **F-R8** | 固定 §8/§9 生产冻结超集；热路径 import fence 仍为既有枚举，不扩成目录扫描。 |
| **F-R9** | 不引入 LEBS/MockQMT/live、Cerebro、PortAnaRecord；只属于本仓向量化研究。 |
| **F-R10** | C 只在新的人裁记录、明确生产差异与独立实施 PR 后生效；本 plan 发布不构成 C。 |

## 5) P* human cuts（Human GO A/A/A 已录入）

> **Human GO recorded 2026-09-19 (Asia/Shanghai):** P3δ3.1=A、P3δ3.2=A、P3δ3.3=A — δ3=A：契约 + data-free pins，不改生产。授权后续 Slice A→B→C docs/tests；本次未实施，B/C 人裁选项未采纳，生产保持冻结。

本表 ID 是 δ3 局部编号，不能覆盖 next plan 的 P1/P2/P4；“Slice C 验收”也不是“人裁选项 C”。

| ID / 决策 | A | B | C | 本轮人裁 |
|---|---|---|---|---|
| **P3δ3.1：交付层级** ✅ Human GO 2026-09-19 | 记录分叉 + data-free pins；生产零行为变更 | 设计 v7 as-of 输入/迁移合同，仍不改生产 | 单独批准 v7 ST PIT 生产改造；明确历史结果可变 | **A** |
| **P3δ3.2：输入时间证据** ✅ Human GO 2026-09-19 | 声明仅名单日期 as-of，可得性未证 | 设计 effective date / available_at / revision 及上游证据要求 | 有真实证据后批准新数据合同与消费接线 | **A** |
| **P3δ3.3：缺名/窗口初态** ✅ Human GO 2026-09-19 | 保留非空名继承、窗口内输入与 helper 差异 | 设计缺名 unknown/前置快照等候选规则 | 批准改变缺名/预载/回退行为并列受影响入口 | **A** |

任何 C 都须先核实 B 级输入合同、列出迁移前后真值表与生产路径，再另开人裁/实施案。只选 B 不授权采集外部数据、增加参数或替换名称 resolver。本轮 A/A/A 已正式录入；合并 #124 后先推进 δ3 契约/pins feat，本次仅记录 GO。

## 6) Non-goals

- 不修 v7 非 PIT 分叉，不给书侧颁发完整 PIT 认证，不回填/生成真实名称历史。
- 不修改 ST 正则、板块档位、Decimal、缺昨收/未知板块政策、买卖时钟或交易产物 schema。
- 不改 pool 1–10 BOOKS 注册、不改 v7 池来源、不接 L2，不跑收益对比。
- 不借本刀关闭 δ2 因子恢复日错域、可得性、噪声带、v4 SMA 或 δ6 经济残留。

## 7) Slices A → B → C（未来路径；本次未实施）

§5 Human GO A/A/A 已授权本节未来 docs + data-free pins 及验收；所有生产冻结。下面的设计 B 分支仅为未采纳的候选，不随本次 A 获授权。

### Slice A：证据合同与输入矩阵

复核 §2，按人裁结果把“名单日期”和“决策可得时刻”拆开写入合同。DoD：两种改名方向、缺名、直传/loader、窗口起点、qlib band 例外齐全；状态仍准确标注，所有生产冻结。若选设计 B，只在文档增加候选数据模型。

### Slice B：data-free pins（真实已有文件；下表新增项均尚未落地）

| Pin | 既有落点 / 复用证据 | 未来验收断言 |
|---|---|---|
| B1 输入时间 | `tests/test_csv_pool.py`，现有 `test_load_pool_names_by_day_keeps_dates_and_non_empty_names` | 双日期/空名/窗口边界；缺名不产生摘帽事件；显式 tmp_path |
| B2 书 as-of | `tests/test_csv_daily_backtest.py`、`tests/test_csv_minute_backtest.py`；§2 列出的已有 tests | 双向改名、缺名继承、空 by-day 优先、追加未来名的前缀一致性；用 public simulate 观察档位及真实买卖，不仅 helper |
| B3 v7 retained fork | `tests/test_csv_minute_backtest_v7.py`，现有 `test_v7_names_flatten_uses_window_end_name_for_earlier_day` | 增补摘帽方向与窗长变化；105 对应 5%/10% 两态；保留资金充足/T+1 控制条件 |
| B4 held 与边界 | `tests/test_ashare_session.py`、`tests/test_ashare_simulate_predicates.py` | 同一名称链作用于持仓 sell/add 档位；名字未知、板块未知、ST 命中独立设例；拦截与 fill 分断言 |

DoD：复用已覆盖项，仅补真缺口；返回可变字典需拍快照后比较。v7 CLI context 链如需 pin，应 stub exdiv/bars/index/writer，仅用临时名单，不误调用湖。未来测试名在实施时命名，本计划不冒充它们已经存在。

### Slice C：验收与冻结证明

实际执行 §8 的未来 data-free 命令并记录命令、exit、覆盖 pin；§9 零 diff。完成仅表示分叉合同验收，不表示 ST PIT 生产修复。若需要 C 级生产改造，停止默认路径并提交独立人裁/实施计划。

## 8) Linux/CI isomorphic acceptance（真实命令；区分本次 docs 与未来 pins）

### 8.1 本次 docs-only：基线、全路径、编码与 whitespace

从仓库根目录用 Bash 执行。`IMPLEMENTATION_BASE` 是本 worktree 起点的 `git rev-parse HEAD` 实测值；以下重新解析同一固定 commit，不跟随移动的 master、不推算 merge-base。将来实施分支若换基线，须在人裁/实施记录中重新用 `git rev-parse` 写全 SHA，并保留此 proposal 的历史锚点。

```bash
set -euo pipefail
IMPLEMENTATION_BASE="$(git rev-parse --verify '1049b904bdd818dbb79f51f1830a008c8f83b141^{commit}')"
[[ "$IMPLEMENTATION_BASE" =~ ^[0-9a-f]{40}$ ]]
git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD
P3_DOCS=(
  docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md
  docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md
  docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md
  docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md
  docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md
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
  for doc in "${P3_DOCS[@]}"; do
    if [[ "$path" == "$doc" ]]; then p3_allowed=true; break; fi
  done
  if [[ "$p3_allowed" != true ]]; then
    printf 'OUT OF SCOPE: %s\n' "$path"; exit 1
  fi
done < "$P3_AUDIT_DIR/paths"
for path in "${P3_DOCS[@]}"; do
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
for path in "${P3_DOCS[@]}"; do
  p3_ws_rc=0
  git diff --no-index --check /dev/null "$path" > "$P3_AUDIT_DIR/whitespace" || p3_ws_rc=$?
  if [[ "$p3_ws_rc" -gt 1 || -s "$P3_AUDIT_DIR/whitespace" ]]; then
    cat "$P3_AUDIT_DIR/whitespace"; exit 1
  fi
done
```

最后的循环覆盖尚未跟踪的新文档；no-index 正常内容差异可返回 1，故同时要求 rc≤1 且 whitespace 诊断为空，不能简单忽略所有非零退出码。全路径审计覆盖 base→HEAD、staged、unstaged、untracked，不靠一张有限冻结表推断其它路径安全。未来 tests-only 实施时必须先在新实施记录中批准/列出 §7 实际测试落点并收窄更新白名单；**本次五文档白名单不允许任何 tests/Python 修改**。

### 8.2 未来 Slice B/C：真实 data-free tests / gates（本 PR 不执行）

以下仅在未来获准的合同/pins 刀执行；本次不会以“现有测试存在”冒报“本次测试已通过”。CI 同构依据为 `.github/workflows/python-tests.yml:27-43`、`:49-56` 的受控 Python 3.12、四个 repo-only gates 与 pytest marker；这是定向合同验收，不代表全量 CI 或宿主回测。

遵循 AGENTS 解释器顺序：`OSKH_MERGE_PYTHON` → `VANNA312_PYTHON` → `VANNA311_PYTHON`。Linux 先显式指定已准备好的项目/CI 3.12 解释器；未设置时本命令失败，不偷偷回落系统 python/pip。Windows 默认解释器由现有 `scripts/_script_bootstrap.py` 的 `resolve_oskh_python` 管理，本命令不探测盘符、不安装依赖。

```bash
set -euo pipefail
P3_CONTRACT_PYTHON="${OSKH_MERGE_PYTHON:-${VANNA312_PYTHON:-${VANNA311_PYTHON:-}}}"
: "${P3_CONTRACT_PYTHON:?Set OSKH_MERGE_PYTHON to a controlled Python 3.12 executable}"
[[ -x "$P3_CONTRACT_PYTHON" ]]
"$P3_CONTRACT_PYTHON" -c 'import sys, pytest, pandas, numpy, pyarrow; assert sys.version_info[:2] == (3, 12); print(sys.executable)'
"$P3_CONTRACT_PYTHON" scripts/gates/verify_oskh_data_contract.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_data_path_ssot.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_no_hardcoded_machine_paths.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_tr_bridge_import_ssot.py

# §7 实际既有落点文件；新增 pin 完成后，逐项记录实际执行结果。
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

所有 gate/test 路径在本基线真实存在；无新造验收脚本。未来只允许合成内存 `simulate` / `simulate_v7` 单元向量或显式 tmp_path/I/O stub，不允许 CLI/宿主回测、湖访问和以真实行情输出为验收。本次连这些合成 tests 也不运行。缺环境依赖记阻塞；必需 pin 被 skip 不算通过；只跑旧测试不能声称 §7 待补组合已覆盖。

### 8.3 默认生产冻结（本次及未来 A/B；与 §9 逐项相同）

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
git diff --exit-code "$IMPLEMENTATION_BASE" -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code "$IMPLEMENTATION_BASE" HEAD -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --cached --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
```

### 8.4 验收结论的范围

本 PR 只可记录 docs 路径、UTF-8/BOM/NUL、whitespace、锚点/链接/真实文件名、冻结数组与表一致性；未运行 §8.2、未新增测试、未实施 §7。将来 Slice C 要另填“commit / 基线 / 环境 / 命令 / exit / 实际 pin / skip / 冻结结果”，不得挪用 δ1/δ2 的历史 passed 数。默认 A/B 全部生产零 diff；如需 C，必须另立明确生产范围和验收合同，不能删除本冻结检查来假装默认路径仍通过。

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

本表与 §8.3 数组的路径/顺序必须一致。表内零 diff 只证明这些文件；§8.1 的全路径白名单另行禁止其它生产与测试修改。不能以本表未列出为理由修改任何 Python、测试、CI 或数据文件；不扩大固定热路径 import-fence 测试的扫描面。


## 10) Changelog

- **v0.2 (2026-09-19，Asia/Shanghai)**：录入 Human GO P3δ3.1/3.2/3.3=A/A/A，授权后续 Slice A→B→C 契约+data-free pins；生产冻结，P1/P2/P4 继续挂起。仅更新 GO 记录，未实施 slices、未新增/执行测试，未改 `IMPLEMENTATION_BASE`、白名单、冻结表或 §8 命令。
- **v0.1 (2026-09-19)**：从 post #123 基线重核 ST 真实接线与既有测试；提出 δ3 A/B/C、人裁默认 A、未来 slices 与冻结超集。只新增 plan，未实施生产/测试变化，未执行回测/湖或宣称 PIT 已关闭。
