# 已合实现进展：QL11 写边界与 QL17 状态指针

MyQuant #118、#119 已分别在固定提交 Grok CLI（显式 grok-4.7）复核 APPROVE、各三项规范 CI 通过后合入；两项的受测树与实际合入树均相同，详见 github-facts.json。

QL11：分钟 provider、staging、派生 full staging 及 receipt 在任何写入前检查与日频 provider 的解析后同根和双向包含关系；receipt 写前再次检查。原来的真实 staging 污染和 receipt 覆盖日历漏洞仅在一次性沙盒复现/修复，没有刷新或推广实际 provider。
本机完整套件 588 passed、7 skipped、18 subtests passed、1 条既有 SyntaxWarning；规范 Linux 同为 588/7/18、47 条 warning。两组七项跳过不同：Windows 为六项目录链接权限不足及一项缺宇宙，Linux 为六项 Windows 大小写平台跳过及一项缺宇宙。595 个远端进度标记与同提交收集顺序对齐，六项目录链接用例通过。源复核逐字文本里的能力跳过/待 CI 句子属于较早的本机输入；当前 Linux 事实单独标注，不重写源引用。

QL17：三页仅追加当前状态指针，原正文、ETF 页、研究戳和生产默认保留。M3-D/Track B 只确认已有实现合入；P6 仍是仓内追踪范围的历史待核，不宣称原包丢失、当前故障或已修，也不代签宿主性能和独立历史研究复核。

本片只追加 P12/QL11 和 P20/QL17 各一条 implementation_ref，没有 audit_items 或 package 关闭回执。QL11 的实际部署/刷新、P12、QL17 及 P20 整项均保持开放；冻结 64 条记录、21 包及全部旧引用/回执保持。已关闭 QL12/QL13 和 BT #555 的 QL10 回执不重复计工。
没有真实 provider、行情湖、QMT、生产 Redis、交易启动或默认行为推广。源提交中的较早 pending 快照保持，当前合入/复核/CI 由本片补记。
