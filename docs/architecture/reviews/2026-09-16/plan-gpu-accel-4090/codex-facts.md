# 事实锚点核查评审（host: codex-facts / Grok 补完）

> 评审对象：[plan-gpu-accel-4090-2026-09-16.md](../../../../backtest/plan-gpu-accel-4090-2026-09-16.md) v1.0（draft [PR #60](https://github.com/baiyibing/MyQuant-backtrader/pull/60)，分支 `origin/docs/gpu-accel-4090-plan`）· 2026-09-16
> 对照简报：[perf-4090-context-brief-2026-09-16.md](../../../../backtest/perf-4090-context-brief-2026-09-16.md)
> 基线：master `db49c85`（含 #58/#61/#62 与 D 烟测简报补丁）
> 角色：pattern-evidence / 事实锚点核查 · 结论：**READY-AFTER-FIXES**
> 范围：**只评审不实施**；未改业务代码、未 merge #60。
> **#57 消费滤镜（红线）**：两条 G 禁区已被 09-16 人裁取代（Cerebro 物理删除=#58；改 6/8 卖点=#61）。WP1(2) ROI 在 band 原生编码前对本仓在研策略无收益（简报 §1.2）。

## 发现列表

### 🔴 必须修（阻塞按原文执行 S0 / 误导判定门）

- **🔴1｜S0① 引用的 `bench_minute_simulate_hotpath.py` 无法「换真实窗口」——脚本是合成热路径，不是 F 湖端到端墙钟工具。**
  证据：
  - 模块 docstring 明文：`Synthetic only: no F lake or cache is read.`（`scripts/research/bench_minute_simulate_hotpath.py` L3–5）
  - CLI 仅 `--days/--codes/--minutes/--lots-days/--reps`（L133–138）；无 `--start/--end/--strategy/--pool` 之类真窗参数
  - 入口构造 `_synthetic_inputs(...)` 后调用 `sim.simulate(...)`（L144+）
  - plan §5 S0 写「换真实窗口（如 version8 20251023–20260909 池名单窗）」与 §6 仅 `--help`，按字面无法执行
  修复：S0 回测半边改为真实入口（与 D 烟测同形），例如 `backtest/research/csv_minute_backtest.py --strategy version8 --start 20251023 --end 20260909 ...`；或明确「热路径合成 bench 仅作分解参照，端到端墙钟以 D 烟测 / 引擎 CLI 为准」并删「换真实窗口」措辞。

- **🔴2｜S0② `full_market_chip_resist.py` 测的是日线筹码+换手阻力，不是 S2 要加速的分钟筹码直方图。**
  证据：
  - 脚本 `reader.read_stock(..., period="1d", ...)`（约 L108–112）
  - `cumpdf = daily_chip_distribution(arr, method="triang")`（约 L125），另算 `compute_crossday_turnover_resistance` / 布林带
  - **未**调用 `oskh_factors.chip.core.minute_chip_distribution`
  - 而 S2 / A-R1 / §8 显存估算均锚定「全市场**分钟**窗直方图」与 `oskh_factors/chip/core.py` 第三后端
  修复：S0 chip 半边必须换/增「分钟 chip 全市场或代表性批」驱动（新建只读 research 脚本或明示用既有 minute chip bench + 批循环），使墙钟与 S2 负载同构；否则 P2「只看 S0 chip 墙钟」测错对象。

- **🔴3｜plan §1「真实 F 湖端到端墙钟…均未实测」相对简报 §2.2 已过时——D 宿主烟测已给出同窗墙钟。**
  证据（简报事实卡 / [money-modes-v8-pername-smoke-2026-09-16.md](../../../../backtest/money-modes-v8-pername-smoke-2026-09-16.md) 宿主节）：
  - 代码态 `a606070`、本机 F 湖、窗 20251023–20260909
  - daily per_name **18.7s**；minute per_name **~90s**（分钟湖 44.8s + 模拟 17.5s）
  - 简报 §2.2 已写：S0 判定门大概率判停
  修复：§1 改为「回测端到端墙钟以 D 烟测为 research evidence（非 SLA）；S0 若保留则聚焦 **chip 负载**（且须对齐分钟核）+ 可选在 4090 机复跑同窗确认硬件差」；禁止继续写「均未实测」。

### 🟡 应修

- **🟡1｜`can_offload` / `reserve_state` 行号漂移。**
  plan / 简报写 `csv_minute_backtest.py:638-644` 与 `:851`。
  master 实码：`can_offload` 在 **:639–646**（另含 `not reserve_limit_up`）；每手 `reserve_state = {...}` 在 **:854**；`:851` 现为 `hm = day_m["hm"].to_numpy(...)`。
  语义结论仍成立（结构性不可达），但锚点须改，避免后人 `sed -n '851p'` 误读。

- **🟡2｜A-R1 / S2 / §6 环境变量名与 H15 先例不一致。**
  plan 写 `OSKH_CHIP_BACKEND=cupy`；H15 实码与文档 SSOT 为 **`MINUTE_CHIP_BACKEND`**（`oskh_factors/chip/core.py:132`，`tests/test_minute_chip_numba_parity.py`，plan-h15）。
  「沿用 H15 开关模式」与新造 `OSKH_CHIP_*` 名冲突。应扩展既有名（如 `MINUTE_CHIP_BACKEND=cupy|numba|python`）或显式迁移说明。

- **🟡3｜A-R1 / S2 过早钉死 CuPy；简报 §2.5 要求推迟到 S2 冒烟在 CuPy vs numba-cuda 间选择。**
  plan 全文 CuPy + `cupy-cuda12x` + `test_minute_chip_cupy_parity.py`；简报允许两者、十分钟 microbench 再选。A-R 应锁「可选第三后端 + 三向/双向 parity + 默认 Python」，实现选型留 S2 启动门，避免 plan 与简报打架。

- **🟡4｜前置 / A-R6 仍写「在飞 #58/#59」「S3 排在 #58/#59 合入后」——状态过时。**
  - #58 已合入（Cerebro 退场）
  - #59 CLOSED 未合（资金管理模式化由 **#61** 合入）
  - #62 收口已合；简报基线已是 post-#58/#61/#62
  修复：前置改为「S0 只读无冲突；S2/S3 排在 #61/#62 之后（已满足）」。勿再把 #59 当 blocker。

- **🟡5｜`oskh_factors/chip/core.py:88-128` 引用偏松。**
  :88 是节注释；numba kernel / availability 在 **:91–124**，`_want_numba_minute_chip` 到 **:133**。建议改 `:91-133` 或「H15 numba 段」。

- **🟡6｜P1 判定门两条件 AND，但「chip 使用频率」无测量法；且回测半边已被 D 烟测预满足。**
  「分钟回测 <5min」对 D 烟测 ~90s 已成立；「全市场 chip 扫描非常跑（<每周一次）」是流程/访谈事实，S0 脚本量不出。plan 须：① 拆成「回测门」与「chip 门」；② 频率由人裁声明；③ 允许「终止 GPU **回测线**、保留条件 S2」的部分停，而非只能整项目停。

- **🟡7｜§8 显存 ~18GB 量级可接受，但缺与 S0 工具的对齐声明。**
  复算：5000×240×240×8×8B ≈ 17.2 GiB，与文中 ~18GB 同量级。问题不在公式，而在 S0 未测该布局（见 🔴2）——风险段应挂在「分钟批」S0/S2，而非日线 resist 脚本。

### 🟢 备注（核实通过 / 不阻塞）

- 🟢 **#54 卖环 75.51% / 编排 ~18.6% / 全程 ~1.2s** 与 plan §1 表一致（上游 profile 文）；量级「分钟级研究窗」被 D 烟测 ~90s 强化，非削弱。
- 🟢 **结构性不可达语义属实**：`can_offload` 要求 `take_profit is None` 且 `reserve_state is None` 等；`simulate()` 每手构造 `reserve_state`（现 :854）。v6/v8/v9/v10 callable take_profit → WP1(2) 对在研书无 ROI（简报折扣，评审已带滤镜）。
- 🟢 **门禁数字**：`scripts/gates/` 13 个 `verify_*`；CI workflow L40–43 恰 4 个——与 #57/#简报一致。
- 🟢 **R12 双份脚本属实**：`verify_minute_chip.py`（`scripts/gates/` + `backtest/research/`）、`verify_turnover_resistance_alignment.py`（`scripts/gates/` + `scripts/research/`）。
- 🟢 **A-R2 / A-R3 / A-R4 / A-R5 / A-R7 方向正确**：不碰成交核与 Rust；GPU 不进 CI；parity 金测试；S0 只读；禁止为骗过 dispatcher 改 `reserve_state`/`take_profit` 传参——与 #57 禁令一致，且不依赖过时 G 禁区。
- 🟢 **S3「另开 dated plan」**（A-R6）与简报 §2.4 band-as-data + 三向 parity 叙事对齐；本 plan 只登记不展开是对的。
- 🟢 **Windows `D:\anaconda3\envs\vanna312\python.exe` 路径**：作为 4090 宿主 runbook 可接受；linux-vm 应用 `/workspace/vanna312/bin/python`（D 烟测已示范）——属环境注而非事实错误。

## 锚点勘误表

| Plan / 简报锚点 | 实际情况（master `db49c85`） |
|---|---|
| §5 S0① `bench_minute_simulate_hotpath.py`「换真实窗口」 | **合成 only**；无真窗 CLI；不能作为 F 湖 E2E 墙钟工具 |
| §5 S0② `full_market_chip_resist.py`「全市场一窗」对 S2 | 测 **1d + daily_chip_distribution**，**不是** `minute_chip_distribution` |
| §1「F 湖端到端墙钟均未实测」 | D 烟测已测：daily 18.7s / minute ~90s（同窗 version8 per_name） |
| `csv_minute_backtest.py:638-644` `can_offload` | **:639–646**（多 `not reserve_limit_up`） |
| `:851` 每手构造 `reserve_state` | **:854**；`:851` 为 `hm` numpy |
| `OSKH_CHIP_BACKEND`「沿用 H15」 | H15 实名为 **`MINUTE_CHIP_BACKEND`** |
| `chip/core.py:88-128` | 更准确 **:91–133**（numba + want 门） |
| 前置 / A-R6「#58/#59 在飞」 | #58/#61/#62 **已合**；#59 **CLOSED 未合** |
| §8 ~18GB 显存 | 量级 OK（~17.2 GiB）；须标明对应**分钟**批布局 |

---

核心结论：判定矩阵与「单次回测不值得 GPU」方向与简报一致，A-R2/3/4/5/7 硬锁可用；但 **S0 两条命令均不能量出它所声称要服务的判定门**（回测用错合成 bench；chip 用错日线 resist），且 **§1「未实测」已被 D 烟测证伪**。须按 🔴1–🔴3 修订 S0/证据段后再裁是否执行任何测量或关闭 GPU 项目。
