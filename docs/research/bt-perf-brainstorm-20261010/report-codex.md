DONE

MyQuant-backtrader 分钟回测性能独立技术意见（2026-10-10）

结论：#456 的方向值得合入，核心价值是消除动作之间的 Python 扫描；但当前证据不足以无条件放行。先处理或归因 CI 红灯，并做同缓存状态的三路差分。下一刀优先做调用包装与日期上下文；若目标是新进程墙钟，优先做湖读取日期下推、缓存 row group 裁剪。不要动卖点、决策价和账本顺序来换速度。

证据与范围

- 已先执行 `git fetch origin`。基线固定为 `96927c5223370d01b80bd4f7e0f573c7cd1c82c8`；候选固定为 `7ca63b542dd3485a6180a6445624fc6aaa5ee61f`，即 `origin/perf/v653-numba-resume`。下文除注明 PR 新增符号外，现状以该基线为准；两者只有分钟宿主、梯子测试和两份说明文档的差异。
- 已通过 `gh pr view 456`、Actions 日志及 `git diff/show` 读取 [PR #456](https://github.com/baiyibing/MyQuant-backtrader/pull/456)。性能数字是作者记录，不是本次独立复测。
- 本次未运行 Python、测试或真湖回测。检查时三个约定 Python 环境变量及两个湖根配置变量均未设置；未猜盘、未安装依赖。没有据此断言机器绝无可用数据或解释器。
- 本次没有修改代码、切分支、创建 PR、写湖或写缓存；只写本报告。共享工作区 HEAD 在研究期间由基线变为候选，不是本次操作；因此使用固定提交取证，不将工作区漂移当作自己的修改。

现状与瓶颈判断

| 路径 / 符号 | 已确认的实现事实 | 瓶颈假设与适用范围 |
|---|---|---|
| `backtest/research/csv_minute_backtest.py::run/simulate` | 分开装载日线、分钟、exdiv，再按日推进；legacy 的 `held_scan`、`pool_buy`、`post_group` 分相存在。X-02 / 部分 TopK 配置另走 `minute_cash_order.run_chronological_day`。 | 6.53 legacy 的收益不能直接推广到所有分钟书或时序路径；`held_scan` 包括 pandas 切片、限价准备、cursor 构建、回调和账本，并非全是内核时间。 |
| 同文件 `_scan_independent_ladder_first` / `_independent_numba_prefix` | 数字谓词扫描到第一根必须交回 Python 的 bar，返回该 bar 之前的 peak；支持台阶、减仓、回撤、step stop。基线首个动作后继续 Python 尾段。 | 稀疏动作、长安静间隔适合重复进核；密集动作和很短下午窗可能主要消耗在 Python 包装。内核仍检查安静 bar，不是启发式忽略行情。 |
| 同文件 `independent_ladder_first_bar`；`csv_ledger.py::IndependentExitPosition` | 每次包装做 dtype 转换调用、标量拆包；每次前缀遍历代码下 lots 筛 position_id，生成 step_costs、scale anchor。`lots/shares/cost` 属性也可能遍历。 | 重复构造小列表、属性访问与 Numba dispatch 是候选热点。`np.asarray` 对已有匹配 dtype 的 ndarray 通常零拷贝；当前日循环已转 float64/int64，不能无证据称每次复制 OHLC。step_costs 列表到数组则确实需构造。 |
| 同文件 `_slice_day/_previous_rows` 和 `simulate` | day_spans 将分钟切片降为 iloc；日线前缀仍 `df.loc[df.index < day]`，持仓循环还对全部前收盘做 `astype(float).tolist()`。 | `day_spans≈0` 不代表逐日视图、日线布尔筛选和列表已无成本。无 sell_gate 的梯子路径可能根本用不到完整前收盘列表。 |
| `backtest/research/bar_store.py::_MEM/mem_get/mem_put/resolve_day_spans` | 同进程复用 DataFrame 和 spans；全覆盖 wanted codes 才命中。当前没有容量淘汰；返回共享帧引用，“只读”主要是调用契约。sidecar 校验身份及长度、首末日指纹。 | 重复网格 run 已有收益，不应再重复发明内存缓存。变动股票集合可全命中失败，多窗常驻可能吃内存；副作用污染与换页风险比字典查找更重要。首末日指纹不是全量内容哈希。 |
| `backtest/research/ashare_bars.py::read_lake_minute_ohlc/load_minute_from_lake` | 选择列后 `pq.read_table`，随后 `table.filter(time)`；默认线程池 16。保留 volume 用于既有零量日规则，去重 keep-last 后排序。 | 冷湖窄窗可能解码大量窗外数据。线程池并不保证更快，磁盘吞吐、Arrow 内部线程和 RSS 要一起测。不能为了少读列把 volume 删掉。 |
| 同文件 `read_minute_cache/_frame_from_cache_group` | 每个 row group 先完整读取，再 `unique(symbol)` 判断过滤；随后 `to_pandas`、构造 ns DatetimeIndex；同码多组反复 concat/sort。 | 新进程文件命中的成本包含解码、对象构造及合并；小名单读大缓存还有无用解码。现有实现已经是 Arrow parquet 读取，“换 Arrow”本身不是方案。 |
| 同文件 `minute_cache_identity/load_minute_ohlc`；`csv_daily_loader.py` | 有 resolver、schema、浅层 source_snapshot 身份和日线缓存；volume/amount 分钟请求绕过旧缓存。深层原地数据修补需显式更新 snapshot。 | 不应照抄旧文档“无缓存身份”的历史描述。缓存优化必须保留价域、来源、快照及能力差异，不能拿旧无量缓存冒充有量输入。 |
| `backtest/research/st_status.py::_load_cached/bind_st_gate/is_st_on/st_blocks_buy`；`csv_ledger.py::execute_buy` | ST 表按路径 LRU(4)，每 run 绑定；每次买尝试仍标准化代码和日期后集合查询。缺表/行有现存 waiver 语义。 | 不是逐 bar 重读 parquet。主要候选是首次装载、重复归一化；预期小收益。仅路径的 LRU 有同路径文件更新后陈旧风险，长驻研究进程要特别测。 |
| `backtest/research/exdiv_map.py::_read_parquet_frame/_load_factor_series/load_exdiv_ratios` | 已做列和日期/代码下推，失败/空结果有重试路径；保留 start 前 10 自然日 warmup，稳定排序、因子 LAG、事件和跳变 fallback。 | 不能再把“新增列下推”当新优化。重复 run 的图重建、日期标准化/排序及 fallback 多次读取才是候选。要测命中/回退分布。 |
| `csv_minute_backtest.py::simulate`；`ashare_exdiv_economics.py::ExDivEconomics` | 持仓扫描前处理 rescale 和昨收映射；显式经济权益为独立状态机，默认参数 None。 | 默认 6.53 没有开启 economics，不能把其 settle/红股状态列成该配方已证实热点；同样不能为了快删掉默认仍运行的 E-R6。 |

#456：收益、风险和合并意见

作者依据：候选中的 `docs/backtest/note-v653-host-perf-summary-2026-10-10.md` §3 与 `note-independent-ladder-numba-2026-10-09.md` §2.8。固定配方为 version6_53、20251023–20260909、industry、总资金 2700 万、名单预算 1 万、PYTHONHASHSEED=0。

| 指标 | 原前缀路径 | resume 路径 | 可作何种判断 |
|---|---:|---:|---|
| 模拟 | 46.1s | 16.6s | 观察值下降约64%，约2.78倍；还不是严格配对成绩 |
| held_scan | 30.4s | 8.8s | 观察值下降约71%，方向可信，需隔离 JIT/缓存和数据布局差异 |
| post_group | 0.4s | 0.9s | 增加0.5s，绝对量小但提示短窗包装开销 |
| Python 评估 bar | 542018 | 16270 | 下降约97%，比混合墙钟更直接支持算法收益 |
| 分钟装载 | 725.7s | 14.9s | 冷建缓存与文件命中不可归因于 resume |
| 墙钟 | 786.8s | 36.1s | 禁止宣传为本 PR 的21.8倍加速 |

作者报告 `trades.csv/daily_equity.csv/pending_sells.csv` 三文件字节相同，期末净值44,341,528.00、成交9621；本次未取得并独立 hash 原产物。`pool_buy` 6.7→3.4s 不应记入本刀；作者解释为缓存热度，本报告只确认有混杂，未独立验证具体原因。另需注意，542018−16270=525748，与 resume_bars=525763 相差15，说明这两个计数不能直接当守恒分解；应补每窗口计数口径，而非由此断言丢 bar。

实现上值得保留的点：

- 新 `_drive_independent_window` 从 `bar_start` 继续扫描，每个动作仍按 open→close 交给 `advance_independent_exit/fill_side_pending/step_stop_exits/scale_out_exits/peak_dd_clear_exits`，账本没有被编译或并行重排。
- 每次重新取 `cursor.cost=pos.cost`，刷新 lot 成本、scale_steps 和回撤状态，方向正确；不能把这些可变值一股脑提到循环外。
- `first_exit_attempted` 后不再更新 peak，pending/side_pending、强制离场、自定义能力等回退 Python，保住失败离场后的状态语义。大于32个 step lot 的中途回退用 -2，避免从0重放动作。
- `OSKH_INDEPENDENT_RESUME=0` 保留旧前缀路径；`OSKH_INDEPENDENT_NUMBA=0` 可作完整 Python 对照。两个开关含义不同。

仍需核查：

- 新 `first_from/python_tail/count_quiet` 依赖 hm 在日内有序，遇大于 hm_hi 提前结束。湖和文件 reader 排序可支撑正常输入；直接 `simulate()` 外部帧的顺序契约应显式检查或保留参考回退，不能静默以未声明顺序改变结果。
- 动态状态必须逐事件比较，包括阶梯减仓使 lot 删除、原始 first_lot 已离场但 anchor 保留、weighted cost、14:55 加仓后下午成本、32/33 lots、待卖与红股锁定。不能只看最终 NAV。
- `_independent_numba_blocked` 在 driver 和 prefix 重复执行，ladder 参数又重读；新闭包和 `count_quiet` 还用 Python 走跳过区间。这不是 correctness 问题，但解释为何内核快了下午窗反而慢。
- 新三项测试覆盖安静减仓间隔、resume OFF、跌停顺延冻结 peak。现有 `_same_trades` 比的是 side/reason/shares/price、部分状态和跌停计数，没有覆盖全部成交时间、现金、commission、pending/audit 字段，不能替代全产物差分。

截至本次查询，PR OPEN、MERGEABLE，但 [候选 CI](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/38020252589/job/114119457627) 为 FAILURE：328 failed、8810 passed、71 skipped、24 deselected。日志可见 TopK 字节基线出现 `skip_st` 字段差异、Mode B 缓存预期 hit 实为 mem、6.51–6.53 baseline owner KeyError 等。它们暗示存在已有基线债务，但不能据此豁免所有失败。[基线 master CI](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/38015123464/job/114103574411) 也在 pytest 阶段失败；本次未取得它的有效失败明细，故没有完成失败集合归因，不能声称328项均非本 PR 引入。

合并建议：值得推进，当前不建议直接合。至少在同一依赖环境对 base/head 建立失败集合与原因对照，处理新增回归；并补下述配对实验。不要用重新录 golden、关闭 ST 或吞掉缓存身份校验使 CI 变绿。文档中“尚未提交/本地工作区”的措辞在7ca63b5已陈旧，应同步改成提交事实；这不影响算法，但影响后续研究准确归因。

下一刀：9项可单独交付的建议

以下收益均为假设或验收目标，不能累加为承诺。所有项对固定输入、价域、规则和快照，均要求经济产物字节不变；计时、cache命中标签和性能计数可以变化，但业务 stats 不能借机忽略。内部缓存文件格式若变化必须单独版本化，不能等同于允许业务输出漂移。

1. P0：把 Numba 静态包装准备移动到 window/cursor 创建时。
   改哪里：`csv_minute_backtest.py::independent_ladder_first_bar/_independent_numba_prefix/_independent_numba_blocked/_drive_independent_window`。一次绑定数组、ladder 数值、静态 fill 能力和开关；保留每动作后的 pending、peak、cost、scale_steps 动态检查。第一片只减少重复字典、环境变量和转换调用，暂不引入复杂 lot 缓存。
   预期收益：目标压低包装时间并收回部分 post_group 的0.5s回退；对 held_scan 设5%–15%的试验目标，未测不承诺。数组本已零拷贝时收益可能很小。
   风险：误将可变字段冻结、改变 dtype、对不同能力套同一快路。是否改结果字节：不应。
   怎么测：分开测包装/内核/动作执行耗时和调用次数；安静窗、连续动作窗、短下午窗各跑；与全Python及resume OFF比全部状态、三CSV和费用。

2. P0：去掉仅为性能计数重复扫描安静 bar 的 Python 循环。
   改哪里：候选 `_drive_independent_window::first_from/count_quiet`。在已验证有序 hm 上一次算有效窗口 [lo,hi)，再按索引差算 gap，推进仍由原内核决定；无序输入回参考处理。不是启发式跳行情。
   预期收益：将计数从 O(覆盖bar数) 降到 O(动作数)，尤其长安静间隔；收益上限是现有计数循环占时，不能再宣传“省掉52万次撮合”。
   风险：hm_hi含端点、午休、缺bar、重复hm、空窗、quiet_slice统计口径出错。是否改结果字节：经济文件不应；要求计数在定义清楚后也一致。
   怎么测：对每窗记录总有效bar/前缀/恢复/实际执行/离场后未访问数，建立互斥守恒；端点14:55/14:56和无序输入专测，测profile开关两档。

3. P0：按 code/day 复用日线前缀位置、分钟视图和限价上下文。
   改哪里：`csv_minute_backtest.py::_previous_rows/_slice_day/simulate` 与 `csv_simulate_loop.py::DayBuyQuotes`。有序日索引用 searchsorted 定严格小于 day 的终点；仅需昨收时取标量，需要 sell_gate 的路径才生成完整历史列表。让同日持仓/买侧共享只读数据上下文，账本状态不缓存。
   预期收益：减少 O(日线长度)布尔掩码和重复 pandas 对象，对多独立持仓/长窗可能比继续优化数字核更划算；先看样本 profile，占比低即停止。
   风险：使用当日close造成前视、停牌日/缺昨收处理改变、names as-of或exdiv参数不在缓存键中。是否改结果字节：不应。
   怎么测：记录切片/列表构造次数；同码多信号、缺当日/缺前日、除权日、名称变更及14:55加仓对照。`tests/test_day_buy_quotes.py`、`test_independent_held_order.py`及全窗三CSV。

4. P1（冷湖优先）：将分钟日期过滤下推到 parquet 读取。
   改哪里：`ashare_bars.py::read_lake_minute_ohlc`，把当前读取后 time filter 提前到读取 filters，并保留结果域核验；在现有时间类型/毫秒范围上做，不改湖文件组织。
   预期收益：若股票文件含多年数据且 row group 有有效time统计，窄窗可显著少读少解码；若单组覆盖全部历史，上限可能很低。只改善冷湖/禁缓存路径，不应在14.9s文件命中上记功。
   风险：时区、上下界与schema不符，漏volume导致零量日语义变动。是否改结果字节：不应。
   怎么测：旧/新 reader 的列值、顺序、dtype、index、重复分钟标志逐一比较；包含端点、乱序原文件、整日零量、v11 volume-only及X-04 amount。测实际读取组数/字节、RSS，workers 1/4/8/16和Arrow线程组合单独试验。

5. P1：缓存读取先裁剪不需要的 row group，再一次拼接同码分片。
   改哪里：`ashare_bars.py::read_minute_cache/write_minute_cache`。利用可信 symbol min/max 或版本化目录判断组与 wanted codes 是否相交；统计缺失/混合组走现有安全路径。积累同码chunks后只concat/sort一次，保持原组顺序和重复项规则。
   预期收益：小名单复用大窗缓存可少解码很多；全市场全命中主要减少多组同码concat/sort，无小名单裁剪收益。
   风险：元数据不可信或sidecar与parquet不同代，误删有用组；新拼接对相同时间戳排序顺序不同。是否改结果字节：业务不应；缓存元数据可版本化新增。
   怎么测：单码单组、多码混合组、同码跨组、统计缺失、subset/partial命中全部与原reader比较；测解码行数和peak RSS；`tests/test_minute_cache_identity.py/test_bar_store.py/test_unified_exit_modeb_load.py`分清mem与file命中。

6. P1：给已支持梯子路径增加按列数组视图，延迟 pandas 物化。
   改哪里：`ashare_bars.py::_frame_from_cache_group/read_minute_cache`、`bar_store.py`与分钟宿主适配点。先做内部opt-in原型，用Arrow列转float64/int64数组和day_spans，旧DataFrame接口仍可用；不用给全部策略改接口。
   预期收益：削掉热文件14.9s中的一部分to_pandas、DatetimeIndex与对象开销；parquet解码仍在。避免同时持有完整双份表示，否则RSS可能更坏。
   风险：chunked/null列并非天然零拷贝、缓冲区寿命、ns时间精度、数组可写共享、ymd字符串膨胀；这是九项中改动面较大的一项。是否改结果字节：业务不应，缓存格式变化必须有新schema身份。
   怎么测：先离线拆出decode/to_pandas/index构造时间和RSS，再决定是否实现；数组与旧帧逐值/dtype/日边界比较，全窗及能力回退对照。不要宣称mmap压缩parquet能省掉解码，也不要引入Redis/GPU。

7. P2（多配方重复run可升P1）：bar_store 支持受限驻留和部分集合复用。
   改哪里：`bar_store.py::mem_get/mem_put/_MEM`、`ashare_bars.py::load_minute_ohlc`和日线loader。返回已有交集，仅为缺失码读文件/湖；增加可观测内存预算及LRU逐出，保持文件缓存为跨进程来源。缺数据不得作为永久负缓存吞掉读取错误。
   预期收益：变动名单网格少重复解码，长驻进程避免换页；单次run和现有完全命中的run几乎不获益。
   风险：共享可写帧污染、跨snapshot误用、淘汰引起性能抖动、部分加载写回丢码。是否改结果字节：业务不应；cache标签可显式变化。
   怎么测：A→A+B→B→换snapshot→强制逐出序列；记录每码decode次数、RSS高水位，输入帧运行前后指纹一致；参照`tests/test_bar_store.py`，不可用深拷贝所有帧作为默认防护而抵消收益。

8. P2：ST 检查准备到每日边界，缓存身份包含源版本。
   改哪里：`st_status.py::is_st_on/st_blocks_buy/_load_cached/bind_st_gate`及账本调用适配。对已保证规范代码/日期的内部路径直接查当日frozenset，通用API仍做标准化；冷加载考虑读过滤后的ST行。长期缓存以显式快照/文件版本失效，避免仅路径缓存陈旧。
   预期收益：买尝试多时省字符串处理，整体预计小，先以ST调用计数和耗时证明优先级；不把ST集合查询列为已证实首要瓶颈。
   风险：把信号日误当成交日、非规范代码绕过、同路径更新和waiver被静默改写。是否改结果字节：固定快照不应；修复陈旧缓存属于另一个正确性对照，不能混算性能。
   怎么测：ST加入/退出日、补仓/追买/首买共门、缺表/行、同路径新版本、规范与非规范输入；`tests/test_st_status.py`及run()的skip_st与成交差分。不能关ST换取更快或更好收益。

9. P2：按输入身份复用不可变 exdiv 图，先测下推回退次数。
   改哪里：`exdiv_map.py::load_exdiv_ratios/_read_parquet_frame/_load_factor_series`。复用键需包含两个来源及版本、代码集合、日期窗、noise_eps/fallback_eps、warmup政策；缓存的是解析结果与诊断，不是`ExDivEconomics`可变账本。观测过滤失败/空结果重试，不能直接删除兼容路径。
   预期收益：同进程重复run可省解析/排序/图重建；首跑或held_scan占绝大部分时收益低。按已存在t_exdiv_s上限决定是否做。
   风险：丢失首日LAG、改变稳定去重与阈值、漏回放skipped诊断、把因子缺失当可靠负缓存、共享权益状态。是否改结果字节：固定有效输入不应。
   怎么测：`tests/test_exdiv_map.py/test_exdiv_hold_hits.py/test_exdiv_ref_fen.py/test_ashare_exdiv_economics.py`，首日事件、缺因子、噪声边界、fallback、两次run及同路径换snapshot；比较k图、诊断、成本/peak、昨收限价、权益锁和现金，不只净值。

共同测量与验收方法

- 先建立三路：固定base的原前缀、固定head的resume OFF、固定head的resume ON；另以NUMBA=0作为参考。前两路须先一致，才能分离循环重构与加速本身。不要把不同策略版本或不同ST政策放进性能对照。
- 分三种环境报告：冷建文件缓存、新进程命中文件缓存、同进程mem命中。冷文件与冷OS页缓存不是同一概念；不能控制就如实标注。JIT首次编译、磁盘JIT缓存加载和已热签名分开记录。
- 固定Python/pandas/NumPy/Numba/Arrow版本、CPU线程数、源码、湖snapshot、pool哈希、命令、规则profile、开关与输出路径。遵循仓库解释器解析顺序；这是一份后续实验协议，本报告没有实际运行这些实验。
- 热态至少5次，交替AB/BA，报告中位数、范围与样本数；独立计时run不要开cProfile。另做一次采样/函数profile归因包装、lots属性、pandas和解码；记录RSS、CPU时间、读字节与实际解码行数。
- 同进程复用行情，每次必须重新创建SimState/positions/经济权益对象；验证行情输入没有被上个run改写。出场状态、现金和顺序绝不能跨run复用。
- 经济结果逐字节比较trades、daily_equity、pending_sells及原有其他固定产物；schema与业务stats也比较。仅明确列出的计时、运行路径、性能计数、cache状态可单独归类，不用“所有stats不稳定”概括排除。
- 增补边界：T0、T+1、红股锁、开盘/成交价跌停、先减仓后trail、未完成/延迟成交、32/33 step lots、同码不同信号、14:55前后、无动作/密集动作、非默认fill和回调回退。用事件级差分定位首个分歧。当前测试文件是起点，不等于已覆盖全部矩阵。
- 接受条件是等价证据成立且目标分相稳定改善；例如包装优化应让post_group接近同缓存旧路径，不能仅用held_scan下降掩盖其他路径退化。若测得低于噪声，保持简单实现。

绝不动的边界

- 正确性与决策价：保留`minute_held_scan_core.py::HeldMinuteCursor.advance`及`minute_cash_order.py::advance_independent_exit`的相位、第一次尝试冻结、pending重试语义；保留stop/trail比较式、epsilon、peak_gap和strict/非strict边界。不启用fastmath，不改float32，不重排浮点求和来换SIMD，不用“差一点没关系”放行字节漂移。
- 行业档位与账本：`market_layer.py/ashare_session.py/ashare_fees.py/csv_ledger.py`的Decimal HALF_UP涨跌停价、板块/日期/ST档、T+1与红股锁、lot取整、费用调用粒度、资金不足异常或skip_cash、同码独立信号身份保持。不并行结算同一账户，不把账本搬进Numba/GPU，不改price-add前后现金次序。
- 分钟假设：普通池买14:55及现有回退、追买09:45及回退、各书特殊时点、stop close/hl、TopK执行选项、X-02/X-04、尾盘窗口与容量都按原开关。不能提前用未来high/low/完整桶volume选价；不能用抽样bar替代完整数字谓词扫描。scan/touch/mark三者不可混为一体。
- 价域和权益：raw分钟、各书front信号约束、E-R6映射、fen opt-in与显式economics分别保留。不能双重除权、默认打开economics、将成本重标与股数权益混同。除权调整必须仍在原扫描前执行。
- 数据与来源：只消费配置湖，resolver和缓存身份不削弱；不写源湖，不探盘，不下载、不vendor merge。缺bar、零量日、重复分钟及volume/amount能力合同不变。已发现ST/exdiv的局部waiver属于现存源码事实，不能借性能任务推广成全局“缺数据返空”，也不能顺手改变其既有行为。
- 仓库边界：本仓向量化研究；不复活Cerebro/Rolling，不引入LEBS/MockQMT/live栈，不用L2扩展交易包，不重写MyQuant winner_ratio feeder。HELP_LOCK、presets和固定热路径fence不扩张；6.53继续PENDING，不借性能证明批准新书、录golden或覆盖历史研究比分。

正确性依据以仓库`docs/backtest/engine-ashare-correctness.md`、`minute-fill-policy-ssot.md`、`ssot/backtest-rule-principles-ssot.md`和本次固定提交的实际实现共同核对。本文没有重新裁定市场法规或推荐策略收益；建议顺序只服务于相同研究合同下的执行性能。
