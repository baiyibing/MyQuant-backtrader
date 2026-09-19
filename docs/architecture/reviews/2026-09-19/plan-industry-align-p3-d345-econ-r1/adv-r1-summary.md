# adv-r1-summary — P3 δ3–δ6 economics plans (Codex adversarial)

> 日期：2026-09-19（Asia/Shanghai）  
> 对象：五份 docs @ PR #124 HEAD `1e9994e`；`IMPLEMENTATION_BASE=1049b90`  
> 三路：dissent-steelman / domain-safety / pattern-evidence（host-parallel `codex exec` · `gpt-6-astra` · `xhigh` · workspace-write）  
> 启动：`_run_adv_host.py` → `_host_launch_summary.md`（三路 rc=0；~406–502s）  
> 计票：**对抗草案不计独立票**；本摘要供 classic fan-out / merge-consensus 取证。

## 三路总览

| 路 | 结论标签 | 要点 |
|---|---|---|
| dissent-steelman | **REQUEST CHANGES**（验收充分性） | DS-1 δ5 partial 后扫描；DS-2 δ6 无 bar NAV；DS-3 held-None 自然可达性；DS-4 qlib band；DS-5 v7 真实接线 pin；DS-6 期初权利窗口 |
| domain-safety | **GO-WITH-NITS** | DS-01 δ6 raw close 域前提；DS-02 δ4×δ3 qlib band；DS-03 δ5 D6 loader 前缀因果 |
| pattern-evidence | **GO-WITH-NITS** | PE-01 δ4 named-band 前提；PE-02 δ6 raw close 过度断言；明确不复用 chip/StockDataReader |

共同否定项（三路一致，**无生产泄漏**）：
- base→HEAD 仅五份 Markdown；生产/测试相对 `1049b90` 零 diff
- 未发现 Mode B fractional / `shares/=k` 被写成经济已关；δ6 C 边界成立
- 未发现 P1/P2/P4 被本包重开；F-R1–10 形式齐全
- 未发现 ghost test 路径；§8 命令语法/文件存在性 OK（**不等于已跑绿**）

## host 抽验（对抗共享事实）

| ID | 主张 | host | 处置建议 |
|---|---|---|---|
| **ADV-R1** | δ4 书侧「未知板块→早拒」缺 `qlib_limit_pct`/named-band 前提；δ3:32 已钉例外 | ✅ `csv_common.py:80-81` 固定 band 绕过 named limits；`csv_strategy_books.py` 有 hook | **must-fix 文档**：δ4 §2 表收窄前提（三路共指） |
| **ADV-R2** | δ6:28 「raw close」写成估值函数普遍属性 | ✅ `csv_ledger.py:173-178` 只取传入 close；域由入口决定 | **must-fix 文档**：标明 none/raw 路径前提 |
| **ADV-R3** | δ5 partial / 无 bar NAV / held-None 可达性 / 接线 pin / 期初权利 | 多为 **未来 Slice B 验收合同缺口**，非本 PR 假断言或 freeze 泄漏 | **黄项→Slice B / § notes**；不挡 docs 人裁入口 |
| **ADV-R4** | production freeze / C creep / P1–P4 bleed | ✅ 未发现 | 维持工作假设 |

## must-fix（建议回填 plan 正文，属 as-built 表述勘误）

1. **δ4 §2 未知板块行**：显式「默认 named-band、`qlib_limit_pct=None`、非 ST；固定 band 为独立例外路径」。
2. **δ6 §2 书 NAV 行**：改为「消费传入 bars 的 close；默认 none/raw 路径才是 raw mark」。

## 黄项 / nits（记入 merge-consensus；优先不整篇改写）

1. δ5：首次触发零/部分成交后扫描游标、rider、peak/mark（dissent DS-1）
2. δ6 B：无 bar 日估值与登记→清仓→到账窗口初态（DS-2/DS-6）
3. δ4：held-None 自然可达 vs seed-only；δ3 C 后须重做可达性交接（DS-3）
4. δ3：真实 `load_pool_names_by_day→context→simulate_v7` 接线 pin 升为必需（DS-5）
5. δ5 D6：loader 整日零量过滤 vs 容量 oracle 前缀因果（domain DS-03）
6. §8「禁止 CLI」措辞：与既有 stubbed `main()` 单元测试并存时需限定「宿主/真实 I/O」

## 对人裁工作假设的对抗立场

| 项 | 对抗综合 |
|---|---|
| δ3=A | 可保留；补接线 pin 与 δ4 交接说明 |
| δ4=A | 可保留（收窄表后）；反对把 seed held-None 当自然风险已复现 |
| δ5=B(design) | 可保留；partial 状态表未完成前勿收口 `.3=A` 为「已设计完」 |
| δ6=A（+optional B） | 可保留；B 须答无 bar/期初权利；**prod 仍须显式 C** |
| P1/P2/P4 | **继续 deferred** |

## 下一动作

1. classic multi-ai fan-out（独立席位）→ `merge-consensus.md`
2. 若 fan-out/host 确认 ADV-R1/R2：小 errata 回填同分支并 push 更新 #124
3. **等人裁**；人裁 GO 前禁止编码 / 禁止开 feat
