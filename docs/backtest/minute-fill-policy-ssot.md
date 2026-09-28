# 分钟成交假设 SSOT（S0，2026-09-28）

## 1. 状态与范围

**S0 docs-only 已获 Human「批 S0，开干」；仅发布成交假设总表、指针与旧文档勘误。** 核查基线为 `fad804a99f36e084f57f98bf57d2cf7a462e1522`（`fad804a`，G7 #237）。合同来源为评审交接 `PLAN_MINUTE_FILL_POLICY_INFRA.md` §1、§4–§6；Kimi 计划评审及 R1+R2 共识均为 APPROVE，本表纳入 `R2_CONSENSUS.md` §Nits。计划浏览副本不入本 PR，不作为本表链接依赖。

`production_C=frozen`：本 PR 不改变生产 fill / scan / fee / clock 默认，也不撤销此前已合入的独立 Human GO。本表记录各入口已有合同及比较资格，不建立可配置超级成交核；三仓分工仍见 [成交引擎定位][positioning]。S1 目录、S2 helper 抽取均未授权；本 PR **勿合，等待 Human「合」**。

本次仅只读核对代码与冻结说明；不运行 Python、测试或湖回测，不提供新 NAV / 收益数字。引用文档中的历史测试、跑数和 SHA 是来源记录，不代表本次复验。

## 2. 读表规则与勘误

下表是 S0 入仓的唯一成交假设总表。行号只供文档引用，**不是已有 API、枚举或新增 CLI**。以后 entry / AGENTS 只链接此表，不另抄一套默认。

“默认”以各自入口为单位；没有跨仓统一 default policy。价格、触发、报价标签、信息可得时刻、决策时刻、实际记账顺序、NAV mark 是不同字段。共享书还须带 `strategy` / book hooks，不能用一个 `close` 概括所有卖出谓词。

本基线优先使用当前接线和已冻结实现说明；旧提案保留为历史，不择段拼装新规则。以下承接计划 §1.1 的勘误；本 PR 已修正 AGENTS 的 TopK 摘要及成交核文档的分钟费率行：

- 统一卖出提案旧段仍写 H/L；**Q39 明确废止**它，当前 Mode B 以 open / close 为准。[Q39][proposal]
- TopK 原计划及 AGENTS 的旧 P1 摘要不包含全部后续能力；本基线已有 P2 `vwap`、P3 walkdown、P4 real。[P1][topk1]、[P2][topk2]、[P3][topk3]、[P4][topk4]
- H/L 原计划曾把 `hl + --fix-s12-price-domain` 写成正交允许；实际该 domain 开关只允许 version12，而 hl 拒绝 version12，故组合拒绝；以 [P1 冻结说明][hl]及 validator 为准。
- 成交核旧费率章节写分钟无费率 kwargs；本基线共享分钟 `main → run → simulate` 已接 `--qlib-cost` 及三项费率参数。默认双边 10bp 未变。[当前入口][csv]
- JR 早期文档写显式 JSON only；本基线 `--bars` 还可在 `--validate-version v2` 下接显式 sealed pack。`--arm` / `--fill-mode` **必填**，不能把常用命令 M-LAG 写成默认；`--bars` 缺失会 `INPUT_BLOCKED`，但不是 argparse `required=True`。[当前 JR CLI][jr-code]
- 敏感格 batch1 的合成 END 标签、局部固定股数和隔夜探针，不支配 batch4 的 START 标签、Q2 重定量、H2 同日到期。两者必须分行。[敏感计划 §2/§9][sensitivity]、[batch4 设计 §9][fullstrat-design]

这些是目录勘误，不授权顺手修业务。原始 [止损/除权计划][stop-plan]、[TopK执行计划][topk-plan]保留审批来路，后续冻结说明补充其当前状态；JR全量时钟重生成归档见[既有交接][jr-regen]，本计划不重开该链路。若代码与已批准合同出现无法解释的真实冲突，记录 **未证实 / needs Human**，不由注册表选择一种实现。

## 3. 成交假设总表

表中“绿 R”是同合同内排名；“绿 S”仅为受控敏感性比较，不能混成一张收益榜；“红”禁止直接混排。完整条件见 §6。

| 行 / 对象 | 入口 | 买价 / 买钟 | 卖价、触发与时钟 | 默认 | 已有 opt-in 名称及边界 | 可否与谁混比 | 文档 / 代码指针 |
|---|---|---|---|---|---|---|---|
| C0 策略8 / 共享分钟普通路径 | `backtest/research/csv_minute_backtest.py --strategy …` | 池买 T 日 14:55 close；缺该根才取 [14:30,14:55] 最后 close，空窗不买；适用书的 chase 为 09:45 close / 原早段回退；加仓依书 hooks | 可卖日起逐根 open 穿止损按 open；否则默认以 close 判止损并按 close；其他卖因依书。峰值可用 high，**不等于 H/L 触价** | `minute_stop_trigger=close`；`fix_minute_cash_order=False`，仍走原处理顺序。策略号必填 | X-02、hl、fen、X-04 等见下行；version11/12 例外单列 | 同池、同资金/价域/时钟等全齐可绿 R；与 A/B、JR、v7 红 | [入口 §3/§7][entry]；[成交核][correctness]；[源码 `_buy_px` / `scan_held_day_python` / `simulate`][csv] |
| C11 version11 时钟例外 | 同共享入口 `--strategy version11 --pool-dir …` | 独立导出池；精确 09:30 open，缺该根不借后行；D 后首 bar T 与资格沿原书 | 前日 EOD 信号置 pending，下一可卖日精确09:30 open尝试；缺根/限价/volume=A不可用则defer；不走普通逐根止损 | 现行 `minute_open` hook、volume=A、无追买保持 | `--fix-s11-exit-domain` 默认 OFF；ON 用独立 front 信号域、raw 成交/mark；与 hl 拒绝 | 仅本书同输入/同域内比较；不能和 C0 因同入口直接排 NAV | [entry §2/§4][entry]；[books][books]；[CSV][csv]；`tests/test_s11_exit_domain*.py` |
| C12 version12 隔离记录 | 同共享入口 `--strategy version12` | 首买沿本书路径；分钟默认 none，日线信号固定 front | 自有 MA/止损扫描；旧域/修正域分列，不替换为 C0/Mode B | `--fix-s12-price-domain` OFF，`--dividend-type none`；不以此保证 NAV 域有效 | domain 修正及 transform 文件只记录既有能力；hl / X-02 拒绝 version12；本刀不改 | 跨域有效性未满足为红；当前 OFF+none 审计标 `invalid_mixed_price_domains`，不许目录“认证”为有效 NAV | [entry §5.5][entry]；[CSV `main` 的 price-domain audit][csv] |
| V7 独立金榕元 | `backtest/research/csv_minute_backtest_v7.py --pool-dir …` | 精确 14:55 close 首买 trial，缺根跳过；14:45–14:55 阶段加仓用 close | 仅当天首根 open 穿线走 gap open；其他止损看 close；timer 用该股当天实际末根 close | 独立仓位机、T+1、fee、旧逐股顺序；池必填 | X-02 / X-04 可选；不注册 `--minute-stop-trigger` / `--exdiv-ref-fen` | 海龟池/阶段账本内部绿 R/S；与共享书、网格红 | [成交核][correctness]；[X-02][x02]；[v7 `simulate_v7`][v7] |
| APP 独立 topk_app_dropout | `backtest/research/csv_minute_backtest_topk_app_dropout.py` | app∩qlib名单交给v7函数，沿其14:55 trial / 阶段close买钟 | 沿v7 stop/timer合同，不是共享TopK dropout卖法 | 原入口默认现金5亿；调用`simulate_v7`保留其默认时序/费用 | 当前CLI不透传TopK exec、hl、X-02/X-04等旗；不因复用v7函数就宣称入口可选 | 只在其独立池/合同内绿 R；与V7/T0/JR直接NAV混排红 | [entry §2/§4][entry]；[APP入口及调用][app-code] |
| A Mode A 日频对照 | `scripts/research/run_unified_exit_modea.py` → `unified_exit_modea.py` | 名单当日日线 front close | 触发日 front close；按市场交易日计期，到期无 K 顺延；期末 mark 不造 SELL | 日频；目标每实例 100 万、名义池 11 亿、双边 0.1%、无额外滑点；`tol=0.002` | **没有分钟 fill selector**；已有次日开盘买敏感锚由原报告路径管理，非新旗标 | 本模式内绿 R；与 B/v8 净值或绝对 PnL 混排红；front 调整币种须标明 | [提案 §一/§八/§9.3][proposal]；[Mode A 代码][modea] |
| B Mode B 网格 Q39 | `scripts/research/run_unified_exit_modeb.py` → `unified_exit_modeb.py` | 名单当日日线 none close，**不是 14:55** | 规则2：open 止损→止盈，未成再 close 止损→止盈，按对应 open/close；H/L 不触发、不成交。trailing 用 close 峰值/close；到期用实际末根 session close，无分钟则顺延、不借日收 | Q39 已是本入口规则；默认保留当前 `iter_grid()`（P1=A 窄格及已有附加臂），不是本轮重开 | CLI 有 `--tol` 等原参数，**没有**可把 Q39 一键应用到其他书的旗；research clock 在独立 harness | 同 B/Q39 全口径一致绿 R；旧 H/L 宿主 E、A、v8、JR 的“Mode B”均红 | [Q36/Q38/Q39][proposal]；[Mode B `_first_hit` / reference evaluator][modeb] |
| T0 TopK close | 共享分钟 `--strategy topk_dropout` | 14:55 close / 原回退，同 C0 | dropout 按扫描命中 bar close；其他卖因/止损沿原书，不统称日终卖 | `--topk-exec close`、walkdown OFF、`--topk-limit-rule qlib`；0.095 浮点带；原止损默认10% | 同参数显式 close 与省略应字节相同；`--stop-pct 0`才是显式nostop，不是默认 | 同 TopK 同合同绿 R；与 T1–T3 仅绿 S；CSV TopK vs JR 红 | [P1][topk1]；[代码][topk-code]；[books][books]；[默认 golden][topk-golden] |
| T1 TopK open | 同上，`--topk-exec open` | 精确 09:30 open 一次；缺根不借后行 | 卖出规则不换；自动进入分钟资金调度，open 卖款可供随后 open 买、同分钟 close 卖款不能倒借 | 非默认 | 仅 topk_dropout；无需额外传 X-02 | 同输入 T0/T2 绿 S；不是“默认 TopK 开盘” | [P1][topk1]；[CSV 调度][csv] |
| T2 TopK intraday | 同上，`--topk-exec intraday` | session [09:30,11:30] ∪ [13:00,15:00] 内首个有效 `open < limit_up`；等于上限继续等，按实际 open 尝试 | 同 T1；非涨停失败按已有规则结束，不能泛化为所有失败都重试 | 非默认；walkdown OFF 时原票日内重试，不跨日 | walkdown ON 改为首次涨停移交；见 T4 | 与 T0/T1 绿 S；严格上限比较不同于 close 的旧 epsilon | [P1][topk1]；[P3][topk3] |
| T3 TopK 名为 vwap 的分片 | 同上，`--topk-exec vwap` | 固定六时钟 09:35/10:30/11:30/13:00/14:00/14:55，各根 **open**；等名义预算 q/6；缺根不借、余款不滚 | 卖规则沿原书；新买通过原账本，预算/现金/容量按 P2 | 非默认；这是 TWAP-style 研究分片，**不按 amount/volume 取价** | `vwap × --limit-walkdown` 硬拒绝；非 s8 尾盘窗 | 与 T0–T2 只可绿 S；不可和 X-04 当同一种 VWAP | [P2][topk2]；[代码 `VWAP_SLICE_CLOCKS`][topk-code] |
| T4 TopK 替补 / 限价两根轴 | 同共享 TopK | 跟所选 exec；walkdown 候补继承原席位整份 q，首次涨停移交、原票当日不复活 | `real` 选择真实 named-limit 路径，适用本次运行买卖参考；不单独改成交时钟 | walkdown OFF；limit rule `qlib` | `--limit-walkdown`；`--topk-limit-rule real`；两者仅 topk_dropout；topk_score_exit 的非默认组合拒绝 | 分别改变候补名单或限价资格，只有显式固定其余轴才绿 S | [P3][topk3]、[P4][topk4]；`validate_topk_exec` |
| J1 JR M-LAG | `scripts/research/run_joint_return_replay.py --intents … --bars … --arm … --fill-mode M-LAG` | 合法 minute open，严格晚于 available_at，且 ≥ effective_at；显式 capacity / 订单合同约束 | 已冻结 SELL 意图同样按合法 open；不生成止损/持有期策略；close 用于估值 | **fill-mode 与 arm 必填，无默认模式**；validate 默认 v1 | `--fill-mode M-LAG`；`--validate-version v2` 为输入/验证能力 opt-in，不是新 fill | 同冻结包/身份/时钟/显式 bars 与 J2 可绿 S；与 CSV/网格红 | [JR 显式输入][jr-doc]；[JR 模块合同 / CLI][jr-code] |
| J2 JR M-REF | 同上 `--fill-mode M-REF`；`all` 分别运行两模式 | 合法 open 时点记账，价格取冻结参考；frozen 包须逐 intent 的独立 raw lake mark 证据，不以该分钟 open 冒充参考价 | 同参考价口径用于 SELL；理想流动性，但仍保留 T+1 / 停牌 / 方向限价；不是原参考时点可执行收益 | 必须显式选择 | `--fill-mode all` 不是混合撮合；frozen 仅 P-BASE；缺证据 INPUT_BLOCKED | 仅 J1/J2 的假设敏感比较；不得称 M-REF 可执行策略收益 | [JR 文档 Mode B][jr-doc]；[JR code][jr-code] |
| R1 敏感格 batch1–3 局部事件 | `scripts/research/run_minute_sensitivity_b.py` 及既有 exports | 固定基线事件/股数后比较候选 open 或 slip；Book chase、v7 add 分列 | batch3 Mode B `next_tradable_open` 为实例对照；Q39 baseline，oracle 另列事后上界 | 独立研究 harness，不是生产旗 | `next_tradable_open` 是研究模型名称，**不是共享 CSV CLI 参数**；合成/真数据的标签和寿命按各批合同 | 只在同实验单位比较局部价差/bp；局部 bp → 全策略 NAV 红 | [敏感计划 §1–§7][sensitivity]；原脚本 / exports |
| R2 敏感格 batch4 全策略 | `scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py` → 独立 adapters | `production_default` 委托原引擎；`next_tradable_open_research` 替换全部买卖 fill；成交价执行 Q2 重定量 | START 标签 close 可得于 hm+1min，submit=decision+1ms；仅 [09:30,11:30) / [13:00,14:57) 候选；买卖同日到期，卖意图不跨日粘住、次日策略重评 | `--cells baseline_default_clock_fee`；API clock=`production_default`、slip=0 | `--cells clock_next_open_fullstrat` / `slip_5bp_fullstrat` / `slip_10bp_fullstrat` / `slip_20bp_fullstrat`；API `clock_mode` / `slip_bp_per_side`，clock XOR slip | Book/v7/B **各自**绿 S，跨引擎红；未默认覆盖 TopK、新8.x、11/12 等全部新能力 | [计划 §9][sensitivity]；[设计 §9][fullstrat-design]；[hooks][research-hooks] |
| H 共享 hl 触发 | 共享分钟 `--minute-stop-trigger hl` | 买侧时钟保持所属行 | low≤stop 按 stop，gap 按 open；high≥已有固定 target 按 target/open，需原回调确认；同 bar 止损优先；不是把 trail/MA 全改 H/L | `close`，显式 close 与省略一致；hl 走 Python | 历史 H/L 切片 S1（普通/独立仓扫描）及 S2（X-02）已接，并非本次 S1/S2 审批门；拒绝 version12、`--fix-s11-exit-domain`；v7/日线无此参数 | 同书 close↔hl 绿 S；与 Mode B 旧 H/L、Q39 不同合同 | [H/L P1][hl]；[扫描][csv] / [X-02 cursor][cash-code]；[小 helper][hl-code] |
| X2 时序现金 | 共享分钟 / v7 `--fix-minute-cash-order` | 保留各报价规则与旧 fallback，按 decision_hm 用当刻现金 | open/close 相位调度（hl 相位见 §4）；同 hm close 卖先买后；不宣称 tick 先后；v7 timer 顺序仍独立 | OFF；TopK 非 close 或 walkdown 会自动走该调度 | version12 ON 拒绝；不能只看 CLI OFF 就推断实际调度为 legacy | 同引擎 OFF/ON 绿 S，必须标记有效 cash-order policy | [X-02][x02]；[CSV][csv]；[v7][v7] |
| X4 尾盘首买 | 共享 8/8.1–8.6 及 v7 | 精确 14:30 open 定父单；14:30–14:56 +15:00 共28片；连续段有 amount 列用 amount/volume_shares，否则 close；有列但无效不回退；15:00 close | 卖侧保持所属书；close 阶段分片、10% 分钟容量及原费用；14:57–14:59 无子单 | `--tail-window-buy` OFF；`--tail-volume-unit shares` | 必须同时 X-02；`lots` 显式×100；Q<2800 股每片0、不用普通首买 supplementary 100股兜底 | 各自尾盘 ON/OFF 绿 S；须有14:30前信号可得证据，未证实时不得宣称可执行；和 T3 红色混同 | [X-04][x04]；`tail_window_buy.py` |
| E 参考价到分 | 仅共享分钟 `--exdiv-ref-fen` | 成交规则不换；改变已映射除权参考价及相应限价门 | ON：成功映射参考价先 HALF_UP 到分；已登记事件 noise_eps=0，fallback 仍原1%门槛；成本/peak 的 k 不舍入 | OFF | version12/front 不走 E-R6 loader，不能因 flag ON 就声称已覆盖；v7/日线不注册 | 同书 OFF/ON 绿 S，价域及 economics 同时固定 | [P2][fen]；[CSV loader wiring][csv] |
| F 费率 opt-in | 共享分钟 `--qlib-cost`；v7 显式 FeeSchedule API | 默认每边10bp/min0；ON 买5bp/卖15bp/min5 | 共享账本按原函数调用收费，v7 聚合调用粒度不同；不是改变成交价模型 | `--qlib-cost` OFF；`DEFAULT_SCHEDULE=BILATERAL_10BP` | 模式网格仍线性佣金；JR 用 manifest 费用，不能套共享默认 | 固定本引擎下可作费率敏感比较；不把费率差误归时钟 | [fees][fees]；[当前 CSV][csv]；[成交核费率合同][correctness] |
| V/E API-only 容量 / 显式权益 | shared `simulate` / `simulate_v7` 原 API | `participation_rate` + `volume_for_bucket`；`exdiv_economics` 显式事件 | 不借未完成量；权益/应收与 T+1 沿原实现。Mode B `shares/=k` 与这套显式权益不同 | 两者均 `None`，非默认研究配置 | **没有上述同名通用 CLI 旗**；按现存 API 范围，不自动扩展 runner/loader | 容量、权益、费率、股数语义不齐则红 | [成交核 §2.4/§2.5][correctness]；[API 签名][csv]、[v7][v7] |
| G7 / domain 邻接开关 | 共享入口已有 `--fix-s81-band-precision`、s11/s12 domain flags | 不定义新买钟 | G7 仅8.1分档精度、ON从原始价格做精确分数；domain 开关各管各书 | 全部 OFF；不重裁业务 | 登记为比较身份的附加约束，不升级为全局 fill 枚举 | 可有独立专题同书 A/B；本刀不派跑、不分析 G8/12 收益 | [G7 冻结说明][g7]；[books][books]、[CSV][csv] |

## 4. 不可抹掉的边界

1. **两个 Mode B 不同名空间**：`unified_exit_modeb` 是 stock_pool 卖出网格；JR 文档“Mode B”是同一冻结意图包的 M-REF/M-LAG 对照。输出标题必须带入口家族，不能只写 Mode B。
2. **三个 close 不同**：`--topk-exec close` 是买侧14:55分钟 close；`--minute-stop-trigger close` 是分钟止损触发域；`--stop-fill close` 指日线 EOD 止损，**共享分钟入口拒绝**。不得提供含糊的全局 `close` 别名。[CSV `simulate`][csv]
3. **H/L 与 Q39 优先级不同**：Q39 先 open 阶段，若 open 止盈已成便不看 close；hl 是保守 OHLC 止损优先，即使 open 越过 target 而同 bar low 穿 stop 也先止损。名称相近不能合成同一规则。X-02 下跳空止损在 open 阶段；H/L 触价在该 bar close 阶段观察并结算，固定目标也在 close 阶段评估，虽跳空目标成交价可取 open。报价为 open 不等于在 open 阶段结算，不据此宣称 tick 级先后。[H/L 冻结说明][hl]、[HeldMinuteCursor.advance][cash-code]
4. **scan / touch / mark 分开**：14:57–15:00 的 `closing_call` 只是标签，现有 touch 资格冻结；共享书 NAV 继续日线 close / prior close / lot-cost fallback。TopK intraday 包含15:00、研究 next-open 排除14:57起、X-04只在15:00另有片，三者不能互相推导。[成交核 P1/P4][correctness]
5. **原模块已经存在**：`ashare_fill_clock.py` 仅命名，`minute_stop_trigger.py` 只是小 helper（`validate_minute_stop_trigger` / `validate_low` / `blocked_bar` / `target_fill`）；**hl scan/fill 语义在 simulate 扫描循环中**，包括 `csv_minute_backtest.scan_held_day_python` 与 X-02 的 `minute_cash_order.HeldMinuteCursor.advance`，不能归给这个小模块。`topk_minute_exec.py` 管 TopK 买侧，`fullstrat_research_hooks.py` 管隔离研究调度。目录不能让这些模块交叉承担新职责。[命名叶子][clock-code]、[小 helper][hl-code]、[扫描][csv]、[X-02 cursor][cash-code]

## 5. 默认锁（计划 §4 摘要）

S0 前后**所有行为保持一致**：成交、拒绝 / 异常、现金、持仓、统计、旧输出格式及既有显式 opt-in 均不变。这里锁定当前基线，不能拿更旧 golden 撤销已合入修正，也不能只凭最终 NAV 一致声称完整状态 / 字节一致。

- 共享普通池买仍为 14:55 close 与原回退，适用书追买仍为 09:45 close 与原回退；version11 精确 09:30 open、version12 自有路径分别保留。`minute_stop_trigger=close`、原扫描顺序及 numba 选择不变；日线 `stop_fill=touch`，分钟继续拒绝 `--stop-fill close`。
- X-02 默认 OFF；TopK 非 close 或 walkdown 自动进入分钟资金调度，`real + close + walkdown OFF` 不单独切调度。TopK 默认 close / qlib / walkdown OFF、原 10% 止损及各 exec 比较边界保持；`--stop-pct 0` 才关闭止损。v7 首根 gap、timer 及独立账本顺序不变。
- S8 的 8/8.2–8.6 默认 `per_name`、加权成本、T+1 延迟及不足现金抛 `InsufficientCashError` 保持；8.1/v7 等仍按原语义。共享默认现金 `21_000_000.0`、名义单码预算 `1_000_000.0`、`ration=file_order`、seed=0、按书解析的 `daily_quota` 与 TopK planned 分母 / 0.95 部署不变；APP 默认 5 亿、v7 默认 2100 万各自保持。
- shared/v7 默认双边 10bp / min 0，`--qlib-cost` OFF；Mode A/B 线性 0.1%，JR 取 manifest。扣费调用粒度及普通路径无新增 slip 保持。各入口限价 / Decimal / 容差、T+1 / 红股锁定与跌停门各自保持。
- X-04 OFF、volume unit=`shares`，已存在的 ON 合同不动；fen OFF、容量 / economics API 默认 `None`。E-R6 的适用 / 跳过规则、Mode B `shares/=k` 与显式权益边界保持。s11/s12 domain flags、`--fix-s81-band-precision` 均 OFF。
- 行情 source 默认 lake、`dividend-type=none`、s12 信号 front 及 domain OFF、各书缺根 / 零量 / 缓存身份 / resolver 报错规则不动。Mode A front 日收、Mode B none 日收买 / Q39 卖及当前网格、期末 mark 不造 SELL 均保持。
- JR 的 arm / fill-mode 必填、validate 默认 v1、缺显式 bars 则 `INPUT_BLOCKED`、意图有效期 / 容量 / Decimal / per-order 费用不变。研究 hooks 默认 `production_default` + slip 0 委托原引擎，harness 默认 baseline cell、clock XOR slip、Q2/H2 不变。
- 所有 book / HELP_LOCK / parser / presets、trades / equity / stats / summary、manifest、touch / mark 分离及固定 hot-path fence 不动；`--emit-run-manifest` 默认 OFF，X-04 现有自动开启行为保持。默认输出不加字段、不重录 golden。本片以文档 allowlist 和非文档零 diff 验收，不宣称运行了行为回归或字节锚测试。

## 6. 研究 opt-in 与混比禁令（计划 §5–§6 摘要）

研究身份须能追溯：**入口家族 + 名单 / 意图 hash + 窗口 / 日历 + 初始资金 / 仓位 + 价域 / 公司行动 + fee / cap / mark + 实际生效的策略 / 时钟 / 限价 / 现金顺序**。记录原始 flags 之外，还要说明自动启用的调度、实际适用范围、信号可得时刻、bar 标签 / 时区、decision / submit / quote / execution、缺根回退与有效期。缺项标“未证实”，不猜默认。

沿用 `topk_exec`、`minute_stop_trigger`、`clock_mode`、`slip_bp_per_side`、`fill_mode` 的现有名称，不新增通用 `--fill-policy` / `--clock`。单个开关已有验证不等于所有组合已认证；分别记录“已有验证 / 允许但联合效果未证实 / 明确拒绝”。新研究行为仍须独立 GO；本表不扩兼容矩阵、不接 CLI 或 writer。

优先引用已有 manifest / run-config、TopK `topk_execution.json`、X-02 audit、JR 工件与敏感格报告；缺项写在新实验的外部说明，不重写旧 CSV / manifest 或默认产物。`session_phase` / `price_rule` 只是非穷尽标签，空值不表示未成交，单列标签不足以识别全部成交假设。[时钟与 mark 合同][correctness]、[TopK 审计][topk-code]、[X-02][x02]、[研究 hooks][research-hooks]保留各自职责。

- **绿 R：同合同内排名。** 必须核齐上述身份；同一共享书省略 / 显式默认应完全一致。同池共享书只有资金、sizing、域、fee、clock 等全齐才可比较规则；`per_name` / `daily_quota` 不同就撤销 NAV 排名资格。Mode A 与 Q39 Mode B 的网格仅各自内部可绿 R。
- **绿 S：分列的受控敏感性比较。** 同书 close↔hl、X-02 / fen / X-04 OFF↔ON，同 TopK exec / walkdown / qlib↔real，同引擎 batch4 baseline↔clock 或 slip，以及同完整冻结包 J1↔J2，均须声明实验轴并固定其余身份。若模式捆绑现金调度等变化，应写“exec 组合假设”，不能声称只换价格。它们不能混成同合同收益榜。
- **红：禁止跨入口直接 NAV / 收益混排。** Mode A↔Mode B、策略8↔A/B、Book↔v7↔网格、APP↔V7 / TopK / JR、CSV TopK↔JR，以及两个“Mode B”均不可仅凭同池、同分或同名排名。Q39 已废止的历史 H/L 宿主 E 只作规则差异说明，旧冠军数字不能移植。
- **红：禁止跨实验单位或证据等级混排。** batch1–3 局部 bp 不换算成 batch4 全策略 NAV；Q38 oracle / 合成 PASS / 合同 PASS 不代表可执行收益。M-REF 是参考价 / 理想流动性对照，不能标成可执行策略收益。TopK 六片 `vwap` 与 X-04 尾盘窗也不能当同一种 VWAP。
- 任何关键身份未知、价域无效或权益 / 数量 / 费用不齐均为**红**。X-04 缺 14:30 前信号可得证据时仅为假设研究；CSV 文件名 / mtime 不能证明信号已可得。batch4 旧 adapters 不自动覆盖当前所有新书或 opt-in。不得拼接不同 policy 区间的 NAV，或把多个 cell 合成实盘曲线；本片不授权新跑数或实现通用 report gate。

局部事件与全策略实验分别见 [敏感计划 §1–§9][sensitivity]、[batch4 设计 §9][fullstrat-design]；JR 显式输入 / 参考价边界见 [JR 合同][jr-doc]。所有绿色都须补齐证据，不能凭表行名称自动放行。

## 7. 本片范围外

- **S1 只读目录需独立 Human GO**，先点名机器消费者及为何 Markdown 不够；本片不建 catalog、API、枚举、测试或 metadata writer。
- **S2 每个 helper 都需单独 Human GO**，证明真实调用点同合同，并对所有受影响入口 / opt-in 提供完整状态与产物 byte-identical 证据。Q39≠hl、v7≠共享 gap、TopK vwap≠X-04、JR≠CSV，不能借同名抽取。
- 不重开 Mode A/B phase-2 网格、甲乙卖点或 stock_pool 收益最大化；不增删网格臂，不开 JR 新刀，不改冻结包 / bars / clock / fee，不处理 G8 / strategy12 业务。
- 本 PR 只改本 SSOT、`research-backtest-entry.md`、`AGENTS.md`、`engine-ashare-correctness.md` 四份 Markdown。无 `.py`、测试 / fixture / config / CI / HELP_LOCK / parser / preset 改动，无湖与新 NAV，无默认翻转。`plan-minute-fill-policy-infra-2026-09-28.md` 浏览副本保持 untracked / out of PR。

[entry]: research-backtest-entry.md
[positioning]: engine-positioning-ssot.md
[proposal]: stock-backtest-unified-exit-proposal-2026-09-17.md
[correctness]: engine-ashare-correctness.md
[stop-plan]: plan-minute-stop-and-exdiv-fix-2026-09-26.md
[topk-plan]: plan-topk-exec-model-2026-09-26.md
[hl]: minute-stop-trigger-hl-p1-2026-09-27.md
[fen]: exdiv-ref-fen-p2-2026-09-27.md
[topk1]: topk-exec-p1-2026-09-27.md
[topk2]: topk-exec-p2-2026-09-27.md
[topk3]: topk-exec-p3-2026-09-27.md
[topk4]: topk-exec-p4-2026-09-27.md
[sensitivity]: reviews/plan-minute-sensitivity-b-2026-09-20.md
[fullstrat-design]: reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md
[jr-doc]: joint-return-frozen-explicit-price.md
[jr-regen]: handoff-joint-return-clock-regen-2026-09-24.md
[x02]: x02-minute-cash-order-2026-09-25.md
[x04]: x04-tail-window-buy-2026-09-26.md
[g7]: g7-81-float-band-2026-09-28.md
[csv]: ../../backtest/research/csv_minute_backtest.py
[v7]: ../../backtest/research/csv_minute_backtest_v7.py
[app-code]: ../../backtest/research/csv_minute_backtest_topk_app_dropout.py
[books]: ../../backtest/research/csv_strategy_books.py
[modea]: ../../backtest/research/unified_exit_modea.py
[modeb]: ../../backtest/research/unified_exit_modeb.py
[topk-code]: ../../backtest/research/topk_minute_exec.py
[jr-code]: ../../backtest/research/joint_return_replay.py
[research-hooks]: ../../backtest/research/fullstrat_research_hooks.py
[clock-code]: ../../backtest/research/ashare_fill_clock.py
[hl-code]: ../../backtest/research/minute_stop_trigger.py
[fees]: ../../backtest/research/ashare_fees.py
[topk-golden]: ../../tests/fixtures/topk_exec_master_close/README.md
[cash-code]: ../../backtest/research/minute_cash_order.py
