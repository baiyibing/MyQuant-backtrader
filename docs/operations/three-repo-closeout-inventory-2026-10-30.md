# 三仓收尾事项明细

本附录按主实施包归并 64 条审计记录。每条只归入一个主包，跨包关系写入依赖；记录包含待核销和后置事项，并非 64 个均应立即执行的项目。
主分支来源锁定于主计划所列提交；交付前 #1258 合入增量见主计划及 github-refresh.json。补充两份未合分支证据：1.3 日期后续计划钉于 6825f22169，BT artifact 草稿钉于 42662418231ea87af4c72e83f8ee69d6396db715；它们不代表主分支已实现。运行现状以目标宿主的新回执为准。主计划与本附录是本次排期快照，原域 SSOT 继续维护权威状态。

机器可读版本：[inventory.json](evidence/three-repo-closeout-2026-10-30/inventory.json)。

<a id="p01"></a>

## P01 先修明确的测试与验收器缺口

### V653_TEST_DRIFT v653 Phase4c/d/e测试漂移收口

**当前状态**：交付前刷新已完成：#1258 于 2026-10-30 09:50:36 UTC 合入；head ceff70d3，18 项 SUCCESS、1 项 SKIPPED；main 为 1ed67467890edb6c931bf8816c121fa7483cc276

**剩余动作**：不再安排第二次实现或合并；合入后的实际 nightly 历史回执归 P02 跟踪，不重开本项。

**完成条件**：最新 head 的必需检查已通过并合入；保留 PR 中 50 条针对测试、342 条相关回归及最终 Windows 检查证据。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1258) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/run-records/2026-10-28-v653-phase4b-p4-08-claim-kill-late-fill.md#L3)

### QL01 将 ETF 与分钟 staging 离线测试接入 CI

**当前状态**：已合测试代码，CI 未调用

**剩余动作**：将当前遗漏的 5 个 tests/ 文件显式接入 CI 的 data-free 路径，并核真实工作流命令覆盖。

**完成条件**：CI 输出覆盖 tests/test_build_etf_qlib.py、test_etf_daily_qlib_offline_smoke.py、test_stage_1min_from_lake.py、test_stage_etf_daily_from_lake.py、test_train_etf_smoke.py；无需真湖或训练。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/.github/workflows/ci.yml#L27) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/.github/workflows/ci.yml#L86) · [来源3](https://github.com/baiyibing/MyQuant/pull/109)

### BT-18 L1 真湖验收 harness 随 industry 默认变化发生低现金配方漂移

**当前状态**：当前脚本 native_argv 未设置 --rule-profile，而 csv_minute low_cash 分支仍要求 InsufficientCashError；#445 已将默认改为industry，短现金行为是shrink/skip，成功退出会被判NOT_COVERED。静态核对已证实预期与默认不同，尚未在本次跑湖复现。 同一验收 manifest 仍硬写 BILATERAL_10BP，未跟随默认 profile 的费用合同。

**剩余动作**：明确验收目标是当前 industry 默认的 native/L1 一致性，还是保留旧legacy历史配方；在命令和报告身份中显式记录profile；按选定profile更新low_cash触发与成功/拒绝判据，并保留正常/非法参数/错误输出路径断言；使真实减少/跳过现金不足与legacy InsufficientCashError两种语义各有恰当验证，不把旧预期变成假故障；同时移除验收 manifest 的旧固定费用身份，显式记录每个入口解析后的 profile、revision 和实际费用合同。

**完成条件**：同一profile native和facade给出相同结果，低现金格不会因默认切换被误报NOT_COVERED；验收manifest包含profile；随后BT-07完成真实宿主格；industry 低现金格必须有实际 shrink 或 skip_cash 直接证据；两侧 exit=0/空成交不构成通过，未触发继续 NOT_COVERED。现金=1只用于skip；缩量可用独立离线夹具验证；manifest 的费用描述与实际解析的费用合同一致，不能将 industry 结果标为旧 bilateral 10bp。

**依赖**：rule-profile合同；无需先更改成交引擎或调用真实湖即可修验收器。

**范围说明**：这是验收器修复，与14书的golden接线/admission、ABI/能力门或宿主验收分别计项。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/scripts/research/verify_run_protocol_lake_parity.py#L382) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/scripts/research/verify_run_protocol_lake_parity.py#L445) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/pull/445) · [来源4](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/scripts/research/verify_run_protocol_lake_parity.py#L552)

### BT-17 Windows Level2 进度日志测试跨平台欠账

**当前状态**：#526验证说明134通过，test_progress_invalid_utf8_warns_and_appends因Windows CRLF为既有失败；Linux最新CI绿。

**剩余动作**：在实际Windows环境复核该测试，若仍失败，修跨平台换行断言或真实写入契约；不要掩盖非法UTF8恢复行为。

**完成条件**：同一实现Windows/Linux都通过，UTF8损坏告警与append恢复仍被验证。

**依赖**：Windows测试环境与该测试当前源码。

**范围说明**：仅为PR报告的环境差异，本轮没重新跑测试；不能将其写成当前已复现的生产数据损坏。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/pull/526)

<a id="p02"></a>

## P02 CI运行证据与合并检查

### OP16 Full Sweep历史持久化与失败修复

**当前状态**：#1253/#1255已合，真实nightly历史/日志回执待观察

**剩余动作**：收集连续两次实际win-ci nightly，验证history恢复与new/fixed/persisting划分；验证失败chunk及lf_retry日志和flaky ledger可下载，按nodeid区分存量/新红再修。

**完成条件**：首轮EMPTY可解释，后轮加载正确历史；失败可从上传日志复现。不能把全部首次报红当新回归。

**依赖**：V653_TEST_DRIFT。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1253) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/pull/1255)

### OP17 三仓合并检查与保护能力核实

**当前状态**：当前CI可绿但默认分支protected=false

**剩余动作**：核各仓需要的检查与实际合并流程，准备可执行的required-checks配置方案；1.3 rulesets API返回403套餐限制，不写成空rulesets；可用性不足时明确现有人工/CLI合并检查。

**完成条件**：按仓说明可强制与不可强制的检查，当前head全部必过结果能被合并流程使用。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/actions/runs/41027368330) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/40990165399)

### BT-11 GitHub 分支保护：有绿 CI，无强制门

**当前状态**：2026-10-30 用 gh 复核 master protected=false，rulesets=[]。最新5个master CI成功，最新 run 40990165399；历史“#450以来CI红”已失效。RB-01 文档仍要求Owner设置required checks。

**剩余动作**：在统一仓库治理范围决定 master 的 required checks、review 与 bypass；以实际工作流 job 名配置；开启后验证 PR 失败/缺check不可合、正常PR可合；保留合法紧急流程。

**完成条件**：gh API 返回已启用保护或规则集，required checks 对应真实 job；有最小验证回执。

**依赖**：repo Owner/admin；grok-bot-ops 仓库治理约定。

**范围说明**：本次只读盘点，没有修改 GitHub settings。CI并行重构/广泛新增测试不是这条必要前提。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/rb01-github-branch-protection-steps-2026-10-06.md#L7) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/40990165399)

<a id="p03"></a>

## P03 机器路径和消费数据质量

### OP09 三仓机器路径与湖权威约定修订

**当前状态**：代码已有resolver；部分宿主文档仍泛化F盘

**剩余动作**：按用户确认区分本机/4090无F与75机有F；使用已配置根和.authority，不探盘猜位置；行情根、workspace和Rust构建缓存分别登记；复核1.3 #1197与BT #496的实际适用主机，修正过时说明。

**完成条件**：每台目标机的配置、marker和读写角色一致；缺配置/缺文件失败，不发生自动搬盘或跨湖fallback。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1197) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/pull/496) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/architecture/f-lake-cross-repo-contract.md)

### BT-10 机器 authority / Rust 构建路径与 ETF/指数/TR 覆盖统一

**当前状态**：市场三树 resolver 与 fail-fast 已实现；9/9 ETF/index 劫持旧文不能当当前缺陷。#496 的 Rust 手册却统一写 F: 迁盘并声称本机/1.3 已改；用户明确 F 仅75物理机，本机与4090无F。策略10最新宿主快照显示 lake∩TR 比湖少约100–120码/日，含约50北交所，不能宣称全市场覆盖。

**剩余动作**：按机器身份记录 authority hint/marker、行情根、workspace 与 Rust artifact/cache 根；核 #496 的主机归属并修旧说明，禁止按文档自动迁盘；汇总1.3最新股票/指数/ETF日线与分钟 coverage manifest；BT只验收消费根和缺失报错；给TR/BJ/缺bands覆盖列明已支持宇宙与补齐策略，区分合法非股票排除、停牌退市和漏刷。

**完成条件**：三仓在每台机器的 resolver 解析到唯一已声明根；不存在靠 F 默认猜根；ETF/index 与 stock 隔离、None/front 合同正确；各研究宇宙的缺失与最新日期有清单。

**依赖**：本机 .authority 核验记录、75/4090 真实配置、1.3 producer coverage、TR Store。

**范围说明**：TR 数量是2026-10-12记录，不是今天本次扫描；旧159915截至7/31只能作为待核线索，不能断言当前仍缺。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/AGENTS.md#L64) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/pull/496) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/engineering/handoff-rust-host-env-to-oskhquant-1.3-2026-09-21.md#L9) · [来源4](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/note-strategy10-source-b-universe-2026-10-12.md#L30)

### SHM_DATA_QUALITY 共享内存读回后的行情内容质量

**当前状态**：真实缺陷/未验证数据字段，独立于通道成功

**剩余动作**：10/24同窗1m close有价但volume全0、suspendFlag全1，分钟volume可用性未证；不能用下载job ok或有行数替代字段验收；按当前策略消费者实际需要验证1m OHLC/volume/suspendFlag及水位，明确停牌/退市与空壳差异。

**完成条件**：按需要字段逐码逐窗口判读，数据有效性、来源、单位与水位都有证据；失败具体列码，不自动换源或填0。

**依赖**：QMT行情本地缓存与导出湖质量；消费者策略是否要求volume，尤其BT相关分钟策略。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1206) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/pull/1208) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/qmt-shm-2026-10/probes/run-2026-10-24-m5-v136-minute-and-mmcancel.md#L50)

<a id="p04"></a>

## P04 共享内存现行业务范围验收

### SHM_RUNTIME 共享内存桥接与下载运行验收

**当前状态**：代码和部分M5验收完成，剩现场证据与运维收口

**剩余动作**：M5未测到180s无status后的lease自动取消：此前job先完成，显式取消PASS不替代；现有记录将继续Phase B后置，恢复前需重新定范围；按#1208现行业务必过口径留存1m+1d同窗的job、evt、item、身份、非全零读回证据；当前已查记录中的同窗1m非零close不足以代签整个新矩阵；将桥/shim版本、唯一桥进程、健康心跳、阻塞/重启恢复与运维监督加入独立数据任务验收；不据协议探针或单测宣称生产切换完成。

**完成条件**：真实记录分别证明取消请求、cancelled终态入环、之后daily不busy，不把180s写成立刻解锁SLA；现行业务1m+1d矩阵PASS及版本/输入窗口/事件身份留证；实际部署与回滚明确；按冻结的消费者字段合同判定：不依赖 volume 的消费者可单独签其通路，但 volume 未验证仍须保留，不代签要求成交量的其他消费者。

**依赖**：目标M5/QMT模拟数据端与桥版本一致；独立数据任务运行窗口与不并发抢占下载job。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1171) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/pull/1195) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/pull/1199) · [来源4](https://github.com/baiyibing/OSkhQuant1.3/pull/1204) · [来源5](https://github.com/baiyibing/OSkhQuant1.3/pull/1205) · [来源6](https://github.com/baiyibing/OSkhQuant1.3/pull/1208) · [来源7](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/qmt-shm-2026-10/probes/run-2026-10-24-m5-v136-minute-and-mmcancel.md#L94) · [来源8](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/qmt-shm-2026-10/probes/runbook-minute-30m-60m-1h-2026-10-22.md#L14)

### SHM_DESIGN_STATUS 原共享内存方案与已合实现的状态整理

**当前状态**：历史方案待归档/重定界，不能当成未实现总清单

**剩余动作**：补一份窄状态映射：原设计哪些被已合实现替代，哪些生产交易总线能力仍未验收，哪些不再继续；保留历史评审。

**完成条件**：活入口明确当前实现/验收范围、仍未获生产切换认可的边界；不让README的旧NO_GO与实际GO互相冒充。

**依赖**：现行代码与M5记录，不能从v3.1伪码缺陷推断v1_36实际代码同样有缺陷。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/qmt-shm-2026-10/README.md#L7) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/architecture/reviews/2026-10-16/pr1171-daqmt-shm-broker-channel-grok-rereview-nits-2.md#L19)

<a id="p05"></a>

## P05 SDD与6.53受限paper首日

### SDD_RUNTIME SDD单活跃日槽目标机验收

**当前状态**：合同/代码/default-on和离线测试完成，实机运营验收未完成

**剩余动作**：目标机真实Redis/目标配置验证缺槽、错槽、同profile双开、同日换profile拒绝；记录keeper/observer拒绝埋点；验证续租/观察连续三败后只停新意图/submit、既有fill/reconcile/cancel仍处理；在新交易日按人工清单演练停旧、核残留、换runtime、写槽、起新；同日不热切。

**完成条件**：真实Redis和进程证据逐场景满足日槽合同；首日签收引用同一记录。

**依赖**：确定目标host/account/runtime/运营槽路径；与v653首日共用同一个现场验收，不再造重复文档仪式。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1212) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/pull/1229) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/sdd-single-active-day-slot-2026-10-14.md#L7) · [来源4](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/sdd-day-slot-audit-signoff-2026-10-28.md#L28)

### V653_PAPER_FIRST_DAY 6.53迁移的目标机首个paper交易日

**当前状态**：paper GO与接线已实现；真实首日NOT VERIFIED

**剩余动作**：目标机真实runtime、账户/userdata/Redis/独立DB/schema、批准名单及合法新交易日日槽；mini/daqmt两腿指数源B完成日数据现场证据；同一部署仍只选一个vendor；按runbook完成precheck、preflight、dry-run、真实paper启动、直接cycle事件、首笔订单到本地状态收敛、EOD快照与冻结残余、停止和人工签收；未触发场景标未触发；受限paper不宣称完整6.53经济语义；无首笔买单时可签 cycle/EOD/stop 子项；intent→execution_log→action-state 链继续未签，真实触发后才可关闭整个首日包。

**完成条件**：首日runbook第6节逐项产物与直接事件，人签；无重复BUY、跨策略串账或无证据放行。

**依赖**：V653测试漂移已由#1258合入收口；SDD同日单活跃现场核验；有效源B与批准名单，仍禁止LIVE/D3和parking/profit-skim执行。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1237) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/pull/1254) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/operations/v653-paper-first-day-runbook.md#L3) · [来源4](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/operations/v653-paper-first-day-runbook.md#L101) · [来源5](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/run-records/2026-10-28-v653-paper-wiring.md#L57)

<a id="p06"></a>

## P06 6.53模式E完整语义

### V653_MODE_E 6.53停泊/利润抽离完整模式E

**当前状态**：仅observe已实现，执行关闭；独立红队与执行验收未完成

**剩余动作**：Mode E独立红队、真实equity/已抽离本金证据和允许执行边界；随后单独实现/验收执行能力或明确受限paper阶段的后置边界；不能用observe通过冒充完整迁移完成。

**完成条件**：模式E所需完整资金状态及执行语义与冻结BT6.53合同逐项核对；未完成前保持execute=false。

**依赖**：真实paper基础路径可观察；经济事实与资金守恒验收；独立L3评审/相应执行授权。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/plan-turtle-to-v653-2026-10-10.md#L3) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/plan-turtle-to-v653-2026-10-10.md#L42) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/operations/v653-paper-first-day-runbook.md#L127) · [来源4](https://github.com/baiyibing/OSkhQuant1.3/pull/1237)

<a id="p07"></a>

## P07 同仓拆包及独立数据服务

### OP01 同仓拆包与独立数据任务生命周期

**当前状态**：架构方向已由用户确认；运行耦合仍需收口

**剩余动作**：巨潮与通知代码留在1.3，沿既有包独立依赖/入口/监督，不新建业务仓库；将交易停止与数据调度停止明确分开；通知ACK/升级当前依赖Monitor，不能只保留scheduler就称完整独立；迁移BT旧Wind/AI pull的producer能力，保留必要兼容入口和冻结run读面；10/24窄例外曾获授权，不追认当时为违规；为QMT日线/分钟和Qlib派生刷新形成实际宿主调度清单；非交易日也检查缺口；统一最近已完成行情目标日与全量front刷新计划；任务运行日与数据目标日分别记录；按 alert_domain=system/breaker/cninfo 分别列出 Monitor 停止后的必需存活能力、仍有依赖能力和明确不覆盖项；必需域未过，不能给整个通知能力独立 PASS。

**完成条件**：停交易后的采集调度及所声明通知能力有独立存活/失败回执；周末补历史、盘后增量、恢复和显式停止均留证；QMT端job取消、桥进程监督、失败汇总与水位验收明确，不能仅按下载进程exit=0判成功；每个声明必需的通知域各自有发送/ACK/升级/失败语义的适用回执；不以某一域成功代签其他域。

**依赖**：OP02；SHM_RUNTIME。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/scripts/ops/stop_turtle_paper_procs.py#L84) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/oskh_notification/ack_policy.py#L22) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/scripts/data/run_daily_adjusted_fast.py#L553) · [来源4](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/scripts/data/run_stock_minute_increment.py#L169) · [来源5](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/operations/corp-actions-incremental-driver.md#L3) · [来源6](https://github.com/baiyibing/OSkhQuant1.3/blob/6825f22169/docs/operations/plan-cninfo-economic-date-evidence-2026-10-30.md)

### OP02 disclosure/notification Phase0 从原型到可运行包

**当前状态**：W01-W06部分原型已合；完整G0/双跑/W07未完成

**剩余动作**：完成完整采集包依赖闭包和目标主机冷启；W01薄wheel通过不等于完整collector可部署；按现有Phase0补宿主材料与缺失签收，安排隔离双跑和真实通知验证窗口；明确独立ACK/升级的迁移范围；RAGFlow接入作为下游可选片，不能成为结构化事实采集前置。

**完成条件**：真实目标机冷启、可观测性、回滚、旧新双跑差异和指定通知能力逐项有回执；未完成字段仍未签；只有offline stub不改变G0/真实通知状态。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1252) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/run-records/2026-10-30-phase0-dual-g0-w07-evidence-pack.md) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/disclosure/phase0-w01-extracted-package.md) · [来源4](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/disclosure/phase0-w01-collection-ingest-pipeline-map.md#L64)

<a id="p08"></a>

## P08 公司行动PR与明确日期证据

### OP03 Hithink/CNINFO 已有PR与冻结合同收口

**当前状态**：1.3 #1256、BT #538草稿；BT #531/#532仍开放

**剩余动作**：核当前head CI与独立评审，决定现有PR的合并/替代关系；避免平行实现采集器；生产方留1.3，BT只导入冻结产物；目录更名PR须核旧run冻结路径和脚本兼容。

**完成条件**：生产/消费合同版本、hash、失败与隔离规则一致；旧数据不被新目录或坏快照静默覆盖；开放PR各有明确处置，代码合并与经济批准/湖发布分别记录。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1256) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/pull/538) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/pull/531) · [来源4](https://github.com/baiyibing/MyQuant-backtrader/pull/532)

### OP04 162条现金事件的公告经济日期补齐

**当前状态**：续片计划及独立设计复核已完成；尚未编码

**剩余动作**：BT导出冻结目标，1.3独立查询162事件码加D11共173码，保存分页/PDF/文本和字段证据；回测仅离线产生日期建议；明确日期、兼容采用日期和政策标志分开；金额原始值与适配值分开；公告窗口、事件窗口、带时区as-of及观察时间分开；中断批次不混拼，COMMITTED后不可续写。

**完成条件**：每条建议可追到明确来源和输入hash，歧义/更正/错身份/缺页/精度差异不自动放行；162条现金事件不因无关红股上市日缺失被阻断；原Wind/Hithink冻结文件hash保持。

**依赖**：OP03。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/6825f22169/docs/operations/plan-cninfo-economic-date-evidence-2026-10-30.md) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/blob/42662418231ea87af4c72e83f8ee69d6396db715/docs/operations/hithink-coverage-followup-2026-10-30.md)

### BT-01 Hithink / CNINFO 公司行动：消费 gate 与真实事实覆盖收尾

**当前状态**：当前 3 个 open PR 是 #538 draft（导入与经济 gate 首片）、#531（协作/四源/扩样文档）、#532（静态快照目录去日期）。#533–537 仅同步 1.3 C2 取证指针，不等于签字、调度、合湖或主源替换。#538 已实现 gate 与诊断，47 条 frozen diagnostic facts、D11 coverage 和换股模型边界仍影响消费准备。

**剩余动作**：按本会话最新 GO 更新 11 码逐事件 coverage；把明确公告日期与旧 listing=ex_date 兼容值区分并保留字段来源；完成 1.3 包拆分、统一采集产物契约；BT 只导入冻结产物、校验身份与经济口径；显式迁移 BT #507–511 的 scripts/data/pull_corp_actions_incremental.py producer 能力到1.3包；可保薄兼容入口。10/24曾获consume-only窄例外授权，最新边界收敛不能遗漏它；处理换股/注销/新股上市等事件，不向现金/送转十列硬塞；不混合来源拼一行；分别收口 #538、#531、#532；机械目录重命名与经济规则审核分开验收。

**完成条件**：指定窗口所有目标码都有完整解释的覆盖账；不支持事件明确阻断或另合同消费；每个补入日期有公告标识和可追溯来源；事实日期与兼容日期可区分；签字/调度/发布分别记录；open PR 状态与实际落地文档一致，consumer 对真实产物给出通过或有原因的拒绝。

**依赖**：根代理掌握本会话最新 GO 与新公告，须以其补充覆盖较旧 PR body；1.3 producer artifacts / 公告证据 / 经济口径审批；BT frozen consumer。

**范围说明**：不得沿用旧 PR body 中“等待东兴结果公告”的说法；已核对 2026-10-27 官方结果公告。已通过字段诊断阈值不等于经济口径审批。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/pull/538) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/pull/531) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/pull/532) · [来源4](https://github.com/baiyibing/MyQuant-backtrader/pull/537) · [来源5](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/operations/corp-actions-incremental-driver.md#L3)

<a id="p09"></a>

## P09 覆盖缺口及证券转换模型

### OP05 公司行动覆盖、经济审批与C3调度

**当前状态**：D11与31条Wind-only历史键仍未闭合；C2签收/C3未完成

**剩余动作**：保留2774码分母，按代码/经济窗口/事件种类出覆盖矩阵；明确查询完成不等于事件完整；解决历史31键与D11身份/无事件证据，或给有证据的有限消费范围，不能删股票缩分母；C2逐源证据与经济政策完成后再开独立备份调度；合湖及默认切源单列。

**完成条件**：每个已放行范围有证据及相应审阅；unknown/unsupported阻断涉及的持仓与请求；C2 38码/152份公告的147一致、0字段差异不冒充全市场替代Wind完成。

**依赖**：OP04。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1251) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/pull/1256) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/pull/538) · [来源4](https://github.com/baiyibing/MyQuant-backtrader/pull/527)

### OP06 东兴换股与证券转换消费模型

**当前状态**：现有现金/送转模型不支持；本片先做事实与研究合同

**剩余动作**：分开issuer/source/target身份与生效/可知时间；保留601198→601995、0.4376等来源事实；冻结目标股估值、待换股权益、成本迁移、交易锁及股东级尾数政策；真实账户数量以登记结果为准；通用消费者接入另片，不能把换股挤入bonus_ratio，也不自动把目标股加入选股池。

**完成条件**：跨摘牌/登记/上市窗口现金与权益不凭空消失；事后公告不提前用于决策；不支持场景显式阻断。

**依赖**：OP04。

**证据**：[来源1](https://static.cninfo.com.cn/finalpage/2026-10-16/1225606336.PDF) · [来源2](https://static.cninfo.com.cn/finalpage/2026-10-27/1225627350.PDF) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/blob/6825f22169/docs/operations/plan-cninfo-economic-date-evidence-2026-10-30.md)

<a id="p10"></a>

## P10 ST ETF及历史事实数据

### OP07 ST历史补批与多主机覆盖对齐

**当前状态**：不同主机覆盖不一致；优先批完成不等于全56批完成

**剩余动作**：先按host与authority根重测status，分开16/56+优先14/14和4090的42/56快照，不能平均或混称权威；补确实缺少的批次/实施日期、复核沪市unknown_end和merge结果；已证明空批不重复请求。

**完成条件**：带host/root/时间/来源hash的当前覆盖清单和待补集合，逐码有效期及unknown_end可追溯。

**依赖**：OP09。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/operations/st-data-channels-ssot.md#L124) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/pull/1120) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/pull/1122)

### OP08 ETF湖与front历史质量缺口

**当前状态**：已有真实回补；残余缺口为旧时点证据，须重测当前湖

**剩余动作**：重核10/13的40个front全零与42个分钟无有效OHLCV清单；按明确来源补齐或维持具名缺口；G.30写入过滤已合，收集全量front刷新后的丢弃埋点/对齐验收，存量44老股清理单列。

**完成条件**：按数据种类/复权域/日期分别给当前分母、水位、缺口原因与处理结果，不复制none伪造front。

**依赖**：OP09。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1167) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/pull/961) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/operations/etf-qmt-download.md) · [来源4](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/accepted-risks-registry.md#L476)

### QL09 历史行业 PIT 与市值来源合同

**当前状态**：明确后置；当前行业表仍是现时快照

**剩余动作**：1.3负责来源与历史区间数据，MyQuant消费日期化行业/市值；记录有效时间、公告可知时间、改分类及缺码策略。

**完成条件**：历史窗口不能读未来分类；缺证据阻断对应实验；源hash及覆盖可追溯。

**依赖**：上游可信历史源与覆盖；跨仓合同。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/pull/100) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/my_scripts/ranking_neutralize.py#L9) · [来源3](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/reviews/2026-09-19-joint-return-implementation-plan.md#L166)

### BT-12 行业模型尚未覆盖的上市特殊期与完整历史 PIT

**当前状态**：industry P01–P11主要规则已落、默认industry；special_no_limit_days 仍 pending false，开启会 DATA-MISSING。G4 s11 双快照只完成受控CYQK替身的合成方法验证，未证明真实Rust CYQK/股本/供应商历史PIT。

**剩余动作**：在1.3数据契约中补PIT IPO/relist/resumption等特殊期事实，再在BT明确特殊无涨跌停规则范围；对真实s11 exporter/Rust CYQK做版本化来源、历史股本与front快照敏感性取证，区分“同快照前缀因果”与“历史当时可得”；将每个当前不支持的模型条件显式标在研究报告，别把源码缺开关当作全市场已实现。

**完成条件**：特殊期处理有明确来源/日期/窗口合同与代表性真实对照；G4 每一未证命题有实际证据或保留边界，不能借 synthetic PASS 盖全历史章。

**依赖**：1.3 PIT instrument/status事实；真实历史快照与Rust library。

**范围说明**：费用、整手/科创/北交所申报、零股、现金缩量、v7时序已实现，不列为缺失；PIT扩展按实际研究需求裁范围。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/industry-rule-profile-2026-10-06.md#L76) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/g4-front-pit-evidence-2026-09-28.md#L3) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/g4-front-pit-evidence-2026-09-28.md#L11)

<a id="p11"></a>

## P11 ETF qlib E3和E4

### QL02 ETF E3 真湖独立 provider 与读回验收

**当前状态**：代码已合，宿主验收仍独立待收口

**剩余动作**：按冻结 2020-01-02..2026-10-13 窗运行 E2；核历史 VWAP 与 front OHLC 复权域；保存日历、全宇宙/长历史子集、逐代码缺日、4 个ETF读回和受保护目录证据。

**完成条件**：E3 逐条通过；读回 close 与 front 湖误差<=1e-4；历史 VWAP 口径有证据；股票日/分钟 provider 未变。

**依赖**：1.3 ETF 湖已就绪；配置根明确；建议先完成 QL01。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/plan-etf-qlib-daily-2026-10-14.md#L92) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/etf-daily-qlib-offline-smoke.md#L34) · [来源3](https://github.com/baiyibing/MyQuant/pull/107) · [来源4](https://github.com/baiyibing/MyQuant/pull/109)

### QL03 ETF E4 Alpha158 训练预测与有效 IC

**当前状态**：入口已合，真实 E4 验收未收口

**剩余动作**：E3通过后跑固定切分 Alpha158+小LightGBM；记录fit边界、跨分段标签剔除、有效样本、IC/RankIC及缺日/幸存者偏差。

**完成条件**：fit/predict成功，预测标签有效样本非空、IC有限；失败不自改标签/模型；不提前加 TopkDropout。

**依赖**：QL02。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/plan-etf-qlib-daily-2026-10-14.md#L93) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/etf-daily-qlib-offline-smoke.md#L34) · [来源3](https://github.com/baiyibing/MyQuant/pull/109)

<a id="p12"></a>

## P12 Qlib派生刷新和产物合同

### QL10 日频 Qlib 刷新运维与纯湖重建尾项

**当前状态**：刷新管道完成；定时刷新/integrity对齐后置

**剩余动作**：把Qlib派生数据刷新纳入独立数据任务编排；核archive+CSV仍承担的特征字段来源；纯湖重建要保持17字段语义；补刷新清单/水位/失败回执与上游完整性对齐。

**完成条件**：定时/非交易日修复路径成功；四门禁后原子swap；日历/宇宙/特征覆盖及回滚可验收。

**依赖**：1.3数据下载独立生命周期；完整字段数据来源。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/plan-three-repo-roadmap-2026-09-12.md#L205) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/run-manifest-spec.md#L77)

### QL11 Qlib 分钟增量刷新宿主验收

**当前状态**：基础设施已合；真实增量回执未找到

**剩余动作**：在已有分钟provider上验证湖新增后日历前推、旧分钟保留、日频provider不变；若确有业务需要再做20标的分钟训练冒烟。

**完成条件**：分钟calendar advances且日频day.txt/hash不变；不截短已有分钟；预测单独输出。

**依赖**：已配置分钟湖；QL01的分钟staging测试接线。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/pull/84) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/qlib-1min-infra-2026-09-18.md#L22) · [来源3](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/qlib-1min-infra-2026-09-18.md#L54)

### QL12 训练与导出 manifest 写盘失败语义

**当前状态**：已知后置修复，当前仍仅告警

**剩余动作**：明确哪些manifest属于交付必需项；必需manifest失败应返回失败或显式不完整产物；保证不会被下游当作完整成功。

**完成条件**：注入写盘失败后不返回可发布成功；训练/导出各路径有失败回执与下游拒绝规则。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/pull/100) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/my_scripts/export_daily_pool.py#L464) · [来源3](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/my_scripts/custom_train_backtest.py#L1049)

### QL13 signal bundle scores-only 两项审阅遗留

**当前状态**：已知非阻塞 nit，当前仍存在

**剩余动作**：决定scores-only且不存在旧bundle时是否拒绝或不生成空bundle；将available-at格式校验放到保留旧bundle的提前return之前。

**完成条件**：旧pool目录不因scores-only得到误导空合同；非法时间参数每条分支都拒绝；默认CSV字节不变。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/pull/100#issuecomment-5826204003) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/my_scripts/export_daily_pool.py#L346) · [来源3](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/my_scripts/export_daily_pool.py#L357)

<a id="p13"></a>

## P13 策略基线与静态研究验收

### BT-04 14 本新增书的正式 off-byte baseline admission

**当前状态**：当前 master PENDING_BOOK_NAMES 明确为 version13、6_51、6_52、6_53、6_54、6_55、6_56、6_63、6_64、version14、6_65、6_67、10_1、10_2。已有研究/性能结果不等于 golden 已入列。

**剩余动作**：按最终规则和当前 industry profile 分批确定需要长期冻结的书，避免对仍试验的每个历史候选自动录 golden；固定日线/分钟适用能力、费用/现金/除权开关、输入与依赖版本，再完成授权 overlay 和 admission；给 1.3 6.53 迁移提供规则版本、事件语义及可复核对照产物。

**完成条件**：每本有明确 admitted / experimental / retired 状态；admitted 书的 golden 与 admission gate 一致；6.53 回测消费与交易迁移共享同一冻结规则，不拿不同配置历史收益作回归金标准。

**依赖**：最终策略规则口径、人裁 baseline 范围、6.53 迁移验收合同。

**范围说明**：TopK dropout 已在 BOOK_NAMES，不应从 #489 旧硬化请求误报其完全没 baseline；PENDING 并不表示策略代码未实现。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/scripts/research/generate_off_byte_baseline.py#L138) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/note-independent-ladder-numba-2026-10-09.md#L209) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/pull/446)

### BT-06 策略11 ma_chip：D 静态档案/seed30 与全市场验证

**当前状态**：A–C 已移植，X03 退出域修复有各自验证；D 尝试停在缺宿主/静态档案，未完成 seed30 与旧七份档案对照，也未证明全市场多头有效。

**剩余动作**：定位并冻结七份静态档案、seed=20240907 的同一30码名单与原参数/数据；做日线/分钟当前实现对照，按成交时点、价格、费用、volume、skip 原因归因；另做全市场敏感性/信号合理性统计；不要复活 Cerebro。

**完成条件**：D 结果有事实范围、差异解释、sanity bound 和最终研究结论；不可获得的旧档案有明确替代方案/取消裁定。

**依赖**：静态档案可获得性、Rust/CYQK 可用产物、明确湖与原 universe。

**范围说明**：这是研究验证尾项，A–C 框架并非没实现；旧档案对照不要求强行字节一致。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/plan-version11-machip-csv-2026-09-21.md#L3) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/plan-version11-machip-csv-2026-09-21.md#L80) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/plan-version11-machip-csv-2026-09-21.md#L99)

### BT-13 策略12 lot0 台阶锚与 s11 X02×X03 组合验收

**当前状态**：G8仍保留lot0全卖/部分卖/买回后的台阶锚业务决策；s11 X02×X03 真湖组合验收格仍“未证实”。这与 s12 SliceD日/分钟5书烟测已完成不同。

**剩余动作**：在继续该策略改进时，冻结 lot0 生命周期预期，再实施/验证对应改动；保持latch=A、residual=2直至明确决定；若研究会使用s11 X02×X03组合，补冻结池/价格域/配置的逐事件真湖验收；不使用则标停用边界。

**完成条件**：规则生命周期具名、代表性出入场序列可解释；启用组合的证据等级明确。

**依赖**：业务规则决策、冻结实验配方/湖、策略11 D可共用证据。

**范围说明**：G7 SMA 等号是另轴候选，无证据把它升级成当前强制缺陷；s12 X02拒绝是合同，不是待补支持。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/industry-state-acceptance-index-2026-09-28.md#L52) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/industry-state-acceptance-index-2026-09-28.md#L101)

<a id="p14"></a>

## P14 引擎真湖验收

### BT-07 引擎 Slice D 与 L1 native/facade 真湖验收

**当前状态**：#108 A–C 已完成；其 D 同窗1–10/v7 reason桶宿主对照非合入门，未找到专属收官记录。#258 L1 lake harness 已写，真实 normal/low_cash/bad_output 格尚未跑通；代码级 fixture 通过不等于宿主 PASS。

**剩余动作**：将旧引擎 D 与当前 native/facade 验收合并到一次具名宿主证据包，但分别标合同和基线；按同一代码/来源/名单身份跑正常、低现金、非法参数、输出路径拒绝；正常格要求真实买卖和非空权益审计。

**完成条件**：所有具名格有 PASS 或明确 NOT_COVERED 的处置；native/L1 输出与拒绝语义一致；旧 D 记录补齐或注明被哪一份新验收替代，避免永久双待办。

**依赖**：BT-18 低现金配方漂移修复完成；当前 rule-profile 决策、稳定日线/分钟/指数数据、宿主执行。

**范围说明**：v7/APP 主引擎迁移 #402 已完成，不能与此验收尾项混为未迁移。BT-18 单列当前验收脚本的实质漂移修复，BT-07 只计算宿主验收工作，不重复估工。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/pull/108) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/plan-ashare-engine-refactor-2026-09-18.md#L194) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/pull/258) · [来源4](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/note-l1-lake-e2e-b-native-cv01-2026-09-29.md#L7) · [来源5](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/scripts/research/verify_run_protocol_lake_parity.py#L382) · [来源6](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/scripts/research/verify_run_protocol_lake_parity.py#L445)

<a id="p15"></a>

## P15 分钟冷加载与性能后继

### BT-05 分钟冷加载：S1.1 后真实测量、分片、codeset、Arrow

**当前状态**：#482 只落 S1.1 probe 脚手架。runtime 仍 monolithic，没有 OSKH_MINUTE_CACHE_SHARD，实现环境没有配置湖，真实宿主数字 PENDING；S1/S2/S3 未交付。

**剩余动作**：在配置冻结湖的宿主跑代表性 scan/open 和 shard write/read 成本测量，记录真实 append/repair 重建文件数；依据测量选粒度；实施默认关闭的 S1 分片缓存并做同 commit OFF/ON CSV 字节与来源身份验证；后续 S2 处理代码集、parking-code 与窗口核对；S3 Arrow 独立确认收益后实施。

**完成条件**：S1 冷加载不退化、warm 二次命中零湖读；窗口/月份边界、G2 变化失效、原子发布与并发临时文件通过；S2 实际 codeset 完整；S3 不改变 frame/成交合同且有实测收益。

**依赖**：机器/authority 盘点、可读冻结湖、代表性 TopK/6.53 工作负载、分阶段范围。

**范围说明**：不要重复做已交付的 Numba、DayBuyQuotes、variable-frame layout。<=5min 不是 S1 单独硬门；不预先承诺速度倍数。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/note-minute-cache-cold-load-s11-2026-10-16.md#L8) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/note-minute-cache-cold-load-s11-2026-10-16.md#L46) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/note-minute-cache-cold-load-s11-2026-10-16.md#L68) · [来源4](https://github.com/baiyibing/MyQuant-backtrader/pull/482)

### BT-16 分钟热点与 pending 事件可观测性残余（测量后取舍）

**当前状态**：10/9最后遗留：held_scan仍有Python真实动作回调；chronological pool_quote仍DataFrame（6.53默认不走）；开盘跌停顺延只计数、未逐根record_limit。已有pending_sells.csv和队列观测 #389，不是完全没日志。

**剩余动作**：优先完成冷加载，之后用当前工作负载profile决定是否处理真实动作回调或chronological quote；如审计需要逐事件跌停顺延，补与现有pending日志一致的记录，不动fill结果。

**完成条件**：优化有实测墙钟收益和成交等价；新增事件审计能追踪且不改变冻结输出。

**依赖**：当前性能与审计需求；golden/成交不变验证。

**范围说明**：不能把早期“Numba nondeterministic”、fixed-span layout等历史试验再列未完成；最终锁与variable-frame选择已完成。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/note-independent-ladder-numba-2026-10-09.md#L209) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/pull/389)

<a id="p16"></a>

## P16 Level2全量覆盖与重复行口径

### BT-02 Level2 Phase3 历史批量 ETL 与真实全量覆盖

**当前状态**：#512–526 已实现 rar→CSV→SSD Parquet→逐日发布，双 ETL、可选 Polars、编码、失败记录、distinct-TranID gap-free 修复。#526 最新提交说明有 1084 日已入湖，13 日假 gap 阻断已修，约 370 日仍待续跑；#526 无后续完成评论。

**剩余动作**：从实际执行宿主 manifest/progress/fail notes 读取最终覆盖，不把 merged 当作全量完成；恢复被假 gap 拦住的日期，再续跑剩余窗口，记录成功/隔离/真实缺号三类；核对文件数、行数、日/码范围与失败重试，形成可重复增量/重跑回执；若继续 mixed Polars，补真实日性能与跨引擎一致性验收；保留当前已批准调度配置。

**完成条件**：声明窗口 manifest 覆盖完整或每个缺口有具名处置；失败队列清空或明确隔离；重跑幂等、发布原子、真实缺号仍 fail-closed；实测吞吐与资源峰值落档。

**依赖**：1.3/宿主原始归档、BT 离线 L2 分析流水线、实际 authority root、宿主执行/磁盘资源。

**范围说明**：1084/约370 是 PR 时点数据，未在本次盘点远程扫湖，不能声称今天仍是该数量。#522 的多数 review nits 已由 d6e2190 修复，不重列。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/pull/526) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/pull/524) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/pull/520) · [来源4](https://github.com/baiyibing/MyQuant-backtrader/pull/522) · [来源5](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/run-records/2026-10-28-l2-etl-polars-compare.md#L1)

### BT-03 Level2 重复成交行的消费/去重规则

**当前状态**：#526 修正了供应商重复 TranID 导致的假缺号，但保留源重复行：600421 有字节完全相同的收盘行；688633/688660 同尾号存在多条不同合法记录。

**剩余动作**：单独界定完全重复行与同 TranID 不同成交的业务区别；检测下游聚合是否会把完全重复行重复计量；必要时在消费侧提供有证据的去重规则与审计计数；如决定重写存量 Parquet，另给版本化迁移与回滚计划；不把 distinct-ID 检查偷换成逐行去重。

**完成条件**：完全重复和合法同号多行有代表性真实 fixture；成交量/金额聚合验证通过；存量影响量已量化。

**依赖**：原始 vendor CSV / 字段合同、Level2 聚合消费者。

**范围说明**：这是 #526 明确后置的独立决策，尚未证实所有下游当前都算错。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/pull/526)

<a id="p17"></a>

## P17 TopK及联合收益后继研究

### QL04 联合收益完整 P-CHASE 与弱信号来源准入

**当前状态**：control-only 已通过；其余臂仍 INPUT_BLOCKED/NOT_RUN

**剩余动作**：明确恢复 full 的范围，补齐原 candidate/anti/label/共同宇宙和P-REF来源；按原统计口径复核，重新冻结；不得只改mode字串或伪造缺字段。

**完成条件**：full源和P-REF核验通过；明确每臂完整日历、分母、来源hash；P-CHASE/weak单独有证据，不借P-BASE状态放行。

**依赖**：保留已完成 P-BASE/M-REF/M-LAG 基线；来源、可知时点及对应合同。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/reviews/joint-return-v1/contract.md#L82) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/reviews/joint-return-v1/input-register.md#L47) · [来源3](https://github.com/baiyibing/MyQuant/pull/95)

### QL05 联合收益 R2 换手预算与 anti-chase 联合约束

**当前状态**：已规划的后继，未见交付

**剩余动作**：先固定换手预算τ、容差和冲突策略；先 P-TURN，再 P-CHASE-TURN；产出turnover/constraints/intents。

**完成条件**：价格漂移与交易分开；现金/初建/旧仓计入；冲突不放宽预算；目标/实际换手、费用、回撤、净超额并报。

**依赖**：已通过R1；P-CHASE-TURN另需QL04。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/reviews/2026-09-19-joint-return-implementation-plan.md#L151)

### QL06 联合收益 R3 组合行业市值中性与尾部暴露

**当前状态**：后置，PIT/风险预算缺口

**剩余动作**：在组合层而非重新残差化score实施风险约束；冻结求解器、精度、排序、基准和不可行处理。

**完成条件**：可行/不可行合成验收；不扩候选票数、不用现金伪装中性；逐臂暴露/尾部/换手/回撤/净超额可复算。

**依赖**：QL05；QL09；风险预算预登记。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/reviews/2026-09-19-joint-return-implementation-plan.md#L162)

### QL07 联合收益 R4 成交敏感性与成本穿透

**当前状态**：跨仓后继未交付；主责 BT

**剩余动作**：在已通过 M-LAG 基线上逐项验证 M-DELAY、M-NOFILL；有证据再做 M-PRICE/M-PARTIAL及组合。

**完成条件**：同signal/hash、完整意图分母、现金守恒、T+1与余量有效期验证；执行差额/费用/实际换手独立归因。

**依赖**：R1同意图配对；费用、公司行动、数量和生命周期合同。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/reviews/2026-09-19-joint-return-implementation-plan.md#L173)

### QL08 联合收益 R5 报告及 R6 后继宿主执行包

**当前状态**：R5尚无拟定脚本；R6最小P-BASE宿主执行已部分完成

**剩余动作**：实现 joint_return_report，固定metric/费用/样本/benchmark与判定标准；优先复用已完成P-BASE台账；后继臂就绪再刷新有限宿主清单及回执。

**完成条件**：fills到NAV/metrics可复算；实现/可比性/收益证据分级；已有窗口不得充作未见盲测；后继包具有输入清单、停止条件与回执。

**依赖**：R1基线已具备；R2/R3/R4只对当次入选臂形成依赖。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/reviews/2026-09-19-joint-return-implementation-plan.md#L184) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/reviews/2026-09-19-joint-return-implementation-plan.md#L195)

### BT-08 TopK #164：剩余过滤/减仓裁决与可复现实验

**当前状态**：唯一 open issue #164。Q5/Q9/Q10 已裁、Q8 仍未固定；Q12 bigvalue / index regime 实现已落。#489 记录 +20.97/+19.98 无法从当前输入重现并降为历史结果；#490 default-on manifest+provenance 已实现。

**剩余动作**：裁定 Q8 的 ST/上市龄/5日涨15% 过滤组合，保留已有默认直到独立研究结果；如继续研究，裁定 dead-cross 部分减仓比例；block/flatten 与 golden 支持不需重写；用新 manifest/hash/qlib calendar stamp 固定完整窗口，做有对照的新研究；历史不可复现收益不再充基准；只在业务确有需要时讨论 vwap×walkdown 等当前拒绝组合。

**完成条件**：未决问题形成选项及真实对照，选定方案的规则/数据/代码身份可复跑；issue 中完成/待裁同步。

**依赖**：MyQuant 分数与过滤 sidecar、冻结 bin/名单/大盘状态、预算与参数决策。

**范围说明**：Q12 与分钟3版本试验已经完成；此线不同于 MQ joint-return R2–R6。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/issues/164) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/topk-joint-research-tracker-2026-09-22.md#L4) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/topk-joint-research-tracker-2026-09-22.md#L435) · [来源4](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/topk-joint-research-tracker-2026-09-22.md#L588) · [来源5](https://github.com/baiyibing/MyQuant-backtrader/pull/490) · [来源6](https://github.com/baiyibing/MyQuant-backtrader/pull/495)

### BT-09 joint-return 后续 R2–R6 与语义 tie-break

**当前状态**：时钟合同重生成 B–G 已收官，NOT_READY_FOR_MODE_B 已解除。P-BASE M-LAG 3631 fills/net +59.1%，Mode B 真湖 M-REF21/M-LAG3631 为已有验收。P-CHASE/weak 仍 INPUT_BLOCKED，M-VWAP/M-NOFILL/M-COST 与 R2–R6 没找到后继实施；G5 只有提案和旧规则锁。

**剩余动作**：与 MyQuant 合并一条任务链：换手/anti-chase、组合风险、成交成本、联合归因、有限执行封装分段完成；共同裁定同分钟同侧资源竞争是否须与 provenance hash 无关；若改合同则版本化，保留旧 pack/seal；每次只冻结一个变化轴并重生成对应输入与证据。

**完成条件**：每一扩展 arm 的真实输入、fill/成本/NAV 归因和完整 seal 可复核；G5 裁决明确保留或替换排序。

**依赖**：按所选研究臂限定：R3 依赖对应 PIT/约束输入；R4 从 R1 开始，不等待 R2/R3；R5 可从 R1 最小 summary 开始；R6 仅纳入当次已交付臂；G5 同分钟资源优先级需先明确合同，不借 symbol/hash 顺序静默裁决。

**范围说明**：已与 qlib_closeout_audit 互证；不要把整个 joint-return 或 Mode B 说成尚未完成。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/handoff-joint-return-clock-regen-2026-09-24.md#L3) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/joint-return-frozen-explicit-price.md#L29) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/g5-jr-semantic-tiebreak-2026-09-28.md#L4) · [来源4](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/g5-jr-semantic-tiebreak-2026-09-28.md#L49)

<a id="p18"></a>

## P18 仍未关闭的live签收条件

### OP10 live签字三件套旧P0承接

**当前状态**：承接SSOT仍OPEN，不能用结构CLOSED或paper GO代替

**剩余动作**：归集修复后R1三实际paper日、A2跨日BUY、A5/G.6去留的分别证据；核当前保留策略与已退役路径；需裁定的旧v4目标按原承接页明确关闭/保留，避免复活旧栈。

**完成条件**：P0-1原SSOT三项都有具名签收或正式修订决定；空窗和离线测试不代签live。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/p0-transferred-live-blockers-2026-09-14.md#L19) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/pull/1028)

### OP11 异机备份和五库恢复演练

**当前状态**：P0-3承接仍OPEN，缺完整双证据

**剩余动作**：确认异机/异盘备份目标与留存；从该副本恢复到隔离目录；执行五库integrity/schema/业务冒烟，记录备份源/恢复过程/耗时与结果。

**完成条件**：每日副本确实可查，恢复源不是同机同盘活动库副本，五库恢复检查均有回执。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/p0-transferred-live-blockers-2026-09-14.md#L29)

### OP12 603556 synthetic-lot结算语义裁决

**当前状态**：P0-5仍OPEN，绿守恒检查不能替代语义裁决

**剩余动作**：基于现有裁决材料确定真实lot不足时采用的硬拒/补账或显式风险接受路径；对所选路径独立红队、直接事件与paper结果签收。

**完成条件**：对应产品语义/风险登记和L3证据完成；不以GREEN_CONSERVED单独关项。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/p0-transferred-live-blockers-2026-09-14.md#L39) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/p0-5-603556-adjudication-brief-2026-09-13.md)

<a id="p19"></a>

## P19 Redis与手续费运行收尾

### OP13 Memurai持久配置与OOM剩余路径

**当前状态**：P0-7 PARTIAL；GAP-3已编码，ops apply和GAP-1/2未闭合

**剩余动作**：核目标机持久maxmemory/noeviction配置，按运维窗口实施与重启复验；不以CONFIG SET冒充持久验收；为qmt_ops无durable重放与check_fills跨重启窗口形成独立设计，保留原超时/结算语义。

**完成条件**：真实服务重启后配置回执、OOM失败可观测和恢复证据齐；GAP-1/2有明确实现或裁决，不因hook完成写整体CLOSED。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/operations/redis-oom-noeviction-runbook.md#L104) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/run-records/2026-09-15-p0-7-memurai-ops-apply-checklist.md)

### OP14 G.25手续费异常运行观察收口

**当前状态**：归因埋点/合理性门已合；根因或观察签收仍OPEN

**剩余动作**：归集9/14以来真实paper fee写入caller及合理性gate结果，识别新异常与历史修复行；复现则锁定写者另片修复；无复现则按原约定决定观察降级，不能只等日期到达自动关闭。

**完成条件**：有当前版本、交易日、日志/库记录关联的观察包及明确结论。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/accepted-risks-registry.md#L409) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/pull/1028)

<a id="p20"></a>

## P20 旧台账与历史目标核销

### OP15 旧运行验收台账核销与结构观察回写

**当前状态**：七条8/31到期pending仍在；部分已退役或被新运行覆盖，需核销

**剩余动作**：逐条核O-CS/O-VB/V9/O-CG/O-MA/SB-P0-1/C6，不因同名V9新任务成功就代替旧SQL锁竞争判据；将仍适用的观察并入下一次paper证据；退役的scale-in机制用退役证据关项，不复活；核#1020独立三日结构观察，并与R1安全soak分开；回写G.31已由#1116修复的基线状态。

**完成条件**：原唯一pending-runtime表逐项有完成/退役/待证据结论；C6真实PARTIAL未发生就保留未触发。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/pending-runtime-acceptance.yaml) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/brief-dual-plan-implementation-audit-2026-09-14.md#L15) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/pull/1116)

### OP18 旧开放数据issue核销

**当前状态**：#34/#37仍开放；问题描述基于旧miniQMT/旧湖布局

**剩余动作**：按现行daqmt与stock/index/etf三树重测相关提取和覆盖，判定仍活跃、已修或已退役；有证据再更新/关闭issue，不按旧14码列表无差别重下，也不复活旧xtdata决策读面。

**完成条件**：两个issue各有当前版本/路径/可复现样例或替代证据和后续处置。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/issues/34) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/issues/37)

### OP19 北斗统计xlsx验收回执

**当前状态**：#1127阈值代码已合；PR真实xlsx验收栏未勾

**剩余动作**：核当前宿主报告是否已按0.6/0.4阈值重生成；无回执时补一次既有脚本验收。

**完成条件**：表头阈值正确，xlsx verify OK，盈利/亏损/无数据总数恒等式成立。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1127)

### OP21 三仓board_limit未知板块口径登记

**当前状态**：BL-001仍在跨仓合同标OPEN，待当前契约核对/裁决

**剩余动作**：核BT未知板块拒绝与1.3既有口径的真实消费边界，确定允许的研究/执行差异并双侧登记；需要行为变更时另片验证边界，不静默选择一个百分比统一三仓。

**完成条件**：已知/未知板块案例、差异理由、消费影响与对应测试形成可追溯合同。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/architecture/f-lake-cross-repo-contract.md#L47)

### QL16 旧 L2 名单晋升线 C/D/E 收口

**当前状态**：A/B已完成；C门槛和D去留待裁定；E回写过时

**剩余动作**：回写1.3 #1024/#1025 A/B已完；判定旧csv_v5研究晋升线是否仍保留；若保留固定C阈值与D纸跑合同，若替代则明确归档；修正路线图“L2未开工”。

**完成条件**：不复活已退役csv-live；旧任务有明确完成/替代/后置结论；晋升门不预填虚假数字。

**依赖**：与当前v653/turtle执行验收定位对齐。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/plan-l2-pipeline-2026-09-13.md#L20) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/plan-three-repo-roadmap-2026-09-12.md#L83) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/pull/1024) · [来源4](https://github.com/baiyibing/OSkhQuant1.3/pull/1025)

### QL17 计划状态回写与旧 CYQ P6 问题核销

**当前状态**：文档漂移；P6是否被后续修复覆盖待证据确认

**剩余动作**：把M3-D blocked/ETF待合/TrackB pending等历史状态加最新终态指针；查9/14同配置topk50明细与summary不一致的原始包是否已被后续分析链替代，给明确归档或复现结论。

**完成条件**：每条旧未完成标记能追到新终态；P6无复现证据时标历史待核，不冒称新现存bug或盲目重跑全部研究。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/plan-midterm-m1m4m2m3-2026-09-13.md#L4) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/plan-etf-qlib-daily-2026-10-14.md#L4) · [来源3](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/reviews/joint-return-v1/track-b/README.md#L3) · [来源4](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/perf-issues-windows-qlib-2026-09-14.md#L86)

<a id="p21"></a>

## P21 继续后置的扩展和重构

### SDD_CLEAN_STOP SDD自动clean-stop与受保护租约释放

**当前状态**：认证分支已合，但生产组合仍capability HOLD；单独后置能力

**剩余动作**：drain/seal、business flush、完整writer inventory、B2/B3外部frontier/残留扫描仍未证明；独立verifier、evidence root/权限隔离与Windows ACL支持未完成；不能由普通退出或超时制造成功释放；是否继续做自动能力需在统一计划单列取舍，当前人工换日清单可继续使用；day-change-in-loop也未接且另案。

**完成条件**：真实受保护证据验证、drain完成和准确owner条件释放，unknown不重试；未支持组合继续HOLD。

**依赖**：L3独立红队与目标Windows/两vendor证据；明确运营收益与范围，避免把自动释放扩成paper首日的额外硬前置。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/pull/1203) · [来源2](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/sdd-single-active-day-slot-2026-10-14.md#L10) · [来源3](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/sdd-day-slot-audit-signoff-2026-10-28.md#L24)

### OP20 结构重构与存储治理后置清单

**当前状态**：v1.10明确DEFERRED，不按旧checklist自动续做

**剩余动作**：P1-4 executor双胖；P1-5 constants；P1-6 MockQMT收窄；P1-7 hkcodex包化；P1-8 tests子包化；P1-9②旧shim清理、③散脚本清理；P2-1 artifacts轮转；P2-2 SQLite备份链；P2-3 L2冷热/停采；P2-4日线读面收敛；P2-5 scripts治理；P2-7 portfolio锁竞争；按现有复现/容量/维护触发条件选择重开；删除/停采先核保留窗与可恢复性。

**完成条件**：每项有保留后置或具名新范围；不因旧plan CLOSED把它们说成已交付，也不自动开大重构。

**证据**：[来源1](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/docs/engineering/plan-repo-industry-alignment-refactor-2026-09-12.md#L200)

### QL14 编号脚本归档与 conftest 路径优先级债

**当前状态**：明确排除/后置的维护项

**剩余动作**：梳理qlib_*.py用途并迁移为清晰入口或归档；随后移除my_tests/conftest.py强制sys.path排序补丁，保持custom_handler导入来源。

**完成条件**：入口/文档引用全齐；无同名模块误导入；CI与本机导入一致。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/pull/100) · [来源2](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/my_tests/conftest.py#L18)

### QL15 工程性能 P2 条件触发后置项

**当前状态**：保留候选，未触发不排实施

**剩余动作**：TTL/磁盘配额仅在重复miss或空间阈值触发时启动；自适应kernels须3类查询稳定>=1.5x且无死锁，默认保持1；内存并行预算/分片pickle以RSS稳定、OOM或大单文件证据触发。

**完成条件**：达到原预登记重提条件后才开片；不盲目增线程、不把合成加速当宿主收益。

**依赖**：宿主性能/资源证据。

**证据**：[来源1](https://github.com/baiyibing/MyQuant/blob/7c428d9bcb66c0dde37ec203a2b5fcc28ac9f1e8/docs/reviews/2026-09-15-qlib-eng-perf-brainstorm/SYNTHESIS-r2-live.md#L36)

### BT-14 B-L2 / δ5 认证级真实来源回执（可后置）

**当前状态**：S1–S5、loaders、单位修复、CLI均已实现。#289把普通研究降到bucket_end/S1声明；halt2160与pool issuer永久stub，现有五个cert pack仍complete=false/NOT_READY。不能把这些高标准认证作为所有普通研究的阻塞。

**剩余动作**：先决定是否仍需要B-L2 R4/δ5 certified；如不需要，明确后置而非不断重复收集无用证明；若需要，给具名window/source/units/provenance重冻S3/S4包，之后独立做真实host验收。

**完成条件**：所选证据等级的完整性和身份可核；普通研究与certified的标签及发布权限分清。

**依赖**：实际研究认证需求、1.3来源/单位/日历事实、独立验收范围。

**范围说明**：不重做已经存在的 participation_rate cap；不把交易所级全生命周期认证强加普通回测。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/note-delta5-real-volume-ingress-2026-09-29.md#L3) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/pull/288) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/pull/289)

### BT-15 minute_orders true-core R3 宿主与 X2–X5 新合同（可后置）

**当前状态**：独立 minute_orders_backend 仍在；R1 CLI/lake、R2 staging、A·X7观察已交付。R3只是host边界登记、参数未裁齐；X2仅提议名冻结、缺live backend_id，X3–X5菜单未实现。

**剩余动作**：按实际需求决定保留/暂缓独立backend；若继续R3，先固定window/symbols/recipe/code/evidence/outroot再验收；X2丰富订单、X3报价路径、X4多账户、X5批量分别订新合同/身份；不借此重写默认CSV引擎；生产写湖归host/1.3，BT不实现writer。

**完成条件**：每一选中的轴单独有合同、oracle、真实证据等级；不选的轴明确后置/取消。

**依赖**：研究需求、R3宿主输入、独立合同批准；X2须具名backend。

**范围说明**：#391已删的是probe bar_scan_exit/minute_true_core_wire，不能误认独立 minute_orders_backend 一并退役；也不应为了补旧清单自动开发四个新引擎轴。

**证据**：[来源1](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/note-true-core-codex-residual-plan-2026-10-02.md#L32) · [来源2](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/note-true-core-x2-richer-orders-contract-freeze-2026-10-03.md#L31) · [来源3](https://github.com/baiyibing/MyQuant-backtrader/blob/418496378ebefc4e707879f9859774b0b8f67284/docs/backtest/industry-state-acceptance-index-2026-09-28.md#L131)
