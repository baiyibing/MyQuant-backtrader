# merge-consensus · fill clock plan r3（v0.4 @ 049cd29）

- 主持：qmt。日期：2026-09-19。席位：codex、cursor:kimi-k3-high、cursor:auto、grok。claude 空槽。计证据，不计票。
- r2 两条（追买缺报价的持仓/指数门、§9 Linux/CI 合同）正文已落地。Kimi 核对过代码事实层。
- 裁决：**仍不能进人裁 GO，不能编码。** 再改两处，然后第四轮。

## 必须回填

1. **删掉不可达的实施基线 SHA。** 主持在 r2 回填指令里写进了这个 SHA。r2 共识只要求「固定完整 SHA、禁止用 merge-base 现算」，没有给出任何值。本机 `git cat-file -t` 报 bad object；`git fetch origin <sha>` 报 `upload-pack: not our ref`。`origin/master` 实为 `c44da87b01ebcc6a68633307eba0fce48940f403`。档头、§7、§9、H4、H5 对该基线值及来源的表述都是错的。改法：bash 里的值换成这个已存在的 master tip，并写明「若人裁当日 master 已前进，换成当时的完整 SHA，禁止再填不可达对象」。§9 在祖先检查前加 `git cat-file -e "$IMPLEMENTATION_BASE^{commit}"`，把对象不存在和有 diff 分开。仍禁止 `git merge-base HEAD origin/master` 现算 SHA。
2. **策略 5「有 14:50 bar 就不到 14:57」不成立。** `csv_minute_backtest.py` 在强卖时间碰到跌停 bar 会 `continue`（收盘跌停，以及开盘跌停提前跳过）。改 plan 约第 52、82 行和勘误 E3：满足 T+1 且该 bar 不是跌停时，策略 5 可以在 14:50 返回；14:50 跌停则继续扫。不改扫描器，不加「有 14:50 就禁止 closing_call」的测试。

## 不升级

numba 导入顺序、parity 可能被 skip、`rg` 不是 CI 必装、追买 `chase_decision` 准入、`run_chase_due_day` 观察口、14:56、冻结表未含 modeb、枚举名，仍是黄。本轮不要求一次写完。禁令不放宽。

## 下一轮

只改 plan 消化这两条，推回 #109，再跑同一四席。无新红才进人裁。
