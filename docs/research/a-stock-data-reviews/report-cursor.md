# simonlin1212/a-stock-data 独立研究报告（Cursor Agent）

> 调研日期：2026-10-09。本报告只写本机可读文件与仓库事实；未采信任何已有草稿研究。
> 主研究对象 `/workspace/a-stock-data`，HEAD `8f6a6a5`，与 `origin/main` 一致，工作区干净。
> 对照仓 `/workspace/OSkhQuant1.3`、`/workspace/MyQuant-backtrader` 全程只读，未做任何改动，未 push，未下载 corp-actions。
> 本次唯一的网络动作是 `git ls-remote --tags origin`（用于核对 tag 与版本号是否一致）；未对东财或任何行情接口发起请求，因此**本报告里所有"实测数字"都是仓库文档自述的数字，不是我跑出来的**，凡我自己数出来的都会写明数法。

---

## 1. 项目本质

### 1.1 它是什么

`a-stock-data` 是一个 **Claude Code / Codex 形态的 Agent Skill（单文件）**，不是 Python 包，也不是行情库。证据是仓库的物理构成：

| 文件 | 行数 | 性质 |
|---|---:|---|
| `SKILL.md` | 7577（433,852 字节） | 唯一产物：带 YAML frontmatter 的结构化 Markdown + 内嵌可运行 Python |
| `README.md` / `README_en.md` | 591 / 528 | 中英说明 |
| `CHANGELOG.md` | 972 | 版本日志 |
| `LICENSE` | 190 | Apache License 2.0 |
| `docs/` | 2 个文件 | `source-integration-v3.8.0.md`、`source-integration-v3.9.0.md`（数据源整合记录） |
| `tests/` | 3 个文件 | `test_official_data.py` / `test_v310_sources.py` / `test_v39_sources.py` |
| `assets/`、`.github/FUNDING.yml` | — | 赞赏二维码与赞助配置 |

**没有 `setup.py`、没有 `pyproject.toml`、没有 `requirements.txt`、没有任何 `__init__.py` 或 `.py` 源码文件**（`tests/` 下的三个文件是测试，不是实现）。所以"pip 安装"这条路径在这个仓库里根本不存在，安装方式是 README「快速开始」写的三步：`mkdir -p ~/.claude/skills/a-stock-data`，`curl` 下载 `SKILL.md`，再 `pip install` 一串第三方依赖。

`SKILL.md` 开头的 frontmatter 确认了它的 Skill 身份：

```yaml
name: a-stock-data
description: 当任务需要写代码实际获取A股及相关市场数据时使用——…仅在需要调用数据接口取数时使用：A股概念解释、投资观点讨论、策略问答等无需取数的话题不要加载本skill。
origin: custom
version: 3.10.1
```

### 1.2 它不是什么

- **不是行情库。** 没有任何存储层、增量更新、落盘、回填、对账、调度的概念。每个端点都是"发一次 HTTP / TCP，返回一个 DataFrame 或 list"。§1.4 腾讯逐笔只有最近一个交易日，§12 指数成分只有最近一次公布的快照，§1.3 通达信盘后包按单个交易日取。没有任何函数会写文件（唯一例外是 §3.2 北向资金的本地自缓存，README FAQ 自述"首次运行只有当天数据"）。
- **不带回测引擎。** README FAQ（#55）原文："本 skill 只负责取数，**不带回测引擎**。回测要把数据交给自己的框架或聚宽。"
- **不是数据封装库的替代品。** README FAQ 明确 V3.0 把 akshare 移除了，理由是"中间层增加了故障点"；`docs/source-integration-v3.9.0.md` 的"可复查的端点发现线索"一节承认端点格式参考过 AKShare、`jing2uo/tdx2db` 等项目，但"实现直接访问提供方域名，未增加这些项目作为依赖"。

### 1.3 产品形态是有意决策

单文件 433KB 的形态不是偷懒，README FAQ 有明确表态："单文件自包含是本项目的**有意产品决策**——拷一个文件就能用、离线可携、便于分发，这个形态会长期保持，不做目录化拆分（相关讨论见 #21 / #22 / #29）。"降耗手段是 v3.3.1 收窄 `description` 触发范围（commit `8b11251`）+ `SKILL.md:231` 的「端点路由速查」总表让 agent 按需定位章节。

同样的"只接可直接取数的来源"原则也体现在 PR 取舍上：`docs/source-integration-v3.9.0.md` 记录 PR #54（用 `easy_tdx` 替换 mootdx）**不合并**，理由是"同协议的另一个客户端库，不是新的数据源"。

### 1.4 版本以何为准

**以 `SKILL.md` frontmatter 的 `version: 3.10.1` 为准，git tag 滞后两个小版本。**

- 本地 `git tag -l` 最新是 `v3.9.0`；`git ls-remote --tags origin` 的结果一致，远端最新 tag 也是 `v3.9.0`（对应 commit `981524a`）。
- HEAD `8f6a6a5`（`fix: v3.10.1 …`）和它的前一个版本 `2e0ae63`（`feat: v3.10.0 …`）都没有 tag。
- README 徽章、README_en 徽章、`SKILL.md` 标题、CHANGELOG 顶部四处都写 V3.10.1，彼此一致。

所以消费方如果按 GitHub Release / tag 取版本，拿到的是 v3.9.0，会**缺掉 #57 这条关键更正**（科创板成交量单位，见 §3.3）。这是本仓当前最值得注意的发布流程缺陷。

另外：`.github/` 下只有 `FUNDING.yml`，**没有 `workflows/` 目录，即没有 CI**。173 条离线测试存在，但没有任何自动化在每次 commit 上跑它们。

---

## 2. 覆盖面

### 2.1 自述口径

README 徽章与 `SKILL.md` 标题一致：**15 层 · 87 个能力端点（82 主入口 + 5 备胎）· 34 个数据源 · 除 iwencai 外零鉴权**。

十五层分别是：行情/K 线、研报、市场信号、资金面/筹码、新闻、基础财务、公告、打板、ETF 期权、舆情互动、宏观与利率、指数与交易日历、期货与大宗商品、事件驱动、可转债。

### 2.2 "87"是怎么数出来的

README「87 个端点能力清单」一节有一段少见的自我对账说明，值得原样引用，因为它解释了这个数字不是函数个数：

> **计数口径：** 下方清单共 88 行，按能力入口计 87 个——「东财 行业研报」与「东财 reportapi」为**同一端点**（仅 `qType` 参数不同）、「同花顺北向（历史）」为本地自缓存（非独立端点），两行不计入；「东财日内异动池」一行含 `list` / `count` **两个端点**，多计 1 个。88 − 1 − 1 + 1 = 87。

我自己数了 `SKILL.md:231` 的「端点路由速查」表：去掉表头和分隔行后是 **82 行数据行**，里面出现 **83 个不同的 Python 函数名**。所以三个数字互不相等，各有各的口径：87 是"能力入口"，82 是路由表行数，83 是函数名。消费方做容量规划时不要把 87 当成"87 个可调用函数"。

### 2.3 主源 / 备胎的分层

`SKILL.md:320`「数据源优先级 & 东财防封」把来源按封 IP 风险排成五档：

| 优先级 | 来源 | 协议 | 封 IP 风险（自述） |
|---|---|---|---|
| 1 | 腾讯财经 | HTTP | 不封 IP，单入口约 600 次后限流（§1.2 已做三入口轮换） |
| 2 | 交易所 / 官方机构 | HTTP | 极低 |
| 3 | 新浪 / 巨潮 / 同花顺 / 华尔街见闻 | HTTP | 低 |
| 4 | mootdx（TCP 7709）、baostock（TCP） | TCP | 不封 IP / 低 |
| 5 | 东财 | HTTP | **有风控，会封 IP**，仅用于它独有的数据 |

五个备胎是：官方龙虎榜、新浪资金流、公告备胎、沪深官方两融、北交所当前行情。`SKILL.md:7379`「备用源速查 & 降级策略」另有一张十四行的"主源 → 独立备胎"表和一份"已死透别用"名单（网易财经 126.net 整站下线、和讯、凤凰行情、腾讯资金流 `ff_`、雪球免登录深度数据）。

这张表自己也标了时效性边界，值得照抄："既有备胎的验证记录为 2026-07-11；两融与北交所备胎在 2026-09-05 跑通真实数据；V3.9 的研报备胎与改过主源的 K 线行在 2026-09-20 实测。**历史验证不代表今天全部接口仍然可用。**"

### 2.4 README vs SKILL.md vs Release 的滞后情况

- **README 与 SKILL.md 不滞后。** 层数（15）、入口数（87）、来源数（34）、版本号（V3.10.1）四项在中文 README、英文 README、`SKILL.md` 三处完全一致。
- **README_en 不滞后。** 英文版同样带 V3.10.1 / V3.10.0 / V3.9.0 三条版本说明，徽章也是 15/87/34。
- **Release / tag 滞后两个小版本**（见 §1.4）。
- **文档内部仍有一处主动声明的滞后**：`SKILL.md` 的 V3.10.0 版本说明写着"行情层重排…新旧编号对照见 Layer 1 开头；**下面历史版本说明里写的仍是旧编号**"。也就是 V3.9.0 及更早的版本说明里引用的 §1.5 / §1.6 / §1.7 是旧编号，和现行 §1.2 / §1.3 / §1.7 对不上。`tests/test_v310_sources.py` 的 `LAYER1` 字典（第 31–34 行）把新编号到函数的映射固化成了断言，算是对这个风险做了部分覆盖。

---

## 3. 可靠性与陷阱

这一节每条都给文件证据。总体判断：**这个仓库对"坑"的记录密度异常高，很多坑是作者自己踩过并写进文档的；但 V3.0–V3.7 的老端点和 V3.9+ 的新端点在错误处理契约上是两套标准，这是最大的结构性隐患。**

### 3.1 mootdx / 通达信公开服务器（#52）——行情命令已失效

`SKILL.md:1867` §1.7 把 mootdx 整节标为"留档"。`docs/source-integration-v3.9.0.md` 记录的实测是："内置 10 台逐台实测，TCP 都可达，财务 / 除权除息正常，F10 只剩「最新提示」一类，K 线 / 五档 / 逐笔返回 0 行。"

衍生出三个具体陷阱：

1. **换 mootdx 版本解决不了**，是服务器端变化（README FAQ 原文）。
2. **F10 的类别名不能写死。** `SKILL.md:3787` 的注释："请求不存在的类别时 mootdx 不报错，而是返回 `{类别: 文本}` 的 dict，按字符串切片会抛 TypeError。"修法是先用 `F10C` 列类别。
3. **验活慢。** README FAQ："`tdx_client()` 在 K 线模式下要先测速，全部失败大约需要 1 分钟才报错。"所以要用 `tdx_client(check='finance')` 走财务命令验活。

另外 mootdx 库本身 README FAQ 自述"最后 commit 2024-07，BESTIP bug 无官方修复"，`SKILL.md:454` 的 `tdx_client()` 内置了绕过方案和一份"2026-06 验证"的备选服务器延迟排序表。

### 3.2 通达信官网盘后包（§1.3）——日期与北交所边界

`docs/source-integration-v3.9.0.md` 的实测边界：

- 最早能取到 **2021-08-16**，2021-08-02 返回 404；2022-01-04、2023-01-03 都能取到；**未逐日验证**。
- **2022-05-06 之前的包没有北交所文件**（二分实测：05-05 无、05-06 有）。原实现会对这些日期整包报错，现在改为"只对这之前的日期放行，之后缺北交所文件报错，不把沪深当成全市场"。
- 函数内置的完整性下限是"沪 1 万 / 深 3000 / 京 50"，依据是 11 个包实测的各市场最小有价记录数（沪 16202 / 深 3641 / 京 87）。

这个"深市 3641"的数字背后是一条容易误判的事实：2022 年以前深市大部分代码当日无价。

### 3.3 成交量单位（#57）——v3.10.1 的核心更正

这是本仓最值得单独拎出来的一条，因为**它只改文档不改返回值**，而 tag 又停在 v3.9.0，所以按 Release 取文件的人会拿到错的单位说明。

CHANGELOG v3.10.1 原文：§1.2 `tencent_kline()` 的 `volume`，**科创板（688 / 689）是股，其余是手**；此前文档全写成「手」，照旧文档换算科创板会大 100 倍。换算规则补全为：沪深主板、创业板、B 股、ETF（含科创板 ETF 588）、LOF、REITs 1 手 = 100 股/份，可转债 1 手 = 10 张，指数也是手。

同一节（`SKILL.md:1201` 起）还列了四条对账口径，每一条都是会让人对不上账的真实行为：

- **整手取整**：科创板以外日线的量是当日总股数取整到手，2020-03-11 起约为四舍五入（差 −52～+50 股），更早是舍去零头（差 −99～0 股），日线不回填。
- **分钟量 T 日整手、T+1 才回填成精确股数**，回填时点"没有测出来"。结论是"最近一个交易日的分钟量别拿来按股精确对账"。
- **13:01 那根的开盘价是上午收盘价**，不是午后第一笔；用 m1 自己合成 5 分钟线时 13:05 会和腾讯原生 m5 / Baostock 对不上。
- **深市整分边界**：hh:mm:00 的成交腾讯算进下一根、Baostock 算进上一根（11:30:00 例外），所以深市逐根对不上、全天合计一致。
- **没有成交的分钟**：第一笔成交以前沪深都没有行；之后沪市补量为 0 的行，深市会整根缺失（抽 51 只低成交深市股，25 只共缺 64 分钟）。

另一处同源的坑在 `SKILL.md:7402`：腾讯分钟 K 线返回数组的**第 8 个字段（下标 7）不是成交额，是换手率基点**，当成交额读会小三个数量级。

### 3.4 复权因子（§1.6）——三个方向性错误都不报错

`SKILL.md:1707` §1.6 和 `SKILL.md:1194` §1.2 共同描述了复权的三道坎：

1. **腾讯前复权是等差口径**（逐次减去每股分红），不是比例口径。文档给的对照："茅台 2020-01-02 原始价 1130.00、腾讯 qfq 870.741，差额正是此后累计分红；高分红老股早年会被减成负数（茅台 2015 年约 −117.6）。"函数遇到 ≤0 价格直接抛错。结论是"长区间回测请取 `adjust=''`，再用 §1.6 的比例因子复权"。
2. **`apply_adjust()` 的 qfq 与 hfq 运算方向相反**：qfq 因子是除数、hfq 是乘数。代码注释（`SKILL.md:1761`）："传错方向不会报错，只会把历史价格放大/缩小几倍。"
3. **因子为空时绝不能原样返回**（`SKILL.md:1767` 注释）："那会把不复权价当成复权价交出去，调用方拿到的数字看着正常却是错的（新浪对不支持的标的就返回空 data）。"现在是抛 `ValueError`。

### 3.5 代码映射与静默错票——修了两轮，仍有残留边界

这是本仓历史上最严重的一类 bug，修复轨迹清晰：

- **v3.7.1（commit `f90d678`）**：`get_prefix()` 认显式前缀却不认等价的后缀写法。`SKILL.md` 版本说明原文："`000016.SH` 以 `0` 开头落到默认深市分支，secid 拼成 `0.000016`（深康佳A）而非 `1.000016`（上证50 指数），**静默返回另一只标的的数据**。"
- **v3.7.2（commit `3a599d0`，#51）**：同一份文件里有两套北交所号段规则——`_natural_market()` / `_anomaly_market()` 只枚举 `43/83/87` + `920`，而 `get_prefix()` 用 `startswith(("4","8"))` + `startswith("92")`。统一为 `startswith(("4","8","92"))`。文档诚实地说明这"不改变任何现有标的的判定结果，修的是一致性与前向兼容"。
- **`norm_ticker()` 的防御**（`SKILL.md:627` 起的注释）：整串锚定正则，拒绝从任意串里"捞"6 位（`6005190` / `foo600519bar` 会被截成 `600519`），拒绝前后缀同时出现（`SH000001.SZ` 自相矛盾），`000xxx` 歧义段单独处理（`sh000001`=上证指数 / `sz000001`=平安银行）。解析失败**抛 ValueError 而不是返回空串**。

**仍然存在的边界**（`SKILL.md:610`、v3.7.1 版本说明都写明了）：走"前缀+原串拼接"的端点——`tencent_quote()`、新浪财报等——**只认纯 6 位或前缀式，不认后缀式**，`600519.SH` 会被拼成 `sh600519.SH` 并返回空载荷，仍然是静默失败。文档的对策是约定"先过 `norm_ticker()` 再传给任何端点"，这是**调用约定而不是代码保证**。对 AI agent 来说，约定靠不住。

### 3.6 北交所——覆盖按端点而异，且老码不报错

`SKILL.md:585` 的警告框是全文最密集的一处风险说明：

> 2026-07-31 实测：东财北交所在市 342 只中 **336 只已是 `920xxx` 号段**，仅剩 3 只老码且全部停牌。
>
> | 接口 | 传老码 `832982` | 传新码 `920982` |
> |---|---|---|
> | 腾讯行情 | 返回 112.60、**成交量 0**（定格在迁移日） | 131.74，正常成交 |
> | 东财研报 | **0 篇**（静默空） | 79 篇 |
>
> 老码行情价与真实价可差 17%~100%+。

v3.6.0 起 `tencent_quote()` 返回 `is_stale` / `stale_reason` 标志，`eastmoney_reports()` 遇老码抛 `ValueError`。判定规则是"成交量 == 0 且 最新价 == 昨收"——文档自己指出"真停牌股同样满足，两者都不该用于估值"。

把各节散落的北交所边界汇总（这张表文档里没有，是我从 `SKILL.md` 与 `docs/source-integration-v3.9.0.md` 拼的）：

| 端点 | 北交所 |
|---|---|
| §1.2 `tencent_kline()` | **不支持**，直接抛 ValueError（腾讯只返回最新 1 根日线，区间与分钟线为空） |
| §1.3 `tdx_daily_package()` | 支持，**且是北交所日线的唯一来源**；2022-05-06 之前的包没有 |
| §1.4 `tencent_ticks()` | 不支持 |
| §2.4 `sina_research_reports()` | 支持，函数自动加 `bj` 前缀（只给数字会得到"没有找到"空页） |
| §6.5 / §6.6 baostock | **不支持** |
| §6.8 `st_stock_list()` | 支持（东财路径）；退到 baostock 兜底时只有沪深 |
| §14.5 `equity_pledge()` | 不支持，传北交所代码直接抛错（全市场 2212 条中没有一只北交所） |
| `to_joinquant()` | 不转换（聚宽公开文档没有北交所后缀，"不猜"） |

### 3.7 东财限流——阈值表之外有一手封禁案例

`SKILL.md:340` 给了一张社区口径的阈值表（>5 次/秒、并发 ≥10、1 分钟 ≥200 次、5 分钟 ≥300 次），但更有价值的是 `SKILL.md:352` 那条标注"一手数据"的实测案例（#36）：

- 触发：选股脚本 10 线程并发、完全不走 `em_get()` 限流，1 小时内 45000+ 请求。
- 后果：`push2` / `push2his` **全系列 RemoteDisconnected，IP 级封禁持续 20+ 小时**——不是"几分钟到几小时"。
- 关键观察一：`datacenter-web.eastmoney.com` **不受影响**，东财不同子域走不同 WAF。
- 关键观察二：腾讯 K 线连续 5000+ 次后返回空，但那是**限流不是封 IP**。

内置的 `em_get()`（`SKILL.md:749`）做串行限流 `EM_MIN_INTERVAL=1.0` + 随机抖动 + Keep-Alive 会话，对应"1 小时最多约 3000 次请求"。重试策略是 `Retry(total=3, connect=3, backoff_factor=0.6, status_forcelist=[429,500,502,503,504])`，注释明确 **403 不重试**（"东财风控信号，重试无益反而加重"）。

**我发现一处文档没提的弱点**：`em_get()` 的节流状态是模块级列表 `_em_last_call = [0.0]`，**没有锁**。文档要求串行调用，所以在遵守约定时没问题；但 AI agent 一旦自作主张开线程池，节流会直接失效——而文档自己说"AI 跑批量循环是被封的头号元凶"。

住宅 IP 另有一类间歇风控（README FAQ #18）："部分大陆住宅宽带 IP 会被东财 push2/search-api 连接级间歇风控（表现 `HTTP 000` 连接被拒、或新闻只返回 `passportWeb` 无文章）。这不是代码问题。"

### 3.8 空结果 vs 接口坏——两套标准，这是最大的结构性隐患

**V3.9+ 的新端点做得很好。** `SKILL.md:802`「V3.9.0 共用 helper」的契约原文：

> **「确实没有数据」与「接口坏了」分开处理**：前者返回空表或抛 `ValueError`（非交易日、日期太早），后者抛 `RuntimeError`（结构改变、重复行、全市场 0 行），不把错误页当空结果。

配套实现也到位：`_v39_http()` 把网络错误和非 2xx 一律转 `RuntimeError`；`_v39_json()` 特意把 `json` 的 `ValueError` 转成 `RuntimeError`，注释说明"不转换会被调用方当成「确实没有数据」"；`_v39_src_date()` 对来源返回的日期认不出时抛 `RuntimeError`（"源格式变了，不是参数写错"）。

**但 V3.0–V3.7 的老端点不走这套。** `SKILL.md:785` 的 `eastmoney_datacenter()`：

```python
def eastmoney_datacenter(report_name, columns="ALL", filter_str="", page_size=50,
                         sort_columns="", sort_types="-1") -> list[dict]:
    params = {..., "pageNumber": "1", "pageSize": str(page_size), ...}
    r = em_get(DATACENTER_URL, params=params, timeout=15)
    d = r.json()
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []
```

三个问题叠在一起：

1. **`return []` 吞掉一切。** 被封、错误码、结构变化、确实没数据——四种情况返回同一个空列表。
2. **`d = r.json()` 没有包装。** 返回错误页（HTML）时抛的是 `json.JSONDecodeError`，它是 `ValueError` 的子类——正好是 V3.9 契约里"确实没有数据"的那一类。两套标准在这里直接打架。
3. **永远只请求 `pageNumber=1`，不翻页。** 默认 `page_size=50`，而 §4.4 `dividend_history()` 的默认是 **20**。超过这个条数就静默截断。

走这个老 helper 的是**整个 Layer 4 资金面层**：§4.1 融资融券、§4.2 大宗交易、§4.3 股东户数、§4.4 分红送转、§4.5 个股资金流 120 日。`docs/source-integration-v3.9.0.md` 自己说明了新旧区别："`_em_datacenter_strict()` 与旧 `eastmoney_datacenter()` 的区别是会翻页、并把错误码抛出来。"——即旧的两样都没有。

**这是我对本仓最重要的一条保留意见**：V3.9 之后的质量标准很高（见 §3.11 的变异测试记录），但老端点没有回头补齐，而文档的层级结构会让使用者以为全仓是同一套契约。

### 3.9 筹码分布（§4.6）——本地推演，播种口径已自述有偏

`SKILL.md:3202` 明确："东财没有公开 CYQ 接口（2026-08-19 实测 `push2/api/qt/stock/cyq/get` 与 `push2his` 两种写法均 404）。业界通行做法是本地推演。"

`SKILL.md` 的 V3.7.0 版本说明给了一条相当坦率的自我批评：

> 初始筹码**播种为首日全部流通盘**——从全零起步会把窗口前的存量持仓一笔勾销（两个 1% 换手日会被算成 50/50，真实应约 99%/1%）。

§4.6 的实测注（`SKILL.md:3329`）给了另一个方向的偏差："窗口累计换手不足 100%，多数筹码仍是期初高位持仓，故均成本高于现价、获利盘偏低。"

函数本身的防御倒是做得细：强制要求 `date` 列并自行升序（注释："若传入常见的「最新在前」倒序，衰减会反向推、且 `close.iloc[-1]` 会把最老的收盘价当成现价——结果完全错却不会报错"），以及振幅窄于网格步长时映射到最近网格点而不是跳过该日。

结论：**这是一个有文档的估算器，不是数据源。**

### 3.10 备用源代码块关闭了 TLS 校验

`SKILL.md:7407`：

```python
_ctx = ssl.create_default_context(); _ctx.check_hostname = False; _ctx.verify_mode = ssl.CERT_NONE
```

这个 `_ctx` 被 `dragon_tiger_backup()`（深交所分支）和 `announcements_backup()`（深市分支）用于 `urllib.request.urlopen(..., context=_ctx)`。也就是对 `www.szse.cn` 的 HTTPS 请求**既不校验证书也不校验主机名**。全仓只有这一处（我 grep 了 `verify=False|CERT_NONE|check_hostname`，只命中 7407 这一行）。

文档没有解释原因，也没有给出警告。对一个"降级到交易所官方拿权威一手数据"的路径来说，这个取舍方向是反的——越是权威路径越该校验。如果要把备用源代码引进内网环境，这一行应当先改掉。

### 3.11 测试：覆盖方式很硬，但没有 CI

测试的设计值得肯定：**它从 `SKILL.md` 里抽取发布代码来跑，而不是维护第二套实现。** `tests/test_v39_sources.py` 第 25–28 行读取 `SKILL.md`，用 16 个 `v39-*` marker 块加上按函数名定位的 `_block_defining()` 取出代码，`_defs_only()` 用 AST 剥掉教程块里的示例调用后 `exec`。`tests/test_v310_sources.py` 还额外断言了 Layer 1 的新编号到函数的映射，以及 `v310-tencent-ticks` 块不含 PEP 604 union（保 Python 3.9 兼容）。

`docs/source-integration-v3.9.0.md` 记录了变异检查："每个修复都做过变异检查：把修复改回去，对应测试会失败……共 209 处，发布前在最终代码上复跑适用的 190 处：186 处全部失败；4 处改坏后仍被另一道检查拦住，属于双重保护。"这是相当高的自查强度。

**数量核对（我自己数的）**：三个测试文件共 `def test_` **177 个**（27 + 35 + 115）。live-gated 的（`@unittest.skipUnless` 之后定义的）共 **4 个**（`test_official_data.py` 1、`test_v310_sources.py` 2、`test_v39_sources.py` 1）。177 − 4 = **173**，与 README「V3.10.1 共 173 条离线测试」完全吻合。

**但我没有执行这些测试**：本机是 Python 3.13.5，只有 `requests`，缺 `pandas` / `numpy` / `mootdx` / `baostock`。所以"173 条当前是否全绿"——**未核实**。又因为仓库没有 CI（`.github/` 下只有 `FUNDING.yml`），上游也没有任何自动化在证明这一点。

---

## 4. 许可证与依赖

### 4.1 许可证

**Apache License 2.0**，`LICENSE` 末尾的版权声明是 `Copyright 2026 Simon Lin`。README 的表述是"自由使用，注明出处即可"。

对本地三仓的实际含义：

- 内部使用、修改、作为依赖集成都没有限制。
- Apache-2.0 §4 的义务只在**分发**（含分发衍生作品）时触发：需保留 LICENSE、保留 NOTICE（本仓没有 NOTICE 文件）、在修改过的文件上标注变更。如果只是把 `SKILL.md` 的代码片段抄进 OSkhQuant1.3 / MyQuant-backtrader 做内部研究，不构成分发。
- 含明示专利授权（§3），比 MIT 更适合企业环境。
- 与两个对照仓的现有许可无冲突（两仓都是私有仓库，未对外分发）。

### 4.2 依赖清单

`SKILL.md:422`「Prerequisites」与 README 一致：

```bash
pip install mootdx requests pandas stockstats numpy baostock xlrd openpyxl
```

| 依赖 | 版本要求 | 用途 | 注意 |
|---|---|---|---|
| mootdx | >= 0.10 | §6.1 财务快照、§6.2 F10（TCP 7709） | 上游 2024-07 停更；行情命令已失效 |
| requests | any | 所有 HTTP 直连 | — |
| pandas | any | 数据处理 + HTML 表格解析 | — |
| stockstats | any | 技术指标 | 仅技术指标用，非取数必需 |
| numpy | any | §4.6 筹码网格计算 | — |
| baostock | >= 0.8 | §6.5 估值历史、§6.6 上市退市日、§6.8 ST 兜底 | **不支持北交所** |
| xlrd | >= 2.0 | 读 `.xls`（§6.7 申万、§12 中证） | xlrd 2.x 已不支持 `.xlsx` |
| openpyxl | any | 读 `.xlsx`（§11.1 社融、§12 国证、深交所两融） | — |

Python 要求 **3.9+**，README 徽章与 `tests/test_v310_sources.py` 的 PEP 604 断言都确认了这一点（代码里特意写 `from typing import Optional` 而不是 `dict | None`，注释注明"3.9 兼容"）。

### 4.3 与共享环境的冲突风险

**风险一：mootdx 锁死 httpx，与 MCP 硬冲突。** README FAQ（#30）："mootdx 上游锁了 `httpx<0.26`，与 MCP 等工具的 `httpx≥0.27` 硬冲突，skill 层改不动它的依赖声明。"作者给了两个绕法：`pip install --no-deps "httpx>=0.27.1"`（理由是 mootdx 取数走 TCP 二进制协议，运行时根本不经过 httpx），或者独立 venv 隔离。

**风险二：装进 1.3 的生产 conda 环境是坏主意。** OSkhQuant1.3 的文档里反复出现的运行环境是 `D:\anaconda3\envs\vanna311` 和 `vanna312`（见 `docs/backtest/data/daily-adjusted-update-ssot.md` §3 的全部命令，以及 `docs/operations/st-data-channels-ssot.md` §2.2）。这个环境里跑的是 QMT/xtquant、DuckDB、pyarrow、Redis 客户端、以及 `curl_cffi`（巨潮 WAF 伪装）。往里装 mootdx（动 httpx）+ baostock + stockstats + 新的 pandas 约束，等于把一个公开数据实验的依赖面糊到生产交易栈上。1.3 自己还有一份 `docs/operations/python-env-isolation-check.md`，说明环境隔离已经是该仓的既有纪律。**结论：任何 a-stock-data 的试跑都应该在独立 venv 里做，产物以 CSV/parquet 交付，不让依赖进生产环境。**

**风险三：本机（Linux 容器）跑不了。** 当前 `python3` 是 3.13.5，只有 `requests`，`pandas` / `numpy` / `mootdx` / `baostock` 全部缺失。所以本报告没有做任何代码执行验证。

**风险四：mootdx 需要国内 IP。** README FAQ："mootdx 走 TCP 直连通达信行情服务器，需国内 IP 才稳定。"#52 之后它只剩财务与 F10，海外环境基本可以不装。

---

## 5. 对 MyQuant-backtrader 的适配

### 5.1 BT 现在从哪里取数（事实基线）

| 数据 | 来源 | 代码位置 |
|---|---|---|
| 日线 OHLC | hive parquet `{period=1d}/dividend_type={none,front,back}/symbol=*/data.parquet` | `backtest/research/csv_daily_loader.py:69-149` |
| 分钟 OHLC | hive parquet `{period=1m}/dividend_type=none/...` | `backtest/research/ashare_bars.py:339-422` |
| 湖根解析 | `OSKH_SOURCE_PARQUET_ROOT` / `.authority` | `common/infra/data_root.py:134-159` |
| 涨跌停价 | **本地计算**：前收 × (1±pct)，Decimal ROUND_HALF_UP | `backtest/research/ashare_session.py:49-71`、`market_layer.py:103-114` |
| 板块分档 | 代码数字前缀 | `backtest/research/market_layer.py:17-22` |
| 限价用的 ST 判定 | **股票池 CSV 的名称列正则** `is_st_name` | `market_layer.py:15,34-36,88-95` |
| 除权参考价 | `ex_date_index.parquet` + `adj_factor.parquet` | `backtest/research/exdiv_map.py:179-259` |
| 分红现金/送股经济学 | **调用方自带，无 loader** | `backtest/research/ashare_exdiv_economics.py:1-7` |
| 申万一级行业 | `{SOURCE}/vendor_wind_sw_l1/sw_l1_map.csv` | `oskh_data/industry_sw_l1.py:19-26,100-116` |
| 交易日历 | 已载入 bar 的日期并集 / `trading_calendar_pmc` | `backtest/research/csv_common.py:48-59`、`oskh_data/reader.py:354` |

### 5.2 BT 自己标出来的两个缺口

这两处是 a-stock-data 唯一可能真正发挥作用的地方，而且是 BT 代码里**显式写死的 DATA-MISSING**：

**缺口一：PIT lifecycle provider。** `backtest/research/rule_profile.py:29-33`：

```python
if self.special_no_limit_days:
    raise NotImplementedError(
        "DATA-MISSING: special_no_limit_days requires a PIT lifecycle provider "
        "(IPO/relist/resumption facts); not inferred from bars"
    )
```

`docs/backtest/industry-rule-profile-2026-10-06.md` 的开关表对应行："IPO, relist, and resumption facts must come from a PIT lifecycle provider; missing data fails closed and is never inferred from bars."

**缺口二：corp-action 现金与送股的 per-event facts。** 同一份文档第 87–89 行："Corporate-action cash and bonus accounting follows the same adopted DATA-MISSING rule as lifecycle facts: real industry runs must use explicit per-event facts and must not derive entitlements from adjustment-factor ratios."

`ashare_exdiv_economics.py` 的 `ExDivEvent` 要求六个字段：`event_id`、`bonus_ratio`、`cash_div_per_share`、`ex_date`、`pay_date`、`list_date`。

### 5.3 可以作为可选离线 / 事件表的

**全部前提：人工跑一次，冻结成 CSV / parquet，再由人审核后交给 BT；回测运行时不得联网取数。**

**（A）§6.7 申万行业变迁史 — 推荐度最高。**
`SKILL.md:4017` 的 `sw_industry_history()` 直接读申万官方 `StockClassifyUse_stock.xls`，返回每只股票每次行业调整一行，带 `计入日期`。配套 `sw_industry_as_of(df, code, as_of)` 取不晚于该日的最后一次调整。自述实测（2026-08-19）：12893 行 / 5905 只 / 38 个一级 / 194 个二级 / 553 个三级，并给了平安银行 1991/2014/2021 三次调整的前视偏差验证。

价值在于：BT 现在用的 `vendor_wind_sw_l1/sw_l1_map.csv` 列是 `Wind代码,证券简称,申万一级行业`（见 OSkhQuant1.3 `docs/prompts/prompt-kimi-datasource-industry-harvest.md`「关键坑点」第 4 条），**没有任何日期列**——是当前快照，不是 PIT。我也在 `oskh_data/vendor_wind_sw_l1.py` 里 grep 过 `date|日期|as_of|PIT`，只命中 `generated_at` 一个产出时间戳。所以 a-stock-data 这条补的是 1.3/BT 真实缺的维度，而且零 key、零 Kimi 额度。

**已知阻塞点**：申万官方只发代码不发中文名（`SKILL.md:4022` 明确："申万官方只发布代码不发布中文名…东财/通达信的行业名不能直接套——分类体系不同，代码不通用"）。要和现有 `sw_l1_map.csv` 的中文行业名对齐，需要一张 `480000 → 银行` 的映射表，这张表不在本端点里。

**（B）§12.4 深交所官方整月交易日历 — 当交叉校验用。**
`SKILL.md:5690` 的 `trading_calendar(year, month)` 读深交所 `monthList` 接口，逐日返回 `is_open`，并校验返回的日期集合等于该自然月全集，否则抛 `RuntimeError`（"深交所尚未返回该月日历；不能推断全月休市"）。

对照方：1.3 的 `common/infra/trading_calendar_pmc.py` 用的是 `pandas-market-calendars` 的 SSE 日历，它的 docstring 自己写着："Unified to SSE (not XSHG): XSHG lacks `regular_holidays` after 2026-10-07 and misclassifies 2027+ statutory holidays as trading days."——这是一个**已记录的、跨年会失效的推断型日历**。官方日历是对它最便宜的体检手段。

**（C）§6.6 baostock 上市/退市日 + §6.5 日频 `tradestatus` — 只能作为 PIT lifecycle 的部分候选。**
`baostock_stock_basic()` 给 `ipoDate` / `outDate` / `status`，README 称其为"唯一零鉴权退市日源"。`baostock_valuation_history()` 的 `tradestatus == "0"` 是停牌日，可回溯至 2016。

但对 BT 的三类事实只能覆盖一类：

| BT 需要 | baostock 能给吗 |
|---|---|
| IPO | **能**，`ipoDate` 直接可用 |
| relist（恢复上市） | **不能**，`status` 只有在市/退市两态，没有恢复上市事件 |
| resumption（复牌） | 只能从 `tradestatus` 0→1 **推导**——而 BT 的原则正是 "not inferred from bars" |
| 北交所 | **完全不支持** |

所以这条的正确用法是先做可行性 spike 并把结论写下来（见 §8 探针 C），而不是直接造表。

**（D）§1.3 通达信盘后包 — 只作为湖的对账样本。**
它是目前唯一能一次拿到某交易日沪深北全市场日线**含成交额**的零鉴权来源，且含北交所。适合拿来抽查 1.3 的 `none` 湖在某几个历史日期上是否有缺股、成交额是否对得上。不适合当湖本身（没有复权、按日取、日期边界见 §3.2）。

**（E）§4.4 分红送转 — 只能当线索，不能喂 `EconomicLookup`。**
`SKILL.md:3112` 的 `dividend_history()` 返回四个字段：`date`（`EX_DIVIDEND_DATE`）、`bonus_rmb`（`PRETAX_BONUS_RMB`）、`transfer_ratio`、`bonus_ratio`，外加 `plan`（`ASSIGN_PROGRESS`）。对照 BT 的 `ExDivEvent` 要求：

- **缺 `pay_date`**（派息到账日）。
- **缺 `list_date`**（送转股上市流通日）。
- `plan` 字段说明返回集里**混有未实施的预案**，直接当事实会把预案当成已发生的分红。
- 走的是老 helper `eastmoney_datacenter()`，**默认 `page_size=20` 且不翻页**（§3.8），长历史会静默截断。
- `bonus_rmb` 的口径注释写的是"每股派息(税前)"，但东财 `PRETAX_BONUS_RMB` 在不同报表里有"每 10 股"口径的先例——**我没有实际调用验证，此处标记为未核实**。

结论：这条数据可以用来**发现**"某只票在某日可能有分红事件"，但不能作为 corp-action 的经济事实。那些事实该留给 Wind（见 §7）。

### 5.4 绝不可进下单决策价的

下面每一条都给出理由，统一的底层原因是：**这些都是无 SLA、无重放、无 PIT 保证的公开 HTTP 快照，与 1.3 已确立的"front = QMT Ground Truth、禁止本地推导"口径（`docs/backtest/data/daily-adjusted-update-ssot.md` §1）直接冲突。**

| 不可用于决策价 | 理由 |
|---|---|
| §1.2 `tencent_kline(adjust='qfq')` | 等差复权口径，老股会变负（茅台 2015 约 −117.6）；与 1.3 湖的 front（QMT GT，比例口径）数值体系不同；科创板量单位坑（#57） |
| §1.1 `tencent_quote()` 实时价 | 可能是僵尸报价（`is_stale` 只是启发式，与真停牌不可区分） |
| 任何东财价格字段 | IP 级封禁可持续 20+ 小时；老端点空结果与接口坏不分（§3.8） |
| §1.4 `tencent_ticks()` | 只有最近一个交易日，不含北交所，15:31 之前 `attrs["complete"]` 不可用 |
| §4.6 `chip_distribution()` | 本地推演，播种口径已自述有系统性偏差 |
| §1.6 新浪复权因子 | 第三方口径；与 1.3 的 `adj_factor.parquet`（= `close_front / close_none`，由 QMT GT 算出）不是同一个定义 |
| 任何前收，用于算涨跌停 | BT 的 `session_prev_close()` 读的是湖的 `none` 前收并经 E-R6 除权调整；换源会让限价和湖脱钩，而限价直接决定成交与否 |
| §12.1–12.2 指数成分/权重 | **只有最近一次公布的快照**，`SKILL.md:5525` 明确"这些快照不提供历史时点成分……做历史回测时不能拿当前成分代替当时成分" |

---

## 6. vs OSkhQuant1.3

### 6.1 1.3 已有的数据层

**三类存储**（`docs/operations/data-three-stores-ssot.md`）：

- **Parquet 行情湖**：唯一必填 env `OSKH_SOURCE_PARQUET_ROOT`；hive 三树 `stock/period={1d,1m}/dividend_type={front,none,back}/symbol=*/data.parquet`，外加 `index/period=1d`、`etf/period=1d` 两棵副轨树，以及散装 `adj_factor.parquet` / `float_shares.parquet` / `ex_date_index.parquet` 等。
- **DuckDB 派生工作区**：`resolve_e_stock_data_container()` = `{OSKH_DATA_ROOT}/stock_data`，`stock_data_{front,none,back}.duckdb` + ETF/index 副本。双根纪律：与 parquet 不同盘不同目录。
- **SQLite 交易运行时**：`data/sqlite/` 下五库（portfolio / execution_trade / audit_trade / strategy）+ 巨潮两库（disclosure / alert_monitor）；与行情数据完全正交。

**日线复权与更新节奏**（`docs/backtest/data/daily-adjusted-update-ssot.md`）：

- 宇宙：QMT sector `沪深京A股`，约 **5548 只**（含北交所）。
- `front` = **QMT Ground Truth**，从 `get_market_data_ex(dividend_type='front')` 下载落盘，**禁止**用 back/none 本地推导（会注入 ~0.5–1.5% 噪声）。
- `adj_factor` **只能计算不能下载**：`cumulative_adj_factor[t] = close_front[t] / close_none[t]`。
- 唯一流水线：`detect_ex_date_changes.py` → `update_adjusted_daily.py --download-only` → `finish_adj_factor_duckdb.py` → `oskh_data.backfill rebuild`，统一入口 `scripts/data/run_daily_adjusted_fast.py --end YYYYMMDD`。
- 节奏：日常增量下 `none`，除权股 delete + 全历史重下 front，非除权股走"路径 B"（`front_today = none_today`）；`back` 日常不下；周日 / 每月 1 号 / `--force-refresh-front` 做全市场 front 重下。
- 运维成熟度很高：`docs/SSOT.md` 第 228 行挂了九份 `run-records`，每份对应一条编号教训（33、34、44、47、51、54、55 等）。

**corp-actions / 分红：1.3 只有"检测"，没有"金额"。** SSOT §1 原文："QMT `get_divid_factors`：**检测可用 / 推导禁用**：用于 `detect_ex_date_changes.py` 发现新除权日；`dr` 不得用于推导 front 价格或因子数值。"也就是 1.3 知道哪一天除权，不知道派了多少钱、送了多少股。

**ST：五渠道，已成体系**（`docs/operations/st-data-channels-ssot.md`）：深交所简称变更（深市事件流 SSOT，生效日口径，免费）/ 巨潮公告（补沪京，WAF 403 按 IP 拉黑）/ Wind 经 Kimi（沪京历史批，耗额度）/ QMT 两产物（交易闸 `daily_st_set` + 回测湖 `vendor_qmt_st_names`，2026-09-16 人裁"禁止互顶"）/ 东财风险警示板（备胎，常 `RemoteDisconnected`）。三仓规矩是 2026-09-14 人裁：**1.3 下载写湖，MyQuant 与 MyQuant-backtrader 只消费**。

**行业：** `oskh_data/vendor_wind_sw_l1.py` → `{SOURCE}/vendor_wind_sw_l1/`，Wind 经 Kimi 采，产物 `wind_l1_map.csv` / `wind_conflicts.csv` / `wind_crosscheck.json`。

**指数：** 只有行情副轨（`index/period=1d`，none-only，基准名单 `config/market_data_etf_index_universe.txt`）。我 grep 了 `oskh_data/`、`common/`、`scripts/` 下的 `成分股|constituent|index_member`，只命中 `common/integrations/guojin_xtdata_gateway.py` 一个文件——**没有指数成分/权重表**。

**交易日历：** `common/infra/trading_calendar_pmc.py`，来自 `pandas-market-calendars` 的 SSE 日历，进程级缓存 + bisect 查询。

### 6.2 a-stock-data 在哪里重复

| a-stock-data 能力 | 1.3 的对应物 | 判断 |
|---|---|---|
| §1.1–§1.3 行情 / K 线 / 全市场日线 | QMT GT 湖（front + none，5548 只，含北交所） | **重复且更差**。腾讯不含北交所、盘后包只到 2021-08、复权口径不同 |
| §1.6 新浪复权因子 | `adj_factor.parquet`（front/none 计算） | **重复且口径不同**。不该混用 |
| §6.8 ST 当日名单（东财 + baostock 兜底） | `st-data-channels-ssot.md` §2.5 东财备胎 + §2.4 QMT 快照 | **重复**。1.3 的 `oskh_data/vendor_szse_st.py` 里本来就有 `EM_CURRENT_ST_JSON` 东财快照路径 |
| §12.4 交易日历 | `trading_calendar_pmc`（pandas-market-calendars） | **重复但来源不同**，有交叉校验价值（见 §8 探针 B） |
| §6.5 baostock 历史 ST（`isST`） | 深交所事件流（深市）/ Wind 经 Kimi（沪京） | **部分重复**，但它是**零额度**的沪市对照源，见 §7 |

### 6.3 a-stock-data 在哪里补缺

按价值排序：

1. **申万行业 PIT 变迁史（§6.7）** — 1.3 的 Wind 产物是无日期的当前快照，这是实打实的缺口。零 key、零 Kimi 额度。
2. **上市 / 退市日（§6.6）** — 1.3 没有独立的 instruments 生命周期表。BT 的 `kimi-financial-data-fill-pointer.md` 提到有一个 2026-10-01 的 instruments 佐证包，但那是 THS `get_price` + Wind 涨跌停价，不是上市退市日，且"不要把 instruments 包视为写湖授权"。
3. **指数成分 / 权重 / 指数估值（§12.1–§12.3）** — 1.3 完全没有。但只有当前快照，不能做历史回测的成分回填。
4. **宏观与利率（§11：社融 / PMI / 中债三条收益率曲线 / FR-FDR 回购定盘 / LPR 全历史 / 全球宏观日历）** — 两仓都没有。
5. **事件驱动（§14：业绩预告 / 机构调研 / 增减持 / 回购 / 股权质押 / 新股申购）与可转债（§15）** — 两仓都没有。
6. **分红送转金额（§4.4）** — 填 1.3"只有除权日检测、没有金额"的缺口，但字段不全（§5.3-E）。
7. 期货与大宗（§13）、研报（§2）、打板（§8）、ETF 期权（§9）、舆情互动（§10）—— 与两仓当前业务无交集，不评估。

### 6.4 一条流程上的提醒

1.3 的 ST SSOT §4「目录纪律」立过一条规矩："按 vendor 分根目录……历史教训：深交所表、东财快照曾被塞进 `vendor_wind_st_status/`，目录名撒谎。"如果以后真要落 a-stock-data 的产物，应当遵循同一条：`{SOURCE}/vendor_astockdata_<kind>/`，不要塞进现有 vendor 根。

---

## 7. vs Kimi / Wind

### 7.1 Kimi/Wind 侧的事实基线

来自 `MyQuant-backtrader/docs/operations/kimi-financial-data-fill-pointer.md` 与 OSkhQuant1.3 的两份文档：

- **三仓分工**（2026-09-14 人裁）：OSkhQuant1.3 下载并写湖，MyQuant 与 MyQuant-backtrader 只消费；不要把采集流程复制到 BT 仓。
- **Kimi Wind 调用口径**：不调 `get_data_source_desc`；`data_source_name=wind`、`api_name=wind_get_financial_data`；每批 100 码。Wind 返回无数据时用本地 `write-empty` 写仅含表头的空 CSV，不重试空批次 `0027/0028`。
- **分钟线接口**：`wind_get_stock_quote`（不是 `wind_get_minute_data`，那个 `API_NOT_FOUND`；也不是 `wind_get_price`，那个只出日线）。2026-10-01 已用它补 002231.SZ / 300379.SZ / 600200.SH；2026-10-04 补 300344.SZ（原始 936 行、入湖 928 行，成交量 `股//100`，时钟 Wind 常见 START 而湖目标 END，"禁止整表盲加一分钟；缺根不补零"）。
- **运行方式**：4090 上无头 `kimi -p`，不用 `--auto`、不用 `--yolo`。
- **同花顺源名** `stock_finance_data`；`get_price` 的 interval 只有 D/W/M/Q/Y；iFinD 不在 kimi-datasource 枚举（枚举是 `stock_finance_data`、`wind`、`gildata`、`yahoo`）。

### 7.2 关于额度

`st-data-channels-ssot.md` §2.3 明确"耗 kimi 额度"，坑里写着"kimi 额度间歇耗尽（QUOTA ≠ FAIL）"，并有一条日常门闩（lesson 61）："用户说「日常 / 不用 Kimi」或 `skip_kimi_on_routine=true` → 只跑深市+巨潮+QMT，**勿**开 kimi prompt。"

§5.1 给出的缺批现状：优先缺批 `0035、0037、0044–0055`；空批（Wind 返回"没找到数据"）实施 `0037、0053、0055`、撤销 `0045–0047、0052–0055`；仍缺实施 `0000–0034`（除 0027/0028）、`0036、0038–0043`。

**但"周额度 / 5h 窗口"这两个具体数字，我在三个仓的文档里都没有找到** —— 本机可读文件里没有写。标记为**未核实**。

### 7.3 corp-actions 导出包

任务提到 4090 上的 `D:\exports\bt_corp_actions_20261006`。我在 `/workspace/MyQuant-backtrader` 全仓 grep 了 `corp_actions|corp-actions|20261006`：`corp_actions` 零命中；`20261006` 的全部命中都是 rule-profile 的 revision 字符串（如 `industry-p11-20261006`）和 off-byte baseline 的文件名，与 corp-actions 导出包无关。OSkhQuant1.3 侧同样未见引用。

**结论：该导出包与两仓代码目前尚无任何接线。**按硬约束未下载、未核实其内容与 schema。

### 7.4 逐项对比

| 维度 | Wind 经 Kimi | a-stock-data（公开 HTTP） |
|---|---|---|
| **ST 事件（戴帽/摘帽，沪京历史）** | 有，事件流，但缺批多、耗额度 | **没有事件流**。§6.8 只有当日快照；§6.5 baostock `isST` 是日频状态列（可回溯至 2016，不含北交所）——可以反推区间，但那是推导不是事件 |
| **ST 深市** | 不该用（额度留给沪京） | 重复 1.3 已有的深交所免费 SSOT |
| **北交所** | 有 | §6.5/§6.6 完全不支持；§6.8 当日快照支持 |
| **corp-actions 现金/送股** | 权威，且是 BT `ExDivEvent` 的合理来源 | §4.4 缺 `pay_date` / `list_date`，混有预案，不翻页（§5.3-E） |
| **上市 / 退市日** | instruments 佐证包（THS `get_price` + Wind 涨跌停价） | §6.6 `ipoDate` / `outDate`，零 key，**不含北交所** |
| **申万一级行业** | 有，但**无生效日**（当前快照） | §6.7 **有生效日的变迁史**，零 key 零额度 —— 唯一一项 a-stock-data 明确优于 Wind 路径的能力 |
| **分钟线补缺** | `wind_get_stock_quote`，已有成熟的对齐规矩（START vs END、不补零） | §1.2 腾讯 m1 最多 320 根（约 1.3 天），T 日整手 T+1 回填，深市整分边界与 Baostock 错位 —— **不适合补湖** |
| **鉴权 / 前置** | Kimi 会话 + 额度 + 4090 在线 + 插件版本 ≥3.4.0 | 除 iwencai 外零 key；但受东财 IP 风控与腾讯单入口 600 次限流约束 |
| **故障模式** | 额度耗尽 / `EMPTY_DATA` / `API_NOT_FOUND` —— 可识别、可重试、可审计 | IP 级封禁 20+ 小时 / 静默空页 / 源结构变更 —— 部分端点连"空"和"坏"都不分（§3.8） |
| **可重放性** | CSV 落盘 + batch 编号 + `harvest_status.json`，有 coverage 口径 | 无。每次调用是一次性快照 |
| **直接成本** | 消耗 Kimi 额度（当前是瓶颈） | 零 |

### 7.5 建议的分工

**应当留在 Wind / Kimi：**

1. corp-action 的现金分红与送转**经济事实**（`pay_date` / `list_date` 是 BT `ExDivEvent` 的必填项，公开源拿不全）。
2. 沪京 ST 历史事件的权威口径（现有缺批仍应用额度补完）。
3. 北交所的任何历史覆盖（baostock 整个不支持）。
4. 分钟线补缺（已有成熟的 START/END 对齐规矩和 remainder audit 流程）。

**可以迁到 a-stock-data（省额度、零 key，且先落到 reviews/exports 而非湖）：**

1. **申万行业 PIT 变迁史** —— 补的是 Wind 路径本来就没有的维度。
2. **沪深上市/退市日** —— 作为 instruments 的零成本补充与对照。
3. **沪深历史 `isST` 的对照** —— 不替代事件流，但可以用来体检 Wind 缺批造成的 open 高估（`st-data-channels-ssot.md` §5.1 记录的"262 含 87 只退市僵尸 open……直接用高估 28%"正是这类问题）。
4. **交易日历交叉校验** —— 对冲 `pandas-market-calendars` 的跨年推断风险。

---

## 8. 下一步实验

三个小探针，都满足：独立 venv、单次手跑、产物只写 `/workspace/a-stock-data-reviews/` 或 `exports/`、不进湖、不改两个对照仓、不批量扫东财。

### 探针 A：申万 PIT 行业表落地与对照（零额度，1 次 HTTP）

**做什么**：独立 venv（Python 3.9+，`requests pandas xlrd`）跑一次 `SKILL.md` §6.7 的 `sw_industry_history()`，落成 CSV；再用 `sw_industry_as_of(df, code, today)` 生成"今日一级行业"列，与 1.3 的 `{SOURCE}/vendor_wind_sw_l1/wind_l1_map.csv` 做比对（比对口径沿用 `MyQuant-backtrader/oskh_data/industry_sw_l1.py` 的 `normalize_industry()`）。

**量什么**：overlap 股票数、今日一级行业一致率、冲突明细。以及一个必须先回答的前置问题——申万只给代码不给中文名，`480000 → 银行` 这张映射表从哪来；如果拿不到，探针的产出就只能是"代码维度的 PIT 表 + 一份缺名清单"。

**为什么值得先做**：这是三个探针里唯一能**直接省 Kimi 额度**并且**补一个 Wind 路径没有的维度**的。成本是一次 xls 下载。

**失败也有价值**：如果申万站点结构已变，`sw_industry_history()` 会抛 `RuntimeError("申万表结构变了，缺列 …")`（它校验 `code`/`start_date`/`industry_code` 三列），这个失败本身就回答了"这条路还通不通"。

### 探针 B：2027 年交易日历交叉校验（12 次 HTTP）

**做什么**：跑 `SKILL.md` §12.4 的 `trading_calendar(2027, m)`，m = 1..12，与 1.3 `common/infra/trading_calendar_pmc.get_trade_days_sse` 的 2027 年结果逐日 diff。

**为什么是 2027**：`trading_calendar_pmc.py` 的 docstring 自己写了 "XSHG … misclassifies 2027+ statutory holidays as trading days"，虽然它已经切到 SSE 日历，但跨年推断的风险类别没变。2027 正是风险年。

**两种结果都是结论**：
- 深交所已发布 → 拿到官方逐日 `is_open`，diff 出的任何差异都是 `pandas-market-calendars` 的推断误差，可以直接开 issue。
- 深交所尚未发布 → 函数抛 `RuntimeError("深交所尚未返回该月日历；不能推断全月休市")`，这恰好证明"官方日历只能当体检工具，不能当唯一来源"，也是有用的边界。

**为什么小**：12 次请求，交易所官方域名，风险等级是优先级 2（极低）。

### 探针 C：PIT lifecycle 可行性 spike（只出报告，不造表，不改 BT）

**做什么**：挑一小批已知样本——至少包含一只恢复上市股、一只长期停牌后复牌股、一只北交所迁码股（如 `920982` / 旧码 `832982`）——跑 §6.6 `baostock_stock_basic()` 与 §6.5 `baostock_valuation_history()` 的 `tradestatus` 列，逐条核对能否构造出 `MyQuant-backtrader/backtest/research/rule_profile.py:29-33` 所要求的 IPO / relist / resumption 三类事实。

**预期结论（需要实测确认，现在只是假设）**：IPO 能直接给；resumption 只能从 `tradestatus` 0→1 推导，而这与 BT 写死的 "not inferred from bars" 原则冲突，需要人裁；relist 与北交所无解。如果这个假设成立，结论就是"baostock 只能覆盖三分之一，`special_no_limit_days` 仍需 Wind"——**这个结论本身就值得在动用任何 Kimi 额度之前先写下来**。

**为什么不直接造表**：BT 的 DATA-MISSING 是 fail-closed 设计，喂一张不完整的 lifecycle 表进去比继续 fail-closed 更危险。先出判定报告，由人决定要不要走 Wind。

---

## 附：核实状态声明

**已核实（本机文件可直接复查）**：仓库文件构成与行数、LICENSE 类型与版权行、`SKILL.md` frontmatter 版本号、本地与远端 tag 列表、`git ls-remote` 的结果、各端点的代码与注释、`eastmoney_datacenter()` 的实现、`ssl.CERT_NONE` 的位置与使用者、测试方法计数（177 总 / 4 live / 173 离线）、路由表行数与函数名数、两个对照仓的文档与代码路径及行号。

**未核实（明确标注，未编造）**：
- 173 条离线测试当前是否全部通过（本机 Python 3.13.5，缺 pandas/numpy/mootdx/baostock，未执行；上游无 CI）。
- `SKILL.md` 与 `docs/` 里所有"实测 N 行 / 实测某日可取"的数字——这些是作者自述，我没有复跑任何端点。
- 东财 `PRETAX_BONUS_RMB` 到底是"每股"还是"每 10 股"口径。
- Kimi 的周额度 / 5h 窗口具体数值（三仓文档中均无记载）。
- `D:\exports\bt_corp_actions_20261006` 的内容与 schema（按硬约束未下载；两仓代码中零引用）。
- a-stock-data 各端点在 2026-10-09 当天的实际可用性（未发起任何数据请求）。
