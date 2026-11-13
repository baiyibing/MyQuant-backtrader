# 共享评审消费迁移验证

实现源版本：8ae982c；依赖 [ops #244](https://github.com/baiyibing/grok-bot-ops/pull/244)，方案及人GO见 [ops #240](https://github.com/baiyibing/grok-bot-ops/pull/240)。J仍暂停；本变更不授予合并或运行业务。

22项消费合同测试通过，边界门通过，变更文件pyright 0 error。独立只读消费审计GO：本仓只保留领域profile、显式路径的宿主适配及薄入口；未恢复共享实现副本。测试覆盖参数缩写/覆盖拒绝、不同cwd、路径/API/scope、native退出码传递与副本回流。

真实ops 674560085394 的离线调用已核验目标root、profile、逻辑奇偶组、author/host、received=0/decision=null；未调用模型。日志及raw字节索引随ops实施证据归档。

review-v2实际dry-run通过；adversarial-v1仍保留原合同，离线嵌套检测按原生返回码拒绝嵌套、没有输出目录。旧API的publisher/adversarial兼容由合同测试验证，publisher未发送任何外部写入。当前跨仓能力以对应仓SSOT与实际入口为准，旧LEBS说明已标历史。
