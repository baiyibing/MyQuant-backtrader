# S1 TopK participation_rate 实现刀

基线 `da173442235beca8861cdde1d008baf6b540c723`（#290），分支
`knife/topk-s1-cap-cli`，工作目录 `/workspace/wt-topk-s1-cap-cli`。
2026-10-01 Human 授权共享分钟 CLI opt-in 接线、真分数窄窗脚手架及 draft PR；
**不合并**。此次明确授权覆盖 v2 合同历史 §1 的“不加 parser flags”停点；
不扩展 certified-real 入口、不改 MatchCore/Fees。

## 交付范围

1. `csv_minute_backtest.main/run` 增加可选 `participation_rate`。省略及 `None`
   均沿用旧参数组装、旧量读取与输出行为；有限 `[0,1]`（包括 0）接既有 VolumeCap。
   数值非有限/越界沿用 ValueError；非数字 CLI 参数仍由 argparse 拒绝。
2. `csv_minute_volume.completed_minute_volumes` 只消费已加载分钟 frame。
   cap-on 要求 raw lake 分钟股数，拒绝 front/qlib 及 tail lots 混用，绕过旧无量缓存。
   `BucketVolume.unit=raw_shares_incremental`，`available_at=bucket_end` 为研究近似。
   09:30 竞价、13:00 开盘行不提供完成桶容量；缺列、坏量、重复桶/缺证券 frame 报错，
   缺 lookup key 由既有核记 `skip_volume_unavailable`，不查日量救场。
3. `scripts/research/run_topk_cap_compare.py` 接显式多证券 S1 scoped Parquet、
   单位/时钟 PIN、完整原始 pred CSV/SHA、三买日 scores/pool。调用同一原生 `simulate`，
   两臂分别 `None` / 显式 rate，独立状态、同一规范化输入。默认 Top50/5、close、
   qlib limit、10% touch stop、原费用保持；不提供改为单股 Top1 的参数。
4. 脚手架先验证原始完整预测日历 `20251023→24、24→27、27→28`，
   scores T 文件不再 shift；逐截面核对全部 code/score 和原生导出 Top50 pool。
   `--prepare-only` 产出 date-map、603196 分数/排名和所需证券，两臂 NOT_RUN。
   默认无 eligibility/walkdown 时，各日 Top55 并集覆盖 Top50/5 的所有潜在成交证券；
   行情按此保守集合取，分数仍保留全截面。MyQuant 同分按 instrument 排，
   引擎仍按 canonical code 排；两者各自验证，不改策略排序。
5. 外部全新 out-dir：两臂 trades/fills/daily_equity/summary/stats/capacity_used，
   根目录 comparison、date-map、required_symbols、PIN 和五字段 STATUS。
   输入 hash 前后检查；输出 hash 入 PIN。失败非零并保留回执，旧目录不覆盖。

## 单位与研究限制

共享 CLI 的 `--participation-rate` 同时声明**已配置分钟源的 volume 是 raw 增量股数**。
它不猜单位、不自动将旧湖手数乘 100；旧湖仍为手时不可直接开此旗。
共享 loader 已有的去重/时钟投影不等于来源认证；本刀不改其默认行为。
cap-on 自动写现有 run manifest/metadata，记录上述假设，OFF manifest 参数不增加新键。
独立脚手架在源去重前校验 scoped PIN/原行，拒绝不明确单位/时钟及缺行情，
支持精确整数股数（无损整数浮点只在 `≤2**53` 范围内转 int）。

窄窗固定买日 20251024/27/28，日线参考从 20251023 起；不根据结果选窗。
2025valid 是 validation/early-stop 窗，**不是 OOS**；两臂差值也不保证 cap 必须改变收益。
脚手架要求候选三日完整连续分钟桶与四日日线；遇稀疏/停牌缺口先 INPUT_BLOCKED，
不猜停牌、不静默缩宇宙。此窄窗工具不承担通用停牌适配。
公司行动 economics 与独立证券状态表未提供，`exdiv=None/exdiv_economics=None`
写入 PIN；缺名称不认定非 ST，研究限制据实披露。
`no_ssot_compare_authorization` 保持；不开 δ5 certified / R4，不写湖、不动 MyQuant 代码。

## 核验与交接

data-free 核验：参数解析/拒绝、省略≡None（且不读量）、0/0.1/1 容量、
09:30/缺 lookup、现有 OFF 字节 golden、Top50/5 多证券两臂、错 shift/单股控制、
源 PIN/覆盖/单位失败、输出隔离、源前后 hash 和四项路径 gate。
结果见 [RUN.md](RUN.md)；物理机命令和输入格式见 [HOST_4090.md](HOST_4090.md)。

外部回执：`/workspace/handoffs/topk_s1_cap_cli_20261001/`。
前次控制接线 `s1_cap_strategy_wire_20261001` 仅作工程背景；
`topk_s1_cap_real_pnl_20261001/SCORES.md` 的真分数 BLOCKED 未被本机测试解除。
后续顺序：本刀 draft → 人转 Grok CLI 核 → 4090bot 取真输入并运行。
本刀只用 Codex CLI，没有代用 Grok 额度或自动发消息给其他 bot。
