# 因子实现先迁 MyQuant（2026-11-09）

用户裁定：因子实现不留 BT，先归 MyQuant；MyQuant 不反向依赖 BT 计算因子。
四仓分工为：MyQuant 管因子定义、计算实验、效果验证、Qlib 训练和信号/名单导出；
infra 管采集、清洗、聚合及对消费者供应的因子数据产制；BT 管信号/名单消费、
成交模拟、费用、持仓和收益回测；1.3 管实盘执行和真栈验收。因子是否接入
infra 按数据处理/交付职责判断，不以“成熟”或消费者数量作为自动迁移条件。

本条替代旧 D8/H13 中“TR/Rust 数值核留 BT”的归属。MyQuant 既有完整 Qlib
研究能力保留；BT 的 Cerebro/LEBS 定位、策略书规则和成交默认值不变。
正式分界正本：[infra boundary](https://github.com/baiyibing/MyQuant-infra/blob/main/docs/architecture/boundary.md)
（本次同步 [infra #92](https://github.com/baiyibing/MyQuant-infra/pull/92)）。

## 本批接收与消费

接收 [MyQuant #139](https://github.com/baiyibing/MyQuant/pull/139)：

| 原 BT 内容 | MyQuant 位置 | BT 处理 |
| --- | --- | --- |
| 筹码分布、换手系数与因子分析/绘图 | `myquant_factors/` | `qlib_cost` 只转发 |
| 筹码 core/bands/shares/adj、价格带、周线 MACD 背离 | `myquant_factors/chip` 等 | `oskh_factors` 只转发 |
| TR Python 桥和 Rust crate（20 个源文件/资产） | `myquant_factors/bridge`、`rust/turnover-resist` | 删除本地 crate，只留 README 指针 |
| 通用扫描、IC/效果验证、诊断与 TR 研究入口 | `myquant_factors/research`；原生 CLI `my_scripts/factor_research` | 旧入口只转发，不留计算实现 |
| 两份 Qlib handler/workflow 样例与筹码 Notebook | `my_scripts/chip_research`、`examples/chip_research` | 三个旧文件全部删除 |

通用旧脚本的 38 条迁移映射位于 MyQuant
`examples/chip_research/entrypoint-migration.json`；另迁原 `research/chip` 四个模块
和周线扫描入口。BT 的全部兼容转发由
[`factor-consumer-exports-20261109.json`](factor-consumer-exports-20261109.json) 固定，
`scripts/gates/verify_factor_consumer_boundary.py` 阻止恢复这些路径的函数/类实现、
训练样例、Notebook 或 Rust crate。缺少 MyQuant 依赖即失败，不回退本地算法。

`requirements-factors.txt` 固定公共 MyQuant 不可变提交。包只安装 `myquant_factors`，
不向 BT 安装 Notebook、训练工作流或 Qlib handler。原 pandas 3.0.6、DuckDB 2.0.0
及 infra `af27dd08c6b5e3653fa686c6f60e541afd1a4941` 钉保持不变。

`oskh_factors/_consumer.py` 仅注入 BT 的路径/时钟/日志、reader 生命周期、
复权门禁、名单解析和 infra Store 接线。子进程经显式宿主薄入口保留同一门禁，
MyQuant 的调用端口不 import BT。Rust 可执行文件经 `TURNOVER_RESIST_EXE`
显式提供；构建在 MyQuant crate 目录内进行。

## 验证与未切换事项

MyQuant 接收侧保留迁入数值单测，并验证 handler 解析、模型配置构造、模拟训练
端口接线、缺输入失败、历史输出完整性和无 BT 反向依赖。38 个通用模块在空的
显式数据目录中导入，禁止创建 reader。Rust 文件逐字节对照原 BT 提交；
MyQuant CI 执行无数据的 `cargo check --locked --all-targets`。

Notebook 的 57 个旧输出完全保留，清除执行计数并标记历史图表；本次未运行
训练、PortAna、真实数据加工或名单发布。Notebook 的环境/缓存路径和 `scr.*`
导入已修正，这不构成当前数据下模型或收益表现的验收。

BT 继续验证分钟 Numba/Python 一致性、TR Store 接线与缓存、复权时点、原入口
兼容及完整成交/收益回归。不重录 golden，不把 Windows 的换行、符号链接权限、
临时目录或缺少 Rust 编译器笼统合并为“环境失败”。最终结果以 PR 的完整 CI
和本地验证回执为准。

本批不宣称 BT 已完全只消费外部名单：与策略书 D→T、CSV 和 manifest 合同耦合的
`export_strategy9_pool`、`export_ta_pool`、`export_strategy11_pool`、
`export_beidou_pool`、`export_topk_app_dropout_pool` 仍在 BT。它们需要连同定义、
调用方和合同另行收口到 MyQuant；不能只搬 CLI 再反向 import BT。
`strategies/tr_filter.py` 当前为已产截面的宿主筛选政策，数值分类器调用 MyQuant。
正式数据供应接入 infra、生产任务切流及策略名单生成的归属切换均未在本批启用。
