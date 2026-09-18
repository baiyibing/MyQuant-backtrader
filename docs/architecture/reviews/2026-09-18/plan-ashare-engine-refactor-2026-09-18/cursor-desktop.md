# cursor-desktop 评审（host 席 · ZCode 主持）

> 待评审：docs/backtest/plan-ashare-engine-refactor-2026-09-18.md（v1.2 → 已回填 v1.3）
> 状态：✅ 已填写；综合裁决见同目录 [merge-consensus.md](merge-consensus.md)（本席 = 该文件的主持裁）。

## 🔴 必须修（均已回填 v1.3，host 亲验 file:line）

- **H1** v7 帧契约未钉：`_day_frame_records` 按 `frame["date"]` 切片（`csv_minute_backtest_v7.py:261`），书帧无 `date` 列（`ashare_bars.py:350-361`）——按字面换 loader 即 `KeyError`。→ §5-A 三选一写死 + 非空 bar 计数门。
- **H2** 谓词落点误置：`execute_buy`/`_sell` 纯填单（`csv_ledger.py:194-243`），谓词在 simulate 调用点；v1.2 文字会诱导改填单契约 / 把书侧 `limits is None` 先拒拧成放行。→ §5-B 改「调用点统一 + 不改填单契约 + 书侧 None 先拒 + `hit_limit_*` 保留」。
- **H3** 共享 cache 污染：`use_cache=True` 默认 + 键仅 `(start,end)`（`ashare_bars.py:551/397-399`），v7 小名单覆写会放大 6.6GB 缺码整读路径。→ §5-A v7 湖路径 `use_cache=False`。
- **H4** topk 共用 v7 `_load_cli_bars`（`csv_minute_backtest_topk_app_dropout.py:22-29`），「topk 不改」低估连带面。→ §5-A/§7 改述 + DoD 含 topk 合成窗非空。
- **H5** handoff 双 SSOT（§2 标题/§3 围栏/§6 清单未同步 v1.2）——系 host v1.2 回填遗漏。→ handoff 已全量同步 v1.3。

## ✅ 做对的地方

v1.2 对抗勘误（E-01..E-16）与代码一致，应保留；三仓守界 / T+1 / 复权 / 涨跌停盲区三席亲验全过；围栏改枚举方向正确（补锚点即可）。

## 总评

docs 流可收；**编码仍不可 GO**——人裁 P1–P5 是唯一开工闸。修的全程是实施指令精度，非架构。第二轮 fan-out 不开（未动 R\*/切片边界，见 merge-consensus 裁定理由）。
