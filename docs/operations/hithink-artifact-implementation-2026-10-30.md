# Hithink 冻结产物实施合同（PR531 v6）

当前续片：[v2 窗外隔离与真实链路结果](https://github.com/baiyibing/MyQuant-backtrader/blob/codex/hithink-artifact-import-20261030/docs/operations/hithink-artifact-v2-2026-10-30.md)。下文保留首次 v1 实施时的事实与停点；2026-10-30 用户“继续GO”后，显式 v2 导出/导入成功、诊断集经复核为 47 键，剩 D11 覆盖阻断。

状态：2026-10-30 用户“可以开始实施了吗”授权实施；主笔 Codex，本机独立工作区。方案基线 [PR531 @179d0f6](https://github.com/baiyibing/MyQuant-backtrader/blob/179d0f6293514d9c4fec3477fca3ae64d475f68a/docs/operations/plan-corp-actions-hithink-channel-2026-10-29.md)。先完成 1.3 producer，再完成 BT 离线导入；两仓分别提交评审。风险 L2，显式命令触发，默认仍 Wind。无调度、湖发布、经济消费接线或生产开闸。

## 产物协议 v1

- 1.3 命令 `scripts/data/export_hithink_corp_actions.py --universe <txt/csv/parquet> --start YYYY-MM-DD --end YYYY-MM-DD --out-dir <new-dir>`。唯一凭据入口是进程环境变量 `HITHINK_FINANCE_API_KEY`。
- 固定四个文件：`hithink_dump.parquet`、`probes.json`、`manifest.json`、最后提交的 `COMMITTED.json`。提交标记绑定 manifest SHA256，manifest 绑定其余两个文件 SHA256、原始宇宙文件 SHA256、规范代码列表、窗口和实际 fetched_at。完成仅代表取数尝试完整留证，不表示覆盖通过。
- 来源固定 `hithink:market-dumps/adjustment-factors`；manifest 的 `format_version=1`、`producer=OSkhQuant1.3`，端点合同见 [供应商接口](https://fuyao.aicubes.cn/llms-full.txt)。请求参数留证，禁止保存 Key、签名 URL、HTTP 异常原文。目录身份/事件探针只保存经过类型检查的必要字段、HTTP/业务状态和错误类别。
- 未提交的目录不自动覆盖；更换输出目录后重跑。完整目录只在所有绑定校验通过且请求一致时幂等返回。供应商主请求失败不能有完成标记；覆盖探针失败记录为 unknown。
- 每个 dump 缺席代码都有目录检索和窗口事件探针记录。只有 HTTP200、业务 code0、身份准确且事件数组明确为空，才可用作窗口无事件证据；3002 永远不是空事件成功。
- BT `pull --artifact-dir` 验证后导入；同样最后写本地提交标记。`--refresh` 仅在未 assemble 前重新完整导入，旧产物不覆盖到新证据链。完成时重新校验输入及全部文件，防读取期间变化。

## 数据与闸门

- 原始所有列完整相等才能折叠；日期按 Asia/Shanghai，金额以 `Decimal(str(value))` 进入 decimal128(24,12)，非法币种/非有限/负值/无法无损存储即失败。重复原始行位置和计数留证。
- 风险配股独立 sidecar；混合配股和分红阻止候选自动准备。Hithink 日期缺失保持 NULL。A/B/C/D 覆盖从冻结 base 与探针计算，override 有审阅证据、日期有效性和实际 D 类约束；初始配置不带任何人工签名。
- 历史 parity 只做离线诊断：46 个冻结差异事实键集合必须相等，全部实际差异留报告。阈值不代表经济口径可用。
- `gate_rows_for_economics` 显式返回 accepted/blocked/reasons，结构或身份错误整批失败。Hithink 即使日期齐全仍需 revision、事件、字段哈希绑定的公告修订链/股东范围/政策审阅证据；多行同日事件须显式消歧。唯一 loader 校验 manifest 哈希再过闸；不接入当前 economics 消费。固定消费文件集合由静态 fence 锁住。

## 验收与责任

直接证据：producer manifest/marker、导入 state/marker、assembled summary/rights sidecar、parity report、economics blocked 明细。验证主请求和探针失败、孤儿文件、哈希变化、重跑/refresh、全列去重、decimal、未来事件、A/B/C/D、override 日历有效期、跨源代码日期碰撞、旧 Wind 测试、未知 source 与绕闸读入。

设计原则：①②③⑥⑨为离线任务不适用；④通过冻结哈希及提交标记保证重放；⑤所有未知/中断失败关闭；⑦固定跨仓协议；⑧显式 channel 与静态 fence；⑩方案及证据用不可变链接。⑪—㉑未触及交易/通信/实时价格边界，无原则例外。策略买卖通道与时点 N/A。

授权不包含合并/OWNER_SIGNOFF/C3/湖写入/来源切换。独立评审和定向门禁结果在编码后补入本页；上线价值与资金口径仍由人裁。宿主锁：本工作区只处理 PR531 v6 这一个离线产物通道，不并行编码其他方案。

只读预审补充（编码前采纳）：parity 使用 `--run-dir` 与同一覆盖分类函数，历史范围取 base manifest 的 ask_start/ask_end。D 类 override 另需 `scope_start/scope_end` 约束实际缺席事件日期，审批期限不代替事实范围。唯一 economics loader 从 manifest 验证 revision、events SHA 和逐事件字段 SHA；直接 gate 调用未携带已验证上下文时不能凭 sidecar 自述 revision 放行 Hithink。缺 pay_date、正送转缺上市日检查适用于所有来源。fence 只保证登记入口，无任意未来代码安全证明。

Kimi 独立预审（256s，结论可实施）采纳：每次 HTTP 显式 timeout=25s，主下载最多 3 次、每次失败重取签名地址，退避 1/2 秒；每个探针最多 2 次，限流/鉴权错误立即停止该类请求且后续探针留 skipped 证据。限额不称作严格墙钟 SLA（urllib timeout 是 socket 阻塞预算），流式下载另检查 monotonic 总时长 120s 及最大文件 64 MiB。探针失败明确落 D 阻断。重复导入请求一致指原始宇宙文件 SHA、规范代码集与 start/end 全相等。日期测试含 1991 年上海夏令时和 BJ 代码。设计原则条号来源为 1.3 `docs/architecture/design-principles.md`。

评审工具记录：默认 Cursor 模型预检失败，未旁路预检；改跑独立 Kimi CLI 与 Claude CLI。编排器的 Claude CMD 多行参数被截断，该次退出码 0 不计有效意见，使用原生 executable 单行提示重跑。主笔侧独立 Codex 只读预审的三项缺口已在上一段关闭；不将工具退出码代替实质评审。

## 实施与复核结果

实现完成，待草稿 PR 评审。Claude 原生 executable 重跑结论“未发现阻断级合同漏洞，可实施”；Kimi 及两路独立 Codex 复核提出的问题均已修复并加回归：Key/header 异常脱敏、短 request_id 留证及缺 ID 禁 C、公告链禁止多根/分叉、base 日期一致性、别名/动态路径绕闸读取、审批内容/哈希一次读取及末尾复核、候选准备前拒绝覆盖旧 summary。

评审入口：[1.3 producer PR1256](https://github.com/baiyibing/OSkhQuant1.3/pull/1256)、[BT importer PR538](https://github.com/baiyibing/MyQuant-backtrader/pull/538)。[原始意见与收敛记录](https://github.com/baiyibing/MyQuant-backtrader/blob/codex/hithink-artifact-import-20261030/docs/operations/evidence/hithink-artifact-2026-10-30/README.md)统一保存在 BT。

- 1.3：29 项离线测试通过；定向 pyright 0 errors/0 warnings；ruff 通过。验证命令使用 vanna312 显式解释器，`pytest --noconftest -o addopts= tests/test_hithink_corp_actions_export.py`（该隔离测试不需要交易栈 conftest）。
- BT：108 项定向测试通过；原 Wind 符号链接测试在本机缺 Windows 创建 symlink 权限，单独排除，CI 仍保留原测试。`pytest --noconftest --basetemp <short-temp> tests/test_hithink_incremental.py tests/test_corp_actions_economics_gate.py tests/test_corp_actions_incremental_driver.py -k 'not output_symlink_escape'`。本仓 conftest 强制长的 repo-local 临时路径，独立工作区下会超过 Windows 路径限制，故这批不加载它。
- BT 定向 pyright 使用与原配置同为 basic 的临时配置，只补仓库根的 import path（原配置将 scripts/tests 各自作为 root，直接命令产生 missing-import warnings）；8 个修改/新增 Python 文件最终 0 errors/0 warnings。ruff 通过。
- 路径/模块契约 4 门、book admission、baseline admission、新 economics fence 共 7 门退出码均为 0；fence 已接入 CI 的 data-free 阶段。
- 真正的跨仓合成串联：1.3 export → BT import → assemble → prepare-merge，新增 1 条 fixture 事件，候选 economics_ready=false，基线未改写。测试在独立目录，不伪装成市场湖。

真实 API 请求已完成下载并进入生产校验：57,709 行，SHA256 `668ad6cacd8972f6991995c7625d545393e01d3de76cc5d8c2c6a90254991ad3`。出口码 2，未生成 COMMITTED；负值为 000887.SZ / 2007-03-30 / bonus -0.67335 与 600381.SH / 2014-06-27 / bonus -0.87581。保持 v6 的整包非负规则；窗外隔离的可选变更尚未收到答复，不预先实现。

冻结旧输入的 Decimal 复算为 47 个阈值差异，原 46 键（cash 10 + bonus 36）仍原样保留。新增 `300708.SZ / 2020-06-02 / cash / 0.0199 / 0.02` 恰等于 1e-4，旧浮点比较漏计。新闸门明确失败，不扩大容差或自行增加批准项。四源旧研究不因此视作经济账验收。

技术债/剩余审阅：真实包异常处理和新增差异事实需独立裁定；当前采集失败不能交给 BT 正式导入。没有湖写入、发布器、C3、OWNER_SIGNOFF、CNINFO parser/policy 修改或消费切源。三问结论：职责边界只穿过冻结文件；失败不产生成功标记；时间/宇宙/哈希及审批有效期可重放并留证。
