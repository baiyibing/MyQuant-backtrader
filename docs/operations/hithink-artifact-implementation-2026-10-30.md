# Hithink 冻结产物实施合同（PR531 v6）

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
