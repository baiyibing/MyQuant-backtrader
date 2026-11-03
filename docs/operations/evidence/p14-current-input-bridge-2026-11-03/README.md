# P14 同市场输入的16格验收与旧数据issue只读核查

新industry八格通过，与已归档legacy八格的完整市场输入字段一致；代码变化仅在docs。
输入桥接只归一化仓库/湖根路径，不删字段或哈希。两个worktree/私有workspace身份保留，不声称同一执行环境。
每种规则内比较native和L1，不主张跨规则或跨家族收益相等。正常、低资金、无效配置、坏输出路径均由既有harness验证实际触发。
industry正常CSV584行、v7 613行；正常/低资金格的交易、净值及执行审计文件native/L1逐字节一致。
原legacy回执见consumer-host-2026-11-03/p14；本片result、recipe、逐格comparison及桥接检查均归档。
P14/BT-07仍开放：旧#108 Slice D迁移前同窗宿主基线、价格/原因对照未补签。没有经济真值/策略准入签收。

P20/OP18及#34/#37仍开放。#34按现行三树核对旧14码：10只股票none/front都有非空数据，back仍缺10只；指数有index/raw，3只ETF有etf none/front，ETF back缺失保留独立覆盖问题。
只证明非空覆盖，不证明价格/因子/最新日或全市场质量；27个选定文件复读哈希未变。
#37的旧转置机制已在a039609b改成标准gateway/extractor，当前773c6260版本45项既有离线测试通过；尚无适用在线宿主/vendor签收，不复活决策路径xtdata日线。
两段只读审计源位于audit-sources，需显式路径参数；湖由现行resolver/环境解析，不猜盘符。

冻结64条items、21包映射、原关闭回执不改，只追加P14/P20的2条implementation_refs；没有新条目/整包关闭。
P02另外由1.3#1275及FullSweep41615284944处理，本片不代签OP16或现场验收。
未写行情湖、登录QMT、操作生产Redis、切换运行时、启动paper/live或推广默认provider。

公开JSON宿主根路径脱敏；raw-record-hashes保存原始记录哈希，recipe_sha256仍指原运行配方。
publication-sha256对Git发布的UTF-8 LF字节计哈希，两种字节域不能混用。独立Grok CLI复核见关联PR。
