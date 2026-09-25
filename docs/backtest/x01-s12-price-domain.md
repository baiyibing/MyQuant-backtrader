# X-01：策略 12 分钟价格域（默认 OFF）

本变更对应[分钟审查 X-01](../reviews/2026-09-25-minute-engine-review/README.md)，落实
[#151](https://github.com/baiyibing/MyQuant-backtrader/pull/151) /
[#158](https://github.com/baiyibing/MyQuant-backtrader/pull/158) 的 front 信号、raw 成交语义。
仅修策略 12 分钟价格单位；不改日线策略 12、其它策略、成交时序或策略规则。

## 开关与账户含义

`--fix-s12-price-domain` / `fix_s12_price_domain=False` 默认关闭。
OFF 保持既有加载器、缓存、trades/equity CSV 和 API stats；不额外依赖 raw 日线。
OFF + none 仍混用 front 信号/估值和 raw 成交，NAV 不宜用于排名；OFF + front
是旧复权单位研究账户，并非人民币 raw NAV。历史回执文件不改、不重录。

ON 只接受策略 12、`--minute-source lake --daily-source lake --dividend-type none`。
其它组合报错。新上下文只读同一冻结快照的 1d/front、1d/none、1m/none，绕过旧分钟缓存。
ON 的 `simulate(..., daily_bars=...)` 显式传 raw 日线供日历、存在性和 mark 使用；
front 仅保留在显式价格上下文，避免后续市场用途误拿信号价。
必要时提供 `--s12-price-transform-file`；无法证明转换关系时停止，禁止默认因子 1、
向前填充因子、用当天收盘拟合、切换 front_ratio 或下载替代数据。

对决策日 D 使用已验证的 `F_D(x)=A_D*x+B_D`：

```text
H_D(t) = (front_close(t) - B_D) / A_D, t < D
MA5、MA10 = 既有 ma_infra 对 H_D 的计算
止损线 = 0.90 * MA10(H_D)
参考价 = Decimal HALF_UP(H_D[-1], 0.01)
涨跌停 = 既有 limit_prices(参考价)，结果再次 HALF_UP 到分
成交 = 原始分钟 open/close（现有取价和时钟）
估值 = 当日或最近此前的真实 raw 日线 close
```

不逐历史日期除各自因子，不锚在昨日，不先在 front 域乘 0.90 再逆变换。
仅参考价落分，MA 历史保留精度。卖出、追买、池买、台阶、买回共用独立参考价。
ON 的 `exdiv` 必须为 `None`，转换不再进入旧参考映射或成本缩放；显式 economics 独立。
缺持仓 raw mark 时，在追加 equity/EOD_MARK 前报错；正常停牌可用此前 raw close。
ON 先调用无写入副作用的 `require_market_marks` 校验全部持仓，再执行原样的
`append_equity_and_eod_marks(..., mark_bars=daily_bars)`；缺 mark 不会留下半写入的 equity/EOD_MARK。
原 P4 AST 不变量测试 `test_book_mark_calls_use_daily_bars_without_touch_or_day_bypass`
保持原断言，mark 调用仍直接使用日线，不引入成交资格或有无当日 bar 的旁路。

## 证据与失败条件

预检在首笔成交之前完成，覆盖冻结池所有代码、研究窗口和原预热窗口。
原始 parquet 在静默去重、零量过滤前检查缺列、重复时间、非法 OHLC、单边缺行；
合法停牌与缺行分开处理，日期遵守湖的交易时钟合同，不猜时区偏移。
输入内容与变换文件绑定哈希，API 同样显式声明三种域并核输入身份。

仅凭一对开盘价不能识别仿射变换。自动等比路径保守要求预热期间已有非退化样本、
整个输入窗口比例不变且所有 OHLC 一致；变化的转换或平价不可识别样本需要显式证据。
通用路径支持 PIT 视图或 `exact_asof_reconstruction`，区分参考可得时点、
生成时点和重建时点，不把最新生成文件冒充历史已发布文件。
固定表示精度检查不是 4090 供应商误差校准，真实数据的容差与来源还需核验。

共同未来乘法/仿射锚点同时作用于 front 和 A/B 时，可抵消于 H_D；测试验证完整成交前缀。
这不证明历史修数、非共同调整、完整数据版本 PIT、s12 日线或策略 11 导出器已正确。

## 变换文件接口：schema v1

`--s12-price-transform-file` 接收 UTF-8 JSON，顶层结构如下。尖括号是待替换占位符，
价格与日期仅展示格式；这份示意不构成可用的权威证据，也不能直接用于真湖验收。

```json
{
  "schema_version": 1,
  "source_snapshot_id": "<冻结快照唯一标识>",
  "sources": {
    "front": {"000001.SZ": {"path": "<resolver得到的1d/front绝对文件路径>", "sha256": "<完整文件SHA256>"}},
    "raw": {"000001.SZ": {"path": "<resolver得到的1d/none绝对文件路径>", "sha256": "<完整文件SHA256>"}},
    "minute": {"000001.SZ": {"path": "<resolver得到的1m/none绝对文件路径>", "sha256": "<完整文件SHA256>"}}
  },
  "provenance": {
    "kind": "pit",
    "algorithm": "<已核验上游算法及版本>",
    "anchor_version": "<冻结锚点版本>",
    "evidence_file": {"path": "evidence.json", "sha256": "<证据JSON完整文件SHA256>"}
  },
  "transforms": [
    {"code": "000001.SZ", "session": "20251023", "A": "1", "B": "-1"}
  ]
}
```

`sources` 三域每域的代码集合必须恰好等于冻结池读取范围，代码使用规范形式如 `000001.SZ`。
每个 `path` 必须对应当前 resolver 实际读到的文件，`sha256` 是整个 parquet 文件的字节哈希，
不是切片 DataFrame 的哈希；建议使用绝对路径，源码中的相对 source 路径相对于进程工作目录解析。
只有 `provenance.evidence_file.path` 的相对路径按变换文件所在目录解析。
读入时会同时记录变换文件和证据文件哈希，不允许三域来自不同次冻结。

`transforms` 必须逐个覆盖预热开始至回测结束期间、过滤双方一致停牌后的**全部配对日线
`(code, session)`**，不能只写除权日、名单日或实际成交日；缺项、多项或重复项均失败。
`session` 使用 `YYYYMMDD`；A/B 建议写十进制字符串，必须有限且 `A>0`。
每行须解释同日全部 OHLC：`front=A*raw+B`，历史信号再统一用决策日这一行的 A/B 重锚。
下面两种证据互斥，`evidence.json` 的 `kind` 和 `source_snapshot_id` 必须与主文件一致。

PIT 证据的 `views` 也恰好覆盖全部变换行，每行包含独立来源及 D 日可得的完整历史视图：

```json
{
  "kind": "pit",
  "source_snapshot_id": "<与主文件一致>",
  "views": [
    {
      "code": "000001.SZ",
      "session": "20251023",
      "source": "<独立PIT视图的可审查来源/版本>",
      "reference_available_at": "2025-10-23T09:00:00+08:00",
      "history": [{"date": "20251022", "close": "10.00"}]
    }
  ]
}
```

每个 `history` 必须按时间顺序完整列出已载入日线中所有 `t<D` 的日期和 D 日 raw 单位 close；
最早载入日可为空，后续不能截短到 MA5/MA10。代码逐项核对它与 `(front_t-B_D)/A_D` 一致。
`reference_available_at` 必须带显式时区，且不晚于该 session 的上海时间 09:30；
仅填写一个较早时间字符串不能替代来源可得性的核验。

精确重建证据则将主文件 `provenance.kind` 改成 `exact_asof_reconstruction`，增加
`provenance.generated_at`（例如 `2026-09-25T12:00:00+08:00`），且每个 transform 增加
`reconstructed_asof`，其日期必须等于该行 `session`。生成时间可以晚于 D，必须如实保留，
不能把最新生成的 A/B 标为当年已发布的 PIT 资料。证据结构为：

```json
{
  "kind": "exact_asof_reconstruction",
  "source_snapshot_id": "<与主文件一致>",
  "common_anchor": {"scale": "0.8", "shift": "0.3"},
  "base_transforms": [
    {"code": "000001.SZ", "session": "20251023", "A": "1", "B": "-1"}
  ],
  "base_front": [
    {"code": "000001.SZ", "session": "20251023", "open": "9", "high": "9.5", "low": "8.5", "close": "9"}
  ],
  "events": []
}
```

`base_transforms` 与 `base_front` 都必须完整且无重复地覆盖主文件全部 `(code, session)`。
上述示意意味着主文件当前锚点的 A/B 应为 `0.8/-0.5`，当前 front OHLC 应为
`7.5/7.9/7.1/7.5`，不是沿用 PIT 示例的数值。代码检查 `scale>0`、每项
`A=scale*base_A`、`B=scale*base_B+shift`、全部 front OHLC 的共同变换，以及 base A/B 与 raw 的关系。
同码相邻日 base A/B 有变化时，`events` 必须有对应的 `code/session` 行，包含
`source`、`confirmed: true`、`from_A/from_B/to_A/to_B` 和已落分的 `reference_raw`；
代码核对系数过渡和重锚参考价。证据应保留上游公式、行动输入与生效时点的可审查来源，
不能用拟合得到的数字自行声明 `confirmed`。

PIT 路径标记 `hash_bound_independent_pit_views`；精确重建路径仅标记
`common_affine_certificate_full_pit_unverified`。后者验证冻结证据的共同变换一致性，
不证明完整历史版本 PIT；真实来源和供应商精度仍须在 4090 核验。
湖文件接口只接受上述两种 provenance；`synthetic_fixture` 仅供内存合成夹具，不可用于真湖文件放行。

## 可重复的合成 A/B

使用已解析解释器运行专用包装器，输出目录应每次新建：

```bash
"$BT_PY" scripts/research/audit_s12_price_domain.py --out-dir "$SYNTHETIC_OUT"
```

`synthetic-ab.json` 保存真实 `run_minute_day` 调用时钟、逐笔账户元组、附加审计字段、
增删/字段差异、每日 raw/book 估值、输入/代码/参数哈希和 OFF 基线哈希。
包装器只观察原 ledger 调用和 mark 调用；不改 trades CSV、不事后排序或重算现金冒充实账。
每笔现金公式分别按 HALF_UP 到分核对，未成交 ledger 调用核对 cash/股数/量预算不变。
限价在调用 ledger 前拒绝的情况保留实际拒绝统计，不伪称捕获了 ledger 未成交调用。

500 万现金、100 万单名预算、raw 恒价 10、默认费率的冻结结果如下。
所有 ON 组均首日买 100000 股一次，期末 NAV 4999000 元；A=1/B=0 两腿成交与账户完全一致。

| 变换 A / B | OFF / ON 成交数 | OFF 期末 NAV | 差异归因 |
|---|---:|---:|---|
| 0.5 / 0 | 0 / 1 | 5000000 | 假涨停池买拒绝及次日拒追 |
| 0.96 / 0 | 1 / 1 | 4959000 | 两个持仓日仅 mark 改变 |
| 1 / 0 | 1 / 1 | 4999000 | 控制组无差异 |
| 1.05 / 0 | 2 / 1 | 5023500 | 首日仅 mark 改变，次日另消除假 MA5 减仓 50000 股 |
| 1.2 / 0 | 1 / 1 | 5199000 | mark 改变；错误跌停参考抑制扫描 |
| 1 / −1 | 0 / 1 | 5000000 | 非零 B 的通用逆变换消除假涨停 |

额外独立合成参考核验：1.014 与半分 1.005 均先落分至 1.01，再算涨停 1.11、跌停 0.91，
三项对照差额均为 0。这里的对照为已知合成值；官方 preClose 不可得，不能冒称官方行情验收。
六组原始账户的 cash + raw 市值 + 累计费用逐日守恒；负现金、股数/量预算残差、未解释差异为 0。
此脚本的量门关闭，量残差为 0 只代表未消耗量预算；容量、显式权益、送转及二次除权、
非零 B 止损边界与完整锚点前缀由 `tests/test_s12_price_domain.py` 的定向夹具另行验证。

## 4090 执行步骤

**真实数据未验证，待 4090。** 本 PR 交付实现、fail-closed 和冻结合成证据。
不得把合成 A/B 当作真湖、收益、跨钟 parity 或生产验收。

1. 记录代码 SHA、解释器/依赖、authority/resolver 结果。只消费已配置湖；缺配置/文件即失败。
2. 冻结 `20251023–20260909`、原预热窗口、原池文件及行序、名称、参数、费率、seed、
   三种价格源和变换证据。固定文件内容哈希，关闭两条腿的旧分钟缓存。
3. 同输入先 OFF，再只开 X-01；使用不同输出目录，不覆盖原回执。
4. 保留逐笔元组 `(date, code, side, price, shares, reason, cash_before, cash_after, hm)`，
   同时记录 append_seq、decision/quote 时钟、phase、lot、佣金、量桶、参考价和域。
   逐事件金额按 Decimal HALF_UP 到分校验，股数精确守恒。
5. 差异区分阈值、限价、估值和后续传播；报告首个分歧、只改 mark 的日期、拒绝统计、
   最低现金、负余额、股份/量残差及未解释项。未解释项不能以期末 NAV 接近放行。
6. 除权日单列未落分参考 → 已落分参考 → 涨跌停，和独立 preClose/公司行动公式逐分对照。
   当前 loader 不提供官方 preClose；不可得时必须明示，推导值不能冒充官方行情。

```bash
"$BT_PY" backtest/research/csv_minute_backtest.py \
  --strategy 12 --start 20251023 --end 20260909 \
  --cash-total 21000000 --daily-quota 1000000 --name-budget 1000000 \
  --pool-dir "$FROZEN_POOL" --minute-source lake --daily-source lake \
  --dividend-type none --no-cache --fix-s12-price-domain \
  --s12-price-transform-file "$TRANSFORMS" --emit-run-manifest --out-dir "$ON_OUT"
```

## 保留限制

δ6：economics 默认 OFF；转换不会送股或发钱，raw 账户不是完整总回报。
显式送转/红利仍按原资格、上市/支付日期与记忆规则记一次。成本、peak、lot 身份和台阶锚不改。
无当日 bar 的公司行动估值另有局限，不补未来报价。
ST 档位、浮点台阶、追买预算、止损丢台阶锚、预热等独立问题均未修。
现核“不足一价位则增减一价位”和最低价位规则未修，不能宣称限价覆盖所有交易所边界。
X-02/X-03 及 B11 不在本 PR；T+1、周期 latch=A、双通道 residual=2、#169 信号 lot、
#170 lot0 保底、v11 volume=A、午休排除、既有费用/容量/时钟及全部 M01–M18 保持。
