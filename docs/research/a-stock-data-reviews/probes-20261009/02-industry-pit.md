# 02 申万行业 PIT HTTP 落地及一级行业对照

申万原始 XLS 成功落地一次 HTTP 200：`raw/sw-http-01.bin`（1,166,336 字节，SHA256 见 `sw-http-manifest.json`）。来源 [申万官方变迁表](https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls)。返回 Last-Modified 为 2026-10-08 07:55:22 GMT，抓取时间 2026-10-09 07:57:21 UTC。

TLS：默认 certifi、系统 CA 两次均报缺发行者证书。另一次重试仍未补入证书而失败；最终从 [DigiCert 证书仓](https://cacerts.digicert.com/GeoTrustG2TLSCNRSA4096SHA2562022CA1.crt) 取到中间证书，openssl verify 使用系统根证书验证成功（`02-chain-verify.log`）。仅给此探针设置 REQUESTS_CA_BUNDLE；没有 verify=False，没有修改系统信任库。失败日志及握手链保留。本任务的一次 HTTP 落地指一次成功 XLS 下载，不隐藏前置 TLS 失败尝试。

- 历史记录 12,925 行、5,930 个代码、38 个历史一级行业码；无空 start_date、无重复 (code,start_date)。
- 以 2026-10-09 为 as_of、每代码取最后一条有效记录，得到 5,930 行；最新 start_date 是 2026-09-24 10:53:00。
- 平安银行：2013 年为 440101，2016 年为 480101，今日为 480301；行业变迁查询生效。
- `02-sw-history.csv` 为原函数解析结果，`02-sw-asof-20261009.csv` 为今日截面。

## 权威今日对照的边界

**1.3 今日 vendor_wind_sw_l1 实表核验仍受阻，不能宣称今日权威表通过。** 本机未设 OSKH_SOURCE_PARQUET_ROOT / OSKH_AUTHORITY_HINT_ROOT；OSKH_DATA_ROOT=/workspace/OSkhQuant1.3 只是工作区，不能当行情湖。指定 1.3 checkout 内（含忽略文件）未找到 sw_l1_map.csv / wind_l1_map.csv；未远连取湖、未访问 4090、未补采 Wind/Kimi。

为使探针有可审阅结果，按 1.3 `docs/engineering/vendor-kimi-wind-harvest-2026-09-14.md` 的历史参考表说明，使用本机已有 MyQuant worktree 导出副本：

`/workspace/wt-myquant-next-knife-after-ami1/exports/m3d_industry`

该副本的 wind_crosscheck.json 标注生成时间 **2026-09-13T07:32:35Z**，Wind 表 5240 行。复制的两张表及交叉检查 JSON 在 `raw/historical-*`，哈希和来源见 `02-comparison-results.json`。这是 9 月 13 日历史快照，不是今日新采；测试 fixture 一律未作为来源。

申万代码表不带名称；独立名称映射取[东财掘金提供的申万 2021 分类表](https://emt.18.cn/api/quant-help/data/stock.html)，从 HTML 六列行业表自动抽取 31 个一级码到 `02-codebook.csv`，原网页在 `raw/sw-codebook-provider.html`。未用 Wind 众数反推名称，避免循环论证；该映射不是东财自有板块分类。

| 对照项 | 数量 |
| --- | ---: |
| 两边共同代码 | 5240 |
| 一级名一致 | 5238 |
| 一级名不一致 | 2 |
| 仅申万历史表中有 | 690 |
| 仅 Wind 快照中有 | 0 |

共同代码一致率 99.9618%。完整逐股对照 `02-industry-comparison.csv`；差异及覆盖外代码 `02-industry-differences.csv`。

| 代码 | Wind 9 月 13 日快照 | 申万今日截面 | 申万计入时间 |
| --- | --- | --- | --- |
| 603336 | 农林牧渔 | 医药生物 | 2026-09-24 10:53:00 |
| 688328 | 机械设备 | 电子 | 2026-09-24 10:53:00 |

同日控制：将申万 as_of 退回 2026-09-13，5,240/5,240 只一级名全部一致；两只差异票的旧记录见 `02-historical-control.csv`。这支持日期差异解释，但仍不能代替今日实表。

两处变化时间晚于 Wind 快照生成日，**与快照时差相符**；未进一步取得公告核实，不能判 Wind 今日数据错误。仅申万侧 690 个代码属于覆盖差，不能算分类冲突，也不能默认全部仍上市。今日截面仍有 38 种一级码，其中 25 个代码保留 7 类旧一级码（不在 SW2021 的 31 类码表内）；这 25 个均在 Wind 对照范围外，不强行映射旧分类。

## PIT 使用限制

此表足以演示按“计入日期”取历史归属，但不能单凭一次最新 XLS 证明严格的“当时已知”PIT：12,652 行 update_date 晚于 start_date，表内可能包含事后修订。应区分 effective_at 与 available_at，保留获取版本/时间。也没有退市退出日期过滤；“今日截面”在这里严格指 as_of 算法结果，不等于今日在市股票清单。

复跑 HTTP：设置 REQUESTS_CA_BUNDLE 为本目录 raw/sw-ca-bundle.pem 后运行 `.venv/bin/python sw_retry.py`；离线重新比对运行 `.venv/bin/python compare_industry.py`。今日权威表补齐后应另做一次同日期核验，不要覆盖历史副本结果。
