# Plan:市场 regime 基建统一(market_regime 泛化)

- 日期:2026-10-18
- 状态:**已人裁(Human:方案 A)**;实现按切片独立 PR
- 上游:#480(bigvalue 共享基建)、#490(data_provenance 指纹)、[topk tracker §6.11/§12](topk-joint-research-tracker-2026-09-22.md)、[plan-strategy13 S3](plan-strategy13-beidou-volume-start-2026-10-17.md)

## 0. 人裁(2026-10-18)

「把大盘闸做成 bigvalue 式共享基建」→ **方案 A:泛化 bigvalue_regime 为序列无关的 market_regime 核心**;`bigvalue_*` 旗与契约原样保留;新增 `--index-regime-*` 族共享核心;`--index-ma5-gate` 降级兼容别名;策略 13 S3 直接消费。**不动** 6.x `load_book_index_gate`/version12 MA10/海龟 MA10(卖点侧冻结书)。

## 1. 动机

同一「环境闸」思想已四份实现:topk 的 `--index-ma5-gate`(A/B 最强,+20.97% 旧引擎)、6.45+ 书族 loader、`bigvalue_regime.py`(共享)、策略 13 S3(计划用 6.45 loader——但其 MA60→半仓/MA120→三成梯度语义 6.45 没有)。而 bigvalue 机器本身已是通用的:`date/value/ma_fast/ma_slow` → 状态 → 确认 N 日 → 执行日标签 → 挡/清/资金投放。指数闸全部同构(上证 MA5 = 快线=收盘、慢线=MA5;HS300 60/120 = 快慢均线对)。

## 2. 设计

### 2.1 核心 `backtest/research/market_regime.py`

- 逻辑自 `bigvalue_regime.py` 平移并中性化:`load_regime(path, fast, slow, *, value_col="bigvalue")`(value 列名参数化,默认不变)、`states`、`confirmed_days`、`flatten_reason`、`regime_cash_fraction`(原 golden_cash_fraction)、`with_regime_gate`(原 with_bigvalue_gate)
- **fast=1 特例**:快线即 value 本身(不要求 ma1 列)——使「收盘 vs MA5」无需伪列
- `bigvalue_regime.py` 变薄壳 re-export(旧导入/测试零改动)

### 2.2 CLI(books parser;`topk_dropout` 起步,策略 13 接续)

`--index-regime-file / --index-block-new / --index-flatten / --index-golden-mult / --index-base-frac / --index-ma-fast / --index-ma-slow / --index-confirm-days / --index-signal`——与 bigvalue 族逐条镜像,同一引擎接线。

- **一跑一个 regime**:bigvalue 族与 index 族互斥(明确报错);`--index-ma5-gate` 变兼容别名 = index 族(湖外显式文件,SSE,fast=1/slow=5/confirm=1)且与显式 index 族互斥
- 指数数据走文件制(与 bigvalue 对齐,预计算、`data_provenance` 自动指纹):生成器就用通用脚本 `scripts/data/bigdata_ma_cross.py`(`--value-col close --ma-windows 5` 或 `60 120`,喂指数收盘 CSV);是否补一个湖内指数直出小导出器,随策略 13 S3 实施时定

### 2.3 消费方

- topk_dropout:双族旗;HELP_LOCK 更新(topk master-close 冻结 fixture 随之重冻结——既有流程)
- 策略 13 S3:HS300 的 `--index-regime-file` + block-new(MA60 档=快线,MA120=慢线,confirm=2);原 S3「复用 6.45 loader」表述作废
- bigvalue 现行为/默认/旗名:零变化

## 3. 切片与验收

| 刀 | 内容 | 验收 |
|---|---|---|
| S1 | market_regime 核心 + bigvalue 薄壳 + 单测平移 | bigvalue 全套契约测试**原样绿**;默认路径逐字节回归 |
| S2 | index 族旗 + index-ma5-gate 别名映射 + 互斥 + HELP/fixture 重冻结 | data-free 单测;同窗 A/B:旧 `--index-ma5-gate` 与「SSE 文件 fast=1/slow=5/confirm=1」结果一致 |
| S3 | 策略 13 接线(+指数文件生成说明) | 策略 13 S3 冒烟 |

风险:HELP 冻结契约更新是已知机械流程;index-ma5 旧语义(信号日=前一上证交易日)与 confirmed_days 的 prior-session 口径一致,映射无歧义。

> **S3 收口(2026-10-18)**:策略 13 的指数闸已由并行会话独立实现并随 r11b 冻结(#488,`build_index_caps` 双档敞口上限,语义与本核心不同且更富)。为不动冻结书,S3「策略 13 接线」**作废**;market_regime 核心留给后续消费书。
