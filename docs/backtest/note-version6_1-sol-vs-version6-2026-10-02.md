# 策略 6.1 sol · 与 version6 对照 + known-baseline 盘点

| 字段 | 值 |
|---|---|
| 日期 | **2026-10-02 CST（Asia/Shanghai）** |
| tip 基线 | **`3f7af6a2684f0f428a8ddde0895f51c9a25f63f3`** |
| 性质 | **最小忠实 sol（docs + 入口可见性 + 参数锁测）**；不改卖点公式、不写湖、不上 4090 |
| 代码锚 | `backtest/research/strategy6_rules.py` · `strategy6_1_rules.py` · `csv_strategy_books.py` |
| 人裁落地 | `bee0b91`（策略 6.1）+ `#301` OFF overlay（`5f31528` / merge `9033f14`） |
| 边界 | ≠δ5≠R4；≠生产写湖；≠ host PASS；≠ New 真核合同；永不进 BOOKS 默认改口（书已注册，本票只补文档） |

## 0. 一句话

**version6_1 已在 tip 落地**（无上限梯子止盈 + per_name 100 万独立组）。本 sol 只做三件事：  
① 钉死 **v6 vs v6.1** 差分表（忠实于人裁 Q1–Q5）；  
② 盘点 **OFF known-baseline** 分层（历史不可变 + S8 overlay + v61 overlay）；  
③ 把入口文档补到「好用干净」——能在 README / AGENTS / 研究入口找到 `version6_1`。

**不**重跑湖回测、**不**改 MatchCore / Fees / `simulate`、**不**重录历史 golden。

## 1. v6 vs v6.1 对照（忠实）

| 轴 | `version6`（`BOOK_TAG=v6`） | `version6_1`（`BOOK_TAG=v6_1`） |
|---|---|---|
| CLI | `--strategy version6`（别名 `6` / `v6`） | `--strategy version6_1`（别名 `6.1` / `6_1` / `v6.1` / `v6_1`） |
| sizing | `daily_quota`（日额度均分） | **`per_name`**，`name_budget=1_000_000`（整笔） |
| 止损 | **2%**（`STOP_PCT=0.02`，T+1 起） | **5%**（`STOP_PCT=0.05`，T+1 起） |
| 止盈时钟 | `TP_MIN_DAYS=1`（T+1 起评） | 同左 |
| 止盈形状 | 两档回撤：峰值涨幅 &lt;6% → 回撤 70%；≥6% → 回撤 50%（`trail:band:lt6` / `ge6`） | **无上限梯子**：峰值涨幅 A 每 5% 一档；离场回撤 `B=5%+2%×档号`；理由 `trail:ladder:{5×档}` |
| 离场价公式 | `cost + keep×(peak−cost)`；`keep=0.30`（lt6）或 `0.50`（ge6） | `peak − cost×B`（人裁 **Q1=G**） |
| 成本下方止盈 | **禁止**（`px < cost` → None） | **允许**（人裁 **Q2**） |
| 档位上限 | 两档封顶 | **无上限**（人裁 **Q3/Q4**） |
| 加仓 | 名单再现可加（输家也加）；daily_quota 均分 | 复用 s8 **独立组**：+20% step 并入首次仓同进同出；名单再现 = 新独立组；同日可与 step 并存（人裁 **Q5**） |
| 峰差 | 15 分钟 | 同左 |
| 买侧 | 引擎既有（尾盘名单 / T+1 09:45 追买） | 同左（本票未改） |
| 全局现金 | CLI `--cash-total`（历史常用例） | CLI `--cash-total`（人裁示例 **40 亿**） |
| 落盘 tag | `csv_{daily\|minute}_v6_{start}_{end}/` | `csv_{daily\|minute}_v6_1_{start}_{end}/` |
| 规则模块 | `strategy6_rules.py` | `strategy6_1_rules.py`（**新书，不改 v6**） |

> **非宣称**：本表 ≠ NAV 对照、≠ 绿 R、≠ 字节等价。v6 与 v6.1 故意不等价；差异须用独立 `--out-dir` / 独立书名复现，禁止改 golden 伪装。

## 2. known-baseline 盘点（OFF 字节）

权威 overlay 说明：[v61-off-byte-overlay-2026-10-02.md](v61-off-byte-overlay-2026-10-02.md)（#301）。

| 层 | 文件 | 角色 | 可变？ |
|---|---|---|---|
| **历史 raw** | `tests/fixtures/off_byte_baseline_eff77f3.json` | 19 书 × 日/分钟 + v7 分钟骨架；SHA-256 `3bfe51b6…8c6c` | **不可变** |
| **历史 canonical** | `tests/fixtures/off_canonical_baseline_eff77f3.json` | 同上 canonical；SHA-256 `34f611da…a04e` | **不可变** |
| **S8 overlay** | `tests/fixtures/off_byte_baseline_s8_independent_20260926.json` | 前例 #212；独立组校正 | 仅 S8 语义票可动 |
| **V61 overlay** | `tests/fixtures/off_byte_baseline_v61_20261002.json` | 仅 `version6_1/daily` + `version6_1/minute`；`rule_revision=v61-unbounded-ladder-2026-10-02` | 仅 6.1 规则改口后 `--record-v61`（禁覆盖已存在） |
| **校验合计** | `generate_off_byte_baseline --check` | 27 未改历史 + 12 S8 + 2 v61 = **41 case** | — |

**明确不在本 sol 范围**：

- TopK frozen-bytes / version12 OFF-byte tip 红项（已知 scatter；不拿来挡 6.1）
- New 真核 C-New / MatchCore 扩展 / 生产写湖 / 4090 host
- 把 v6.1 「迁入」New 核或 BOOKS 默认

录制 / 校验命令（pandas **3.0.6**）：

```text
python -m scripts.research.generate_off_byte_baseline --record-v61   # 已存在则拒绝覆盖
python -m scripts.research.generate_off_byte_baseline --check
pytest tests/test_off_byte_baseline.py -k 'not version12'
pytest tests/test_strategy6_1_rules.py tests/test_version6_1_sol_compare.py
```

## 3. 入口可见性（本 sol 补丁）

落地前 tip 已注册 `version6_1`，但根 README / AGENTS / 研究入口表仍写「1…6/8…」，易漏。本票最小补丁：

- `README.md` / `AGENTS.md`：choices 文案含 `version6_1`
- `docs/backtest/README.md`：策略 6 段落后补 **策略 6.1** 一段
- `docs/backtest/research-backtest-entry.md`：§4 表加一行
- `tests/test_version6_1_sol_compare.py`：锁上表关键常量差分（不锁 NAV / 不锁 writer 字节）

## 4. 非目标 / 锁

- ≠δ5 certified ≠R4  
- 不盲写生产湖、不上 4090、不改 MatchCore / Fees / `simulate` / source_loader  
- 不改 `strategy6_rules.py` / `strategy6_1_rules.py` 卖点数字（已人裁）  
- 不重录历史 OFF golden；不碰 TopK frozen-bytes  
- **勿合**；等人裁「合」或「grok核了再合」

## 5. 残差（另 GO）

| 项 | 说明 |
|---|---|
| 宿主同窗 NAV 对照 | v6 vs v6.1 真湖分钟对照（须人裁窗 / cash / pool） |
| New 核迁书 | 仅当 Human 点名把某书迁到 C-New；默认不迁 |
| 生产写湖 / 4090 | 真核残差另票；≠ 本 sol |
