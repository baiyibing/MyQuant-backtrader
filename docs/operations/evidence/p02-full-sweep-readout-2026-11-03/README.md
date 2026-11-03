# Full Sweep 通过实证与 Linux runner 阻塞回执

[实际FullSweep41615284944](https://github.com/baiyibing/OSkhQuant1.3/actions/runs/41615284944)已成功：934文件/13分块，11788 passed、101 skipped、35 deselected、0 failed；0新增/0持续失败，全部分块首轮通过。
它运行于#1275固定feature head4d421edd60，尚不是默认分支合入签收。
最初run41557432402加载134历史并有1条竞价时钟测试失败，#1274修复后消失；前轮run41607070691加载135历史，暴露14条SHM fake maxlen参数失败，写出149历史。
本轮实际从缓存加载149条，全部first-seen日期保留，前轮14条不再失败；132/130种子加入0条、修正0日期，不能靠种子解释这14条的保留。
原始/前轮/当前报告、恢复来源、前后149条历史归档，audit-sources/verify_history_pair.py可无湖复核。

前轮失败chunk和lf_retry日志、flaky ledger已下载；本轮13份chunk日志均已下载。
干净首轮通过时run_full_test_sweep.py不会调用_append_flaky_ledger，所以本轮无ledger文件是预期；current/ledger-status.json记真实缺席，不伪造空ledger。
恢复记录里的cache_persistence_verified保留准备阶段原值false，实际缓存149及全日期对照才是这里的恢复证据。

#1275的GrokCLI复核APPROVE、113项相关本地测试及Windows公共门禁通过，但Linux PR门禁仍红：
首次公共pytest子进程退出247且未见pytest断言；仅一次同SHA失败job重跑后，GitHub确认linux-ci-02与服务器失联，第二次日志不可下载。
linux-runner-block.json保留三个job/annotation/原日志哈希；不把未知CPU/内存/网络原因写成已确认OOM，不关闭/跳过任何检查。
运维说明grok-bot-ops/docs/bot-vm/linux-vm-grokbot-ci.md:21明确VM无公网入站，Windows不能SSH直连，须持有VM的Bot/Computer恢复。已请求用户提供/恢复该入口；未向其他bot发消息，也未盲目第三次重跑。

因此#1275仍OPEN，不合入；OP16/P02均OPEN。本片只追加1条implementation_ref，没有新条目/整包关闭。
源PR实际规范CI全绿并合入后，再单独追加OP16audit_items关闭回执。三仓主分支protected=false快照单列，Owner治理仍待完成。
较早#1274复核为ClaudeCLI当时配置的GLM，用户后来指定GrokCLI，本轮#1275与本回执采用显式grok-4.7，最终文本/实际模型按各PR记录。

冻结64条items、21包映射、全部旧回执/refs保持；P14/P20证据已另于BT#553合入，不重复追加。
M5模拟SDK指纹、首个paper交易日、实湖质量、P14旧SliceD和旧issue等未代签。没有行情湖写入、QMT登录、生产Redis操作、运行时切换、交易启动或默认provider推广。
公开history_path脱敏；raw-record-hashes为原字节，publication-sha256为Git发布UTF-8 LF字节。
