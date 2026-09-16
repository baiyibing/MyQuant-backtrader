# 交接 · v8 规则 v2 实施（Codex 接手）

> 日期：2026-09-16
> 状态：**✅ 已人裁 GO（2026-09-16，PG-1–PG-4 全采纳）——交接已生效**。分支 `feat/v8-rules-v2`；切片 A/B/C 即做，**切片 D 挂 E-R5 复核结论后**。
> 权威对象：[plan-v8-rules-v2-2026-09-16.md](plan-v8-rules-v2-2026-09-16.md)（v1.1）。
> 评审链：[zcode-facts](../architecture/reviews/2026-09-16/plan-v8-rules-v2/zcode-facts.md)（含**断言翻转全清单 §4**——切片 B 唯一权威清单）/ [zcode-arch](../architecture/reviews/2026-09-16/plan-v8-rules-v2/zcode-arch.md)（含**边界测试向量表**——切片 A 必收 #6/#10/#14/#16/#20/#21/#22）/ [merge-consensus](../architecture/reviews/2026-09-16/plan-v8-rules-v2/merge-consensus.md)。
> 分支：从当时 master 开 `feat/v8-rules-v2`；A/B 分 commit。

## 0. 硬边界（勿越）

1. 只改 plan §7 落点表所列；`csv_ledger.py` / `csv_simulate_loop.py` / 成交核 / v7 / 1–6/9/10 书**一行不碰**。
2. 规则数学以 plan §1 表为唯一权威（档位开闭按业务原文、价格比较判定、px≥cost 前置、reason=`trail:band:1..5`）；发现表内未覆盖的边界语义 → **停下回写 plan**，不自裁。
3. 断言翻转只按 facts §4 清单（含 `tests/test_csv_daily_backtest.py:324`）；golden（v1/v6）必须不红。
4. `n_days: int = 1` 默认值与 4 参位置调用契约不变；`tests/fixtures/csv_engine_pre_er1/` 禁再生成。
5. 新文件/改动 UTF-8 无 BOM、NUL=0；验证命令一律 vanna312 全路径。

## 1. 切片 A · rules 重写

- `strategy8_rules.py`：band 数据化（arm=[0.06,0.15,0.50,1.00]、keep=[0.30,0.60,0.70,0.80]、档2 绝对底 1.02、档3 全局底 1.15）；**价格比较判定**（`peak` vs `cost×(1+arm)`）；`take_profit_reason` 头部加 `if n_days < 2: return None`；保留 `if px < cost: return None`；reason 按档序号；`record_strategy8_params` 键与 summarize 同步（旧键 profit_base/peak_dd_arm/peak_dd_pct 的消费点 `csv_daily_backtest.py:590-598`）；docstring/HELP_LOCK 全换（含档1 保本声明）。
- 单测：arch 向量表必收行 + facts §4a 重写（三参调用= n_days1 → 全 None 是机制不是 bug）。

## 2. 切片 B · 引擎放开 + 断言校准

- 删 `csv_strategy_books.py:105-106`（per_name→allow_add=False 覆写两行）——这是引擎侧唯一 diff。
- 按 facts §4b–f 翻转断言（推演后的期望值已给：如 `test_csv_daily_backtest_v8.py:88-93` 卖日 20251106@11.80 等）。
- 引擎级向量 #21：minute `scan_held_day` 注入路径 + daily `simulate` pending_exit 路径各一条。
- 验收：全量 pytest 绿 + fixture 窗 1–6/9/10 trades 逐字节不变。

## 3. 切片 C · 文档

- stale 文案四处：`strategy8_rules.py:92-96`、`csv_daily_backtest.py:152-153`、`csv_minute_backtest.py:99/108/110`、`README.md` v8 段；归档 money-modes plan 头加取代注记；plan §状态回写；pre_er1 禁再生成注记。

## 4. 切片 D · 宿主 5 亿重跑（非合入门，宿主执行）

双引擎 `--cash-total 500000000` 同窗重跑；必报 days==1 trail 占比前后对照、双引擎峰值并发（日线是资金风险侧）；research_* 四表再生成；超 5 亿 → 报业务四选项（plan §8）。

## 5. 门禁

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
```

完成后缺陷优先复核 diff（重点：`strategy8_rules.py` 的新函数与向量表逐条对；`csv_strategy_books.py` diff 只有两行删除），回写 plan 状态与本交接完成标记。
