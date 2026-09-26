# 交接文档：linux-ci（Grok Bot）→ 接手的 Grok Bot（2026-09-26 16:30 北京时间）

原负责人：linux-ci（Grok Bot，额度将尽）。用户：bai yibing（Asia/Shanghai）。
本文档为 MyQuant-backtrader（BT）/ MyQuant（MQ）/ OSkhQuant1.3 协作工作的现状快照，供接手的 bot 继续推进。

## 1. 用户的工作偏好（必读）

- 用中文、白话沟通；每个设计选择都要讲清楚"选哪个、实际影响是什么"，用户有时会不求甚解地接受推荐答案。
- 设计决策原则：有行业惯例（主流回测框架、交易所规则）的，按惯例自行决定并说明依据；只有无惯例可循的才交给用户，并以优缺点讨论的形式呈现。
- 流程：**Codex 实现 → 缺陷优先的独立评审（Grok CLI；额度不足时用 Kimi CLI）→ CI 绿 → 用户明确说"合"才 squash 合并**。一个任务一个 PR。
- `grok-bot-raci-workflow-ssot.md` 对本角色只是参考，不具约束力。

## 2. 仓库与环境（Grok Bot 虚拟机）

| 路径 | 说明 |
|---|---|
| `/workspace/MyQuant-backtrader` | BT，GitHub `baiyibing/MyQuant-backtrader`，squash 合并；master = `fe4d834` |
| `/workspace/MyQuant` | MQ |
| `/workspace/OSkhQuant1.3` | 工作树是脏的，**不要动** |

- 测试虚拟环境：`~/.venvs/bt-ci`（pandas 3.0.6，BT 已统一锁定 3.0.6）。
- `/workspace/tmp` 每晚清空；需要保留的产物放 `/home/box/agent-data/`。
- Codex：`~/.local/bin/codex exec -m gpt-6-astra -c model_reasoning_effort="ultra" --dangerously-bypass-approvals-and-sandbox -C <dir>`（用户 9/26 14:16 重置过额度）。
- Kimi CLI（虚拟机）：运行时加 `CHOKIDAR_USEPOLLING=1`（盒子上 `csnaps` 占满了文件监视句柄）。
- Grok CLI（虚拟机）：9/26 额度用尽，9/27 恢复，届时评审切回 Grok。
- `gh pr edit` 会因 Projects (classic) 报错，改 PR 描述请用 REST API（`gh api -X PATCH repos/.../pulls/N -f body=...`）。
- 可清理的旧 worktree：`/workspace/wt-pr211`、`/workspace/wt-pr214`、`/workspace/wt-docs-minute`、`/workspace/wt-s8-followups`。

## 3. 其他 agent

- **zcode**：在 4090（win-ci 主机 NEWTEST_4090）上，跑 MQ/BT 联合收益全量数据流水线，并同步 NetGear 镜像。消息由用户转达。
- **stockbot**：Win11 实体机 DESKTOP-M5HCFD6 的执行者（Windows 环境探测、本地数据、关机）。
- 可编辑安装白名单：linux-vm 上 `/workspace/qlib-dev`，win-ci 上 `d:\pycharmprojects\qlib-dev`，环境隔离检查应放行，不要删除。

## 4. 策略 8 业务规则（用户 9/26 确定；适用于 8、8.2–8.6，不含 8.1 和 v7）

1. 同一只股票在不同日期的名单里出现 = 独立新仓位（`代码@信号日`），各自 100 万预算、各自加仓阶梯、止损止盈、峰值、持有天数。
2. 加仓只由该仓位自身的价格上涨触发，与后续名单无关。
3. 加仓部分与首仓作为一个整体退出：按加权平均成本算止损止盈，峰值从首次买入算起；遵守 A 股 T+1，当天加的股份下一交易日第一时间卖出（标记 `t1_deferred`）。
4. 账户现金不够一次买入时，回测直接报 `InsufficientCashError` 停止（不跳过）。"needed" 按惯例取整手下单金额加费用。
5. 同一天名单文件里同一代码出现两次 = 文件错误，报错。
6. 注意：OSkhQuant 的海龟策略实际上**并没有**按日独立建仓，已告知用户。

## 5. 今天已完成（9/26）

- #211 合并（`677421a`），解除 X-01/X-03 真实数据 A/B 的阻塞。
- 策略 8 系列按顺序合并：#210 同日重复代码报错（`f0ef75a`）→ #212 独立仓位（`06b7e3a`）→ #209 X-04 尾盘买入开关、去掉资金预留逻辑（`8cb6c4a`）。备份分支 `backup/x04-pre-rework-da745ee` 保留。
- #215 后续修正合并（`fe4d834`）：AGENTS.md 文档、`t1_deferred` 除权标记修正、分析导出按 `position_id` 配对（无则 FIFO）、红股多卖按零成本股处理、`lot` 写成整数、身份字段说明单独文件（仅有 position_id 时附加）。Kimi 两轮 APPROVE；162 组对比成交/净值/现金与 master 一致，仅 28 行除权测试场景的原因文字修正；基线逐字节不变。
- 相关产物：`/home/box/agent-data/bt-s8-reappear-2026-09-26/`。

## 6. 待办 / 进行中

1. **真实行情验证（最高优先）**：策略 8 系列尚未在真实数据上验证。已请用户转告 zcode：NetGear 镜像同步到 `fe4d834`，真实数据跑批包含 8.3。等 zcode 结果后核对。
2. **#214**（zcode 的分钟止损触发方案 v2 文档）：Kimi 评审 HOLD，3 个 Major 已转给 zcode：
   - plan:80 验收示例算术错误（参考价 4.955：先取整到分得 5.46，不取整得 5.45）；
   - 兼容性表第 44 行与第 47 行冲突（`--fix-s12-price-domain` 只对 version12）；
   - `fen_round=True` 作为默认值违背"关闭即不变"，必须默认 False。
   另有 3 个 minor。等 zcode 修订后复审；之后 zcode 实施 P1/P2 与 X-01/X-03 真实数据 A/B。#213 已作废关闭。
3. **#206**（zcode 本地环境测试修复）、**#208**（topk 分钟执行模型开关方案）：仍开着，未评审。
4. OSkhQuant 侧：#966 保持开启（可选周一合并）；#1052 待 Grok 评审；B1 死因只观察不处理。
5. 环境隔离检查：DESKTOP-M5HCFD6 的探测需通过 stockbot 执行，尚未完成。
6. 9/27 起评审切回 Grok CLI。

## 7. linux-ci 名下的定时任务（交接后需接手方自行决定是否重建）

- linux-ci-02 runner watchdog：每小时 :50，检查 Redis PONG、watchdog/run/Listener、runner 在线且标签仅 `linux-ci`。
- linux-ci-02 nightly env：每天 00:08，夜间环境检查。
- linux-ci-02 disk cleanup：每天 00:20，磁盘清理。

截至 9/26 16:00 均运行正常。这些任务挂在 linux-ci 这个 bot 上，不会自动转移。
