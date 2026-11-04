# 用户复评后的计划修订

用户抽查 BT-04、BT-18、#539 后认可文档合入，并提出提前准备首日输入、核 volume 依赖、单列 Owner 操作、机器回执及人裁排队五项风险。本轮在同一 PR 修订，保持 21 包/64 条映射及原域授权边界。

| 意见 | 处理结果 |
|---|---|
| 批次 2 外部等待应提前暴露 | 增加批次 0.5，I01～I07 从批次 0 开始准备，与批次 1 并行。区分离线合同核对与目标机只读回执；真实 Redis、路径、名单批准和输入有效性不能离线代签 |
| 6.53 是否需要 volume | 静态核到源 B 的指数 1d/none/T−11..T−1 读取要求 OHLCV 有限且大于 0，volume=0 的测试断言 UNKNOWN。当前接线未见分钟 bar volume 依赖；日线真实有效性及部署采集方式仍待宿主核实 |
| 分支保护需要 Owner | H01～H03 从 CI 开发片中独立列为 Owner/admin 操作队列；先准备参数与验证步骤。本轮未修改 GitHub settings。1.3 是 main，其他两仓是 master；1.3 rulesets 的 403 不能概括为「没有规则集」 |
| 计划也会漂移 | 冻结审计 `items[].status`，新增 `closeout_receipts` 只追加原域证据索引。已合 #1258 先登记条目级回执；只有包内全部条件满足才允许整包关闭 |
| 人裁吞吐限制 | 14 本书、TopK Q8、603556 lot、G5 分别准备可审选项与证据；未裁片等待，独立片继续，不以并行准备承诺同时完成 |

两处表述作精确化：P01 仅 `V653_TEST_DRIFT` 已完成，QL01/BT-18/BT-17 仍未关闭；首日输入清单可以提前准备，但实际账户/Redis/源 B 有效性不是纯离线证据。

## 静态事实依据

复核时 `gh` 读取 1.3 main 仍为 `1ed67467890edb6c931bf8816c121fa7483cc276`。此前 compare 已证明该提交仅变更 #1258 七个测试/场景辅助/编排文件，以下源码与冻结 `7e52e6e0cd6a289ad04bccaefb5edced40850841` 一致。

- `live_trading/runtime/v653/inputs.py:36–65`：指数树专用 reader，1d/none，T−11..T−1；OHLCV 正且有限，synthetic 拒绝。[冻结源码](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/live_trading/runtime/v653/inputs.py#L36)
- `tests/test_v653_paper_wiring.py:313–315`：将完成日 volume 改为 0，gate 必须 UNKNOWN。[已有断言](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/tests/test_v653_paper_wiring.py#L313)
- `loop_hooks.py:131–134` 调用源 B，异常写 `index_source_b_unavailable` 并使用 UNKNOWN。分钟调度频率不等于读取分钟 bar。[接线](https://github.com/baiyibing/OSkhQuant1.3/blob/7e52e6e0cd6a289ad04bccaefb5edced40850841/live_trading/runtime/v653/loop_hooks.py#L131)

此次只核代码与已有测试断言，未运行新宿主实验；源码/测试证明失败语义，不能证明目标湖今天的 volume 有效。

## 机器回执核验

首条真实回执 `oskh-pr1258-v653-test-drift`：主包 P01、作用域 `audit_items`、仅 `V653_TEST_DRIFT`、关闭时间为已核 PR 合入时间，链接原 PR、合入提交及 Windows CI。字段、UTC 时间、唯一 ID、条目归包、原域证据链接均校验。由回执推导 P01 剩余三项，不能推导 P01 关闭。

后续关闭 PR 同步添加本索引回执；跨仓完成时可由紧随的索引 PR 链回原域。人签要求继续由原域合同决定，机器条目不提供授权。
