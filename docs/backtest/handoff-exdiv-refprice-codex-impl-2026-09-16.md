# 交接 · 除权日参考价修正片 实施（Codex 接手）

> 日期：2026-09-16
> 状态：✅ **A/B/C 已落地**（人裁 PX-1…PX-7 全部「是」）。切片 D 宿主-only，见 runbook 注记；勿在 CI/本 PR 宣称 D 完成。
> 权威对象：[plan-exdiv-refprice-2026-09-16.md](plan-exdiv-refprice-2026-09-16.md)（v1.1）。
> 评审链（施工图）：[zcode-facts](../architecture/reviews/2026-09-16/plan-exdiv-refprice/zcode-facts.md)（5 触点精确行号锚 + 数据层契约）/ [zcode-arch](../architecture/reviews/2026-09-16/plan-exdiv-refprice/zcode-arch.md)（**边界向量 T1–T16** + E-R5 收窄措辞 + 残留声明）/ [merge-consensus](../architecture/reviews/2026-09-16/plan-exdiv-refprice/merge-consensus.md)。
> 分支：从当时 master 开 `feat/exdiv-refprice`；A/B 分 commit；**与 PR #81（v8 v2）同文件不同区域，后合者 rebase**。

## 0. 硬边界（勿越）

1. 只修参考量：`rescale_position`（csv_ledger 新纯函数）+ 5 处 prev_close 映射（helper 传入）；**成交价/估值/shares/佣金/T+1/chase 判定逻辑一行不碰**；任何 `*_rules.py`、v7、E-R1–E-R4、湖数据不动。
2. 事件门 = **ex_date_index 主 ∪ 跳变>1e-2 兜底**；k = 因子行比（LAG 型）；**禁用 dr 数值**；噪声带 ≤0.5% 不修正。
3. **布线锁：`simulate(..., exdiv=None)` 显式参数，仅 `run()` 加载**——直接调 simulate 的既有测试必须拿到与 master 逐字节一致的结果。
4. 文件缺失/读失败 = 空 map + 一次性 stderr，禁止抛异常（CI data-free）。
5. 新 stats 行条件打印（防 np3_layering summarize golden 红）；UTF-8 无 BOM、NUL=0。

## 1. 切片 A · exdiv_map.py

- `load_exdiv_ratios(codes, start, end)`：读窗含 warmup；pyarrow 下推（stock_code in codes）只读 date/stock_code/cumulative_adj_factor 三列；事件门 ∪ 兜底；LAG 行比；normalize_date 双格式兼容。
- 单测：合成 parquet（复用 `test_exdiv_hold_hits.py:137-163` 模式）——事件枚举、兜底触发、噪声带过滤、NaN/缺行跳过计数、文件缺失空 map、warmup 边界。

## 2. 切片 B · 引擎接入

- `csv_ledger.rescale_position(pos, k)`：`pos.cost *= k; pos.peak *= k`（peak_hm 不动）。
- 日线：缩放+映射在 :260-261（prev_close 替换）与 :266（lot 环）前；分钟：:859-867 与 :872-874（**绝不**插在 :875 与 :902-903 之间）。
- 共享 chase（`csv_simulate_loop.py:129-131`）与 pool 买（:195-202）的 closes[-1] 经 helper 映射。
- `simulate(..., exdiv=None)` 参数贯通两引擎；`run()` 调 `load_exdiv_ratios`。
- stats 三键（exdiv_adjusted_lots / exdiv_prev_close_mapped / exdiv_skipped_no_factor）条件打印。
- 单测按 arch 向量表 T1–T16（必收 T1 假止损消失 / T3 假成交消失 / T4 touch 止损 D 域成交价 / T5 band 一致性 / T8 chase 到期=除权日 / T9 pool 涨停挂 chase / T11 停牌跨界 / T14 检测门 / T15 空 map 逐字节）。

## 3. 切片 C · 文档

- `engine-ashare-correctness.md`：E-R6（含残留三句）+ E-R5 收窄（arch §4 措辞：噪声带近似 + 历史数字「修正前口径」标注）。
- 两引擎 HELP_LOCK 一行 + README 一句。
- **三份历史文档加「修正前口径」脚注**：er5-recheck-5e8-note / np2-exdiv-hold-hits-host-note / v8-pername-capital-requirement-note。

## 4. 切片 D · 宿主验证（宿主执行，非合入门）

v1 规则 5 亿分钟重跑：预期止损 149→~120–144、总亏损回收上界 +35~125 万（≈0.01–0.025pp）——短记**预写此量级防「12% 回收」误读**；research_false_stops 前后对照；顺带跑 facts §3 三项停牌实测。完成后**放行 v2 切片 D**（通知宿主 agent）。

## 5. 门禁

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
```

完成后缺陷优先复核（重点：csv_simulate_loop diff 只允许 helper 传入、golden v1/v6 绿、空 map 逐字节对照），回写 plan 状态与本交接完成标记。

## 6. 完成标记

- [x] 切片 A · `exdiv_map.py` + tests
- [x] 切片 B · 引擎 5 触点 + `rescale_position` + `simulate(exdiv=)` + T1–T16 必收向量
- [x] 切片 C · E-R6 / E-R5 收窄 + HELP_LOCK×2 + README + 三份历史脚注
- [ ] 切片 D · 宿主 5 亿重跑（**host-only**；见 [exdiv-refprice-slice-d-host-runbook-2026-09-16.md](exdiv-refprice-slice-d-host-runbook-2026-09-16.md)）
