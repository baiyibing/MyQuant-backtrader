# SSOT：A 股 ST 状态

- 日期：2026-10-09
- 状态：standing
- 依据：当日对湖容器的只读核查，以及「三份材料不合成一张日表」的分工。
- 本仓只消费。采集、补洞、写湖在 OSkhQuant1.3。本文件不授权在本仓 merge vendor 或再做一份 ST 采集。见 [plan-ashare-engine-refactor-2026-09-18.md](../plan-ashare-engine-refactor-2026-09-18.md) §0.2。

路径都相对 `resolve_parquet_container()`。不写死盘符。文件不存在就失败，不把缺文件当成「没有 ST」。

---

## 1. 三份材料各管一件事

| 材料 | 湖路径 | 它回答的问题 | 它不回答的问题 |
|---|---|---|---|
| Wind 日表 | `vendor_wind_st_status/st_daily.parquet` | 某个交易日这只股票是不是 ST | 全市场名册是否采全；今天的简称快照 |
| QMT 名称快照 | `vendor_qmt_st_names/date=YYYYMMDD/names.parquet` | 该快照日全市场简称里谁标着 ST | 快照日之前某一天是不是 ST |
| 巨潮公告 | `vendor_cninfo_st_status/` | 尚无可用表 | 任何 ST 判断 |

`st_daily` 合同只读 Wind 日表。不把 QMT 快照或巨潮并进这张表，也不用快照回填历史日期。

同目录里的 Wind 辅助文件不进消费合同：

| 文件 | 用途 |
|---|---|
| `st_intervals.parquet` | 实施日到撤销日的区间，用来生成日表 |
| `st_implement.parquet` / `st_revoke.parquet` | 实施、撤销事件 |
| `st_coverage.json` / `harvest_status.json` | 采集覆盖与是否半成品。读日表的代码不读这两份来判定某只某日是不是 ST |

读日表的合同与 topk 的 `--st-daily-file` 相同：只认列 `code`、`trade_date`、`is_st`，并且 `is_st` 为真才算当日 ST。实现见 `backtest/research/topk_dropout_eligibility.py` 的 `load_st_daily_by_day`。该函数写明不读 `st_coverage.json`。

---

## 2. 缺行怎么读

Wind 日表现状只存放 `is_st=True` 的行。消费以这张表现有的行为准。

- 当天有 `is_st=True`：这只股票在这一天是 ST，发信号和买入都排除。
- 当天没有这只代码的行，或整张表不存在：免责放行。不把缺行失败成整次回测停摆，也不把缺行写成「已证明不是 ST」。
- 回测日晚于日表最后一天：这一天没有数据，同样免责放行。

QMT 快照仍只用来事后核对采集缺了谁。不把快照日的 ST 名单写回更早的交易日。巨潮目录在出现可消费的表之前，不参与判断。

策略 9 原书已经接上这道闸：`scripts/data/export_strategy9_pool.py` 在写名单前丢掉当日 ST；日线和分钟买入经 `st_on` 再查一次。实现是 `backtest/research/st_status.py`。

---

## 3. 和涨跌停名称档是两件事

| 用途 | 输入 | 现状 |
|---|---|---|
| 某日是否因 ST 不得进新仓 | Wind `st_daily` 的当日 `is_st` | topk 可选 `--st-daily-file`，缺文件失败。策略 9 导出和买入走 `st_status.is_st_on` |
| 涨跌停幅度里的 ST 档 | 名单 CSV 第二列简称，`is_st_name` 认 `ST` / `*ST` | 书引擎按名单日期 as-of。空简称不当成 ST。见 [plan-industry-align-p3-d3-st-pit-2026-09-19.md](../plan-industry-align-p3-d3-st-pit-2026-09-19.md) |

策略 9 的名单文件只有六位代码，简称过滤仍然为空。ST 排除走 §2 的 Wind 日表，不走简称。

---

## 4. 2026-10-09 湖上快照

容器当日解析为 `F:\stock_data`。数字会随 1.3 补采变化；补采后以新文件为准，本表不自动更新。

| 材料 | 当日事实 |
|---|---|
| 巨潮 | `harvest_status_cninfo.json`：`banned=true`，HTTP 403。无 parquet |
| QMT | 仅 `date=20260915` 与 `date=20260918`。9 月 18 日 5592 只有简称，其中 `is_st_risk` 204 只。600180.SH 当日名称为 `*ST瑞茂`，`st_kind=star_st` |
| Wind 日表 | 2020-01-02 至 2026-09-15，1626 个交易日，521 只曾出现，261155 行，全部 `is_st=True`。相对 600000.SH 的 2026-01-05 至 2026-09-18 交易日，缺 2026-09-16、09-17、09-18 |
| Wind 采集声明 | `partial=true`，`do_not_download=true`，`n_harvested_codes=4381`。9 月 18 日 QMT 的 204 只 ST 里有 29 只在日表全历史零行，含 600180.SH、600491.SH。600180 在 `st_intervals` / `st_implement` / `st_revoke` 里也是零行 |

因此这张日表还不是全市场每一天的完整 ST 名单。消费按 §2：有 `is_st` 行就排除，没有行就免责放行。
