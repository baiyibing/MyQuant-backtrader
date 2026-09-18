# merge-consensus · fill clock plan r2（v0.3 @ d86008c）

- 主持：qmt。日期：2026-09-18。席位：codex、cursor:kimi-k3-high、cursor:auto、grok。claude 空槽。计证据，不计票。
- 上一轮四条红（追买非固定 T+1、切片 C 必须改 as-built 错句、open_board 夹具先涨停再开板、IMPLEMENTATION_BASE 固定 SHA）已关闭。cursor 与 grok 都核对过正文与代码。
- 裁决：**仍不能进人裁 GO，不能编码。** 再改两处，然后第三轮。

## 必须回填

1. **缺报价不 pop 不是无条件的。** `csv_simulate_loop.py:131` 已持仓且不允许加仓时先清 pending；`:136` 指数门 `allow_new_name` 失败会 pop 并计 `skip_index_gate`。这两支都在 `quotes_for` 之前。只有过了持仓门和指数门、进入取报价之后，`quoted is None` 才保留 pending。改 §2.1、F-R4、测试表：合成用例注明「未持仓、指数门放行」。不改生产代码，不推翻「成交可以晚于 T+1」。
2. **§9 必须有一份和 CI 同构的 Linux 命令。** 合入工作流是 Linux：`python3 -m pytest -q -m "not production and not benchmark"`，再跑四个 `scripts/gates/verify_*.py`。裸 `pytest -q tests/` 会跑进读湖的 `test_oskh_data_integration.py`，与 F-R11 矛盾。`D:\anaconda3\...` 降为别名，不能当唯一合同。`git merge-base --is-ancestor` 仍允许；禁止的只是用 `git merge-base HEAD origin/master` 现算 SHA。

## 不升级

Kimi 无红，实验支持已回填的四条。cursor 把 Linux 合同和追买准入放在黄项，不构成反证。夹具细节（14:56 不进 fallback、昨收、modeb 进冻结表）仍是黄，本轮不要求一次写完。禁令不放宽。

## 下一轮

只改 plan 消化这两条，推回 #109，再跑同一四席。无新红才进人裁。
