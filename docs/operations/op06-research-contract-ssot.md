# OP06 证券转换事实/研究合同 SSOT（2026-11-08 迁移指针）

> **Human 裁定（2026-11-06 / 2026-11-08）：** infra = 量化栈数据产制 SSOT；介质不决定归属，下游消费者决定。BT 只消费成品、不处理数据。OP06 东兴换股/证券转换的**事实与研究合同**属数据侧，正本迁 **MyQuant-infra**（由 hostbot 编码）。本仓不实现该合同，也不另起正本。

## 现行归属

| 能力 | 归属 |
|---|---|
| 证券转换事实与研究合同（分开 issuer / source / target 与生效/可知时间；冻结目标股估值、待换股权益、成本迁移、交易锁、股东级尾数政策；真实账户数量以登记结果为准） | **MyQuant-infra**。本仓不重实现。 |
| 消费侧拒绝门：禁止把换股塞进现金/送转十列（[#550](https://github.com/baiyibing/MyQuant-backtrader/pull/550)，稳定原因键 `unsupported_stock_conversion_in_cash_bonus_schema`） | **保留，不删除、不削弱。** #550 把 `PINNED_STOCK_CONVERSIONS` 写入当时的 `backtest/research/corp_actions_econ_gate.py`（钉死 601198.SH → 601995.SH @ 0.4376，运行时不读 JSON）。[#576](https://github.com/baiyibing/MyQuant-backtrader/pull/576) 按「BT 只消费成品」删除处理管线，拒绝语义随 `econ_gate` 迁至 `myquant_infra.corp_actions.econ_gate`（infra [#66](https://github.com/baiyibing/MyQuant-infra/pull/66)）。BT 禁止重建过滤逻辑。 |
| 经济学成品消费 | infra 出合格表，BT 回测只读 parquet |

通用消费者接入另片；不能把换股挤入 `bonus_ratio` / `transfer_ratio`，也不自动把目标股 601995.SH 加入选股池。

## 仍留本仓、供 infra 承接的产制/合同材料（冻结原文，不是正本）

以下路径以 `origin/master` tip `0cf9673b5b11f9b6e49399b83539ecc56a4da395` 计。blob 为 git 对象 SHA。本指针不删除这些文件。

| 路径 | 角色 | blob | 最后写入 |
|---|---|---|---|
| `docs/operations/evidence/hithink-artifact-2026-10-30/coverage-identity-facts.json` | 身份事实 JSON。`601198.SH` 分类 `in_window_stock_merger`：换股登记 2026-10-16、摘牌 2026-10-19、目标 `601995.SH`、比例 `0.4376`、股东级尾数政策；公告 [1225606336](https://static.cninfo.com.cn/finalpage/2026-10-16/1225606336.PDF)（sha256 `9553a01c4278f46f18fcc05665640fbe39a759c546d5f2f6a47010cc1c7d94cf`）。另含 000016.SZ / 002731.SZ 身份事实。listing 修订提议 `approved=false`。 | `9eef7114992d5c043dd5253606eac11fd4aa8ea6` | `445861ebde3f7b3e113d0521ee2383cf1695badf`（[#538](https://github.com/baiyibing/MyQuant-backtrader/pull/538)） |
| `docs/operations/hithink-coverage-followup-2026-10-30.md` | 覆盖后续说明。§三个身份缺失代码 + 可执行后续顺序第 3 条：为 601198 **单独准备证券转换合同**（来源/目标、登记日、换股完成与上市日、股东级零碎权益、原成本转移、待登记期间估值与卖出限制、源修订链与重复导入幂等）。这是未完成的研究合同提纲，不是实现。 | `8e1958dbe6c87a6a13d3ee172b6a02f0c67d57ed` | `445861ebde3f7b3e113d0521ee2383cf1695badf`（#538） |
| `docs/operations/three-repo-closeout-inventory-2026-10-30.md` §「OP06 东兴换股与证券转换消费模型」 | 收尾台账：状态为「本片先做事实与研究合同」；完成条件为跨摘牌/登记/上市窗口现金与权益不凭空消失、事后公告不提前用于决策、不支持场景显式阻断。 | `ef5ba36847a5685a88b5b3fcdcc13a68b15e173f` | `a21bc4b5e135eac65b40bf9ade8c0f22f67fe4d7` |
| `docs/operations/evidence/three-repo-closeout-2026-10-30/inventory.json`（`id=OP06`） | 同上条目的机器可读版。证据另列实施结果公告 [1225627350](https://static.cninfo.com.cn/finalpage/2026-10-27/1225627350.PDF)（身份事实 JSON 尚未收入该份）。 | `7971db7b7fac8ddec8ce79b8692fcde119b06d35` | `a21bc4b5e135eac65b40bf9ade8c0f22f67fe4d7` |

相关冻结证据（不是合同正文，但解释 601198 的 13 条 Wind-only 历史键与取证范围）：

| 路径 | blob | 最后写入 |
|---|---|---|
| `docs/operations/evidence/hithink-artifact-2026-10-30/coverage-historical-gaps.json` | `e330912bd4c054021cff96fe0be24c8c7e23b18c` | `445861ebde3f7b3e113d0521ee2383cf1695badf` |
| `docs/operations/evidence/hithink-artifact-2026-10-30/README.md` | `ece5edbe1d238806c0f4055f50cf8748be463b8a` | `445861ebde3f7b3e113d0521ee2383cf1695badf` |
| `docs/operations/evidence/hithink-artifact-2026-10-30/coverage-period-facts.json` | `9c52d1c13542e338c214f2be3c1d7356ee8b2f0f` | `445861ebde3f7b3e113d0521ee2383cf1695badf` |

工作区与未合分支中**没有**未提交的 OP06 研究合同草稿。

## 本仓明确不迁走、不削弱

- [#550](https://github.com/baiyibing/MyQuant-backtrader/pull/550) 消费侧拒绝门。实现提交 `1279108a987af882722090fe5bb0b3eb6401dbf4`，合入 `6f3a3305b2dacba6bb4fe49549a05284227ac43f`。#576（`3221cdeb31ad5bd3b40daf1db1cb2629071e3b24`）从本仓删除 `corp_actions_econ_gate.py` 与 `tests/test_corp_actions_op06_conversion_gate.py`，语义现由 infra `econ_gate` 执行。本指针不恢复处理模块，也不改原因键。
- #550 运行记录：`docs/run-records/2026-11-02-op06-conversion-cash-bonus-reject.md`（blob `973d2f0700ad16199e8aec361a2e85657c268e1d`）。
- 消费侧经济学 fence：`scripts/gates/verify_corp_actions_economics_fence.py` 与 `tests/test_corp_actions_economics_fence.py`。

## OSkhQuant1.3

当前 `origin/master` **没有**独立的 OP06 合同或产制文件，因此本迁移不开 OSkh PR。

库存引用的前瞻段落在历史快照 `6825f22169222dd58be2765c6fcda80aa4a8872f` 的 `docs/operations/plan-cninfo-economic-date-evidence-2026-10-30.md`（「东兴案例」：先输出不可执行的证券转换事实与独立研究合同；10-16 权益登记、10-19 摘牌、10-23 新股登记、10-29 无限售股可交易；目标股进持仓/估值宇宙而非选股池）。该文件不在当前 OSkh master。本仓 [#580](https://github.com/baiyibing/MyQuant-backtrader/pull/580) 对其只留了 OP04 消费侧薄指针，并写明未实现东兴换股引擎。

## 禁止

- 在 BT 或 OSkh 实现证券转换研究合同、采集或结算模型。
- 把换股挤入现金/送转十列，或自动把 601995.SH / 601059.SH 加入选股池。
- 删除或改写 #550 拒绝原因键，或在 BT 重建 `econ_gate` 过滤逻辑。
- 本指针不改 MyQuant-infra。合入交 ZCode。
