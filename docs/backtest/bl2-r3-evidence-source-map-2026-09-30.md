# B-L2-01 R3 证据源地图：量单位 / 涨跌停与 lot / 停牌与缺失（2026-09-30）

> 性质：研究笔记 + 原件登记，**不是** [#270](https://github.com/baiyibing/MyQuant-backtrader/issues/270) `bl2_proof_v1` 的已填证明。
> 采集范围：本仓 + `OSkhQuant1.3` + `MyQuant` 三仓、本机 QMT 安装目录（`D:\国金证券QMT交易端`）、F 盘券商随机手册（`F:\gjzqqmt\QMT操作说明文档`）、公开互联网。全部采集时间 2026-09-30。
> 六份空模板已在远端 master（a268e11）入库：`tests/fixtures/minute_orders_source_attestation/`；ingress §9 见 `docs/backtest/note-l2-lake-source-ingress-b-l2-01-2026-09-29.md`（本文所述登记/绑定规则均以该 §8.2–§9.5 为准）。本机工作副本 master 落后（f8b2b52），本文档以远端 master 为基提交。box 侧落点 `D:\exports\b_l2_01_4090_r3_20260930\evidence\`（本机无此路径）。
> 探针窗口：603196.SH · 20251023–20251104（R3 未冻结）。

2026-09-30 后续人裁已接受此窗口 `basis=cross_source_ratio`；#1111 `ec19fd6`
提供 daqmt/THS 对账、Wind 逐日 limits 与 suspendFlag 原材料。
见 [Human GO 与 remapped drafts](b-l2-01-evidence-2026-09-30/attestation_packages/README.md)
及 ingress §10 的窄例外。下文保留采集时记录；vendor 单位声明仍不存在，
不得把本次人裁写成 `source_declaration`。R3 不变、R4 未授权、production_C=frozen。

## 0. TL;DR

1. **湖的分钟 bar 供应商 = 国金 QMT（xtquant / daqmt 垫片）**，volume 全链路零换算直写 parquet → 湖的单位就是 QMT K 线的原生单位。
2. **① 量单位：四类官方载体（券商 API 手册 PDF、随厂 xtdata.pdf、官网文档、PyPI wheel 内 xtdata.md）对 K 线 `volume` 均无单位声明** → 现成 source_declaration 不存在；只能向迅投要书面确认，或人裁改 basis，否则 ① 保持 BLOCKED。
3. **② 涨跌停/tick/lot：vendor 字段级声明齐**（`get_instrument_detail` 的 `PriceTick/UpStopPrice/DownStopPrice/PreClose/InstrumentStatus`；K 线逐 bar `preClose`）；历史窗口走 derived 路线（钉死 inputs + 交易所规则版本 + 双 issuer），第二 issuer 用 tushare `stk_limit`。
4. **③ 停牌/缺失：K 线字段 `suspendFlag` 是 vendor 逐 bar 停牌声明**（湖当时未采，重拉窗口即可得）+ `get_trade_times` 交易时段声明 + tushare `suspend_d`（含日内停牌时段 `suspend_timing`）；双 false 格子三源共证。

## 1. 湖分钟 bar 供应商链路（vendor = QMT）

`OSkhQuant1.3` 写湖链路（行号为 2026-09-30 工作树）：

- 入口壳 `oskh_data/minute_backfill.py:17` → `oskh_data/backfill.py --period 1m`（盘中禁跑门禁 :382；完成后 `_verify_minute_bar_integrity` :779）
- 下载 `oskh_data/downloader.py::DataDownloader.download_data` → `oskh_data/download_transport.py`：后端旋钮 `OSKH_DAILY_DOWNLOAD_BACKEND`（:87-90，repo 默认 `daqmt`；mini 机须显式 `xtdata`）
  - xtdata 后端：`xtdata.download_history_data2(...)`（:346）→ `xtdata.get_market_data_ex(field_list=["time","open","high","low","close","volume","amount"], ..., fill_data=True)`（:469-487）
  - daqmt 后端：`oskh_core/daqmt_download_transport.py:192/:290`（大 QMT 垫片，逐只 `download_history_data`）
- 写盘 `_merge_write_one_minute`（`downloader.py:918-934`）→ `stock/period=1m/dividend_type=none/symbol=<key>/data.parquet`（`PeriodDataManager.get_file_path` :269-275）

**volume 零换算的证据**：写侧只做 `pd.to_numeric`（:797-799）与 dtype 钳制 `STANDARD_DTYPES volume:int64`（:151）；日线 `volume.round().astype("int64")`（`daily_parquet_write.py:138-140`）是取整不是单位换算；读侧 `oskh_data/reader.py:1027` 只锁 dtype。全链路无 ×100 / /100 / 手↔股。

`MyQuant` 仓是湖消费方（`my_scripts/build_winner_ratio.py`、`data_root.py` 等），对三样证据无独立供应商链路。

## 2. 原件登记表（路径 + bytes SHA-256）

| # | 原件 | 绝对路径 / 来源 | SHA-256 |
|---|------|----------------|---------|
| A1 | 国金 QMT Python API 手册（券商发行） | `F:\gjzqqmt\QMT操作说明文档\国金QMT极速策略交易系统_模型资料_Python_API_说明文档_Python3.pdf` | `ac1e256f80c5b00c6adf603604cce9e4e3168fad578e186f3e7ce65b96653183` |
| A2 | 国金 QMT 操作说明（券商发行） | `F:\gjzqqmt\QMT操作说明文档\国金QMT极速策略交易系统-操作说明.pdf` | `fe00ed1e608334e41848d67abfd215b849a0fe96e7aa237c3f4c44082e082848` |
| A3 | 随厂 xtdata 文档（2023-08-01） | `D:\国金证券QMT交易端\bin.x64\Lib\site-packages\xtquant\doc\xtdata.pdf` | `3288c96996c105db0165ec1c759ae47c1160be0f3f3c4c4071b3af77a694c2b0` |
| A4 | 随厂 xttrader 文档 | `D:\国金证券QMT交易端\bin.x64\Lib\site-packages\xtquant\doc\xttrader.pdf` | `f3912e1caa5bfec0b6f68390d644574cc728f76b719ef8788dbbf2f7ae3af640` |
| A5 | PyPI wheel（内含 `xtquant/doc/xtdata.md`） | <https://files.pythonhosted.org/packages/b4/bb/a5fa80e4cf880d320e6abc75bb061075824bc3c0a7f55446f90f79013159/xtquant-250807.1.2-py3-none-any.whl> | `91f19ff9a92971c5abe64fbd077e5212e0418f0820aa3427aef3444230f72921` |
| A6 | 1.3 缓存 vendor 文档（XtData 行情模块全抄本） | `E:\PycharmProjects\OSkhQuant1.3\docs\knowledge\vendor\xtquant\国金证券XtQuant.XtData行情模块.md` | `f9f5149d2d0a07c295b556f5f2011b0c43be02a159589b870f3637612e86af20` |
| A7 | 1.3 mock-qmt 设计文档（tick 单位项目内声明） | `E:\PycharmProjects\OSkhQuant1.3\docs\engineering\mock-qmt\mock-qmt-design.md` | `49b2722f9bbc9c242e160504f54898eebe5035860968b53393c1f903c141e4c3` |
| A8 | 迅投官方在线文档（dict.traderquant.com 新地址） | <https://dict.thinktrader.net/nativeApi/xtdata.html> | 2026-09-30 抓取核验，网页未存档 |

注意事项：

- A5 版本 `250807.1.2` 在 PyPI 标记 **yanked**；作为文本载体引用时注明版本号与下载日。
- PDF 文本用 pdfplumber（vanna312 环境）抽取，抽取物在本机临时目录，**不入库**。
- **vendor 原件不复制进本仓**（scope：外部下载与 vendor 归 1.3 / 机器路径；本仓只登记路径 + 哈希 + 引文）。4090 侧填包时原件以本表路径搬运或重新采集后按同规则登记。

## 3. ① 量单位：官方载体全部无声明

### 3.1 K 线 volume 原文对照（四类载体一致）

| 载体 | K 线（1m/5m/1d）字段表原文 |
|------|---------------------------|
| A1 券商 API 手册 | `volume - int 成交量`（无单位） |
| A3 随厂 xtdata.pdf | `'volume' #成交量`（无单位） |
| A5 PyPI xtdata.md | `'volume' #成交量`（无单位） |
| A8 官网文档 | `'volume' #成交量`（无单位） |

K 线字段表全文（A5，A3/A6/A8 同）：

```text
'time' #时间戳  'open' #开盘价  'high' #最高价  'low' #最低价  'close' #收盘价
'volume' #成交量  'amount' #成交额  'settelementPrice' #今结算  'openInterest' #持仓量
'preClose' #前收价
'suspendFlag' #停牌标记 0 - 正常 1 - 停牌 -1 - 当日起复牌
```

### 3.2 相邻声明（记录在案，但都不能当 K 线 volume 的 basis）

- L2 千档盘口：`'bidVolume' #多档委买量(向量)，单位是手`、`'offVolume' #多档委卖量(向量)，单位是手`（A5 `xtdata.md` l2thousand 节）——是 QMT 行情侧唯一明写「手」的声明，但对象是委托量不是 K 线成交量。
- IPO 数量：`actIssueQty - int 发行总量，单位：股` 等（A5）。
- 交易侧：`order_volume - int 委托数量，股票以'股'为单位，债券以'张'为单位`（A4 xttrader.pdf；A6 :1873 同）——交易所申报口径，非行情 K 线。
- lot（手数定义）：A2 操作说明「股票的最小交易单位为100」「在内地市场，一手默认为 100 股」。
- tick 快照：A7 `mock-qmt-design.md:414`「QMT `get_full_tick` 返回的成交量单位为股，非手」（:418 并警告 A 股各源单位不一）——**对象是 tick 快照，不是 K 线**，1.3 项目内声明。

### 3.3 结论与可行路径

- 1.3 全链路零换算（§1）⇒ 湖内分钟 volume = QMT K 线原生值；`amount/(close×volume)≈100` 指向「手」，但属 #270 明令禁止的启发式。
- **现成 source_declaration 不存在**。可行路径（按优先级）：
  1. 迅投官方书面确认（QMT 技术支持工单 / 官方群答复），问法须同时覆盖单位与增量口径：「xtdata `get_market_data_ex` 股票 1m/1d K 线 `volume` 字段单位是手还是股？每根 K 线的 volume 是该分钟增量还是累计量？」（ingress §9.2 要求声明明确增量而非累计）；答复原文 + 渠道 + 时间戳存档后登记为原件；
  2. 要不到 → 人裁是否改 basis（Human 决定，不默认）；
  3. 都不行 → ① 保持 BLOCKED（不得填「通常值」）。

## 4. ② 涨跌停 / tick / lot

### 4.1 vendor 字段级声明

`get_instrument_detail`（A6 instrument detail 节；A3/A5 同）：

```text
- `PreClose` - float 前收盘价格
- `UpStopPrice` - float 当日涨停价
- `DownStopPrice` - float 当日跌停价
- `PriceTick` - float 最小价格变动单位
- `VolumeMultiple` - int 合约乘数（对期货以外的品种，默认是1）
- `InstrumentStatus` - int 合约停牌状态
- `IsTrading` - bool 合约是否可交易
```

K 线逐 bar `preClose`（§3.1 字段表）＝按日 vendor 事实参考价（含除权日交易所口径），可避开「拿湖内昨收冒充 reference」的禁令。注意 `UpStopPrice/DownStopPrice` 是**当日**值 → 历史窗口（20251023–20251104）无法回溯拉取，走 derived 路线。

### 4.2 交易所规则与第二 issuer

- 规则源：《上海证券交易所交易规则（2023 年修订）》——主板 ±10%，`涨跌幅限制价格 = 前收盘价 ×（1 ± 涨跌幅限制比例）`，四舍五入至最小价格变动单位 0.01 元。原文在 sse.com.cn「法律规则 → 业务规则」栏目，**R4 采集时下载官方 PDF 并按 §2 规则登记**（本机未存档）。版本注意：2026 年有修订动态（风险警示股 5%→10%），按窗口日期适用当时有效版本；603196.SH 为主板非 ST → ±10%。
- 第二 issuer：tushare [`stk_limit` 每日涨跌停价格](https://tushare.pro/document/2?doc_id=183)（输出 `trade_date/ts_code/pre_close/up_limit/down_limit`；2000 积分；交易日 9 点左右更新）。

### 4.3 derived 路线（填 `instruments.derived.template.json`）

- 钉死 inputs（ingress §9.3：inputs 指向已 pin 原始材料，规则材料本身也要登记）：QMT 1d K 线 `preClose`（窗口每日 + 前一交易日，`dividend_type='none'` 原始口径，dump 成文件）＋ `get_instrument_detail` 导出 `PriceTick` ＋ SSE 交易规则版本化 PDF（规则内容、批准材料、舍入方式一并作 input）。
- 规则：`limit_up/down = round(preClose × (1 ± 0.10), 2)`（`approved_rule_version` 钉版本；loader 不执行公式，只消费已供给值）。
- 双 issuer：primary proof 与 `independent_verification` 须不同 proof ID、不同 issuer（QMT dump 一方、tushare `stk_limit` 一方），两组都引用全部 inputs、保存相同输出 binding；两者 `pre_close` 对不上 ⇒ 除权/参考价口径问题的信号，正好兜住除权日。
- lot/tick 事实：`get_instrument_detail` dump（PriceTick）＋ A2 操作说明（lot 100 股/手）＋ 1.3 lot SSOT `oskh_core/a_share_buy_lot_contract.py:34-58`（主板 100、科创板 200、北交所特例；步进主板 100 / 688·BJ 1）。

### 4.4 1.3 现成调用点（不用新写）

- `oskh_core/daqmt_broker_adapter.py:1400` `get_instrument_detail`（daqmt 垫片 `query_instrument_detail`）；消费与 fail-closed 在 `hkcodex_miniqmt.py:2383-2389` / `:2449`，fallback `:2673-2690`。
- 探针：`scripts/probes/probe_guojin_limit_price_sources.py`、`scripts/diagnostics/_probe_premarket_instrument_detail.py`。
- 预热缓存只进 Redis L1（`oskh_core/limit_info_preheat.py`），湖侧无 per-symbol 涨跌停导出；湖 sidecar `float_shares.parquet` 只含 `FloatVolume/TotalVolume/name`（`oskh_data/float_shares.py:142-149`）。
- 已知分歧备忘：`oskh_core/board_limit.py:18` 静态幅度表 vs 研究侧口径的 BL-001 仍 OPEN（1.3 `docs/architecture/f-lake-cross-repo-contract.md` §5）。

## 5. ③ 停牌 / 缺失分钟

### 5.1 vendor 声明

- **K 线 `suspendFlag`**（§3.1 字段表）：`0 - 正常 1 - 停牌 -1 - 当日起复牌`，1m K 线同带——湖当时未采此字段，对窗口重拉即可得 vendor 级逐分钟状态。
- **交易时段**（A5 `get_trade_times`）：

  > `list，返回交易时段列表，第一位是开始时间，第二位结束时间，第三位交易类型（2 - 开盘竞价， 3 - 连续交易， 8 - 收盘竞价， 9 - 盘后定价）。时间单位为"秒"`

- **停牌填充语义**（A1 券商 API 手册，`ContextInfo.get_market_data` 策略层；xtdata 层仅 `fill_data - bool 是否向后填充空缺数据`，见 A8）：

  > `skip_paused`…「true：如果是停牌股，会自动填充未停牌前的价格作为停牌日的价格；False：停牌数据为nan」
  > `fill_data：停牌填充方式，默认为True（暂不可用）`
  > `ContextInfo.is_suspended_stock()`：True：停牌；False：未停牌

  归属注意：以上三条是大 QMT 策略层（ContextInfo）声明；1.3 的 xtdata 读回用 `fill_data=True`（`download_transport.py:486`）。

### 5.2 1.3 侧对应实现与观察

- 写侧时段 mask：`downloader.py:305-310`（09:30–11:30 / 13:00–15:00）＋ SSE 日历过滤 `:289-303`；核对网格 `integrity.py:116-140`（expected_times）。
- 占位 bar 语义：`downloader.py:53-89` `_is_latest_bar_placeholder`（QMT 对停牌/未 finalize 返回 OHLC=前收、volume=0；:79 实证 002677.SZ）——与 5.1 vendor 声明互为印证；分钟侧**不**丢全零占位行（`:816-835` 仅对 1d+front 生效）。
- 日历 SSOT：`common/infra/trading_calendar_pmc.py`（SSE/XSHG，pandas_market_calendars）。

### 5.3 第二 issuer 与网格构造

- tushare [`suspend_d` 每日停复牌](https://tushare.pro/document/2?doc_id=214)：输出含 `suspend_timing`（日内停牌时间段，仅日内停牌有值）——对分钟网格直接有用。
- 网格构造规则（ingress §9.4）：预期分钟集 = 冻结 `symbols × intervals` 展开的每个 session 分钟桶（`get_trade_times` 连续交易段）；每格显式填 `missing/halted/reason/issuer/proofs`。`halted` = `suspendFlag==1` 或 `suspend_d/suspend_timing` 命中；**无源行不得自动设 missing、更不得据此设 halted（no halt-from-silence）**；零量源行仍是「存在的记录」（对应 §5.2 占位 bar 语义）；**双 false 格子**由「bar 存在 ＋ `suspendFlag==0` ＋ `suspend_d` 无记录」三源共同支撑（`basis=explicit_status`）。

## 6. R4 采集步骤（照做清单）

前置：QMT 终端在线（本机 `D:\国金证券QMT交易端`，走 1.3 网关 / daqmt 垫片或 QMT 自带 python）；tushare token ≥2000 积分。

```python
# QMT 侧（示例；字段以本地网关接口为准；dump 保存原始返回 + SHA-256）
from xtquant import xtdata
xtdata.download_history_data2(["603196.SH"], period="1m", start_time="20251020",
                               end_time="20251104", dividend_type="none")
m1 = xtdata.get_market_data_ex(
    field_list=["time","open","high","low","close","volume","amount","preClose","suspendFlag"],
    stock_list=["603196.SH"], period="1m", start_time="20251023", end_time="20251104",
    dividend_type="none", fill_data=False)          # fill_data=False：避免前向填充污染状态网格
d1 = xtdata.get_market_data_ex(field_list=["time","close","preClose","suspendFlag"],
    stock_list=["603196.SH"], period="1d", start_time="20251022", end_time="20251104",
    dividend_type="none", fill_data=False)
detail = xtdata.get_instrument_detail("603196.SH")   # PriceTick / UpStopPrice / DownStopPrice / PreClose / InstrumentStatus
times  = xtdata.get_trade_times("SH")                # 交易时段声明
dates  = xtdata.get_trading_dates("SH", start_time="20251020", end_time="20251104")
```

```python
# tushare 侧（第二 issuer）
pro.stk_limit(ts_code="603196.SH", start_date="20251023", end_date="20251104",
              fields="trade_date,ts_code,pre_close,up_limit,down_limit")
pro.suspend_d(ts_code="603196.SH", start_date="20251023", end_date="20251104")
```

- 每个 dump 单独登记：绝对路径 + schema + bytes SHA-256；proof 的 `source_refs` 只指原件、不得自证。原材料须落成可 pin 的行式载体（Parquet 行或 JSON `data.rows` 摘录，ingress §9.1）；六份模板见 `tests/fixtures/minute_orders_source_attestation/`（master @ a268e11）。
- 交易所规则 PDF（sse.com.cn 当时有效版本）同规则登记。
- ① 的前置（迅投书面确认）未拿到前，units 模板不填——宁可继续 BLOCKED。
- 原件齐后丢进 box 的 `D:\exports\b_l2_01_4090_r3_20260930\evidence\`，点名「开 4090 B-L2 R4」。

## 7. 非主张与边界

- 本文档是证据源地图与引文登记，不构成 #270 六模板的已填证明，不改变 R3 BLOCKED 状态。
- 未做湖写、未派 4090、未改 SSOT / δ5 / JR G；未提供或认证任何市场事实。
- vendor 原件不复制进本仓（scope：vendor 归 1.3 与机器路径）；PDF 抽取物与 wheel 解包物留本机临时目录。
- ① 的结论是「负结果」：四类官方载体均无 K 线 volume 单位声明。任何把启发式或相邻字段声明升格为 basis 的做法都需要 Human 明确批准。
