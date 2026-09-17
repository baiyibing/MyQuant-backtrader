# 模式 A · 宿主跑数 runbook（统一卖出规则网格）

> **日期**：2026-09-17
> **状态**：✅ **宿主已完成 2026-09-17**（短记：[unified-exit-modea-host-note-2026-09-17.md](unified-exit-modea-host-note-2026-09-17.md)）。
> **权威**：[提案](stock-backtest-unified-exit-proposal-2026-09-17.md) §四/§十二；[handoff](handoff-unified-exit-modea-codex-impl-2026-09-17.md) §4。
> **前置**：PR #88（提案 + 预检脚本）与 `feat/unified-exit-modea` 均已合 master。

## 0. 硬边界

- 不改湖数据；不改 `*_rules.py` / 成交核 / 1–6/8/9/10 书。
- 名义现金池 11 亿（Q30）；峰值并发预期 ≤ 10.53 亿（N=20 无早退出上界，§9.7），**实测触 11 亿须在短记显著标记**。
- 结果随 front 分区每日刷新漂移是**已接受口径**（Q35=D）：报告头记当日指纹（可选留痕），不做一致性门槛。

## 1. 步骤（宿主）

1. 合入后重跑预检，留基线（约 4 分钟，exdiv 段最慢）：
   ```powershell
   D:\anaconda3\envs\vanna312\python.exe scripts/research/report_unified_exit_precheck.py
   ```
2. 跑模式 A 全网格（233 有效组 + 锚线 + 稳健性四件套）：
   ```powershell
   D:\anaconda3\envs\vanna312\python.exe scripts/research/run_unified_exit_modea.py --start 20251023 --end 20260909 --pool-dir stock_pool
   ```
3. Sanity 对照（全部来自 §9.7 预检，偏差大 = 实现 bug，先查再报）：
   - 实例 5061；封板跳过 ≈ 795；实开 ≈ 4266
   - 9 笔受冻实例（600929.SH / 002870.SZ / 002998.SZ 系）
   - 峰值并发 ≤ §9.7 ⑤ 表（N=1:88 … N=20:1053）+ 停牌延长余量
   - 规则 2 的 N=1 各组结果应与规则 1 的 N=1 **逐字节一致**（等价性内置校验）
4. 通读 top 20 排名 + 锚线（N=∞ / N=1 / oracle 上界 / 退市敏感性）+ 前后半窗一致性。
5. 落短记 `docs/backtest/unified-exit-modea-host-note-YYYY-MM-DD.md`：实际数字 vs 预检基线、top 组摘要、峰值并发、异常与 STOP 项。

## 2. 完成定义

短记落盘 + `backtest_output/unified_exit_modea/` 四类产物（排名 / 明细 / 汇总 / 稳健性）齐全。**本 PR / CI 不得勾选本切片为完成。** 后续（另行开工）：模式 B 分钟网格（届时评估迁移 4090 高配机）。
