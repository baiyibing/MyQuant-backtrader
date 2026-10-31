# Hithink 窗外异常隔离续片

状态：2026-10-30 用户“继续GO”，承接首次实施中“窗外历史负值隔离、窗内仍阻断”的建议。L2，沿用显式离线命令；不改变默认 v1 严格行为。

1. 1.3 新增 `--quarantine-outside-window`。仅非负规则可按已验证的除权日期隔离；非法代码、币种、时间戳、非有限值及精度损失仍整批失败。异常在 start/end 内（含边界）仍失败。
2. 选项产生 v2 产物：原始 parquet 原封保存，增加 `quarantine.json`，manifest/COMMITTED 均标版本 2；请求绑定固定 policy `negative_amounts_outside_window_v1`、原始宇宙哈希和窗口。v1 四文件与行为不变。
3. 全列去重后隔离，sidecar 逐行保存原始位置、规范原始行 SHA、代码/日期和负数字段。原始数值仍在原始包中。统计区分原始行、唯一行、可用行、隔离行，双方独立重算并校验 sidecar，不信任生产方自报统计。
4. BT 只接受已知 v1/v2 与固定 policy。导入、幂等及完整提交校验按实际版本文件集合工作。assemble 明示隔离数量。parity 若其历史区间包含隔离行，明确失败并列明，不能静默删历史。
5. 复核 300708.SZ / 2020-06-02 的原始 Wind 0.0199 与 Hithink 0.02。事实属实后将该精确 5 元组加入诊断清单（46→47），保存旧清单哈希与差异记录。集合恒等、Decimal 阈值和经济闸门保持；这不是权益金额批准。

直接验收：窗口前/内/后及两端点、非法字段不可隔离、sidecar 删除/篡改/错误窗口、v1 兼容、重复原始行、历史 parity 隔离交集、跨仓真实导出/导入/assemble 留证；不伪造 D 类审批，不发布候选到湖。

独立预审已采纳：覆盖 presence 按原始 dump 全部代码（含隔离行）计算；仅有窗外隔离行的代码不误报为供应商缺码，当前窗口计无事件并单列隔离身份。`accepted_rows + quarantined_rows == deduped_rows`，重复隔离位置仍由 duplicates 留证。版本须为严格整数，manifest/marker/文件集合匹配，v1 带 quarantine sidecar 拒绝降级。

原则④⑤⑦⑧⑩：冻结文件版本、明确失败、显式开关、单一统计与证据；交易进程/资金/策略通道时点均 N/A。代码后独立只读复核，问题闭环后更新原草稿 PR。

## 完成结果

1.3 44 项、BT 122 项定向测试通过（另有 1 项本机 Windows symlink 权限测试排除，CI 保留）；双方定向 pyright 0 errors/0 warnings，ruff 通过。独立只读复核补齐了 bool/整数严格比较、重封 state 不得丢隔离记录及 v1 不得注入隔离记录三项边界，最终结论无剩余实现阻断。

真实 v2 导出已成功提交，BT 导入成功并组装 162 条窗口内事件：57,709 原始行、57,708 唯一行 = 57,706 可用行 + 2 隔离行。原始包未删改。冻结事实集经 [精确边界复核](evidence/hithink-artifact-2026-10-30/decimal-boundary-review.json) 为 47 键；实际复算无新增/消失键，21,709 个历史键对拍，历史比较窗口与隔离行无交集。

覆盖仍为 A4/B3/C0/D11，31 个仅 Wind 历史键未解释，故 parity 总状态和 prepare-merge 继续阻断。完整 [真实运行摘要](evidence/hithink-artifact-2026-10-30/v2-real-run.json) 与 [11 码事实复核表](evidence/hithink-artifact-2026-10-30/v2-coverage-review.json) 已留证。基线是从冻结 CSV 在独立目录重建的离线参考，不是发布的湖修订；没有生成可发布候选、签人工例外或写湖。

后续 [D11 公告取证](hithink-coverage-followup-2026-10-30.md) 已确认三种身份事件：窗口内主动摘牌、退市整理期和换股吸收合并。另八码找到报告期不分配文件，但不足以证明整个窗口无事件。31 个 Wind-only 历史键全部关联前三码；原覆盖阻断和冻结输入保持。

为让整体 CI 能继续，1.3 同步主线 7943d10 后修复了已确认的基线问题：`l2_phase3_pipeline.py` 去 BOM、使用明确上海时区；`extract_stock_rar_data.py` 明确返回 bool；两份 v653 CLI 去重复的同名 parser 声明。保留原 parser 逻辑和退出码，help=0/非法参数=1 冒烟通过，四文件定向 pyright 0 errors/0 warnings。原 CRLF 字节保留并注明 whitespace 规则，未重构其业务代码。CI 最新结果以两个 PR 为准。
