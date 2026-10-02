# OFF 字节基线与 #205 参数回显

`tests/fixtures/off_byte_baseline_eff77f3.json` 继续保存原始 eff77f3
的字节和账户快照，不覆盖、不重新命名。SHA-256 为
`3bfe51b6d3e20b665c3fed0449ebf8569988022719da275b7fcc9635a9988c6c`。

## master 为什么红

父链为 `eff77f3 → 6c438d8 (#205) → fdb5158 (#202)`。
[#202 成功 CI](https://github.com/baiyibing/MyQuant-backtrader/actions/runs/36147213447)
测试的是 `1e50ee12` 合入 eff77f3 的临时 merge `a17dbd8`，未包含 #205。
随后 #205 先合入，新增 `SimState.stats.daily_quota` 用于 summary 回显；
#202 的历史 structured 比较因这一新增键在 master 出现 76 failed / 3 passed。
原测试先检查 production/library CSV hashes 和 fill_counts，再检查 structured；
此次独立重跑也验证了这些比较，未依赖断言短路顺序。

## 历史核实

在三个提交的原样生产源码上运行同一份 fdb5158 capture harness：
19 本 × 日线/分钟 + 独立 v7 分钟 = 39 组，省略开关/显式关闭各一遍。
共 234 captures、468 份生产 CSV；同时核对 library serialization。

| 对比 | trades/equity 原始字节、两套 SHA-256、fill_counts | structured |
| --- | --- | --- |
| eff77f3 重生成 vs 原 golden（两种 OFF） | 全相同 | 全相同 |
| eff77f3 → 6c438d8（两种 OFF） | 全相同 | 每个非 v7 组合仅新增 `stats.daily_quota = 1000000.0`；v7 无变化 |
| 6c438d8 → fdb5158（两种 OFF） | 全相同 | 全相同 |
| 每个提交 omitted → explicit-off | 全相同 | 全相同 |

现金、持仓、成交、权益曲线、费用及所有既有 stats 均不变。
唯一新增键来自 [#205](https://github.com/baiyibing/MyQuant-backtrader/pull/205)
的 `init_sim_state`：日线/分钟 simulate 将已有 quota 传入并记录。
summary 的 quota 回显不属于 structured 或 trades/equity CSV。
该矩阵显式传入 1M quota，直接调用 simulate；不经过 CLI 的资金模式解析。
#205 对未显式指定 quota 的 topk CLI 默认行为确有改变，本结论不覆盖该场景。

## 比较契约（方案 B）

`post205_expected_case` 仅在历史 expected 的副本中为非 v7 添加
`structured.stats.daily_quota = 1_000_000.0`，并先断言历史 stats 不含此键。
随后仍全量比较 structured：新字段必须存在且等于固定值，其它新增字段、
所有旧字段漂移仍失败。v7 不作适配。fill_counts 全量比较不变；
CSV 两套原始哈希在相同 pandas major.minor 下继续精确比较，跨版本规则见下节。
pytest 和生成器 `--check` 共用该规则；原始生成的 HEAD/禁止覆盖保护保留。
此方案保留与 eff77f3 的直接证明，避免复制近乎相同的新 golden。

复查入口：`tests/test_off_byte_baseline.py`（79 项）及
`scripts/research/generate_off_byte_baseline.py --check`。
完整逐组旧→新字段表、三版本快照、原始 CSV 和运行日志归档于
`/home/box/agent-data/bt-minute-fix-2026-09-25/baseline205/`，见
`root-cause.md`、`comparison.json`、`capture-manifest.json`。

## pandas 版本稳健化与 CI 锁定 3.0.6

4090 开发机报告 pandas 2.3.3 下旧字节检查失败；原 `pandas>=2.0`
允许安装结果随时间变化。BT 统一 `pandas==3.0.6`，CI 安装后打印并断言版本。
选择精确 `==`，因为 `~=3.0.6` 仍允许将来 3.0.x 补丁未经验证就改变序列化。
固定前后全新 pip 解析的 29 个包版本，与 bd422e9 的成功 CI 实际安装逐项一致；
未因本次锁定改变其它包。该审计不代表其它依赖也已锁定。
**开发机（4090 当前 pandas 2.3.3）需要升级到 pandas 3.0.6**：使用该机
BT 解释器执行 `-m pip install -r requirements.txt`。

原 golden 已记录 `captured_environment.pandas = "3.0.6"`，Python 3.12.14/Linux。
再次提取 eff77f3 原样生产源码，注入 fdb5158 的原始 capture harness，
在 pandas 3.0.6 下重跑 39 组 × omitted/explicit-off：78 次 structured/fill_counts、
156 个 production 原始哈希及 156 个 library 原始哈希均与原 golden 完全相同；
原 golden 的文件 SHA-256 仍为本文开头所列值，**没有重录任何原始字节哈希**。

canonical 参考新增于
[`off_canonical_baseline_eff77f3.json`](../../tests/fixtures/off_canonical_baseline_eff77f3.json)。
它只保存上述已逐字节核实的 **eff77f3 输出**的 canonical 摘要，记录源提交、
原 golden 文件 SHA-256、生成环境和精度契约，不以当前逻辑的输出作为参考。
不能仅从旧 `structured.fills` 推导完整 trades：它只含 BUY/SELL，
17 组 CSV 另有共 30 行 `EOD_MARK`。新摘要覆盖这些行，避免跨版本漏检期末持仓标记。
同时已逐组核实原 CSV 的 BUY/SELL 子集与 structured fills、全部 equity 与
structured equity 一致，现金与原快照一致；两种 OFF 的 canonical 完全相同。

canonical 的固定定义为：

- 用标准库 `csv.DictReader` 解析 production 和 library 的 trades/equity，
  不经 pandas 或浮点重解析；保留所有行、列及顺序。
- 日期、代码、方向、原因及其余文本原样保留，包含大小写、空字符串和 `EOD_MARK`。
- `shares`、`lot`、`hm` 通过 Decimal 验证为精确整数，拒绝小数股数，不经浮点转整数。
- `price`、`notional`、`commission`、`cash`、`holdings`、`equity` 使用
  `Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)`，
  固定 8 位小数，保留亚分价格/费用并消除浮点尾差；拒绝 NaN/Infinity。
  CSV 输入直接使用原字符串。账户最终现金以同一精度对照原 structured。
- canonical 表按 UTF-8 JSON（`ensure_ascii=False, sort_keys=True, separators=(',', ':')`）
  计算 SHA-256；列序单独记录，JSON 键排序不丢失列序。
  原完整 structured（含现金、持仓、费用、权益、stats）仍额外执行未量化的精确比较。

每个参数化测试先强制验证两套 canonical、现金、fill_counts 和完整 structured，
任何差异直接失败。之后比较 pandas major.minor：相同（包括不同 3.0.x 补丁）
继续执行原有 production/library 两套原始字节 SHA-256 精确比较及二者相等断言；
不同时才调用 `pytest.skip`，原因明确列出 golden 与运行版本，以及 canonical 已通过。
因此跨版本终态显示 skipped 的 78 项都已执行 canonical，而非整项提前跳过。
生成器 `--check` 同样先强制断言 canonical，再明确打印字节 SKIP；CLI 不依赖 pytest。
原 Linux LF / 独立 v7 CRLF 字节契约保持不变。

临时环境仅替换 pandas 为 2.3.3 并添加其必需的 pytz，其余 bt-ci 包保持一致。
3.0.6 的基线为 **79 passed**；2.3.3 为 **1 passed / 78 skipped**，
skip 原因为 `golden pandas=3.0.6, runtime pandas=2.3.3 (major.minor differs)`，
并明确 `canonical trades/equity/cash and full structured assertions passed`。
2.3.3 的生成器 `--check` 另报告 **39 canonical CSV/account cases PASS**；
25 项防退化测试在两个版本均通过。最终全套与 CI 回执见 PR #207 和外部 `result.md`。
该 Linux/NumPy 环境下旧测试也通过，未复现 4090 的原始字节错误；
本次跨版本实验证明显式 skip 和强制 canonical 的行为，不据此认定该机器差异的唯一来源。
新增 mutation 测试验证股数、价格、原因、EOD_MARK、现金、权益、library 输出和
quota 元数据漂移在 skip 前失败，且同 major.minor 的字节漂移仍失败。

证据在原归档目录：`pandas-provenance/`（原源码、CSV、raw/canonical 来源证明）、
`audit-scripts/`（独立复现脚本）、`pandas-dependency-audit.json`、
`pandas306-baseline.log`、`pandas233.log`。本次不触碰 zcode 的 #206，不合并 PR。
