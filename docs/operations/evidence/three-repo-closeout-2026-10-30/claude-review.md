核验完成。所有检查均已做完，以下是评审结论。

---

# 只读评审报告：三仓收尾计划（2026-10-30）

**评审对象**：`docs/operations/three-repo-closeout-plan-2026-10-30.md`、`three-repo-closeout-inventory-2026-10-30.md`、`evidence/three-repo-closeout-2026-10-30/inventory.json`（均未跟踪新文件）。未改动任何文件、未启动服务、未发通知、未提交/合并。

## 一致性核验（全部通过）

| 检查项 | 结果 |
|---|---|
| 计划「21 个实施包、64 条审计记录」vs JSON | ✅ 21 包 / 64 条，ID 一一对应，无重复 |
| 明细归包（markdown P## 章节 vs JSON `work_packages.audit_ids`） | ✅ 64 条全部一致，每条只归一个包 |
| 每条记录的标题、证据链接集合（md vs JSON `sources`） | ✅ 逐条 URL 集合完全一致 |
| 「共索引 1,549 条 PR 记录」 | ✅ 903+109+537=1,549，与 `github_counts` 吻合 |
| 开放 PR/issue 2/2、0/0、3/1 | ✅ 与 JSON 一致，且与正文对应（1.3 #1256/#1258 + #34/#37；BT #538/#531/#532 + #164） |
| BT 快照 SHA `418496378ebe` | ✅ 等于本 worktree HEAD；34 条 BT blob 链接全部钉在该 SHA |
| 锚点 p01–p21 与计划表内链接 | ✅ 全部存在、可解析；本地相对链接无死链 |
| JSON 完整性 | ✅ 64 条均含 status/remaining_actions/acceptance/sources；`completed_or_superseded` 29 条 |
| 溯源哈希 `source_inventory_sha256` | ✅ 4 个 findings 文件（`../root_findings.json` 等）实测 SHA256 全部 MATCH |

## 代码级事实抽查（确认属实）

- **BT-18（验收器漂移）**：`scripts/research/verify_run_protocol_lake_parity.py:382` 的 `native_argv` 确实不含 `--rule-profile`；`verify_run_protocol_lake_parity.py:445-450` 的 csv_minute low_cash 格硬要求 `InsufficientCashError`、退出 0 即判 `NOT_COVERED`；而 `backtest/research/csv_daily_backtest.py:285` 与 `csv_minute_backtest.py:1451` 默认 `rule_profile="industry"`（含 `shrink_on_short_cash`）。**误报机制成立，诊断准确。**
- **BT-04（14 本 pending 书）**：`scripts/research/generate_off_byte_baseline.py:138` 的 `PENDING_BOOK_NAMES` 与文档所列 14 本逐项一致。

## 发现的问题

1. **【轻微】未加说明的第二 OSkh 快照 SHA。** OP01/OP04/OP06 引用 `plan-cninfo-economic-date-evidence-2026-10-30.md` 时用了 `6825f22169`，而明细开头声明「来源锁定于主计划所列提交」（主计划只列 `7e52e6e0cd6a`）。该文件日期与计划同日，大概率是快照之后才合入、作者改用后快照提交补链——做法合理但零解释，与自述的锁定原则冲突。建议在 JSON `limits` 或明细脚注加一句说明该例外。我尝试远程核验该文件在 `7e52e6e0` 下是否存在，网络抓取失败（仓库疑似私有），无法匿名验证。
2. **【外观】明细 markdown 有 91 处 `。；` 拼接痕**（如 BT-18「…显式记录profile。；按选定profile…」）。是 JSON 列表项机械用 `；` 连接、又保留了各项结尾 `。` 的产物，纯渲染问题，不影响内容，合入前可顺手清理。

## 内容质量评价

计划本身的纪律性很强：四级状态（待实现/待验收/待核销/后置）定义清晰并明示「64 条≠64 个故障」；三条重点线（SHM/SDD/6.53 首日）的「已完成/应收尾/后置」切分与明细逐项对得上，未发现矛盾；依赖图（P01→P03→P04→P05→P06、P03→P10/P14）与 mermaid 及批次文字一致；「只拆包不拆业务仓库」「运行日≠行情目标日」「无触发写未触发」等边界反复贯彻；限制一节如实声明了未登录宿主、未读外部 VM 冻结目录。逐片 GO 沿用原域授权、不批量 default-on 的收尾原则与 §7 交接格式是合理的治理约束。

## 结论

**可合入**。结构、数字、溯源链、代码断言均经得起核验；仅上述两处轻微问题（未解释的后快照 SHA 链接、91 处 `。；` 拼接痕），可在本次或后续小改中处理，均不构成阻塞。
