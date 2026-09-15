# money-modes / v8 每股预算：切片 D 烟测短记

- 关联：[plan v1.1](plan-money-modes-v8-pername-2026-09-16.md)、[交接](handoff-money-modes-v8-pername-codex-impl-2026-09-16.md)、[PR #61](https://github.com/baiyibing/MyQuant-backtrader/pull/61)。
- 执行环境：linux-vm；实际执行日期 **2026-09-15 UTC**（文件名沿用计划的 2026-09-16 标识）。
- 实施版本：A `c63c0a4`、B `12d1910`、C `092a96c`；烟测于 C 后执行。
- 状态：**已尝试，缺行情；跳过宿主重跑与分钟对照，非合入门**。没有生成 summary / equity / trades，不能报告实盘数据窗的收益或入选偏差。

## 尝试与 blocker

```bash
/workspace/vanna312/bin/python backtest/research/csv_daily_backtest.py \
  --strategy version8 --start 20251023 --end 20260909 \
  --out-dir /tmp/pr61-daily-per-name
```

退出码 1；日志 `/tmp/pr61-daily-smoke.log`：

```text
loading daily bars: 2322 codes, 20251013..20260909; pool 20251023..20260909 (215 days)
loaded 0/2322 daily series, 215 pool days
no daily bars in window
```

`resolve_period_root("1d")` / `resolve_period_root("1m")` 分别解析到
`/workspace/OSkhQuant1.3/stock_data/stock/period=1d` / `period=1m`，两目录均不存在。
只读检查，未下载、未合并供应商数据、未改 resolver 或写湖。

同窗 `backtest_output/csv_daily_v8_20251023_20260909/` 无基线工件。切换前代码参考为
**`c63c0a4cb1aaee8055a775559a98127e233e1b2d`，2026-09-15**：v8 为 daily_quota、20% 止损、有第一档武装、允许加仓；更早 scaffold 为 `9f4303c`。
**此 SHA 是代码基线，不是已有回测工件的来源证明**；宿主需补实际基线工件 commit、生成日期、池快照与窗口。

## 待宿主补全的统计

| 日期 / 窗口 | 名单宽度 | bought（池买 / 追买） | skip_cash / 跳过目标金额 | skip_held | 持仓代码数 |
|---|---:|---:|---:|---:|---:|
| 每交易日，20251023–20260909 | 待逐日汇总 | 缺行情 | 缺行情 | 缺行情 | 缺行情 |

名单按契约行序先到先得，现金不足整笔跳过，含佣金；上表用于呈现现金受限时偏向小代码的入选偏差。空缺不表示 0。

| 工件 | sizing | NAV 状态 |
|---|---|---|
| 切前 daily 同窗基线 | daily_quota | 工件缺失；不能与 per_name 做 NAV 排名 |
| 切后 daily 同窗 | per_name / 1M | 缺行情，未生成 |
| 切后 minute 同窗 | per_name / 1M | daily 未成功，按 M-R8③ 跳过 |

NAV 对照仅在同 sizing 的 daily / minute 工件齐备后补入；跨 sizing 只报告 lot 收益分布、胜率与单码敞口。
止损滑出分布待基于 trades 中 `stop_loss:*` SELL 匹配 BUY 的成本计算
`成交价 / 买入价 - 1`，并相对 -30% 报超出幅度的分位数、最差值与样本数；不更改 ledger stats。
匹配时须区分平仓后重新入场，不能把重复使用的 code/lot 编号跨持仓周期连接。

**P1 有/无武装 A/B**：真实窗口未运行，缺数据不能量化周转与收益影响。规则单测已验证：成本 10、峰值 10.10、现价 10.05 时，去武装后触发 `trail:band:2`；旧规则须先到 +6%，此例不触发。日线用例验证次日开盘离场，分钟用例验证当前 bar close 成交。这些是合成测试，不替代宿主 A/B；宿主 A/B 须固定 per_name 预算、止损 30%、池与行情，仅改变第一档武装。

## 恢复顺序与验证

1. 宿主提供可读湖与同窗同池切前基线，记录基线来源，保存旧工件。
2. **先重跑 daily v8 per_name**，核对 summary 的 `sizing=per_name`、`name_budget=1,000,000` 和窗口。
3. daily 成功后再运行同窗分钟版；同 sizing 的 caption 才可解释为卖点时钟差。caption 代码保持现状，流程锁已写回交接。
4. 补逐日表、同 sizing NAV、lot 级跨模式指标、止损滑出分布及固定其它参数的 P1 A/B；数字不写数据湖。

最终全量测试：**581 passed, 3 skipped, 1 warning**（既有 TR 非标准窗口警告），15.69s；日志 `/tmp/pr61-final-pytest.log`。策略 1/6 与切片 A 前基线 trades 逐字节一致，pre_er1 静态锚点未重生成。缺陷优先复核确认模式经策略书单点锁住加仓、现金预检复用原定股/佣金、追买失败 pop 后永久弃单、per_name 不保留日额度累加；禁改文件检查留在完成记录。

补充检查：四个 data-free gate 均通过（oskh_data contract、data path SSOT、machine-path、TR bridge）；`rg 'import backtrader|from backtrader' backtest/ tests/` 零命中。相对 origin/master 的禁改文件检查通过；修改文本 UTF-8 无 BOM、NUL=0，`git diff --check` 通过。
