• 我先看下审计目录的快照结构，然后按疑点抽查。

• 按我的评审侧重，动手核一下 180s 协作取消的真实代码行为（docstring 不可信），看 cancel 置位后在途 job 的实际走向。

• # 评审结论

  ## 总体判断

  **无阻塞性问题。** 我按疑点逐条回到冻结快照（`oskh`/`qlib`/`bt` 各自 head.json 钉的 SHA，经 cache.git `git show` 读取）核对，计划与明细中的关键事实性主张均与代码/记录一致，未发现把已有实现误写为欠账、把已取消路径复活、或把明确后置项重新提升为硬门槛的情况。21 包的归口、次序和前置关系自洽。

  抽查验证过的关键点：

  - **BT-18 验收器漂移属实**（非误报欠账）：冻结 SHA `41849637` 的 `verify_run_protocol_lake_parity.py` `native_argv` 确实不传 `--rule-profile`，low_cash 格仍要求 `InsufficientCashError`；而 `csv_minute_backtest.py:1393` 默认 `rule_profile="industry"`。0C 修验收器不需动引擎，定性正确。
  - **SHM 180s 定位准确**：我直接读了 `daqmt_shim_v1_36.py` 源码（不信 docstring）：`_mm_safe_step`/` _dl_safe_step` 中 `>180.0` 仅置协作 `cancel=True` 标志（:1744/:2194），在逐只代码之间检查，在途单只同步下载不可抢占，`MM_BUDGET_S` 时间片后让出——与「取消请求≠解锁 SLA」的口径完全一致。10/24 探针记录证实真机 job 5–45s 先完成、未测到 180s，故「已实现、真机未证、继续后置」是准确描述，计划没有把它写完成也没有提升为首日硬门槛。
  - **P07 拆包覆盖真实缺口**：`stop_turtle_paper_procs.py:84-85` 默认连 `ops_scheduler daemon` 一起停（`--keep-daemon` 才保留）；`ack_policy.py` 确认 ACK/升级归 Monitor、Monitor 停则 fail-closed 无接管。计划「仅加 --keep-daemon 不能代签通知完全独立」判断正确；盘后/非交易日 QMT、运行日 vs 目标行情日、exit=0 不代签水位，在 §3.2 和 OP01 完成条件中均已分离，未发现生产/消费、PIT/as-of、数据质量/运行成功的混淆。
  - **6.53 边界分清**：P05 首日依赖只列「V653 测试漂移收口、SDD 现场核验、有效源 B、批准名单」——不含 P13 的 14 本 baseline、不含 P06 模式 E；runbook 自身（`v653-paper-first-day-runbook.md` 头部）也声明 NOT VERIFIED、parking/profit-skim execute=false。P18 旧 live 条件明确「不以新 GO 自动冲销旧账」。
  - **QL01 属实**：冻结 SHA `7c428d9b` 下 5 个测试文件都存在，但 ci.yml data-free job 只跑 7 个 joint_return 文件——确为「代码已合、CI 未调用」。
  - **开放项无遗漏**：三仓全部开放 PR/issue（1.3 #1256/#1258/#34/#37；BT #531/#532/#538/#164；MyQuant 无）均各有着落包。

  ## 具体发现（均不阻塞）

  **P2-1：批次 0A 完成条件钉死了旧 head 的测试计数。** 明细 V653_TEST_DRIFT 完成条件写「50 条修复测试与相关 342 条回归通过」，这是旧 head `82c3fce` 口径；head 已更新到 `ceff70d` 且作者在收尾，若修复集增删，该数字条件会失配。建议把完成条件改为「最新 head 的 Phase4c/d/e 契约域全绿 + Windows 完整契约门结束」，具体计数作为参考而非判据。（快照刷新已由主代理负责，此项只作措辞建议。）

  **P2-2：OP01 通知独立的验收粒度可再细一档。** 完成条件要求「所声明通知能力有独立存活/失败回执」，但 `ack_policy.py` 的 `P0AckContract` 是按 `alert_domain`（system/breaker/cninfo）分别 fail-closed 描述的。建议验收时按 alert_domain 分别签收「Monitor 停止时哪些能力必须存活、哪些允许标 NOT_COVERED」，避免一份笼统的「通知独立 PASS/FAIL」掩盖 cninfo app-only 升级这类单域缺口。

  **建议（不阻塞）：** P04 的「1m+1d 矩阵非全零读回 PASS」与 P03 的「10/24 同窗 1m volume 全 0 须重查」之间存在隐含先后——若当前分钟消费者确实要求 volume，则 P03 字段修复是 P04 矩阵 PASS 的事实前置；计划已在批次 1 把两者放同一基线线，建议在 P04 完成条件里补一句「若消费者确认不要求 1m volume，允许 zero-volume 通过并在证据中显式标注该判据」，与 SHM_DATA_QUALITY 的既有依赖说明对齐即可。

  除以上外，排期风险（宿主等待、真实交易日观察的外部等待、批次 2 同宿主 SDD 演练与首日的隔离要求）计划均已显式声明，未见不必要重做项。
