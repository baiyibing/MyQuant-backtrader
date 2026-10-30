# PR531 v6 实施审阅证据

这些是取证和评审记录，不是经济口径或湖发布签字。

续片当前证据：[v2 真实运行](v2-real-run.json)、[D11 事实复核](v2-coverage-review.json)、[第 47 键原始记录核对](decimal-boundary-review.json)。以下首次 v1 记录保留为历史；v2 的两条隔离边界与诊断扩充不改变经济审批状态。

公告续查：[三个身份事件](coverage-identity-facts.json)、[八码报告期不分配文件](coverage-period-facts.json)、[31 个历史缺失键关联](coverage-historical-gaps.json)。11 份本地 PDF 的 SHA256 已复核，只归档链接、事实和页码；PDF 不入仓。详见 [D11 后续处理](../../hithink-coverage-followup-2026-10-30.md)。这些文件不被导入器当作覆盖放行或签字输入。

独立只读复核确认报告期、提案状态、页码、哈希和 7+11+13 历史键关联一致；已将换股证据措辞收紧为“公告实施安排”，不声称已核实转换登记完成。没有把窗口内摘牌归 A，也没有把报告期不分配归 C。

- [Kimi 原始设计评审](design-kimi.md)：CLI `kimi-code/k3`，256 秒。包含编排器原提示和实质意见；timeout/重试、短签名重取等已采纳。
- [Claude CLI 重跑原始结果](design-claude-cli.txt)：原生 executable；沿用本机配置的模型 `glm-5.3[1m]`，未改模型 pin。最初 CMD 包装器截断多行提示，该次退出 0 未当作有效意见；重跑明确读取合同和 v6 原方案，结论可实施。
- [真实导出证据](real-export.json)：2026-10-30 实际 API 下载的行数、哈希、两条负值和拒绝结果。没有凭据、签名 URL 或原始数据文件。
- [冻结输入诊断](pinned-input-diagnostic.json)：2026-10-29 旧 dump 的复算结果；严格 Decimal 阈值比原 46 键多一项，不修改冻结清单。

独立 Codex 实施复核的最终收敛记录（对话原件保留在执行线程）：

| 发现 | 修复与验证 |
|---|---|
| CR/LF 或 Unicode Key 可能进入 ValueError 原文 | 入口可打印 ASCII 检查、transport 异常固定类别；无 Key 回显回归 |
| 公告链允许多个根/分叉 | 只接受首根 + 逐项 supersedes 前项；分叉/多根被 blocked |
| 维护模块别名及变量路径 reader 可绕过 fence | 拼接 module/alias、只准直接导入唯一 loader；登记现有两处 reader 表达式和数量 |
| 审批旧内容可能绑定新哈希 | 字节快照一次读取、覆盖/parity 复用、结束复核；并发修改反例通过 |
| 再 prepare 先改 summary 再发现旧候选 | 准备及 assemble 入口前置不可变检查；旧 summary/events 哈希不变 |
| base 日期一致性、request_id 留证不足 | 全源日期关系检查；短 ID 安全保留，缺 ID 不能归 C |

经济/覆盖复核最终结论：前述 4 项均修复，限定范围内未发现新阻断。产物边界复核最后一项 request_id 接线也已修复并有回归。合成跨仓 export/import/assemble/prepare 已通过；真实数据仍因严格负值规则受阻。详见[实施记录](../../hithink-artifact-implementation-2026-10-30.md)。
