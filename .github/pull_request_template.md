## 摘要

<!-- 简述本 PR 做什么、为何需要 -->

## 自检

- [ ] **消费边界**：涉及共享数据、因子或 ops 入口时，已对照 [AGENTS.md](../AGENTS.md#scope)，说明公共 API 与宿主适配的变化，并运行相关的 [`verify_infra_consumer_boundary.py`](../scripts/gates/verify_infra_consumer_boundary.py)、[`verify_factor_consumer_boundary.py`](../scripts/gates/verify_factor_consumer_boundary.py) 或 [`verify_ops_consumer_boundary.py`](../scripts/gates/verify_ops_consumer_boundary.py)。已迁实现只通过公共接口消费，缺依赖明确失败。
- [ ] **行情与路径**：行情保持只读，湖根使用显式配置与 resolver；采集、加工、存储 IO 和湖维护调用 MyQuant-infra。涉及路径或存储接线时，已运行 [CI 对应门禁](workflows/python-tests.yml)，并说明宿主配置、reader 生命周期及研究输出路径的影响。
- [ ] **研究契约与验证**：涉及策略、成交、费用、资金或持仓时，已说明默认行为及相关契约测试结果；presets 跨仓基线和 golden 的变更有明确依据。实际运行的检查、跳过项及未验证范围已写入 PR 描述。
