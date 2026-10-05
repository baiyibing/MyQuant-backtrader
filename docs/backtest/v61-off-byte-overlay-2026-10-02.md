# version6_1 OFF 字节基线：scoped overlay（前例 #212）

`bee0b91` 注册第 20 本策略书 `version6_1`（无上限梯子止盈 + per_name 100 万独立组）。
提交留言明确：`test_off_byte_baseline` 注册表冻结（19 书）需后续走 scoped overlay
扩展（前例 #212 s8 overlay），本轮不擅自改冻结基线。

## 契约

- 历史文件保持不可变：
  - `tests/fixtures/off_byte_baseline_eff77f3.json` SHA-256
    `3bfe51b6d3e20b665c3fed0449ebf8569988022719da275b7fcc9635a9988c6c`
  - `tests/fixtures/off_canonical_baseline_eff77f3.json` SHA-256
    `34f611da359f1a1d059bc78be75b2e9e2458c533b1dc3b46cfd61130fca7a04e`
- 历史矩阵仍为 19 书 × 日/分钟 + 独立 v7 分钟 = 39 case。
- 新增书仅通过 additive overlay 进入矩阵：
  `tests/fixtures/off_byte_baseline_v61_20261002.json`
  （`version6_1/daily`、`version6_1/minute` 两 case；修订标识
  `v61-unbounded-ladder-2026-10-02`）。
- 录制：`python -m scripts.research.generate_off_byte_baseline --record-v61`
  （要求 pandas 3.0.6；已存在则拒绝覆盖）。
- 校验：`--check` 覆盖 27 未改历史 + 12 S8 校正 + 2 version6_1 增量 = 41 case。

## 相关

- 策略对照 / 入口 sol：[note-version6_1-sol-vs-version6-2026-10-02.md](note-version6_1-sol-vs-version6-2026-10-02.md)

## 非目标

- 不重写 / 不触碰 TopK frozen-bytes 或其它 byte snapshot scatter。
- 不改 MatchCore，不写湖。
- 不修改 S8 overlay 语义；仅把「非 overlay 历史 case」计数从
  `CASES - S8` 收窄为 `HISTORICAL_CASES - S8`，避免把新增书误当成历史字节契约。
