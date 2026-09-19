# merge-consensus — plan-industry-align-next-2026-09-19 r1

> 日期：2026-09-19  
> 对象：[plan v0.2](../../../backtest/plan-industry-align-next-2026-09-19.md) @ `075cfc29408462991951873e239cb56ad33e6193`（IMPLEMENTATION_BASE=`41f3d11a34c665cc8a21b3e1d351b9e06b0466b5`）  
> 对抗前置：[adversarial-errata.md](../plan-industry-align-next-2026-09-19/adversarial-errata.md)（E-01..E-05 已回填 v0.2）  
> 本轮席位：codex / cursor-kimi-k3-high / cursor-auto / grok（claude=host 空槽）  
> 计票：**证据裁决，不投票**。host 对全部 🔴 亲验。

---

## 四路总裁决

| 席位 | 裁决 | 要点 |
|---|---|---|
| codex | **不可直接 GO** | R1 freeze 命令≠表；R2 Slice A 未覆盖 ST/停牌主目标 |
| cursor-kimi-k3-high | **修 R1 前不可 GO** | 冻结证明漏 3 文件；其余多为 NITS |
| cursor-auto | **R1/R2 修前不进实现** | 同 R1；E-R2 全称与分叉并存需钉口径 |
| grok | **按现文不可进实现** | G1=E-04 回填未完成（§8 改了 §7 未改）；G2 Slice A 可观测性不足 |

**主持综合**：方向正确（零行为变更、契约化书/v7 门禁分叉），**v0.2 文本不可进人裁 GO**。必须先回填下方 MC-* 成 **v0.3**，再开人裁；无新 🔴 则不必再开 fan-out。

---

## host 抽验记录（🔴 亲验）

- **MC-1 / R1 / G1 ✅**  
  §7 `git diff` 仅 9 文件；§8 表多出 `market_layer.py` / `csv_common.py` / `csv_daily_loader.py`。  
  三文件均存在且在 `limits is None` / 零量路径上（`market_layer.limit_prices` 未知板块→None；`csv_daily_loader` 滤 `volume==0`）。  
  按 §7 跑 freeze 改这三文件仍绿 → **假绿成立**。E-04 只改表、未改可执行命令，对抗回填不完整。

- **MC-2 / R2 ✅**  
  文首主船并列 limits / halt·zero-volume / ST name；Slice A DoD 仍以 `limits=None` + gate≠fill 为主。  
  ST 名称 PIT 分叉（书 `book_names_asof` vs v7 `flatten_pool_names`）与零量加载入口未在 Slice A 清单落成可编码测试行。  
  **不要求本轮改行为**，只要求契约落点与主目标对齐。

- **P1–P4 默认 A**：四路均未要求重开 #112 B/C；维持后置。

---

## 勘误表（回填 v0.3）

| # | 严重度 | 来源 | 勘误 | 回填落点 |
|---|---|---|---|---|
| **MC-1** | 🔴 | 四路 R1/G1 | §7 可执行 freeze 与 §8 **同一列表**（含 `market_layer.py` / `csv_common.py` / `csv_daily_loader.py`）。建议 `FROZEN_PRODUCTION_FILES=(...)` 一处定义。另恢复 worktree 门：`git diff --exit-code` + `git diff --cached --exit-code` 对同一数组；可选 base→HEAD changed-path allowlist（仅 docs + 点名 tests） | §7、§8 |
| **MC-2** | 🔴 | codex R2 / auto | Slice A 实施清单显式增加两行（仍 data-free、不改生产行为）：(1) ST 名称跨日分叉：钉书侧 as-of vs v7 窗末近似为**保留分叉**；(2) 零量/缺 bar：按日线·分钟·v7 **真实加载入口**引用既有测试或补测，区分「加载器过滤」与「模拟器无 bar 冻仓」 | §6 Slice A |
| **MC-3** | 🟡 | grok G2 / codex R3 | Slice A DoD 写清 v7 held-**add** 的测试落点：公开入口 `simulate_v7`（勿只测私有 `_buy`）；断言 gate 未拦 + post-gate `skip_cash`/无成交两态；注明 `run(..., **kwargs)` 的 v7 分支不转发 kwargs，测试须直接调公开入口或先修测试帮手 | §6 Slice A |
| **MC-4** | 🟡 | kimi / auto | §7 pytest 前置写明需 CI 同构 venv（`pip install -e .` / 工作流依赖）；裸系统 python 无 pytest 不构成 plan 失败 | §7 |
| **MC-5** | ⚪ | kimi R5 | 若文中仍有「待裁 P\*」口吻，改为「默认建议 A=继续后置；人裁确认」，避免读成重新开放 #112 | §4 |

---

## 对 P1–P4 的立场（供人裁）

| 点 | 四路 | host |
|---|---|---|
| P1–P4 = A 继续后置 | 一致支持 | **维持 A**；本船不重开 14:57 / trades 列 / 费率·ST PIT / 触价耦合 |

---

## 下一步

1. 回填 plan → **v0.3**（仅 MC-1..MC-5；不改生产代码）。  
2. 推 PR #114；**不再自动开 r2 fan-out**（本轮 🔴 均为文档可执行性，回填即可验证）。  
3. **等人裁**：P1–P4 是否全 A；人裁 GO 后才开 feat 实施切片 A→B→C。  
4. 合 docs PR ≠ 实施 GO。

