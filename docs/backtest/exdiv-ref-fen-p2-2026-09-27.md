# 除权参考价到分 P2 实现冻结（2026-09-27）

P1 已合并（#228）。本文为 P2 实现冻结记录，现已合并 #229。
合同见 [计划 §2 / §4](plan-minute-stop-and-exdiv-fix-2026-09-26.md)。
冻结时 P3 真湖 A/B **未做**；后续归档见文末，不代表默认切换 GO。

- 仅共享分钟 CLI 注册 `--exdiv-ref-fen`（store_true，默认 OFF）。
  main → run → simulate 传递；日线 / v7 不注册，共用参数表不变。
- R1：`mapped_prev_close(..., fen_round=False)` 保留默认乘法结果。
  ON 且成功映射时，对乘法结果用 `Decimal(str(mapped)).quantize(Decimal("0.01"),
  rounding=ROUND_HALF_UP)` 到分，再计算涨跌停。无事件 / 无映射的 raw 原价不舍入。
- 参数传到普通持仓扫描、时序现金引擎、共享买入 / 追买 / 加仓、尾盘切片和
  TopK 分钟买入参考价，避免同日买卖基准不一致。共享 helper 默认仍 False；
  日线调用不变。EOD 信号参考价与 version12 自有路径不改。
- R2：仅 ON 时 `load_exdiv_ratios(..., noise_eps=0)`，已登记 ex-date 的任意非零
  因子变化都可进入 map。无 ex-date 的 fallback 门槛仍为 1%；不扩展事件识别。
  持仓缩放仍使用原 k，不把 k 或成本舍入到分。
- R3 配股价未做；R4 version12 / front 仍跳过 E-R6 loader，exdiv=None 原价不变。
  默认 OFF 不增加 state 字段，不改变旧输出。

合成验收纠正计划原算术笔误：10.00 × 0.5 = 5.00；若要得到 5.003，
可用 10.006 × 0.5。到分后 5.00，对应涨停 5.50 / 跌停 4.50。
5.003 × 1.1 = 5.5033，到分是 5.50，并非 5.55，因此该例本身不能展示限价差异。
另以 10.01 × 0.5 = 5.005 验证 HALF_UP → 5.01：跌停从未先到分的
4.50 变为 4.51，涨停 5.51。微额分红 k≈0.999 在 OFF 被过滤，ON 映射到 9.99。

测试覆盖 helper 半分、缺失映射、微额分红与 fallback 边界、普通 / 时序现金
限价、默认与显式 OFF 完整 state 一致、CLI → run → loader / simulate、
version12 / front 跳过 loader、日线 / v7 拒绝参数。另运行共享 helper 相关回归；
本地验证结果见 PR。冻结时不声称全 CI 或 P3 已完成。

本地验证：以下扩大集 1179 passed，2 条既有 pandas 弃用警告；随后追加三个
买入 / 半分边界断言，新文件单跑 22 passed。四项 data-free CI 路径门禁通过。

```bash
OSKH_MERGE_PYTHON=/tmp/pr206-venv/bin/python /tmp/pr206-venv/bin/python -m pytest -q \
  tests/test_exdiv_map.py tests/test_exdiv_refprice_engines.py \
  tests/test_csv_minute_backtest.py tests/test_exdiv_ref_fen.py \
  tests/test_csv_daily_backtest.py tests/test_csv_daily_backtest_v8.py \
  tests/test_csv_simulate_v8_hooks.py tests/test_minute_cash_*.py \
  tests/test_tail_window_*.py tests/test_topk_minute_exec.py \
  tests/test_minute_stop_trigger.py tests/test_s12_price_domain.py \
  tests/test_s11_exit_domain*.py tests/test_ashare_simulate_import_fence.py
```

2026-09-27 后续：[P3 4090 真湖 A/B 记录](stop-exdiv-p3-ab-2026-09-27.md)（`20260927e`）已归档。
s8 fen on 相对 off 的 NAV 在 close / hl 下均约 **−7.7k**（资金 `5e8`）；s12 本窗 fen off ≡ on，NAV 字节一致。
后者与 R4 / version12 自有除权语义一致；本窗无可见效果，默认仍 **OFF**，不翻默认。
