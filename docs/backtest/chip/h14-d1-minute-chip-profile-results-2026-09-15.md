# H14 / D1 — minute/hybrid chip hotpath profile results

- 日期：2026-09-15（Asia/Shanghai）
- Plan：[../plan-h14-d1-minute-chip-profile-2026-09-15.md](../plan-h14-d1-minute-chip-profile-2026-09-15.md)
- Bench：[`scripts/research/bench_minute_chip_hotpath.py`](../../../scripts/research/bench_minute_chip_hotpath.py)
- 环境：Linux box · project Python 3.12 (vanna312) · numpy 2.3.x · 合成数据（无 F 湖）
- 默认规模：80 日 × 240 分钟；`step=0.01`；reps 见下

## Ranked timings（ms/call，hottest first）

| Rank | Kernel | ms/call | Notes |
|------|--------|---------|-------|
| 1 | `minute_chip_distribution` | **~50.7** | 80d×240m = 19200 bars；bins≈414；reps=30 |
| 2 | `hybrid_chip_distribution` | **~1.01** | 80 daily + 240m today；bins≈218；reps=30 |
| 3 | `calc_curpdf` × N（triang Python loop） | **~0.69** | N=80，bins≈213；reps=80 |
| 4 | `calc_cumpdf`（已 `@jit` numba） | **~0.021** | shape (80,213)；reps=400；warmup 后 |

相对量级：`minute` ≈ **50×** `hybrid` ≈ **70×** `curpdf×N`；`cumpdf` 已非瓶颈。

## cProfile 热点（摘要）

### `minute_chip_distribution`

- 几乎全部时间在函数本体 Python `for`（~0.05s / call @ 19200 bars）。
- 次热点：每 bar **`np.zeros(len(price_bins))`**（~19201 次分配）——单 bin 写后再做 `cumpdf * diff + curpdf`。
- 未调用 `calc_curpdf`（分钟路径是 close→bin 直方图 + 衰减，不是三角 PDF）。

### `hybrid_chip_distribution`

- 主耗时：历史日循环调 `cyq.calc_curpdf` → `calc_triang_pdf`（~79 次）+ 当日分钟直方图。
- `calc_cumpdf` 在 hybrid 尾部；相对可忽略（已 numba）。

## D2 recommendation

| 路径 | 建议 | 理由 |
|------|------|------|
| `minute_chip_distribution` | **numba（优先）** | 清晰 Python 热环 + 每 bar 分配；研究窗 80×240 单票已 ~50ms；多样本/滚动会放大。先向量化/单缓冲 + numba 累积，**勿改语义**。 |
| `hybrid_chip_distribution` | **leave**（或 D2 轻量跟 minute 同批） | 已 ~1ms/call；生产全市场 TR 不走此路径（Rust Store）。 |
| `calc_curpdf` / triang | **leave**（短窗） | hybrid 里够用；全市场日频已有 Rust / 既有 numba batch（`full_market_canonical_resist`）。 |
| `calc_cumpdf` | **leave** | 已 numba；~0.02ms。 |
| Rust rewrite minute/hybrid | **暂不** | 非生产 TR SSOT；H13：不复刻 MyQuant feeder。仅当 D2 numba 后仍有产品级吞吐需求再开片。 |

**一句话 D2：** 只切 **`minute_chip_distribution` 的 numba/向量化 offload**（语义锁 + 对拍）；hybrid/curpdf/cumpdf 默认 leave；不启 Rust、不迁 MyQuant CYQ。

## 非目标（重申）

无算法语义变更 · 无全市场湖跑 · 无 MyQuant feeder 迁仓 · 无 Cerebro 删除 · 无 CloudAgent。
