# simonlin1212/a-stock-data 独立研究报告（Grok CLI）

- 研究对象检出：`/workspace/a-stock-data`，`HEAD` = `8f6a6a53a59813bf5f010875f16f794fdc4f44f4`，与 tag `v3.10.1` 同一提交，作者日期 2026-10-07 14:22:38 +0800，说明为「v3.10.1 更正腾讯 K 线成交量单位与对账口径（#57）」。远程 `origin` = `https://github.com/simonlin1212/a-stock-data.git`，分支 `main` 与 `origin/main` 对齐。
- 本检出是浅克隆：`.git/shallow` 只有 `90fbbb47db2b7894024be484f9936c6658c06462`（2026-05-11，「docs: add TikTok to English author line」）。`git rev-list --count HEAD` = 50。2026-05-11 之前的历史对象不在本机，下文不引用浅边界之前的未检出提交。
- 对照仓 A：`/workspace/OSkhQuant1.3`，`HEAD` `42d066b81`（2026-09-30）。只读。
- 对照仓 B：`/workspace/MyQuant-backtrader`，`HEAD` `42d3f50`（2026-10-06）。只读。
- 本文不把 `/workspace/a-stock-data-reviews/` 里已有草稿当事实。没有访问 4090，没有下载公司行为包，没有对东财做批量请求。仓库 CHANGELOG / SKILL 里的「实测行数、价差、封禁时长」是**该仓库作者写下的记录**，本报告没有复跑，不把它们改写成新的实测。

跟踪文件只有 14 个：`SKILL.md`、`README.md`、`README_en.md`、`CHANGELOG.md`、`LICENSE`、两份 `docs/source-integration-v3.*.md`、三份 `tests/test_*.py`、`.github/FUNDING.yml`、`.gitignore`、两张赞助图。没有 `pyproject.toml`、`setup.py`、`requirements.txt`，也没有 GitHub Actions workflow。

---

## 1. 项目本质

它是一份给 AI 编程助手用的 **Skill**：一个自包含的 `SKILL.md`（本检出 7577 行），YAML 头声明 `name: a-stock-data`、`version: 3.10.1`，正文把可执行 Python 嵌在 Markdown 代码块里。`README.md` 第 45–49 行写明：Skill 是结构化 Markdown 加内嵌 Python，兼容 Claude Code、Codex、OpenClaw；安装方式是把文件放到 `~/.claude/skills/a-stock-data/SKILL.md`，或把正文贴进系统提示词。`SKILL.md` 第 119 行的使用方式与此相同。

它不是可 `pip install` 的 Python 发行包。仓库根没有包目录、没有入口模块、没有锁定的依赖文件。调用方式是助手在对话里摘出代码块执行，或测试用 `exec` 抽出标记块执行。`tests/test_v310_sources.py` 模块说明写着离线测试「直接执行 SKILL.md 里的发布代码」；`test_v39_sources.py` 提供 `load_shipped_code()` / `_marker_code()`。`docs/source-integration-v3.9.0.md`「验证方法」同样写：离线测试从 `SKILL.md` 取出发布代码执行，不访问网络。

它不是本地行情库。检出里没有 parquet、csv、sqlite，也没有日更调度。每次取数都是当场 HTTP 或 TCP（mootdx / baostock）。`SKILL.md` FAQ「能直接回测吗？」（约第 7498–7502 行）写明：本 skill 只负责取数，不带回测引擎；回测要把数据交给自己的框架或聚宽。

版本以三处同时为准，本检出三者重合：

| 位置 | 记载 |
|---|---|
| `SKILL.md` frontmatter | `version: 3.10.1`；标题「A股全栈数据工具包 V3.10.1」 |
| `README.md` / `README_en.md` | 徽章 layers-15、endpoints-87、sources-34、Python 3.9+、License Apache 2.0；中文 README 把 V3.10.1（2026-10-07 · #57）放在文首版本说明 |
| git | tag `v3.10.1` 指向 `8f6a6a53`，与 `main` 相同 |

`CHANGELOG.md` 首节即 `v3.10.1 — 2026-10-07`，并声明十五层、87 入口、34 来源在该补丁中不变。更早的 tag 从 `v2.1.0` 到 `v3.10.0` 都在本检出的 `refs/tags` 里；浅克隆不保证每个 tag 的完整树都可独立检出，版本身份以当前 `HEAD` 上的 `SKILL.md` 为准。

---

## 2. 覆盖面

### 2.1 仓库自述的层、入口、来源

`README.md` 与 `SKILL.md` 文首一致：**15 层、87 个能力入口（82 主入口 + 5 备胎）、34 个来源**。计数口径写在 `README.md`「87 个端点能力清单」：清单展示 88 行，按能力入口计 87。「东财行业研报」与「东财 reportapi」是同一端点（只是 `qType` 不同）；「同花顺北向（历史）」是本地自缓存，不单列；「东财日内异动池」一行含 `list` / `count` 两个端点。`to_joinquant()` 是辅助函数，不计入（`CHANGELOG.md` v3.9.0、`SKILL.md` 路由表「前置」行）。

15 层在 `README.md` 架构树与 `SKILL.md`「端点路由速查」（约第 231–318 行）对齐，当前 Layer 1 编号是 v3.10.0 重排后的：

| 层 | 路由表 § | 代表函数 | 主源（路由表「源」列） |
|---|---|---|---|
| 1 行情 | 1.1–1.7 | `tencent_quote`、`tencent_kline`、`tdx_daily_package`、`tencent_ticks`、`baidu_kline_with_ma`、`sina_adjust_factor`/`apply_adjust`、`tdx_client` | 腾讯、通达信官网、百度、新浪；mootdx 留档 |
| 2 研报 | 2.1–2.4 | `eastmoney_reports`、`eastmoney_industry_reports`、`ths_eps_forecast`、`iwencai_search`、`sina_research_reports` | 东财、同花顺、iwencai、新浪 |
| 3 信号 | 3.1–3.9 | 热点、北向、板块、资金流、龙虎榜、解禁、行业排名、板块资金流 | 同花顺、东财 |
| 4 资金面/筹码 | 4.1–4.7 | 两融、大宗、股东户数、`dividend_history`、120 日资金流、`chip_distribution`、`etf_shares` | 东财、本地计算、沪深交易所 |
| 5 新闻 | 5.1–5.5 | 个股新闻、财联社、全球资讯、华尔街见闻、新闻联播 | 东财、财联社、华尔街见闻、央视网 |
| 6 基础 | 6.1–6.8 | 季报、F10、东财个股信息、新浪三表、`baostock_valuation_history`、`baostock_stock_basic`、`sw_industry_history`、`st_stock_list` | mootdx、东财、新浪、baostock、申万 |
| 7 公告 | 7.1–7.2 | `cninfo_announcements`、F10「最新提示」 | 巨潮、通达信 |
| 8 打板 | 8.1–8.5 | 四池、同花顺涨停揭秘、监控池、异动 | 东财、同花顺 |
| 9 ETF 期权 | 9.1 | 新浪合约 / T 型 / 希腊字母 | 新浪 |
| 10 舆情 | 10.1–10.3 | 互动易、热榜、上证 e 互动 | 巨潮、同花顺、东财、上证 e 互动 |
| 11 宏观利率 | 11.1–11.6 | 社融、PMI、中债曲线、回购定盘、LPR、宏观日历 | 人民银行、统计局、中债、货币网、东财、华尔街见闻 |
| 12 指数日历 | 12.1–12.4 | 成分、权重、估值、`trading_calendar` | 中证、国证、深交所 |
| 13 期货大宗 | 13.1–13.7 | 五家交易所日行情与期权、四家持仓排名、新浪实时与日 K、A50、上金所 | 交易所官方 + 新浪 + 上金所 |
| 14 事件 | 14.1–14.6 | 预告、调研、增减持、回购、质押、IPO 日历 | 东财 datacenter |
| 15 可转债 | 15.1 | `convertible_bonds` | 东财 datacenter |

5 个备胎在路由表末段：`margin_trading_backup`、`bse_quote_backup`，以及备用源速查一行里的 `dragon_tiger_backup` / `fund_flow_backup` / `announcements_backup`。`README.md` 另写「另有 5 个备胎」，与 82+5 一致。

优先级写在 `SKILL.md`「数据源优先级」（约第 320–331 行）：腾讯第一（K 线单入口约 600 次后限流，三入口轮换），交易所/官方机构第二，新浪/巨潮/同花顺/华尔街见闻第三，mootdx 第四且行情命令自 2026-09 起返回空（#52），东财第五且只用于别处拿不到的数据。大商所官网日行情未接入（`docs/source-integration-v3.9.0.md`「未接入」：纯 HTTP 返回 412）；大商所品种走 `futures_realtime` 与 `futures_kline`。

来源数的加法在 CHANGELOG 里可顺着读：v3.8.0 写 19→22（新增中证、国证、北交所）；v3.9.0 写 22→34，新增 12 个来源（通达信官网盘后包、华尔街见闻、央视网、上证 e 互动、中债、中国货币网、上期所、上期能源、郑商所、中金所、广期所、上金所）；v3.10.0 写来源数不变，新增 2 个入口（`tencent_ticks`、`futures_kline`），腾讯与新浪已在 34 之内。本报告没有把「34」重新拆成一份独立清单去和第三方网站对账。

### 2.2 README、SKILL、Release 是否滞后

**版本号与 15/87/34 没有滞后。** 当前 `README.md`、`README_en.md`、`SKILL.md` frontmatter、`CHANGELOG.md` 首节、tag `v3.10.1` 说的是同一版。`tests/test_v310_sources.py` 的 `LAYER1` 字典把 §1.1–§1.7 钉在重排后的函数名上（`tencent_quote` … `tdx_client`），并检查路由表行与章节一致。

**章节号在历史文档里滞后，而且是仓库自己声明保留的。** `CHANGELOG.md` v3.10.0 Breaking Changes：Layer 1 重新编号，旧 1.2 腾讯财经 → 1.1，旧 1.5 腾讯 K 线 → 1.2，旧 1.6 盘后包 → 1.3，新增逐笔 → 1.4，旧 1.3 百度 → 1.5，旧 1.4 新浪因子 → 1.6，旧 1.1 mootdx → 1.7。函数名与签名不变。同一节写明：更早的 CHANGELOG 条目和 `SKILL.md` 开头的历史版本说明仍用旧编号。因此：

- `docs/source-integration-v3.9.0.md` 仍写「K 线改走 §1.5 腾讯、§1.6 通达信官网盘后包」。按 **当前** `SKILL.md`，这两处是 §1.2 与 §1.3。
- `SKILL.md` 文首 V3.7 / V3.9 历史块里的「§1.4 复权因子」「§1.5 / §1.6」是重排前的编号。当前路由表第 244 行才是 §1.6 `sina_adjust_factor`。

读旧笔记时要按函数名，不要按当时的 § 号。

**联网验收日期没有覆盖全部入口。** `CHANGELOG.md` v3.9.0 测试节写：2026-09-20 对 25 个新入口做了真实接口验证（数据日 2026-09-18）；「旧版 60 个入口没有全部重新联网验证」。v3.10.1 写全量 177 条（173 离线 + 4 联网，联网默认跳过），作者环境为 Python 3.9.6 与 3.12.13。本机是 Python 3.13.5，且 `import pandas` 失败，**未复跑**这 177 条。

`stockstats` 出现在 `SKILL.md` 第 425 行与第 7567 行的 `pip install` 清单，以及依赖表「技术指标计算」。全文检索没有 `import stockstats`。它是声明依赖，不是当前嵌入代码的调用点。

---

## 3. 可靠性与陷阱

下列每条都能在当前 `SKILL.md` / `CHANGELOG.md` / `docs/` 里指到位置。数字是作者记录，不是本报告新测。

### 3.1 mootdx / 通达信 TCP（#52）

`SKILL.md` FAQ（约第 7482–7493 行）与 `docs/source-integration-v3.9.0.md` 第 10 行：2026-09-20 对内置 10 台服务器逐台查看，TCP 可达，财务与除权除息正常，F10 只剩「最新提示」，K 线、五档、逐笔返回 0 行。换 mootdx 版本解决不了。`tdx_client(check='finance')` 用于 §6.1 / §6.2 / §7.2；行情模式失败时错误信息指向腾讯 K 线与盘后包。

同文件「mootdx 客户端」节（约第 454–458 行）：mootdx 0.11.x 在 `~/.mootdx/config.json` 的 `BESTIP.HQ` 为空字符串时，`Quotes.factory(market='std')` 会 `ValueError: not enough values to unpack`。作者明确写不要靠锁 `mootdx==0.10.12`：干净 Python 3.9 上该锁会因 numpy/pandas 二进制不兼容在 `import mootdx` 时崩溃。规定走 `tdx_client()`，显式传 server。`_probe` 只做 TCP 握手；`_validate` 才真实取数，避免握手成功但 2 字节空 body 变成空表（历史 #43，文首 V3.4.1）。

行情替代：沪深 K 线用 §1.2 `tencent_kline`；某日全市场含北交所用 §1.3 `tdx_daily_package`；当日分笔用 §1.4 `tencent_ticks`。mootdx `bars` / `quotes` / `transaction` 留在 §1.7。

### 3.2 复权因子：两套算法，都不能当成 QMT 前复权

`SKILL.md` §1.2（约第 1197–1199 行）写明腾讯前复权是**等差口径**（逐次减去每股分红）。作者记录：茅台 2020-01-02 原始价 1130.00、腾讯 qfq 870.741；高分红老股早年会被减成负数（茅台 2015 年约 -117.6）。函数遇到价格 ≤0 直接抛错。同段要求长区间回测改取 `adjust=''`，再用 §1.6 比例因子。分钟线只有不复权，`adjust` 非空会 `ValueError`（`tencent_kline` 函数体，约第 1273–1276 行）。

§1.6 `apply_adjust`（约第 1758–1761、1838–1855 行）：`qfq` 是除数（不复权价 ÷ factor），`hfq` 是乘数。传反方向不报错，只会把历史价放大或缩小。因子表为空时抛 `ValueError`，避免把不复权价当成复权价。早于最早因子日的 K 线抛 `RuntimeError`。作者用 baostock `adjustflag` 对照：2015-01-05 茅台不复权 202.52，baostock 前复权 143.46，`raw ÷ qfq` 对齐，`raw × qfq` 得到 285.90。后复权与 baostock 差一个作者记录的恒定倍数 1.1582，收益率形态可保留，数值不能和别的后复权源直接比。

北交所：同节写 `bj920982` 的新浪 qfq/hfq 文件返回 404，函数抛 `HTTPError`。

已退市标的：§6.6 后的警告（约第 4011–4013 行）写通达信 `xdxr()`、东财历史快照、baostock 三者对已退市（尤其北交所）的除权除息都缺，复权对不上是源侧保留策略。

### 3.3 代码映射与静默错票

这些是已经写进当前代码的修复，残留边界也写在同一段里。

- **后缀写法。** 文首 V3.7.1（约第 56 行）：`get_prefix()` 曾经只认 `sh000016`，不认 `000016.SH`。`em_secid("000016.SH")` 会拼成 `0.000016`（深康佳 A）而不是 `1.000016`（上证 50）。现已在 `get_prefix()` 开头认 `.sh/.sz/.bj`。同一段的残留：走「前缀 + 原串拼接」的端点（点名 `tencent_quote()`、新浪财报）仍只认纯 6 位或前缀式；后缀式会把 `.SH` 拼进请求串。使用顺序是先 `norm_ticker()`。
- **5 开头 ETF 与沪市指数。** 文首 V3.4.1：`510300`、`000016` 曾落入默认深市。`000016` 曾被当成 `sz000016`。`get_prefix()` 现含 `5x→sh`、沪市指数白名单、显式前缀透传，用来拆开 `000001`（上证指数 vs 平安银行）。
- **前后缀矛盾。** `norm_ticker()`（约第 648–704 行）解析失败抛 `ValueError`，不返回空串。示例包括 `SH000001.SZ`、`SZ600519`、`600519.XSHE`。`stock_only=True` 时拒绝指数。
- **聚宽后缀。** `to_joinquant()`（路由表与 FAQ #55）：北交所公开文档没有后缀，函数抛 `ValueError`，不做猜测。`_JQ_SUFFIX` 只有 `xshg`/`xshe`（约第 637 行）。
- **国证港股五位码。** `CHANGELOG.md` v3.8.0：直接拒绝，避免 `00700` 补零成 `000700/SZ`。
- **显式沪市指数。** v3.9.0：事件驱动与上证 e 互动收到 `sh000001` / `000001.XSHG` 时直接报错，不再查到同号深市个股。

### 3.4 北交所

- `tencent_kline` 遇 `get_prefix(code)=="bj"` 抛 `ValueError`，指向 §1.3（函数体约第 1269–1271 行）。原因写在 §1.2 开头：腾讯对北交所只返回最新 1 根日线，区间和分钟线为空（作者 2026-09-20 记录代码 920021 / 920982 / 920185）。
- `tdx_daily_package`：2022-05-06 之前的包没有北交所文件，只返回沪深；之后缺北交所文件报错，不用沪深冒充全市场（函数文档字符串，约第 1483–1484 行；`docs/source-integration-v3.9.0.md` 同述）。
- 老号段 43/83/87。文首 V3.6.0 与「市场前缀规则」警告（约第 586–600 行）：作者 2026-07-31 记录东财北交所在市 342 只里 336 只已是 `920xxx`，老码在腾讯上仍 HTTP 200，但是定格价、成交量 0。`tencent_quote()` 置 `is_stale` / `stale_reason`。`eastmoney_reports()` 遇老码抛 `ValueError`，不返回 0 篇。判定启发式：成交量 == 0 且最新价 == 昨收。真停牌也满足该式，两者都不该用于估值。
- V3.7.2（#51）：`_natural_market()`、`_anomaly_market()` 与 `get_prefix()` 统一为 `startswith(("4","8","92"))`。作者写当时在市只有 `43x/83x/87x/920x`，`921` 尚未启用，该改动不改变当时标的的判定，只对齐规则。
- `equity_pledge()` 不含北交所，传北交所代码报错，不返回空表（v3.9.0 修复条）。
- `baostock_valuation_history` 不支持北交所，登录前抛 `ValueError`（文首 V3.7.0；服务端码 `10004011` 是作者记录）。
- `bse_quote_backup`：当前快照，核对交易日，路由表与 README 都写不提供历史回填。
- `st_stock_list`：东财路径含京市；东财不可达时退 baostock，作者写兜底只有沪深、无价格（`README.md` 基础数据表、`docs/source-integration-v3.9.0.md`）。

### 3.5 东财限流，以及空结果 vs 接口坏

`em_get()`（约第 752–783 行）串行，`EM_MIN_INTERVAL=1.0` 秒加随机抖动，复用 `EM_SESSION`。FAQ 与「防封铁律」禁止对东财开多线程。作者记录的封禁案例（约第 352–362 行，issue #36，2026-06-30）：10 线程、不走 `em_get`、1 小时 45000+ 请求后，`push2` / `push2his` 整段 `RemoteDisconnected`，IP 级封禁 20+ 小时；`datacenter-web.eastmoney.com` 当时不受影响。腾讯 `web.ifzq.gtimg.cn` 连续 5000+ 次返回空，作者把它写成限流而不是封 IP。社区阈值表（每秒 >5、并发 ≥10、5 分钟 ≥300）与这条案例并列，案例比阈值表更严。

**两套东财查询语义不同，这是接入时最容易混用的边界。**

- 旧 `eastmoney_datacenter()`（约第 785–799 行）只取第 1 页。`result` 或 `data` 缺失时 **`return []`**。龙虎榜、解禁、两融、大宗、股东户数、`dividend_history` 走这条。空列表同时表示「没有行」和「响应形状不对」。V3.6.1 修的是 `dragon_tiger_board()` 在空窗口抛 `UnboundLocalError`；修完后空窗口返回空结构。那次修复没有把旧 helper 改成「错误码必抛」。
- V3.9 的 `_em_datacenter_strict()`（约第 966 行起的说明，第 802–807 行总述）：翻页；「返回数据为空」只在第 1 页当空表；其他错误码、翻页中途失败、条数与总数不符抛 `RuntimeError`。事件驱动、可转债等新入口走这条。`ValueError` 表示参数错或确实没有数据，`RuntimeError` 表示源坏了或格式变了。

因此：Layer 14 的空表可以按作者契约理解；§4.4 `dividend_history` 的空表不能。

`dividend_history`（约第 3113–3133 行）默认 `page_size=20`，经旧 helper 只拿一页，字段来自东财 `RPT_SHAREBONUS_DET`：`EX_DIVIDEND_DATE`、`PRETAX_BONUS_RMB`、`TRANSFER_RATIO`、`BONUS_RATIO`、`ASSIGN_PROGRESS`。代码注释把转增/送股写成「每 10 股」。本报告没有用样本核对这个单位。

### 3.6 成交量单位

§1.2 表（约第 1195 行）与 v3.10.1 CHANGELOG：`tencent_kline` 的 `volume`，**科创板 688/689 是股，其余是手**。日周月、分钟、复权与否同一规则。科创板 ETF `588`、LOF、REITs、可转债、指数按「其余」：1 手 = 100 股/份，可转债 1 手 = 10 张。v3.10.1 之前文档把全部写成手；按旧文档把科创板量乘 100 会放大 100 倍。返回值故意不改，只改文档。

同节对账口径（作者 2026-10-05，对照盘后包与 Baostock）：

- 非科创板日线是整手。2020-03-11 起作者记录为四舍五入（差 −52～+50 股），更早是舍去零头（差 −99～0 股）。日线不回填。
- 非科创板分钟线在最近一个交易日也是整手，下一个交易日才回填成精确股数。回填时点作者写「没测出来」。
- 1 分钟线每天 241 根：09:30 只有集合竞价；13:01 的开盘价是上午收盘价。
- 深市整分时刻的成交，腾讯算进下一根（11:30:00 留在 11:30），Baostock 算进上一根。全天合计一致，逐根不一致。
- 第一笔成交前没有行；之后无成交分钟，沪市补 0 量，深市可能整根缺失。

§1.3 `tdx_daily_package` 文档字符串（约第 1481 行）：个股 `volume` 是股，`amount` 是元；指数等特殊代码的 volume 为通达信原值。

§1.4 `tencent_ticks`（约第 1517 行）：量是手，**含科创板**。与 §1.2 的科创板「股」不同。分笔约 3 秒一笔，不是 Level-2。`frame.attrs["complete"]` 在 15:31 以后用快照盘后成交额核对；低价 ETF 一两手的缺笔仍可能被容差盖住（CHANGELOG v3.10.1）。

备用源表里「新浪的量是股」是 v3.10.1 补上的作者记录（09-30，5 只与盘后包逐股相等）。成交额不能用「量(手) × 100 × 均价」套到科创板和可转债上。

分钟 K 线数组第 8 个字段（下标 7）是换手率基点，除以 100 才是百分数，不是成交额（§1.2 代码注释，约第 1295–1297 行；v3.10.1 更正了「第 7 个字段」的笔误）。

### 3.7 其他会静默出错的点

- **筹码。** §4.6（约第 3202–3209 行）：东财 `cyq/get` 作者记录为 404。`chip_distribution` 用 OHLC + 换手率本地推演。初始筹码播种为首日全部流通盘，窗口前的存量持仓被当成已经换手掉。输入依赖 §6.5 baostock，因此北交所走不进这条链。
- **申万。** §6.7：`https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls`，只有代码，没有中文名。`sw_industry_as_of` 取不晚于 `as_of` 的最后一次调整。东财/通达信行业名与申万代码不是同一套，不能直接 join。
- **指数成分。** §12 与 README：中证/国证给的是最近公布的成分和权重，保留源侧日期，不回填历史时点。权重单位是百分数，不假定与成分同一天。`index_valuation` 不含 PB，不承诺全历史。
- **交易日历。** `trading_calendar(year, month)` 只收深交所整月标志，缺日或未知标志抛错，不自行猜节假日（v3.8.0 CHANGELOG）。
- **F10。** 2026-09 起类别只剩「最新提示」。请求不存在的类别时 mootdx 返回 dict，对 dict 切片会 `TypeError`；当前写法先 `F10C` 列类别。
- **北向历史。** FAQ：本地自缓存；作者写 eastmoney 北向净买额自 2024-08 起为 NaN/0。深股通分钟序列在披露收紧后不可靠，权威日统计指向 HKEX 备胎（文首 V3.4.0）。
- **腾讯字段号。** FAQ：字段 43 是振幅不是 PB，46 才是 PB。总市值与流通市值下标与东财 push2 的方向相反（§1.1 附近，约第 1179–1182 行，中船特气例子）。
- **百度。** `baidu_kline_with_ma` 使用裸 `requests.get`（约第 1692 行），不走 `em_get`。FAQ：`ResultCode` 有时是 int 有时是字符串 `"0"`。
- **已死名单。** `SKILL.md` 约第 7401 行：网易 126、和讯、凤凰行情、腾讯资金流 `ff_`、雪球免登录深度数据。mootdx 库最后提交作者写为 2024-07。

---

## 4. 许可证与依赖

`LICENSE` 是 Apache License 2.0 全文，附录版权行是 `Copyright 2026 Simon Lin`。该许可证覆盖本仓库作品（Skill 文本与测试）。它不把腾讯、东财、交易所、baostock、申万等上游数据的使用条款一并授予。iwencai 需要单独申请的 key（`SKILL.md`「iwencai API Key」节，环境变量 `IWENCAI_API_KEY`）。

声明的运行时（`SKILL.md`「Prerequisites」，约第 422–437 行）：

| 包 | 仓库写的版本 | 用途 |
|---|---|---|
| Python | 3.9+（徽章与多处「保留 Python 3.9」；代码禁止 `dict \| None`，用 `Optional`） | 语法下限 |
| mootdx | `>=0.10` | 财务快照与 F10；0.11.x 必须走 `tdx_client()` |
| requests | any | HTTP |
| pandas | any | 表 |
| numpy | any | §4.6 网格 |
| stockstats | any | 声明用于 RSI/MACD/BOLL；当前 `SKILL.md` 无 import |
| baostock | `>=0.8` | §6.5、§6.6、§6.8 兜底 |
| xlrd | `>=2.0` | 申万 `.xls`、中证 |
| openpyxl | any | 社融 `.xlsx`、国证、深交所两融 |

V3.0 起移除 akshare。FAQ 把理由写成 akshare 在 pandas 3.0 上的 `ArrowInvalid` 等中间层故障。V3.7 起 baostock 是额外 TCP 客户端，作者注明「零第三方封装」只适用于其余端点。

与本机两个对照仓的环境是分开钉死的，**不要把上述 `pip install` 打进它们的解释器**：

- MyQuant-backtrader：`pyproject.toml` `requires-python = ">=3.12"`；`requirements.txt` 注释写 `D:\anaconda3\envs\vanna312\python.exe`，`pandas==3.0.6`，`numpy>=1.24`。文件中没有 mootdx、baostock、stockstats、xlrd。
- OSkhQuant1.3：`pyproject.toml` `requires-python = ">=3.11"`，`license = { text = "Proprietary" }`，`dependencies = []`。运行锁在 `deploy/requirements-runtime.txt`：对齐 vanna311、Python 3.11，`pandas==2.3.3`，`numpy==2.3.5`（2026-08-09 lock）。该文件同样没有 mootdx / baostock。

冲突点是具体的：同一台机器上 vanna312 已是 pandas 3.0.6，而 a-stock-data 的 FAQ 把 pandas 3.0 当成离开 akshare 的原因；mootdx 0.10.12 在作者记录里会和某些 numpy/pandas 二进制轮子互斥。baostock、xlrd 都不在两仓锁文件里，装进共享 env 会变成未锁定的额外包。Skill 代码用 `exec` 运行，不需要 `import a_stock_data`，因此正确隔离方式是单独的 venv，而不是 `PYTHONPATH` 指向 1.3 或 BT。

本机研究环境是 Python 3.13.5，没有 pandas。与仓库声明的 3.9 / 作者复测的 3.12.13 都不是同一解释器。3.13 上这套依赖能否导入，**未核实**。

---

## 5. 对 MyQuant-backtrader 的适配

BT 的行情合同在本仓是只读湖，生产在 1.3。`README.md` 第 75 行：Bars、复权、流通股本由原仓生产，本仓用 `oskh_data.StockDataReader` 读，无 QMT 下载。`AGENTS.md`：parquet 为 hive 三树 `stock|index|etf`，复权类型分分区。成交核 `docs/backtest/engine-ashare-correctness.md`：

- E-R5：csv 日线/分钟链的成交与估值全程 `dividend_type=none`。
- E-R6：除权日只缩放**已持有的参考价**（cost/peak、涨跌停用的昨收映射）。事件来自 `ex_date_index` 主路径，因子跳变兜底；`k` 是因子行比。成交价、净值估值、股数、佣金、T+1、现金红利入账都不改。
- `oskh_data/__init__.py`（1.3，BT 侧消费同一语义）：交易侧默认 `none`，因为 T-1 不可变，涨停检查和收盘价查询用它；回测侧 `front` 用于连续价格指标，并且要盘后重建。
- `AGENTS.md` 策略 12：分钟湖/成交域默认 raw `--dividend-type none`；日线信号域固定 `front`；禁止 front 日线加 none 分钟的静默双重调整。

1.3 日线复权 SSOT（`docs/backtest/data/daily-adjusted-update-ssot.md`）把 QMT `dividend_type='front'` 定为 ground truth，禁止用 back/none 本地推导 front。`cumulative_adj_factor = close_front / close_none`，由 `oskh_data/adj_factor.py` 从已落盘价格计算。QMT `get_divid_factors` 只允许发现除权日；`dr` 不得用于推导价格或因子数值。`scripts/data/detect_ex_date_changes.py` 的 `EX_DATE_INDEX_SCHEMA_COLUMNS` 是 `stock_code, ex_date, dr, fetched_at`。

### 5.1 可以当作可选的离线研究表或事件旁证

这些输出不进入 `load_minute_ohlc` / 日线 none 帧，也不写入 `adj_factor.parquet`。落盘前要自己加 `source` / `fetched_at`，并接受东财限流与旧 helper 的空表语义。

| 用途 | 函数 | 边界 |
|---|---|---|
| 事件旁证：预告、调研、增减持、回购、质押、打新日历 | §14 六个函数 | 走 strict datacenter。质押不含北交所。是东财字段，不是 `ex_date_index` |
| 分红送转**线索** | `dividend_history` | 旧 helper、默认 20 行、空表含糊。只能提示「去对 `ex_date_index`」，不能生成 `dr` 或 `k` |
| 当日 ST 名单交叉 | `st_stock_list` | 当日快照。baostock 兜底丢京市和价格。不是 1.3 的 `st_intervals` / `st_daily`，也不是交易闸 `daily_st_set` |
| 行业 as-of 代码 | `sw_industry_history` / `sw_industry_as_of` | 申万 2021 分类 xls，无中文名。可做研究特征。不能替换 `vendor_wind_sw_l1` 的 Wind 名 |
| 上市/退市日 | `baostock_stock_basic` | 作者写这是零鉴权退市日来源之一。已退市标的的除权链仍然缺 |
| 估值、停牌、历史 ST 标记 | `baostock_valuation_history` | 日频研究。不支持北交所。不是成交价 |
| 公告、新闻、研报、互动、打板、监控池 | §2、§5、§7、§8、§10 | 文本与名单。巨潮在 1.3 另有 WAF 与公告库，见第 6 节 |
| 指数**当前**成分/权重/PE、深交所月历 | §12 | 不做历史成分回填。月历可与 BT 已有交易日历对一天，不能替换湖 |
| 单日不复权核对 | `tdx_daily_package(某日)` 对一只代码 | 个股量是股、额是元，适合抽查湖 `none` 的 close/volume/amount。不是历史库，2021-01-04 作者记录已 404，未逐日验证 |
| 可转债条款、期货日行情 | §15、§13 | BT 成交核是 A 股股票/ETF 研究路径。这些表留在各自研究里 |

### 5.2 绝不可进入下单决策价

下单决策价在本仓指：撮合用的 bar 价（E-R5 的 none/raw）、涨跌停与昨收、以及 E-R6 用来缩放参考价的 `k`。下列任何一项进入这些字段，都会改写成交或闸门。

1. `tencent_kline` 的 `qfq`/`hfq`，以及默认日线（默认就是 qfq）。等差复权，早年可为负，与 `close_front/close_none` 不是同一个数。
2. `apply_adjust` / `sina_adjust_factor` 乘除出来的价格，以及拿新浪 factor 去填 `cumulative_adj_factor` 或 E-R6 的 `k`。新浪 qfq 是除数阶梯；1.3 的因子是 QMT front÷none。hfq 与 baostock 还有作者记录的常数倍差。
3. `tencent_quote`、百度 K 线、北交所 `bse_quote_backup`、新浪实时期货、A50。它们是当下或单日快照，北交所老码还会带 `is_stale` 定格价。
4. mootdx `bars()` / `quotes()` / `transaction()`。2026-09 起行情命令返回空；空表若被当成「无成交」会改写当日 bar。
5. `tencent_ticks` 的价格与量。约 3 秒分笔，科创板量仍是手，盘中不保证完整。不能当成分钟 bar，更不能当成 Level-2。
6. `chip_distribution` 的平均成本、获利比例。本地三角分布，窗口起点播种失真。
7. 腾讯 K 线的 `volume` 不经单位换算就写入湖的股数成交量，或拿去算容量上限。688/689 是股，其余是手；可转债 1 手 = 10 张。盘后包才是股。
8. 用 `dividend_history` 的派息/送转去改 E-R6、去增股、去把红利记入现金。BT 的 E-R6 明确不动股数和现金；1.3 禁止用 `dr` 推价格。东财这一页也不是 `ex_date_index` 的 schema。

信号域如果要用前复权，合同已经指定湖里的 QMT `dividend_type=front`。腾讯 qfq 不能并行再调一次，否则与 none 分钟成交形成第三套价格。

---

## 6. 与 OSkhQuant1.3 的数据层对照

1.3 的存储一页纸是 `docs/operations/data-three-stores-ssot.md`（`docs/SSOT.md` 第 195 行指向它）：

- **Parquet 湖**：`OSKH_SOURCE_PARQUET_ROOT`。A 股日线/分钟在 `{container}/stock/period=*`，指数与 ETF 分根，散装文件经 `resolve_source_parquet`。未设 SOURCE 则报错，禁止猜盘符。细粒度 `OSKH_PERIOD_*` 会盖过一键（lesson 58）。
- **DuckDB**：`resolve_e_stock_data_container()`，派生库 `stock_data_front.duckdb` / `none` / `back`，与湖不同目录。
- **SQLite**：订单、持仓、资金、审计，加巨潮 `disclosure.db` / `alert_monitor.db`。与行情根无关。

日更节奏在 `docs/backtest/data/daily-adjusted-update-ssot.md`：全市场 QMT 板块 `沪深京A股`（文档写约 5548 只）。日常唯一流水线是 `detect_ex_date_changes.py` → `update_adjusted_daily.py`（只下载）→ `finish_adj_factor_duckdb.py`（只算因子）→ rebuild。推荐入口 `scripts/data/run_daily_adjusted_fast.py`。日常下 `none`；除权股 delete 后全历史重下 QMT front；非除权股路径 B 用当日 none 填当日 front。`back` 默认不下。指数/ETF 是副轨，`scripts/data/update_etf_index_daily.py`，禁止塞进 A 股主宇宙。

`oskh_data/` 是本地历史行情基础设施，不是 HTTP skill。包说明见 `oskh_data/__init__.py`。与本对照直接相关的模块：

| 路径 | 作用 |
|---|---|
| `oskh_data/reader.py` | `StockDataReader`，parquet / duckdb |
| `oskh_data/downloader.py`、`download_ops.py`、`qmt_xtdata.py`、`minute_backfill.py`、`backfill.py` | QMT 下载与回填 |
| `oskh_data/daily_parquet_write.py`、`repair_daily_parquet_schema.py` | 1d 落盘 |
| `oskh_data/adj_factor.py`、`adj_factor_meta.py` | 从已落盘 front/none 算因子 |
| `oskh_data/etf_backfill.py`、`etf_local_bars.py`、`index_minute.py` | ETF / 指数副轨 |
| `oskh_data/float_shares.py`、`float_shares_history.py`、`free_float_shares.py` | 股本 |
| `oskh_data/vendor_wind_st.py`、`vendor_szse_st.py`、`vendor_qmt_st_snapshot.py` | ST 事件与 QMT 名称快照 |
| `oskh_data/vendor_wind_sw_l1.py` | Wind 申万一级，批次 100，写 `{SOURCE}/vendor_wind_sw_l1/` |
| `oskh_data/symbol_format.py` | 规范代码 `^\d{6}\.(SH\|SZ\|BJ)$` |
| `oskh_data/freshness.py`、`integrity.py`、`audit.py` | 新鲜度与审计 |

公司行为在 1.3 侧的落地是 `ex_date_index.parquet`（`resolve_source_parquet`）加 `adj_factor.parquet`，检测脚本是 `scripts/data/detect_ex_date_changes.py`。行业是 Wind 申万一级湖，提示词 `docs/prompts/prompt-kimi-datasource-industry-harvest.md`，总述 `docs/engineering/vendor-kimi-wind-harvest-2026-09-14.md`。指数价格在 `index/period=1d`（副轨，none-only 的大盘基准，见日更 SSOT §2.1），不是成分历史。

ST 五渠道在 `docs/operations/st-data-channels-ssot.md`：深交所简称变更（深市事件 SSOT）、巨潮公告（补沪/京，公告日≠生效日，WAF 403 按 IP）、Wind 经 Kimi（沪/京历史批，每批 100）、QMT 两产物禁止互顶（交易闸 `daily_st_set` vs 回测湖 `vendor_qmt_st_names`，`day=` 不是历史 as-of）、东财风险警示板作备胎。2026-09-14 人裁：1.3 下载写湖，MyQuant 与 BT 只消费。

### 重复与补缺

**重复、且不应另起一条生产链的：**

- 日线/分钟 OHLC、前复权、复权因子、除权检测。1.3 已有 QMT 湖、路径 B、`adj_factor`、`ex_date_index`。a-stock-data 的腾讯 K 线、新浪因子、东财分红页是另一套定义。
- 当日 ST 是否戴帽。1.3 已有交易闸和 15:30 后的全市场名称湖。`st_stock_list` 只是东财/baostock 当日名单。
- 巨潮公告。1.3 已有 `oskh_disclosure`、`disclosure.db`、PDF 根，以及 ST 专用 `vendor_cninfo_st_status`。a-stock-data 的 `cninfo_announcements` 是对话里临时检索。
- 申万**当前**一级名称。1.3 的权威是 Wind 写湖 `vendor_wind_sw_l1`（代码规范为 `000001.SH` 这种形式，见 `normalize_wind_code`）。

**1.3 湖里没有、a-stock-data 能补的研究材料：**

- 申万**变迁史**（多次调整、as-of 代码，无中文名）。Wind 模块文档写的是申万一级采集与 merge，不是这条 xls 变迁表。
- 事件表：业绩预告、机构调研、增减持、回购、质押、IPO 日历、可转债条款。1.3 SSOT 索引没有对应的生产湖。
- 研报、一致预期、新闻、互动易、涨停池、龙虎榜席位、北向分钟、宏观利率曲线。这些不在三类存储的行情合同里。
- 深交所官方月历、中证/国证**当前**成分与权重文件。1.3 指数树是价格，不是成分快照。
- 通达信官网单日盘后包，可做某一天 none 日线的外部抽查（量是股）。它不是 1990 年起的 hive，也没有分钟。
- QMT 停机时的**只读抽查**：一只票、一天、不复权。不能把抽查结果写回 `period=1d`。写湖仍归 1.3（ST 文档的人裁同样适用于行情：BT 不拉数）。

---

## 7. 与 Kimi / Wind 对照

指针文件是 `MyQuant-backtrader/docs/operations/kimi-financial-data-fill-pointer.md`（14 行）。它规定：A 股数据缺失时，不找本地 Wind、iFinD 或同花顺桌面端，也不因 QMT 停机停止补缺。ST 采集以 1.3 的 `docs/operations/st-data-channels-ssot.md` 和 `docs/prompts/prompt-kimi-datasource-st-harvest.md` 为准（指针写 commit `b1863731178e`，lesson 61）。口径是 `data_source_name=wind`、`api_name=wind_get_financial_data`，不要调用 `get_data_source_desc`，每批 100。Wind 返回无数据时写仅表头的空 CSV，不重试空批次 `0027/0028`。1.3 下载写湖，BT 只消费。

同一指针还记录了与 ST 不同的另几次用法，不能并成一种接口：

- 2026-10-01 instruments 佐证包在 BT `docs/backtest/b-l2-01-evidence-2026-09-30/kimi_instruments_fill_20261001/`（指针写 commit `38374f0f`，PR #287）。THS `stock_finance_data.get_price` 取 `reference_price`，Wind 取涨跌停价，并且**这次要求**调用 `get_data_source_desc`。指针写明不要把该包当成写湖授权。ST 采集仍不调用 `get_data_source_desc`。
- Wind 分钟：`api_name=wind_get_stock_quote`，不是 `wind_get_minute_data`，也不是 `wind_get_price`。指针写 2026-10-01 补过 002231.SZ、300379.SZ、600200.SH，报告在 `D:\exports\topk_s1_cap_cli_host_20261001\vendor_fill\FILL_REPORT.md`。时钟：QMT 湖目标是 END，Wind 常见 START，禁止整表加一分钟，缺根不补零。对齐文档 `docs/backtest/ssot/vendor-bar-alignment-ssot.md`。
- 2026-10-04：同花顺 `get_price` 的 interval 只有 D/W/M/Q/Y；`get_stock_realtime_price` 对若干分钟点返回 `EMPTY_DATA`。iFinD 不在 kimi-datasource 枚举里。

1.3 侧写湖入口：`docs/engineering/vendor-kimi-wind-harvest-2026-09-14.md`。ST 模块 `python -m oskh_data.vendor_wind_st`，申万一级 `python -m oskh_data.vendor_wind_sw_l1`。日常深市走 `pull-szse-namechange` + `merge`，不耗 Kimi。`st-data-channels-ssot.md` §2.3：额度间歇耗尽时 `QUOTA` 不等于任务失败；「没找到数据」写空 CSV。

**额度。** 「周额度 / 5h」在 BT `docs/operations/grok-bot-raci-workflow-ssot.md` §3.1（该节标题写已核验 2026-10-06）：Kimi Code 的查询是 `GET {base_url}/usages`，主字段 `usages.limit_7d.used_ratio` 与 `usages.limit_5h.used_ratio`，各自有 `reset_time`。这是 **kimi-code 账号窗口**，不是 Wind 终端自己的合同配额。文档要求报告 used_ratio 和窗口，不要把某次探测的瞬时数字写死。本报告没有调用该接口，当前 used_ratio **未核实**。`docs/engineering/multi-ai-review-workflow.md` 第 15 行另写：独立 kimi-code 周额度用尽时，评审席位默认改走 Cursor 上的 Kimi。

**成本与可靠性。** a-stock-data 的公开 HTTP 不需要 Wind 账号，也不扣 `limit_7d` / `limit_5h`。代价是东财 IP 封禁、腾讯按入口限流、来源随时改 JSON、以及第 3 节的单位和复权差。Kimi/Wind 的代价是账号窗口、每批 100、空批不能重试，以及分钟时钟是 START 而湖是 END。Wind 经 Kimi 的字段有插件 schema；a-stock-data 的字段是网页接口，两边没有一份对照过的列映射。可靠性上，1.3 已经把「空结果」和「额度耗尽」分成两种处置；a-stock-data 只在 V3.9 strict 入口上做了同样的区分，旧 datacenter 入口仍把异常收成 `[]`。

**公司行为目录。** 任务说明里的 4090 路径 `D:\exports\bt_corp_actions_20261006` 在两个对照仓的已检索 Markdown 和本机 a-stock-data 中都没有出现。本机不是 4090，没有列出该目录。文件是否存在、schema、是否已入湖，**未核实**。不能把任务说明里的路径写成「已验收的 Wind 公司行为库」。1.3 本地已有的除权产物是 `ex_date_index.parquet`（列 `stock_code, ex_date, dr, fetched_at`）和由 QMT front/none 算出的 `adj_factor.parquet`。

**留在 Wind/Kimi 的：**

- 沪/京 ST 历史批次（深市日常用深交所简称变更，不耗 Kimi）。`st_stock_list` 补不了区间和摘帽日。
- 申万一级**名称**湖 `vendor_wind_sw_l1`，BT 与 1.3 已按此消费。
- QMT 停机时的分钟补缺：`wind_get_stock_quote`，并按指针做 START→END，缺根不补零。腾讯分钟线只有最近 ≤320 根、无北交所、深市桶边界与 Baostock 不一致，不能代替这条补缺。
- instruments 包里的涨跌停价与 `reference_price`。那是一次佐证，不是写湖授权；更不能改用腾讯实时价顶上。
- 任何已经入湖、并被 E-R6 / 交易闸读取的表。

**可以改用 a-stock-data、且不替代上述湖的：**

- 当日 ST 名单抽查、申万变迁代码（无中文名）、东财事件六表、当前指数成分文件、单日盘后包对一只股票的 none 抽查、宏观利率和新闻研报。
- 分红页只作「是否要去打开 `ex_date_index`」的提示。公司行为的价格与 `dr` 仍以 QMT `get_divid_factors` 和 front/none 为准。在 `bt_corp_actions_20261006` 未核实之前，不用 a-stock-data 的分红页去填那份导出。

---

## 8. 下一步实验

三个探针都小，都不扫全市场，都不下载 4090 上的公司行为包，也都不把结果写进 1.3 的湖或 BT 的成交帧。

**探针 1 — 离线执行契约，隔离 venv。**  
在临时目录建 venv，只安装 `SKILL.md` Prerequisites 那一行，解释器不要用 vanna311 / vanna312。然后：

```bash
python -m unittest discover -s /workspace/a-stock-data/tests -v
```

不要设置 `ASTOCK_LIVE_V39` 或 `ASTOCK_LIVE_V310`。作者记录是 173 条离线通过、联网默认跳过。本机 3.13 无 pandas，这一步尚未跑。通过只说明标记块能被 `exec`、单测断言成立；不说明上游网站今天仍返回同样的行。

**探针 2 — 一只股票、一个交易日、不复权价对湖。**  
选湖里已经有 `dividend_type=none` 的一天和一只非科创板、一只 688。各调用一次 `tdx_daily_package(date)`，只打印这两行的 `close/volume/amount`，与 hive `data.parquet` 的同日 close、volume、amount 并列。volume 预期：盘后包是股；若再调用 `tencent_kline(..., adjust='')`，非科创板要先明确「手 × 100」再比，688 按股比。调用间隔服从腾讯三入口冷却，不对东财发请求。本 Linux 工作区没有挂载 `OSKH_SOURCE_PARQUET_ROOT`，这一步要在有湖的宿主上做。本报告没有做。

**探针 3 — 分红页与 `ex_date_index` 的列对照，最多一只票。**  
先离线：把 `dividend_history` 返回字典的键（`date, bonus_rmb, transfer_ratio, bonus_ratio, plan`）与 `EX_DATE_INDEX_SCHEMA_COLUMNS`（`stock_code, ex_date, dr, fetched_at`）写成两列表，确认没有同名列、没有 `dr`。若要看空表语义，只对 `600519` 调用一次 `dividend_history`，记录是抛异常还是 `[]` 还是最多 20 行。不要翻页扫全市场，不要用返回的派息去除权价。与 `ex_date_index.parquet` 的比较只读已有 parquet 里该代码的 `ex_date`，看东财这 20 行是否覆盖得上，覆盖不上就停，不补数。

---

## 附：本报告没有做的事

- 没有 `git push`，没有改 `OSkhQuant1.3` 与 `MyQuant-backtrader`，没有改 `a-stock-data` 的跟踪文件。
- 没有联网请求东财、腾讯、交易所或 Kimi `/usages`。
- 没有打开 `D:\exports\bt_corp_actions_20261006`。
- 没有把 CHANGELOG 里的行数、封禁小时数、茅台价差复测一遍。那些句子的证据等级是「仓库文本如此写」，引用路径见上文各节。
