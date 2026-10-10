# simonlin1212/a-stock-data 独立技术研究报告

研究者：Codex。核查日期：2026-10-09。范围：本机只读检出、仓内代码与指定操作文档，以及公开 GitHub 发布页。没有读取或采用 `a-stock-data-reviews/` 内的其他研究稿，没有修改三个研究仓、安装依赖、下载公司行为数据或批量请求东财。

本文把三种证据分开：**实现事实**指当前代码的可读行为；**仓内记录**指作者或操作文档记录的历史观测，本次没有重复联网验证；**本次验证**仅指文中明确列出的本地只读检查。适配建议是根据这些事实提出的方案，不代表已经接入或已经验收。

| 对象 | 本次读取基准 |
|---|---|
| `/workspace/a-stock-data` | HEAD、tag `v3.10.1` 均为 `8f6a6a53a59813bf5f010875f16f794fdc4f44f4`；工作树干净 |
| `/workspace/OSkhQuant1.3` | HEAD `42d066b81a083be49881f0dd8c5ab53ed4f422f6`；存在与本研究无关的既有工作树改动，未触碰 |
| `/workspace/MyQuant-backtrader` | HEAD `42d3f500008769024c42bd8cecdb94b30a0ac534`；工作树干净 |

已先读取主仓 README、SKILL、CHANGELOG、LICENSE 与三个测试文件，再核对 BT 的 [Kimi 金融补缺指针](/workspace/MyQuant-backtrader/docs/operations/kimi-financial-data-fill-pointer.md:1)、1.3 的 [SSOT 数据条目](/workspace/OSkhQuant1.3/docs/SSOT.md:195)、[三类存储](/workspace/OSkhQuant1.3/docs/operations/data-three-stores-ssot.md:1)、[ST 渠道](/workspace/OSkhQuant1.3/docs/operations/st-data-channels-ssot.md:1)、[Wind/ST/行业采集](/workspace/OSkhQuant1.3/docs/engineering/vendor-kimi-wind-harvest-2026-09-14.md:1)、[日线复权更新](/workspace/OSkhQuant1.3/docs/backtest/data/daily-adjusted-update-ssot.md:1)及 `oskh_data/` 实现。下文路径与行号均对应这次读取版本。

## 1. 项目本质与版本依据

`a-stock-data` 的交付物是一个自包含的 **Skill：结构化 Markdown 加内嵌 Python**。README 的安装方法是复制 `SKILL.md` 并安装它使用的第三方库，FAQ 明确说不带回测引擎。当前 Git 跟踪清单中没有 `pyproject.toml`、`setup.py`、可导入的主业务 Python 包或随仓分发的行情数据库；实际业务函数位于 7,577 行的 `SKILL.md`，三个 `.py` 测试文件从其中抽取代码运行。因此，它可以作为取数配方和代码来源，不能把当前检出描述成一个已经封装好、可直接 `pip install` 的行情 SDK，更不能把它当作本地完整行情库、持久化数据湖或撮合系统。此判断不涉及是否有人另行发布了同名 PyPI 包，后者未核实。[README：产品形态](/workspace/a-stock-data/README.md:45)、[安装](/workspace/a-stock-data/README.md:122)、[回测边界](/workspace/a-stock-data/README.md:485)、[测试抽取器](/workspace/a-stock-data/tests/test_v39_sources.py:37)。

版本应以**固定 commit 的 SKILL 实现**为准，tag 用于定位，README 和发布说明用于理解变更。此次 SKILL front matter 为 `3.10.1`，README 和 CHANGELOG 也已更新；公开 [v3.10.1 Release](https://github.com/simonlin1212/a-stock-data/releases/tag/v3.10.1) 标为 Latest，并指向 `8f6a6a5`，与本地 tag 一致。这次没有发现 README 顶部版本落后于 Release 的情况。[SKILL 版本](/workspace/a-stock-data/SKILL.md:1)、[CHANGELOG v3.10.1](/workspace/a-stock-data/CHANGELOG.md:3)。

一致的版本号不等于所有段落同步。现存三个具体偏差是：SKILL 前部把官方来源排在 mootdx 前、东财最后，尾部旧排序仍把 mootdx 排第二、东财 datacenter 排第三；尾部还写百度提供概念板块，而前面的 v3.2.2 记录已说明百度该接口失效并迁至东财；“每类数据都有独立备胎”的总括句紧接着又被备胎章节明确限定，打板、期权、舆情、事件驱动和可转债没有独立备胎。历史更新说明中的 §1.x 旧编号则是明确保留的历史编号，不应当作当前函数位置。[前部优先级](/workspace/a-stock-data/SKILL.md:320)、[百度迁移](/workspace/a-stock-data/SKILL.md:98)、[尾部旧表与总括](/workspace/a-stock-data/SKILL.md:7328)、[备胎限制](/workspace/a-stock-data/SKILL.md:7379)、[编号变更约定](/workspace/a-stock-data/SKILL.md:1048)。

## 2. 覆盖面、计数与主备来源

当前发布口径为 **15 层、87 个能力入口，其中 82 主入口、5 备胎，34 个来源**。这不是“87 个现在均已联网验活的独立 HTTP API”。README 的计数方法是能力清单 88 行，减去复用 reportapi 的行业研报行和本地北向历史缓存行，再给异动 list/count 增加一个入口。CYQ 属本地计算，mootdx 行情仍作为留档条目存在；“34 来源”也不是 34 家彼此独立的供应商，东财按若干服务分列，上交所与其 e互动按接口分列。[计数说明](/workspace/a-stock-data/README.md:144)、[来源表及计数注释](/workspace/a-stock-data/SKILL.md:7330)。

| 层 | 当前入口覆盖及主要来源 | 可核实的边界 |
|---|---|---|
| 1 行情 | 腾讯报价、日周月/分钟 K 线、当日分笔；通达信官网盘后包；百度 K 线；新浪因子；mootdx 留档 | 腾讯 K 线只支持沪深，分钟最多最近 320 根且不复权；分笔不是 Level-2；盘后包是某日全市场 raw 日线。[§1](/workspace/a-stock-data/SKILL.md:1048) |
| 2 研报 | 东财列表/PDF，同花顺一致预期，iwencai 语义搜索，新浪列表 | iwencai 需要 Key；新浪第二来源没有评级、目标价。[§2](/workspace/a-stock-data/SKILL.md:1910) |
| 3 信号 | 同花顺热点、北向；东财概念、资金流、龙虎榜、解禁、板块排名 | 北向历史是调用后积累的本地缓存；当前行业/概念不能自动代表历史归属。[§3](/workspace/a-stock-data/SKILL.md:2300) |
| 4 资金/筹码 | 东财两融、大宗、股东数、分红、资金流；本地 CYQ；沪深 ETF 份额 | CYQ 是 OHLC 与换手率推演；上交所份额按日归档、深交所为当前快照。[§4](/workspace/a-stock-data/SKILL.md:3005) |
| 5 新闻 | 东财、财联社、华尔街见闻、央视网 | 返回新闻文本或条目；不存在统一历史全量保证。[§5](/workspace/a-stock-data/SKILL.md:3484) |
| 6 基础数据 | mootdx 财务/F10；东财基本面；新浪三表；baostock 估值、ST、上市退市；申万历史行业 | baostock 不支持北交所；F10 当前文档只承诺“最新提示”；ST 快照与历史事件分开。[§6](/workspace/a-stock-data/SKILL.md:3759) |
| 7 公告 | 巨潮查询与附件地址，mootdx F10 摘要 | 巨潮映射有缓存和 fallback；摘要不是完整事件账本。[§7](/workspace/a-stock-data/SKILL.md:4217) |
| 8 打板 | 东财涨跌停/炸板/监控/异动，同花顺题材 | 没有独立备胎；属于池、标签和当期事件接口。[§8](/workspace/a-stock-data/SKILL.md:4313) |
| 9 ETF 期权 | 新浪合约、报价、Greeks、IV | 当前报价面，没有在此交付期权历史库。[§9](/workspace/a-stock-data/SKILL.md:4637) |
| 10 舆情互动 | 巨潮互动易、上证e互动、同花顺/东财热榜 | 互动易主要深市，上证e互动补沪市，不能混用覆盖范围。[§10](/workspace/a-stock-data/SKILL.md:4719) |
| 11 宏观利率 | 人民银行社融、统计局 PMI、中债曲线、货币网 FR/FDR、东财 LPR、见闻日历 | 不同发布日期、起始日和频率；获取时间不是历史已知时间。[§11](/workspace/a-stock-data/SKILL.md:5010) |
| 12 指数/日历 | 中证/国证成分权重、中证估值、深交所月度日历 | 成分权重为当前/最近文件，不能宣称历史调样库。[§12](/workspace/a-stock-data/SKILL.md:5511) |
| 13 期货大宗 | 五家期货交易所日行情/期权，四家持仓排名，新浪日 K/实时/A50，上金所现货 | 大商所官方日行情未接，新浪补其日 K；不同品种起始日不一。[§13](/workspace/a-stock-data/SKILL.md:5731) |
| 14 事件 | 东财业绩预告、机构调研、股东增减持、回购、质押、新股申购 | 默认 limit 有界、最大 5,000；质押仅沪深；公告日、变动日、报告期不可混同。[§14](/workspace/a-stock-data/SKILL.md:6506) |
| 15 可转债 | 东财条款、转股价、价值、溢价与上市摘牌状态 | 当前条款/状态接口，没有独立备胎。[§15](/workspace/a-stock-data/SKILL.md:6848) |

五个计数内备胎为官方龙虎榜、新浪资金流、公告、沪深官方两融、北交所当前行情。备胎表另外列有 URL 级配方和能力有限的降级：例如腾讯三个 K 线入口是同一后端的域名轮换；同花顺分钟备胎只有 30/60 分钟，1/5/15 分钟在 mootdx 恢复前没有独立备胎。换域名、换数据商、换字段覆盖是不同的事，不能据此声称所有字段都能无损切源。[README 备胎摘要](/workspace/a-stock-data/README.md:79)、[SKILL 备胎矩阵](/workspace/a-stock-data/SKILL.md:7383)。

README/CHANGELOG 中的历史延迟、可取日期、成功次数都是上游记录。此研究没有重测 87 个入口，不将“免费”“不封 IP”“稳定”这些文档标签改写为当前可用性、延迟或 SLA 承诺。

## 3. 可靠性与具体陷阱

### 3.1 TDX 与 mootdx：TCP 连通不代表行情可用

`tdx_client()` 为 BESTIP 问题提供候选服务器和真实请求验活，并区分 bars 与 finance 检查。当前版本明确记录：2026-09 起公开服务器 K 线、盘口、分笔返回空，财务/F10 仍可用；默认 bars 验活失败会报错并指向 HTTP 替代。F10 不能照旧写死九个类别，代码先用 `F10C` 枚举类别并实际读取“最新提示”。这里的可用性是发布时记录，本次没有 TCP 探测。[客户端](/workspace/a-stock-data/SKILL.md:454)、[留档行情](/workspace/a-stock-data/SKILL.md:1867)、[财务与 F10](/workspace/a-stock-data/SKILL.md:3761)、[变更记录](/workspace/a-stock-data/CHANGELOG.md:143)。

留档示例还有两个实际契约：`bars()` 返回 raw 价；频率参数是 `frequency`，传 `category` 会被 `**kwargs` 吞掉而继续默认日线。前者影响跨除权比较，后者可能把日线误认为分钟线。[SKILL §1.7](/workspace/a-stock-data/SKILL.md:1881)。

### 3.2 复权：不同来源的 qfq 不能只凭名字拼接

腾讯 K 线默认 qfq，文档解释其现金分红处理为等差口径，并记录长历史高分红股票可能出现非正价格；实现拒收非正 OHLC，推荐长区间另取 raw 后套新浪比例因子。新浪 `apply_adjust()` 的 qfq 是 raw **除以**因子、hfq 是 raw **乘以**因子，按不晚于 bar 日期的最近生效因子取阶梯值；空因子、早于最早因子的 bar 和零因子会失败。这不能直接替换 1.3 的 `close_front/close_none` 因子定义。[腾讯口径](/workspace/a-stock-data/SKILL.md:1190)、[新浪实现](/workspace/a-stock-data/SKILL.md:1719)、[1.3 因子 SSOT](/workspace/OSkhQuant1.3/docs/backtest/data/daily-adjusted-update-ssot.md:15)。

仍有可复现缺口：`apply_adjust()` 只检查 `cur == 0`，没有要求因子为正有限数；本次从原文 AST 抽取函数后，输入 `factor=-1` 得到负价格，输入 NaN 得到 NaN。该函数也只变换指定价格列，不生成现金应收、送股到账或登记日资格。应将其视为价格变换函数，不能当公司行为会计。[实现检查和变换范围](/workspace/a-stock-data/SKILL.md:1791)。

### 3.3 代码映射：必须同时保留六位代码与交易所

现有 `norm_ticker()` 用整串匹配，拒绝七位码、杂字串、前后缀矛盾；`get_prefix()` 已修复 `.SH/.SZ/.BJ` 与聚宽后缀，`stock_only=True` 拒绝显式沪市 `000xxx` 指数。本次纯函数探针得到 `em_secid('000001.SH') == '1.000001'`、`em_secid('sz000016') == '0.000016'`，这些修复在当前代码中存在。[市场规则](/workspace/a-stock-data/SKILL.md:557)、[归一化实现](/workspace/a-stock-data/SKILL.md:648)。

风险没有因此消失：裸 `000001` 默认深市个股，裸 `000016` 默认沪市指数；`norm_ticker()` 返回纯数字并丢失市场。实测 `get_prefix(norm_ticker('sh000001')) == 'sz'`，说明只做“先归一化再请求”会把上证指数导向同号深市票。应使用原串的市场加归一化数字，或边界统一成 `000001.SH` 后做端点专用映射。旧 `tencent_quote()` 还有独立路由实现，`600519.SH` 会被拼入非法查询串；不能假定所有函数接受同样输入格式。[歧义说明](/workspace/a-stock-data/SKILL.md:584)、[明确例外](/workspace/a-stock-data/SKILL.md:604)、[报价拼串](/workspace/a-stock-data/SKILL.md:1073)。

### 3.4 北交所：覆盖按端点判定，旧码不能机械替换

当前代码识别 `4/8/92` 号段，但没有完整的证券历史改码主表。仓内记录称部分北交所旧码会返回静止报价或空研报；报价函数仅加 stale 标志，研报函数仅在**结果为空且代码前两位为 43/83/87**时拒绝，并不是所有旧码一律拒绝。不能把号码规则当成已经验证的历史身份映射。[旧码警告](/workspace/a-stock-data/SKILL.md:586)、[研报条件](/workspace/a-stock-data/SKILL.md:1958)。

腾讯 K 线、腾讯分笔、baostock、股权质押分别拒绝或不覆盖北交所；北交所当前行情备胎不是历史行情。通达信盘后包以 `2022-05-06` 为含北交所文件的边界，之前只返回沪深，之后缺北交所文件报错；这是当前实现的边界和上游历史抽查结论，不能推导为北交所全历史齐全。[K 线](/workspace/a-stock-data/SKILL.md:1184)、[盘后包](/workspace/a-stock-data/SKILL.md:1389)、[分笔](/workspace/a-stock-data/SKILL.md:1509)、[baostock](/workspace/a-stock-data/SKILL.md:3899)、[质押](/workspace/a-stock-data/SKILL.md:6519)、[官方备胎](/workspace/a-stock-data/SKILL.md:7168)。

### 3.5 限流与重试：helper 不会替调用方完成并发隔离

`em_get()` 使用复用 Session、默认 1 秒间隔、在需要等待时附加随机抖动；urllib3 重试配置覆盖连接错误和 429/部分 5xx，不包含 403。实现只有进程内时间戳，没有线程锁或跨进程锁，所以“串行限流”依赖调用方确实串行；多个 agent 或进程各自加载一份 helper，不会形成 IP 级全局限速。旧 urllib3 不能构造重试配置时还会降级。[实现](/workspace/a-stock-data/SKILL.md:754)。

SKILL 自身既写腾讯“不封 IP”，又记录单入口限流后返回空；东财部分子域被封而 datacenter 未受影响的案例，也与笼统“全系同一风控面”说法不完全一致。合理可核验的结论是：代码有有限退避和域名降级，公开接口依然可能限流、失效或返回伪空；文档列出的社区请求阈值不是本次测量的安全边界。[限流记录](/workspace/a-stock-data/SKILL.md:340)、[腾讯轮换](/workspace/a-stock-data/SKILL.md:1186)。

### 3.6 成交量、金额与分钟时钟不能统一猜测

v3.10.1 修的是腾讯 K 线**文档单位**，没有改返回数值：688/689 科创板是股，其余相关股票/ETF 为手，通常每手 100 股/份；可转债每手 10 张。腾讯分笔包括科创板在内仍是手；通达信盘后包的个股成交量是股，指数等特殊代码保留通达信原值，须另核单位。单位必须绑定“来源、函数、品种”，不能对所有返回量乘 100。[变更原文](/workspace/a-stock-data/CHANGELOG.md:10)、[K 线返回合同](/workspace/a-stock-data/SKILL.md:1194)、[分笔合同](/workspace/a-stock-data/SKILL.md:1509)。

仓内还记录腾讯非科创日线整手取整，最近交易日分钟量随后回填、确切回填时刻未测定；腾讯与 Baostock 的深市整分边界不同，13:01 开盘价和集合竞价归桶也有特别语义。K 线本身没有成交额，不能把换手率字段当金额，更不能用 `close×volume` 冒充真实成交额。BT 已要求分别声明分钟标签、单位、时间编码、稀疏网格和竞价政策，缺根不等于已观测零成交，禁止盲补零、盲加一分钟。[腾讯对账说明](/workspace/a-stock-data/SKILL.md:1197)、[BT 对齐合同 §§2–5](/workspace/MyQuant-backtrader/docs/backtest/ssot/vendor-bar-alignment-ssot.md:9)。

### 3.7 空结果与接口坏：新旧层不能合并评价

v3.9 的 `_em_datacenter_strict()` 检查 HTTP、JSON、业务码、分页、总数变化和中途空页；第 1 页明确 `9201` 无数据可返回空，其他业务错误失败。`_v39_frame()` 附带 `source/source_url/fetched_at`，但 `fetched_at` 是获取时间，不是事件当时的可知时间；`max_rows` 仍允许在来源总数超限时截断。[严格 helper](/workspace/a-stock-data/SKILL.md:934)、[分页实现](/workspace/a-stock-data/SKILL.md:966)。

旧 `eastmoney_datacenter()` 固定 `pageNumber=1`，不检查 HTTP 状态或业务码，缺 `result.data` 就返回 `[]`。`dividend_history()` 复用它；旧 `eastmoney_reports()` 用 `d.get('data') or []` 作为翻页终止条件。本次给三个函数注入 `{'success': False, 'code': 500, 'message': 'upstream failed'}` 的模拟返回，三者均返回 `[]`。这是本地执行发布代码得到的结果，直接否定“所有空表都可靠地表示没事件/没覆盖”的假设。[旧 helper](/workspace/a-stock-data/SKILL.md:785)、[分红调用](/workspace/a-stock-data/SKILL.md:3113)、[研报处理](/workspace/a-stock-data/SKILL.md:1948)。

旧腾讯报价对短载荷直接跳过，可最后返回 `{}`；输出没有行情时间，`is_stale` 的实际条件是成交额为零、价格等于昨收且大于零，不能验证行情是否新鲜。新浪研报则记录“限流空页与真正无研报相同”，最小间隔加重试只能降低误判，不能证明每次空页真实无数据。[腾讯解析](/workspace/a-stock-data/SKILL.md:1094)、[stale 条件](/workspace/a-stock-data/SKILL.md:1127)、[新浪空页记录](/workspace/a-stock-data/SKILL.md:2227)。

分笔完整性也有三态：`attrs['complete']` 可为 True、False、None；盘中或无法对账不等于完整。收盘后金额容差仍可能漏掉小额缺笔，数据为约 3 秒分笔快照，不能当逐笔 Level-2 证据。[分笔与完整性](/workspace/a-stock-data/SKILL.md:1509)、[v3.10.1 限制](/workspace/a-stock-data/CHANGELOG.md:35)。

### 3.8 本次验证到哪一步

三个测试文件确实直接抽取发布的 Markdown 代码，并使用 mock 覆盖日期、单位、分页、错误传播等。静态计数为 official 27、v3.9 115、v3.10 35，共 **177 个测试方法，其中 4 个需显式开启联网**。这个数字是方法数，不是 87 个入口的覆盖率，更不是本次成功调用数。[测试加载方式](/workspace/a-stock-data/tests/test_official_data.py:21)、[v3.9 标记块](/workspace/a-stock-data/tests/test_v39_sources.py:27)、[v3.10 测试](/workspace/a-stock-data/tests/test_v310_sources.py:1)。

本次尝试运行离线 unittest 时设置 `PYTHONDONTWRITEBYTECODE=1`、清除全部 `ASTOCK_LIVE*`，并让 socket 连接直接失败；系统 Python 3.13 缺少 pandas，测试导入及大量 setUp 失败，**未完成整套测试验证**。没有安装依赖。上述代码映射、旧 helper 伪空、负/NaN 因子三个小探针使用标准库 AST 提取函数单独完成，未联网。CHANGELOG 声称在 Python 3.9.6/3.12.13 下全套通过，本文仅保留为上游记录。[依赖导入](/workspace/a-stock-data/tests/test_official_data.py:17)、[上游测试记录](/workspace/a-stock-data/CHANGELOG.md:60)。

下面命令复现本次三个纯函数探针；仅抽取定义，避免执行文档内的联网示例，不写文件。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import ast, re
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

wanted = {
    'get_prefix', 'em_market_code', 'em_secid', 'norm_ticker',
    '_natural_market', 'eastmoney_datacenter', 'dividend_history',
    'eastmoney_reports', 'apply_adjust',
}
constants = {'SH_INDEX', '_TICKER_RE', '_JQ_SUFFIX'}
ns = {'re': re, 'Optional': Optional}
text = Path('/workspace/a-stock-data/SKILL.md').read_text()
for block in re.findall(r'```python\n(.*?)\n```', text, re.S):
    try:
        tree = ast.parse(block)
    except SyntaxError:
        continue
    body = [n for n in tree.body
            if (isinstance(n, ast.FunctionDef) and n.name in wanted)
            or (isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in constants for t in n.targets))]
    if body:
        exec(compile(ast.Module(body=body, type_ignores=[]),
                     'SKILL.md:offline-audit', 'exec'), ns)
error = {'success': False, 'code': 500, 'message': 'upstream failed'}
ns.update(em_get=lambda *a, **k: SimpleNamespace(json=lambda: error),
          DATACENTER_URL='audit:no-network', REPORT_API='audit:no-network')
print('mapping', ns['em_secid']('000001.SH'), ns['em_secid']('sz000016'),
      ns['get_prefix'](ns['norm_ticker']('sh000001')))
for fn in ('eastmoney_datacenter', 'dividend_history', 'eastmoney_reports'):
    print(fn, ns[fn]('600519'))
for value in (-1.0, float('nan')):
    print('factor', value, ns['apply_adjust'](
        [{'date': '2020-01-01', 'close': 10.0}],
        [{'date': '1900-01-01', 'factor': value}]))
PY
```

本次输出依次为 `mapping 1.000001 0.000016 sz`、三个 `[]`，以及 `close=-10.0`、`close=nan`。模拟错误载荷只验证解析行为，不证明真实服务在本次返回过该错误。

## 4. 许可证、Python 与共享环境

当前 LICENSE 是 **Apache License 2.0**，版权行 `Copyright 2026 Simon Lin`。README 的“注明出处即可”不是完整条款：LICENSE §4 还列出再分发时提供许可证、修改文件显著说明、保留适用声明，以及原分发含 NOTICE 时的相应保留要求；§7–8 为无担保和责任限制。这里只描述仓内文本，不把代码许可证扩展成第三方行情、公告 PDF 或 Wind 数据的再分发授权，后者未核实。[LICENSE §§4、7–8](/workspace/a-stock-data/LICENSE:89)、[版权行](/workspace/a-stock-data/LICENSE:178)、[README 简述](/workspace/a-stock-data/README.md:587)。

README 声明 Python 3.9+。安装清单是 `mootdx requests pandas stockstats numpy baostock xlrd openpyxl`；SKILL 对 mootdx、baostock、xlrd 给下限，其余多为 any，没有随仓 lockfile。mootdx 和 baostock 走 TCP，其他主体走直接 HTTP；iwencai 是需要 Key 的例外。v3.0 移除了 akshare 依赖。[依赖表](/workspace/a-stock-data/SKILL.md:422)、[iwencai](/workspace/a-stock-data/SKILL.md:441)、[v3.0](/workspace/a-stock-data/CHANGELOG.md:896)。

共享环境风险有明确依据：README FAQ 记录 mootdx 声明 `httpx<0.26` 与 MCP 所需较新 httpx 冲突，并建议过 `--no-deps` 强升或隔离环境。本次没有做 resolver 实验，不能说当前共享环境已经发生该冲突，也不能把绕过依赖声明当成兼容性证明。BT 则固定 `pandas==3.0.6`、要求 Python ≥3.12；1.3 AGENTS 指定 vanna312 环境与解释器解析顺序，并禁止在自托管 CI 安装依赖。因此可执行的接入方式应先在隔离解释器测试所需片段，而不是把 README 安装命令直接放进共享交易环境。[冲突 FAQ](/workspace/a-stock-data/README.md:518)、[BT 依赖](/workspace/MyQuant-backtrader/requirements.txt:1)、[BT Python](/workspace/MyQuant-backtrader/pyproject.toml:8)、[1.3 环境约束](/workspace/OSkhQuant1.3/AGENTS.md:41)。

## 5. 对 MyQuant-backtrader 的适配边界

BT 当前定位是向量化研究，已不是一个等待接入行情源的 Cerebro 服务；`AGENTS.md` 明确所有外部下载和 vendor merge 由 1.3 拥有，BT 只读配置湖。因而合适的形态是**1.3 侧采集的可选离线数据或经过校验的研究旁表，BT 按显式参数消费**，不能在策略循环里复制取数代码，也不能在缺行情时悄悄调用腾讯补齐。[BT 定位](/workspace/MyQuant-backtrader/AGENTS.md:1)、[采集所有权](/workspace/MyQuant-backtrader/AGENTS.md:58)、[Kimi 指针分工](/workspace/MyQuant-backtrader/docs/operations/kimi-financial-data-fill-pointer.md:5)。

| 候选用途 | 适配判断与必要条件 |
|---|---|
| 机构调研、业绩预告、增减持、回购、解禁、公告、新闻 | 可作可选事件/文本旁表；保存原始返回、来源、获取时间、公告时间与生效时间，确认分页与 limit 后才能做历史 join。[事件合同](/workspace/a-stock-data/SKILL.md:6506) |
| 上市退市、历史 ST、申万变迁 | 可作研究过滤或交叉核查；baostock 限沪深，当前 ST 快照不能补历史戴摘帽；行业生效日回溯不自动等于当时发布版本可得性。[基础数据](/workspace/a-stock-data/SKILL.md:3899) |
| 当前指数成分/权重、ETF 份额、宏观 | 可作带快照日期的研究表；当前成分不能回填过去选股宇宙，修订后的宏观历史值也没有自动证明 PIT。[指数边界](/workspace/a-stock-data/SKILL.md:5511) |
| 备用 OHLCV | 可作单票小窗离线对拍；先证明身份、raw/front 口径、单位、时钟、竞价和稀疏语义，再讨论研究 overlay；不能因为数字相近直接混写现有湖。[BT 对齐合同](/workspace/MyQuant-backtrader/docs/backtest/ssot/vendor-bar-alignment-ssot.md:36) |
| CYQ | 只能作为另一种研究算法进行比较；BT 已明确 CYQ/TR 分工，不能把此处本地推演当成官方筹码，或再复制一套全市场 feeder。[CYQ 实现](/workspace/a-stock-data/SKILL.md:3202)、[BT 边界](/workspace/MyQuant-backtrader/AGENTS.md:52) |

BT 的信号价与模拟成交价也不能混用。例如 version12 的日线信号域固定 front，分钟成交默认 raw/none，front 分钟只允许显式选择且缺分区即失败；外部 qfq 数据不应触发第二次静默除权调整。[version12 价域约定](/workspace/MyQuant-backtrader/AGENTS.md:23)。

分红尤其不能直接接：`dividend_history()` 默认只取 20 行，字段只有除息日、现金、送转和进度；现金原值被注释为每股，送转原值被注释为每 10 股，代码没有做完整的单位规范化。它没有支付日、新增股份上市日、唯一事件标识或公告可知时间。现金原字段的实际单位本次**未核实**。[原始字段](/workspace/a-stock-data/SKILL.md:3113)。

BT 的 `ExDivEvent` 则要求 `event_id/bonus_ratio/cash_div_per_share/ex_date/pay_date`，可选 `list_date`；日期为 `YYYYMMDD`，支付与上市日期不得早于除权日。`ashare_exdiv_economics.py` 明说不含 loaders，登记日资格也不在该切片范围内。故目前缺的是可验证的事件映射与数据完整性，不是把五列重命名后即可使用；把缺失支付日猜成除权日、把缺字段默认零视为“无分红”，都会改变现金和股份时序。[BT 事件合同](/workspace/MyQuant-backtrader/backtest/research/ashare_exdiv_economics.py:1)、[验证与记账](/workspace/MyQuant-backtrader/backtest/research/ashare_exdiv_economics.py:85)。

**绝不可进入 live/paper 下单决策价的内容**包括 a-stock-data 的腾讯报价、五档备胎、分钟/日线、分笔、推算均价、复权价，以及缓存后的这些价格。1.3 当前原则㉑只允许 `get_full_tick` 与 `instrument_detail`，连 QMT 自己的 `get_market_data_ex` 下载缓存也禁止；白名单取不到价就跳过，不能以公开 HTTP 或本地湖回落。这里限制的是下单决策价，不是否定经校验的离线回测输入。[价格源铁律](/workspace/OSkhQuant1.3/docs/architecture/design-principles.md:205)。

## 6. 与 OSkhQuant1.3 的已有数据层比较

### 6.1 1.3 已有的存储和模块

1.3 的“三类存储”明确为 **Parquet 行情湖、DuckDB 派生读面、SQLite 交易运行时库**。`OSKH_SOURCE_PARQUET_ROOT` 是行情容器必填入口，未设时报错，不能猜 E/F 盘；细粒度 `OSKH_PERIOD_*` 可覆盖它。DuckDB 经 `resolve_e_stock_data_container()` 位于工作区 `{OSKH_DATA_ROOT}/stock_data`，SQLite 经 strategy_config 独立解析。文档里的开发机 F 盘、测试机 E 盘是实例，不是跨机常量。[存储总览及 resolver](/workspace/OSkhQuant1.3/docs/operations/data-three-stores-ssot.md:9)、[源码](/workspace/OSkhQuant1.3/common/infra/data_root.py:103)。

行情湖按资产分三树：`stock/period={1d,1m}`、`index/period={1d,1m}`、`etf/period=1d`，再按复权与 symbol 分区；还有 `adj_factor.parquet`、股本与 vendor 旁表。`lake_kind.py` 要求代码带市场，裸 `000001` 为 unknown，恰好比公开接口的号段猜测更严格。`StockDataReader` 支持逐文件、DuckDB 内存扫描 Parquet、持久 DuckDB 只读，并按资产与复权路由。[三树](/workspace/OSkhQuant1.3/AGENTS.md:11)、[资产识别](/workspace/OSkhQuant1.3/oskh_data/lake_kind.py:1)、[读面](/workspace/OSkhQuant1.3/oskh_data/reader.py:1)。

| `oskh_data/` 职责 | 已有模块 |
|---|---|
| QMT 下载与通道 | [downloader.py](/workspace/OSkhQuant1.3/oskh_data/downloader.py)、[download_transport.py](/workspace/OSkhQuant1.3/oskh_data/download_transport.py:87)、[qmt_download_channel.py](/workspace/OSkhQuant1.3/oskh_data/qmt_download_channel.py) |
| 读取与维护 | [reader.py](/workspace/OSkhQuant1.3/oskh_data/reader.py)、[backfill.py](/workspace/OSkhQuant1.3/oskh_data/backfill.py)、[minute_backfill.py](/workspace/OSkhQuant1.3/oskh_data/minute_backfill.py)、[daily_parquet_write.py](/workspace/OSkhQuant1.3/oskh_data/daily_parquet_write.py) |
| 质量检查 | [download_coverage.py](/workspace/OSkhQuant1.3/oskh_data/download_coverage.py)、[freshness.py](/workspace/OSkhQuant1.3/oskh_data/freshness.py)、[integrity.py](/workspace/OSkhQuant1.3/oskh_data/integrity.py)、[audit.py](/workspace/OSkhQuant1.3/oskh_data/audit.py) |
| 因子与股本 | [adj_factor.py](/workspace/OSkhQuant1.3/oskh_data/adj_factor.py)、[float_shares.py](/workspace/OSkhQuant1.3/oskh_data/float_shares.py)、[free_float_shares.py](/workspace/OSkhQuant1.3/oskh_data/free_float_shares.py) |
| 指数、ETF、专题来源 | [index_minute.py](/workspace/OSkhQuant1.3/oskh_data/index_minute.py)、[etf_backfill.py](/workspace/OSkhQuant1.3/oskh_data/etf_backfill.py)、[vendor_wind_st.py](/workspace/OSkhQuant1.3/oskh_data/vendor_wind_st.py)、[vendor_wind_sw_l1.py](/workspace/OSkhQuant1.3/oskh_data/vendor_wind_sw_l1.py)、[vendor_qmt_st_snapshot.py](/workspace/OSkhQuant1.3/oskh_data/vendor_qmt_st_snapshot.py) |

这些文件证明 1.3 已有存储、下载、维护和消费框架；它们不证明远端 Windows 机器此刻每个分区都完整。a-stock-data 并未交付这些同等的湖管理设施。

### 6.2 更新节奏与价格口径

权威日更入口是 `run_daily_adjusted_fast.py`：检测新除权日，增量下载 none，除权股删除旧 front 并全历史重下 QMT front，非除权股通过路径 B 追加当日 `front=none`，随后只读已落盘 front/none 计算因子，再 rebuild DuckDB。back 默认不下；`get_divid_factors` 的 dr 只做除权检测，不得推导 front。代码中每月 1 日或 `--full`、周日或 `--force-refresh-front` 触发全市场 front 重下。这里核实的是流程和触发条件，实际任务今日是否执行、调度时间及水位未核实。[日更 §§1–3](/workspace/OSkhQuant1.3/docs/backtest/data/daily-adjusted-update-ssot.md:11)、[日期触发实现](/workspace/OSkhQuant1.3/scripts/data/run_daily_adjusted_fast.py:562)。

股票主轨、指数/ETF 副轨已经分开；指数 none-only，ETF none/front，另有指数分钟独立通道。不能因为 a-stock-data 也返回日线，就绕过已有复权基准和资产分树规则。[副轨](/workspace/OSkhQuant1.3/docs/backtest/data/daily-adjusted-update-ssot.md:47)、[指数分钟](/workspace/OSkhQuant1.3/oskh_data/index_minute.py:1)。

需要防一处旧注释误导：`oskh_data/__init__.py` 仍描述交易用本地 none 查涨停和收盘，已与当前原则㉑冲突；本文按当前明确价格白名单划界，不能用旧模块简介为公开行情进入实盘决策背书。[旧简介](/workspace/OSkhQuant1.3/oskh_data/__init__.py:9)、[当前原则](/workspace/OSkhQuant1.3/docs/architecture/design-principles.md:205)。

### 6.3 已有事件与真正的补缺处

ST 已有五渠道分工：深交所简称变更提供深市生效日事件，巨潮补沪京公告，Wind/Kimi 补沪京历史，QMT 提供当日名称，东财仅当日备胎。QMT 的盘前交易闸 `daily_st_set` 与 15:30 后独立拍摄的 `vendor_qmt_st_names` 研究湖不能互顶；`day=T` 是缓存键，不是历史查询，不能据此回填历史名称。a-stock-data 当日 ST 主源仍是东财、fallback 为仅沪深 baostock，主要重复已有快照备胎，补不了真实历史戴摘帽日期。[ST 五渠道及日程](/workspace/OSkhQuant1.3/docs/operations/st-data-channels-ssot.md:10)、[QMT 历史限制](/workspace/OSkhQuant1.3/docs/operations/st-data-channels-ssot.md:53)、[a-stock ST](/workspace/a-stock-data/SKILL.md:4095)。

行业的缺口更具体：1.3 的 `vendor_wind_sw_l1.py` 合并产物为代码、名称、当前 Wind 申万一级三列，没有生效日期。a-stock-data 从申万 XLS 取 `start_date` 和层级代码，`sw_industry_as_of()` 按生效日取记录，可补历史分类研究候选；但只有分类代码，不能套用东财/通达信中文名，也没有证明原始 XLS 各历史发布版本可追溯。[1.3 合并 schema](/workspace/OSkhQuant1.3/oskh_data/vendor_wind_sw_l1.py:105)、[申万历史实现](/workspace/a-stock-data/SKILL.md:4017)。

公司行为方面，1.3 `ex_date_index` 的列是 `stock_code/ex_date/dr/fetched_at`，用途是发现除权并触发 front 刷新；这不等于包含登记、支付、新股上市与现金/送转数量的完整事件账本。`free_float_shares.py` 另有报告期股本历史，其报告截止时间也不自动代表公告可知时间。在本次检视的 `oskh_data/` 与相关下载脚本中，未核实到与用户 4090 corp-actions 目录等价的完整导入管线。a-stock-data 五列分红摘要同样不能补齐该合同。[除权索引](/workspace/OSkhQuant1.3/scripts/data/detect_ex_date_changes.py:49)、[股本历史](/workspace/OSkhQuant1.3/oskh_data/free_float_shares.py:4)。

因此，重复项主要是 OHLCV、复权、指数/ETF 行情、当前 ST 和当前行业；补缺候选主要是申万历史变迁、沪深上市退市信息、机构调研/回购/增减持等事件、研报文本、宏观、指数当前成分权重，以及期货大宗资料。这里的“补缺候选”是相对已检查的数据面，不宣称 1.3 全仓绝无同类能力；公告尤其已有巨潮/Kimi 体系，应复用既有职责而非再造采集器。[1.3 公告索引](/workspace/OSkhQuant1.3/docs/SSOT.md:246)、[a-stock 能力表](/workspace/a-stock-data/README.md:59)。

## 7. 与 Kimi/Wind 金融补缺比较

### 7.1 现成链路、鉴权和额度

BT 指针与 1.3 操作页互相一致：1.3 本地生成问题串并 merge，Kimi 会话通过 `data_source_name=wind`、`api_name=wind_get_financial_data` 获取 ST/行业数据，不是本地直连 Wind 桌面或一个 Python Wind SDK。提示词前提是启用 `kimi-datasource≥3.4.0` 并 `/login`，每批 100 码，403/额度即停；深市日常 ST 已走深交所免费渠道，不应重复消耗 Kimi。[采集所有权](/workspace/OSkhQuant1.3/docs/engineering/vendor-kimi-wind-harvest-2026-09-14.md:3)、[ST 提示词](/workspace/OSkhQuant1.3/docs/prompts/prompt-kimi-datasource-st-harvest.md:1)。

调用纪律是场景相关的：ST/行业提示词禁止 `get_data_source_desc`，BT 2026-10-01 instruments 佐证包却要求它；不能把某一场景规则推广到全部 Wind 调用。BT 指针还明确分钟接口是 `wind_get_stock_quote`，并记录实际补缺案例；错误接口名返回 `API_NOT_FOUND` 不等于 Wind 没有分钟线。[BT 指针](/workspace/MyQuant-backtrader/docs/operations/kimi-financial-data-fill-pointer.md:6)。

**周额度与 5 小时窗口有本地文档依据**：BT 额度操作页记载 Kimi `/usages` 的 `usages.limit_7d.used_ratio`、`usages.limit_5h.used_ratio` 与各自 `reset_time`，鉴权为配置中的 API Key。它描述 Kimi Code 账户额度，不能据此虚构独立的 Wind 每周次数上限。本次未读凭据、未查询账户，当前套餐、剩余额度、重置时间和单次调用成本均未核实。[额度字段，§3.1](/workspace/MyQuant-backtrader/docs/operations/grok-bot-raci-workflow-ssot.md:91)。

### 7.2 公司行为、分红与上市信息的证据强度

用户指定 4090 的 `D:\exports\bt_corp_actions_20261006` 是本任务的宿主定位信息。本次没有访问 4090、没有下载该目录；在两个对照仓已检索的 Markdown 中也未找到该目录名。**其文件清单、schema、哈希、覆盖率、支付日/上市日字段、是否已入湖均未核实**，不能把“路径存在于任务说明”改写成“完整 Wind 公司行为库已通过验收”。

本地已有的 instruments 原始 CSV 也要按字段理解：`wind_603196_info.csv` 包含“成立日期”和公司资料，没有结构化的上市日或历史 ST 生效区间字段；成立日不能当 IPO 日，当前简称不能证明过去某窗口不是 ST。佐证包 README 本身将其定位为 evidence-only，未重写 living instruments。本文不把包内总结性结论当成历史上市资格已经证明。[原始字段](/workspace/MyQuant-backtrader/docs/backtest/b-l2-01-evidence-2026-09-30/kimi_instruments_fill_20261001/raw/wind_603196_info.csv:1)、[包用途](/workspace/MyQuant-backtrader/docs/backtest/b-l2-01-evidence-2026-09-30/kimi_instruments_fill_20261001/README.md:3)。

a-stock-data 的对照是：baostock `stock_basic` 返回 `ipoDate/outDate/status`，适合作沪深上市退市的独立核查；`ipo_calendar()` 是新股申购日历，不是完整证券生命周期库；`dividend_history()` 是有字段和分页缺口的分红摘要；Layer 14 提供调研、预告等其他事件，不能与公司行为到账表混为一谈。[上市退市](/workspace/a-stock-data/SKILL.md:3991)、[事件接口](/workspace/a-stock-data/SKILL.md:6506)、[分红摘要](/workspace/a-stock-data/SKILL.md:3110)。

### 7.3 可靠性与成本不是“付费可靠、免费不可靠”的二分

| 比较点 | Kimi/Wind 本地可核实情况 | a-stock-data 本地可核实情况 |
|---|---|---|
| 访问与费用 | 依赖登录、插件和账户额度；实际账单和 Wind 商业条款未核实 | 多数公开接口免 Key，iwencai 例外；文档称免费，运维与修解析器成本仍存在，未测金额 |
| 空数据 | ST 指南记录 Wind “没找到数据”可能作为工具错误返回，需确认后 write-empty；QUOTA 不等于数据失败 | 新严格 helper 区分空和坏；旧分红/研报入口已复现伪空 |
| 结果质量 | 行业指南记录 canned/空码/空行业需隔离并拆批重试，不能把自然语言返回自动当合格表 | URL/解析器可读，易复现；上游字段、反爬与历史范围会变，缺统一持久化/全链路验收 |
| 行情补缺 | BT 有 `wind_get_stock_quote` 分钟补缺及区间、单位对齐记录 | 腾讯分钟仅最近有限根数，时钟与单位有明显端点差异，不是任意历史分钟替代品 |

依据：[Wind 空批规则](/workspace/OSkhQuant1.3/docs/prompts/prompt-kimi-datasource-st-harvest.md:9)、[行业拆批规则](/workspace/OSkhQuant1.3/docs/prompts/prompt-kimi-datasource-industry-harvest.md:8)、[BT 分钟记录](/workspace/MyQuant-backtrader/docs/operations/kimi-financial-data-fill-pointer.md:9)、[公开接口限制](/workspace/a-stock-data/SKILL.md:1184)。未做同样本现场对拍，故本报告不提供二者完整率、延迟、成功率或费用节省百分比。

### 7.4 保留与迁移的具体边界

适配建议是保留 Wind/Kimi 作为沪京历史 ST 生效事件、经过原始字段核实的公司行为、公开接口缺失的历史分钟及关键争议字段的补缺渠道；用户已有 corp-actions 产物先保留来源身份，待宿主只读 schema 核查再决定消费。这个建议建立在公开替代品的可见缺口上，不是宣称未读的 Wind 文件已完整。

可减少 Kimi 消耗的方向是公开研报/公告/新闻、调研与回购等可选研究事件、官方指数当前文件、宏观、沪深上市退市核查和申万历史分类。应逐入口迁移，并保留生效日、来源和错误语义；深市 ST 日常已经使用深交所，属于现有免 Kimi 流程，无须为采用 a-stock-data 再迁一遍。分红摘要、ST 当前名单、当前指数成分，以及未对齐的腾讯分钟数据，都不具备直接替换完整历史事件或湖行情的证据。[既有 ST 分工](/workspace/OSkhQuant1.3/docs/operations/st-data-channels-ssot.md:14)、[基础与事件覆盖](/workspace/a-stock-data/README.md:59)。

## 8. 下一步：三个小探针

以下是有限范围实验建议，不是本次已经完成的联网工作；不要求改两套对照仓或下载 4090 corp-actions。

1. **补齐隔离环境后的离线合同复跑。** 使用一个已具备 pandas、requests、openpyxl 等测试依赖的隔离解释器，从主仓运行 `PYTHONDONTWRITEBYTECODE=1 <隔离Python> -m unittest discover -s tests -v`；清除全部 `ASTOCK_LIVE*`，继续阻断 socket。目标是验证 173 条默认离线测试，并重复本次三个小探针：显式市场不能丢、错误 JSON 不能被外部适配器当真空、因子必须正且有限。保留“缺依赖/断言失败/正常空”三种不同结果；无需在共享 vanna312 内强升依赖。[测试入口](/workspace/a-stock-data/README.md:558)、[需重点封装的旧 helper](/workspace/a-stock-data/SKILL.md:785)。

2. **四票、一天的成交量对拍。** 固定 `688981、588000、600519、000001`，取已结束的 `2026-09-30`：只调用一次 `tdx_daily_package('2026-09-30')`，再各调用一次 `tencent_kline(code, start='2026-09-30', end='2026-09-30', adjust='')`；串行、遇错误停止，不扫东财。按科创 ×1、其余股票/ETF ×100 转股，与盘后包同证券比较 OHLC、量，保留日线取整差异；若日期文件不可取就记未完成，不扩大扫描。全部结果只作为研究证据保存在 reviews 下，不能写湖。这是 v3.10.1 已有单位测试的小规模固定日期版本；通过仅证明所选四票当天的单位关系。[现有 live 测试](/workspace/a-stock-data/tests/test_v310_sources.py)、[盘后包与单位](/workspace/a-stock-data/SKILL.md:1389)。

3. **一个分红端点的离线 schema 演练。** 抽取原文 `dividend_history()`，将 `eastmoney_datacenter` 替换成内存 fixture：一条完整上游行、一条缺支付/上市字段的行、一条错误 JSON 经旧 helper 返回空的情况。把输出字段集合与本地 `ExDivEvent` dataclass 对比，只生成缺口表，不构造支付日、不调用 economics 记账、不下载 Wind 数据。验收应明确得到“现有摘要不能直接构造有证据的事件”，并列出金额/每股比例、event_id、pay_date、list_date、公告可知时间的待补证项；未来若在 4090 就地读用户现有目录，可用同一缺口表核对原始字段，而不搬运整库。[分红实现](/workspace/a-stock-data/SKILL.md:3113)、[BT dataclass](/workspace/MyQuant-backtrader/backtest/research/ashare_exdiv_economics.py:18)。

当前证据支持的采用范围是：把固定 commit 的 a-stock-data 当作可审计的公开取数代码来源，逐入口验证后补离线研究数据；沿用 1.3 的采集与湖所有权、BT 的消费合同，以及 tick/instrument_detail 的下单决策价边界。远端 corp-actions 实物、当前在线可用率、共享环境完整兼容性和实际费用仍为未核实项。
