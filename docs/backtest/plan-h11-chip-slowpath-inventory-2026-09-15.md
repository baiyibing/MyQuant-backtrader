# H11：Chip / TR slow-path inventory（主题 D 软切片）

- 日期：2026-09-15
- 状态：已完成（Grok 核无有效 🔴）
- 父队列：[plan-hygiene-backlog-2026-09-15.md](plan-hygiene-backlog-2026-09-15.md)（软扩展；H1–H10 已收口）
- 主题：**D**（chip / TR 慢路径清点；**不是** full Rust rewrite / 算法重写）
- SSOT 清点：[chip/chip-slowpath-inventory-2026-09-15.md](chip/chip-slowpath-inventory-2026-09-15.md)

## 目标

把 chip / TR 相关代码路径按角色标清，方便后续「是否 offload」决策，本切片**只做 inventory + 指针 + 轻量桥接 import 门禁**：

| 桶 | 含义 |
|----|------|
| **Rust SSOT** | `turnover-resist` 已是规范实现；Python 经 bridge 消费 |
| **Python research consumers** | 研究 / 校验 / 名单读 Store；不改卖点 |
| **Cerebro Indicator fossils** | bt.Indicator / Cerebro 对照；观察退役，**不物理删除** |
| **Hot Python loops** | 仍热、值得日后 numba/Rust；本切片不改算法 |

## 交付

1. 本 plan
2. SSOT：[chip/chip-slowpath-inventory-2026-09-15.md](chip/chip-slowpath-inventory-2026-09-15.md)（路径表 + recommendation：`leave` / `later offload` / `fossil`）
3. 可选 data-free 门禁：`scripts/gates/verify_tr_bridge_import_ssot.py` + `tests/test_tr_bridge_import_ssot.py`  
   — 仅断言已知 TR bridge 入口仍指向 `oskh_factors.bridge.turnover_resist`（经 `oskh_core.turnover_resist_bridge` re-export 亦可）；**无湖**
4. `docs/backtest/README.md` chip 区指针；backlog **H10✓ H11✓**；主题 **A–F 仍开放**；**不扩 L2**；**不删 Cerebro**
5. Grok → `docs/architecture/reviews/2026-09-15/h11-chip-slowpath-inventory/grok.md`；修有效 🔴；**不 push**

## 明确不做

- 不改 simulate / 卖点 / 6/8 语义；不重写 chip / TR 算法
- 不做 full Rust rewrite；不把需湖 chip/TR 门禁塞进 CI
- 不扩 L2 交易/策略面；不物理删除 Cerebro / `chip_indicator` / ma_chip
- 无 Cursor CloudAgent；不 push

## 完成定义

- 清点表覆盖 Rust SSOT / research / fossil / hot-loop 四桶
- bridge import 门禁（或 pytest）本地绿、无湖
- backlog / README 指针；Grok 无有效 🔴；无 push
