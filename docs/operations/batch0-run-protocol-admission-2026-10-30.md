# 批次 0：真湖验收器规则身份与 Windows 测试收尾

> 2026-11-01 本机路径/源 B 追加核验见文末；P03/P05 未整包关闭。

对应统一计划 P01 / BT-18、BT-17，批次 0C。改动对象是验收器及离线测试；后续 P14 的目标宿主真湖矩阵尚待执行。

## 规则、费用与低现金判据

验收器新增 `--rule-profile industry|legacy`，默认 `industry`；八个格均显式传给原生 CLI，L1 使用相同 argv。`recipe.json.economic_flags` 记录解析后的规则名、revision、完整 profile 设置和费用各组件（佣金、最低费用、订单粒度、日期税费开关）；各格也记录规则名和 revision。费用从原生入口使用的 resolver 获取，旧固定双边 10bp 标签已移除。

| 入口 / profile | cash=1 格的必要直接证据 |
|---|---|
| CSV 分钟 / industry | exit=0 且 `execution-audit.json.events` 有 `side=SKIP, reason=skip_cash`；拒单不进入原成交 CSV |
| CSV 分钟 / legacy | 非零退出且真实 `InsufficientCashError` 带 date/code；其他异常失败，未触发则 NOT_COVERED |
| v7 / 两种 profile | exit=0 且原生 trades 有 `side=skip, reason=skip_cash` |

每一侧都必须触发；原生/L1 经济产物与输出比较仍先于格判定。两侧空成交、仅退出 0、其他拒单事件均不代签。本格只测试零可买数量；部分缩量继续由已有 `test_if_p08_shrink_on_short_cash.py` 的 1400 股真实 ledger 夹具验证，不从成交数量猜测触发，也不扩大真湖参数矩阵。

## Windows 复现与修复

`test_progress_invalid_utf8_warns_and_appends` 在本机复现：append 使用 Windows CRLF，测试却只接受 LF。断言现按 `os.linesep` 检查追加行，仍逐字节验证原非法 UTF-8 前缀保留、告警存在及追加内容正确。未改动生产 ETL 写入行为。

## 本地验证

Windows vanna312，`PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`：

- `test_verify_run_protocol_lake_parity.py`、`test_if_p08_shrink_on_short_cash.py`、`test_l2_phase3_pipeline.py`：**231 passed**。
- 原规则与短现金兼容域 `test_if_p01_rule_profile.py`、`test_b7_on_short_cash.py`：**32 passed**。
- 新增验收测试用实际 ledger/audit_scope 生成 cash=1 拒单事件；空事件及其他原因不能覆盖低现金格。预注册测试核 receipt 的规则/费用及未配置数据时只启动非法参数格。

Windows 默认 GBK 模式下，原有无编码 `read_text()` 测试会解码 UTF-8 产物失败；验证明确采用 UTF-8 模式，未把该环境差异当成引擎或数据故障。真实湖尚未运行，不由这些离线结果关闭 P14。

合入并完成当前 head 的 CI 后，统一索引追加 BT-18/BT-17 的条目级关闭回执；MyQuant QL01 由其独立 PR 验收。

## 批次 0D / 0F / 0.5 准备

[首日输入回执](evidence/three-repo-closeout-2026-10-30/batch0-readiness.json)记录本机已配置湖根和 resolver 读回、marker SHA 及目录存在。用户已指定本机 `DESKTOP-M5HCFD6`；[1.3 #1259](https://github.com/baiyibing/OSkhQuant1.3/pull/1259)保存独立部署候选的私有配置/空库准备、Redis 隔离租约实测、Windows 运维入口修复与正式预检拒绝结果。真实账户信息不在本仓复制。

I01 配置与 I02 schema 已核；I03 Redis 原语通过但正式槽和旧栈残留交接未签；I04 无新首日批准名单，I05 指数日线止于 2026-10-15，I07 首日日期/窗口待定，继续阻塞真实启动。I06 的日线 volume 合同已核，但不据此代签 SHM 生产者或其他分钟消费者。precheck 为 14 PASS / 3 FAIL / 1 WARN，dry-run 拒启；这次准备不关闭 P05 或完整 SDD，不新增模式 E 为受限 paper 首日的硬前置。

[Owner 队列](evidence/three-repo-closeout-2026-10-30/batch0-owner-queue.json)已核三仓默认分支和 CI 检查名：1.3 main、MyQuant/BT master 均未保护；1.3 rulesets 查询为套餐限制 403，其他两仓为空。列出供 Owner 选择的实际 job context，以及设置后读回和失败/缺 check 验证所需材料。本轮未变更 GitHub 设置，OP17/BT-11 保持待人工。

机器索引的 `implementation_refs` 已指向 [MyQuant #110](https://github.com/baiyibing/MyQuant/pull/110)、[BT #540](https://github.com/baiyibing/MyQuant-backtrader/pull/540) 和 [1.3 #1259](https://github.com/baiyibing/OSkhQuant1.3/pull/1259)。这里仅保存实施入口，最新状态由 PR 和原域回执读取；冻结审计条目及现有 `closeout_receipts` 保持原样，完成条件满足后再追加关闭回执。

## 2026-11-01 合入回执

上述本机测试与准备数字属于 10/30 的切片。最终 [BT #540](https://github.com/baiyibing/MyQuant-backtrader/pull/540) head 为 `b50101c95a66ad3732436426132d7114d7c7740f`，最终 [CI](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/41216264475) 通过，于 10/31 15:48:06 UTC 合入 `f9e51d57bd3149d40fee3c28a450caf3da06e49d`。Windows 已验证的 L2 测试文件与最终合入树 blob 相同；结合最终 Linux CI，BT-17 / BT-18 代码与测试条件满足。

[MyQuant #110](https://github.com/baiyibing/MyQuant/pull/110) 最终 head `7716ab6588a3a3faa8a799f5c0ee54154343733a` 三项 CI（含五文件 data-staging）通过，10/31 14:09:08 UTC 合入 `11720e5b394b440101b31f32038c85ab536f572e`，QL01 完成。与 #1258 的既有 V653_TEST_DRIFT 回执一起，P01 四项全部满足，机器索引追加一次 package 关闭回执，原冻结 64 条记录与旧回执不改。

[1.3 #1259](https://github.com/baiyibing/OSkhQuant1.3/pull/1259) 也已合入，但只证明 Windows 工具与候选准备；P05 仍开放。[后续程序 #1260](https://github.com/baiyibing/OSkhQuant1.3/pull/1260) 在原只读预检中补入真实名单/hash/session、实际环境湖根和源 B 完整性，并修复两处旧 CLI 守卫；本机新程序的历史日期诊断为 15 PASS / 5 FAIL / 2 WARN。现场未签项仍在 1.3 [原域回执](https://github.com/baiyibing/OSkhQuant1.3/blob/6be2d6358b7528fbeae160327fbf70e3aa8c9c5d/docs/run-records/2026-11-01-v653-input-precheck.md)维护，本仓只保存实施入口与固定证据链接，不复制另一套运行状态。

## 2026-11-01 P03 本机原工作区路径核验

对 `DESKTOP-M5HCFD6` 三个原工作区分别用独立冷进程读取各自 resolver，
没有切换用户分支或导入交易/QMT/Redis 栈。[固定回执](evidence/p03-local-paths-2026-11-01/local-original-checkouts.json)
保留实际分支 SHA、模块路径、Process/User/Machine 注册值和 marker hash；
这是原工作区的读回，不代签实际部署进程或远端主机。

| 原工作区 | 配置 Parquet 容器 | 工作区容器读回 | 仅 marker hint、没有 SOURCE |
|---|---|---|---|
| 1.3 | `E:\stock_data`，存在 | 本仓 `stock_data/`，存在 | 拒绝；marker 只作诊断 |
| MyQuant | `E:\stock_data`，存在 | 不拥有 1.3 DuckDB 工作区 | 拒绝；必须配置 SOURCE |
| BT | `E:\stock_data`，存在 | 本仓 `stock_data/`，未存在 | 显式 hint 可解析已有 marker |

三仓实际股票 1d/1m、指数和 ETF 日线根都指向该容器下对应树，目录存在。
`.authority` hash 一致，未写入或更改。Process 与 User 的 SOURCE 均为上述 E 根；
Machine 未注册 SOURCE，不能把 User 配置当作 SYSTEM 服务已经继承的证据。
沿用显式 SOURCE 即可满足三仓共同合同，本片不统一或改变 resolver 行为。

4090/75 尚未重新实机核验，75 的 F 盘位置仍按用户提供信息登记；未扫描盘符。
构建产物路径与实际服务环境仍待核，不能由 CARGO_TARGET_DIR 未设置推导构建目录。
此快照也不证明市场数据最新或字段全覆盖，P03 保持开放。

同次[源 B 只读探针](evidence/p03-local-paths-2026-11-01/source-b-gap.json)以本地日历
`20261102` 作诊断目标：上证指数实际日线止于 `20261015`，所需的 `20261016..20261030`
十一会话全部缺失；调用原预检验证器仍 FAIL，文件 hash 前后不变。
该目标不是首日批准日期；未补数、未启动交易。P05 活状态及后续现场回执仍归 1.3。
