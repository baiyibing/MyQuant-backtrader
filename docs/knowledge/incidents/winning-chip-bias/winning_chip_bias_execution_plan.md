# 赢筹偏差诊断 — 执行计划

## Context

诊断计划文档 (`winning_chip_bias_diagnosis_plan.md`) 已通过多轮专家评审，现进入执行阶段。核心问题：本地计算的赢筹率与券商存在偏差，需系统性修复并量化。

### 当前基线

| 项目 | 现状 |
|------|------|
| `float_shares.parquet` | 仅 100 只（1.8%），其余 5,400+ 用 100 亿股默认值 — **P0** |
| 复权配置 | 分钟线不复权（QMT 限制），`hybrid_chip_distribution` 已有代码但未验证 |
| `config/chip_diagnosis.yaml` | **不存在**（计划要求 SSOT） |
| `scripts/diagnostics/preflight_chip_diagnosis.py` | **不存在**（计划要求自动拦截） |
| `verify_chip_factor_consistency.py` | 存在，只做 daily vs minute 内部对比 |
| 外部基准（AKShare） | 网络封禁，需走降级路径 |

---

## 执行顺序

### 阶段 1：基础设施（不可跳过，后续依赖）

**1.1 创建 `config/chip_diagnosis.yaml`**
- 集中管理所有诊断参数：窗口长度、复权类型、样本列表、MAE/RankIC 阈值
- 作为全流程的 SSOT，脚本不允许各自硬编码参数

**1.2 创建 `scripts/diagnostics/preflight_chip_diagnosis.py`**
- 6 项检查：float_shares 覆盖率/日线数据/分钟线数据/样本量/YAML 哈希绑定/非零退出
- 后续作为发布前强制门禁

**1.3 float_shares 补全（P0 修复 #1）**
- 先给 `float_shares.py` 加备份逻辑（写入前 `.bak.YYYYMMDD_HHMMSS`）
- 在 QMT 在线时运行 `python -m oskh_data.float_shares` 获取全市场流通股本
- 验证覆盖率 >= 99%

### 阶段 2：P0 修复验证

**2.1 复权一致性核查（P0 #2）**
- 运行 `verify_chip_factor_consistency.py`，获取日线 front vs 分钟线 none 的 baseline r
- 确认 `hybrid_chip_distribution` 调用链正确
- 用 baseline 结果对照 P0 #2 关闭标准（r > 0.85，按日期 r >= 0.75，失败切片 <= 10%）

**2.2 运行 preflight**
- 在阶段 1-2 完成后执行 `preflight_chip_diagnosis.py`
- 确认退出码为 0

### 阶段 3：方案 A — 算法修复 + 敏感性分析

**3.1 窗口长度敏感性**
- 选 20 只代表性股票（4 大/4 中/4 小/4 高波动/4 低波动）
- 60/80/100/120 天各跑一次 cyqk_c
- 仅在敏感股票 >20% 时才调优

**3.2 理论偏差清单**
- 调研通达信/同花顺公开参数，列出与本地差异

**3.3 方案 A 交付物**
- 敏感性分析报告 + 理论偏差清单

### 阶段 4：方案 B — 样本对比（降级路径）

外部 API 不可达时走降级路径：
- 一级基准：修复前 vs 修复后两轮对比，量化方案 A ROI
- 人工 sanity check：5-10 只覆盖大小盘

若外部 API 后续可达，叠加 MAE/RankIC 量化对比。

### 阶段 5：收口

- 填写调查报告，记录所有修复效果和偏差结论
- 若 P0 已关闭 + 停损条件满足 → 关闭调查
- 若 P0 未关闭 → 保持"禁止上线"状态

---

## 关键约束

- **QMT 必须在线**：阶段 1.3（float_shares）和阶段 2.1（verify 脚本需要读数据）
- **数据冻结**：方案 B 两轮对比期间禁止任何 backfill/补录
- **对比期数据只读**：从阶段 3 开始到阶段 4 第一轮完成，冻结 DuckDB 和 Parquet
- **所有 Python 命令使用** `D:\anaconda3\envs\vanna311\python.exe`
- **config.yaml 哈希写入报告**：每次执行记录配置版本

---

## 验证方式

每个阶段完成后的验证：
1. 阶段 1.3：`preflight` 检查 float_shares 覆盖率 >= 99%
2. 阶段 2.1：`verify_chip_factor_consistency.py` 输出 Pearson r 和按日期分组 r
3. 阶段 2.2：`preflight_chip_diagnosis.py` 退出码 0
4. 阶段 3-4：对照停损条件检查是否满足关闭条件
5. 阶段 5：调查报告完整性检查
