# 2026-09-09 hive 分树消费者同步交接：MyQuant-backtrader

> **写给**：MyQuant-backtrader（`E:\PycharmProjects\MyQuant-backtrader`）的同步重构执行者（人或 agent）。
> **背景**：OSkhQuant1.3 于 2026-09-09 午休完成 F 盘权威 parquet 湖三树化（plan #922 v1.5，PR #929 → 0450cc1f，S2a/S2b 数据面已即时执行）。
> **权威参照**：plan [`plan-hive-ashare-pure-index-etf-split-l2-2026-09-09`](../engineering/plan-hive-ashare-pure-index-etf-split-l2-2026-09-09.md)｜执行记录 [`2026-09-09-hive-ashare-split-s0-s1`](../run-records/2026-09-09-hive-ashare-split-s0-s1.md)。
> **一句话**：MyQuant-backtrader vendored 的是**改前数据面**——本机因 env 已改指，股票日线/分钟读取自动跟到新树（当前能跑）；但**无 env 环境（默认解析）会指到已消失的旧根**，且 **ETF/指数读取正依赖 S5 将删的 legacy 副本**。两条断供轴必须同步修。

## 1. 磁盘终态（2026-09-09 12:16 起已生效）

```
F:\stock_data\
  stock\period=1d\dividend_type={none,front}\symbol=*\data.parquet    # 股票日线（env 指此）
  stock\period=1m\dividend_type=none\symbol=*\data.parquet            # 股票分钟（env 指此）
  index\period=1d\dividend_type=none\symbol=*\data.parquet            # 指数日线（none-only！）
  etf\period=1d\dividend_type={none,front}\symbol=*\data.parquet      # ETF 日线
  quarantine\20260909_1m_nonstock\...                                 # 1m 脏分区隔离区（勿读）
```

- **旧根 `F:\stock_data\period=1d`、`period=1m` 已不存在**（同卷 rename 进 `stock\`）。
- **不变项**：分区名 `symbol=CODE_EXCH`（下划线，如 `symbol=000001_SZ`）、`time` 列 epoch 毫秒（日线 UTC 午夜）、列 schema（time/open/high/low/close/volume/amount）、`.authority` marker 仍在容器根。
- **index 树 none-only**（v1.3 人裁锁：既有指数 front 丢弃，未迁移）。

## 2. env 矩阵（本机 HKCU+HKLM 双注册表已生效）

| env | 旧值（2026-09-09 12:16 前） | 现值 |
|---|---|---|
| `OSKH_PERIOD_1D_ROOT` | `F:\stock_data\period=1d` | `F:\stock_data\stock\period=1d` |
| `OSKH_PERIOD_1M_ROOT` | `F:\stock_data\period=1m` | `F:\stock_data\stock\period=1m` |
| `OSKH_INDEX_DAILY_ROOT` | （无此变量） | `F:\stock_data\index\period=1d` |
| `OSKH_ETF_DAILY_ROOT` | （无此变量） | `F:\stock_data\etf\period=1d` |
| `OSKH_SOURCE_PARQUET_ROOT` | `F:\stock_data` | 不变 |

陷阱：①**setx 前启动的 shell/进程仍持旧值**（幽灵旧根事件实证，见 run-record §3）——重启 shell 生效；②`unset` ≠ 回滚（flip 铁律），回滚=显式 setx 旧值+搬回目录。

## 3. MyQuant-backtrader 现状盘点（2026-09-09 13:2x 实测）

| 事实 | 影响 |
|---|---|
| vendored `common/infra/data_root.py` 为**改前形态**（`resolve_period_root` 默认 `container/period={p}`，L215），且与 1.3 合并前版本（e816902944）**也有差异**（更旧或本地改动） | 不能整文件盲拷，须先 diff 再语义合并 |
| vendored `oskh_data/reader.py` 含旧 etf 劫持形态（L477/569/661：`_resolve_period_root(period, base=etf_dir)`，env 胜 base） | ETF 读在 env 下被劫进 `stock\` 树读 **legacy 副本**——**S5 删除后断供** |
| 无 `oskh_data/lake_kind.py` | 缺三树分类路由 |
| 自有胶水（`qmt_utils_adv.py`/`backtest_main_full.py` 等）无硬编码盘符/period 字面 ✓ | 胶水层基本不用动 |
| 对端 `tr/backfill_turnover_resistance_bands.py:42` 有 `data_dir / "period=1d"` 字面 join（1.3 本仓对应文件在 `scripts/data/` 下，#932 已改） | 会读已消失的旧根，须改 resolver |
| vendored `tests/test_data_path_authority_marker.py:66` 断言旧默认根 | 同步后须校准为 `stock/period=1d` |

**当前（同步前）各读取路径的行为**：
- 股票 1d/1m（env 已指新树）：**正常** ✓（本机新起的 shell/进程）。
- 股票 1d/1m（无 env 环境，如 CI/别的机器）：默认解析指旧根 → **FileNotFoundError** ✗。
- ETF（`asset_type="etf"`）：env 劫持进 `stock\` 树 → 暂时能读到 legacy 副本 → **S5 后断供** ✗。
- 指数（如 `000300.SH` 按股票读）：同上，读的是 `stock\` 树内 legacy 副本 → **S5 后断供** ✗；终态应读 `index\` 树。
- 1m 的 `000300.SH`/`159915`/`510050`/`588000`：已 quarantine → 读空（新世界正确语义）。

## 4. 同步重构步骤（建议序）

1. **取参考实现**（1.3 @ `7362ca2361`，均随 #929 合入）：
   - `common/infra/data_root.py`：`resolve_period_root` 默认 `container/stock/period=*`（新根优先·仅旧根存在时回落）+ `resolve_index_daily_root`/`resolve_etf_daily_root`（**永不读 `OSKH_PERIOD_1D_ROOT`**）；
   - `oskh_data/lake_kind.py`（新文件）：`classify_daily_lake_kind` 带后缀裁决（ETF=前缀 SSOT `is_etf_code`；指数=`000xxx.SH`/`399xxx.SZ`；A股=SH 60/68·SZ 00/30·BJ 43/82/83/87/92；其余 unknown fail-closed；**裸码不猜后缀**——`000001` 裸码≠上证指数）；
   - `oskh_data/reader.py`：`_lake_period_root`（etf 读者走 `resolve_etf_daily_root()`，显式 `base_dir` 语义保留）等 6 处 + `build_persistent_db(asset_type=)`；
   - `oskh_data/daily_parquet_write.py`（`_file_path` 三树路由）、`oskh_data/downloader.py`（分钟树仅股票）——**即使该 repo 只读不写也建议带上**（防将来误写回旧根/写穿污染）；
   - `tests/test_hive_lake_kind_and_roots.py`（39 例，含 F6 劫持回归）。
2. **先 diff 后合并**：vendored `data_root.py` 与 1.3 的 e816902944（改前基线）diff，弄清差异是"更旧"还是"本地魔改"；本地魔改部分人工保留，其余按新实现合并。
3. **校准 vendored 测试断言**：默认根 `marker/period=1d` → `marker/stock/period=1d`。
4. **修 TR 字面**：`backfill_turnover_resistance_bands.py:42` 改 `resolve_period_root("1d")`。
5. **验收**（照抄可跑，见 §5）。

## 5. 验收清单

```python
# ① resolver 断言（无 env、marker 在 F 时）
from common.infra.data_root import resolve_period_root, resolve_index_daily_root, resolve_etf_daily_root
assert str(resolve_period_root("1d")).endswith(r"stock\period=1d")
assert str(resolve_index_daily_root()).endswith(r"index\period=1d")
assert str(resolve_etf_daily_root()).endswith(r"etf\period=1d")

# ② F6 劫持回归：设 OSKH_PERIOD_1D_ROOT 不得影响 etf 根
import os; os.environ["OSKH_PERIOD_1D_ROOT"] = r"F:\hijack"
assert "etf" in str(resolve_etf_daily_root()) and "hijack" not in str(resolve_etf_daily_root())

# ③ 四树实读（pyarrow）
import pyarrow.parquet as pq
for f in [r"F:\stock_data\stock\period=1d\dividend_type=none\symbol=000001_SZ\data.parquet",
          r"F:\stock_data\stock\period=1m\dividend_type=none\symbol=600519_SH\data.parquet",
          r"F:\stock_data\index\period=1d\dividend_type=none\symbol=000001_SH\data.parquet",
          r"F:\stock_data\etf\period=1d\dividend_type=none\symbol=510050_SH\data.parquet"]:
    assert pq.read_table(f, columns=["time"]).num_rows > 0
```

另：回测主链端到端跑一只股票（`backtest_main_full.py` 单票 smoke）确认 Cerebro feed 无感切换。

## 6. 陷阱与时间线

- **S5（1.3 侧待二次人签）将删 `stock\` 树内 legacy 指数/ETF 分区**（1d none 7 个、front 4 个）——同步完成前，指数/ETF 读取看似能跑是**假绿**（读的是待删副本）；同步后读 `index\`/`etf\` 树才是终态。
- `F:\stock_data\quarantine\20260909_1m_nonstock\` 4 个 1m 分区：**勿读勿删**（处置待 1.3 侧 S5 人裁）。
- E 盘旧副本（`E:\PycharmProjects\OSkhQuant1.3\stock_data\period=*`）= 回退点，1.3 未动，勿当数据源。
- etf 树 `159915` 止于 2026-07-31（主湖副本数据可疑未合并），gap 由 1.3 副轨更新补——若你的策略读它，近期日期可能缺。
- 指数 front 复权数据已按人裁**永久丢弃**（none-only），别试图从旧根找回。

## 7. 变更责任与后续

- 磁盘布局/env/1.3 代码：本仓负责（本 PR 链 #929/#930）。
- MyQuant-backtrader 侧同步：按本文 §4 执行；若 vendored 副本后续有同步机制（脚本/子树），建议以 1.3 的 `common/infra` + `oskh_data` 为源做一次基线对齐。
