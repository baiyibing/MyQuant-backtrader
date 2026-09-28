# G4：s11 front 双快照、双锚点前缀证据

本次 Human sequential GO 仅授权 G4 合成取证。结论为 **PASS-for-method**：选定 s11 exporter 的价格比较路径中，共同正缩放/仿射夹具保持信号；舍入、非共同修数和固定网格守卫边界产生可归因的差异；同一快照扩展截止日不改写共享早期前缀。**本 PR 无需生产代码修改；勿合，等待 Human「合」。** G5–G8 未开始，不重开 G2/G3 或其他研究线。

依据：[审计 G4](industry-gaps-bt-2026-09-28.md#g4front-输入的历史可得性出口信号的锚点不变性未完整证明m)、[X-01 转换证据](x01-s12-price-domain.md)、[X-03 PIT 边界](x03-s11-exit-domain.md)。X-01 仅覆盖声明的 s12 分钟上下文，X-03 仅覆盖退出域；均不能授予 s12 日线或 s11 exporter/CYQK 完整历史 PIT 证明。

## 方法与隔离边界

入口为 [tests/test_g4_front_pit_evidence.py](../../tests/test_g4_front_pit_evidence.py)。纯帧适配器 `signal_prefix(frame, cutoff)` 直接调用现有 `export_strategy11_pool.prepare_frame` 和 `compute_signals`，使用生产 BB、MA20/60、显式 prefix weekly MA20、edge_condition、200 日窗口及固定网格守卫。未复制或改写生产信号公式，未运行 exporter CLI，也未测试名单 D→T 输出或成交/NAV。

**CYQK 是受控替身**：前 199 行 NaN，之后固定 0.8；股本固定 1e8，volume 固定 1000。替身检查调用长度、window=200、start_i=199、step=0.01，以及进入回调的窗口不超过 250000 网格跨度。它隔离价格比较与边缘逻辑，**不计算 Rust CYQK，不验证其直方图固定步长、阈值敏感性或 as-of 股本来源**。固定网格桶只验证生产 exporter 的超限守卫，不冒充 Rust 分桶效应证据。

两快照各含同样六个合成 symbol、同样 240 个工作日，从 2023-04-03 起；使用 `bdate_range`，不是交易所节假日日历。生成后写入 `tmp_path/A|B/*.csv`，按 `%.17g`、UTF-8、LF 冻结，逐文件 SHA-256，并以 round-trip 精度读回后精确核对，再从冻结字节计算。A/B 只是本地夹具标签，`upstream_version_id=null`，不代表供应商历史版本。

两个 cutoff 都落在周三，特意覆盖尚未结束的周：

- C1 = 2024-01-31（位置 217，含当日 218 行）。
- C2 = 2024-02-28（位置 237，含当日 238 行）。

每桶分别比较 A(C1)/B(C1)、A(C2)/B(C2)；对 A、B 各自精确比较 `signals(C1) == signals(C2)[:C1]`（包括 CYQK、grid、finite，保留 NaN 位置），并核对预先截断帧与适配器截断结果。另将 C1 后所有 OHLC ×3，确认 C2 重算仍不改 C1 前缀。测试断言早期有有效指标且 A 有实际信号，避免空前缀或全预热假通过。

## 冻结桶与结果

基线 OHLC：open=10、low=9.875、close=10、high=close+0.125；在 D1=2024-01-22（位置 210）与 D2=2024-02-19（位置 230）令 close=11。各桶只对自己的 symbol 做以下变化，不把多个扰动叠在同一条价格序列。A 在各桶均有 D1/D2 两个信号；下表差异均为 B 移除对应 A 信号。

| 合成 symbol / 桶 | A → B 的唯一受控处理 | C1 信号差异日 | C2 信号差异日 |
|---|---|---|---|
| 600001.SH / positive_scale | 全历史 OHLC ×2 | 无，same-prefix | 无，same-prefix |
| 600002.SH / common_affine | 全历史 OHLC ×2+3 | 无，same-prefix | 无，same-prefix |
| 600003.SH / rounding | A 的 D1/D2 close=10.004、high=close+0.125；B 全 OHLC 保留 2 位小数，close 归到 10 的等号 | D1，differed | D1、D2，differed |
| 600004.SH / non_common_revision | 仅 B 的 D1 close 从 11 改为 10 | D1，differed | D1，differed |
| 600005.SH / fixed_grid_guard | A 位置 205 的 high=9.875+250000×0.01；B 仅将此 high 向正无穷推进一个浮点 ULP | D1，differed | D1、D2，differed |
| 600006.SH / future_only_revision | 仅 B 的 D2 close 从 11 改为 10（晚于 C1） | 无，same-prefix | D2，differed |

网格桶 A 恰好等于上限，B 超过上限：C1/C2 分别有 13/33 行 grid 状态差异，B 相应 CYQK 为 NaN、finite=false。这是刻意构造的极端边界，不声称真实市场出现频率。舍入桶是输入小数精度处理，不是 G7 的全库浮点容差方案，也不更改任何比较符号。

同一快照内六桶 × A/B 的 C1 对 C2 共享早期窗口全部 **same-prefix**。跨快照的非共同历史修数可以改变相同日期的历史信号，这与同一快照内的因果前缀不变性是两个命题。

共同正仿射 `p'=a*p+b, a>0` 数学上保持 close/MA/weekly 的大小关系；BB 的标准差随 a 缩放，上轨也服从同一变换。这里仅在所列安全跨度、受控 CYQK 与数值夹具上核对。固定 step=0.01 的真实 CYQK 和 grid 守卫不具备任意尺度保证；任意浮点等号也不获得普遍保证。未在此运行逆转换路径。

冻结总指纹是对 `{symbol: CSV_SHA256}` 做键排序、紧凑 JSON 编码后 SHA-256，测试固定断言，避免夹具被静默更换；逐文件指纹保存在生成的 report.json：

指纹 SSOT 为 `tests/test_g4_front_pit_evidence.py` 的 `FROZEN_DIGESTS`；合法重新冻结时先更新测试，再同步下表。

| 标签 | 总指纹（仅本地合成快照） |
|---|---|
| A | `69da5b4f12eb40d6234b58455be862fd648498b531f966c5707fe0e5965233ac` |
| B | `5f0689fade0ed63d9b156f5bd97e00e46979de66543a7a7daf838c2b3fea1dfa` |

指纹依赖 `%.17g` 格式；numpy/pandas 或 `%.17g` 数值表示变化可能合法地要求重新冻结，现有指纹锁定断言会检出差异。

## 复现与验收

按 AGENTS 的解释器优先级设置 `OSKH_MERGE_PYTHON` 后运行（本次显式选择 `/workspace/vanna312/bin/python`，Python 3.12.13、numpy 2.3.5、pandas 2.3.3、pytest 9.0.3）：

```bash
"$OSKH_MERGE_PYTHON" -m pytest -q -s tests/test_g4_front_pit_evidence.py
"$OSKH_MERGE_PYTHON" -m pytest -q tests/test_g4_front_pit_evidence.py tests/test_export_strategy11_pool.py tests/test_strategy11_rules.py
```

专用 harness 3 tests；联合回归 **36 passed**。`-s` 输出 JSON，包含 12 行桶/截止日对照、差异日期、grid 差异数量、输入 hash 与非认证标记；完整 CSV 和 report.json 在本仓 `artifacts/pytest_tmp/run_<pid>/test_two_frozen_snapshots_two_0/`，属于临时合成产物。专用测试将 resolver、Parquet 读取替换为立即失败，禁止触湖；既有 exporter 回归仅使用 tmp_path 合成 Parquet。

本次没有发现必须修复才能诚实运行 harness 的局部 helper bug。受控差异均符合输入变化或现有守卫合同，因此 **PASS-for-method，不改生产 exporter**。尚未取证的 Rust CYQK / 全历史版本问题不能据此结案，也不能反过来自动授权生产重写。

## 明确保留的非结论

- `common_affine_certificate_full_pit_unverified` 保持 **unverified for full history**。报告使用这一边界标记，不颁发 X-01 的可消费证书。
- 未访问湖、4090，未下载真实 front，未调用真实湖 `resolve_period_root`；没有真实供应商快照身份或历史可得性证据。
- 不认证 s12 日线、真实 s11 CYQK、股本历史、名称历史、供应商舍入或非共同修数；不把退出域证据外推到入场域。
- G5–G8 未启动；G2/G3、TopK、hl/fen、δ5/δ6、Cerebro/PortAna 均未改动。不新增策略版本，不改变任何生产默认值。
- PR 仅提交可复现方法及合成证据，**勿合；Human「合」之前不合并**。真实快照或生产修复另需相应人裁，不能从本刀继承授权。
