# S1 TopK CLI 本机执行回执

实现及 data-free 验证已完成。真实分数/多证券真湖两臂 **NOT_RUN**：
VM 缺 `预测结果_8a061ea4_2025valid.csv`，此前 BLOCKED 回执没有被控制值或合成测试解除。
Grok CLI 核、4090bot 宿主执行留待人转交；本刀只使用 Codex CLI。

基线 `da173442235beca8861cdde1d008baf6b540c723`；
分支 `knife/topk-s1-cap-cli`；workdir `/workspace/wt-topk-s1-cap-cli`。
draft PR 创建后，外部 handoff 的 `PR_URL.txt` / `PR_TIP.txt` 记录完整 URL/SHA，
此版本文档可从 PR 的 Files changed 或分支直接查看。
不自动合并。

## 已执行验证

解释器由 `OSKH_MERGE_PYTHON=/workspace/vanna312/bin/python` 明确指定：
Python 3.12.13，pandas 2.3.3，numpy 2.3.5。本地不是 CI 的 pandas 3.0.6 环境，
故本回执不代称远程 CI 已通过。

```bash
/workspace/vanna312/bin/python -m pytest -q \
  tests/test_csv_minute_participation.py \
  tests/test_topk_cap_compare.py \
  tests/test_ashare_volume_cap.py \
  tests/test_csv_minute_backtest.py \
  tests/test_topk_minute_exec.py \
  tests/test_bt_run_manifest.py \
  tests/test_research_run_protocol_csv_minute.py \
  tests/test_ashare_simulate_import_fence.py \
  tests/test_ashare_bars.py
```

最终：**399 passed in 12.23s**（退出 0），日志在外部
`/workspace/handoffs/topk_s1_cap_cli_20261001/pytest-final.log`。
包括旧 OFF 哈希 golden、run 省略≡None、不请求量、显式 0/0.1/1、Top50/5、
09:30 不可用、缺 lookup/坏量/源域拒绝、真实原生 simulate 的多证券合成两臂，
以及单股控制、错 shift、错 PIN、缺证券/日线/完成桶/单位/时钟等失败分支。
所有合成数据由 pytest 临时构造；没有将测试收益写作真实研究结论。

初轮测试纠正了两个测试假设：既有 version6 的 5000 额度可买 500 股，
不是 400；09:30 竞价缺行不属于缺“完成桶”，缺桶负例改为删除 09:31。
元数据旧结构测试由三块扩展为四块，并继续验证 sibling keys 不被覆盖。
未改成交/费用核来让测试通过。

四项 data-free gates 均 PASS：

```bash
/workspace/vanna312/bin/python scripts/gates/verify_oskh_data_contract.py
/workspace/vanna312/bin/python scripts/gates/verify_data_path_ssot.py
/workspace/vanna312/bin/python scripts/gates/verify_no_hardcoded_machine_paths.py
/workspace/vanna312/bin/python scripts/gates/verify_tr_bridge_import_ssot.py
```

两入口 `--help` 可执行并展示新参数；`git diff --check` 通过。
所有改动 `.py/.md` 已按 UTF-8 无 BOM 解码、NUL=0 校验，Python AST 解析通过。

## 改动文件

- `backtest/research/csv_minute_backtest.py`：共享 run/CLI opt-in 接线与现有 manifest 参数。
- `backtest/research/csv_minute_volume.py`：纯已加载分钟量映射/验证，股数不换算。
- `scripts/research/run_topk_cap_compare.py`：真分数窄窗预检及两臂脚手架。
- `tests/test_csv_minute_participation.py`：共享参数、OFF 等价和 cap-on 回归。
- `tests/test_topk_cap_compare.py`：多证券脚手架及输入/隔离拒绝。
- `tests/test_topk_minute_exec.py`：容量元数据与已有元数据并存回归。
- `docs/backtest/topk-s1-cap-cli-2026-10-01/{PLAN,HOST_4090,RUN}.md`：可随 PR 拉取的交接。

## 后续命令与状态

4090 的完整 PowerShell 命令、参数、PIN 形状及五字段 STATUS 见
[HOST_4090.md](HOST_4090.md)。单次 `run_topk_cap_compare.py --participation-rate 0.1`
运行 cap-off=None 与 cap-on=0.1 两臂；必须全新外部输出目录。

共享 CLI 用例（**仅当 resolver 已配置兼容既有 loader 的 raw 股数分钟源**）：

```text
<resolved-python> backtest/research/csv_minute_backtest.py --strategy topk_dropout --scores-dir <buy-day-scores> --pool-dir <buy-day-pool> --start 20251024 --end 20251028 --participation-rate 0.1 --out-dir <new-output>
```

旧湖为手时禁止照抄该命令直接运行；本 HOST 流程用 S1 scoped 文件和单位 PIN，
无运行时 ×100，也不将 S1 列结构冒称旧 lake loader 可直接读。
省略 flag 保持原状，不改 Top50/5、触价止损、MatchCore/Fees、HELP_LOCK 或策略注册。
cap-on `available_at=bucket_end` 仅研究完成桶近似；validation 非 OOS，
权益与证券状态限制见输出 PIN。`no_ssot_compare_authorization` 保持。

没有修改 MyQuant 业务代码，没有运行其 exporter；命令仅交给宿主清单。
没有写湖，没有开 δ5 certified / R4，没有自动合并。
