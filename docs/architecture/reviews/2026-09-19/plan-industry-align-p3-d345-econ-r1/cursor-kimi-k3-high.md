<!-- agent=cursor:kimi-k3-high cmd-prefix=/home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/node /home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/index.js --model kimi-k3-high -p --output-format text --trust -f --mode ask --workspace /workspace/wt-p3-d345-econ-plans <prompt> -->
评审完成。以下为独立评审意见（已读取五份文档全文、核对基线 diff、静态核验约 40 处锚点，并按本席位职责对关键 fallback/None/分叉语义做了最小动态实验）。另外两席已完成意见（pattern-evidence / dissent-steelman / domain-safety）已交叉核对，其可复现的事实性发现我均独立验证后采纳或修正评级。

---

# 评审：P3 δ3–δ6 + index（docs-only 包）

## 基线核验（先行事实）

- `git rev-parse HEAD` = `1e9994e88a67d0f5f651953fa7ad0e57b59a3677` ✓；`1049b904…^{commit}` 解析成功且为 HEAD 祖先 ✓；base→HEAD 恰好只有五份 Markdown，tracked worktree/index 无其他 diff ✓。生产/测试源码与 IMPLEMENTATION_BASE 一致，锚点可在基线核验。
- 五份文档 §8.3 的 22 文件冻结数组与各自 §9 表逐项同序一致，且为 δ1(10)/δ2(17) 超集；22 个文件全部存在。§8.2 引用的 13 个测试文件 + 4 个 gate 脚本全部存在；11 处具名测试引用均找到 `def`；pytest marker 与 `.github/workflows/python-tests.yml:27-43`、`:49-56` 一致。未发现幽灵命令/幽灵测试。

## 本席位动态实验（in-memory，无文件写、无湖/CLI）

用纯 dict 夹具直接调用真实 `simulate_v7` / `market_layer` / `ashare_session` / `csv_common._pool_names_asof`（pandas 以内存 stub 满足 import）：

1. **ST 优先于未知板块**：`limit_pct("999999.SZ","*ST甲")=0.05`，非 ST 未知前缀=`None`；`limit_prices(10.05,10%)=(11.06, 9.05)`（Decimal HALF_UP，11.055→11.06）✓ — 证实 δ3 `market_layer.py:57-84` 与"未知代码不总等于 None"。
2. **None 双门 fail-open**：`skip_buy_at_limit(999,None)=False`、`defer_sell_at_limit(0.01,None)=False`、`session_limit_prices(…,None)=None` ✓（δ4 `ashare_session.py:73-78`）。
3. **名称 resolver 边界**：`pool_names_by_day={}` 优先于 flat map（返回 `{}`，无 fallback）✓；游标单调、回查早日不 rollback ✓；**返回同一可变 dict（`d1 is d3` == True）**——δ3 §2.1 的"不保证快照独立"警告经实验坐实；`flatten_pool_names` 直传空串会覆盖为 `""` ✓。
4. **v7 未知板块首开（自然路径）**：`skip_unknown_board`、无持仓 ✓（δ4 真值表 v7 行）。
5. **held-None 自然不可达不变量**：ST 名+未知前缀自然首开成功（5% 档买入 2000 股）后，spy 统计 `session_limit_prices` 在后续 held 会话 **0/3 次返回 None**——在"flat names + closes 一次物化"的当前输入合同下，held-None 只能由 seed 构造到达。这动态证实了 δ4 :53 只部分披露的事实（见 🟡-3）。
6. **δ6 经济残留（v7, k=0.5）**：D1 买 20000@10（cash 20799800），D2 除权 raw close 5 → shares 仍 20000、cash 不变、equity 20999800→20899800（−100000，无补偿）✓ — 与 δ6 B1/B2 oracle 语义一致。

## 🔴 必须修

**R1. δ4 §2.2 书侧真值表把"未知板块→`skip_unknown_board` 早拒"写成无条件 as-built 事实，遗漏 qlib 固定 band 例外。**
`docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md:38`（及 :39 minute 行、:107 DoD）。实现上 `csv_common.py:80-82` 在 `qlib_limit_pct is not None` 时直接返回固定 band、绕过板块/名称判断；该参数不是死接口——`csv_strategy_books.py:713`、`:788` 为两类 topk 书实际接线 `QLIB_LIMIT_PCT`。对非 ST 未知前缀 + prev_close=100 + pct=0.095，helper 返回 109.5/90.5 而非 None，不会进入 `skip_unknown_board`。δ3 :32 已正确记录此例外，但 δ4 声称"每份均可独立审阅"（index :20），其真值表自身不成立。这是"已核实 as-built"表里的事实性错误，会误导 Slice B pin 作者选错入口。最小修：δ4 §2.2 表头/相关行加"默认 named-band、非 ST、`qlib_limit_pct=None`"前提，并加一行固定 band 对照。纯文档勘误，不动生产。（与 pattern-evidence PE-01、domain-safety DS-02、dissent DS-4 一致，我独立复核属实；按本评审 rubric"事实错误/会误导实现"升为 🔴。）

## 🟡 应修（均可进文档勘误 / Slice 设计缺口，不阻主船）

1. **δ6 :28 把书 NAV 写成普遍"raw close"**。`csv_ledger.py:173-178` 只消费调用方给的 close；`csv_daily_backtest.py:584-587` 对 front/back/qlib_day 跳过 exdiv，此时 mark 不是 raw 域。3000→2500 残留仅在 none/raw 输入成立。应改为"按输入 bars close 估值；none/raw 路径才是 raw mark"，防止未来 C 对复权输入重复补偿。（PE-02/DS-01，属实。）
2. **δ4 缺 held-None 自然可达性表 + δ3→δ4 交接门**。我的实验 5 动态确认：当前输入合同下 v7 held-None 自然不可达（首开必经 `:389`/`:392` 双重非 None，names 每 run 扁平）。δ4 :53 只披露"seed 属测试构造"，未写此不变量；而未来 δ3 `.1=C`（逐日名称）会使其**自然可达**（D1 *ST 买入、D2 摘帽→None）。应在 δ4 加"自然不可达/seed-only/输入变更后可达"三态表，并在 δ3 C 人裁处挂强制交接：重裁 δ4 可达性矩阵。（dissent DS-3，属实且重要。）
3. **δ3 把 v7 context→names 真实接线 pin 写成"如需"（:120）**。现有 `test_d2_v7_main_keeps_real_context_chain_with_nonempty_pool` 把 `load_pool_names_by_day` stub 为 `{}`、mock `simulate_v7`，只断言 exdiv 透传（`tests/test_exdiv_refprice_engines.py:689-705`）；ST 测试手工 flatten（`tests/test_csv_minute_backtest_v7.py:276`）。若 `:583-584` 的 `names=names` 被误删，现有测试全绿。Slice B 应把至少一个非空双日期 `load_pool_names_by_day→load_limit_context→simulate_v7` 接线 pin 列为必需。（dissent DS-5，属实。）
4. **δ5 部分成交缺"首触发零成交后的扫描续行"状态设计**。`scan_held_day` 首个触发即 return（`csv_minute_backtest.py:287-291`、`:318-329`），每 lot 每日只调一次、随后单笔 `_sell`；cap 拦截首触发后没有续行游标，D1–D7 的数量 oracle 全部可被"只实现 `min(req,eligible,R)` 的参考账本"通过。`.3=A`（允许部分成交）收口前必须先答 `首次触发×零/部分/全成×后续触发×桶结束` 状态表。（dissent DS-1，属实。）
5. **δ6 B6 无 bar 生命周期 oracle 缺估值真值**。`market_close_mark` 无当日 bar 回落最近历史 close（`csv_ledger.py:173-178`）：纯现金 c=1、除权日无 bar、mark 仍 10 时，确认应收 100 会使 NAV=3100≠3000（重复补偿）。B6 需补无 bar 数值轨迹与 pay/list 日落在无行情会话时的转换政策。（dissent DS-2，属实。）
6. **δ6 缺登记窗口期初权利决策**。清仓即删持仓（v7 `:250`；ledger 卖出循环），"登记后卖光、到账日在后"的应收无法从 positions 反推。B 设计须裁定"完整重放 vs 带版本期初 entitlement 快照"。（dissent DS-6，属实。）
7. **δ5 D6 时间前缀 oracle 未交接 loader 层前缀敏感性**。`ashare_bars.py:370-371` 按**整日** volume 求和决定去留：追加当日 14:55 正量会改变 09:30 零量记录是否保留，从而影响 v7 早时点 stop 评估。D6 的桶级前缀保证不能端到端成立，应在 B1 固定为 as-built 残留。（domain-safety DS-03，属实。）

## 🟢 可选

- §8.1 全路径白名单对环境敏感：任何额外 untracked 文件（如本轮评审产物目录）都会使其 exit 1；index :26 已披露"exit 0"是在只含五文档的发布副本取得。建议在 §8.1 显式注明"需在干净树/发布副本执行"，避免未来执行者误报。
- §8.2 文字"不允许 CLI"与整文件 pytest 选择存在张力：`tests/test_csv_minute_backtest_v7.py:212-238` 含 tmp_path 下直调 `main()` 的既有单元测试。建议把禁令限定为"宿主/真实 I/O 回测"。
- δ6 锚点 `exdiv_map.py:233-239` 是签名/docstring 区，`k=prev_cum/cum` 机制实际在 `:300-316`；配对的 `:288-319` 已覆盖，仅锚点略松。
- index :24 的统计（85 锚点/41 链接/316 路径/11 具名测试）我核验了全部具名测试、冻结文件、gates、CI 行，未逐项重数总量；不影响结论。

## ✅ 做对的地方

- **无 δ6 C creep**：Mode B `shares/=k` 被多重显式隔离（`unified_exit_modeb.py:421-424`、`:805-806`、`:1029` "no cash dividend"；δ6 F-R3/F-R4、:42、:72、:87、:147；index :16）。生产 shares/cash/NAV 变更必须显式 `.1=C` + 独立实施案，文本闭环。
- **无 production-freeze 泄漏**：base→HEAD 仅五文档；默认 A/A/B/A 在四 plan 头部与 index 完全一致；顺序 δ3→δ4→δ5→δ6 互相引用无矛盾；22 文件冻结数组四份逐字一致且为 δ1/δ2 超集。
- **P1/P2/P4 无 scope bleed**：全部维持挂起；触边处均显式要求重裁（δ4 :92→P2、δ5 :106→P1、δ6 :98→P2、δ6 F-R8→P4）。
- **锚点质量高**：我静态核验的约 40 处 file:line（含 δ3 的 resolver/接线/v7 平铺、δ4 的七条路径、δ5 的 loader/量接线、δ6 的 ledger/v7/Mode B）除上述 🔴/🟢 外全部属实；具名测试 11/11 存在且行号吻合（如 v7 :254/:263/:276、predicates :122/:139/:154/:173、daily :944/:969、minute :521）。
- **oracle 算术自洽**：δ5 D1（B=250→成交 200/R=50）、D2（200+100=300）、D4（卖 200 留老 100+新 200）、D7（15bp/min5：2×max(1.5,5)=10 vs max(3,5)=5，与 `ashare_fees.py` QLIB_PORTANA 一致）；δ6 B1/B3/B4/B5 的守恒代数（含 k=0.9 不可识别性例子）全部验算正确；B1 类残留经我的实验 6 动态复现。
- **诚实边界**："日期 as-of ≠ 可得性 PIT"（δ3 :48）、"零量过滤 ≠ cap"（δ5 F-R2）、"k 不可分解事件"（δ6 F-R4）、"不挪用 δ1/δ2 历史 passed 数"（§8.4）等否定性声明准确且与代码一致。

## 总裁决

**GO-WITH-NITS** —— 主船（docs-only 范围、默认推荐、冻结与人裁闸门）事实扎实、无生产泄漏；🔴 R1 为单点文档勘误（加 named-band 前提限定），连同 🟡-1/2/3 在行裁引用对应表格前回填即可，均为 docs-only 修改，无需重审实质内容。

## 建议人裁表

| 刀 | 建议 | 条件 |
|---|---|---|
| δ3 | **A**（.1/.2/.3 均 A） | Slice B 把 v7 names 真实接线 pin 列为必需（🟡-3）；未来 .1=C 时强制重裁 δ4 可达性矩阵（🟡-2） |
| δ4 | **A** | 先回填 🔴 R1 真值表限定 + 🟡-2 可达性三态表；fail-closed/显式 policy 仍须 .1=C 另案 |
| δ5 | **B（仅设计）** | .3=A（部分成交）收口前必须完成 🟡-4 状态/续行矩阵；p 不给生产默认；D6 标注桶级 vs loader 级前缀边界（🟡-7） |
| δ6 | **A**（需要账本设计时可另选 B） | B 设计必答 🟡-5 无 bar 估值与 🟡-6 期初权利；生产 shares/cash/NAV 仅显式 .1=C + 独立实施 PR |
| P1/P2/P4 | **维持 deferred** | 本包无任何重开证据 |

## 是否可进人裁

**yes** —— 可在回填上述 docs-only 勘误后进人裁；人裁 GO 前仍禁止任何编码。
