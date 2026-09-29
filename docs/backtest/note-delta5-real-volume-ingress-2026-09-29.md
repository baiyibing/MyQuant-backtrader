# Track D｜δ5 真实分钟量研究接入合同（2026-09-29）

**合同 ID：`D5-REAL-VOLUME-INGRESS-v1`；本刀仅文档，来源验收 / 实施 / 湖运行均 NOT_RUN。**
核对基线：`fd74932dc2d86bb01cd47f2ebc39ce8a389ace2f`；`production_C=frozen`。
授权：2026-09-29 Human「D GO」；范围来自同日 ORDER_EVAL（A–E residual tracks）§7「Track D card — industry / #135 线」。
本页冻结下一刀可实现的接入合同，不表示已有 certified source、harness、运行回执或比较授权；**未经 Human「合」不合并**。

## 1 唯一首消费者与边界

- 唯一消费者：共享分钟 **`version8`** 的 [`csv_minute_backtest.simulate`](../../backtest/research/csv_minute_backtest.py)，既有 kwargs **`participation_rate` / `volume_for_bucket`**。
- 下一刀以**独立 research harness/provider** 读取、核验并映射 certified raw incremental minute volume；调用原生 API，不经共享 CSV `run/main`，不加通用 parser flags，不重写 [`VolumeCap`](../../backtest/research/ashare_volume_cap.py)。v7 待同一来源合同验证后另列验收。
- 首批输入限具名沪深主板普通股票、完整交易日短窗、公司行动覆盖证据明确为无事件；池、名称、日历、费用、资金及全部实际参数预登记。无法证明适用性即拒绝该样本，不能默认为无事件 / 非 ST。
- 使用 version8 当前 `per_name` 独立持仓；`minute_stop_trigger=close`，X-02/X-04 及其他新增 opt-in 均 OFF，`exdiv=None`、`exdiv_economics=None` 只在上述无事件证据成立时使用。不改默认书、BOOKS、HELP_LOCK、presets、golden、writer 或输出 schema。
- `participation_rate=None` 唯一表示 cap-off：不创建 cap、不查询 provider，仍为该基线、**同一规范化输入**的既有行为。显式有限 `0≤p≤1` 才 cap-on；`p=0` 是零容量，`p=1` 仍受真实桶量约束。本文 `.10` 等均为算术夹具，无默认 rate。
- cap-on 为 **completed-bar capacity approximation**；真实成交量 **≠ 可成交量 / 排队证据**。不证明订单到达顺序、冲击、竞价撮合或 NAV 可执行性，不授予 SSOT 绿 R/S；`no_ssot_compare_authorization` 保持。

## 2 来源、单位与价格域：先认证，后构造 API 输入

认证对象是一个不可变、具名源快照及映射规则，不是把 `unit` 或 `source_kind` 填成某个字符串。
实际 provider、分区、日期与 hashes 尚未取得，禁止从本页例子推导真实数据可用。

| 维度 | 未来 ingress 必须满足的合同 |
|---|---|
| 路径与身份 | 仅消费配置 resolver：`resolve_period_root("1m")` / `resolve_period_root("1d")` 下显式 `dividend_type=none` 分区；记录 resolver 配置来源、解析后绝对根、实际分区/文件、源发布者/版本、snapshot ID、schema 与逐文件 SHA-256。缺配置/根/文件即报错；不猜盘、探盘、下载或 merge |
| 证券与粒度 | 记录 source symbol→engine symbol 显式一一映射；碰撞/未知证券拒绝。一条记录对应一个证券、一个 session、一个物理一分钟区间；同键重复（即使同值）、重叠桶、乱序或无法确认的聚合行均拒绝，不能 keep-last、相加或自动修补 |
| 数量 | 源必须证明为 **raw 域增量股数**，非手、金额、累计量、复权量或买卖方向子集；值为有限非负整数，bool/null/NaN/负数拒绝。存储为浮点时须有股数单位证明、精确整数值及可无损表示证据，否则拒绝；不凭 dtype 猜单位、不四舍五入 |
| 转换边界 | v1 不支持 lots×100、amount/price、累计差分或日量分摊。需要这些来源先申请独立映射合同；类型化 `BucketVolume` 不是来源认证 |
| OHLC / mark | 分钟 OHLC 与量来自同一物理桶和冻结快照；价格均为 raw 元/股，有限正值且 OHLC 自洽，量仍为增量股数。日线 raw close 用于既有估值；禁止 front 日线与 raw 分钟混用，也不把 EOD 量用于 cap |
| reference / limits | 记录每日参考价所用前一有效交易日日线 raw close、证券/名称 as-of 证据及既有 `book_limit_prices` 参数；首日须有前序日线。无事件证据覆盖前序参考日到结束日；不替换参考价、不改到分/档位规则、不从价格跳变猜公司行动 |
| 覆盖证据 | 显式交易日历、每证券生命周期/停牌状态、预期桶集合、无公司行动覆盖及各证据 hash。交易日不存在、代码未上市与缺数据不能混为一类；样本不适用即停，不能静默缩宇宙/窗口 |

上述股数单位、精确整数值及可无损表示证据全部通过后，harness 必须显式转为非 bool 的 `int` 再传入 `BucketVolume.shares`；不得透传 `2500.0` 等整数值浮点。helper 拒绝非 `Integral` 值（以及 bool），诊断为 `skip_volume_unavailable:invalid_shares`；不得为此修改 `VolumeCap`。

未来核验应在旧 reader 去重、过滤或丢列**之前**检查源记录。现有 `read_lake_minute_ohlc` 有 keep-last/时钟投影，G2 缓存指纹也不是内容或单位认证；不得把已清洗 frame 当原始来源证明。

## 3 时间合同：物理区间 → close key → available_at

先取得源时间字段的 epoch/墙钟编码、时区、START/END 定义及边界说明，再转换；禁止根据 `09:30`、字段名 `UTC` 或首末行猜标签。
逻辑时区固定 `Asia/Shanghai`：真实 UTC instant 先换本地；若源以 UTC 容器存本地墙钟，须有该编码证明并按墙钟解码，不能机械加八小时。
最终给 `simulate` 的 index 为本地墙钟的无时区 DatetimeIndex，`ymd=YYYYMMDD`、`hm=60×hour+minute` 与其一致；helper 不再换钟。

| 源标签 / 情形 | 唯一映射及拒绝边界 |
|---|---|
| START `09:30`，证明为 `[09:30,09:31)` | close key=`09:31` / `571`；该行 OHLC、量、index、ymd/hm **一起**映射，不能只移动 volume 后拿另一行价格 |
| END `09:31`，证明对应同一物理桶 | close key 仍为 `571`；START/END 两份等价合成输入应产生相同规范化 frame/map 和原生结果 |
| 午休 / 日尾 | START `11:29→11:30`、`14:59→15:00` 仅在源确证该物理一分钟时成立；`11:30→11:31`、`15:00→15:01` 越出相应交易段即拒绝，不滚到午后/翌日。跨午休/跨日/多分钟聚合不得拆成一分钟 |
| 开收盘特殊标签 | `09:30` END、`13:00` END 及 `14:57–15:00` 行必须有区间/竞价聚合说明；无法证明逐桶增量或含重复竞价量即源不适用并失败。**不**因 L2 的 14:57 截止裁掉旧扫描器行，也不改变旧 touch/mark 资格 |
| `available_at` | 使用源记录或发布合同可证明的最早已知时刻，且不早于 close；来源/规则/原始时间均归档。只证明桶结束而不证明可得性不够，不能为了成交填 `available_at=hm`；事后文件 mtime 不充当历史可得时刻 |
| 精度及 API 投影 | bar 边界须精确到分钟；秒级发布时间向上取整到同 session 分钟，不能向下取整。转换成 `BucketVolume(shares, available_at, "raw_shares_incremental")`，要求 `hm≤available_at<1440`；跨 session 发布时间 v1 不支持，拒绝该源记录 |
| 成交尝试 | 完成桶 close 仅在 `hm≤available_at≤attempt_at<1440` 可用；open 使用 `attempt_at=hm-1`，lookup 前就拒绝未完成桶。不找前桶救 open，不借后桶/EOD/未来可得量 |
| 实际报价回退 | 原 pool/step ≤14:55、chase ≤09:45 路径若回退，cap key 取**实际报价行**；不能取目标时刻的量。现调用点按该行时刻检查可得性，不能由 harness 放宽为目标钟点 |

START 规范化是独立 harness 的显式输入映射，不修改共享 loader 的时钟，也不宣称与未经规范化的旧 CLI 源帧逐字节等价。

## 4 缺失、停牌、零量与窗口失败

- 未来 run 在 `simulate` 前做完整预检：具名证券×预登记执行日历×源合同预期桶，以及所需前序日线/mark。start/end 为闭区间完整交易日，另列 warmup/reference 窗；不接受半桶或只剩部分首尾 session 的裁切。
- 按**映射后物理 close**判断执行窗；START 原始读取边界须覆盖最后桶，不因转换漏掉末桶。首尾缺桶、缺首日前收、缺应有日线/mark、静默日期 clamp 或源更新导致 hash 漂移，整次 ingress FAIL，保存缺口清单，禁止返回空表/空成功。
- 普通 active 桶缺行、量字段缺失、身份/单位/可得性未知：整次 ingress FAIL；不补零、不前填、不插值、不拿邻桶替代。v1 仅接受已证停牌的缺行例外；其他稀疏源先拒绝，不能靠原生报价回退通过来源预检。
- **有效零量**须有源记录和明确状态，`V=0` 可传 typed sample，`skip_volume_cap:zero_or_exhausted` 是业务零成交；零量不等于停牌。分钟零量行不为“跑通”删除，正价格仍须有来源，不能造 OHLC。
- **已证停牌**允许无分钟行，独立 coverage 记录原因/日期/证据；不造零 bar。若源提供零量行则如实保留；停牌却有正量或相互矛盾状态即 FAIL。持仓/mark 继续原日线 on/prior 规则，不能因无分钟量删除估值；需有相应真实日线参考。
- 确认存在但延迟可得的量可以是合法输入，在过早 attempt 下由 API 记 `skip_volume_unavailable:available_at`；这与缺数据的 ingress FAIL 分开。输入不通过预检时不能靠原 API 的 missing skip 冒充有效研究。
- 未来 provider 对已登记合法 key 返回冻结 typed sample；已证无 bar 的停牌项可返回 `None` 并保留证据。遇未登记 key/覆盖违约必须抛出会传播的异常（例如 `ValueError`；不用会被 cap 吞为 missing 的 `LookupError`）。不吞其它程序异常、不自动重试换源。
- 窗口末仍有残仓按既有 mark 记录，不能额外强平或借窗外容量。若某验收格需要下一 session 退出，运行前扩展并冻结窗口；缺尾部证据则该格 NOT_RUN，不能事后延长求 PASS。

## 5 既有 δ5 经济与状态锁（按本页基线，不复原历史旧书）

`B=floor(p×V)`、`R=max(0,B-used)`；既有 helper 用 `Decimal(str(p))` 的精确整数比取整。
每 run 的 `(engine_symbol, session_yyyymmdd, close_hm)` 跨买卖、pool/chase/step、所有同码持仓/lot 共用；成功记账后仅扣实成股数。
首查固定 sample（含缺失）；回访不重置，换桶不结转，不跨 run 共享。原路径/lot 遍历顺序不改造成新的全局事件栈。

| 路径 | 冻结行为 |
|---|---|
| 门与数量 | 原价格/档位/名称/T+1/资金门先行；请求含费现金不足不得用 cap partial 解围。version8 当前 `per_name` 保留 `InsufficientCashError`；买量按 `min(requested,eligible,R)` 向下整百，force-min 不突破 R；卖可为整数零股 |
| 买残量 | 仅实际买量建 lot/扣现金/推进原成功状态；未成请求失效，不生成跨桶订单。原追买、台阶条件可独立再触发，但不保存本次剩余数量 |
| version8 卖残量 | 当前独立持仓按整体加权成本评退出、逐 lot 记账；既有退出意图锁存后，容量拒绝/partial 的余仓沿原 pending 规则在后续可卖已完成桶 close 继续处理，同日后桶也可重试，价格反弹不取消已锁退出。保留原因、position_id/lot 与 T+1 归因；不把纯容量延迟标成 `t1_deferred` |
| 原子关联组 | 既有旧 lot `pending_exit` / `ride_with` 分支仍整组 T+1 可卖且 R 足够才成交；不足为 `skip_volume_cap:atomic_exit`、扣量 0，嵌套树保持 `unsupported_ride_tree`。**不能把 version8 独立持仓视图误作旧 ride 组**，也不能把旧组改成逐笔跨桶补单 |
| 费用与 mark | version8 保留逐 lot / 每次实际 fill 的佣金调用及最低费；不按桶/整组净额合并费用。mark 不耗量，费用默认、现金、统计、配额与持仓状态按实际原生结果保留 |
| 与 L2 分界 | 不引入 L2 reserve、双侧整手容量、显式订单 expiry/cancel 或其时钟/费用累计模型；δ5 买整百/卖整数、策略 pending 和 L2 外部订单生命周期保持独立 |

源码锚：[`ashare_volume_cap.py`](../../backtest/research/ashare_volume_cap.py)、[`csv_ledger.py` 的 `_sell_s8_group` / `_sell`](../../backtest/research/csv_ledger.py)、[`minute_cash_order.py` 的 `advance_independent_exit`](../../backtest/research/minute_cash_order.py)。
历史 [δ5 §2.4](plan-industry-align-p3-d5-volume-cap-2026-09-19.md) 的普通 lot“一日首次尝试”不能盖掉后续 [version8 独立持仓 §1.3](s8-independent-positions-2026-09-26.md)；本刀只说明当前分叉，不重写任何实现。

## 6 下一刀验收矩阵（可手算；本刀未执行）

每格保留人工 oracle、直接原生 API（手工构造规范化 frame/map）与未来 harness（源 fixture→同一 API）三列结果；不得两侧共用被测 mapper 算预期。
`N/H` 表示须做 native/harness 完整结果对照，`I` 表示源预检负例（harness 拒绝且 API 未调用），`L` 表示既有 helper/ledger 边界验证；不能把 L 说成 version8 public E2E。

| 格 / 层 | 输入与正反例 | 手算或可核预期 |
|---|---|---|
| M1 N/H | 同输入省略 rate / 显式 None；provider 若调用即报错；对比 p=0 | 前两者完整旧结果相同、provider 调用 0；p=0 启用且合法正量亦无成交 |
| M2 N/H + L | p=.10，V=2500，现金充足请求买500 | B=250，买200，used=200，R=50；后续同桶请求100不能 force-min 成交；300剩余不挂单 |
| M3 N/H | p=.10，V=3000；同码不同持仓/path 依原顺序买200后买200 | 第二笔最多100；used=300，回访无新增容量；新桶独立，不结转旧余量 |
| M4 N/H + L | p=.10，V=3000；N/H同桶按原顺序卖旧仓200再买100；L反向买100再卖旧仓200，另测卖101 | 双向 used=300，无买卖各300；卖101在T+1/原子规则允许时可成交，不强制整百 |
| M5 N/H + I | START 09:30 / END 09:31 的同物理桶；available_at=571 / 572 | 规范化两源相同；close571前者可用、后者 unavailable；open570即使V巨大也不查询未完成桶；未知标签/倒填时间失败 |
| M6 I + L | 普通14:55缺失；另在原生fallback夹具给14:54报价、V=3000，895桶巨量 | harness因缺行拒绝；原生夹具仍用894桶、B=300，不借895，不把旧API容错改成生产异常或声称harness通过 |
| M6b N/H | 隔离的单持仓连续退出夹具，仅改变后桶量，关闭无关买入/退出路径 | 之前桶的分配/used相同，后桶可不同；只验证该夹具容量前缀，不宣称X-02 OFF全日扫描具有全局因果时序，亦不要求末尾NAV不变 |
| M7 N/H + I | typed V=0；负/null/NaN/bool/手/累计/重复键/不明来源；已证停牌 | 零量为业务 cap skip；非法源为 I，原生边界缺 sample 为 unavailable；停牌不造 bar/容量，mark 保留 |
| M8 N/H | version8旧仓500，退出桶B=200、后完成桶B=300，之后价格反弹；另测退出前已加同日新lot | 旧仓200+300沿锁存原因退出，容量延期无T+1后缀；新lot遵守T+1，解禁后沿原原因与归因退出 |
| M9 L | 旧ride组300+200，R=400 / 500；子lot为今日 / 嵌套树 | R400整组0；R500且全可卖才500；T+1或嵌套失败0扣量、关系与原因保留；不推广为version8整仓必须原子 |
| M10 N/H + L | 两lot各卖100股×10元；夹具费率=.0015、最低5 | 每lot max(1.5,5)=5，共10；不得合并成一次最低费5。现金/T+1/limit失败不耗量；资金不足保留原异常 |
| M11 I | 缺根/分区/首日前收/首末桶/mark、跨午休/跨日、source hash变化 | fail并记录准确缺口，禁止截短、填空或输出成功NAV；已存在输出根也须拒覆写 |

完整对照至少包括：输入 canonical hash、provider key/调用轨迹、成交顺序及全部原生字段（价/量/费/reason/标签/身份）、现金、各lot及独立组状态、pending/peak/台阶、stats/配额、equity/EOD_MARK、`volume_cap.used`、异常类型/信息、运行状态与输出文件集合。
同输入两侧经济字段必须一致；仅显式预登记的绝对输出路径/耗时等非经济差异可单列，保留原值，不 scrub 后声称 byte-identical。不重录 golden，不因未触发格而声称覆盖；每格 PASS / FAIL / NOT_RUN / 未覆盖分别记录。
参考既有合成锚：[`test_ashare_volume_cap.py`](../../tests/test_ashare_volume_cap.py)、[`test_s8_group_exit.py`](../../tests/test_s8_group_exit.py)、[`test_s8_ledger_review.py`](../../tests/test_s8_ledger_review.py)；引用不是本刀重跑证明。

## 7 Provenance、缓存与外部输出

未来研究工件使用独立 schema `d5_ingress_v1`；下表为必需字段组，非对旧 manifest 的追加要求。

| 字段组 | 必须记录 |
|---|---|
| authority / run | contract ID与文档hash、实施/运行GO路径及hash、run_id、code SHA、解释器/依赖摘要、strategy与完整显式参数（含rate、费用、seed及OFF开关）；输入为真实行情时池/信号来源仍独立注明，合成池不得标真实策略 |
| source / evidence | resolver配置来源/解析根、发布者及snapshot、实际文件清单/大小/schema/SHA-256、读取前后身份校验、证据出处/认证者/时间；synthetic 与 certified-real 分开，B线只可复用逐项核实的源事实，不能借其经济PASS |
| mapping | symbol映射、time编码/时区、START/END与物理区间、unit/raw/incremental证明、availability规则及原值→投影值、mapping版本/hash、规范化frame与bucket map的canonical hash |
| coverage / prices | 请求窗/实际窗/前序日线/日历、预期与实际桶计数、零量/停牌/缺口明细、公司行动覆盖、reference/limits/mark来源与价域、池/名称文件hash |
| result / audit | 每格状态、native/harness原值与差异、输出文件hash、失败阶段/异常/缺口；`comparison_status=no_ssot_compare_authorization`，不得写SSOT green |

- 缓存姿态固定 **不读不写共享分钟缓存**；本刀也不建新缓存。未来 harness 可在单次 run 内冻结已验证 map，跨 run 不复用；G2 shallow identity/token 不能替代本合同的实际源文件hash。不得污染旧缓存或重建它来“认证”volume。
- 未来输出仅写用户显式指定、仓库及行情/共享缓存/既有研究产物之外的 `external_parent/run_id/` 新目录；parent不得重叠输入根，run_id不得逃逸目录，已有根拒覆写。两侧子目录隔离，失败也保留输入身份/阶段回执，不能放到旧 CSV writer 或 L2 artifacts 根。
- 退出判定：预检/provider/API/隔离写出失败为非零；合法零量/容量拒绝可是成功研究run但验收格未必覆盖。不得凭exit0、summary存在或非零成交任一项升级来源/比较资格。

## 8 下一实施刀 allowlist 草案与确认表

**实施后续（2026-09-30，Human「开 δ5 实施」）**：data-free implement 已落代码，待 PR 审查 / Human「合」；独立 [harness CLI](../../scripts/research/verify_delta5_real_volume_ingress.py)、[synthetic mapper/provider](../../backtest/research/delta5_volume_ingress.py)、[验收测试](../../tests/test_delta5_real_volume_ingress.py) 与 [双侧独立构造的完整 session 夹具](../../tests/fixtures/delta5_ingress.py)。GO 留于外部交接 `d5_impl_harness_20260929/HUMAN_GO.md`。CLI 要求显式 fixture JSON/hash、GO、rate（含 none/omitted）及 external parent/run-id，输出 `d5_ingress_v1`，不经共享 run/main、不读写共享分钟缓存。只接受 synthetic source；前文“本刀仅文档 / 未执行”保留为 #260 合同冻结的历史状态。

本次 data-free 覆盖：M1–M4、M6b、M7、M8、M10 的 N/H 完整原生状态对照；M5 的 START/END、三种显式时间编码、可得时间向上取整 N/H（买点 14:55），09:31/09:32 与 open570 门另以 L 验证；M6 为缺行 I + 原生 fallback 边界，**没有 harness 缺桶成功**；M9 仅旧 ride 组 L。M5/M6/M7/M11 的非法记录、覆盖缺口、输入 hash 漂移及输出隔离有 I/CLI 负例。真实 resolver 根/分区验收、真实来源认证/湖运行、v7 及完整 M5 09:31 买点 public E2E 均 **NOT_RUN**。每次 CLI 只报告其 fixture 的具名 N/H 子格，其余格与剩余子例明确 NOT_RUN；测试总覆盖与命令结果见外部 `D5_CODEX_RECEIPT.md`。`production_C=frozen`、`comparison_status=no_ssot_compare_authorization`；没有 SSOT green，也没有以改引擎求 PASS。

须另获具名 GO 后再确定路径：新 `scripts/research/verify_delta5_real_volume_ingress.py`（独立 harness，可内含provider）、必要的新独立映射模块、新 `tests/test_delta5_real_volume_ingress.py` 与synthetic fixtures、本页及外部receipt。
下一刀先完成 data-free 映射/拒绝/原生对照；真实源认证与湖运行还须具名源、宿主、配方和显式运行GO。不得凭本次D GO发车；遇既有行为冲突先报告差异，不修改引擎求PASS。
任何生产 opt-in 接线、共享 loader/parser、writer/schema、默认变化须**后续另份 GO**；δ6全权益/税务/补发、G5/G8、日线/全板块cap、vwap×walkdown、新策略与L2模型合并均不在本刀。

| classic 项 | 已有状态 / 权威 | 本次确认 |
|---|---|---|
| P1 | A，closed；[next plan §4](plan-industry-align-next-2026-09-19.md#4-p-human-cuts-p1-closed-as-a-2026-09-20) | **no re-open**；不新增竞价模型或14:57过滤 |
| P2 | B，delivered；书trades `session_phase` / `price_rule` 已交付，同上及 [fill-clock §5](plan-industry-align-refactor-2026-09-18.md) | **no re-open**；标签可空，旧schema/经济不变 |
| P4 | A，closed/delivered；[#135](https://github.com/baiyibing/MyQuant-backtrader/pull/135)，同上 | **no re-open**；touch与close/mark独立，不借源映射联动改估值 |

上述classic编号不是后续TopK P1–P4或#214 P1–P3。本刀完成标准仅为合同与窄指针可审查、文档/编码/allowlist检查通过；无生产改动、无湖执行、无SSOT绿灯。
