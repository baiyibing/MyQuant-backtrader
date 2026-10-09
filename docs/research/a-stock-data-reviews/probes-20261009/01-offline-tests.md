# 01 隔离 venv 离线单测与补充探针

结论：上游现有单测 177 项，173 通过、4 跳过、0 失败、0 错误。4 项均为 opt-in 联网测试；离线执行显式清除三个 ASTOCK_LIVE 环境变量，并拦截 socket.connect/create_connection。安装依赖阶段联网，测试阶段禁止网络。

执行环境为本目录 `.venv`（Python 3.13.5），依赖版本见 `requirements.freeze.txt`，安装日志见 `venv-install.log`。未在原仓安装依赖或改代码。

复跑：

```bash
/workspace/a-stock-data-reviews/probes-20261009/.venv/bin/python /workspace/a-stock-data-reviews/probes-20261009/offline_probe.py
```

`01-unittest.log` 保留全部用例；`01-results.json` / `01-run.log` 为结果。测试运行时约 13.1 秒。用例由原仓 tests 自动发现，测试原仓 SKILL.md 内嵌实现。

## 东财旧 helper：空与坏混淆

现有 `EastmoneyStrictTests` 覆盖 `_em_datacenter_strict`，不能推断旧 `eastmoney_datacenter` 也具备该契约。未找到旧 helper 和新浪复权因子有限性的专门用例，因此在输出目录增加可复跑观测探针（没有修改上游测试）。

| 输入 | 旧 helper 实际输出 | 结论 |
| --- | --- | --- |
| `result.data=[]` | `[]` | 正常空 |
| `success=false,code=500,result=null` | `[]` | 业务失败伪装成空 |
| `{}` | `[]` | 缺 schema 伪装成空 |
| `result.data="BAD"` | 字符串 `BAD` | 不验证返回必须为记录列表 |

源码 SKILL.md:785 仅调用 `.json()`、检查 truthiness；不校验业务状态，不在此处 `raise_for_status`，只请求第一页。它仍被 `dividend_history` 使用。

## 复权因子有限性

加载原始 `sina_adjust_factor` + `apply_adjust`，模拟新浪合法 JSON 外壳内的因子字符串（基准 close=10）。

| 因子 | qfq 收盘价 | hfq 收盘价 | 是否拒绝 |
| --- | --- | --- | --- |
| NaN | NaN | NaN | 否 |
| +Inf | 0 | +Inf | 否 |
| -Inf | -0 | -Inf | 否 |
| -1 | -10 | -10 | 否 |
| 0 | RuntimeError | RuntimeError | 是 |
| 1 | 10 | 10 | 否，正常对照 |

`01-results.json` 中非有限值用字符串保存以满足标准 JSON；原计算确实产生浮点 NaN/Inf。价格有限不代表安全：Inf 的 qfq 输出虽为 0，但附带因子仍为 Inf。建议接入边界同时验证因子有限且严格为正、价格有效。此轮只取证，未修补实现；现有测试全绿不能覆盖这些缺口。
