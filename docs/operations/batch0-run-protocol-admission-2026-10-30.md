# 批次 0：真湖验收器规则身份与 Windows 测试收尾

对应统一计划 P01 / BT-18、BT-17，批次 0C。改动对象是验收器及离线测试；后续 P14 的目标宿主真湖矩阵尚待执行。

## 规则、费用与低现金判据

验收器新增 `--rule-profile industry|legacy`，默认 `industry`；八个格均显式传给原生 CLI，L1 使用相同 argv。`recipe.json.economic_flags` 记录解析后的规则名、revision、完整 profile 设置和费用各组件（佣金、最低费用、订单粒度、日期税费开关）；各格也记录规则名和 revision。费用从原生入口使用的 resolver 获取，旧固定双边 10bp 标签已移除。

| 入口 / profile | cash=1 格的必要直接证据 |
|---|---|
| CSV 分钟 / industry | exit=0 且 `execution-audit.json.events` 有 `side=SKIP, reason=skip_cash`；拒单不进入原成交 CSV |
| CSV 分钟 / legacy | 非零退出且真实 `InsufficientCashError` 带 date/code；其他异常失败，未触发则 NOT_COVERED |
| v7 / 两种 profile | exit=0 且原生 trades 有 `side=skip, reason=skip_cash` |

每一侧都必须触发；原生/L1 经济产物与输出比较仍先于格判定。两侧空成交、仅退出 0、其他拒单事件均不代签。本格只测试零可买数量；部分缩量继续由已有 `test_if_p08_shrink_on_short_cash.py` 的 1400 股真实 ledger 夹具验证，不从成交数量猜测触发，也不扩大真湖参数矩阵。

## Windows 复现与修复

`test_progress_invalid_utf8_warns_and_appends` 在本机复现：append 使用 Windows CRLF，测试却只接受 LF。断言现按 `os.linesep` 检查追加行，仍逐字节验证原非法 UTF-8 前缀保留、告警存在及追加内容正确。未改动生产 ETL 写入行为。

## 本地验证

Windows vanna312，`PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`：

- `test_verify_run_protocol_lake_parity.py`、`test_if_p08_shrink_on_short_cash.py`、`test_l2_phase3_pipeline.py`：**231 passed**。
- 原规则与短现金兼容域 `test_if_p01_rule_profile.py`、`test_b7_on_short_cash.py`：**32 passed**。
- 新增验收测试用实际 ledger/audit_scope 生成 cash=1 拒单事件；空事件及其他原因不能覆盖低现金格。预注册测试核 receipt 的规则/费用及未配置数据时只启动非法参数格。

Windows 默认 GBK 模式下，原有无编码 `read_text()` 测试会解码 UTF-8 产物失败；验证明确采用 UTF-8 模式，未把该环境差异当成引擎或数据故障。真实湖尚未运行，不由这些离线结果关闭 P14。

合入并完成当前 head 的 CI 后，统一索引追加 BT-18/BT-17 的条目级关闭回执；MyQuant QL01 由其独立 PR 验收。
