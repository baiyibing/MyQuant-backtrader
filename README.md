# MyQuant-backtrader

研究脸：负责回测策略研究、实验输入组织，以及**向量化**成交模拟、费用、持仓和收益回测。既消费外部信号 / 日名单 CSV，也生成回测专用候选名单。因子研究、Qlib 训练/模型信号输出及当前已归并的筹码/TR 公共数值核见 [MyQuant](https://github.com/baiyibing/MyQuant)；同一口径公共计算只保留一份实现，BT 调用公共接口。行情只读 path-SSOT parquet；数据采集与湖加工在 [MyQuant-infra](https://github.com/baiyibing/MyQuant-infra)。成交验收（LEBS / MockQMT）在 [OSkhQuant1.3](https://github.com/baiyibing/OSkhQuant1.3)。

研究与验收引擎怎么分工：[`docs/backtest/engine-positioning-ssot.md`](docs/backtest/engine-positioning-ssot.md)。成交核（档位 / 全卖因跌停 / Decimal 涨跌停价 / E-R6 除权日参考价修正）：[`docs/backtest/engine-ashare-correctness.md`](docs/backtest/engine-ashare-correctness.md)。名单 CSV 契约：[`docs/backtest/pool-csv-contract.md`](docs/backtest/pool-csv-contract.md)。MyQuant 保留完整 Qlib 研究回测（2026-11-08 用户澄清）；Cerebro / Rolling 已退场（2026-09-16）。本仓没有 `backtest/lebs/`。

研究与执行分工：MyQuant 负责完整 Qlib 研究回测及信号导出，本仓负责自身向量化研究，1.3 负责执行验收；LEBS 只在 1.3，且 LEBS ≠ MockQMT 真栈。本仓无 `python -m backtest.lebs` 入口。研究问题地图（三份主名单 × 策略 1–12 / Mode A/B / TopK）：[`docs/backtest/research-backtest-entry.md`](docs/backtest/research-backtest-entry.md)。

Seeded from OSkhQuant slim snapshot at `5d41252`。S2（2026-09-09）之后本仓收研究面；交易栈只留 `oskh_factors` chip/bridge 微包。

## Layout

| Path | Role |
|------|------|
| `backtest/research/csv_daily_backtest.py` | 向量化日线（策略 1/2/3/4/5/6/8/9/10 策略书） |
| `backtest/research/csv_minute_backtest.py` | 向量化分钟（策略 1/2/3/4/5/6/8/9/10） |
| `backtest/research/csv_minute_backtest_v7.py` | 策略 7 金榕元仓位机（独立） |
| `backtest/research/csv_minute_backtest_topk_app_dropout.py` | 新策略 topk_app_dropout（不改策略 7） |
| `backtest/research/csv_ledger.py` | 6/8 共用账本（Position / 买卖 / 追买桶） |
| `backtest/research/market_layer.py` | 涨跌停档位与 Decimal 涨跌停价 |
| `backtest/research/csv_pool.py` | 名单 CSV：裸六位码 → canonical |
| `backtest/research/csv_strategy_books.py` | 1/2/3/4/5/6/8/9/10 策略书 |
| `backtest/research/chip/` | Chip 因子消费者 |
| Cerebro / Rolling 历史栈 | 已退场（2026-09-16）；chip / ma_chip 对照产物为静态档案，代码路径已删 |
| `backtest/legacy/` | 非 Cerebro 旧回放 |
| `oskh_data/` | infra 只读消费薄适配（三树 hive）；保留宿主配置与门禁 |
| L2 数据加工 / 查询 | 已迁至 MyQuant-infra；本仓不保留实现 |
| `qlib_cost/`、`oskh_factors/` | MyQuant 因子包的薄兼容转发，数值实现已迁出 |
| `turnover-resist/README.md` | MyQuant Rust 源码与构建指针，本仓无 crate |
| `oskh_factors/bridge/turnover_resist.py` | 转发 MyQuant 的 Rust Python 桥 |
| `strategies/tr_filter.py` | 换手阻力选股过滤 |
| `oskh_core/` | TR 再导出 + `a_share_symbol_normalize` |
| `trade_decision/presets.py` | 卖点 presets（研究副本，不改 1.3 交易核） |
| `common/infra/` | 宿主配置、时钟/路径政策与 infra import 转发 |
| `scripts/gates/` | 契约 / path-SSOT gates |
| `scripts/research/` `scripts/data/` `scripts/tr/` | chip / TR / 回测研究 CLI |
| `stock_pool/` | 6/8 **可变默认**日名单（非快照；不是海龟池）；实验/冻结见 `exports/` — [pool-csv-contract](docs/backtest/pool-csv-contract.md)#lifecycle-ssot-stock_pool-vs-exports |

## Infra consumer boundary

已迁入 MyQuant-infra 的代码从本仓删除，需要时调用 `myquant_infra`；本仓只保留必要的 import 转发、路径/配置、复权门禁、reader 生命周期与回测研究规则。缺依赖明确失败，不使用本地实现兜底。L2 加工、湖写入/维修、复权因子产制和数据回填审计入口均在 infra；不会因旧接口语义不同而在 BT 留第二套实现。2026-11-09 起，筹码/TR（含 Rust）、价格带、周线背离和通用研究工具先归 MyQuant，存储 IO 继续调用 infra。

共享实现由 `requirements-infra.txt` 固定版本，`requirements.txt` 会一并安装；开发机和 CI 都需要具备该依赖仓库的读取权限。边界检查可离线运行：`scripts/gates/verify_infra_consumer_boundary.py`。

2026-11-08 复核依据：[infra 四仓分界](https://github.com/baiyibing/MyQuant-infra/blob/1a497682258503bf748e1e873aea9be9a818e92e/docs/architecture/boundary.md)、[湖 SSOT §7](https://github.com/baiyibing/MyQuant-infra/blob/1a497682258503bf748e1e873aea9be9a818e92e/docs/architecture/data-lake-ssot.md)及 [ops 移交记录](https://github.com/baiyibing/grok-bot-ops/blob/master/docs/ops/HANDOFF_to_MyQuant-infra_20261104.md)。公司行为采集、Hithink 组装、历史对拍及 economics 处理入口沿用已合入的迁出删除裁定；运行时经济权益边界继续受 gate 约束。SSE 日期数据缓存/查询已调用 infra，BT 保留时钟、覆盖窗和进程失败策略。infra pin 更新到 `1a497682`，以覆盖本轮共享 helpers、日历及契约公共接口。

2026-11-09 OP04 收尾：巨潮经济日期 targets 导出与离线证据建议已有 infra 正式入口，本仓删除 `oskh_data/cninfo_economic_date_targets.py`、两个旧产制 CLI 及其产制单测。直接调用固定版本 infra，命令与迁移差异见 [消费指针](docs/operations/plan-cninfo-economic-date-evidence-2026-10-30.md)。该次 pin 为 `6bcf33f38ce88a92ddcdf0be4916cbb9cdd1def0`（已合入的 OP04 离线建议版本）；相对前 pin，湖/reader、参考数据、provenance、TR store、utils 和 CI 脚本均未变化。此变更不接入回测运行时、不转换旧证据包，也不授权采集、合湖或经济批准。

2026-11-09 vendor 收尾：当前 infra pin 为 `af27dd08c6b5e3653fa686c6f60e541afd1a4941`（已合入 #88）。新共享接口要求显式仓库、标的及保护根；BT 旧 CLI 保留兼容默认值和宿主配置，处理实现与产制测试迁入 infra。边界 gate 禁止在薄入口恢复本地转换、比较或文件 IO。原 START/END、股/手、边界排除、Sparse A、余数审计与 delta5/R4 验收锁不变；未执行真实数据加工。

本仓维护自身向量化策略研究，代码归属按用途判断，名单格式或“写 CSV”不构成迁出依据。2026-11-09 ops 通用运行时与已核对的 infra 重复产制入口已收口；Qlib 旧训练/handler、Notebook 与因子计算依赖迁入 MyQuant #139。Human 续裁定：以下回测专用名单生成属于 BT 的保留职责，不再作为必须迁出的剩余项。

| 当前代码 | 归属与后续处理 |
| --- | --- |
| `scripts/research/vendor_to_lake_adapter.py`、`vendor_bar_xcheck.py` | 已迁入 infra `adapters.vendor_bars`（#88）。BT 保留 CLI 薄入口、默认研究样本、显式仓库和配置湖根注入；解码、比较、转换、写盘与审计验证均调用 infra。staging 不获 apply 授权。 |
| 通用评审/发布工具 | 接收实现见 [ops #187](https://github.com/baiyibing/grok-bot-ops/pull/187)：本仓删除 `multi_ai_common.py` 与运行/发布实现，仅保留三个薄入口及领域 JSON 配置。显式 `MYQUANT_OPS_ROOT` / `--ops-root`，无本地兜底；见 [消费与剩余边界复核](docs/engineering/ops-runtime-consumer-20261109.md)。 |
| `qlib_cost/qlib_workflow.py`、`factor_expr.py` | 已迁入 MyQuant #139，Notebook 与全部计算依赖一并接收，BT 删除旧训练文件及 Notebook。MyQuant 不依赖 BT 源码。 |
| `scripts/data/export_strategy9_pool.py`、`export_ta_pool.py` / `export_strategy10_pool.py`、`export_strategy11_pool.py`、`export_beidou_pool.py`、`export_topk_app_dropout_pool.py` | Human 确认保留 BT：回测策略的筛选条件组合、参数、D→T 映射、实验名单与 CSV/manifest 导出。App ∩ Qlib 组合可由 BT 完成，原始 Qlib 预测仍由 MyQuant 提供；公共指标计算复用共享接口。不是迁出欠账。 |
| `qlib_cost/factor_analyze.py` | 已迁入 MyQuant `myquant_factors.factor_analyze`，旧路径只转发。`bigdata_ma_cross.py` 沿用 master 已删除状态。 |

上述清单按职责和实际读写入口核对，不是全仓逐行审计。原 D8=A 中通用因子数值核和通用研究入口的归属，已由 2026-11-09 迁出裁定替代；范围与薄适配见[接收记录](docs/engineering/factor-owner-migration-20261109.md)。回测专用名单生成、成交、费用、账本和经济权益门禁继续归 BT，无需追求“BT 只能消费外部名单”。同口径公共数值核只保留一份实现；当前调用 MyQuant 公共包，后续若归并到 infra 则整项迁移并删除旧实现。`data/`、`exports/` 与历史证据不作为源码迁移时的删除对象。

本轮已完成、未完成及原因，连同 PR 状态和验收范围，见 [四仓分界与 pandas 升级工作总结（2026-11-10）](docs/engineering/work-summary-quant-boundary-pandas306-20261110.md)。

## Environment

```text
D:\anaconda3\envs\vanna312\python.exe -m pip install -r requirements.txt
```

## Run research backtest

旧 CSV CLI 保留为真身（P5=A），HELP_LOCK 不变；本轮不新增薄包装。v7 / topk 的湖分钟行情共用 `ashare_bars` 书帧，qlib_1min 源仍保留。施工边界见 [撮合核收口 plan §0.3 / §5](docs/backtest/plan-ashare-engine-refactor-2026-09-18.md)。

必须 `--strategy version1|…|version6|version6_1|version8|version9|version10`。7 不在 choices，必须走独立入口并传 `--pool-dir`。9 / 10 在 choices 里，但也必须 `--pool-dir`（`export_strategy9_pool.py` / `export_ta_pool.py`），拒绝 `stock_pool/`。`stock_pool/` 是 6/8/6.1 可变默认，不是实验快照；可复现跑用 `exports/`（见 [pool-csv-contract](docs/backtest/pool-csv-contract.md)）。`version6_1` 对照见 [note-version6_1-sol-vs-version6-2026-10-02.md](docs/backtest/note-version6_1-sol-vs-version6-2026-10-02.md)。数据经 `oskh_data` / `resolve_period_root`（须设定 `OSKH_SOURCE_PARQUET_ROOT`；未设定或文件缺失即报错）。

```powershell
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py --strategy version6 --start 20251023 --end 20260909
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest.py --strategy version8 --start 20251023 --end 20260909
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest_v7.py --start 20260804 --end 20260909 --pool-dir E:\PycharmProjects\OSkhQuant1.3\stock_pool_turtle
```

R5（仅做 pred TopN 管道检查）：

```powershell
# MyQuant 仓导出（不要使用 holdings 口径的 exports/r0_*）
D:\anaconda3\envs\vanna312\python.exe my_scripts/export_daily_pool.py --pred my_scripts\预测结果.csv --topk 10 --asof pred_minus_one --out-dir exports/r2_pred_topn_20260302_20260323
# 本仓；<first>/<last> 是导出目录内首末 CSV 的文件名 stem
D:\anaconda3\envs\vanna312\python.exe -c "from pathlib import Path; from backtest.research.csv_pool import validate_pool_dir; err=validate_pool_dir(Path(r'<r2 out>')); assert err == [], err"
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py --strategy version6 --pool-dir <r2 out> --start <first> --end <last>
```

`--start/--end` 跟导出文件名走：H0 / `pred_minus_one` 常没有 `20260302.csv`，最后一个 pred 日也不写文件。无名称的 ST 按代码前缀使用 10% / 20% / 30% 档，不按 5%；本例只检查管道，不能把 NAV 或涨跌停桶当作模型结论。详见 [R2/R5 计划](docs/backtest/_archive/plans/plan-pool-pipeline-r2r5-2026-09-12.md)与[名单 CSV 契约](docs/backtest/pool-csv-contract.md)。

细则与 1.3 入口：[`docs/backtest/README.md`](docs/backtest/README.md)。

Cerebro / Rolling 已退场（2026-09-16）。chip / ma_chip 对照产物为静态档案，代码路径已删；纯筹码计算与 Rust TR 保留。version11（ma_chip）已注册为 `--strategy version11`，CSV 移植 A–C 已落地；成交时点与 volume=A 已人裁，D 静态档案对照仍待完成。

## Market data (read-only)

Bars、复权、流通股本由 MyQuant-infra 生产，这里经 `oskh_data.StockDataReader` 薄适配调用 infra 读侧。无 QMT / xtquant 下载。

Config: `config/reader.yaml`（默认 `mode: parquet`）。盘符分层见 `AGENTS.md`。

## Rust turnover-resist

数值实现和构建已迁至 [MyQuant `myquant_factors`](https://github.com/baiyibing/MyQuant/tree/master/myquant_factors)。BT 安装 `requirements-factors.txt` 固定的公共源码包，不安装 Qlib 训练工作流或 Notebook。Rust 产物通过显式 `TURNOVER_RESIST_EXE` 或已安装扩展提供；不再在 BT 构建本地 crate。

因子研究命令的旧路径只转发 MyQuant；宿主路径/reader/时钟/门禁由 `oskh_factors/_consumer.py` 注入。MyQuant 不反向 import BT。详细清单与验证见[迁移记录](docs/engineering/factor-owner-migration-20261109.md)。

## Tests

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q
```

共享环境版本不符时使用独立验证环境，不修改 pandas `3.0.6` 版本钉或重录 golden：

```powershell
D:\anaconda3\envs\vanna312\python.exe -m venv --system-site-packages backtest_output/.venv-regression
$env:OSKH_MERGE_PYTHON = (Resolve-Path backtest_output/.venv-regression/Scripts/python.exe).Path
& $env:OSKH_MERGE_PYTHON -m pip install -r requirements.txt
& $env:OSKH_MERGE_PYTHON -m pytest -p no:cacheprovider -q -m 'not production and not benchmark'
```

pytest 默认只发现 `tests/`，临时输出默认放系统临时目录，并尊重显式 `--basetemp`。需避开仓库、输入与湖目录，否则应触发路径保护。Windows 缺少符号链接权限（WinError 1314）时只跳过依赖该能力的用例；Linux CI 设 `BT_REQUIRE_SYMLINK_TESTS=1`，必须实际执行这些保护测试。字节合同说明文本以 LF checkout；测试仅规范化临时路径及平台分隔符，不改变 golden。

CI 安装步骤通过 `MYQUANT_INFRA_READ_TOKEN` 获取私有依赖。账号持有人在本仓 **Settings → Secrets and variables → Actions** 维护同名 secret：fine-grained PAT 的资源所有者为 `baiyibing`，仅选 `MyQuant-infra`，Repository permissions 仅需 **Contents: Read-only**（Metadata 为 GitHub 必需项）。不要将令牌放进源码、URL 或聊天。普通 `GITHUB_TOKEN` 的权限只限当前仓库，不能靠扩大本仓 `contents` 权限读取另一个私有仓库；见 [GitHub 权限说明](https://docs.github.com/en/actions/concepts/security/github_token)。缺 secret 会明确失败；不通过 fork PR 提供私有凭据，也不使用 `pull_request_target` 执行未受信代码。

## Git

- Public: https://github.com/baiyibing/MyQuant-backtrader
- `master` tracks a private internal remote named `origin`. Do not publish that URL. Use `git push github` for the public mirror.
