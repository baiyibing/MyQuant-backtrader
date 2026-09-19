<!-- agent=cursor:auto cmd-prefix=/home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/node /home/box/.local/share/cursor-agent/versions/2026.09.18-9a7762b/index.js --model auto -p --output-format text --trust -f --mode ask --workspace /workspace/wt-p3-d345-econ-plans <prompt> -->
核验范围：五份 plan 全文 + `IMPLEMENTATION_BASE=1049b90` 源码/测试（base→HEAD 仅五文档）；交叉对照了 `pattern-evidence` / `domain-safety` 已有发现。侧重 **SSOT 一致性与行级精确性**。

---

## 🔴 必须修

**1. δ4 书侧「未知板块→早拒」真值表漏掉 named-band / `qlib_limit_pct` 前提（与 δ3 SSOT 矛盾）**

- 文：`plan-…-d4-…md:38-39`（及 `:47` 书侧早拒概括）把「未知板块」无条件写成 `skip_unknown_board`。
- δ3 已钉例外：`plan-…-d3-…md:32` → `csv_common.py:80-82` 在 `qlib_limit_pct is not None` 时走固定 band，绕过 named limits。
- 生产接线真实存在：`csv_strategy_books.py:713`、`:788` 为 topk 书设置 `qlib_limit_pct`；daily/minute held 传入该 hook（`csv_daily_backtest.py:320-321`、`csv_minute_backtest.py:612-614`）。
- 静态反例：未知非 ST 前缀 + 有效昨收 → named-band 得 `None`；同码 + `qlib_limit_pct=0.095` → 有档位，不进 `skip_unknown_board`。
- **风险**：独立审 δ4 会把 topk 固定 band 路径误判为回归，或诱改 helper。最小回填：表头/行限定「默认 named-band、非 ST、且算得 `limits=None`」；增固定 band 对照行。

**2. δ6 书 NAV as-built 写成普遍「raw close」（与 δ2 入口域 SSOT 冲突）**

- 文：`plan-…-d6-…md:28`「原股数×当日/最近历史 **raw** close」。
- 实：`csv_ledger.py:173-178` / `csv_simulate_loop.py:399-403` 只消费传入 bars 的 `close`，无 raw 认证。
- δ2/本刀自身也保留混域残留（δ6 `:52`）；daily 可走 front/back/qlib（`csv_daily_backtest.py` 入口仍可跳过 exdiv 但用同一 bars 估值）。
- **风险**：C 案若在已复权 close 上再叠权益 → 双重补偿。最小回填：改为「按输入 close 估值；none/raw 夹具下才是 raw mark 残留」。

---

## 🟡 应修

**3. δ6 `exdiv_map` 行锚把 `k=prev_cum/cum` 挂到错行**

- 文：`plan-…-d6-…md:25` 锚 `:233-239`、`:288-319`。
- 基线 `:233-239` 仅 warmup docstring / 日期 normalize；公式在 `:305-307`（落在第二段）。应改第一锚到含 `k = prev_cum / cum` 的循环。

**4. δ3 把 v7 context→`names=` 写成已核实锚点，未来 pin 却标「如需」**

- 锚点真：`csv_minute_backtest_v7.py:571`、`:583-584`（`load_limit_context` → `simulate_v7(..., names=names)`）。
- 既有 pin `test_v7_names_flatten…`（`:276`）是手工 `flatten`+`simulate_v7`，不断真实 loader/context。
- Slice B3（δ3 `:120`）把 CLI/context 接线写成可选 → 名称接线失效时现有 ST pins 仍可全绿。A 交付若声称「分叉合同可回归」，至少一条 `load_pool_names_by_day → load_limit_context → names=` 必选 pin。

**5. δ4 held-None 的自然可达性未钉；与未来 δ3.C 缺交接**

- 现有 pins（`test_ashare_simulate_predicates.py:122-135`、`:173-191`）依赖 seed/monkeypatch；自然首开仓要求 `previous`/`priced` 非 None（`csv_minute_backtest_v7.py:389-400`），flat name 全程不变时 held-None 难自然出现。
- 若 δ3.C 改 v7 逐日名，可「D1=*ST 建仓 → D2 普通名 → limits=None」使 fail-open 自然可达。索引「独立决策」（index `:20`）应补：δ3.C 强制重做 δ4 可达性矩阵。

**6. δ5 D6 时间前缀 oracle 未交接现有整日零量过滤前缀敏感**

- 设计 D6（δ5 `:70`）要求 t 后追加 volume 不改 t 前成交。
- as-built：`ashare_bars.py:369-371` 按**整日** volume sum 决定是否保留当日全部分钟后再丢列——追加尾盘正量可改变早盘记录是否存在（既有 minute loader pins 已锁相关行为）。
- D6/B1 须标明：独立 cap 模型 ≠ 端到端 loader→撮合因果；该残留保留到 C 前缀验收。

**7. δ5 `.3=A` 部分成交缺「首次触发被 cap 拒绝后扫描续行」状态表**

- 书分钟 scanner 首触即返回（`csv_minute_backtest.py` scan 路径）；lot 每会话一次 scan。D1–D7 数量算术盖不住 residual 后 peak/再触发/rider/P4。
- 设计 B 收口前补状态矩阵，或暂推荐 `.3=B`（整笔拒绝）并显式写代价；触碰 touch↔mark/fill 时点须另裁 P4/P1。

**8. §8.2「禁止 CLI」措辞过宽**

- 所列整文件含调用 `main()` 的 tmp_path 单元测（如 `test_csv_minute_backtest_v7.py` 空池 CLI）。路径存在、非幽灵；应改为「禁宿主/湖回测，允许 stubbed `main` 单元」。

---

## 🟢 可选

- 索引 `:24` 的「85 file:line / exit 0」是作者历史核验；含 review 产物的 worktree 再跑 §8.1 会因白名单失败——索引 `:26` 已说明发布副本，建议加一句「审阅 worktree ≠ 发布树」。
- δ5 `:184-195` 等预算锚略宽（含 fail 统计行）；可收紧到 `execute_buy` / `_buy_size` 真值行。

---

## ✅ 做对的地方

- **生产冻结**：base→HEAD 仅五 Markdown；四刀 §8.3/§9 **22 文件同序一致**，且含 δ1=10 / δ2=17 超集；F-R1–10 + 全路径白名单双重约束。
- **默认与顺序 SSOT**：index A/A/B/A（δ6 可 B；prod 须显式 C）与各刀 §5 一致；P1/P2/P4 全程挂起，无 fill window / trades 列 / touch↔mark 重开。
- **δ6 C creep 防护到位**：Mode B `shares /= k`（`unified_exit_modeb.py:423`、`:806`）与 `no cash dividend`（`:1029`）已隔离；`test_unified_exit_modeb_exdiv.py:61-64` 钉 shared ledger 不增股；F-R2/F-R3 + index `:16` 禁止外推。
- **关键行为锚点多数可在基线复现**：书 as-of（`csv_common.py:85-106`）、v7 flatten（`ashare_session.py:81-85`）、None 双门 False（`ashare_session.py:73-78`）、v7 首开拒 / held fail-open（`csv_minute_backtest_v7.py:341-409`）、volume 丢列（`ashare_bars.py:369-371`、`qlib_bin_1min.py:57-64`）。
- **§8 路径**：四 gate + 所列 test 文件 / 具名测试均存在；`bash -n` 级命令可执行；未冒报本 PR 已跑 §8.2。
- **人裁表清晰**：交付层级 vs 次级设计 vs Slice C 验收 vs 选项 C 生产，四处未混用。

---

### 1) 总裁决

**GO-WITH-NITS**

### 2) 建议人裁表

| 项 | 建议 |
|---|---|
| δ3 | **A**（契约+未来 pins；不修 v7 PIT） |
| δ4 | **A**（须先回填 named-band 前提；fail-closed 另案 `.1=C`） |
| δ5 | **B**（仅设计；生产 cap 须另案 C；`.3` 待状态表后再裁） |
| δ6 | **A**；账本清晰可选 **B**；生产 shares/cash/NAV **必须显式 `.1=C`** |
| P1/P2/P4 | **维持 deferred** |

### 3) 是否可进人裁

**yes**（可进人裁讨论；**人裁 GO 前须回填两条 🔴**；人裁 GO 前仍禁止编码 / 不合并实施）
