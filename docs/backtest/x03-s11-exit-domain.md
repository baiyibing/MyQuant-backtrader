# X-03：策略 11 收盘退出 front 域与验收

本修复对应 [review README 的 X-03](../reviews/2026-09-25-minute-engine-review/README.md) 与 [#152](https://github.com/baiyibing/MyQuant-backtrader/pull/152) 的策略 11 双钟合同。日线、分钟共用布尔开关 `--fix-s11-exit-domain`，默认 OFF；库接口为 `fix_s11_exit_domain=False`。不引入新策略版本，不依赖 X-01/X-02 的行为代码。

ON 只接受 version11、raw lake 执行数据与独立 lake front 日线信号；日线 qlib/front/back、分钟 qlib/front 组合明确拒绝。收盘退出的 INITIAL 与 HOLD 都使用同一 front 序列：`previous` 是严格早于 T 的末值，SMA5 输入才拼上 T 的 front close。INITIAL 保持 `close <= previous`，HOLD 保持 `close < SMA5`；天然不足五根仍按旧规则不触发 SMA 卖点，不处理 X-20。

[旧 s11 handoff §0.1](handoff-version11-codex-impl-2026-09-21.md) 的“执行侧 none + mapped_prev_close”在 ON 时仅保留执行含义：raw 成交、raw mark、原限价参考映射与成本/峰值参考调整继续沿用；front 信号 previous 不再 mapped。参考映射不派送股票或现金，economics 默认 OFF。

日线仍收盘买，分钟仍严格 09:30 open 买；EOD 在买循环后写 pending，下一可成交开盘才卖。T+1、跌停保护、缺开盘/零量延期、volume=A 的未完成 09:30 桶、无追买、卖日不重入均保留。不开 X-02，不宣称已验证两修复的交互；在两 PR 各自验收后另跑交互矩阵。

ON 在第一笔成交前校验两域源文件、代码与窗口内实际历史：缺目录/代码/T/历史点、非有限或非正价格、非法 OHLC、重复日期、两域观察日期冲突均失败。采用保守合同，覆盖本次加载的完整预热窗口，而非仅截取末五根。旧 loader 不改；严格读取先于其静默去重/零量过滤。raw/front 零量过滤后的有效观察日期也必须一致，双方一致的停牌与单边丢失分开处理，不填造 bar。不因修退出重新导出池。这些检查与源字节 hash 只能证明本次消费数据的完整性/一致性，不能推定供应商完整快照或历史版本已验证。

OFF 不额外读 front；旧 trades/equity 格式和 `st.stats` 不增键。域和源哈希元数据在外层 `run_metadata`；开启 `--emit-run-manifest` 后写独立 `run-metadata.json`，其 hash 纳入 `run-manifest.json` 的 artifacts，不改 `bt_contract` schema。`entry_signal_domain=front` 是 v11 exporter 的输入合同，外来 pool 必须另有出处证明，不能由 flag 替它背书。执行参考描述为 `legacy_none_reference_map`，并记录实际加载状态；它不是用户显式提供的公司行动权益。

## 合成回放

按 AGENTS 的解析顺序选定实际解释器后运行（本 CI 环境使用 `~/.venvs/bt-ci/bin/python`）：

```bash
BT_PY=~/.venvs/bt-ci/bin/python
"$BT_PY" scripts/research/audit_s11_exit_domain.py --out-dir "$X03_AUDIT_OUT"
```

`X03_AUDIT_OUT` 必须由调用方指定。脚本只有冻结合成输入，不读取或下载行情，也不是通用真湖 trace 接口。每钟有 OFF、ON、front×0.37、front×0.37+2、真实同域破位 OFF/ON 六次回放。主要数字如下：

| 引擎 | 买入 | 买后现金 | OFF 卖后现金/NAV | ON 末日股数 | ON raw NAV | ON−OFF |
|---|---|---|---|---|---|---|
| 日线 | 400 @ 10.5 | 95,795.80 | 99,671.92 | 400 | 99,675.80 | 3.88 |
| 分钟 | 400 @ 10.2 | 95,915.92 | 99,792.04 | 400 | 99,795.92 | 3.88 |

raw `[10,10,10,10.5,9.45]` 的 SMA5=9.99 导致 OFF 假 pending 与次开卖出。front `[9,9,9,9.45,9.45]` 的 SMA5=9.18 不触发退出。9.7 的末日 raw mark 相同；3.88 是取消卖单后的手续费差额，不能解释为策略收益验证。

每个 `trace.json` 在真实账本调用前后捕获现金、股数与量使用；从实际选中报价和调用方局部上下文取得 quote/reference/limits，禁止从 reason 或行序猜时钟。专用 wrapper 对未知调用分支报错，避免把通用成交误标成此夹具的 pending-open 分支。原 CSV writer 保持不变，sidecar 记录：

```text
(date, code, side, price, shares, reason, cash_before, cash_after, hm)
append_seq, decision_hm, quote_hm, fill_phase, lot_id, commission,
bucket_id, volume_at, signal_domain, reference_price, mark_domain, flags
```

日线 `hm/decision_hm/quote_hm=null`，实际阶段为买 EOD / 卖 open，不伪造分钟报价；分钟来自实际 09:30 行（570）。EOD 信号及状态另记，不能冒充成交。`report.json` 保留输入、参数、代码、OFF golden 与两腿原 CSV 字节哈希、首个 FSM/成交分歧、新增/消失成交、逐日现金/股数/NAV/mark 差异与归因。现金公式两侧分别 Decimal HALF_UP 到分核对，原始 float 保留；股数严格比较，未成交保持现金、持仓和量预算。容量默认关闭，因此量预算残差为零仅代表未启用预算，volume=A 另由下表测试覆盖。

完整 OFF golden 基于 eff77f3，19 本×双钟 76 hash，加 v7 两 hash，每组真实买卖。`1d8799e`、`a2f2851` 是与 PR #202 相同来源的 cherry-pick 基线（#202 对应 `6f781cf`、`4c91e1a`）；本修复不重录 golden，不引入 #202 的 X-01 行为代码。

2026-09-25 先 `git fetch origin`，再以本分支 head `7dbeb80` 预演。三份基线文件 `tests/fixtures/off_byte_baseline_eff77f3.json`、`tests/test_off_byte_baseline.py`、`scripts/research/generate_off_byte_baseline.py` 与 #202、#204 均完全一致；两次预演均无基线冲突，合并树保留原文件。

- [#202](https://github.com/baiyibing/MyQuant-backtrader/pull/202)（X-01，`fix/x01-s12-price-domain`）当前 head `1e50ee1`：`git merge-tree --write-tree --merge-base=eff77f3 HEAD origin/fix/x01-s12-price-domain` 返回 1，仅 `backtest/research/csv_minute_backtest.py` 有五处接线冲突：
  1. `simulate` 参数：X-03 的 `fix_s11_exit_domain` / `signal_bars_front` 与 X-01 的 `fix_s12_price_domain` / `s12_price_context`。
  2. `simulate` 入口的两套校验守卫。
  3. `run_eod_exits` 的 front 信号参数与随后插入的 `require_market_marks`。
  4. `run` 参数：X-03 开关与 X-01 开关 / `s12_price_transform_file`。
  5. 日线/分钟加载：X-01 把旧加载包入 `fix_s12_price_domain` 分支，X-03 在旧 `load_daily_ohlc` 后调用 `load_signal_bars_front`。
- [#204](https://github.com/baiyibing/MyQuant-backtrader/pull/204)（X-02，`fix/x02-minute-cash-order`）head `ee65453`：`git merge-tree --write-tree --merge-base=eff77f3 HEAD origin/fix/x02-minute-cash-order` 同样返回 1，仅 `backtest/research/csv_minute_backtest.py` 有五处接线冲突：`simulate` 参数（X-03 开关/front 信号与 X-02 的 `fix_minute_cash_order` / `audit_sink`）、`simulate` 入口守卫、`run` 参数、CLI 参数注册（含 `--execution-audit-file`）、`main` 向 `run` 传参。

两次预演中 `csv_simulate_loop.py` 均自动合并，`csv_daily_backtest.py`、`csv_artifacts.py` 均无冲突。与 #202 合并时保留 `fix_s11_exit_domain=False` 和 `fix_s12_price_domain=False`；与 #204 合并时保留 `fix_s11_exit_domain=False` 和 `fix_minute_cash_order=False`。后合者只在分钟入口做接线合并，保留原 golden 的 hash 与断言、不重录，再跑 OFF 79 与双方回归。这里只验证文本合并冲突，未实际 merge，也未验证 ON 交互；X-02×X-03 交互仍待两独立 PR 验收后另跑。

## M01–M18 回归对应

表中是验收映射，实际命令、计数与 CI 状态以 PR / `result.md` 为准；不把未运行的真湖场景写成通过。

| 项 | 保留合同 | 最近测试或隔离证据 |
|---|---|---|
| M01 | T+1、旧/新 lot、未知板块拒单 | `test_partial_sell.py`、`test_ashare_exdiv_economics.py`、`test_strategy11_engine.py`、新 ON 合同测试 |
| M02 | 全卖因跌停、Decimal 档位 | `test_exdiv_refprice_engines.py`、新 ON pending 跌停与参考映射测试；market/ledger 未改 |
| M03 | 午休、零量、停牌 raw mark | `test_ashare_session.py`、v11 volume loader 与 ON 缺开盘/零量测试；时段和原 loader 未改 |
| M04 | S1 实际扣股、余股留 lot | `test_partial_sell.py`；ledger 未改 |
| M05 | s12 MA 截昨收与双钟卖时点 | `test_strategy12_engine.py`、`test_strategy12_rules.py`；s12 ON 误用拒绝 |
| M06 | s12 50% floor100 / lot0 保底 | `test_strategy12_engine.py`、`test_strategy12_rules.py`；s12 未改 |
| M07 | latch=A、residual=2 | 同上；全书 OFF 字节矩阵 |
| M08 | MA10×0.90 优先、双记忆和 step 单调 | 同上；s12 未改 |
| M09 | s12 无单日笔数闸/指数闸 | `test_csv_strategy_books.py`、s12 engine/rules；策略注册未改 |
| M10 | s12 延期锁 lot / 分钟重判 | `test_strategy12_engine.py`；延期实现未改 |
| M11 | 参考映射/权益分层、economics OFF | `test_exdiv_refprice_engines.py`、`test_ashare_exdiv_economics.py`、新 ON 映射一次/信号零次与权益测试 |
| M12 | 费用、容量默认关、pending 原子性 | `test_partial_sell.py`、volume 测试、新双钟现金精确到分测试 |
| M13 | v11 双钟买、EOD pending、次开卖、不重入 | `test_strategy11_engine.py`、`test_s11_exit_domain.py` 的 ON 版本 |
| M14 | D→首 T≤4 自然日、周线 prefix | `test_export_strategy11_pool.py`；冻结原池，导出器未改 |
| M15 | 无 chase、09:30 volume=A | `test_strategy11_engine.py`、新 ON 未完成桶买 skip/卖 defer/无追买测试 |
| M16 | CYQK/asof 股本、边缘/NaN、池篱笆 | `test_export_strategy11_pool.py`、`test_strategy11_rules.py`；导出器/CYQK 未改 |
| M17 | 8.x 比较/配给/池顺序/seed | `test_csv_strategy_books.py`、`test_off_byte_baseline.py`；其它书禁止传 front 信号 |
| M18 | 旧时钟、缺 bar、11/12 禁 stop 参数 | 既有书与 v7 回归、全书 OFF 字节矩阵；没有 X-01/X-02 改动 |

## 真实数据未验证，待 4090

本次是实现、合成与 CI 验证。未访问 4090 真湖，未确认全部真实 front/none 日期和历史版本、未跑真实池 A/B，未完成策略 11 Slice D；框架验证不等于已验证多头。

4090 按以下顺序留下独立回执：

1. 记录 repo SHA、选定解释器/依赖、authority 与 resolver 结果。仅消费已配置湖；未配置或缺源直接失败，不猜盘、不下载、不绕过配置。固定同一快照的 1d/none、1d/front、1m/none 与原预热数据。
2. 冻结原 `20251023–20260909` version11 已导出池、原 D/T 审计、CSV 字节及行序、名称/费率/现金/预算/seed。不能为本次退出修复重跑 exporter；缺原池就列为阻塞。对入场来源不明的池不声称已验证 front 导出合同。
3. 同一 SHA、参数和冻结输入各跑日线 OFF/ON、分钟 OFF/ON，X-01/X-02 保持 OFF。分钟显式 `--no-cache`；各腿单独输出目录，不能跨湖更新。例中的路径变量必须由冻结输入填写。

```bash
"$BT_PY" backtest/research/csv_daily_backtest.py \
  --strategy version11 --start 20251023 --end 20260909 \
  --cash-total 21000000 --daily-quota 1000000 --name-budget 1000000 \
  --pool-dir "$FROZEN_POOL" --dividend-type none \
  --strict-pool --emit-run-manifest --out-dir "$DAILY_OFF"
# 原参数复制到 DAILY_ON，只追加 --fix-s11-exit-domain。

"$BT_PY" backtest/research/csv_minute_backtest.py \
  --strategy version11 --start 20251023 --end 20260909 \
  --cash-total 21000000 --daily-quota 1000000 --name-budget 1000000 \
  --pool-dir "$FROZEN_POOL" --dividend-type none \
  --minute-source lake --daily-source lake --no-cache \
  --strict-pool --emit-run-manifest --out-dir "$MINUTE_OFF"
# 原参数复制到 MINUTE_ON，只追加 --fix-s11-exit-domain。
```

4. 上述 CLI 产生旧格式 CSV 与新外层 manifest，不含通用逐笔现金 trace。真湖回执需用经审核的实际调用上下文捕获器扩展本专用 replay，覆盖真实可能出现的分支后再取 §8.2 sidecar；不得把普通 trades CSV 事后按时间排序补现金或从 reason 猜时钟。本脚本不伪装已支持任意真湖输入。
5. 保存真实命令、所有输入 hash、两源 hash、拒绝/缺失清单、逐笔差异、参考价/raw mark 审计与运行时长。差异依次归因为信号、限价、估值、现金可用、持仓可用及后续传播；未解释变化不得用总体 NAV 接近放行。
6. 同时核正乘法/正仿射锚点与 EOD 前缀不变性；本次 exit FSM 合成夹具通过，不扩大到 exporter 的 CYQK 固定网格、asof 股本或湖历史修数。保留两锚点快照/上游版本证据后再讨论完整 PIT 数据版本结论。

共同正仿射变换在数学上保持 close/previous/SMA 的大小关系，但现有 float SMA 在机器精度等号边界仍可能翻转。例如 HOLD 模式 `[5.12] * 5` 不退出，整段 ×0.37 后的 `[1.8944] * 5` 可因 SMA 舍入误差触发严格 `<`。本 PR 保留既有 `sma_series` 与比较符号，未为锚点测试改均线或增加容差；不能把已通过的合成夹具表述为任意浮点边界的普遍保证。该既有精度边界列为待确认项。

待确认仍为真实湖与原池可用性、4090 A/B 的未解释项、X-02 后续交互。已知限制：X-08 exporter/CYQK 未验，Slice D 未完成，δ6 economics 默认 OFF 导致除权后经济口径不完整，X-20 预热不修；不据此自动把默认开关改为 ON。
