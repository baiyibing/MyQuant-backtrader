# OP06 事实/研究合同 SSOT 迁 MyQuant-infra

Human t120u（2026-11-08，Asia/Shanghai）：立刻把 OP06 从交易/研究仓迁到数据产制仓。边界正本见 MyQuant-infra `docs/architecture/boundary.md`：infra = 量化栈数据产制 SSOT；BT 只消费成品、不处理数据。

## 本片做了什么

- 新增 `docs/operations/op06-research-contract-ssot.md`：写明事实/研究合同正本迁 MyQuant-infra；列出仍留本仓的身份事实 JSON、覆盖后续说明、收尾台账及 blob/commit SHA，供 hostbot 承接。
- 在 `docs/operations/corp-actions-incremental-driver.md` 与 OP04 薄指针中交叉引用该文，避免把「东兴换股引擎」再排进 BT。
- **不**删除、不削弱 [#550](https://github.com/baiyibing/MyQuant-backtrader/pull/550) 消费侧拒绝门（原因键 `unsupported_stock_conversion_in_cash_bonus_schema`）。该门已随 [#576](https://github.com/baiyibing/MyQuant-backtrader/pull/576) 迁入 `myquant_infra.corp_actions.econ_gate`。
- **不**在 BT 重实现研究合同或恢复 `corp_actions_econ_gate.py`。
- **不**改 MyQuant-infra，也**不**开 OSkh PR（当前 master 无独立 OP06 产制文件）。

## 盘点摘要

未发现未提交的 OP06 研究合同草稿。产制侧待承接材料见指针文表格；#550 运行记录与经济学 fence 留在本仓。

合入交 ZCode。
