# Plan: industry-align P3 δ5 volume participation cap design (2026-09-19)

> **Status**: **v0.3 · design docs landed · Slice A（+C docs acceptance）完成（§8.4） · Human GO P3δ5.1=B（2026-09-19，Asia/Shanghai）**：只设计，不接生产 cap；未授权 `.1=C`。本 feat 仅三份 docs；Slice B SKIPPED，未新增/修改/执行测试，生产对固定基线零 diff，保留未提交工作区交付。
> **Main ship / 单行范围**: 成交量 participation cap 的数据、时间、预算与部分成交候选合同及 D1–D7 文档算术 oracle 已落 engine SSOT §2.4 / README；当前无 participation cap，生产不变。
> **IMPLEMENTATION_BASE**: `e0250efb2fae42e4e7f38a9585b1b4e95a1529bc`（本 feat worktree 起点，已由 `git rev-parse HEAD` 核对全 40 字符；post #126，含 δ4）。历史 proposal 基线 `1049b904bdd818dbb79f51f1830a008c8f83b141` 仅保留沿革，不用于本 feat 冻结证明。
> **Human GO recorded**: **P3δ5.1=B（只设计）**；授权设计文档落地，其它项按 §5 推荐保留为 B 下的设计候选，不视为已裁生产政策。生产 cap 接线未授权；P1/P2/P4 继续挂起。
> **前序**: [δ1 fees](plan-industry-align-p3-fees-2026-09-19.md)、[δ2 exdiv](plan-industry-align-p3-d2-exdiv-2026-09-19.md)、[next fill gates](plan-industry-align-next-2026-09-19.md)、[engine SSOT](engine-ashare-correctness.md)；[四刀索引](plan-industry-align-p3-d345-econ-index-2026-09-19.md)。

---

## 0) One-line scope

为未来容量约束建立可证伪的输入/预算/成交/剩余量合同与 data-free oracle，明确“零量过滤已有、按成交量限额尚无”；本次只交文档，不增加生产撮合参数、成交量列或部分成交。

## 1) Why now

δ1 已固定佣金调用粒度；δ2 已固定参考价换域但保留原股数。容量门若切碎成交，会影响 fee floor、T+1 lot、跟单/台阶、pending 与 NAV，不能视作一个局部 `min(shares, volume)` 修补。现有分钟帧还丢弃 volume，本刀必须先设计可得时间与数据单位，再决定是否值得另开生产案。这里只陈述仓内模型边界，不提供真实市场容量或收益估计。

## 2) Verified as-built anchors（以本 IMPLEMENTATION_BASE 为准）

以下按 `git show e0250efb2fae42e4e7f38a9585b1b4e95a1529bc:<path>` 重新阅读核实；既有测试仅作源码锚点，本轮不运行、不新增或修改。落地合同见 [engine SSOT §2.4](engine-ashare-correctness.md#24-p3-δ5-volume-participation-cap-designhuman-go-b)。

| 合同项 | 已核实行为 | file:line |
|---|---|---|
| 书买量 | `_buy_size(per_quota, price)` 按预算取整百股；不足一手可由补充资金凑 100；无 volume 入参 | `backtest/research/csv_ledger.py:187-197` |
| 书成交记账 | `execute_buy` 检查含佣金现金后建 lot；`_sell` 按该 Position 全部 shares 记一笔 | `backtest/research/csv_ledger.py:200-258`、`:261-276` |
| 共享买路径 | chase/pool/step 以预算、价格、现金决定量；`apply_capital_ration` 是资金分配次序，不是市场参与率 | `backtest/research/csv_simulate_loop.py:79-90`、`:181-189`、`:287-306`、`:362-378` |
| v7 买卖量 | `_buy` 为 NAME_BUDGET×fraction 后向下整百；`_sell_lots` 汇总符合 T+1/kind 的数量；没有 volume 参数 | `backtest/research/csv_minute_backtest_v7.py:57`、`:205-251` |
| 日线 volume | 可选读取 volume，用零量剔除占位 K，随即丢 `_volume`；缺列保持旧路径 | `backtest/research/csv_daily_loader.py:69-96` |
| 湖分钟 volume | 可选读入，按会话内记录的日汇总去掉整日零量，随后丢 `_volume`；并非逐分钟零量拒绝 | `backtest/research/ashare_bars.py:343-371` |
| qlib 分钟帧 | 读取 open/high/close，输出 date/hm/open/high/close；该路径没有 volume 列 | `backtest/research/qlib_bin_1min.py:34-65` |
| 持仓分钟扫描 | 输入数组 open/high/close/hm 与规则参数；此处无容量预算 | `backtest/research/csv_minute_backtest.py:619-642` |
| 日线/分钟 loader pins | 零量、有/无 volume 两种路径已覆盖 | `tests/test_csv_daily_backtest.py:78`、`:101`；`tests/test_csv_minute_backtest.py:27`、`:56` |
| 现有资金/多 lot pins | quota 等分/逐日重置、已有名加 lot | `tests/test_csv_daily_backtest.py:533`、`:612`、`:643`；费率用 `tests/test_ashare_fee_wiring.py` |

当前缺少的是本表 CSV 书/v7 撮合路径的**市场成交量预算**。不据此断言全仓所有其它研究模型都没有 volume，也不把 `has_volume` 读取成功等同于单位、复权域、累计/增量语义已认证。日线与分钟源的列结构不同；只靠在买量函数加一个参数不能完成接线。

### 2.1 已关 / 仍钉 / deferred

| 面 | 基线状态 | 本刀处理 |
|---|---|---|
| 预算整手、含费资金门、T+1、零量占位过滤 | 已有实现/pins | 保留，不改成 participation cap 的证明 |
| 正成交量大小对当前撮合量无约束 | 上表接线可见；专门量变不变性 pins 可补 | 已记录源码合同；pins 仅未来候选，本轮不加 |
| 成交量单位、可得时刻、消费帧、预算归属 | 合同尚缺 | 本刀设计供人裁，不对真实湖做认证 |
| 部分成交、残量、费用重算、lot/state 迁移 | 未实现 | 提出独立 oracle；生产须 C |
| 价格冲击/排队与实际可成交概率 | 未建模/未证 | 不随 cap 关闭 |

### 2.2 候选合同（仅设计；不是 as-built / 不是新增默认值）

| 维度 | 推荐候选 | 尚须明确的边界 |
|---|---|---|
| 单位与域 | `V` 为该证券、该容量桶、raw 域的**增量股数**；单调累计量须先转换；保留 source/unit/时间元数据 | 不把手/金额/累计 volume 直接当股；不能从成交额猜单位，不对真实源自动猜测 |
| 时间可得性 | volume 仅可用于其已知之后的决策；优先设计已完成且有 available_at 的分钟桶 | 同 bar close 成交若使用整根成交量，只能称完成 bar 容量近似；开盘/盘中触发绝不能读取整日终值或未来 bar |
| 预算键 | 单次模拟内 `(symbol, session, bucket)` 共用一份容量；买卖双向合计占用，所有 pool/chase/step/held lot 共用 | 两个独立研究 run 不合并；日线与分钟容量不能叠加算两遍；side 独立预算是另一政策 |
| 容量公式 | `B=floor(p×V)`，`0<=p<=1`，以股计；`R=max(0,B-used)` | p 无本刀生产默认/经验推荐；示例 10% 只是算术夹具；使用明确十进制定点避免浮点边界误差 |
| 成交上限 | 先满足现有时点、ST/limits/T+1/资金门；实际 `q_fill<=min(q_requested,q_eligible,R)`，买入再按整手向下取整 | 凑一手不得突破 cap；资金不足时不扣容量；不得为了消耗容量改变成交价/提前成交 |
| 使用与释放 | 仅成功记账的实际股数增加 used；失败、纯 mark、价格/资格拒绝不占用；桶切换重置 | 如以后引入预留/并发，要再设计原子预留释放；本刀不增加订单服务 |
| 缺失与零值 | cap 启用后的候选：缺失/负数/非有限/单位未认证为 unavailable，拒绝该次尝试并可诊断；V=0 是有效零容量 | cap 未启用仍保持基线；不能新增静默无限容量 fallback；现有无 volume 路径不受本次影响 |
| 残量与状态 | 候选保留未成交持仓；买单未成部分在桶结束失效，不新建隐式跨桶队列 | 卖出 partial 后 stop/timer/pending 如何续行、ride_with/step 份额、v7 stage 何时跃迁必须逐项裁定 |

日线 close、daily gap-open/trigger、分钟 bar 内触发和 v7 14:55 是不同时间合同；本刀没有授权用一个完整日 volume 接遍全部入口。若只能拿到事后成交量，设计必须标“事后容量近似”，不能宣称因果可交易。δ5 的可得时刻与 P1 成交窗口分开，不能为拿到 volume 把 fill 推到下一根而不重裁。

### 2.3 文档算术 oracle（document arithmetic oracles；候选模型，未接线、未转成测试）

| Oracle | 输入与明确前提 | 应满足的合同 |
|---|---|---|
| D1 整手与资金 | p=0.10，V=2500 股，used=0，买请求 500 股，现金充足，整手=100 | B=250、实际买 200、R=50；第二个买请求不能由 force-min 再买 100 |
| D2 跨路径共享 | 同桶两笔买请求各 200，B=300，先 A 后 B，现金充足 | 成交 200+100，总量=300；调换次序可换受配者但不能改变总预算；重复访问不得重置 |
| D3 拒绝不消耗 | B=300；先资金不足/limit 拒绝，再合格买 200 | 首次 used=0、无新增 lot/费用；第二次后 used=200 |
| D4 部分卖与 T+1 | 老 lot=300、今买 lot=200；候选可卖只含老 lot；R=200 | 卖 200 后留下老 100+新 200；T+1 禁卖的新 lot 不因 cap 可卖；费用仅按实际卖量 |
| D5 零/缺与桶边界 | p=0 或 V=0；另有 volume 缺失；随后到新桶 | 零容量不成交；缺失按候选 unavailable 拒绝并独立诊断；新桶仅用自身量，不累借未来量 |
| D6 时间前缀 | 相同截至 t 的已完成桶，追加 t 后巨大 volume | t 之前所有分配/成交不得改变；全日终量不能代替此证明 |
| D7 fee floor | 显式 sell=15bp/min5，100 股×10 两笔 vs 合并 200 股×10 | 逐次两笔费用=10，合并一次=5；遵守 δ1 调用粒度，不承诺切碎交易后费用不变 |

买入整手不代表所有未来卖出/公司行动零碎股都必须整百。D4 特意使用整百可卖量隔离争议；零碎股处置与 δ6 衔接，仍待裁。D1–D7 的数字是设计 oracle，不是计划已接到撮合器的证明；要证生产必须走真实 public simulate 的触发→预算→记账链。

## 3) Delta roadmap

| 刀 | 状态 / 顺序 | 与 δ5 的关系 |
|---|---|---|
| δ1 fees | 基线已含 | partial fill 会改变 min-floor 次数；不可静默合并计费 |
| δ2 exdiv reference | 基线已含，经济未关 | raw price/volume 单位与事件映射必须分开 |
| [δ3 ST PIT](plan-industry-align-p3-d3-st-pit-2026-09-19.md) | #125 契约/pins 已含于基线 | 不在容量设计中重取名字 |
| [δ4 limits-none](plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md) | #126 契约/pins 已含于基线 | 档位可用性与 volume 可用性是不同门 |
| **δ5 volume-cap** | **本文件：Human GO B，Slice A + C 文档验收完成；B 跳过** | 生产需另裁 `.1=C`，本轮不授权，未承诺上线顺序/日期 |
| [δ6 economics](plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md) | Human GO A 残留+oracle，账本可选 B docs | 新增权益/零碎股不会自动扩大市场容量；两者同时实施需重新核定组合合同 |

## 4) F-R* hard locks

| ID | 硬锁 |
|---|---|
| **F-R1** | 本 feat 仅 §8.1 白名单三份 Markdown；所有生产 Python、tests、配置/依赖/CI 均不改，不增加撮合/loader/CLI/容量参数或行为。 |
| **F-R2** | 已有零量过滤 ≠ participation cap；不得把设计 oracle、历史容量/收益推测写成已实现。 |
| **F-R3** | 必须显式单位、价格域、累计/增量、时间可得性；不猜源、不读湖认证。 |
| **F-R4** | 任何未来 cap 预算必须定义跨路径/lot/side 归属；真实成交才消耗，不能一 lot 重置一份。 |
| **F-R5** | cap 不越过价格/limits/T+1/现金门，不以 force-min 突破；Mark 不消耗成交容量。 |
| **F-R6** | partial fill 触及手续费、v7 stage、pending/ride_with/step 时必须显式设计并另裁；不能 silent 改成交。 |
| **F-R7** | P1/P2/P4 挂起；δ1/δ2、δ3/δ4 当前语义不变；未授权改 fill 时点以迁就 volume。 |
| **F-R8** | future pins 仅合成内存/tmp_path；当前不跑测试/回测/湖；不造新 vendor feeder。 |
| **F-R9** | §9 是 δ1/δ2 超集；全部生产受路径白名单约束，既有 import fence 固定枚举不扩大。 |
| **F-R10** | 不接 L2/live/LEBS/MockQMT，不复活 Cerebro/PortAnaRecord；模型限于研究向量化。 |

## 5) P* human cuts（Human GO .1=B；其余推荐仍为设计候选）

> **Human GO recorded 2026-09-19 (Asia/Shanghai):** P3δ5.1=B — δ5=B：只设计，不接生产 cap。授权设计文档落地；P3δ5.2/5.3/5.4 的推荐保持为 B 下候选，未单独裁决。**本轮没有 `.1=C`，不授权生产 cap 接线或撮合变更。**

| ID / 决策 | A | B | C | 本轮人裁 / 设计推荐 |
|---|---|---|---|---|
| **P3δ5.1：交付层级** ✅ Human GO 2026-09-19 | 只记录当前无 cap + pins | 设计数据/预算/状态合同 + oracle，生产不变 | 独立批准生产接线/撮合变更 | **B（只设计）** |
| **P3δ5.2：时间模型** | 先设计完成分钟桶，标明可得时刻与近似 | 先做事后日容量诊断设计，不约束盘中 fill | 设计下一桶执行/逐笔模型；涉及 fill 时点须重裁 P1 | **A**，不能当作已认证数据 |
| **P3δ5.3：预算与成交形态** | 共用 symbol/bucket 双向预算、允许部分成交的候选 | 同预算，但整笔不满足则拒绝 | side/路径拆预算的其它明确政策 | **A**，state/费用待设计完才能申请 .1=C |
| **P3δ5.4：缺失/无效 volume** | cap 启用时 unavailable 拒绝并诊断 | 只诊断、不限量的观察模式 | 显式 fallback 政策，必须列所有来源/默认 | **A**（仅候选）；cap 关闭沿用基线 |

选择其它行的 A/B/C 不独立授权代码变化；生产必须 `.1=C` 并具备完整数据源合同、部分成交状态表、迁移/回滚与真实入口 pins。比例 p 尚待未来用例/数据证据裁定；本次不猜 5%/10% 为生产默认。

## 6) Non-goals

- 不加 capacity 参数、volume 传输列/缓存、不改 loader、不修改资金配额或整手规则。
- 不实现冲击成本、滑点、订单簿排队、跨策略实盘容量共享，不把 cap 当成真实执行验收。
- 不改 v7 stage/stop、书 lot/ride_with/pending、费用 floor、T+1、P1/P2/P4。
- 不跑容量扫描、回测、湖、L2，不下载数据，不选最佳参与率，不报告未验证收益。

## 7) Slices A → B → C（本 feat：A + C docs 完成；B SKIPPED）

本轮 Human GO B 仅授权设计文档落地，D1–D7 保留为文档算术 oracle；Slice A 与 Slice C 的文档审计/冻结证明已完成。下面测试落点和 §8.2 data-free 命令只保留为后续候选，**Slice B SKIPPED，no tests added**。任何生产 cap 接线或 matcher/loader 变更仍须另裁 `.1=C`，本轮没有此授权；Slice C 验收不等于生产选项 C。

### Slice A：数据与状态设计（文档已落地）

§2 的源码锚点已按固定基线复核；§2.2 八维候选矩阵与 §2.3 D1–D7 已落 [engine SSOT §2.4](engine-ashare-correctness.md#24-p3-δ5-volume-participation-cap-designhuman-go-b)，[README](README.md) 增加设计入口。DoD：as-built / design / production default 明确区分，现有无 cap 与零量过滤不混同，全部生产冻结。逐入口数据源的单位/可得时刻认证、双账本 partial 后的 stage/stop/timer/pending/ride_with/step 状态迁移、零碎股与迁移/回滚仍是未来 `.1=C` 的前置设计缺口，不随本次文档落地关闭。

### Slice B：SKIPPED（本轮未授权测试；以下 B1–B4 仅未来候选）

| Pin | 真实已有文件 | 未来验收边界 |
|---|---|---|
| B1 loader 现状 | `tests/test_csv_daily_backtest.py`、`tests/test_csv_minute_backtest.py`、`tests/test_ashare_bars.py` | 复用零量/缺 volume pins；临时正量小/大只改 volume，记录过滤及输出列现状；不偷加列 |
| B2 无 cap 的 public 接线 | `tests/test_csv_daily_backtest.py`、`tests/test_csv_minute_backtest.py`、`tests/test_csv_minute_backtest_v7.py` | 相同价格/名单/预算，正量大小变化不改变当前成交；逐笔对比 shares/cash/reason，明确证明“无 cap” |
| B3 数量与资格 | `tests/test_ashare_simulate_predicates.py`、`tests/test_csv_minute_backtest_v7.py` | 复用 T+1/现金/held 多 lot 证据；D1–D6 若做人造账本 oracle，必须独立标 design-only，不能 mock 生产后称 cap 已接线 |
| B4 费用粒度 | `tests/test_ashare_fees.py`、`tests/test_ashare_fee_wiring.py` | 复用 D7 真实费用计算/双账本粒度，不复制费率算法；没有 partial-fill 生产接线闭环前不声明容量已实现 |

设计选择 B 可以把 D1–D6 保留为文档算术表，或在人裁允许的后续 tests-only 刀加入独立参考模型；无论哪种，不能让“模型自己的函数测自己”代替 public matcher 验收。实施 C 必须另列生产落点与真实 cap 集成 pins，本表不是它的替代计划。

### Slice C：设计验收与冻结（docs acceptance 已完成）

仅执行 §8.1 文档审计与 §8.3 冻结检查，结果见 §8.4；§8.2 **NOT run**。DoD：三 docs 全路径白名单、UTF-8/BOM/NUL、whitespace 与 §9 / 全 research / 全 Python / tests 零 diff 均 PASS。D1–D7 只是文档候选，不代表生产容量门已实现；**must cut C? NO**。

## 8) Linux/CI isomorphic acceptance（真实命令；区分本次 docs 与未来 pins）

### 8.1 本次 docs-only：基线、全路径、编码与 whitespace

从仓库根目录用 Bash 执行。`IMPLEMENTATION_BASE` 是本 feat worktree 起点的 `git rev-parse HEAD` 实测值；以下重新解析同一固定 commit，不跟随移动的 master、不推算 merge-base。proposal 历史锚点见页首，不用于本轮冻结。

```bash
set -euo pipefail
IMPLEMENTATION_BASE="$(git rev-parse --verify 'e0250efb2fae42e4e7f38a9585b1b4e95a1529bc^{commit}')"
[[ "$IMPLEMENTATION_BASE" =~ ^[0-9a-f]{40}$ ]]
git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD
P3_DOCS=(
  docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md
  docs/backtest/engine-ashare-correctness.md
  docs/backtest/README.md
)
P3_AUDIT_DIR="$(mktemp -d)"
trap 'rm -- "$P3_AUDIT_DIR"/{head,worktree,index,untracked,paths,whitespace}; rmdir -- "$P3_AUDIT_DIR"' EXIT
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
git diff --check "$IMPLEMENTATION_BASE" -- "${P3_DOCS[@]}"
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

最后的循环覆盖完整文件（含尚未跟踪文档）；no-index 正常内容差异可返回 1，故同时要求 rc≤1 且 whitespace 诊断为空，不能简单忽略所有非零退出码。全路径审计覆盖 base→HEAD、staged、unstaged、untracked，不靠一张有限冻结表推断其它路径安全。白名单收窄为实际触及的 **三 docs**，d345 索引未改；**本轮不允许任何 tests/Python 修改**。未来 tests-only 必须另获授权并在新的实施记录中列明路径，本轮不得扩白名单。

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
  tests/test_csv_daily_backtest.py \
  tests/test_csv_minute_backtest.py \
  tests/test_ashare_bars.py \
  tests/test_csv_minute_backtest_v7.py \
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
git diff --exit-code "$IMPLEMENTATION_BASE" -- backtest/research/
git diff --exit-code "$IMPLEMENTATION_BASE" -- '*.py'
git diff --exit-code "$IMPLEMENTATION_BASE" -- tests/
git diff --exit-code "$IMPLEMENTATION_BASE" -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code "$IMPLEMENTATION_BASE" HEAD -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --cached --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
```

### 8.4 本次运行记录与验收范围

验证 HEAD / 固定 IMPLEMENTATION_BASE 均为 `e0250efb2fae42e4e7f38a9585b1b4e95a1529bc`；验收对象为本 feat 的**未提交工作区文档**，没有实现 commit。2026-09-19（Asia/Shanghai），在 `/workspace/wt-p3-d5-volume-cap-feat`、Linux / Bash / Git / Perl Encode 上执行文档审计；未运行 Python/pytest/gates，未安装依赖，无网络、回测或湖访问。

| 命令 / 检查 | 本次结果 | exit |
|---|---|---|
| §8.1 固定基线祖先、全路径白名单（base→HEAD/index/worktree/untracked） | **PASS：仅三 docs**（本 plan、engine correctness、README）；无其它路径、无 staged/untracked 变更 | 0 |
| §8.1 UTF-8 严格解码 / BOM / NUL / whitespace | **PASS：三 docs UTF-8、BOM=0、NUL=0**；`git diff --check`（含 base / staged / unstaged）与完整文件 whitespace 检查均 clean | 0 |
| §2 `git show <IMPLEMENTATION_BASE>:<path>` 源码锚点复核 | 已重新阅读书/v7 数量记账、共享买路径、三 loader/帧与分钟扫描；既有测试锚点只读 | 0 |
| 文档静态核对；§8.1 / §8.3 命令块逐字提取与 `bash -n` | PASS；八维矩阵、D1–D7 与 engine §2.4 一致；20 个 §2 file:line 范围、15 个相关本地链接与新 §2.4 片段有效；两个命令块执行均成功 | 0 |
| §8.3 `git diff --exit-code "$IMPLEMENTATION_BASE" -- backtest/research/` | **PASS：对固定基线全部 research 零 diff** | 0 |
| §8.3 `git diff --exit-code "$IMPLEMENTATION_BASE" -- '*.py'` / `-- tests/` | **PASS：全仓 Python（含 tests）及测试目录零 diff** | 0 |
| §8.3 22 文件四种冻结 diff；数组 / §9 表逐项与顺序、表行对基线 | PASS；四种 diff 均为空，22 文件数组/表同序，§9 表行与基线原文一致 | 0 |
| §8.2 tests / gates；Slice B B1–B4 | **NOT run / SKIPPED；no tests added，既有测试亦未修改**；D1–D7 仅文档算术 oracle，无新增 pins | — |

本轮只验收设计文档与生产冻结，不引用 δ1–δ4 的历史 passed 数，不声称 D1–D7 已接 public matcher。Human GO B 不授权生产 cap；P3δ5.2/5.3/5.4 仍为候选，P1/P2/P4 继续 deferred。**must cut C? NO**；未来任何 matcher/loader/容量参数/预算/partial-fill 变更须另裁 `.1=C` 并补齐数据/状态/迁移合同与真实入口 pins。本轮不提交、推送或开 PR。

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

本表与 §8.3 数组的路径/顺序必须一致。表内零 diff 只证明这些文件；§8.3 另查全部 `backtest/research/`、全仓 Python（含 tests）与 `tests/`，§8.1 三 docs 全路径白名单禁止任何其它生产、测试、CI 或数据修改。不能以本表未列出为理由改生产；不扩大固定热路径 import-fence 测试的扫描面。


## 10) Changelog

- **v0.3 (2026-09-19，Asia/Shanghai)**：按 Human GO P3δ5.1=B 落设计文档，Slice A + C docs acceptance 完成，Slice B SKIPPED；基线刷新为 post #126 `e0250efb2fae42e4e7f38a9585b1b4e95a1529bc`，proposal 基线留作历史。复核 §2 源码锚点；engine SSOT §2.4 / README 收录无 cap 现状、八维设计矩阵与 D1–D7 文档算术 oracle。白名单收窄为三 docs，保留 §9 原 22 文件冻结表；§8.4 记录文档审计与冻结证明，§8.2 NOT run，无新增/修改测试或 pins。P3δ5.2/5.3/5.4 仍候选，未授权 `.1=C`，生产不变，保留未提交交付。
- **v0.2 (2026-09-19，Asia/Shanghai)**：录入 Human GO P3δ5.1=B，只设计、不接生产 cap；§5 其余推荐仍是 B 下设计候选，无 `.1=C` 授权，P1/P2/P4 继续挂起。本次仅更新 GO 记录，未实施 slices、未新增/执行测试，生产、基线、白名单、冻结表与 §8 命令不变。
- **v0.1 (2026-09-19)**：post #123 核实数量/资金接线、可选 volume 过滤和分钟帧丢列；新增设计合同、D1–D7 oracle 与待裁 A/B/C，推荐只设计 B。无生产/测试修改、无回测/湖、无 participation cap 上线或收益结论。
