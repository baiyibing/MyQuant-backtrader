# plan-industry-align-next-2026-09-19 v0.2 — 三路对抗评审勘误（host 裁决）

> 日期：2026-09-19  
> 路线：dissent-steelman / domain-safety / pattern-evidence  
> 对象：`docs/backtest/plan-industry-align-next-2026-09-19.md`  
> 结论：三路均给出 **BLOCKING**，host 复核红项属实；已回填 v0.2（仍 Draft / not-GO）。  
> 说明：Grok Bot 盒子路径 `/workspace/wt-industry-align-impl/...` 在当前工作区不可见，本次先落 host 勘误权威表。

---

## 三路总裁决

| 路线 | 裁决 | host 摘要 |
|---|---|---|
| dissent-steelman | **BLOCKING** | §7 使用仓内不存在的 gate 命令，DoD 不可执行（E-01）。 |
| domain-safety | **BLOCKING** | halt/zero-volume 冻结证据锚点引用错位，且 v7 已知分叉 pin 未完全复用（E-02/E-03/E-05）。 |
| pattern-evidence | **BLOCKING** | 冻结面少列真实在路径 helper，且 add-side fail-open pin 未写入 Slice A DoD（E-04/E-05）。 |

---

## host 现场抽验（file:line）

- Gate 脚本存在性：`scripts/gates/verify_oskh_data_contract.py`、`verify_data_path_ssot.py`、`verify_no_hardcoded_machine_paths.py`、`verify_tr_bridge_import_ssot.py` 均存在；`scripts/run_common_package_contract_gates.py` 与 `scripts/run_stream_execution_contract_bundle.py` 在本仓不存在。  
- Halt/zero-volume：`tests/test_csv_daily_backtest.py:990+` 明确覆盖 zero-volume placeholder 日的不可买卖与 last-close 标记；`:964` 是 mark/equity 口径测试，不是 freeze/no-trade 主锚。  
- Sell-side None-limits fork pin：`tests/test_ashare_simulate_predicates.py:119-134` (`test_none_limits_sell_side_records_existing_split`) 已存在且可复用。  
- v7 add/sell `limits=None` gate-pass 路径：`backtest/research/csv_minute_backtest_v7.py:342-353`, `:367-373`, `:402-405`；谓词定义 `backtest/research/ashare_session.py:73-78`。  
- 真实 on-path helper：`backtest/research/csv_common.py` (`book_limit_prices`) 与 `backtest/research/market_layer.py` (`limit_pct/limit_prices`) 明确在 limit 计算链路上；`backtest/research/csv_daily_loader.py` 提供 zero-volume 日过滤输入。

---

## 勘误表（E-01..E-05）

| ID | 严重度 | 问题 | host 裁决 | v0.2 回填 |
|---|---|---|---|---|
| E-01 | 🔴 BLOCKING | §7 要求运行仓内不存在的 ghost gate 脚本 | 属实，必须替换为真实 `scripts/gates/*` 四脚本 | ✅ 已改：删除 ghost 脚本，替换为四个真实 gate 命令 |
| E-02 | 🟡 | halt/zero-volume freeze 锚点用到 `:964`（仅 mark/equity） | 属实，freeze/no-trade 应主锚 `:990+` | ✅ 已改：`:990+` 作为 freeze/no-trade，`:964` 降为 mark-only |
| E-03 | 🟡 | 未显式复用现有 sell-side None-limits 分叉 pin | 属实，应复用 `test_none_limits_sell_side_records_existing_split` | ✅ 已改：§2 和 Slice A 增加该测试锚点/复用要求 |
| E-04 | 🟡 | 冻结表未覆盖真实 on-path helper | 属实，应补真实路径，禁止臆造 | ✅ 已改：补 `market_layer.py`、`csv_common.py`、`csv_daily_loader.py` |
| E-05 | 🟡 | Slice A DoD 未点名 add-side fail-open pin | 属实，需单列 held add-side gate-pass ≠ fill | ✅ 已改：Slice A DoD 增加 add-side `limits=None` pin + post-gate non-fill 断言 |

---

## 余项与边界

- P1–P4 继续默认 **A=keep deferred**；不重开 #112 的 B/C 行为改动。  
- 本轮仅 docs 纠偏：不改生产 Python，不跑 backtest。  
- 仍需后续多模型 fan-out 复核 v0.2，再走人裁 GO。

---

## 下一步

1. 以 v0.2 文本作为新评审对象。  
2. 触发一轮 multi-model fan-out（同三路）检查是否还有新的 🔴。  
3. 若无新 🔴，再做人裁；有新 🔴 则继续 docs 勘误，不进入实现。
