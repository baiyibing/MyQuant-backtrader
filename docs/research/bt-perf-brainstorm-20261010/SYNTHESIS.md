# BT 回测性能头脑风暴合成（2026-10-10）

成员：Codex / Cursor / Grok（三份 DONE）· 主持 bt · 对照 PR #456 `7ca63b5`

## 共识

1. **#456 方向对**：动作后重进 Numba，安静 bar 回核；`held_eval_bars` 542k→16k 量级可信。
2. **不要宣传墙钟 21×**：冷/热缓存混杂；看 `held_scan` / 评估 bar，不看整段墙钟。
3. **暂不无条件合**：master/CI 本就红；需 base/head 失败归因 + 同缓存配对差分；仅三 CSV 字节相同不够。
4. **下一刀靶子已变**：安静 bar 已打掉 → 优先削 **Python 包装 / 每持仓日装配**，以及热缓存下仍贵的 **装载**。
5. **绝不动**：卖点/账本顺序、行业规则、决策价、启发式跳 bar、吞 ST/缓存身份换绿。

## 下一刀（三方重叠）

| 优先级 | 项 | 谁提 |
|---|---|---|
| P0 | 包装静态化：数组/梯子参数绑一次，动态状态仍每动作刷新 | 三方 |
| P0 | held_scan 用 `searchsorted` 替代 `_previous_rows` 掩码；6.53 无 sell_gate 时不建无用 prev_closes list | Cursor/Codex/Grok |
| P0 | 去掉仅为计数扫安静 bar 的 Python `count_quiet` | Codex/Grok |
| P1 | `to_numpy(..., copy=False)` 与池买侧对齐 | Cursor |
| P1 | 湖/缓存日期·row-group 下推（新进程装载） | Codex/Grok |
| P1 | 测 `post_group` 0.4→0.9 回归是否可收回 | 三方 |

## 产物

- `report-codex.md` / `report-cursor.md` / `report-grok.md`
- PR：https://github.com/baiyibing/MyQuant-backtrader/pull/456
