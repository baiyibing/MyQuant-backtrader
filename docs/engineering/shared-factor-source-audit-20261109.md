# 共享因子后续盘点与交付修复（2026-11-09）

本轮继续落实两项已确认职责：回测专用名单生成保留 BT；同口径公共因子核
通过一个共享组件复用，各消费仓不各自维护源实现。此前三份迁移/分界 PR
复核时均为绿色、待合并；本轮不自行合并或切换生产任务。

## 本轮交付

MyQuant 公共包根导出改为按能力加载，保留原 19 个函数/类与 7 个模块的公共入口。
调用 TR bands、路径端口或 Rust 桥时不再预加载 Qlib、Numba、绘图与筹码研究栈。
阻断这些模块导入的独立进程测试验证轻量入口可用；对象身份及 star import 合同
也做兼容验证。数值公式、窗口、价格域与策略条件均未改变。

`TURNOVER_RESIST_EXE` 显式配置的文件不存在或指向目录时，立即给出带配置名及
路径的错误，不静默选用其他二进制。未配置 EXE 时保留显式 `CARGO_TARGET_DIR`
及共享 crate 目标目录的查找顺序。公共包同时补齐纯计算所用的基础 loguru 依赖；
既有 pandas 3.0.6、DuckDB 2.0.0 与 infra 钉保持不变。

接收仓 Rust README 改为可移植构建说明，移除旧机器固定盘符结论。BT 筹码文档
索引修复空白字段和历史路径控制字符，并将旧算法/框架/构建说明标明为历史材料。
当前调用与构建均指向公共因子组件，回测策略名单仍在 BT。

## 1.3 存量副本证据

只读核对 GitHub `main` 的 `0aff26bd84020dfbbdb0f5490516c8945e7ee201`，没有
使用其开发分支代替主分支，也未修改原工作树中的未跟踪文件。
共享组件版本及逐定义结果见[结构化回执](shared-factor-source-audit-20261109.json)。

| 1.3 模块 | 与共享组件对比（忽略 import） | 收口关注点 |
| --- | --- | --- |
| `oskh_factors/chip/bands.py` | 4 个定义结构一致 | TR BB 公式、列名、NaN/窗口合同 |
| `oskh_factors/chip/adj_factor.py` | 5 个定义结构一致 | 保留 1.3 路径、缓存、复权 freshness 政策及异常身份 |
| `oskh_factors/chip/paths.py` | 2 个定义结构一致 | 通过宿主端口注入解析器，禁止机器盘符回退 |
| `oskh_factors/bridge/turnover_resist.py` | 6 个定义结构一致，2 个存在差异 | CLI 编码/BOM 与可执行文件定位需要显式对齐 |

已发生的漂移包括：1.3 CLI CSV 按 `utf-8` 读取，共享桥处理 `utf-8-sig` 的表头；
共享桥显式解析 subprocess UTF-8 输出，而 1.3 使用平台默认编码；1.3 定位器还有
固定构建盘符回退，共享桥使用显式配置和自身 crate 的目标目录。
因此不能用文件名相同或“调用过同一种 Rust 算法”来推断所有路径已经一致。

使用纯合成输入完成 56 组 TR BB/分类对拍与 16 组注入复权乘数的算术对拍，结果
完全一致。对拍不导入 1.3 交易代码、不读取行情，也不验证其 freshness、reader、
会话或决策运行时。该证据支持后续抽取，不能当作交易接线验收。

## 1.3 后续接线要求

`trade_decision/wiring.py` 直接消费 `StaleDataError` / `get_adj_factor`，不是仅有
离线脚本调用。因此后续应保留宿主路径、时钟、日志、cache reset、过期判定与
异常对象合同，先补跨入口失败语义与 CLI UTF-8/BOM 对拍，再切薄转发并删除副本。
不将 1.3 的交易政策搬进公共算法，也不让共享包反向 import 1.3。

1.3 自身 [AGENTS.md](https://github.com/baiyibing/OSkhQuant1.3/blob/0aff26bd84020dfbbdb0f5490516c8945e7ee201/AGENTS.md)
要求 L2（含跨模块/facade）“plan + multi-AI + GO 前禁编码”。本轮仅提交盘点及
公共包就绪性修复；1.3 facade 切换须在该仓按其计划与评审门禁单独收口。
本记录不宣称四仓的公共因子副本已经全部清除。

## 验证

MyQuant 本轮全量本地回归：809 passed、2 skipped、18 subtests。另有轻量导入、
原公共对象身份、无效显式 EXE 与正常目标目录搜索测试。BT 更新固定消费提交后，
继续执行原消费/Numba/TR/Store/复权回归与 CI。未重录 financial golden，
未训练模型、运行真实行情计算或替换已部署二进制。
