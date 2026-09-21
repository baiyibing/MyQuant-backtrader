# merge-consensus：plan-ma-infra-shared v0.1（2026-09-21）

四家独立评审（codex 361s / kimi 702s / cursor:auto 451s / claude 308s，全 rc=0，产物平铺本目录）。
证据裁决，不投票；cursor-desktop 席由主持回避（见 [cursor-desktop.md](cursor-desktop.md)）。
四家总评一致：**不可直接进实现；按下述五面修订后可 GO**（均为 plan 文本级，零架构改动）。

## 证据裁决表

| # | 面 | 裁决 | 证据（多路独立收敛） |
|---|---|---|---|
| **C1** | §1 盘点两处事实错误 | **成立（4/4 收敛）** | 「布林无存活实现」假：`oskh_factors/price_bb.py:11`（`np.std` **ddof=0**）、`scripts/data/full_market_canonical_resist.py:246-255`（pandas rolling **ddof=1**、`<20` 根回退全序列 mean/std——与 R5 None 口径分歧）、`scripts/data/full_market_chip_resist.py:49`（**ddof=0**）、`oskh_factors/chip/bands.py:27-49`（ddof=1 但 **round(...,4)** 四位舍入会改 `high > 上轨` 边缘）。「全仓唯一 MA」过强：`weekly_macd_divergence.py:183` 周线 MA200、`strategy7_rules.py:171-173` 上证 MA10 手写。σ 口径在仓内**实际分裂**（ddof=0 与 ddof=1 并存） |
| **C2** | 周线 asof 键与末端周 | **成立（3/4，含两组实验）** | codex 实验：W-FRI 标签可为 `_last_day` 之后的未来日；kimi E1：节假短周 `label=2024-09-13` 而真最后交易日 `09-12`；空周直接消失。**必须 pin：返回 `date = _last_day`（周最后交易日，非 Friday 标签）；末端未完成周保留（`_last_day ≤ D` 可参与）；停牌空周无行**。归档锁三条（`_archive/plans/plan-ma-chip-edge-strategy-2026-09-07.md:34`）原文如此 |
| **C3** | 批量件缺口（v11 R8 无法兑现） | **成立（2/4，两组实测）** | codex：全市场逐日 asof 682s vs 周序列增量 1.56s；kimi E4：5000 票×1000 日 215–505 min。**§2 必须加 `weekly_sma_series` 与 `bb_series`**（纯 Python 增量即可，kimi E4：纯 py 比 pandas 快 2.3×）；`*_asof` = 序列件 `[-1]` 薄封装，标量/批量永同口径 |
| **C4** | NaN / 边界语义未定 | **成立（3/4）** | 现状实验：`sma_asof([1,nan,3],3) → nan`（**传播，非 None**）；cursor Y4：**原样搬家保持现状，不得"清理"成一律 None**（gate 对 NaN/None 恰好都 fail-closed，但 `is not None` 分支不同）；`bb_asof(n=1)` → ZeroDivisionError（ddof=1 分母 n−1）；`sma_live` 必须 pin **尾部 n−1 根 + px**（非前缀）；`sma_series` 与输入等长、前 n−1 位 None（否则 v11 `cond[D]`/`cond[D-1]` 错位）；数值比较用 `pytest.approx`（FP 漂移 1.24e-12 实测） |
| **C5** | 复权域契约缺失 | **成立（2/4，且引 SSOT）** | E-R5 锁定 v4 SMA 门用原始 closes **除权日不换域**（`engine-ashare-correctness.md` E-R5 ③）；引擎默认 `dividend_type="none"`（`csv_daily_loader.py:108`）；v11 价格锁 front（归档 §2）。**裁决：模块零复权、域 100% 在调用方；明文禁止为统一口径把 v4 改前复权；v11 导出器自行传 front 序列**。ma_infra R4 加一句域指针即可 |
| C6 | 刀 B 文字自相矛盾 | 成立（4/4） | 「调用点改向」vs P3「gate 不动」vs DoD「仅 import 行」。事实：`csv_strategy_books.py:483-484` 按模块属性消费，**全仓零调用点需改**。统一为「删本地 def + re-export；gate 函数体零 diff；DoD=diff 仅 import 行+删 4 行 def」。gate 内继续调用本地名 → **无需冗余别名**（不触发 F401）；快检命令补 `tests/test_strategy4_rules.py` |
| C7 | import fence 无 pandas 门 | 成立（4/4） | fence 固定 15 模块清单只禁 qlib/lebs/trade_fee_policy/fill_clock（`test_ashare_simulate_import_fence.py:39-57`）。R2 改述真实机制：**标量六件标准库零依赖（含周线，kimi E4 纯 py 更快）；`*_frame` 若做须独立子模块 + 函数内 import + AST pin**，不扩 fence（AGENTS.md 纪律） |
| C8 | CI 口径 + HEAD 引用 | 成立（2/4） | CI = `-m "not production and not benchmark"`（`.github/workflows/python-tests.yml:56`）；§7 裸 pytest 会吃 production 标记误判红。HEAD 统一改回填时点 |
| C9 | 跨 plan：v11 R3 与 R8 周线归属互斥 | **成立（cursor R5 独挖）** | version11 R3「周线复用 oskh_factors」vs R8「只走 ma_infra」两把锁必破一把。裁决：**v11 R3 改为周线走 `ma_infra.weekly_sma_asof`；`_daily_to_weekly` 保持私有不外露；`weekly_macd_divergence.py:183` MA200 不迁不删** |
| C10 | 差分 pin（双副本防漂移） | 成立（3/4，kimi E2 证明可行） | 纯 py port 可与 pandas resample 逐值对齐（含节假短周+空周）。切片 A DoD 增「vs `_daily_to_weekly` 差分 pin（测试内联 pandas）」；出处注释加「冲突时以差分测试裁判」 |
| C11 | sma_live 消费方依赖 strategy12 P2-B | 成立（kimi R10） | P1 栏标注 sma_live 为「P2-B 预留」；人裁顺序先裁 strategy12 P2 |
| C12 | σ 数值 pin | 成立（cursor Y1 实验） | `std([1..5], ddof=1)=1.5811388300841898 ≠ ddof=0=1.4142...`；测试 pin 写死该数，防"改齐"通达信口径 |

## 分歧与处置

- `weekly` 件用纯 Python 还是 pandas：kimi（纯 py 快 2.3×）vs 无反对者 → **纯 Python**（C3/C7 一致解）。
- 布林返回结构（tuple vs NamedTuple）：codex 🟢 建议 NamedTuple 扩展位，claude/kimi/cursor 未跟 → **维持 tuple + YAGNI 记录**。
- 「唯一/无存活」的定性：四家均要求改写，措辞取 claude 版「书侧消费路径上无共享实现；存量 scripts 副本口径已分裂，收敛范围=书侧/研究侧 asof，chip/TR 面不在本刀」。

## 修订指令（回填 v0.2 清单）

1. §1 盘点表重写（C1）：补已知存活件与 σ 分裂图；SSOT 边界声明。
2. §2 API 面加 `weekly_sma_series`/`bb_series`；`weekly_sma_asof` 参数名 `n_weeks`；`date=_last_day` 三条 pin（C2/C3）。
3. R4 加复权域句（C5）；R2 改述 fence 真机制（C7）；R5 补 NaN 传播/尾部拼接/等长/approx 四条（C4）+ σ 数值 pin（C12）。
4. 刀 B 统一文字 + 无需别名（C6）；§7 命令补文件与 CI 口径（C8）；刀 A DoD 加差分 pin（C10）；P1 标 sma_live 预留（C11）；风险档拆刀 A/B（cursor Y5）。
5. 同 commit 修 version11 R3 周线归属（C9）。
6. HEAD 引用统一为本回填 commit 前实测点。

## 结论

**修订后可进人裁**：P1（API 面六件+序列件）、P2（纯 Python 前缀和/增量，不做 *_frame）、P3（刀 B 统一为删 def+re-export）、P4（位置 `backtest/research/ma_infra.py`）——四问在四稿中均无实质分歧，人裁确认即 GO。
