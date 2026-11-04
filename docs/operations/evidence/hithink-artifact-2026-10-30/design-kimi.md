<!-- agent=kimi cmd-prefix=C:\Users\Stock\.kimi-code\bin\kimi.EXE -m kimi-code/k3 --output-format text -p 你是资深 A 股量化交易系统评审专家。请评审下面这份设计稿。

【待评审文档】D:\PycharmProjects\MyQuant-backtrader\_agent_runs\pr531_implementation_20261030\bt\docs\operations\hithink-artifact-implementation-2026-10-30.md
请先用读文件工具读该文档全文；需要时读仓内相关代码/文档取证（以事实为准）。

【硬约束】
- 只输出评审意见。绝对不要修改、创建、删除任何文件，不要运行任何写操作。
- 证据引用纪律：`file:line` + 最多 5 行关键片段即可，禁止整文件/整段源码粘贴
  （历史教训：源码 dump 导致超时零产出）；评审意见本体控制在 300 行内；
  时间或上下文吃紧时，优先保 🔴 条目与总评，🟢 可舍弃。

【并行轮次说明】
本轮为并行 fan-out：各评审员输出实时写入 `D:\PycharmProjects\MyQuant-backtrader\_agent_runs\pr531_implementation_20261030\design-review/_parallel/<agent>/<agent>.md`。
完成时点不定——若你在该目录读到其他评审员的**已完成**意见，可交叉核对
（引用其条目编号，如 kimi R1；发现其误判，凭代码/实验证据指出并标注）；
没读到就独立完成，**不要等待或轮询**其他评审员。

【特别考虑】
0) 对齐中国 A 股量化程序黄金准则与业内最佳实践，参考业内成熟开源工具。
1) 小团队：不必按券商/公募「全栈合规工程」要求自己，把有限精力压在「会亏大钱或不可逆出错」的几件事上，其余用清单和习惯补齐。
2) 主程序未上线、还在模拟柜台阶段：尽量把方案和意见趋向「激进一次到位版」。
3) 方案会经过多个专家多轮评审：修订后的意见要逻辑一致自洽，不要自相矛盾。
4) 认真阅读分析现有文档和代码再作答，尽量利用已有基础实施，参考性能基线，慎重回答。
5) 本地 redis/数据库已就绪、国金 miniqmt 已登录；把握不准可读代码或做实验，以事实为准。

【裁决原则（重要）】
- 视自己与其他评审者为同行专家，**参考学习、互相验证、取长补短**：结论交叉核对、补彼此盲区，而非单纯挑错。
- **事实类断言**（函数位置 / SQL / 行为 / 数值等可验证项）→ **以代码与实验为准**：读代码取证，把握不准时跑最小实验，不靠票数下结论。
- **经验/取舍类断言**（该不该这样做、风险量级、更稳的写法）→ **以业内 A 股量化惯例与成熟开源实践为准**。
- **SSOT 一致性检查**：若方案涉及数据格式/符号规范/配置键/API 契约等，**必须对照仓库 SSOT 文档**（`docs/backtest/data/symbol-format-ssot.md`、`docs/SSOT.md`、`docs/operations/disclosure-data-source-ssot.md` 等）检查是否冲突。若方案与 SSOT 不一致，标记为 🔴 并指出具体 SSOT 文件及条目。
- **★ 安全阀/超时/并发类设计，必须跑最小实验验证行为**（不只读代码！）：timeout / budget / safety-valve / circuit-breaker / 并发锁 / 异步 / fallback / 重试——这些 bug 藏在 stdlib/框架行为里（如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效），**读代码看不出来**。实验格式：构造 slow fn + tight budget → 测调用方**何时返回**（`time.monotonic` 对比 budget_s vs 实际）。2026-07-04 实测：option-X budget docstring 宣称 "releases caller" 但实际 8s 才返（非 1s budget）——**docstring 不可信，实验为准**。**实验结论须附可复现脚本 + 完整原始输出**（含进程 pid/存活检查等），与官方文档/CPython 源码矛盾的结论标注「建议主持裁/下游复核」。2026-07-16 教训：r3 kimi 实验「subprocess.run(timeout) 不杀子进程」结论错，r4 qoder 引源码 + 主持裁亲自实验（child TERMINATED）才纠正——下游 incorporate 实验断言须亲自复现。

【输出格式】
按严重度分级，每条尽量带 file:line 证据：
- 🔴 必须修（事实错误 / 会误导实现 / 逻辑矛盾）
- 🟡 应修（设计缺口 / 风险）
- 🟢 可选（nice-to-have）
- ✅ 做对的地方（保留）
末尾给一句总评 + 是否可进实现。

【你的评审侧重】优先**跑实验验证关键行为**：对 timeout/budget/safety-valve/并发锁/异步/fallback/重试类设计，构造最小实验（slow fn + tight budget → 测调用方何时返回）。读码不够时动手测——**docstring 不可信**（docstring 宣称的行为可能被 stdlib/框架吞掉，如 `ThreadPoolExecutor.__exit__`→`shutdown(wait=True)` 让超时从不生效）。保持这个习惯。 <prompt> -->
• 实验已确认两个方向。再快速核 SSOT/符号规范与 EVENT_SCHEMA 锚点。

• 评审完毕。以下为评审意见（kimi 侧；`_parallel/claude/claude.md` 内容实为其运行失败的空转输出——它声称"文档没传过来"，非有效评审，无法交叉核对）。

  # 评审意见：hithink-artifact-implementation-2026-10-30.md（PR531 v6）

  ## 取证情况

  - 被审文档 29 行，是 plan v6 的实施合同缩写；逐条与 `docs/operations/plan-corp-actions-hithink-channel-2026-10-29.md`（pr531_lake_audit worktree 版）核对，**未发现与 plan 的实质性偏离**。
  - plan §3 代码锚点逐一复核**全部属实**（`bt/scripts/data/pull_corp_actions_incremental.py`）：`initialize()` :185、`pull()` :371、`assemble()` :484、validate_base 的 `record_date is None → raise` :553-554、init-only 冻结检查 :646；`EVENT_SCHEMA` decimal128(24,12) :50-54；`wind_code()` 只收 `\d{6}\.(SZ|SH|BJ)` :76-79；`decimal_value()` 用 `pa.scalar` 做精度溢出 fail-closed :83-90；`Run.write` tmp+`replace` :153-159。
  - `ashare_exdiv_economics.py`：`pay_date: str` 必填 :24、`list_date` 缺省回退 ex_date :123、`_date(None)` 抛错被吞为 `invalid_event` :132-134 —— plan §4.8 的三条事实断言全部属实。
  - SSOT：本仓 `docs/backtest/data/` 下**不存在** prompt 举例的 `symbol-format-ssot.md`（ls 实测）；符号规范事实 SSOT 即 `wind_code()`，plan 让 `thscode` 走同一校验，无冲突。

  ## ★ 实验（评审侧重项）

  设计唯一涉及"框架行为可能吞掉语义"的点是 1.3 producer 的 HTTP（plan §4.2：「走 stdlib urllib，不引新依赖」）。**两份文档均未规定 connect/read timeout 与重试预算**。实测 stdlib 默认行为：

  ```python
  # 本地 server accept 后永不响应（sleep 8s 再 close）
  urllib.request.urlopen(url)            # 无 timeout
  # → RemoteDisconnected at 8.03s（全程阻塞，直到对端关闭；对端不关则永久挂起）
  urllib.request.urlopen(url, timeout=2)
  # → TimeoutError at 2.03s（按预算返回）
  # python 3.12.13, pid 7560, 两次实验独立进程复现
  ```

  结论：urllib 不传 `timeout` = 无限阻塞（`socket._GLOBAL_DEFAULT_TIMEOUT` 为 None）。合同只写了「失败不得产出完成标记」，挂起不是失败——producer 会无声楔死，操作员只能猜。

  ## 🔴 必须修

  无事实错误或逻辑矛盾。

  ## 🟡 应修

  1. **producer HTTP 必须钉死 timeout 与重试预算**（plan §4.2 / 合同 line 7 均缺）。实验证实不写 `timeout` 即无限挂起。建议合同补一句：connect/read timeout 显式值（如 10s/60s）、总预算、重试次数与退避；「下载重试测试放在 1.3」（plan :198）不能替代设计期给出预算——否则测试没有可断言的合同。
  2. **预签名 URL 5 分钟过期 vs 重试的交互未规定**（plan :51「拿到立刻下载」）。若下载中途失败时 URL 已过期，重试必须**重新走 download-url 请求**而不是复用旧 URL；现文未区分，实现者容易写出「拿旧 URL 死循环 403」。
  3. **合同 line 10「覆盖探针失败记录为 unknown」措辞有歧义**。plan §4.3 的语义是探针失败/证据不足 → **落 D 阻断**；「unknown」易被实现者读成一个可放行的中性分类。建议改为「探针失败 = D 类阻断，不作无事件证据」，与 line 11 的 3002 条款语气对齐。
  4. **幂等返回的"请求一致"未定义**（合同 line 10：「完整目录只在所有绑定校验通过且请求一致时幂等返回」）。manifest 绑定了宇宙/窗口/fetched_at，但 BT 侧 `--artifact-dir` 重复导入时「请求一致」比较的是什么（当前 run 的宇宙 sha256 + 窗口？）没写。plan §4.2-5 的续跑合同较完整，合同作为实施入口应直接引用或抄全，避免实现者自由发挥。

  ## 🟢 可选

  5. hithink `thscode` 的北交所后缀格式未在合同中钉死（`wind_code()` 只收 `.BJ`）。首跑时若 hithink 用其他后缀，BJ 码会整批落 `codes_vendor_unknown`——机制上 fail-closed 无风险，但建议在验收清单（line 23）加一条「BJ 码身份抽查」。
  6. `ex_date_ms → Asia/Shanghai`（plan §4.3）：若供应商存的是 UTC 零点还是上海零点未实测区分，parity 集合恒等能兜住系统性 off-by-one，但建议在 PR-A 测试里加一条已知除权日的精确断言。
  7. 合同 line 25 引 ①②③⑥⑨ 但未注明条号出处是 OSkhQuant1.3 `docs/architecture/design-principles.md`（本仓 AGENTS.md 无此编号）——跨仓引号不注明源，下游无法核对。

  ## ✅ 做对的地方

  - 提交标记链（COMMITTED → manifest SHA256 → dump/probes SHA256，line 8）方向正确，「完成仅代表取数尝试完整留证，不表示覆盖通过」语义诚实。
  - 3002 永不作空事件证据（line 11）、D 类唯一放行路径为带日历过期的 override、parity 差异集合恒等（line 18）——这三处是历轮评审（v2 静态白名单 fail-open、v3 容差按码剔除）教训的正确固化。
  - §4.7 validate_base 分通道期望是真实的前向兼容雷（已核实 :553-554 现状会阻断含 hithink 行的 base），合同 line 17 已覆盖。
  - `--refresh` 仅限未 assemble 前（line 12）与 plan §4.2-5 的证据链钉死语义一致。
  - Windows 下 `Run.write` 的 `.tmp-uuid` + `Path.replace`（:153-159）同目录 rename 原子性成立，「原子复制」沿用它有事实依据。

  ## 总评

  合同与 plan v6 自洽，全部代码锚点与关键事实断言经复核属实，fail-closed 主线完整；**可进实现**，前置条件是把 🟡-1（HTTP timeout/重试预算，有实验证据）与 🟡-2（预签名 URL 过期重取）写进合同再动 1.3 producer——其余均为措辞收紧，不阻塞 BT 侧开工。
