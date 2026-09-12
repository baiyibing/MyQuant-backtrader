# cursor 对抗综合（host，不计独立票）

评审对象：`docs/backtest/plan-pool-pipeline-r0r1-2026-09-12.md` **v1**  
三路：dissent-steelman / domain-safety / pattern-evidence（2026-09-12）  
回填：plan **v1.1**

## 1. 主笔让步

1. **`name_asof` 必须 `ymd<=ds`。** 「向前扫描已加载整窗」无上界 = 后日赢换皮。补断档回退与「后日 `*ST` 不得污染前日」；分钟对等注入。
2. **扁平 `pool_names` 保持 `dict[str,str]`。** 只加可选 `pool_names_by_day`。后日赢不得继续当生产契约。
3. **C 默认文档降级。** 日线/分钟加载器不读 `volume`。落地才 ≡ 缺 K（pending / 追买不 pop / 不更新 peak / 净值按缺行）；同路径探测；禁止筹码读法；禁止与 D 互验。
4. **R0 只解析 `持仓标的列表:`。** 仓内 fixture。胶水放 `scripts/data/`，不进 `scripts/research/`，不是第二份 Qlib 导出 SSOT。
5. **R1 去掉「约 30 行」。** validate = 严格六位门；`run()` 不因此 SystemExit。外仓 README / 路线图 §8 移出完成定义。
6. **无名 ST 失真扩到 300/688/920。** 不当 E-R2 验收。

## 2. 未让步

- 不重写引擎；不改卖点；不改 `presets.py`。
- R0 不写 `stock_pool/`；不喂策略 7；不用 R0 净值判断模型。
- 不在本仓实施 R2/R3/R5。
- 不为 R0 编造名称列。
- 不删 Cerebro；不复活 `engine.py`。
- **胶水可留本仓**（人裁「以本仓为主」）。反对「必须搬去 MyQuant」。

## 3. 勘误表（已回填 v1.1）

| 对抗 | 回填 |
|------|------|
| 三路：名称回退看未来 | P-R2 `ymd<=ds` + 三条单测 |
| dissent：扁平签名不可逆 | 只加 `pool_names_by_day` |
| 三路：后日赢双 SSOT | `run()` 禁 `load_pool_name_map` |
| 三路：加载器无 volume | P-R3 默认降级 |
| domain：pending/追买/peak | 落地才 ≡ 缺 K |
| dissent：R0 双源解析 | 只认列表 |
| pattern：`scripts/research/` | 改 `scripts/data/` |
| pattern：外仓完成定义 / 30 行 | P-R6 / 切片 E |
| domain：无名 ST 全板块 | §1 / P-R5 / §6 |

## 4. 结论

v1 按原文实施会在 B（未来名称）和 C（无 volume 列却改热路径）上出错。v1.1 把 as-of 谓词写死，把停牌改成默认可降级，把 R0 收成「本仓胶水、不是导出 SSOT」。对抗不计票。下一步 classic fan-out（codex + Cursor Kimi + cursor:auto + claude），host 综合 `merge-consensus.md`。
