# 四仓分界、代码迁出与 pandas 3.0.6 工作总结

状态截止：**2026-11-10 14:46（北京时间）**。范围为本轮四仓分界收口、共享因子/ops 工具迁出、pandas 升级和验证修复，不代表所有历史 backlog 已完成。PR 状态和当前源提交 CI 取自本次重新读取的 [GitHub 快照](evidence/quant-work-summary-20261110/github-snapshot.json)；后续变化以对应 PR 为准。

## 1. 当前结论

BT 已删除本轮已迁出的 infra、ops 与公共因子实现，消费公共接口，不保留缺依赖时启用的本地算法。MyQuant 不反向依赖 BT 计算因子。回测专用名单仍由 BT 组织，这是已确认的职责，不是迁出欠账。

四仓的精确 `pandas==3.0.6` 升级提交均已交付，本机实际版本也已升级；**不能宣称四仓主分支已全部合入**：MyQuant #142、infra #100 仍待合并。1.3 pandas/Windows、GBK 修复，以及 MyQuant TR 桥/BT 消费更新已合入。

本次核对的 8 个近期 PR 均无失败或待运行检查；其中信息性 coverage、Gitea 专用 probe 有配置性跳过。**本机 SDK 严格审计仍失败，1.3 公共因子接线仍未实施，真实交易栈也未作发布签字。** CI 通过不能替代这些结论。

## 2. 已完成什么

### 2.1 分界与迁出

| 事项 | 已完成的结果 | 依据 |
| --- | --- | --- |
| 四仓分界 | MyQuant 管因子研究、计算实验、效果验证、Qlib 训练及研究/模型信号；infra 管采集、清洗、聚合和公共数据产制；BT 管策略研究、实验输入和成交/收益回测；1.3 管执行及真栈验收。MyQuant 保留完整 Qlib 研究能力 | [infra #92](https://github.com/baiyibing/MyQuant-infra/pull/92)、[分界正本](https://github.com/baiyibing/MyQuant-infra/blob/main/docs/architecture/boundary.md) |
| infra 消费收口 | L2 加工、湖写入/修复、vendor 处理、Store IO、公共契约等调用 infra；BT 只保留 import 转发及宿主路径、配置、reader 生命周期、时效/研究门禁。缺依赖明确失败 | [BT #587](https://github.com/baiyibing/MyQuant-backtrader/pull/587)、[消费边界复核](ops-runtime-consumer-20261109.md) |
| ops 通用评审/发布工具迁出 | 模型目录、命令构造、重试、进程/输出收集和发布实现归 ops。BT 删除通用实现，保留三个薄入口和领域配置；显式指定 ops 根，无本地兜底 | [ops #187](https://github.com/baiyibing/grok-bot-ops/pull/187)、[BT 消费记录](ops-runtime-consumer-20261109.md) |
| 公共因子迁入 MyQuant | 筹码/TR、价格带、周线背离、Rust crate 及通用研究工具迁入 `myquant_factors`；BT 只转发，边界 gate 阻止恢复本地实现、Notebook 或 Rust crate | [MyQuant #139](https://github.com/baiyibing/MyQuant/pull/139)、[BT #589](https://github.com/baiyibing/MyQuant-backtrader/pull/589)、[迁移清单](factor-owner-migration-20261109.md) |
| 旧 Qlib 样例与 Notebook | `qlib_workflow.py`、`factor_expr.py` 和唯一历史 Notebook 调用方一并迁到 MyQuant，修正 `scr.*` 导入及环境路径；不再从 BT 源码计算因子 | [MyQuant #139](https://github.com/baiyibing/MyQuant/pull/139) |
| 共享包可用性 | 公共入口按能力加载，轻量入口不预加载 Qlib/绘图研究栈；显式 EXE 配置无效时失败；BT 固定不可变 MyQuant 提交 | [共享因子审计](shared-factor-source-audit-20261109.md)、[requirements-factors.txt](../../requirements-factors.txt) |

同口径因子计算通过同一组件复用，不在各仓复制实现。同一组件内的参考/Rust/Numba 后端可以共存，但须共用合同并对拍。因子是否归 infra 按数据供应职责判断，不以“成熟”或消费者数量自动迁移。

### 2.2 pandas、验证环境与 Windows 问题

- MyQuant requirements/包 metadata、infra 的 14 个 pandas extras 提交精确 3.0.6；BT 根依赖及 `qlib_cost` 原已钉 3.0.6；1.3 runtime 从 2.3.3 升至 3.0.6。历史 vendor/冻结 wheelhouse/旧回归收据保留原始版本，不冒充当前安装声明。
- 修复 1.3 三份数据工具的四处 ns/us/ms 转换，显式转为毫秒单位后取整数，保留时区和区间合同。新增独立固定 epoch 回归在原实现为 7 failed / 4 passed，修复后受影响完整文件 20 passed。
- 共享本机 vanna312 的 pandas 已为 3.0.6，`pip check` 通过。全部 runtime/dev pins 与固定 infra `4a4914f` 的齐套验证在独立环境完成，不将此结论扩大为“所有开发机全部包都已对齐”。未发现阻止升级的其他包兼容冲突。
- CI 各 pandas 消费 job 断言真实版本；Linux 使用已核验的 `pandas-3.0.6` 能力节点。linux-ci-03 在 job 外升级并恢复路由；self-hosted job 不执行 pip。未核验的节点不冒充 3.0.6 验收。
- 私有 infra 的读取权限已由实际 CI 安装和测试证明可用，已不再是这条流水线的待指定阻塞。凭据只在安装步骤使用，不写入文档、Git URL 或共享依赖缓存。
- Windows 编码、换行/指纹、符号链接权限、临时目录分别处理：MyQuant 两个测试文件显式 UTF-8；集成 1.3 主线 junction 路径保护与 front fixture 根隔离；验证目录放在临时工作区。没有统一归为“环境失败”。
- Windows common 原 1800s 预算在 208 文件推进至 87% 后终止，不能计通过。集成主线四批执行，共享一个 2700s 截止点；Linux 单进程也按主线 2700s，common 合并外层两平台 4500s，其他入口保留 1800s。部分 `passed` 输出仍不能接受超时，业务 TIMEOUT 不变。
- GBK 下知识库 CLI 打印状态符号会崩溃，已在 CLI 入口用 `backslashreplace` 保留调用方编码；UTF-8 保留原字符，导入路径不改流。[1.3 #1353](https://github.com/baiyibing/OSkhQuant1.3/pull/1353) 已合入。

### 2.3 共享 TR 桥的后续修复

共享 CLI 原来把固定 `_turnover_resist_<date>.csv` 写入输入数据目录且不清理，同日并发也会共用文件。已在 MyQuant 单源改为独立临时目录，成功、非零退出、超时及解析异常均清理；临时根位于输入目录时，在任何探测写入之前拒绝。

独立复核发现 `tempfile.gettempdir()` 首次调用本身会写探测文件，故进一步改为先只读核验候选目录。fresh 子进程审计监测 `open` 写标志与 `mkdir`，验证 env/cache 两种湖内临时根都零写入。原公开参数、UTF-8/BOM 和错误传播合同保留。

[MyQuant #143](https://github.com/baiyibing/MyQuant/pull/143) 与 [BT #590](https://github.com/baiyibing/MyQuant-backtrader/pull/590) 已合入；BT 当前固定 `910a7c028ac74930cba44f95c18fe97030779e02`。该升级还继承已合 MyQuant #141 的 Qlib 窗口预热/缺失值日期对齐修复，已明确披露；BT 只有该模块转发，现行 CSV 策略不直接调用。Rust 和其他数值核未变。

## 3. 已验证到什么程度

以下计数绑定列出的源提交，不能替换成别的 head，也不能合计成一次全仓/全平台验收。当前各 PR 检查状态另见快照。

| 验证对象 | 源提交 | 实际结果/限制 |
| --- | --- | --- |
| MyQuant pandas 钉版 | `528a6533fd`，[#142](https://github.com/baiyibing/MyQuant/pull/142) | CI 847 passed / 2 skipped / 18 subtests |
| infra pandas 钉版 | `94bde81f44`，[#100](https://github.com/baiyibing/MyQuant-infra/pull/100) | CI 4738 passed / 15 skipped |
| 1.3 pandas 与主线集成 | `c5d11f81ec`，[#1336](https://github.com/baiyibing/OSkhQuant1.3/pull/1336) | 21 success / 1 信息性 coverage skipped；Windows common 四批完整 208 文件合计 4237 passed / 55 skipped，Linux 4219 passed / 73 skipped；两边真实 pandas 均 3.0.6 |
| 1.3 目标环境/时间合同 | 同 #1336 实施收据 | 全部声明依赖 + 原固定 infra：95 文件 1531 passed / 3 skipped；3 项缺真实复权文件。hosted Windows/Linux 时间合同、远端全量 Pyright 通过 |
| Qlib/LightGBM 兼容 | #1336 实施收据 | 固定 Qlib 的合成训练 100 行输入、20 个有限预测，原 NaN 保留；不是市场数据效果验收 |
| MyQuant TR 桥 | `910a7c028a`，[#143](https://github.com/baiyibing/MyQuant/pull/143) | CI 854 passed / 2 skipped / 18 subtests；桥两完整文件本地 17 passed / 1 未构建 Rust 可执行文件的 skip |
| BT 新共享因子 pin | `c1278ac2c9`，[#590](https://github.com/baiyibing/MyQuant-backtrader/pull/590) | CI 9927 passed / 85 skipped / 21 deselected（配置排除 production/benchmark）；本地七个完整消费文件 67 passed、六项边界 gate 通过；未重录 golden |
| GBK CLI | `9dc2310623`，[#1353](https://github.com/baiyibing/OSkhQuant1.3/pull/1353) | 5 个真实子进程/导入回归通过；CI 18 success / 1 信息性 coverage skipped |
| ops Windows 评审进程 | `2335329fc5`，[#200](https://github.com/baiyibing/grok-bot-ops/pull/200) | 本地 28 runtime + 8 workflow 用例通过；最新 GitHub 检查为 1 success / 2 Gitea 专用 probe skipped，不写成三项都执行成功 |
| 1.3 因子接线方案 | `d55a9036e1`，[#1355](https://github.com/baiyibing/OSkhQuant1.3/pull/1355) | 9 项检查通过，4956 份文档索引已重建；这是方案/基线验证，不是接线代码验收 |

公共 TR BB/分类另有 56 组、注入复权乘数另有 16 组合成对拍一致；它们没有验证真实 reader、时效政策、QMT 会话或交易接线。原补充本地 common 超时和本地可选类型依赖缺失均未计通过。

## 4. 没有完成什么，为什么

| 未完成项 | 当前已经做到哪一步 | 没有继续实施的具体原因 | 后续条件 |
| --- | --- | --- | --- |
| MyQuant/infra 的 pandas 主分支全部合入 | #142/#100 已提交，当前 CI 无失败，仍 open | 升级交付不等于 PR 已合并；本轮未代替仓库审阅流程作合并决定 | 对应 PR 完成审阅/合并；不能仅凭提交完成就宣称四仓主分支统一 |
| ops Windows 运行时修复合入 | 通用工具迁出 #187 已合；修复 #200 已实现、验证，仍 open | 共享运行时修复还在 PR 审阅阶段 | 审阅/合并 #200；不能将传输修复等同所有外部模型服务可用 |
| 1.3 四模块因子去重接线 | 已盘点 bands、paths、adj_factor、TR bridge，并提交 docs-only draft #1355；暂留的源副本已明确列出 | wiring 直接依赖异常身份、实际 cache、水位与上一交易日；盲换 import 会改变行为。仓库要求 L2/L3 方案评审和明确代码 GO，当前没有该计划的正式实施批准 | 按 #1355 完成评审/GO 后连续实施 A→B→C；不能宣称四仓因子副本已全部清除 |
| 共享 metadata-reader 注入端口 | 已识别并列入 #1355 接收仓前置；TR 临时输出前置已由 #143 完成 | 旧共享 adj_factor 无条件导入 infra；1.3 原 reader 在无 sidecar 时可无需 infra。直接迁入可能新增缺包异常，并被 wiring 泛异常路径接住后回落 raw price | 在 MyQuant 增加经评审的 reader 端口、固定新提交，验证无 sidecar/无 infra、异常身份、cache reset 与精确热路径 gate；不能在 1.3 复制算法绕过 |
| 本机 QMT SDK 严格审计全绿 | 已核对源码、签名/PE 版本及 native 文件名，准备 [#1341](https://github.com/baiyibing/OSkhQuant1.3/issues/1341) 维护步骤 | 模拟客户端指纹 `335d392206100f4746121c5c3d08eafa`，canonical/冻结基线 `55b83dace545a4b96ce6edbf82e5440b`；三个文件统一换行后仍不同。没有已核验的、供应商支持的整套目标发行物，也没有本次维护窗口批准 | 可信发行物、来源/checksum、ABI/回滚核验及受控维护；之后重跑严格 gate 和 merge 总入口。当前 exit=1 仍是事实 |
| Notebook 历史图表和真实因子/收益效果验收 | 迁移并保留 57 个历史输出、标记历史图表；做了结构、导入、数值及合成训练验证 | 代码迁移和兼容验证不是重新训练或市场表现研究；历史输出不能当当前实验结果 | 明确真实数据根、数据/时间窗口及实验计划后另验；本轮未执行真实湖产制、名单发布或新收益实验 |
| 所有 CI 节点/所有开发环境整套升级 | 本机 pandas、独立齐套验证环境、linux-ci-03 已维护，linux-vm 已有 3.0.6 实测；消费 job 有版本断言和能力标签 | 其他节点未取得本轮完整版本/维护收据；不能拿另一台 smoke 或标签猜实际版本。`pip check` 也不证明每个仓库的全部精确 pin 匹配 | 逐机核验，在 job 外维护并复验再授标签；不在 self-hosted job 中自愈装包 |
| 所有外部模型评审席成功 | pandas 有有效 Kimi 评审及独立只读复核，其他失败记录已保留 | 部分席配额/服务拒绝、模型不可识别或超时；未继续追加付费重试、未经批准改模型钉，也没有将同族只读复核当外部多模型一致 | 按 ops RACI 恢复相应服务/配置后补评审；服务失败不是 pandas 包不兼容证据 |
| 共享桥完整 Pyright 零诊断 | 新/受影响两测试文件 0 error；桥模块与原源对照均为 13 项既有 pandas 类型诊断，无新增 | 本轮修复临时文件生命周期，没有同时重写原计算函数的类型声明；不能把局部类型检查扩大为整个 SDK 零诊断 | 在单独类型收口中处理并保留计算/索引合同；此项不作为新缺陷或已解决来上报 |
| paper/live 发布与真实栈签字 | 已有离线契约、MockQMT 相关回归和上述 CI 证据 | 当前工作范围是归属、复用和依赖兼容；SDK 严格审计及接线审批仍有明确缺口，未取得运行期开闸授权 | 另行运行时验收和签字；不能以 CI 绿灯代替生产批准 |

1.3 的流程依据是其 [AGENTS](https://github.com/baiyibing/OSkhQuant1.3/blob/87fd35a9059fb5e94bce43556ac284e8096e7507/AGENTS.md) 与 [AI 产码 DoD §3](https://github.com/baiyibing/OSkhQuant1.3/blob/87fd35a9059fb5e94bce43556ac284e8096e7507/docs/engineering/ai-code-review-governance.md)：L2/L3 **“plan + multi-AI + GO 前禁编码”**，运行期开闸另签。不是把普通已授权修复再次列为逐文件请示。

SDK 默认 CLI 的 `vendor=None` 严格检查也是既有明示合同。部署 startup/preflight 可按明确解析的 vendor 使用现有 capability 政策；不能让 common/merge 猜测部署 vendor 来掩盖严格审计失败。本轮没有重写信任基线、设 SKIP、跨 ABI 复制 SDK 或重启客户端。

## 5. 有意保留、不是欠账的内容

- 策略 9/10/11/13、App ∩ Qlib TopK 的条件组合、参数、D→T 映射及 CSV/manifest 导出留在 BT。Human 已明确同意；名单不必全部来自 MyQuant，公共计算仍复用同一个组件。
- BT 的成交模拟、费用、持仓、收益及研究门禁继续留在 BT；infra 的 IO/产制和 1.3 的交易政策没有因去重被挪到共享算法层。
- 历史证据、冻结 wheelhouse/vendor 版本记录及财务 golden 保持历史身份，没有为了绿色结果重写或重录。源实现的 archive/vendor 副本不在 BT 留存。
- 策略书默认值、订单/账本、QMT 会话与真实市场数据供应没有在本轮顺手改动。代码边界收口不构成新策略或默认执行行为的授权。

## 6. PR 状态索引

| PR | 截止快照状态 | 本轮含义 |
| --- | --- | --- |
| [MyQuant #142](https://github.com/baiyibing/MyQuant/pull/142) | open，3 success | pandas 精确钉版待合 |
| [infra #100](https://github.com/baiyibing/MyQuant-infra/pull/100) | open，2 success | pandas 精确钉版待合 |
| [ops #200](https://github.com/baiyibing/grok-bot-ops/pull/200) | open，1 success / 2 skipped | Windows 长提示词及进程清理修复待合 |
| [MyQuant #143](https://github.com/baiyibing/MyQuant/pull/143) | merged，3 success | TR 临时文件单源修复已合 |
| [BT #590](https://github.com/baiyibing/MyQuant-backtrader/pull/590) | merged，1 success | 新共享因子 pin 已消费并合入 |
| [1.3 #1336](https://github.com/baiyibing/OSkhQuant1.3/pull/1336) | merged，21 success / 1 skipped | pandas/时间单位/Windows 验证修复已合 |
| [1.3 #1353](https://github.com/baiyibing/OSkhQuant1.3/pull/1353) | merged，18 success / 1 skipped | GBK CLI 修复已合 |
| [1.3 #1355](https://github.com/baiyibing/OSkhQuant1.3/pull/1355) | draft open，9 success | 方案可评审，未实施/未获代码 GO |

更早的 infra/ops/因子迁移 PR 合入状态也保存在快照中；这些历史项本次只刷新 PR 元数据，没有重新采集其 CI，因此不能把缺少 `checks` 字段读成“零测试”。本总结及证据文件只增加工作记录，不代替分界正本、接线计划或发布签字。
