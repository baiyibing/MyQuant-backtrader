# cursor-desktop 评审（host 空槽）

> 待评审：`docs/backtest/plan-strategy7-turtle-csv-minute-2026-09-11.md` v1.1 → 综合后 **v1.2**

对抗层：`review-by-cursor.md`（不计票，已回填 v1.1）。  
fan-out 四家 rc=0。本槽不重复打分，裁决见 `merge-consensus.md`。

## host 本轮只锁这些

- 指数暖机 **11** 个交易日（claude R1）。
- 新开 14:55 / 加仓盘中（codex R1）。
- 交替止盈公式 + 分档已卖账本（cursor-auto R1–R2、codex R3）。
- `--pool-dir` 由 v7 解析，禁 `pool_dir=None`（codex R4）。
- 减试错后 3b 次分钟可立即全清 = 数字后果，补单测，不发明重新穿越（kimi R1 → 选 (a)）。
