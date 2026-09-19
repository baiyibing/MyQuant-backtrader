# Plan: industry-align P3 δ5 volume participation cap production (2026-09-19)

> **Status**: **v0.4 · production volume-cap landed · Human GO C/A/A/A**；Slice A/B/C 完成，验收见 §8.4。此刀独立实施 δ5；δ6 production economics NOT started。
> **Main ship / 单行范围**: 分钟书 `simulate` 与 `simulate_v7` 可显式启用共享成交量预算，允许部分成交；默认 cap off = as-built。
> **IMPLEMENTATION_BASE**: `7428a1a89e309c5f5cbc21eab6eda2e38448c6cd`（#129 merge tip，δ4 fail-closed；worktree 起点实测 40 字符）。不跟随移动分支或推算 merge-base。
> **Human GO recorded 2026-09-19 (Asia/Shanghai)**: **P3δ5.1=C / P3δ5.2=A / P3δ5.3=A / P3δ5.4=A**。本次新授权覆盖 #127 的 B design-only freeze，仅限下列生产例外；P1/P2/P4 deferred。
> **前序**: [δ1 fees](plan-industry-align-p3-fees-2026-09-19.md)、[δ2 exdiv](plan-industry-align-p3-d2-exdiv-2026-09-19.md)、[δ4 fail-closed](plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md)、[engine SSOT §2.4](engine-ashare-correctness.md#24-p3-δ5-volume-participation-cap-productionhuman-go-caaa)。历史 B 见 §10。

## 0) One-line scope

只接生产 volume participation cap；不改 fill clock、ST PIT、费用 schedule、除权权益 shares/cash/NAV，不接湖或 CLI 容量参数。调用方提供已认证语义的合成/外部容量查询，loader schema 保持原样。

## 1) Why now

新 Human GO C 授权独立生产刀。容量门必须与双账本的费用调用粒度、T+1、lot、stage、pending/ride_with/step 一起闭环；本刀以真实公开入口和 ledger helpers 的内存测试验收，不提供真实市场容量或收益估计。

## 2) Baseline / production boundary and freeze exceptions

基线书 `execute_buy` 依预算整百/force-min/现金门建 lot，`_sell` 全卖一个 Position；v7 `_buy` 按 fraction 整百，`_sell_lots` 汇总 T+1/kind 可卖量。两者均无市场成交量预算。日线与分钟 loader 已有可选零量过滤，随后丢 volume；已有零量过滤不等于 participation cap。

**§9 的 C-cut 例外仅四行**：`csv_ledger.py`、`csv_simulate_loop.py`、`csv_minute_backtest.py`、`csv_minute_backtest_v7.py`；另新增 `ashare_volume_cap.py`。这些文件只允许 δ5 接线；§9 其它 **18 行全部零 diff vs IMPLEMENTATION_BASE**。日线入口、所有 loader、费用/档位/策略 hooks、P1 时钟与 import-fence 枚举不变。完整全路径白名单见 §8.1，不能仅靠有限冻结表放宽其它文件。

### 2.1 Current entry contract

| 入口 / 模块 | Cap off | Cap on / 落点 |
|---|---|---|
| 分钟书 `simulate` | 原参数默认；成交/现金/lots/统计/mark 与基线一致 | `participation_rate=None`、`volume_for_bucket=None` 新 kwargs；启用时建单 run VolumeCap，绑定实际 quote/scan bar |
| v7 `simulate_v7` | 原结果、费用/stage/stop/timer | 相同两 kwargs；每个 buy/sell/timer 访问当前 hm 同一预算 |
| 书共享 chase/pool/step | 原顺序、门和资金规则 | `volume_bucket_for(code)` 只传 bucket；不改 hooks/BOOKS |
| 日线 `simulate`、run/CLI 与 loaders | 冻结 | **日线容量未接，deferred**；不把 EOD volume 伪装成盘中容量；无 CLI 默认参与率 |
| `ashare_volume_cap.py` | 不创建对象、不查询 volume | 只依赖标准库的预算 helper；不扩大 SIMULATE_HOT_PATH |

### 2.2 Production contract matrix（C/A/A/A）

| 维度 | 已落生产合同 | 边界 |
|---|---|---|
| 单位与域 | `BucketVolume(shares, available_at, unit="raw_shares_incremental")`；shares 必须非负整数，排除 bool；明确 raw 域增量**股数** | 必须由调用方认证来源和单位；裸 int/float、手/金额/累计量不自动转换，不读湖认证；未知输入拒绝 |
| 时间可得性 | key=`(engine symbol, YYYYMMDD, hm)`，hm 是该会话分钟桶 close 标签；`available_at` 为同会话 minute-of-day 整数，须 `hm <= available_at <= attempt_at < 1440` | 与现有会话钟点一致（不做 UTC→CST 换钟）。若源标签代表 bar 开始，应提供真实较晚 available_at，该标签处会拒绝；不可倒填可得时刻 |
| 完成 bar 近似 | close 成交使用对应完整分钟桶，明确 **completed-bar capacity approximation** | 开盘价触发使用 `attempt_at=hm-1`，桶未完成，lookup 前 unavailable 拒绝；本刀不改成交时点、不寻找前桶补容量。没有 EOD/future fallback |
| 预算键 | 单 run `(symbol, session, bucket)` 双向共用，所有 pool/chase/step/held lots 共用 | 维持既有路径/lot 遍历顺序，未实现按时间排序的新撮合循环；两个 run 不共享。每键首次 lookup 固定快照（含缺失）；重复访问不重置 |
| 容量公式 | `B=floor(p*V)`，`R=max(0,B-used)`；p 由 `Decimal(str(p))` 转精确整数比后 int 乘除 | `None` 唯一表示关闭；有限 `0<=p<=1`，无生产默认 rate；p=0 是启用且零容量。0.10 仅测试夹具 |
| 成交上限 | 现有价格、名称/limits、T+1、现金门先过，再 `min(requested, eligible, R)`；买量向下整百 | 原请求含费现金不足仍整笔拒绝，不用 partial 绕过原现金门；force-min 不突破 R；卖出可剩整股零头，不创造公司行动权益 |
| 消耗与诊断 | 成功记账后只扣实际 shares；纯 mark / cash / limit / T+1 拒绝扣 0 | `skip_volume_unavailable:<detail>` 为缺失/单位/数值/可得时间失败；`skip_volume_cap:<detail>` 为零量/耗尽/原子退出不足（helper T+1 防线也在此族） |
| 残量 | 买剩余失效，不产生跨桶订单；卖出保留原 lot 的剩余 shares | pending / ride_with / step 见 §2.4；不增加 live 队列、预留或并发订单服务 |

`volume_for_bucket` 可为 mapping，或 `lookup(symbol, session_yyyymmdd, bucket_hm)` callable。返回 `BucketVolume | None`；缺 key/LookupError 视为 missing；其它 provider 异常显式传播，不吞掉程序错误。book symbol 沿入口原标识，v7 使用既有 canonical symbol。无隐式 schema/unit 默认；调用方没有可信容量时应返回 None。这个类型是调用方语义声明，不是自动数据源认证。

书买价回退（pool/step ≤14:55、chase ≤09:45）使用**实际报价行**的 hm，不能借目标时刻或后续 volume。日线容量保持 deferred；即使将来接日量也只能另标 ex-post capacity approximation，不能成为盘中因果容量。这里不重裁 P1，也不声称既有全日扫描顺序等于真实事件栈。

### 2.3 D1–D7 production oracles

| Oracle | 已测真实路径 | 断言 |
|---|---|---|
| D1 整手/资金 | public book + execute_buy | p=.10,V=2500，原请求500→200，R=50，force-min 再买100失败；费用/lot/mark 以200为准 |
| D2 共享 | 真实 pool/chase helpers 双顺序；public book pool+step | B=300 两路径分配200+100；共享 key；step lot 只有实际100 |
| D3 拒绝不扣 | 书 cash/limits 与 v7 cash/T+1/kind | lookup/used 均不动；后续合格请求仍能用原预算 |
| D4 partial/T+1 | public book sell、public v7 buy/add/stop + book ledger | old300/new200，卖200后 old100/new200；avg_cost、entry/stage/date 保留正确 |
| D5 零/缺/桶 | 两 public matcher 参数矩阵 + ledger | V=0 为 cap skip；缺/负/非有限/浮点/未认证 unit/时间为 unavailable；换桶不借、回访不重置 |
| D6 前缀 | public v7 顺序桶、book quote fallback、双入口 gap open | 改后桶巨量不改前缀分配；只读实际 quote 桶；开盘不读未完成桶 |
| D7 floor | 真实书 `_sell`、v7 `_sell_lots` + δ1 fee helper | 100股×10 两个书调用收5+5；v7 一次聚合200股收5；同桶先买100再卖200总耗300 |

此外：三公开入口的 cap-off 序列化快照 SHA-256 固定于本 IMPLEMENTATION_BASE（用 `git show` 装入冻结模块取得），volume=0/1/10^12/NaN 均逐字节匹配；启用前不调用 provider。该快照覆盖成交、现金、lots、equity 与书统计/配额，不把新增内部 `volume_cap` 对象序列化成旧输出。

### 2.4 Partial-fill mini state table

| 路径 | 成功 partial 后 | 拒绝 / 下一次评估 |
|---|---|---|
| book `execute_buy` | lot.shares=实际 filled；cash/quota/supplement/commission 按 filled 重算 | 剩余请求作废；不创建 pending/ride queue |
| book `_sell` 普通 lot | 原 Position.shares 减实际 sold；cost/entry/peak/reserved/is_step 保留，清零才删除 | 既有每 lot 每日首次 scan 触发只尝试一次；余仓/容量拒绝留到后续 session 原策略重评，不额外扫描本日后桶 |
| book `pending_exit` / `ride_with` 关联退出 | 保留原子退出：关联组全部 T+1 可卖且 R 足够才整组成交；每 lot 原费用粒度 | 不足整组则整组拒绝、0扣量、pending原因/父子关系不变；不允许 orphan rider，不创造跨桶队列；嵌套ride树在父lot记账前以 `skip_volume_cap:unsupported_ride_tree` 整组拒绝 |
| book chase / step | chase 成功 partial 沿原路径结束；step append 实际 filled 的独立 is_step lot | cap 拒绝 chase 记 `chase_buy_fail_volume`，不误记 cash；原无bar pending 保留规则不动。step成功后按原 lot计数；失败由原条件未来重评，不存剩余数量 |
| v7 `_buy` | append 实际 filled lot，按 filled 更新 avg_cost；`last_add_date` 与原成功逻辑一致 | 只有真实成功 buy 才按原 ladder 规则推进 stage；0 fill 不推进。partial成功也推进一次，不追加剩余档位订单 |
| v7 `_sell_lots` | wanted先以R裁剪，再按原 lots顺序/KIND/T+1 扣股；按实际总卖额单次收费 | 同日lot保持不可卖；剩余 lot buy_date/price/kind 不变，avg_cost重算；stage/timer anchor不重置，下一个原触发可重评 |

所有卖出份额仍是整数股；cap不强制卖出整百。这里不实现 δ6 的权益、拆股或公司行动零碎股政策。

### 2.5 Migration / rollback

部署默认 `participation_rate=None`，cap off = old behavior，不创建“无限 cap”对象或标签。仅明确 rate 的调用启用失败关闭容量。无 schema/data migration；rollback = revert 本 PR。只提交到指定分支，host 负责 merge；**Ready for δ6 only after host merges this PR**，当前 δ6 production NOT started。

## 3) Delta roadmap

| 刀 | 状态 | 本刀边界 |
|---|---|---|
| δ1/δ2 | 基线已有 | 不改 fee schedule / 参考价换域；partial 仅按实际成交额沿原收费调用 |
| δ3/δ4 | ST PIT pins / δ4 fail-closed 已在 #129 | 不重取名称、不放宽 limits=None |
| δ5 | C/A/A/A production landed | 本文及 §8.4 定向验收；等待 host 合并 |
| δ6 | **production NOT started** | 本刀合并后才可准备下一刀；现有 docs/oracle 不扩成经济账本 |

## 4) F-R* hard locks

| ID | 硬锁 |
|---|---|
| F-R1 | 只允许 §8.1 九路径；生产例外限定 §2，其余 vs 固定 base 零 diff |
| F-R2 | 零量过滤不等于 cap；不宣称真实湖容量认证或收益 |
| F-R3 | unit/raw/incremental/available_at 显式，禁止猜源、日终或未来量 |
| F-R4 | 单 run symbol/session/bucket 跨 side/path/lot 共享；实际成交才扣 |
| F-R5 | 既有门先行，force-min 不破 cap，mark 不扣容量 |
| F-R6 | partial 状态按 §2.4；原子 pending/ride 失败保留整组，无隐式残量队列 |
| F-R7 | P1/P2/P4 deferred；δ1–δ4 及 exdiv economics 不扩范围 |
| F-R8 | tests仅内存/tmp_path；禁止湖/CLI回测/网络/download |
| F-R9 | §9 保留22行；仅4个既有例外+1新helper；SIMULATE_HOT_PATH 枚举不扩大 |
| F-R10 | 不接 L2/live/LEBS/MockQMT、不复活 Cerebro/PortAnaRecord；无嵌套 Codex/agent |

## 5) P* human cuts（当前 C/A/A/A）

| ID | Human GO 2026-09-19 | 已实施 |
|---|---|---|
| P3δ5.1 | **C**：独立生产 cap wiring PR | 覆盖先前 B design-only freeze，仅限本 allowlist |
| P3δ5.2 | **A**：completed minute + available_at | same-bar close 标完成bar容量近似；open/future/EOD 不借量 |
| P3δ5.3 | **A**：共享双向预算，允许 partial | 两账本实际成交扣量；原子关联退出例外已显式固定 |
| P3δ5.4 | **A**：invalid/unavailable reject + diagnosis | 缺失/负/非有限/未认证单位拒绝；V=0 有效零容量 |

不选择生产 rate；0.10 仅算术夹具。#127 B 历史与 proposal 基线保留在 §10，不再作为本 C cut 的全生产冻结指令。

## 6) Non-goals

无 δ6 生产经济、费用数字变化、ST PIT/fill-clock 变更、订单簿/冲击模型、容量扫描/实盘承诺。日线 cap、loader volume retention、CLI flags 均 deferred。不得修改 market_layer、unified_exit、策略 hooks、CI 或 import-fence enum。

## 7) Slices A → B → C（production acceptance）

| Slice | 完成内容 | DoD |
|---|---|---|
| A | Human GO C/A/A/A、输入/时间/共享/状态/迁移合同、engine §2.4 / README | 明确 cap-off as-built 与 cap-on、完成bar近似、实际生产例外 |
| B | `tests/test_ashare_volume_cap.py` 的公开入口 + ledger/helper pins | D1–D7、off快照、partial stage/T+1、原子组、时间前缀均验证生产 |
| C | §8.2 指定pytest + §8.3 全路径/冻结/编码检查 | §8.4 记录结果，commit留分支；不推送/开PR |

## 8) Acceptance（Linux / controlled Python 3.12）

### 8.1 Actual production / docs / tests allowlist

```text
backtest/research/ashare_volume_cap.py
backtest/research/csv_ledger.py
backtest/research/csv_simulate_loop.py
backtest/research/csv_minute_backtest.py
backtest/research/csv_minute_backtest_v7.py
docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md
docs/backtest/engine-ashare-correctness.md
docs/backtest/README.md
tests/test_ashare_volume_cap.py
```

### 8.2 Tests（实际执行）

```bash
/tmp/industry-align-venv/bin/python -m pytest -q -m 'not production and not benchmark' \
  tests/test_ashare_volume_cap.py \
  tests/test_csv_daily_backtest.py \
  tests/test_csv_minute_backtest.py \
  tests/test_csv_minute_backtest_v7.py \
  tests/test_ashare_simulate_predicates.py \
  tests/test_ashare_simulate_import_fence.py \
  tests/test_ashare_fees.py \
  tests/test_ashare_fee_wiring.py
```

全部 fixture 内存/tmp_path；没有湖、CLI backtest、网络、download/安装。此定向验收不等于全量 CI。

### 8.3 Freeze proof / encoding

以下从 repo 根目录运行；包含新增未跟踪文件，commit 前后均可复核。

```bash
set -euo pipefail
BASE=7428a1a89e309c5f5cbc21eab6eda2e38448c6cd
git merge-base --is-ancestor "$BASE" HEAD
git diff --name-only "$BASE" -- backtest/research/
git diff --name-status "$BASE"
git diff --check "$BASE"
/tmp/industry-align-venv/bin/python - <<'AUDIT'
from pathlib import Path
import re
import subprocess
base = '7428a1a89e309c5f5cbc21eab6eda2e38448c6cd'
plan = Path('docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md').read_text()
allowed = set(plan.split('```text\n', 1)[1].split('```', 1)[0].splitlines())
changed = set(subprocess.check_output(['git', 'diff', '--name-only', base], text=True).splitlines())
changed.update(subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], text=True).splitlines())
assert changed <= allowed, changed - allowed
production = {p for p in allowed if p.startswith('backtest/research/')}
pattern = re.compile(r'^(?:' + '|'.join(re.escape(p) for p in sorted(production)) + r')$')
assert all(pattern.fullmatch(p) for p in changed if p.startswith('backtest/research/'))
rows = re.findall(r'^\| `(backtest/research/[^`]+)` \|', plan.split('## 9)', 1)[1], re.M)
assert len(rows) == 22
frozen = [p for p in rows if p not in production]
assert len(frozen) == 18
subprocess.run(['git', 'diff', '--exit-code', base, '--', *frozen], check=True)
for name in sorted(changed):
    raw = Path(name).read_bytes()
    raw.decode('utf-8')
    assert not raw.startswith(bytes.fromhex('efbbbf')) and raw.count(b'\x00') == 0, name
print('PASS: allowlist, production regex, 18 frozen rows, UTF-8; BOM=0; NUL=0')
AUDIT
```

### 8.4 Results（Human GO C/A/A/A）

2026-09-19，worktree `/workspace/wt-p3-d5-volume-cap-prod`，分支 `feat/industry-align-p3-d5-volume-cap-prod`；HEAD 起点实测为固定 #129 基线。解释器 `/tmp/industry-align-venv/bin/python`（3.12.13）。

| 验收 | 结果 |
|---|---|
| §8.2 指定八测试文件 | **282 passed, 2 warnings in 1.53s（exit 0）**；旧 δ1–δ4 / import-fence 同跑，无skip/deselected；两条既有 `ashare_bars.py:503` pandas `copy` 弃用警告 |
| 新 volume-cap tests | **25个新test函数 / 62个参数化cases全部PASS**；其余220项既有回归PASS；D1–D7 真实入口/helpers、off基线快照、原子状态与时间门 |
| 基线字节快照来源 | 冻结 `git show 7428a1a…` 的 ledger/loop/daily/minute/v7 模块，四种 volume 的每入口 SHA一致；新 cap-off 与其匹配 |
| §8.3 allowlist / freeze | **PASS（exit 0）**：仅5个生产文件（helper/ledger/loop/minute/v7）；§9其余18行与所有非白名单路径零diff；原22行表逐字一致 |
| 编码 / whitespace | **PASS（exit 0）**：全部9路径UTF-8、BOM=0、NUL=0；`git diff --check BASE` clean；§8.3命令提取后 `bash -n` 与实际执行均PASS；engine §2.4 file:line锚点有效 |
| 未执行范围 | 无湖/CLI backtest/网络/download/agent；未跑全量 CI、未实施 δ6 生产经济 |

交付 commit 留本分支，host 推送/开PR/合并；δ6 production NOT started，只有 host 合并本PR后才能准备 δ6。

## 9) Frozen production file table（保留22行；本 C cut 仅 §2 的4行例外）

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

§2 的四行例外仅允许 δ5；其余18行严格零diff。新增 helper 由 §8.1 单独授权；此表不扩大 import-fence 枚举，也不授权表外任何改动。

## 10) Changelog

- **v0.4 (2026-09-19，Asia/Shanghai)**：NEW Human GO **P3δ5.1=C / .2=A / .3=A / .4=A** 覆盖 #127 B freeze；IMPLEMENTATION_BASE 刷新为 #129 `7428a1a89e309c5f5cbc21eab6eda2e38448c6cd`。分钟书/v7 production opt-in cap、完成桶 available_at、共享预算、partial 与原子关联组、诊断和迁移/回滚落地；新增生产测试并与 δ1–δ4 合跑，§8.4 记录验收，提交留分支。日线/loader/CLI 不接，P1/P2/P4 deferred，δ6 production NOT started。

- **v0.3 (2026-09-19，Asia/Shanghai)**：按 Human GO P3δ5.1=B 落设计文档，Slice A + C docs acceptance 完成，Slice B SKIPPED；基线刷新为 post #126 `e0250efb2fae42e4e7f38a9585b1b4e95a1529bc`，proposal 基线留作历史。复核 §2 源码锚点；engine SSOT §2.4 / README 收录无 cap 现状、八维设计矩阵与 D1–D7 文档算术 oracle。白名单收窄为三 docs，保留 §9 原 22 文件冻结表；§8.4 记录文档审计与冻结证明，§8.2 NOT run，无新增/修改测试或 pins。P3δ5.2/5.3/5.4 仍候选，未授权 `.1=C`，生产不变，保留未提交交付。
- **v0.2 (2026-09-19，Asia/Shanghai)**：录入 Human GO P3δ5.1=B，只设计、不接生产 cap；§5 其余推荐仍是 B 下设计候选，无 `.1=C` 授权，P1/P2/P4 继续挂起。本次仅更新 GO 记录，未实施 slices、未新增/执行测试，生产、基线、白名单、冻结表与 §8 命令不变。
- **v0.1 (2026-09-19)**：post #123 核实数量/资金接线、可选 volume 过滤和分钟帧丢列；新增设计合同、D1–D7 oracle 与待裁 A/B/C，推荐只设计 B。无生产/测试修改、无回测/湖、无 participation cap 上线或收益结论。
