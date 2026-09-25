# MyQuant-backtrader 分钟引擎与三组策略审查

日期：2026-09-25。审查基线：/workspace/wt-bt-minute-review，HEAD 057761a41028540b60e7438afa157635d84c84ba。正文相对路径的 file:line 均指该 worktree 当前版本，历史文档内嵌的旧行号不作为当前代码依据。PR 评论依据用户提供的 context/ 离线副本；未访问或修改 GitHub。

结论：三组策略应为 version12、version11、version8.1/8.2/8.3 家族。存在可复现的价格域、资金时序及策略边界错误，当前分钟净值不宜直接作为策略优劣结论。最先修复的是 version12 混价域、全天卖款提前可用、version11 退出均线错域。多数人裁规则已经实现，但“已有测试通过”和“符合真实分钟交易”是两层不同证据。本报告列出 12 项正式发现；已批准的研究近似单独说明，未把它们冒充实施违约。

执行约束披露：本次未修改受版本管理代码，未执行 git commit/checkout/stash/reset/push、PR 或评论；没有下载市场数据。但一个并行审查进程误运行了会加载 tests/conftest.py 的 pytest。该文件 :13–18 无条件覆盖外部 basetemp，创建了 /workspace/wt-bt-minute-review/artifacts/pytest_tmp/run_3728488 下的测试空目录及四个 *current 符号链接。这违反了严格只读要求；发现后停止该方式，没有擅自删除。后续测试均加 --noconftest，临时目录及 Numba 缓存限定在 /tmp/codex-scratch/。不能用最终 git status 干净来宣称没有上述写入。正式交付文件只有本报告。

## 0. 三组策略、代码与时间证据

| 策略 | 身份与证据 | 当前主要代码 | 计划、交接与评审 |
|---|---|---|---|
| version12 / 12 / v12，金榕元 MA 减仓/买回书 | 2026-09-21 的 PR #151；原业务稿曾称“11”，后来明确把 11 留给 ma_chip。与独立 v7 不同。#158 同日改变分钟复权默认；#169/#170 于 09-23 修日线 D1。身份裁定见 plan-strategy12-jinrongyuan-2026-09-21.md:12、:78 | backtest/research/strategy12_rules.py；strategy12_engine.py；csv_strategy_books.py:648、:1458；csv_minute_backtest.py:717；csv_daily_backtest.py 的 run_daily_day hook | docs/backtest/plan-strategy12-jinrongyuan-2026-09-21.md；handoff-strategy12-codex-impl-2026-09-21.md §0；docs/architecture/reviews/2026-09-21/plan-strategy12-jinrongyuan/；pr-151-strategy12-jinrongyuan/grok-review.md；context/pr-151/158/169/170.md |
| version11 / ma_chip CSV port | 09-21 提交 e560a44（规则）、9133ca8（导出/volume A）、f5a0dd9（双引擎）、c9b4380（pandas 修正）；PR #152 07:39:01Z 合入。是旧静态策略档案的框架移植，未证明多头有效 | backtest/research/strategy11_rules.py；scripts/data/export_strategy11_pool.py；csv_strategy_books.py:984；csv_minute_backtest.py:773；csv_simulate_loop.py:519 | docs/backtest/plan-version11-machip-csv-2026-09-21.md；handoff-version11-codex-impl-2026-09-21.md；docs/architecture/reviews/2026-09-21/plan-version11-machip-csv/；pr-152-version11-machip-csv/；context/pr-152.md |
| version8_1 / version8_2 / version8_3，里程碑书家族 | b2b406e（2026-09-21）确实新增三份 rules 并注册双引擎，因此最符合“第三组策略”。它是三个配置/规则变体组成的一组，不应说只有一个新类 | backtest/research/strategy8_1_rules.py；strategy8_2_rules.py；strategy8_3_rules.py；csv_strategy_books.py:723、:752、:787、:1341 | 规则文件 HELP_LOCK；docs/backtest/research-backtest-entry.md；用户提供 git-log-0919-0923.txt、commit b2b406e 的只读历史 |

#156 的 fullstrat Q2/H2 是独立研究重放适配器，负责按实际成交价定股数、加订单时钟与滑点对照，没有注册为新策略书，故不计第三组。其决策完整列在第 4 节。ma_infra 也不是策略：#150 先合交接文档，实际代码由 #154（af6b812，09-21）合入。

范围区分：研究引擎定位是本仓向量化，LEBS/MockQMT 真栈属于 1.3；本次不建议引入这些交易包。backtest/research/engine.py:93–119 只是选择意图占位，run_dates 返回空 fills；其 fee 配置不能证明实际 csv_minute_backtest 已有相同费率。MyQuant 只涉及名单/信号可得性接口，不复审训练或重写 feeder。参见 docs/backtest/engine-positioning-ssot.md 与 plan-ashare-engine-refactor-2026-09-18.md:44。

## 1. 与行业分钟回测惯例的对齐

### 1.1 没有统一的“所有平台都是 next-open”规则

| 系统 | 官方文档描述 | 对本仓的实际启示 |
|---|---|---|
| Backtrader | 常规 Market 在下一根 bar open；当根已闭合 close 不能作为读完该 bar 后新订单的既有成交价。默认成交也不考虑 volume | next-open 是可用的保守对照，但预设 stop、限价、竞价必须另定规则。不能因同为 bar 模型就宣称同价/容量等价。[官方订单执行说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/) |
| vectorbt | from_signals 按传入价格/信号模拟；是否移位由调用者负责。官方特别提示 stop 与普通信号的先后和价格配置可能引入未来信息 | 向量化不自动保证因果；数组必须同时带信号可得时间、选价和资金处理顺序。[Portfolio API](https://vectorbt.dev/api/portfolio/base/)、[StopExitPrice 说明](https://vectorbt.dev/api/portfolio/enums/) |
| Zipline | VolumeShareSlippage 使用分钟 close，并按成交量占比的平方加入冲击；默认该模型 volume_limit=.025、price_impact=.1 | 使用 close 不自动等于错误，关键是订单已经可提交、bar 的完成时间及容量约束；默认参数也不是 A 股实证校准。[官方实现文档](https://zipline.ml4trading.io/appendix.html) |
| QMT | 官方内置回测说明：指定价在当前 K 线高低之间按指定价撮合，超出则按当前 close，超过可用数量按可用数量 | QMT 自身也是有明确简化的模型，不能把“与 QMT 类似”当作真实盘口成交证明；更不能把本仓与 1.3 MockQMT 真栈混称。[迅投回测说明](https://dict.thinktrader.net/innerApi/start_now.html) |
| 聚宽 | 官方 API 手册的分钟回测在每分钟第一秒执行，以前一分钟最后价格加滑点作为成交代理；也描述量比约束 | 区别“上根已知价”与“看完本根再倒填本根价”。该公开手册为历史版本，不能据此保证当前所有套餐/运行模式完全一样。[官方 API 手册](https://cdn.joinquant.com/help/img/JoinQuantAPI.pdf) |

公平比较应固定池、价格域、信号时钟、实际可卖股、现金顺序、费用、缺 bar 和公司行动，再比较订单级差异；不要求跨框架 NAV 强行一致。

### 1.2 本仓逐项口径

| 项目 | verified-in-code 现状与证据 | 评价及建议 |
|---|---|---|
| bar 标签与时区 | ashare_bars.py:362–379 按 epoch 的 UTC 钟面提取 hm，不做 +8h。历史湖探针明确是“中国钟点标为 UTC”，241 根/日并含 09:30、15:00：docs/architecture/reviews/2026-09-11/plan-strategy7-turtle-csv-minute-2026-09-11/codex.md:165 | 不应盲目补 +8h。可是钟面正确不等于证明 bar-open/bar-close 标签；数据帧不携带 label/available_at 合同。外部正常 UTC epoch 或不同供应商必须显式适配、拒绝混用 |
| 信号时刻 | 普通池使用文件名 T 当日；_buy_px 取 14:55 close；追买取 09:45 close。v11 是 D 后第一有效日 T、09:30 open；v12 MA 截止昨收，但触发还看当前 minute close | v11 D→T 因果链较明确。其它池的文件名本身不能证明 14:55 前已知；require-signal-bundle 默认关。不能一概断定所有池都有未来数据，也不能一概免责 |
| 止损/止盈选价 | csv_minute_backtest.py:328–336：open 已越止损线用该根 open；否则只有 close 越线才触发并以 close 成交。未使用 low，所谓 stop_loss:touch 实为 close-confirmed；峰值用当根 high。trail/MA 也多为同根 close | 应保持真实名称：它不是任意 low 触线即成交的 stop 模型。close 生成新意图又按该 close 无延迟成交属于乐观执行假设。建议与 #156 的因果 next-open、额外滑点分轴回放 |
| VWAP/滑点 | 生产普通分钟引擎没有 amount/volume 的 VWAP，也没有每笔价格冲击。#156 的滑点仅研究适配器 | 不得把 OHLC 平均称为 VWAP；要用成交额/股数并核单位。0/5/10/20bp 可作压力档，不能声称已校准默认 |
| 跨股票现金 | 普通路径按股票/lot 扫完全天，再 chase/pool/step；v7 按股票扫全天；v12 专门按 hm 再股票遍历 | 普通引擎资金可逆时使用，见 M02。v12 的逐 hm 编排应保留，但同 hm 的确定性资金优先级仍需记录 |
| T+1 | ashare_session.py:39–41 以买日 < 当前 session 判可卖；普通 lot 逐笔保护，v11 pending 次开；bonus 有独立 list_date 锁，见 csv_ledger.py:190 | 基本对齐 A 股库存约束；这不自动保证资金时序正确。股票卖款当日可用于再买是合理的，前提是已经卖出 |
| 涨跌停 | Decimal HALF_UP 到分，未知且名称未命中ST的代码/缺昨收交易拒绝；买达涨停跳过、卖达跌停延后。普通扫描还会因本根 open 跌停跳过整根。market_layer.py:57、:73；ashare_session.py:29、:34 | Decimal 正确；以触价代替排队是保守近似，不建盘口。ST 优先 5% 和无日期规则是 M06。IPO 无限制阶段/恢复上市没有事件建模，不能声称全 A 股制度完备 |
| 午休/竞价 | ashare_bars.py:308–331 接受 [09:30,11:30] 与 [13:00,15:00]，不接受 09:25。closing_call 只是标签，14:57–15:00 未建竞价撮合 | 交易所连续竞价止于14:57；09:15–09:25为开盘集合竞价，14:57–15:00为收盘集合竞价。[上交所交易时间](https://one.sse.com.cn/onething/gptz/)。P1=A 明确保留现近似；可做竞价敏感性，不能把15:00估值同步删除 |
| 整手 | csv_ledger.py:223–233 全市场 floor100，预算不足仍补100；cap 买入也是 floor100 | 主板整手近似基本可用，科创板最低200且其后可加1股不对齐，见M07。卖零股和实际部分成交不应简单等同于新买整手 |
| 停牌/零量 | minute loader 仅丢整日 sum(volume)==0，普通路径随后丢 volume 列；日内零量分钟仍可成交，缺volume也允许。v11例外强制保留volume且开盘需>0，ashare_bars.py:350、:381–385 | 是 E-R4 已裁定的日级停牌近似，不是完整临停/逐分钟流动性检查。cap 默认关闭；大额结果不能当作容量验收 |
| 费用 | 默认双边10bp、min0。当前分钟 CLI 已有 --qlib-cost，买5bp/卖15bp/min5；csv_minute_backtest.py:684、:1303。每个 _sell 调用收费，v7 聚合 _sell_lots 一次收费 | 这是研究代理成本，不是券商逐项账单。普通 A 股佣金最低5有监管规则依据；2023-08-28起卖方印花税为0.05%，过户费自2022-04-29起按成交金额0.01‰双向。不能在现代理费之上随意再叠一行税，需新费用口径及日期表。[佣金规则](https://www.csrc.gov.cn/csrc/c100024/c1492350/1492350/files/928bdd362fa24b79bdadb0072d67acee.pdf)、[印花税公告](https://shanghai.chinatax.gov.cn/zcfw/zcfgk/yhs/202308/t468451.html)、[券商执行中国结算过户费通知](https://www.xcsc.com/main/a/20220429/1022871784.shtml) |
| 复权/公司行动 | raw分钟是默认；v12日线front固定，v11导出front而执行日线raw；E-R6一般只缩放cost/peak/昨收；经济权益仅显式 API 打开 | 分离信号/成交职责是正确方向，但连接不完整，见M01/M03/M09。forward-adjusted历史必须与探测价同域；raw NAV要记分红/送转；不得同时靠复权收益和现金红利双计 |
| 现金/估值 | 主书买扣notional+fee、卖加notional-fee；NAV=现金+股数×日线mark+已确认应收；无当日K用前收、完全无历史才用cost；末日EOD_MARK不是真卖。v7不同：用最后可见minute close，缺值才用avg_cost，且无EOD_MARK（csv_minute_backtest_v7.py:397、:487、:493） | 算术链清晰；mark和成交资格独立是正确选择。v12传错mark域例外是M01。期末没有实际平仓成本，需区分浮动收益和可变现净额 |
| 缺分钟 | 普通14:55缺根取14:30–14:55最后close；09:45缺取早盘最后close。v7缺精确14:55不买；v11缺09:30不借后根；分钟held还要求当日日线，csv_minute_backtest.py:734 | 属不同书合同，不能统一修成任意ffill。旧报价回填成交及缺bar漏卖应单独计数；公司行动不能因没有行情就当不存在，见M09 |
| 交易日/EOD | 主书日历来自日线并集，非独立交易所日历；v7 CLI传指数日历。主书日末按日线估值、保存pending；v7按最后可见分钟价估值；两者末日均不强平 | 同时缺全部日线会缩短会话/持有天数；应报告覆盖率。v7 API默认日历还有可复现输入格式错误，见M10 |
| 数据读取/缓存 | 路径经resolver；lake只读单一data.parquet，排序去重keep last；旧缓存仅start/end；qlib_1min缺open/high会用close替代，缺low适配时用high | 单文件/重复行处理为既有人裁；不能把compact旧输出当唯一正确答案。字段降级必须披露，不能宣称OHLC同等质量。缓存源身份问题见M08 |

2026 年制度不能用早年常识替代：2026-07-06 起沪深主板风险警示股票由 5% 改为 10%，创业板/科创板风险警示仍为20%；应按回放日期查规则，而不是把整个历史一律换成最新值。[深交所2026交易规则第3.3.13及生效条款](https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf)、[上交所修订发布说明](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml)

## 2. 业务契约兑现与正式发现

### 2.1 已兑现的主要要求

version12：实际卖出量写回双记忆；MA10 止损优先；仅 T+1 可卖股参加减仓；step 优先、lot0 最后并保100；周期 latch、residual=2、同日再减/再买回；池/chase 成功买入清双记忆，steps 不倒退；不继承 v8 涨停保留/旧止盈。#169/#170 的“锁定日线信号时可卖 lot、次开 clamp 并重新保 lot0”已修复，不再列为当前分钟缺陷。

交付状态更正：策略12分钟五本 Slice D 已于09-22执行并由 #165 回填回执，不能沿用旧 handoff:71 的“尚未执行”。当前证据为 docs/backtest/reviews/slice-d-minute-five-book-20260922c-2026-09-22.md:10、:31，tip为6aeffef，窗20251023–20260909，分钟none。记录的v12收益−7.69%、8.3收益+7.21%只是历史结果，不是本次重跑或修复后收益；本次未访问凭据所指底层产物，也不据此排策略优劣。#165明确不主张parity或生产验收。

version11：四项信号与 CYQK>.70 的边缘条件、200窗Rust CYQK、显式周线prefix、D后首根有效日K且≤4自然日、日线T收盘/分钟09:30开盘、EOD阴阳→HOLD两段FSM、无追买、卖出日不重入、lake volume强制保留均有代码和测试支持。Slice D 的跳过是明确后续人裁，不是实施者私自省略；因此保留“框架验证，收益/parity未验证”。

8.1/8.2/8.3：各自里程碑与 sizing 已注册，不把 #156 算第四本书。8.1 实际仍继承 daily_quota；8.2/8.3 是 per_name。docs/backtest/research-backtest-entry.md:85 将这组概括为 per_name 不够精确，使用时以 csv_strategy_books.py:1341 及各书 apply 为准，建议顺带修文案，不把这处文案偏差扩大成核心算法错误。

### M01 — critical — verified-in-code：version12 默认混价域，信号、涨跌停与NAV均会错

引用：backtest/research/csv_minute_backtest.py:1108、:1122、:1182、:990；backtest/research/strategy12_engine.py:128、:228、:254；backtest/research/strategy12_rules.py:79、:125；backtest/research/csv_simulate_loop.py:564、:571。

描述：run() 强制 daily/front，又用 minute/none 成交；同一 front daily 同时被当作 raw 昨收计算涨跌停、与 raw 当前价比 MA、传入日末 mark。#151/#158 只批准分开信号和成交域、禁止静默双调，未批准将两种价格单位直接混算。关闭 exdiv_map 并不能修好这些单位。

实测：现金100000、每笔10000、raw分钟14:55恒10。daily同域10时买1000股、NAV99990；front日线9.6时仍买1000@10，却mark9.6，NAV99590，平白少400元；front日线5时把raw10与错误涨停5.5比较，整笔跳过。raw当前9.8、raw历史10本应MA5减500股；将同一历史写成front9.6，反而无减仓。

影响：不只是分红日误差，复权基准覆盖的历史区间内都可改变选票、减仓、止损、现金和回撤。现有 none/front 路由测试采用两域同价，无法发现它。

建议：独立传递 signal_front、execution_raw、mark_raw；将探测价或MA显式换到同一当日价域，涨跌停使用官方raw参考价，真实股数用raw估值，显式权益单独入账。用非1复权因子、送转、现金分红及复权锚变更回放证明不误买卖且账户守恒。

### M02 — major — verified-in-code：全天卖出先结算，未来卖款可支付过去买单

引用：backtest/research/csv_minute_backtest.py:731、:769、:800、:852、:888、:934；backtest/research/csv_ledger.py:390；backtest/research/csv_minute_backtest_v7.py:371、:392。version12 的专门 hm 循环不适用本项同一结论。

描述：普通主书先遍历所有持仓并扫描整天，找到当日任意时刻卖点就立即加现金，然后才执行09:45 chase和14:55 pool。这是资金可得性的前视，不能由T+1已正确实施来抵消。

内存回放：9月2日1001元买A100股@10，含费后现金0。9月3日A09:30仍10，14:59 close9.4触发显式5% stop；B在14:55报价6、候选买100股。实际记录先 SELL A@9.4，再 BUY B@6，余现金338.46。14:55实际现金应仍为0，B不应成交。此例用受支持 stop_pct=.05 隔离问题；原理也适用于任何买时钟之后发生的止盈/止损。

影响：现金紧张、追买、多股票共享资金时虚增可成交订单，扭曲选股顺序与资金利用率。v7按股票扫全天也没有全市场统一时间排序，不能仅凭其单股循环证明跨股票因果。

建议：在现有研究引擎内先形成带成交时刻的候选，再按时间/稳定优先级推进共享现金与容量；或明确定义并回放当时已可用资金。无需引入LEBS或live订单总线。检验“每笔买入前现金足够，且仅包含此前卖款”，并对同刻资金争用固定规则。

### M03 — major — verified-in-code：version11 的 EOD SMA5 仍是 raw，除权制造假破位

引用：backtest/research/csv_minute_backtest.py:1054、:1108、:1115、:988；backtest/research/csv_simulate_loop.py:535；backtest/research/strategy11_rules.py:102。合同：docs/backtest/plan-version11-machip-csv-2026-09-21.md:30；docs/architecture/reviews/2026-09-21/plan-version11-machip-csv/merge-consensus.md:12。

描述：导出买信号用front，但运行EOD退出只映射一个 previous，整个 closes 仍为raw。正确传入 exdiv k 也不能消除SMA窗口断点。

实测：T买10.2、收10.5进入HOLD；次日10%除权、raw收9.45并传k=.9，得到 pending_exit=ma_signal:SMA5，raw SMA5=9.99。相同经济路径的front窗口[9,9,9,9.45,9.45]没有卖信号。

影响：错误次日卖出，改变持有期、费用、再入场；共享EOD的日线亦受影响。建议：仅为v11补独立front卖出信号序列或完整窗口换域；保持raw成交、raw档位、raw估值，不顺带改v4已冻结的raw门。

### M04 — major — verified-in-code：8.3 首笔涨停追买绕过50%试探预算

引用：backtest/research/csv_simulate_loop.py:275、:312、:317、:330、:208；backtest/research/strategy8_3_rules.py:45、:95。

描述：队列在调用 name_lot_budget 之前保存 per；首笔涨停时保存默认100万，次日追买直接用此额度，不再执行半仓函数。循环内 per 又会被前面的普通票修改，所以同一涨停票的额度还可能依赖名单中前一票。

实测：首票涨停后pending存1000000；次日open10.9、09:45 close11，追买90900股、名义999900、佣金999.9；按50万试探约应45400股。

影响：首仓近乎翻倍，风险与后续加仓序列不符合8.3。建议：为每个候选独立计算预算，在入队前冻结该股票正确的首笔/加仓额度；明确后续状态变化是否重算。回放首票、后票及队列等待期间已有持仓三类情况。

### M05 — major — verified-in-code：8.1 的精确+60%峰值会被浮点误分到更高止盈档

引用：backtest/research/strategy8_1_rules.py:32、:41、:89。

描述：用 peak/cost-1 的float直接与.60作右闭区间比较。cost10、peak16在二进制中得到0.6000000000000001，被分到>60%的档。

实测：当前14，本应属于(40%,60%]，地板+30%=13，不卖；实际错误采用+50%地板并触发卖出。

影响：边界触发过早止盈，改变后续峰值与持仓，不是可忽略的金额尾差。建议：在价格域比较峰值与成本×倍率，或给业务边界制定统一精度；对各精确阈值及上下一个tick回放，保留原数学区间，不修改策略定义来迁就float。

### M06 — major — verified-in-code：ST固定5%且不接日期，与板块及2026规则不符

引用：backtest/research/market_layer.py:43、:57、:63；backtest/research/csv_common.py:73；backtest/research/ashare_session.py:63。既有选择：docs/backtest/engine-ashare-correctness.md:121。

描述：名称先命中ST就返回5%，覆盖创业板/科创板/北交所板块；函数没有session或上市阶段参数；名称ST还会先于未知板块检查命中，未知代码带ST名并非fail-closed。2026-07-06后的主板ST也仍5%。例如昨收10，现值10.6被代码当作超过涨停10.5，但在10%/20%板块仍可能正常交易。

影响：错误拒买、错误延后卖出，且回放窗口跨制度生效日也不能正确切换。缺IPO例外还会错误限制上市前几日。ST名称的PIT问题是另一层：v7默认窗末平铺名字，延长结束日期可能改变早期结果，asof选项仅修日期继承，不能修档位本身。

建议：维护只消费的按证券/板块/生效日期/上市事件查询规则，优先官方历史上下限；已知ST板块不被统一5%覆盖，未知信息明确失败。保存旧模型标签，重放2026-07-06前后与创业板ST案例。[深交所2026规则](https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf)、[创业板风险警示20%原规则](https://www.szse.cn/disclosure/notice/general/t20200710_579459.html)

### M07 — major — verified-in-code：统一100股允许科创板非法首买

引用：backtest/research/csv_ledger.py:223、:229、:259；backtest/research/ashare_volume_cap.py:83；backtest/research/csv_minute_backtest_v7.py:227、:231；backtest/research/market_layer.py:18。

描述：市场层承认688/689为可交易20%板块，账本却没有按板块选择最小申报量。_buy_size(1000,10)返回100，资金足够就能为688代码建100股首仓。

影响：科创板最低200的新买约束被突破，且超过200时可按1股递增的真实规则也被整百近似；小预算、高价股、部分容量裁剪尤其明显。v11 exporter排除688不代表通用引擎或其它池排除。

建议：把最小申报数量/增量/零股卖出作为共享证券规则输入；区分申报整手与允许的部分成交，不能把全部卖量强行整百。补主板100、科创200/201、不足200及零股全卖回放。[上交所科创板数量规则](https://edu.sse.com.cn/tib/qa/c/4866268.shtml)

### M08 — major — verified-in-code：缓存命中不验证湖来源或数据版本

引用：backtest/research/ashare_bars.py:416、:491、:584、:587、:590；backtest/research/csv_minute_backtest.py:1152。已知边界：docs/backtest/plan-ashare-engine-refactor-2026-09-18.md:191。

描述：缓存文件名只有minute_none_start_end；完整命中所需代码后，不访问新lake_root，也不验证源分区内容、mtime、schema或覆盖天数。JSON元数据只记录起止/行数/创建时间，读取未校验它。相同代码换配置湖或湖修补，仍可直接使用旧行情。

影响：指定权威湖变化后回测结果可能不变，也可能混合旧已缓存股票与新补入股票；命中不能证明数据完整/最新。不是要求每次全量hash，而是不能把时间窗当作数据身份。

建议：缓存键/manifest绑定resolver解析的源身份、价格域、schema/volume合同及分区版本或可信指纹；命中检查覆盖率，失配拒绝或重建。front及v11目前绕过该缓存是正确保护，应保留。

### M09 — major — verified-in-code：默认raw账户无公司行动权益；普通主书/v7开启后仍可能因缺ex-day bar永久漏账（已公开的人裁限制）

引用：backtest/research/csv_minute_backtest.py:618、:695、:734、:742；backtest/research/csv_ledger.py:154、:166；backtest/research/ashare_exdiv_economics.py:92、:103；backtest/research/csv_minute_backtest_v7.py:373、:381。范围依据：docs/backtest/engine-ashare-correctness.md:260、:286。

描述：普通CLI不提供economic lookup，E-R6只改参考cost/peak，不加送转股或现金红利。普通主书及v7即便API显式提供事件，持仓也必须通过当日bar门才登记；缺分钟/停牌时跳过，随后按日期查询也不会补发。v12在行情检查前调用_prepare_day（strategy12_engine.py:118、:217），不能套用同一缺bar漏账结论；其标准CLI默认没有economic lookup则仍成立。文档明确保留该限制，所以本项是结果用途风险，不是声称实现违反δ6人裁。

实测：1001元买100@10，除息0.1、正确显式事件与k=.99，最后raw9.9。ex日有分钟：cash10、cost9.9、NAV1000；只删ex日分钟、仍有daily及后续minute：cash0、cost10、事件计数0、NAV990。收益差来自漏权益，非市场价格变化。

影响：长窗或高分红池的NAV不是总回报；开关on也不是充分保证。建议：按持仓和独立事件日历登记权益，不依赖是否有成交bar；交易资格仍需行情。没有事件数据时显著报告经济不完整，不能由k倒推现金/送股。按现有三仓分工只消费明确信息，不新增下载。

### M10 — major — verified-in-code：v7 默认日历对DataFrame输入只保留名单日

引用：backtest/research/csv_minute_backtest_v7.py:333、:334、:343、:350；CLI规避点 :660、:664。

描述：frame路径把minutes设为{}，未给index_days时却以set(minutes)|set(pools)构造日历，frame自身交易日被丢掉。公开simulate_v7参数允许省略index_days。

实测：9月1日14:55买100、9月2日09:30跌至89，D1昨收98使89尚未跌停；相同数据作为records得到2个权益点并在D2止损，改为DataFrame只得到D1一个权益点、仍持仓。

影响：公开API/研究调用随输入表示改变结果，漏止损、计时退出与估值。标准非空池CLI传指数日历，不能把这个API缺陷扩大为所有CLI必然出错。建议：要求显式市场日历，或从frame规范日期并集构建一致fallback；两种输入形式做同一回放对照。

### M11 — minor — verified-in-code：version11运行只预热10自然日，MA不足静默当作不卖

引用：backtest/research/csv_common.py:18；backtest/research/csv_minute_backtest.py:1090；backtest/research/csv_daily_loader.py:37、:82；backtest/research/strategy11_rules.py:92、:105。

描述：长假/个股停牌可使预载不足4个prior close。SMA5为None时没有明确warmup诊断，直接HOLD。导出器200根预热和执行侧加载是两个独立过程。

实测：复用tests/test_strategy11_engine.py内存fixture，T买9.4；完整历史得ma_signal:SMA5，只留1根prior时pending为空，成交相同。影响集中于起始窗口。建议：按有效bar数保证历史，缺足够数据时明确报错/skip计数，不用固定自然日猜测。

### M12 — minor — verified-in-code；预期加速 inferred：Numba开关不加速实际三组书，Python重复准备显著

引用：backtest/research/csv_minute_backtest.py:447、:455、:456、:560、:765、:820；backtest/research/strategy12_engine.py:232、:243、:253、:284；backtest/research/strategy12_rules.py:70、:125。

描述：通用simulate每lot传reserve_state，8.x还有take_profit callback；v12有exit_plan，均不满足当前Numba offload条件。v12每码每分钟又新建四个长度1数组/lambda，重复计算日内不变的昨收MA及memory查找。v11开盘专用分支前也准备了不用的整日o/h/c/hm。

影响：将CSV_SCAN_HELD_DAY_BACKEND设为numba不会得到预期加速；大名单、多lot成本按分钟和lot重复增长。建议及测量见第3节，先去重复准备，再为明确支持的书编译状态机，不静默改默认成交规则。

## 3. 性能：实测、热点和可验证优化

### 3.1 便宜基准结果

使用指定 /home/box/.venvs/bt-ci/bin/python，PYTHONDONTWRITEBYTECODE=1，NUMBA_CACHE_DIR=/tmp/codex-scratch/numba-root。没有读取真实湖。脚本 scripts/research/bench_minute_simulate_hotpath.py；30交易日×16代码×240分钟，前10个买日、多lot，热身1次、计时3次。累计计时/剖析远低于10分钟。

| 请求后端 | 实际后端 | 平均simulate | sell scan | pool buy | mark | 其余编排 |
|---|---|---:|---:|---:|---:|---:|
| 默认python | Python | 1265.63ms | 53.05% | 5.99% | 1.16% | 39.79% |
| numba环境开关 | Python | 1235.40ms | 53.01% | 6.17% | 0.91% | 39.90% |

两次都得到160个活lot、160笔BUY、含EOD_MARK共320行。约2.4%的耗时差不能解释为Numba收益，实际根本没有offload。day slice约3.3%、previous rows约8.3%是嵌套测量，不能再和上表相加。09-15旧文档的scan约75%是旧环境/旧版本测量，本次复测约53%，不能不加说明沿用旧占比。

另一次cProfile：约572万调用、3.289s（含profile开销），3760次scan累计1.939s，_pool_quote_for .553s，run_step_adds_day .414s，_buy_px .293s，_previous_rows .217s；reserve_step_minute与peak_gap_blocks各902400次。主循环已用numpy数组，不是每根分钟都pandas.iterrows；pandas成本主要集中在每码每天切片、历史列表、重复报价。

v12独立小夹具：4代码×30日×240根，固定价、首日买入、cap关；plain 0.4404s。cProfile 1.325s中scan包装27840次/.689s，_ma 55680次/.197s，memory_for 55824次/.125s，后端探测27840次/.097s，buybacks7200次/.140s。该数不能与上表不同场景直接比谁更快。

### 3.2 建议优化顺序（均未实施）

| 优先级 | 修改位置与方法 | 预期收益（inferred，非承诺） | 正确性风险/验收 |
|---|---|---|---|
| 1 | 每code/day缓存昨收、必要尾窗、limits、09:30/09:45/14:55报价和hm索引；_previous_rows不用整段mask+astype+tolist重复生成；backtest/research/csv_minute_backtest.py:560、:855、:906 | 当前基准准备约8%且报价还有重复；纯simulate约5–20%改善可检验，不能承诺数量级 | 缓存键含价格域、exdiv日和源版本；精确缺根fallback与重复时间戳规则必须一致 |
| 2 | v12预计算MA5/10和memory引用，直接标量状态转移；只在pool/chase实际时钟执行相关helpers，只扫有余额的买回记忆 | 小型v12纯模拟可能1.5–3x；需实测，I/O重任务会稀释 | 保留hm顺序、MA10优先、实际partial量、周期解锁、T+1、同刻共享现金；不能把路径依赖状态机简单变成全列信号 |
| 3 | v7把_day_frame_records的全窗mask改为day spans/array view，避免逐日to_dict；v11在minute_open分支前避免无用数组与全部历史list | v7长窗减少重复O(日数×全窗行数)过滤；v11改善准备成本，整机倍数未知 | frame/record日历先修M10；排序、日期、缺bar和last price完全可回放 |
| 4 | 受支持8.x状态机独立Numba/Rust kernel，显式输入数值规则和reserve状态；输出填单候选，再由正确时间顺序记账 | 若仅把53%扫描加速10x，Amdahl上限约1.91x整体；单扫描可能更高 | callback、partial、跨日peak_hm、涨停保留、force/EOD分支不得丢。先保Python参考，回放reason/时刻/股数/现金，不只比NAV |
| 5 | Parquet predicate pushdown，读前用row-group time/symbol统计；当前backtest/research/ashare_bars.py:354先整表读再filter；cache读取:533也先解压每组再筛symbol | I/O改善取决于行组布局和窗口占比，本次无湖不量化 | 不改变单data.parquet合同；缓存须先修M08，加入domain/schema/volume/分区版本。不能丢volume换速度 |
| 6 | v11股本历史按symbol索引一次；exporter读front时投影必要列并下推日期；Rust CYQK保留 | 全市场可减少反复扫描股本总表；真实pyd/湖未运行，收益未知 | backward-asof、缺值传播、200窗及grid gate不变；不重写MyQuant winner_ratio feeder |

Decimal不是当前主要逐bar热点：limits通常在code/day或交易尝试计算，volume rate在构造时转整数比。优先缓存同一档位而非把HALF_UP换成float round。对价格档边界（M05）反而需要更明确精度。

回放验收建议：冻结池、raw/front数据及因子指纹；保留实际信号可得时刻、成交候选时刻、股数、fee、现金前后、可卖库存及book_state摘要。先比较事件序列和守恒，再比NAV。允许浮点尾差/字节不同，但不允许同bar先后、漏公司行动、容量超用或资金逆时。策略12现SELL未传hm，csv_ledger.py:392不能填session_phase；既有trades只有date，建议在复核产物中补足分钟时刻，单靠reason和日总收益不足以验收上述优化。

## 4. 实施人裁、共识与默认选择总账

本节把“人明确选了什么”“评审建议被交接吸收”“代码自身默认”分开。A/B/C在不同计划里含义不同，不跨表套用。重复评论合并为一个语义决定，保留对应全部P/S/V/C编号；历史选择被后续覆盖时同时列出，不能拿旧plan推翻新handoff或PR评论。未见原文的收益背书不作推断。

### 4.1 核心引擎和行业对齐的人裁

以下每行同时说明问题、选择、结果影响与建议。代码证据已在第1–3节；裁定来源行号列在表中。

| 裁点/来源 | 大白话问题、已选 | 对结果的影响 | 判断/建议 |
|---|---|---|---|
| 引擎重构P1=A；plan-ashare-engine-refactor-2026-09-18.md:153 | 是否一次合并所有引擎？先统一T+1/涨跌停/读取，保留书账本和v7账本 | 两路径费用粒度、lot表达仍可不同 | 保留分工；统一谓词不等于全部行为相同 |
| 重构P2=A；同上:154 | 是否立即按券商完整费用？默认旧10bp，未来显式开关另计划 | 现默认不是印花/过户/最低5全账单 | 保留旧结果基线；真实收益研究单独校准且勿双扣 |
| 重构P3=C；同上:155 | 是否这次加送转/红利/ST PIT？全部后置 | 旧raw净值残留继续存在 | 后续δ6仅部分解除；分钟主研究用途应优先补M09 |
| 重构P4=A；同上:156 | 是否限制成交量？首船不做 | 大资金仍可理想成交 | 后续δ5仅API opt-in，CLI默认风险仍应披露 |
| 重构P5=A；同上:157 | 要不要换统一新命令？旧CLI保留真身/HELP_LOCK | 入口兼容，防参数意义漂移 | 保留，不复活Cerebro/LEBS |
| 切片A补裁；同上:13、:191 | 书帧与旧compact不同怎么办？七类fixture变化接受，新书帧为结果；读取器不改 | 盘外/零量/重复/分片等差异是预期迁移 | 保留明确边界；其它差异不能用“全绿”豁免 |
| E-R1；engine-ashare-correctness.md:120 | 只有止损要避跌停吗？所有卖因都避 | trail/MA/force均可延后 | 保留方向门，但这不是排队模型 |
| E-R2；同上:121 | 板块怎么定？代码前缀10/20/30、ST优先5、未知拒绝 | 明确失败优于未知默认10；ST现规则错 | 未知拒绝保留；档位和日期改M06 |
| E-R3；同上:122 | 1分钱边界怎么舍入？Decimal HALF_UP | 1.65的10%跌停为1.49 | 保留，优化不能换银行家round |
| E-R4；同上:123 | 停牌、无K、追买怎么处理？零量日当无K、旧close估值、追买保pending到有K再判一次 | 不虚构当日成交；也可能把“次日追”延到以后 | 保留已选语义并报告等待天数；日内临停另建显式资格 |
| E-R5/E-R6；同上:124–125 | 除权修什么？先修参考价，不靠k改股或造红利 | 修部分假止损，不修总回报 | 原数字只能按参考修正模型解释；保留显式权益独立职责 |
| E-R5重开条件；同上:129 | 什么时候必须再审残留？止损<10%、高分红池、分钟成为主面、NAV差<1% | 当前分钟专项及精细MA风险管理已符合再审动机 | 建议优先推进域/经济闭合，不拿旧延期当收益保证 |
| fill-clock P1=A；plan-industry-align-next-2026-09-19.md:83 | 14:57–15:00要禁成交吗？保持扫描行为，只命名、不模拟真竞价 | 尾盘仍可能理想bar成交 | 保留历史基线，另做竞价/延迟敏感性 |
| P2：旧A→B；同上:84 | 要不要在trades加时段/取价标签？后续选B追加两列，未命名留空，v7不改 | 只增强部分审计，不改善经济/时序 | 保留；新增书应补足可回放分钟时刻 |
| P3=A；同上:85 | 费用/ST等在本命名票顺带改吗？否，分δ裁 | 本票不授权真实交易模型重构 | 保留清晰范围，不误读成永久拒绝修复 |
| P4=A正式关闭；同上:86 | 不许盘中触价是否也删15:00估值？两者独立、都保持现状 | EOD官方close可以用于估值，即使未来收窄成交 | 保留，估值与可成交性不可绑定 |
| δ1 P3.1=A；plan-industry-align-p3-fees-2026-09-19.md:127 | 默认费用是否切5/15bp+min5？仍双边10bp/min0 | 小额与高换手结果成本不同 | 保留命名基线，报告实际schedule |
| δ1 P3.2=A；同上:128 | 是否另记印花税行？仅说明边界，不新增 | 不会重复加代理成本 | 保留；若完整成本另定义明细和日期 |
| δ1 P3.3=A；同上:129 | 能否import live费率模块？严格fence | 研究不长成交易栈 | 保留，复制口径也要有单一SSOT |
| δ2.1=A；plan-industry-align-p3-d2-exdiv-2026-09-19.md:154 | 哪些日当除权？事件表∪严格>1%因子跳变兜底 | 缺事件索引仍可能推断事件，非完整PIT认证 | 保留可复现实验；正式总回报要显式事件 |
| δ2.2=A；同上:155 | k作用范围？Fprev/FD，仅既有参考价，无补发/幂等扩展 | 无bar错过事件不会后来修，重复helper会重复乘 | 建议在新经济/参考事件层修M09，不改k成股数比例 |
| δ2.3=A→δ6 C；同上:156 | 送转红利先不做？当时保留残留，后续仅显式lookup支持 | 默认仍不增加权益 | 保留历史沿革，on/off结果必须标明 |
| δ2.4=A；同上:157 | ≤0.5%小额跳变要不要忽略？保留噪声带 | 小额现金分红可能不修参考，低价边界可能差1分 | 收紧止损/比较微小收益时建议重裁，不把阈值叫市场规则 |
| δ2.5=A；同上:158 | 是否统一所有数据源的复权接线？保持daily连续域跳过，minute/v7旧分叉 | qlib_day与raw minute混域仍危险 | 建议明确price-domain元数据并拒混域；不以数据源名称代替认证 |
| δ3.1=A；plan-industry-align-p3-d3-st-pit-2026-09-19.md:95 | 是否立即把v7改PIT名称？当时只记录/钉测试 | 默认窗末名仍可能改早期档位 | 新研究优先用asof，但它仍不是available_at完整PIT |
| δ3.2=A；同上:96 | 名单日期是否证明名称盘中已知？明确未证 | 防“asof就无前视”的误述 | 保留声明，补源时间证据 |
| δ3.3=A；同上:97 | 缺名/初态怎么补？保持非空继承和窗内输入 | 起始窗缺旧ST名仍可能按普通股 | 建议只消费可靠前置快照，不能猜ST |
| δ4.1=C；plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md:94 | v7未知档位只写文档还是改行为？批准生产修复 | 覆盖旧held fail-open | 保留 |
| δ4.2=B；同上:95 | limits=None能不能试买卖？首开及held stop/add/timer均拒绝，无policy开关 | 少了无参考的假成交 | 保留；不能把None当IPO合法无限制 |
| δ4.3=A；同上:96 | 新增报表列吗？复用现有skip/counter | 输出兼容，诊断粒度有限 | 保留，必要细审可另输出manifest |
| δ5.1：B→C；plan-industry-align-p3-d5-volume-cap-2026-09-19.md:110 | 容量仅设计还是接生产？后来授权API opt-in | 默认None仍不查量，日线/CLI未接 | 保留明确开关，不能宣称默认有容量 |
| δ5.2=A；同上:111 | 开盘能否用整分钟量？只可用completed及available_at，不借未来/EOD量 | gap-open被拒；v11 bucket570/at569开cap必无新买 | 因果保守，保留合同并显著提示不可用组合；如改需独立成交模型 |
| δ5.3=A；同上:112 | 多笔订单是否各有一份容量？同桶双向共享，允许partial，关联退出原子 | 不超额反复用量；先处理lot得优先权 | 保留共享预算，修M02后确保真实时间次序 |
| δ5.4=A；同上:113 | 无量/错单位可当无限吗？拒绝并诊断，0是有效零容量 | 避免缺失数据伪造可交易 | 保留；源单位需调用方认证 |
| δ6.1：旧A→C；plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md:57 | 是否实现经济权益？显式生产增股/入账/NAV | 只on时进入完整一部分经济账 | 保留，但缺bar保留限制见M09 |
| δ6.2=A；同上:58 | 能从k猜红利和送股吗？只收显式ExDivEvent | 不会把不同公司行动混成同一比例 | 保留 |
| δ6.3=B；同上:59 | 什么时候确认和到账？ex日股份/应收、pay日转现金 | pay前应收进NAV，不能提前用于买入 | 保留；独立事件资格不应依赖bar |
| δ6.4=B；同上:60 | 送股零碎怎么办？按每lot floor，余数舍弃 | 不同lot拆分可有碎股价值差 | 批准近似应披露；不要求这种夹具精确守恒 |
| δ6.5=A；同上:61 | 公司行动算交易吗？不写BUY/SELL、不扣佣金、不耗量，stats诊断 | 不虚增换手或双计收益 | 保留；审计可单列权益流水 |


### 4.2 策略12：全部P/S、人裁与实现修复

证据简写（均为本 worktree 文件，行号为当前版本）：**P**=`docs/backtest/plan-strategy12-jinrongyuan-2026-09-21.md`；**H**=`docs/backtest/handoff-strategy12-codex-impl-2026-09-21.md`；**S**=`docs/architecture/reviews/2026-09-21/plan-strategy12-jinrongyuan/merge-consensus.md`。P:3 记录 P2–P13 全按共识及四个二选一由主持按评审倾向定案；H:9、H:11 的后续直接人裁覆盖 P 表旧措辞；H:63–68 覆盖最初全 front 契约。PR #169/#170 没有追加用户问答，下面标作实现修复，不伪称额外人裁。

| 决策及证据 | 大白话问题 | 当时选择 | 对回测结果的具体影响 | 判断与建议 |
|---|---|---|---|---|
| P1/R7；P:12、P:78 | 新书是否占用 ma_chip 编号 | 金榕元新书叫 version12，别名 12/v12；11 留给 ma_chip | 防止同一编号加载不同规则 | 保留，策略身份清晰 |
| P2/S8/R3；P:67、P:79；H:29；S:19 | 均线算到什么时候，分钟什么时候卖 | 仅昨收 MA；逐分钟 close 判、当根 close 成交；日线收盘判次开卖 | 不把今日收盘放入盘中 MA；但假设可按已观察到的 close 成交 | 昨收符合 PIT；当根 close 是已批准理想模型，保留历史口径并补下一可成交 bar 敏感性 |
| P3；P:80；H:16 | 50% 是总仓位一半还是可卖仓位一半 | T+1 可卖 lot 合计，含 step，扣 locked bonus，floor100 | 大量当日新仓时实际减仓远少于总仓位一半 | 符合 T+1，保留；结果报告分母 |
| P3/S7/S17；H:15；S:18、S:28 | 多笔持仓先卖谁 | step 优先，中间 lot_id 升序，lot0 最后 | 留住台阶锚，部分卖的成本归属取决于 lot 顺序 | 保留业务顺序；不是全部 lot FIFO |
| P4；P:81；H:18 | 买回按钱还是按卖掉的股数 | 对应通道记忆股数上限、整百买回，现金不足 skip_cash | 股价涨后买回需要更多现金，可能长期未买满 | 符合买回股份目标，保留 |
| P4；P:81 | 减仓买回最多循环几次 | 无次数限制 | 盘中反复穿线可高换手 | 属主动业务选择，保留并做成本/容量敏感性 |
| P5；P:82；H:61 | 止损和减仓同时触发谁先 | MA10×0.90 止损优先，清理全部可卖股；再考虑 MA5 | 不会先减半再漏掉剩余止损；T+0/锁定股仍不能卖 | 保留，文档整仓不能覆盖 T+1 |
| P5/S19；P:82；S:30 | 止损是否作废原减仓记忆 | reduced/stopped 并存，各买各的，同日先卖后买 | 同一时点可有两笔买回，增加费用与现金需求 | 符合原文无作废条款，保留 |
| P6；P:26–28、P:83；H:40 | 一次加仓多大，亏着也加吗 | 每笔 name_budget 默认100万，名单再现输赢都加 | 总持仓可多倍超过100万 | 业务定额而非风险上限，保留且披露累计暴露 |
| P6/S18；P:3、P:83；H:22；S:29 | 每个股票每天最多买几笔 | 不设次数或总买入金额闸；池/chase/step/双买回可共存 | 不是每天最多2笔，循环买回次数没有日上限 | 人裁明确，保留；不能将 HELP 理论买因数量当成风险限额 |
| P6/S9；H:22；S:20 | 卖掉台阶仓后同一涨幅能再加吗 | 独立单调 steps，不再数活着的 step lot | 消除同一价段卖掉又重复 step 加仓 | 保留，符合按上涨台阶加仓目标 |
| P7；P:84 | 是否加上证 MA10 闸 | 不加 | 大盘弱也按本书买入 | 原文未要求，不是漏接；保留 |
| P8；P:3、P:85 | 必须明确传名单目录吗 | 默认 stock_pool/；与 v7 必填池分工不同 | 默认会消费当前可变名单 | 保留业务入口；研究建议冻结名单/hash，不能擅称默认池可重现 |
| P9①/S10；P:86；H:13、H:18；S:21 | 买回下单股数怎样确定 | shares_override，per=实际 notional | 不再从原预算重新猜股数 | 保留，数量和记账一致 |
| P9②；P:54、P:86；H:18 | 今天买回的能立刻再卖吗 | T+1 过滤，减仓基数扣未解禁 bonus | 同日再跌破只能卖旧股 | 符合 A 股，保留 |
| P9③/S15；P:86；H:17；S:26 | 送转后记忆怎么办 | 显式 economics 开启才乘股份倍数，floor100，残余计 stats；现金分红不缩记忆 | 送转取整可能主动舍弃不足100股；默认没有自动权益事件 | 保留已裁取整特例，勿与普通成交 residual=2 混淆；CLI raw 跨除权局限需披露 |
| P9④/S4；P:86；S:15 | 买回还受总市值100万限制吗 | 否决市值帽，仅按通道记忆股数限额 | 已多次加仓也能买回，避免永久被市值帽卡住 | 符合目标，保留 |
| P9④；P:3、P:86；H:17 | 池/chase 又买进后旧买回还做吗 | 成功新买清零双记忆，不按新买股数部分冲抵 | 即便新买小于旧记忆，也取消全部旧买回 | 明确人裁，保留并解释全清语义 |
| P10/S5 初裁；P:87；H:21；S:16 | MA 怎样避免送转断点假止损 | 原定统一 front，跳过 E-R6 remap | 避免 raw 历史断点直接进入 MA | 目标合理；分钟方案已由后续人裁覆盖 |
| #151 option2/#158；P:6–10；H:63–67 | 分钟湖没有 front 怎么办 | 默认 minute none、日线信号固定 front；front minute 可选但缺分区即失败 | 能消费实际 raw 分钟湖，不强制不存在的1m/front | 保留双域职责，修价格转换、raw档位与raw估值，不能直接比较不同价域 |
| #151/#158 ex-div；H:67 | 混域时是否自动再做除权 | 仅显式 economics/文档路径，禁止静默双调 | 标准 run 不加载隐式 exdiv_map，也不自动入权益 | 保留禁止双调；这不等于可以省略价域换算和真实权益 |
| P11/S6 后续 latch=A；P:4、P:88；H:9；S:17 | 收复后同一天再跌破能再减吗 | 能，只有周期锁，无每日锁 | 当日多次穿线可再次减少原可卖股 | 直接人裁覆盖旧 plan 每日一次；保留，补成本敏感性 |
| 后续 residual=2；P:5；H:11 | 卖150买100后的50股怎么办 | 双通道保留残余、合入下一轮，立即 re-arm | 不丢买回权益，也不因余股永久锁死 | 保留，实际成交记忆正确 |
| residual=2 边缘；H:11 | 不足100股完全没买回，也能解锁吗 | 合格 reclaim 即解锁，残余仍留；禁止等归零 | 微小容量成交不会永久关闭减仓 | 保留，双通道均已 pin |
| P12/S3；P:89；H:19；S:14 | 继承 v8 自动卖出吗 | reserve_limit_up=False、defer_limit_up=False、daily_same_bar_prefixes=() | 避免开板整仓卖绕过双记忆 | 保留；这些 False 不取消实际涨跌停成交门 |
| P12；P:89；H:19 | 止损按买价还是 MA | 书侧 MA10×0.90，不走通用 STOP_PCT，--stop-pct 拒绝 | 不会叠加买价百分比止损 | 符合策略目标，保留 |
| P12；P:89；H:19 | MA 卖出要等峰值后15分钟吗 | peak_gap_min=0 | MA触发不会受旧峰值冷却延迟 | 保留 |
| P13/S13；P:3、P:90；H:15；S:24 | 减仓能否耗尽 lot0 | 减仓至少留100股，必要时少卖 | 保台阶锚，实际减幅可能低于50% | 保留业务目的；现实板块数量规则另按全局撮合核审查 |
| S1/§0.1–2；H:13–14；S:12 | 部分卖后能否删掉整 lot | 每次扣实成交股，剩余lot保留，现金股数守恒 | 修复历史静默丢股 | 已修，保留 |
| S2/γ契约；H:13、H:18、H:35；S:13 | 部分卖/买回放在哪一层 | γ三触点，书侧编排，独立 exit_plan/buyback_plan；买回第四买因 | 共享账本仍是成交与现金权威 | 保留；避免把数量藏进字符串信号 |
| S10；H:17、H:36；S:21 | 容量不足时记计划量还是实量 | 实际成交才累加/扣减记忆 | 买回不会超过实际卖出 | 保留 |
| S11；H:17；S:22 | 多次回测是否共用记忆 | 状态挂 st.book_state，不放模块级dict | 避免跨run串状态 | 保留 |
| S12；H:23；S:23 | 扫描器是否新增返回值 | 保留5-tuple，部分卖数量out-param | 保留旧调用兼容性 | 保留公开契约；内部性能优化可绕过单bar包装 |
| S14/R8；P:72；H:5；S:25 | 先做独立 MA 还是等共享组件 | #150合入才开Slice A，仅消费ma_infra | 不同策略复用均线口径 | 保留 |
| S16/S17；S:27–28 | 错误函数锚点、遗漏触点怎样处置 | 修文档引用，明确第三exdiv触点及中间lot顺序；1401为当时基线 | 工程可审查，通常不直接改变收益 | 保留正确说明；1401不能当当前固定测试总数 |
| S19 reason/§0.8；H:20；S:30 | 新建 ma12 分类还是复用 | 四个 ma_signal: 具体reason | 同入sell_ma桶，细分需看reason | 保留，报告区分减仓和止损 |
| S19 chase等值；P:31；S:30；H:29 | 09:45等于开盘能追吗 | abandon；必须严格大于且非涨停 | 边界股票不买 | 人裁已锁，保留 |
| S19 容量；S:30；H:29 | 计划整百是否保证实际整百 | 计划floor100，cap/locked bonus可使实卖非整百 | 产生残余记忆，也可能偏离真实委托手数 | 保留研究已裁语义，真实申报约束另行验收 |
| R1/R2/§0.12/S19；P:65–66；H:24、H:36；S:30 | 新书能改旧书行为吗 | hooks默认关，旧12本日/分钟 trades/equity字节等价，不改Mode A/B | 限制回归范围 | 保留，但不等于新书价格域正确 |
| §0.12 文本/检查；H:24、H:55 | 编码、测试、语义分叉谁决定 | UTF-8无BOM、ruff/pytest；新分叉停报而非自行定策 | 工程质量与审批边界，无直接收益公式 | 保留历史要求；本次审查按用户只读/不提問覆盖执行流程 |
| Slice D人裁；H:45、H:69–71；P:107 | 实湖比哪些，能否宣称收益有效 | 12 vs8/8.1/8.2/8.3，窗20251023–20260909；数字默认不入库、不主张returns/parity | A–C框架通过不等于策略收益验证 | 保留；后续#165已回填分钟五本回执，见4.7；旧handoff未执行状态已过时，回执仍不等于生产验收 |
| #169 D1（实现修复）；backtest/research/strategy12_engine.py:88、:183 | 日线次开能卖到信号后新买的lot吗 | 锁定信号时可卖lot，次开仅clamp，不溢出新lot | 避免旧股未减却锁住周期；分钟同根路径没此旧bug | 已修，保留；PR无新用户问答 |
| #170 D1（实现修复）；backtest/research/strategy12_rules.py:108、:117 | 次开lot0已缩小还要保100吗 | clamp重新保底，仅减仓保底，STOP不保；补chase/step回归 | 防延迟成交耗尽锚 | 已修，保留；零成交pending重试改变明确延期，不能称已解决 |

### 4.3 策略12：配置和代码默认值

下表属于实现默认或 CLI 选择；未在 PR 中逐项问答的，不能反写成用户逐项批准。

| 配置/代码证据 | 大白话问题及当前选择 | 对结果的具体影响 | 判断与建议 |
|---|---|---|---|
| backtest/research/csv_strategy_books.py:1460、:1468 | version12/12/v12；allow_add=True；per_name；每笔100万 | 多次名单/台阶可以超过100万总仓 | 保留人裁；明确每笔不是每股仓位上限 |
| backtest/research/csv_ledger.py:29 | 默认现金2100万 | 影响现金耗尽时点与投资比例 | 合理研究参数，必须随结果记录 |
| backtest/research/csv_minute_backtest.py:1009；backtest/research/strategy12_engine.py:219、:288 | ration=file_order、seed=0；每日先排序，逐分钟不重复洗牌 | 钱不够时CSV前排优先，名单排序可改变持仓 | 保留默认并公布排序；研究可比较shuffle/seed敏感性 |
| backtest/research/csv_minute_backtest.py:1029、:1049、:1129 | 两源默认lake；none默认；v12拒qlib；front minute可选且缺分区失败 | 不认证qlib域，避免静默源切换；none/front本身影响价域 | 拒不支持源合理；双域转换必须修正 |
| backtest/research/csv_minute_backtest.py:1090；backtest/research/strategy12_rules.py:70 | MA10预热用22日历日slack；不足5/10根返回None | 长停牌/缺历史会暂不触发相关MA规则 | 合理失败方式，但应统计warmup不足，不能假设22日保证10根 |
| backtest/research/strategy12_engine.py:235、:239、:241 | 09:45缺bar用09:30–09:45最后一根；14:55缺bar用14:30–14:55最后一根 | 可能提前执行，缺bar与停牌/迟到数据无法区分 | 既有时钟默认须显式披露；建议严格时钟/缺失延期敏感性 |
| backtest/research/csv_simulate_loop.py:377；backtest/research/strategy12_engine.py:273、:284 | step实际仅当日一个pool clock检查，每次最多一笔 | 一次跨越多级涨幅不会当天全补台阶 | 与代码既有节奏一致；HELP台阶N只是买因理论式，不保证同日N笔 |
| backtest/research/strategy12_rules.py:18、:75、:79、:84、:169 | MA5/MA10固定，止损0.90、台阶0.20；跌破用<，收复用>= | 相等边界只收复不减仓/止损，参数写死 | 符合批准书，保留；不要偷偷另开版本 |
| backtest/research/csv_minute_backtest.py:618、:624、:1002、:1223 | simulate的exdiv_economics/participation_rate默认None，run/CLI不暴露 | 标准CLI无真实量约束，也不自动入公司行动股息送股 | 已公开范围限制；收益报告必须声明，后续以显式事件/容量接口扩展 |
| backtest/research/csv_minute_backtest.py:1303、:1346 | --qlib-cost默认off：10bp双边无最低；on为买5bp/卖15bp/min5 | 高频小额残余/拆lot费用对开关敏感 | 不能称默认已按A股最低5及现行税费；建议与正式费率模型并列对照 |
| backtest/research/csv_strategy_books.py:669；backtest/research/csv_minute_backtest.py:1043 | v12拒--stop-pct；分钟拒--stop-fill close | 不能用通用买价止损/日收盘退出替代MA书 | 保留显式拒绝，避免静默忽略参数 |
| backtest/research/csv_minute_backtest.py:1016、:1288 | workers16，缓存默认开，可--no-cache/--rebuild-cache | 主要影响加载速度；缓存若缺域/数据版本信息可污染重现 | 记录源与缓存版本，性能开关不应改交易语义 |
| backtest/research/csv_minute_backtest.py:1315、:1319、:1323 | emit-run-manifest、require-signal-bundle、strict-pool均默认关 | 默认无法仅靠产物确认冻结名单和严格输入校验 | 旧CLI兼容可保留；正式研究建议显式开启，并保存bundle/hash |
| backtest/research/strategy12_rules.py:207；backtest/research/csv_minute_backtest.py:1265；H:68 | record先写price_domain=front，minute run结束改成成交域；另存两域字段 | 只调用simulate的stats与run的price_domain解释不同 | 建议固定独立字段含义，避免一个字段被两次赋不同职责 |


### 4.4 version11：全部P/V、人裁与实现默认

证据层级必须区分：P0–P7 是 plan 逐项人裁问题，PR152 body 与 handoff 记载「全按共识建议」；V1–V17 是评审共识修订项，被批准的 plan/handoff 接纳，不表示用户分别回答过 17 个独立问题。PR152 后续对「严格晚于 D」「周线 prefix」「volume=A」有明确追加人裁；Slice D 也有最终显式跳过决定。下表用「人裁」「接纳共识」「实现选择」「文档/验收」区分这些来源。

本小节简称：plan/handoff分别为下列version11计划/交接文件，exporter为scripts/data/export_strategy11_pool.py，minute为backtest/research/csv_minute_backtest.py，其余短文件名均位于backtest/research/。

主要依据：`docs/backtest/plan-version11-machip-csv-2026-09-21.md:74`、`docs/backtest/handoff-version11-codex-impl-2026-09-21.md:20`、`docs/architecture/reviews/2026-09-21/plan-version11-machip-csv/merge-consensus.md:12`，以及预收集 `context/pr-152.md` 全部评论。合并单元格覆盖重复决定，但每个 P/V 编号均保留。

| 决策 ID / 证据性质 | 大白话问题 | 当时选择 / 实现锚点 | 对回测结果的具体影响 | 行业/业务判断与建议 |
|---|---|---|---|---|
| P0，人裁 | 盈筹率高是否真应该买，先验证策略还是先搬框架？ | a：框架移植先行；CYQK>.70 不改方向；HELP 明示「抛压区、非已验证多头」；`strategy11_rules.py:23` | 跑通不等于能赚钱；阈值方向有效性未验证 | 保留诚实定位；补分组前瞻收益研究后再判断有效性 |
| P1 / V13，人裁+接纳共识 | 日线不能精确模拟次日开盘，怎样比较？ | a=日线契约 T 收盘；b=分钟精确09:30 open，以 b 为准；handoff`:13` | 日线/分钟买价、当日收益天然不同，不能要求成交价 parity | 符合数据分辨率边界；保留，不混用两者绩效 |
| P2 / V4 / V16，人裁+接纳共识 | 收盘决定卖，什么时候成交，买日能否卖？ | 日线沿pending_exit；分钟T+1 09:30 open；买循环后EOD写pending；无T+1旁路；`csv_minute_backtest.py:773`、`:988` | 收盘信号隔夜，开盘跌停继续持有 | 保留，符合因果与股票T+1 |
| P3 / V10，人裁+接纳共识 | 买信号放引擎里还是先导出？能否读TR store现成指标？ | 独立导出器；复用装载/股本bridge；CYQK window200现算；禁读store window1000的CYQK/布林；`scripts/data/export_strategy11_pool.py:127` | 名单能冻结审计，不暗换筹码窗口 | 保留 |
| P4 / V9，人裁+接纳共识 | 只跑历史30票还是全市场？ST/科创如何处理？ | 双模式；默认seed20240907、每板10；front∩float；沪60/深000–003/创300–301；universe滤ST并排688；seed沿归档不滤ST；exporter`:65`、`:78` | 两种universe不同；seed可保留ST，裸码池不表达历史ST名称 | 保留双模式；seed须注明ST/名称局限；严谨全市场研究应使用PIT状态 |
| P5，人裁 | 需要多少历史，哪天起统计？ | load-start20220701、stats floor20240101；窗前edge置假；exporter`:37`、`:190` | 排除预热期信号，统计窗前的信号不入池 | 保留；导出预热不能替代执行引擎SMA5预热 |
| P6，人裁 | 新旧引擎必须逐字相同吗？ | 不求byte parity；成交价/费用/skip三类差异+信号/成交数量级sanity bounds；plan`:82` | 容纳成交模型差异，不能只看最终收益接近 | 保留比较方法；实际D未执行 |
| P7，人裁 | 布林、周线数学口径改不改？ | 沿用ddof1、周线backward、末端未完成周允许；`ma_infra.py:65`、`:108` | 相比ddof0上轨略高，突破边缘可能减少；周内均线随当时数据更新 | 与批准业务一致；保留，平台对照须显式匹配参数 |
| V1 / handoff§0.1，接纳共识 | 信号和成交是否用同一复权价？ | 信号front；成交raw+映射昨收；exporter`:281` | 目标是防除权假信号且保留真实成交价；现有EOD SMA5接线未完全兑现 | 保留双域设计，修v11卖出信号仍用raw历史的问题 |
| V2 / PR追加明确人裁 | D是信号日还是预定交易日？停牌等几天？ | D=原信号日；T严格晚于D的第一根正量日K；D→T≤4自然日；stale从原D算；exporter`:99` | 周末计入4日；长假/停牌会消耗信号；禁止D日收盘信号拿D日开盘成交 | 保留严格因果；4自然日是策略选择，并非交易所通则 |
| V3，接纳共识 | 周线算法归谁，能否每天重跑pandas？ | 统一ma_infra series；全市场不逐日resample；exporter`:164` | 算法同源，避免高昂重复计算 | 保留 |
| PR周线追加明确人裁 | 加入未来周五数据后，之前周一的信号能否改变？ | A：每D截断等价；显式prefix opt-in；旧默认不变；`ma_infra.py:127`、`:153` | 新数据追加不改历史信号 | 保留，这是必要因果约束；默认series不能无脑用于全历史信号 |
| V5，接纳共识 | 筹码窗口有坏值、数组错长怎么办？ | 坏窗口NaN→该日该码skip；ValueError→该码skip+计数；exporter`:154`、`:181` | 坏股本影响覆盖它的200日窗，可能长时间无信号 | 保留fail-closed；展示skip覆盖率 |
| V6，接纳共识 | 极宽价格跨度把Rust网格撑爆怎么办？ | step=.01，跨度/step>250000则skip；等于阈值允许；exporter`:139` | 高跨度窗口被排除，样本覆盖变化 | 保留资源闸，报告排除比例 |
| V7，接纳共识 | 能否拿今天流通股本倒填历史？ | 每日backward-asof circulating_capital；禁止date=None；`oskh_factors/bridge/turnover_resist.py:70` | 防未来股本混进历史筹码；缺值按窗口传播 | 保留 |
| V8 / R10，接纳共识，明确否决旧fallback | Rust失败是否切Python算法求结果？ | 不切算法；显式改变旧归档fallback口径；plan`:70` | 牺牲覆盖率换可复现，避免两算法混算 | 保留，显示失败比例；不能称与旧归档算法执行路径完全一致 |
| V11，接纳共识 | 当日卖完再进名单能否马上买回？ | sold-today闸禁止；`csv_minute_backtest.py:948` | 防同日往返、重复手续费，减少再入场 | 保留，符合单笔状态机 |
| V12 / V15 / R9，接纳共识及追加确认 | 涨停买不到，后面继续追吗？ | apply显式limit_up_chase=False，实际pending chase为空；`csv_strategy_books.py:993` | 信号消耗，不会T+2或30日后追买 | 保留，与本书FSM吻合 |
| V14，接纳共识 | 零量bar能否充当下一交易日？ | 导出剔daily volume==0；分钟保留零量行供计数，但拒开盘成交，不借后续bar；exporter`:123`、minute`:921` | 无量日不成为T；开盘无量不补09:31 | 保留，明确有效bar定义 |
| V16 / SMA5口径，接纳共识+实现pin | 买日红绿判断每天重做吗？MA含当天吗？ | 仅entry_close判阴阳；阳线转hold_sma5；SMA5含T；`strategy11_rules.py:76` | 后续阴线但仍高于SMA5继续持有；买日阳线也可因破SMA5排次日卖 | 保留；两段FSM已回归 |
| V17 / handoff§0.10–11，接纳共识 | 怎样保证产物可复查？ | 裸六码日期CSV；拒stock_pool；独立rejected/manifest；记录front、pyd路径/版本、skip计数；exporter`:222` | 防错池/旧池污染，能追溯数值实现 | 保留；真实pyd/湖验收仍缺席 |
| PR volume A，追加明确人裁，否决B | 开盘能否用这整分钟稍后才知道的量？ | A：严格可得性bucket570>at569→买skip/卖defer；拒v11同分钟完整量例外；minute`:792`、`:947` | cap启用后新买恒为0；已有pending可一直等待，不能解释成没有信号 | 因果保守但不适合容量研究主结果；保留当前合同、显著提示无成交，后续单独重裁可成交近似 |
| handoff§0.12，范围约束 | 顺手改变其它书与默认吗？ | 禁改1–10/8.x/12、ModeA/B和cap默认；handoff`:41` | 防旧策略结果漂移 | 保留范围约束 |
| PR Slice D，最终明确人裁 | 没真实pyd/归档，还继续阻塞吗？ | 2026-09-21T07:28:14Z显式跳过D，诚实STOP，不主张收益/parity | 只有框架/data-free证据，无seed30/全市场湖验收 | 保留未验证标签，具备条件后另做验收；不把获准跳过写成违规 |
| PR实施/合入程序，流程人裁 | 实施代理能否自动merge？ | 多次明确禁自动merge，合入另等人裁；随后PR实际已合并 | 影响交付流程，不直接改变数学 | 记录时间线即可，不据此推断数值问题 |

#### version11 CLI与固定参数

这些是可核实的实现默认，不能全部冒充用户逐项选择；有对应 P/V 的才追溯到前表。来源：`scripts/data/export_strategy11_pool.py:37`、`:262`；`backtest/research/strategy11_rules.py:10`；`backtest/research/csv_strategy_books.py:984`。

| 配置/默认 | 大白话含义与当前选择 | 对结果影响 | 判断与建议 |
|---|---|---|---|
| `--sample [int]` / `--universe` | 二选一；默认sample20240907、每板10；真实语法不是`--sample seed=20240907` | 决定统计对象 | 保留；文档使用实际语法 |
| `--start` | 默认20240101，另有不可低于20240101的stats floor | 提前传start仍不会导出floor前信号 | 与归档统计窗一致；manifest/说明明确 |
| `--end` | 默认运行当天 | 不固定则窗口随日期变化 | 冻结研究必须显式固定end |
| `--load-start` | 默认20220701；load-start<start≤end | 用户可缩短历史；sample不足失败，universe可能无信号 | 保留灵活性，展示warmup覆盖 |
| `--out-dir` | 默认exports/s11_machip_<start>_<end>；池在pool/；非空拒覆盖 | 防旧日期残留污染 | 保留 |
| `--pool-dir` | v11必填，拒stock_pool/ | 防误用别的策略名单 | 保留 |
| `--strategy` | 11/v11/version11，tag v11 | 同一本书别名 | 保留 |
| `--stop-pct` | CLI拒绝；内部apply强制None | 无额外盘中止损覆盖，只走批准MA卖点 | 与计划一致；保留并展示 |
| minute source | 必须lake并有volume；绕过旧无量cache；拒qlib_1min | 装载较慢，但不默默丢量 | 保留；可新增含volume、版本化可校验缓存 |
| dividend type | v11分钟只允许none；导出固定front | 成交raw合理，但EOD信号缺独立front | 保留成交约束，修信号域接线 |
| 数学常量 | CYQK200/.70、20周线、MA20/60、BB20/2/ddof1、退出MA5 | 决定触发数量/时间 | 都是策略定义而非行业唯一值；未经业务重裁不自行改 |
| ALLOW_ADD=False | 单票一笔，不加仓 | 限制集中度和信号累积 | 与归档一致，保留 |
| PEAK_GAP_MIN=0 | 不采用通用盘中止盈的15分钟等待 | v11不走通用intraday退出 | 与EOD FSM一致，保留 |
| minute_open/eod_exit/skip_sold_today | apply固定开启 | 固定开盘成交、日终决策及卖日不重入 | 保留 |
| participation_rate=None | 默认不限制成交占市场量比例；正量开盘可成交 | 默认研究结果没有容量验证 | 保留明确模型标签；开启后的恒零成交限制见人裁A |
| 仓位/成本继承 | 沿通用CSV daily_quota/fee，不沿用Cerebro自写费率 | 旧新结果可能仅费用就不同 | 保留CSV统一模型，对照必须拆费用差异；通用具体数值见引擎配置表 |

### 4.5 ma_infra：全部P/C决策及默认

P1–P4 为明确人裁；C1–C12 为评审共识修订，被获准plan/handoff接纳。C8等为交付规则；tuple属于评审建议取舍；`prefix_equivalent`来自后续version11追加人裁，不冒充ma_infra初始四问。依据：`docs/backtest/plan-ma-infra-shared-2026-09-21.md:54`、`docs/backtest/handoff-ma-infra-codex-impl-2026-09-21.md:9`、`docs/architecture/reviews/2026-09-21/plan-ma-infra-shared/merge-consensus.md:9`。

| 决策 ID / 性质 | 大白话问题 | 当时选择及对结果影响 | 行业/业务判断与建议 |
|---|---|---|---|
| P1 / C3 / C11，人裁+接纳共识 | 需要哪些均线工具，现在加EMA/WMA吗？ | 八件SMA/asof/live、BB/series、weekly转换/series/asof；live为strategy12预留；不做EMA/WMA | 保留，避免增加未经批准的策略定义 |
| P2 / C3 / C7，人裁+接纳共识 | 批量指标用pandas还是纯Python？ | stdlib前缀和/增量；模块不import pandas/numpy；不做*_frame；影响效率、浮点累加顺序 | 保留，优化须回放数学与NaN语义 |
| P3 / C6，人裁+接纳共识 | strategy4迁移是否顺便改买卖门？ | 删旧def后import/re-export，gate函数体零diff | 行为冻结正确，保留 |
| P4 / C9，人裁+接纳共识 | 算法放哪，周线用谁？ | backtest/research/ma_infra.py；v11统一消费；旧oskh_factors私有周线和MA200不动 | 保留；双副本用差分测试防漂移 |
| C1 / C12 / handoff§0.3，接纳共识 | 布林σ用总体还是样本，四位舍入吗？ | ddof1、无round4；[1..5]σ=1.5811388300841898；旧chip/TR ddof0件不强行改齐 | 参数改变突破阈值；保留明确业务口径，跨平台必须匹配参数 |
| C2 / handoff§0.4，接纳共识 | 周线标周五还是实际最后交易日，半周算不算？ | W-FRI分桶，key=_last_day；末端未完成周保留，停牌空周消失 | 会改变均线参与时点；保留，v11使用prefix维持逐日因果 |
| C4 / handoff§0.2，接纳共识 | 缺值、NaN、小数窗口怎样处理？ | 保留seed：NaN传播、int(n)截断、n≤0 None；series等长且前n−1 None；BB n<2全None | 防兼容漂移；调用方必须区别不可计算与条件不成立 |
| C4 / handoff§0.8，接纳共识 | 实时MA用最老还是最近n−1根？ | 尾部n−1 close+现价；history不足或px≤0→None | 决定盘中触线时点；保留 |
| C5 / handoff§0.9，接纳共识 | 数学模块自行复权吗？ | 零复权、零证券代码；域/截断由调用方负责；v4保持raw、v11导出front | 分工合理；保留，修v11 EOD调用方错域 |
| C7，接纳共识/范围 | 为新模块扩大整个research import fence吗？ | 不扩大固定热路径列表；未来frame独立模块、lazy import/AST pin另做 | 不直接改变收益，防范围膨胀；保留 |
| C8，接纳共识/交付 | 哪些测试算门禁？ | CI=-m "not production and not benchmark"，补strategy4快检 | 区分data-free与真实湖验证；保留，不能以CI绿替代湖验收 |
| C10，接纳共识 | 纯Python周线怎样避免偏离旧pandas？ | 差分pin覆盖短周/空周/跨年/NaN/周六；旧函数仍私有 | 对有意义边界验证等价；保留 |
| tuple建议，评审取舍，未单独人裁 | 布林输出要不要换NamedTuple？ | codex建议未采纳，维持tuple | 无数学影响；保留，不把未采纳建议列为缺陷 |
| prefix_equivalent=False，后续v11人裁 | 默认周线series是否逐D截断等价？ | 默认保持full-history backward alignment；v11显式True | 默认和逐D信号含义不同；保留兼容，调用方必须显式选择 |
| PR150/154，交付事实 | handoff先合并是否等于代码完成？ | #150先合文档；真正代码后续#154于2026-09-21合入 | 无直接数值影响；报告应纠正时间线，不将ma_infra算第三个策略 |

初始implementation的Ruff版本/隔离Python环境属于实施工具选择，预收集材料未显示用户逐项回答；不把它们包装成策略人裁。它们也不构成回测参数。

### 4.6 第三组：8.1/8.2/8.3的业务选择

以下是源码锁定的策略选择。所给上下文没有对应每一条的原始用户问答，因此标为 **code default／冻结合同**，不冒充逐条新的人裁。8.1/8.2/8.3 是 2026-09-21 注册的历史里程碑家族；#156 是研究成交适配器，不是第三个注册策略。

| 决策、性质 | 大白话与已选内容 | 对结果的具体影响、判断与建议 | 工作树依据 |
|---|---|---|---|
| 历史规则配当前引擎；冻结合同 | 卖点按历史包冻结，费用、涨跌停、除权、追买沿用当前宿主 | 得到“同引擎异规则”的比较，不是历史原环境收益复现；保留，记录宿主 tip | `backtest/research/strategy8_1_rules.py:3`；`backtest/research/strategy8_2_rules.py:3`；`backtest/research/strategy8_3_rules.py:3` |
| 8.1 止损；code default | 跌20%卖 | 宽止损是策略偏好，不是市场惯例；保留冻结合同 | `backtest/research/strategy8_1_rules.py:23` |
| 8.1 小利润保护；冻结合同 | 先涨到+6%，再跌回+2%卖 | 文案中的“2%×2按6%”是历史口径，不能自行改成4%；保留6%，澄清表述 | `backtest/research/strategy8_1_rules.py:26`；`backtest/research/strategy8_1_rules.py:101` |
| 8.1 大利润阶梯；code default | 峰值(15%,40%]/(40%,60%]/(60%,80%]/(80%,100%]/(100%,120%]分别用15/30/50/70/90%地板；超过120%改峰值回撤20% | 退出是绝对盈利地板而非全程固定比例回撤；保留业务数学，修复分档边界浮点误判 | `backtest/research/strategy8_1_rules.py:30`；`backtest/research/strategy8_1_rules.py:66` |
| 8.1 止盈前置；code default | 现价低于成本时不按止盈卖，止损另判 | 回落穿成本但未触20%止损可继续持有；保留并解释 | `backtest/research/strategy8_1_rules.py:85` |
| 8.1 仓位；code default | daily_quota；同码可再买，各lot独立；峰值等待间隔0 | 每日100万分给名单，与8.2/8.3每票预算不同；保留，比较时单列资金模式 | `backtest/research/strategy8_1_rules.py:20`；`backtest/research/strategy8_1_rules.py:103`；`backtest/research/csv_strategy_books.py:1341` |
| 8.1 止盈资格；code default | 规则不另禁T+1止盈，由宿主T+1可卖门约束 | 比8.2提前一天可以兑现；保留 | `backtest/research/strategy8_1_rules.py:84`；`backtest/research/csv_minute_backtest.py:807` |
| 8.2 止损/止盈资格；冻结合同 | 止损30%；T+1仅止损，T+2起止盈；峰值从T+1累计 | T+1利润不能按止盈兑现，仍进入以后峰值；保留冻结合同 | `backtest/research/strategy8_2_rules.py:22`；`backtest/research/strategy8_2_rules.py:81`；`backtest/research/strategy8_2_rules.py:105` |
| 8.2 比例阶梯；code default | 小涨保留30%；6–15%回到+2%；15–50%保留60%且至少+15%；之后保留70%/80% | 小涨可以保本、扣费后微亏退出；保留 | `backtest/research/strategy8_2_rules.py:25`；`backtest/research/strategy8_2_rules.py:58` |
| 8.2 分档边界；冻结合同 | 用峰值价格对成本倍数比较；(0,6%)/[6%,15%)/[15%,50%]/(50%,100%]/(100%,∞) | 精确50%、100%仍留在较低一档；不要拿8.3边界覆盖它 | `backtest/research/strategy8_2_rules.py:38` |
| 8.2 仓位；code default | per_name100万，同码可再入、独立lot，峰间隔0 | 同日多票时仓位可远大于8.1；保留，明确预算不是天然累计单票上限 | `backtest/research/csv_strategy_books.py:1353`；`backtest/research/strategy8_2_rules.py:106` |
| 8.3 止损；code default | 跌10%卖 | 比8.1/8.2更紧；保留 | `backtest/research/strategy8_3_rules.py:36` |
| 8.3 止盈；冻结合同 | T+1起；峰值须超过6%才评档位回撤；15/50/100%处采用自己的开闭区间 | 不同于8.2；例如精确50%进入下一档。保留各自合同 | `backtest/research/livermore_exit_rules.py:23`；`backtest/research/livermore_exit_rules.py:74` |
| 8.3 僵持；code default | 满8个交易日且峰值从未到6%退出 | 释放长期无表现资金；保留，但说明仍经过宿主扫描门 | `backtest/research/livermore_exit_rules.py:53`；`backtest/research/livermore_exit_rules.py:70` |
| 8.3 峰值间隔；code default | 创新高后至少15分钟才评止盈 | 快速冲高回落未必立刻退出；保留并对午休/隔夜语义做回放 | `backtest/research/strategy8_3_rules.py:34`；`backtest/research/strategy8_3_rules.py:93` |
| 8.3 首仓/加仓；冻结合同 | 首仓50%；现价须不低于各lot成本，且至少一个lot峰值到+3%才加 | 降低首次暴露，只给赢家加仓；保留，追买路径也必须遵从50%预算 | `backtest/research/strategy8_3_rules.py:45`；`backtest/research/strategy8_3_rules.py:53` |
| 8.3 大盘门；冻结合同 | 上证连续两日收在MA10下，第三日起新仓、加仓全停；只用昨收 | 避免拿当日指数收盘指导盘中买入；保留 | `backtest/research/strategy8_3_rules.py:65`；`backtest/research/strategy8_3_rules.py:98`；`backtest/research/csv_minute_backtest.py:1213` |
| 大盘表缺失处理；code default | 直接库调用没传表就不设门；表缺某日默认不挡；CLI的8.3强制加载 | 库回放与CLI可能不同；建议明确记录门是否存在，缺所需会话应报错 | `backtest/research/strategy8_3_rules.py:72`；`tests/test_strategy8_milestones.py:145`；`backtest/research/csv_minute_backtest.py:1219` |

### 4.7 分钟敏感性B与#156：人裁和实验合同

**上下文逐项覆盖**：已读 `pr-137/141/142/156/157/159/165/167/173/176.md` 的正文和全部评论。#156有三次实质人裁（先H2、后补卖单过期、再Q2）。#137/#141正文记录GO入口，实际最新GO A记录在工作树人裁卡；其预收集评论区为空。#142评论只谈路径CI修正和4090运行回填，没有新增买卖裁定。#157/#159/#165/#167/#173/#176评论区均为空，不能从PR作者的实施说明倒推用户回答。#157为策略12评审，#159为已批准实验的数值回填，#165为五书分钟回执，#167为TopK旁路，#173为9月23日8.4–8.6后续，#176仅更新测试基线；其行为选择分别记录在相应实现/CLI或另章。

**Slice D状态更新**：#165的20260922c五书分钟回执已经完成并记录具体NAV/收益/回撤；工作树证据为 `docs/backtest/reviews/slice-d-minute-five-book-20260922c-2026-09-22.md:10`、`:15`、`:31`。它取代早期s12交接文档中的“尚未执行”状态，但只是历史回执转录，不等于本轮复跑或证明后续#169/#170修正后的结果。#173/#176无新的用户问答：前者是获准close-clear等后续书实现，后者只刷新其基线测试，不能另造一组人裁。

| 决策、性质 | 大白话 | 当时选了什么 | 对回测结果的具体影响、判断与建议 | 工作树依据 |
|---|---|---|---|---|
| Human GO B；明确人裁 | 发现分钟假设有风险，要先实验还是直接改默认 | 先只读敏感性研究，生产默认冻结 | 先补证据再决定行为变更；保留 | `docs/backtest/reviews/plan-minute-sensitivity-b-2026-09-20.md:3` |
| #141 Human GO A；明确人裁 | 几笔局部差异能否拿来改全策略默认 | 继续扩样，补组合NAV/DD/rank，没有选行为变更C | 局部bp不是组合收益；保留 | `docs/backtest/reviews/human-cut-minute-sensitivity-b-defaults-2026-09-20.md:5`；`docs/backtest/reviews/human-cut-minute-sensitivity-b-defaults-2026-09-20.md:30`；`docs/backtest/reviews/human-cut-minute-sensitivity-b-defaults-2026-09-20.md:46` |
| GO option2；明确人裁 | 旧runner不能做完整时钟实验，是否准许新增代码 | 允许独立research-only fullstrat hooks，默认继续冻结 | 可以完整重放现金、仓位而非静态改价；保留隔离 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:9` |
| H2覆盖范围；明确人裁 | 只换追买/加仓还是全部买卖 | 所有fill换next-open；未选H1局部交换或H3跨日pending | 完整覆盖，但与旧局部结果不可混比；保留清晰标签 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:182`；`docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:184` |
| H2订单寿命；明确人裁 | 今天没成交，明天是否继续等 | 买卖均严格同日到期 | 晚入场可能全部消失；适用于明确DAY实验，不是所有订单的唯一市场惯例；保留实验合同 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:185`；`backtest/research/fullstrat_research_hooks.py:181` |
| H2无baseline回退；明确人裁 | 延迟后不能买，能否偷偷沿用旧入场 | 接受未成交、全现金NAV，不回退 | 防止混合时钟冒充全替换；保留；全现金不能证明策略优秀 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:186`；`tests/test_fullstrat_research_hooks.py:141` |
| 卖单到期；补充人裁 | 卖不掉后继续坚持卖，还是明天重新判断 | 清除意图，持仓保留，下一交易日正常评估 | 次日条件恢复则继续持仓；属于明确业务偏好，保留 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:187`；`backtest/research/fullstrat_research_book.py:193` |
| Q2；明确人裁覆盖Q1 | 实际价格变贵，是固定原股数拒单还是重新算股数 | 按实际next-open/slip价跑整手sizer，覆盖固定股数Q1 | 1万元预算、10.1元成交会由1000股改900股，现金剩950.91；适合预算单实验；保留 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:195`；`backtest/research/fullstrat_research_book.py:104` |
| START可得性与1ms；实验合同 | 一分钟close到底什么时候才能知道 | label+1min可得，下单再+1ms | 同时刻open不可用；14:55close到14:56已知，14:56open早于提交，14:57又不接，故无成交；保留但明确是保守延迟假设 | `backtest/research/fullstrat_research_hooks.py:52`；`backtest/research/fullstrat_research_hooks.py:117` |
| 交易区间；实验合同 | 是否允许午休和收盘集合竞价 | open仅[09:30,11:30)、[13:00,14:57) | 故意不模拟集合竞价；保留边界，不能说覆盖市场所有可交易阶段 | `backtest/research/fullstrat_research_hooks.py:123` |
| 事件排序/现金；实验合同 | 晚些卖出的钱怎么防止提前拿来买 | clock轴按真实事件排序，实际成交才改变现金/阶段，不预留现金 | 防止未来卖出资助早买；保留并验证现金守恒 | `backtest/research/fullstrat_research_hooks.py:80`；`backtest/research/fullstrat_research_hooks.py:98`；`docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:201` |
| clock XOR slip；固定矩阵 | 一格是否同时改延迟和滑点 | 每格只改一轴；slip只能0/5/10/20bp | 容易归因，未测交互项；保留本轮，组合压力另开格 | `backtest/research/fullstrat_research_hooks.py:21` |
| 滑点与费用；实验合同 | 是总收益扣几个bp还是重新记账 | 买乘1+s、卖乘1−s；按成交金额重算费用和股数 | 体现股数阶跃、现金竞争；保留 | `backtest/research/fullstrat_research_hooks.py:38`；`docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:157` |
| slip执行顺序；实验合同 | 滑点实验是否顺便修原执行顺序 | 保留生产默认顺序 | 隔离滑点影响，但保留基线时序问题；保留标签，不能当执行真实性证明 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:201` |
| 市值估值；实验合同 | 未卖持仓也按不利滑点价估值吗 | 保持无冲击市场mark | 防止尚未发生的卖出滑点进入NAV；保留 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:207` |
| 费用基线；实验合同 | 时钟实验是否同时换收费 | 双边10bp、min0，不换QLIB费率 | 保持可比，但只是成本代理；保留基线，真实费用另列轴 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:50` |
| 容量另轴；实验合同 | 延迟/滑点实验是否同时限量 | capacity另测，接口传容量参数直接拒绝 | 防止混因；保留，但不能凭结果证明大资金可执行 | `backtest/research/fullstrat_research_book.py:47` |
| 默认隔离；实现约束 | 不选实验时是否仍用旧引擎 | 默认和0冲击直接委托原引擎 | 防止实验修改常用结果；保留 | `backtest/research/fullstrat_research_hooks.py:188` |
| 缺数；证据约束 | 没有湖/名单/结果能否填估计值 | DATA_GAP，不发明数字 | 保留；未成交与缺数据要分开 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:44`；`docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:169` |
| 排名；证据约束 | Book/v7/ModeB能否放一个胜负榜 | 分引擎、分cell；v9/v10还分池，oracle不入可执行排名 | 防止规模、名单与规则混因；保留 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:76`；`docs/backtest/reviews/addendum-batch4-slice-d-fullstrat-hooks-2026-09-21.md:44` |
| SliceD排除baseline；实施选择 | D是否重跑基线 | D故意只跑clock和三档slip，历史baseline不改 | 需对照各自tip，不能声称同期重跑；保留溯源 | `docs/backtest/reviews/addendum-batch4-slice-d-fullstrat-hooks-2026-09-21.md:5`；`docs/backtest/reviews/addendum-batch4-slice-d-fullstrat-hooks-2026-09-21.md:39` |
| 当时发布流程；历史人裁 | 实现能否自动并入主线 | 当时只允许draft，等人工tip，禁自动merge；后来PR已合并 | 不改变数学；记录历史，不把旧禁令当本轮新授权 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:9`；`docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md:193` |

### 4.8 主分钟CLI/config选择矩阵

本表均为 **verified-in-code 的默认或接口选择**。没有找到逐项原始用户回答的，不标为人裁。与具体三书无关的TopK开关也列出，因为它们被同一个主分钟CLI暴露。独立接口的重复参数合并列示。

| 入口与默认 | 大白话、对结果的具体影响 | 行业/业务判断与建议 | 工作树依据 |
|---|---|---|---|
| `--strategy`必填、aliases规范化 | 必须主动选策略，防止默跑另一书 | 保留 | `backtest/research/csv_strategy_books.py:182` |
| `--start 20251023`、`--end 20260909` | 写死历史窗口；end来自MINUTE_LAKE_END，不自动到今天 | 有利于复现；必须记录窗口和实际覆盖 | `backtest/research/csv_strategy_books.py:363`；`backtest/research/ashare_bars.py:26`；`backtest/research/csv_minute_backtest.py:1281` |
| `--cash-total 21_000_000` | 初始资本影响仓位率及现金拒单 | 保留显式参数，比较时统一 | `backtest/research/csv_ledger.py:29` |
| `--daily-quota 1_000_000` | daily_quota模式下一天名单共用额度 | 明确适用书，不能等同每票100万 | `backtest/research/csv_common.py:17`；`backtest/research/csv_simulate_loop.py:283` |
| `--name-budget 1_000_000` | per_name每次预算，书钩子可减半；不是天然累计单票上限 | 保留并改help澄清 | `backtest/research/csv_strategy_books.py:379`；`backtest/research/csv_simulate_loop.py:330` |
| `--ration file_order`或`seeded_shuffle`，seed0 | 现金不足先满足靠前票；乱序按日期派生可重复顺序 | 保留，增加多seed资本配给敏感性 | `backtest/research/csv_strategy_books.py:385`；`backtest/research/csv_simulate_loop.py:92` |
| `--workers 16` | 数据加载并行度，应只改速度 | 保留可调，线程数不应改结果 | `backtest/research/csv_strategy_books.py:364`；`backtest/research/csv_strategy_books.py:397` |
| `--pool-dir stock_pool` | 默认池；v9/v10/v11拒绝该默认，v12与8.x允许 | 保留业务隔离 | `backtest/research/csv_strategy_books.py:55`；`backtest/research/csv_strategy_books.py:398` |
| `--stop-pct None` | 未传用各书止损，8.x覆盖要求0<值<1 | 保留；help内旧v6/v8默认说明应更新 | `backtest/research/csv_strategy_books.py:205`；`backtest/research/csv_strategy_books.py:736` |
| `--profit-base .01`、`--trail-t1..t5 .3/.4/.5/.6/.7` | 旧v6/10锚参数；其他书忽略，当前v6专用take_profit也不再按旧锚算 | 建议只对有效书暴露，避免成功解析却不生效 | `backtest/research/strategy6_rules.py:23`；`backtest/research/csv_strategy_books.py:213` |
| `--minute-source lake/qlib_1min`、`--daily-source lake/qlib_day`，均默认lake | 两个域可独立选；各root参数隐含切换对应source | 必须记录来源与复权，防跨域组合 | `backtest/research/csv_minute_backtest.py:1292`；`backtest/research/csv_minute_backtest.py:1328` |
| `--dividend-type none`，front仅v12可选 | raw分钟默认；v12日线信号固定front；v11必须lake分钟volume | 按分域合同执行；不能把front信号价当raw成交参考 | `backtest/research/csv_minute_backtest.py:1048`；`backtest/research/csv_minute_backtest.py:1057`；`backtest/research/csv_minute_backtest.py:1294` |
| cache默认开；`--no-cache`、`--rebuild-cache` | 跳缓存或重建，理论上不改行情 | 保留，记录cache血缘/版本 | `backtest/research/csv_minute_backtest.py:1288` |
| `--qlib-cost`默认关 | 默认双边10bp/min0，开启买5bp卖15bp/min5 | 可做费率对齐，不是独立税费账单；保留对照 | `backtest/research/csv_minute_backtest.py:1303` |
| `--out-dir`默认策略+窗口目录，拒绝非空覆盖 | 保存三件套，避免覆盖老结果 | 保留 | `backtest/research/csv_minute_backtest.py:1362` |
| `--emit-run-manifest`默认关 | 默认没有完整运行provenance | 正式交付建议开，并考虑改为默认 | `backtest/research/csv_minute_backtest.py:1314` |
| `--require-signal-bundle`默认关 | 默认不强制名单hash/交接包 | 跨仓正式对照建议开 | `backtest/research/csv_minute_backtest.py:1318` |
| `--strict-pool`默认关 | 默认宽松解析名单 | 正式研究建议开，避免静默漏行 | `backtest/research/csv_minute_backtest.py:1322` |
| `CSV_SCAN_HELD_DAY_BACKEND=python` | 可选numba但只支持无callable的trail；8.1/8.2/8.3均回落Python | 保留显式后端；不能把设置环境变量当已加速证明 | `backtest/research/csv_minute_backtest.py:265`；`backtest/research/csv_minute_backtest.py:443` |
| 库参数`participation_rate=None`，CLI未接容量 | 默认无限量成交近似；不是0参与率，也不是验证过无限流动性 | 正式大资金研究需明确启用/独立容量测试 | `docs/backtest/reviews/eval-minute-pitfall-vs-asbuilt-2026-09-20.md:101` |
| TopK `--pred-csv`/`--scores-dir`默认无 | 前者T用T−1分数，后者文件名为买入日 | 仅TopK有效；要保留日期契约 | `backtest/research/csv_strategy_books.py:253` |
| TopK `--topk 50`、`--n-drop 5` | 控制目标持仓数和每天换出数 | 业务选择，保留显式参数 | `backtest/research/strategy_topk_dropout_rules.py:17` |
| `--st-daily-file`/`--age-map-file`默认无；`--age-days 60` | 可选PIT ST与上市年龄过滤 | 记录是否开启，不能把未提供过滤表误说成已过滤 | `backtest/research/csv_strategy_books.py:277` |
| `--return-threshold-filter`默认关 | 5日涨幅>15%不新买 | 是选股规则改动，单轴实验 | `backtest/research/csv_strategy_books.py:295` |
| `--stop-fill touch` | CLI可解析close，但分钟入口拒绝close | 正确区分bar close与日终close；保留拒绝 | `backtest/research/csv_strategy_books.py:303`；`backtest/research/csv_minute_backtest.py:1043` |
| `--buy-state-file`默认无，`--buy-state-rule oral` | 无文件不加买门；规则可选盈筹/MA20/周20/个股MA5组合 | 改变入选及闲置资金；保留显式标签，核实数据可得性 | `backtest/research/csv_strategy_books.py:312` |
| `--index-ma5-gate`默认关 | 上证前一交易日低于MA5则下一日不新开 | 可因果实现的风险闸门；保留可选 | `backtest/research/csv_strategy_books.py:335` |
| `--keep-buy-vacancy`默认关 | 开启后原名单均线门失败就留现金，不继续补票 | 直接改变仓位率；保留并说明ST/年龄/涨幅过滤不遵从同一留空逻辑 | `backtest/research/csv_strategy_books.py:344`；`backtest/research/strategy_topk_dropout_rules.py:51` |
| v7起止必填；池CLI或`OSKH_TURTLE_POOL_DIR`必填 | 不回落stock_pool；现金默认21M，数据source默认lake/lake | 保留v7独立合同 | `backtest/research/csv_minute_backtest_v7.py:604`；`backtest/research/csv_minute_backtest_v7.py:627` |
| v7 `--asof-pool-names`默认关 | 默认窗口静态名，开启才按日期取名/ST状态 | 建议默认PIT，避免未来改名污染早期涨跌停档位 | `backtest/research/csv_minute_backtest_v7.py:609` |
| fullstrat `--cells`默认仅baseline | 实验需主动选固定clock/slip格 | 保留，避免无意改时钟 | `scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py:1052` |
| fullstrat窗口20260825–20260909；三引擎；Book1–6/8–10 | 固定矩阵没有包含新8.x/11/12 | 不能把该批数值外推到新三书 | `scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py:34`；`scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py:48`；`scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py:1066` |
| fullstrat qlib根、pool、output及`--engines/--strategies` | 可选数据路径/子矩阵，qlib根优先环境变量再历史默认 | 建议去除机器默认根，统一显式来源；保存全部路径和选择 | `scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py:1059`；`scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py:1066` |
| fullstrat `--dry-run/--emit-stubs/--execute/--force` | 展示、写缺口桩、执行、允许覆写桩；实验结果仍禁复用 | 保留隔离，避免旧baseline伪装实验数据 | `scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py:1076`；`scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py:969` |

## 验证记录、覆盖与限制

本次验证均使用 /home/box/.venvs/bt-ci/bin/python，并设置 PYTHONDONTWRITEBYTECODE=1。只运行合成数据和便宜夹具；未配置、探测或下载市场湖，没有执行研究CLI去生成仓内回测产物。官方网页查询仅用于核实平台合同和交易所规则。前述 pytest 临时目录误写另行披露，不以这些措施掩盖。

| 验证范围 | 结果 | 可以支持什么／不能支持什么 |
|---|---|---|
| 主分钟、v7、bars/session/fees/volume/economics 七组既有测试 | 183 passed，1.22s；5个配置/弃用警告 | 支持所覆盖合同未失败；未覆盖本报告全部反例，不是全CI |
| version11规则、双引擎、exporter与ma_infra | 103 passed，1.10s | data-free框架回归；没有真实Rust pyd和湖的Slice D |
| 8.x milestone与fullstrat hooks | 62 passed | 现有规则/实验合同回归；不代表精确60%边界或8.3追买预算正确 |
| version12规则与双引擎 | 93 passed，1.24s | 本组误加载conftest并造成开头披露的临时目录写入；通过不证明none/front不同价格值的接线正确 |
| 新的内存反例 | M01、M02、M03、M04、M05、M09、M10、M11均用明确输入观察到所述分歧 | 未向仓内添加测试文件；数值/输入见各项。M06/M07/M08主要为源码及合同直接验证 |
| Python/Numba请求、cProfile、v12小夹具 | 见第3节 | 仅本机合成数据开销，不是全市场吞吐或实湖I/O基准 |

核心测试的安全重跑方式（必须保留 --noconftest；本仓 conftest 会覆盖 --basetemp）：

```bash
PYTHONDONTWRITEBYTECODE=1 \
NUMBA_CACHE_DIR=/tmp/codex-scratch/numba-root \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
/home/box/.venvs/bt-ci/bin/python -m pytest \
  --noconftest -p no:cacheprovider \
  --basetemp=/tmp/codex-scratch/pytest-minute-core -q \
  tests/test_csv_minute_backtest.py \
  tests/test_csv_minute_backtest_v7.py \
  tests/test_ashare_bars.py tests/test_ashare_session.py \
  tests/test_ashare_fees.py tests/test_ashare_volume_cap.py \
  tests/test_ashare_exdiv_economics.py
```

便宜基准的重跑命令（普通Python一次；另一次加入 CSV_SCAN_HELD_DAY_BACKEND=numba，须核实实际后端）：

```bash
PYTHONDONTWRITEBYTECODE=1 \
NUMBA_CACHE_DIR=/tmp/codex-scratch/numba-root \
/home/box/.venvs/bt-ci/bin/python \
  scripts/research/bench_minute_simulate_hotpath.py \
  --days 30 --codes 16 --minutes 240 --lots-days 10 --reps 3
```

本次没有执行完整生产/benchmark测试集，也没有验证所有股票的真实bar标签、历史ST名称、因子available_at、供应商修订或公司行动表完整度。文档中的09-22回执与本次HEAD不是同一个tip，不能移作本次性能、收益或验收结果。`verified-in-code` 指代码行为或合成回放已证实，不能解释为真实市场样本的发生率或收益损失已经量化；报告没有对这些发生率作推断。

收口时 HEAD 仍为057761a41028540b60e7438afa157635d84c84ba，`git status --short --untracked-files=normal` 无输出；这一检查不包含被忽略的 pytest 临时目录。没有修改、提交或修复任何生产文件；所有建议均留待后续独立实施。

## 按优先级排序的 Top 10

| 排名 | 发现 | 应先做的改动及验收重点 |
|---:|---|---|
| 1 | **M01 · critical · v12混价域** | 分开front信号、raw档位/成交/估值，补非1因子和账户守恒回放；修复前不要据当前NAV判断该书优劣 |
| 2 | **M02 · major · 未来卖款提前可用** | 全市场按实际成交时刻推进现金；09:45/14:55买单不能用后来卖款 |
| 3 | **M03 · major · v11退出均线raw断点** | EOD SMA5改用独立且一致的信号价域，验证除权前后经济等价路径 |
| 4 | **M06 · major · ST档位无日期/板块规则** | 按交易日、板块及上市状态查历史规则，覆盖2026-07-06制度切换与创业板ST |
| 5 | **M04 · major · 8.3追买超出试探预算** | 逐股票独立计算入队预算，所有首买路径保持50%，消除名单前序依赖 |
| 6 | **M05 · major · 8.1止盈边界浮点错档** | 统一业务边界比较，钉精确阈值及相邻tick，保留原开闭区间 |
| 7 | **M09 · major · 公司行动权益漏记** | 独立事件日历确认股份/应收/到账；缺行情不丢权益；明确默认结果是否总回报 |
| 8 | **M08 · major · 缓存无来源/版本校验** | 缓存绑定权威源、域、schema和分区版本；换湖/修数不能静默命中旧值 |
| 9 | **M07 · major · 科创板100股首买** | 共享证券数量规则区分主板100与科创200/1、零股退出和部分成交 |
| 10 | **M10 · major · v7 DataFrame丢非名单日** | 对records/frame采用一致交易日历，重放无名单日的止损、计时和估值 |
