# a-stock-data 三路独立研究综合（SYNTHESIS）

- 综合日期：2026-10-09（Asia/Shanghai）
- 研究对象 HEAD：`8f6a6a53a59813bf5f010875f16f794fdc4f44f4`（与 tag `v3.10.1` 同提交；作者日 2026-10-07）
- 路径：`/workspace/a-stock-data`；对照 `/workspace/OSkhQuant1.3`、`/workspace/MyQuant-backtrader`
- 原始报告：
  - Codex ✅ [`report-codex.md`](report-codex.md) · log `log-codex.txt`
  - Grok CLI ✅ [`report-grok.md`](report-grok.md) · log `log-grok-final.txt`（初试 ENXIO / `dontAsk` 卡权限；`bypassPermissions`+PTY 成功）
  - Cursor Agent ✅ [`report-cursor.md`](report-cursor.md) · log `log-cursor.txt`（首轮 Connection lost×3）+ `log-cursor2.txt`（重启后落盘）

未采信用户草稿为真；三路均为只读本地核查（Cursor 仅额外 `git ls-remote --tags`）。未批量扫东财、未访问 4090 corp-actions。

---

## 三路高度一致

1. **形态**：自包含 Skill（`SKILL.md` ≈7577 行 Markdown+内嵌 Python），非 pip 包、非本地行情库、无回测引擎。
2. **口径**：当前内容为 **v3.10.1 / 15 层 / 87 入口（82+5）/ 34 来源**；`SKILL`/中英文 README/CHANGELOG 版本徽章一致。应以**固定 commit 的 SKILL 实现**为准。
3. **草稿纠偏**：用户草稿称「README/Release 停在十层」——对 **本 HEAD**，三路均确认 README **不**滞后。Layer 1 旧 § 编号在历史段落中滞后，属仓库自声明保留。
4. **#52 TDX**：公开服务器 K 线/盘口/逐笔空返回；财务/F10 仍可用；行情改腾讯 / 盘后包 / `tencent_ticks`。
5. **#57 成交量**：科创 688/689=股，其余多为手；v3.10.1 **只改文档不改数值**。
6. **复权**：腾讯 qfq 等差 ≠ 新浪比例阶梯 ≠ QMT `front/none` 因子；不可写入湖因子或 E-R6 的 `k`。
7. **东财双轨**：旧 `eastmoney_datacenter` 伪空（资金面/分红受影响）；v3.9+ `_em_datacenter_strict` 才区分空/坏。
8. **CYQ**：本地推演+首日播种，非交易所筹码。
9. **组织边界**：1.3 写湖、BT 只消费；公开价**绝不可**进 live/paper 决策价（原则㉑：`get_full_tick`+`instrument_detail`）。
10. **corp-actions 路径** `D:\exports\bt_corp_actions_20261006`：三路均未访问；两对照仓文档**无接线引用**；schema/入湖**未核实**。

---

## 分歧与需裁决的事实差

| 议题 | Codex | Grok | Cursor | 综合裁决 |
|---|---|---|---|---|
| GitHub tag/Release 是否落后 HEAD | Release `v3.10.1`=Latest，指向 `8f6a6a5`，与本地 tag 一致 | tag `v3.10.1`≡HEAD | 写「本地/远端最新 tag 仍是 v3.9.0，落后两小版」 | **Cursor 此项有误。** 本机 `git tag` 与 `ls-remote`、GitHub Releases API 均可看到 `v3.10.1`（2026-10-07）。消费方仍应以 commit 钉死，但「tag 停在 3.9」不成立。 |
| Kimi `limit_7d`/`limit_5h` | 指向 `grok-bot-raci-workflow-ssot.md` §3.1 | 同左；并说明是 kimi-code 账号窗而非 Wind 合同 | 「三仓文档未找到，未核实」 | **Codex/Grok 正确**；Cursor 漏检该 RACI 文档。当前 used_ratio 仍无人实测。 |
| 旧 helper 伪空证据强度 | 注入失败 JSON 本地复现 `[]` | 主要引文档 | 强调 Layer4 全走旧 helper + 文档自述 | 同向；Codex 执行级最强。 |
| 优先小探针 | 离线单测 / 四票量价 / 分红 schema 缺口 | 同左（略改表述） | **申万 PIT 落地对照 / 2027 日历 / lifecycle spike** | 两套都小、互补；见文末合并建议。 |

---

## 各自独特发现

**Codex**：证据三分类；`norm→get_prefix` 丢市场可复现；`apply_adjust` 负因子/NaN；`oskh_data/__init__.py` 旧简介 vs 原则㉑冲突。

**Grok**：浅克隆边界；`stockstats` 声明但未 import；E-R5/E-R6 与「绝不可入决策价」操作清单最细；大商所 412→新浪日 K。

**Cursor（额外高价值）**

- 备用源 `ssl.CERT_NONE`（`SKILL.md` ~7407，深交所龙虎榜/公告备份）——权威降级路径反关掉 TLS。
- 无 CI（`.github/` 仅 FUNDING）；177/173/4 测试计数自数吻合 README。
- 盘后包日期/北交所二分边界表；腾讯分钟第 8 字段=换手率基点非成交额。
- 明确：**申万 PIT 变迁是公开源相对 Wind 当前快照的稀有优势维度**。
- 探针指向 2027 日历 vs `pandas-market-calendars`、BT lifecycle fail-closed。

---

## vs OSkhQuant1.3

**已有、勿再造生产链**

- 三类存储 SSOT：`docs/operations/data-three-stores-ssot.md` + `common/infra/data_root.py`（`OSKH_SOURCE_PARQUET_ROOT` 必填）。
- QMT 日更与因子：`docs/backtest/data/daily-adjusted-update-ssot.md`、`oskh_data/adj_factor.py`、`ex_date_index`（`stock_code,ex_date,dr,fetched_at`）。
- ST 五渠道：`docs/operations/st-data-channels-ssot.md`；申万**当前**名：`oskh_data/vendor_wind_sw_l1.py`；巨潮公告库；指数/ETF 副轨价格。

**重复**：OHLCV/复权/因子、当日 ST 快照、当前申万名、公告主链。

**补缺候选（研究旁表；1.3 写湖或 BT 显式读）**

- 申万**变迁史**（有 `start_date`，无中文名）——三路共识的最优先公开补缺。
- 东财事件六表、研报/新闻/打板/宏观/可转债条款。
- 中证/国证**当前**成分权重、深交所月历。
- 单日通达信盘后包对湖 `none` 抽查；baostock 沪深上市/退市核查（无北交所）。

---

## vs Kimi/Wind

| | 留 Wind/Kimi | 可迁 a-stock-data（省额度） |
|---|---|---|
| 内容 | 沪京 ST 历史事件；corp-action 经济事实（pay/list）；北交所历史；分钟补缺 `wind_get_stock_quote`（START→END，禁盲平移） | 申万 PIT；沪深上市退市对照；研报/新闻/事件旁证；宏观；当前指数文件；单日盘后抽查；日历交叉体检 |
| 成本/故障 | 扣 `limit_7d`/`limit_5h`；QUOTA≠FAIL；空批 write-empty | 零 Key（iwencai 除外）；IP 封禁/伪空/接口漂移；旧入口空坏不分 |
| 分红 | 未核实的 4090 包 + QMT `get_divid_factors`/`ex_date_index` 仍是价格侧权威 | `dividend_history` 仅线索，缺 pay/list/event_id，默认≤20 行 |

深市 ST 日常已走深交所免费渠，**不必**为 a-stock-data 再迁一遍。

---

## 合并后的下一步（仍保持小）

1. **隔离 venv 离线单测** + 旧 helper 伪空 / 因子正有限回归（Codex/Grok）。
2. **申万 PIT 一次 HTTP 落地**，与 `vendor_wind_sw_l1` 今日一级对照（Cursor；省额度）。
3. **四票×一日量价**或 **分红 schema 缺口表**（二选一先做）；日历 2027 diff 可作为并行低风险探针。

---

## CLI 账本

| CLI | 状态 | 备注 |
|---|---|---|
| Codex `gpt-6-astra` ultra | ✅ | ~9.5 min |
| Grok `grok-4.7` | ✅ | 需 PTY + `bypassPermissions` |
| Cursor `agent -p --force` | ✅（二次） | 首轮 API Connection lost；重启后 ~12 min 落盘 |

全部产物目录：`/workspace/a-stock-data-reviews/`
