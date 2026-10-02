# Wind ↔ QMT/lake 分钟 OHLCV 只读样本核对

Human「按你建议来」授权本 scaffold；基线 76808e373df05d71a014724796bedffda3e42514（#292）。依据 [vendor alignment SSOT](../ssot/vendor-bar-alignment-ssot.md) §2–§4，以及 box 本地 host RECEIPT / market_PIN.json。此刀不是 ingest 验收。

样本计划：002231.SZ / 300379.SZ / 600200.SH；窗口 20251023–20251028（交易日 23、24、27、28）。host 证据仅证明该批 Wind START shares、历史 siblings lots 及 overlay 未写湖；不能外推全 vendor。物理 host 湖核对留待 Human GO 后由 4090bot 执行，本刀仅合成验证。

## 比较合同与判定

- 仅构造比较键 `(symbol, ymd, hm)`，不改输入表。连续 START 区间 `[t,t+1)` 映到 END t+1；显式报告 09:30→09:31、13:00→13:01。09:30 是否竞价仍需逐源 PIN，不因 PASS 自动认定。
- START 支持 09:30–11:29、13:00–14:59；END 支持 09:31–11:30、13:01–15:00。其他时间拒绝，保留异常供 Human 核对，禁止跨午休机械平移。
- 只比较交集；wind_only / lake_only 数量、键样本单列为 coverage note。不补造根、不零填。重复键、非有限数值、负值、非分钟时间、空交集及任一标的无交集 FAIL。
- OHLC 默认绝对容差 1e-8、相对容差 0；volume 默认绝对容差 0、相对容差固定 0。CLI 可显式改价格绝对/相对容差及 volume 绝对容差，均记录 report。
- 未缩放原始交集的正 lake volume 上，median(wind/lake) 距 100 或 0.01 在 5% 内仅标记 `volume_unit_suspect`；该启发式不判定单位、不自动换算。`--volume-scale` 是用户显式指定、始终记录的 lake-volume 比较乘数；100 表示 **lake volume ×100** 后与 Wind 比较，0.01 同理。PIN acknowledgement 仅确认疑点，显式 scale 仅按指定乘数比较；本脚本禁止静默探测并转换 lots↔shares，后续编辑也不得在此 CLI 加入自动单位换算。
- PASS 要求每标的非空交集、零 OHLCV 超容差字段、无未确认单位疑点。确认方式为显式 scale 或 PIN 顶层非空 `volume_unit_suspect_acknowledgement`（写明依据）；确认疑点不豁免数值差异。PASS 只覆盖已观测交集，不表示 coverage 完整、竞价范围一致或全表转换获批。

## 入口与输出

CLI：[scripts/research/vendor_bar_xcheck.py](../../../scripts/research/vendor_bar_xcheck.py)。`--wind` / `--lake` 可重复并各接多个文件；Wind CSV/parquet，lake parquet；支持 flat symbol/time 或 hive symbol=XXXXXX.SZ/data.parquet。数值 time 按 `local_wall_as_utc_ms` 解码（不加八小时）；datetime 无时区按上海墙钟，有时区转上海。其他数值编码应先在另行授权流程明确，不能套用此入口。

```bash
/workspace/.venv-bt-ssot/bin/python scripts/research/vendor_bar_xcheck.py \
  --wind /explicit/wind.csv --lake /explicit/lake.parquet \
  --symbols 002231.SZ 300379.SZ 600200.SH --out-dir /separate/handoff/out
/workspace/.venv-bt-ssot/bin/python -m pytest tests/test_vendor_bar_xcheck.py -q
```

`--host-root` 发现 vendor_fill/raw/wind_*_1m*.csv 与 prepare/**/*minute*.parquet；`market/**/*.parquet` 仅列入 `market_not_adopted`，混合 START/END overlay 默认不得当作纯湖。市场叠加 opt-in 须另获独立 Human GO，再显式提供 lake 路径；不得折入本刀默认路径。可显式提供 lake 覆盖自动发现。未找到 lake 时输出 FAIL 及发现清单，不猜盘符；可用显式或合成输入运行。标签默认 Wind START、lake END，可显式选择。`--pin` 只读并记录 notes，不从 PIN 静默改标签或单位。

输出 STATUS.json（status/stage/reason/tip/out_dir）、report.json（输入路径/hash、策略、逐标的交集/差异/单位/边界）、REPORT.md。PASS exit 0，其余非零。out-dir 必须在输入目录和 HostRoot 之外；仅写报告。

12 个合成测试通过 / sample PASS 仅覆盖 scaffold 合同，不替代 δ5 certified 或 R4 市场验收；STATUS 的 PASS 也不得外推为该验收。**≠δ5 ≠R4**。

## 非目标

不写湖；不在 Human「合」前 merge；不开放 δ5 certified / R4；不改 MatchCore / Fees / engine / simulate；不对整表静默 START→END 重标；不补造 bar；无 PIN/显式声明不静默换 volume 单位；物理 host/E:\ 湖对照延后。START→END 实际数据转换仍受样本证据及独立授权门槛约束。

合成验证不构成市场验收；自动单位换算与 market 自动采纳均不在本刀范围内，后续不得由 PASS 或测试通过推导授权。
