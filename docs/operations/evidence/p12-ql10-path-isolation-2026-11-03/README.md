# P12 / QL10：日频刷新路径隔离实现回执

[MyQuant #117](https://github.com/baiyibing/MyQuant/pull/117)已合入，固定 head `1f7688a5508f74fa506226f5367da9e1cf507a95` 经 Grok CLI（显式 grok-4.7，实际 grok-4.7-build）复核 APPROVE，规范 CI 三项全部通过。受测树与合入树同为 `9c88cf1b8744fe2e2efecd439880f306c9654094`。

旧入口允许 new 输出与现有 provider 同根，wipe 随后会删除 provider。实现现在在 CLI、清理和 swap 的破坏性步骤之前拒绝解析后同根、祖先或子孙路径；保护 live/archive/CSV/index/显式 SOURCE，合法同前缀兄弟目录保留。没有执行真实 provider 刷新或推广。

同一提交的本机完整 CI 命令为 557 passed、4 skipped、18 subtests passed，1 条既有 custom_utils SyntaxWarning；GitHub Linux 全套同为 557/4/18，45 条 warning 如实单列。
两套四项跳过的组成分开记录：本机 Windows 为三项目录链接权限不足及一项缺 my_data 宇宙；规范 Linux 为三项 Windows 大小写平台跳过及一项缺 my_data 宇宙，三项目录链接实际通过。implementation-review.json 的逐字源复核结论来自较早的本机 Windows 快照，其中“链接能力跳过”一句只描述该本机输入；后附的 Linux 结果不改写这段历史引用。

Linux 的 561 个进度标记与相同提交的完整收集顺序对齐：四个跳过恰为缺 my_data 宇宙的一项及三项 Windows 大小写用例，validate/wipe/swap 三种真实目录链接用例均对应通过。原始日志哈希、归一 nodeid 映射见 JSON。复核者未执行宿主测试。

源仓 acceptance.json 保留提交时 147 个相关测试通过、远端尚待的真实快照；完整套件与合入事实由本片补记，不重写旧证据。
这里只追加一条 implementation_ref，QL10 的实际日频刷新现场条件和 P12 整包仍开放；没有新增 audit_items/package 关闭回执。已关闭的 QL12/QL13 不重复计工。
冻结 64 条记录、21 包映射及全部旧回执/引用保持。source-references.json 指向固定源 head 的计划、复核与基线；不代签其他宿主、默认 provider 部署、行情湖质量或首个 paper 日。
