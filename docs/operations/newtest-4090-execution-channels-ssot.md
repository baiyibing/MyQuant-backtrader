# newtest_4090 执行通道 SSOT（Actions / tea / agent CLI / GUI）

- 适用范围：Grok Bot 协作下，在 **newtest_4090** 上选择执行通道。
- 角色 / 模型钉 / headless 以 [`grok-bot-raci-workflow-ssot.md`](grok-bot-raci-workflow-ssot.md) §3/§6/§6.1 为准；**本文只定通道选型**。
- **Cursor Auto = Cursor agent CLI headless + Auto 模型**，属于第 3 通道；桌面 / 浏览器 GUI 自动化另列为第 4 通道。
- 生效：2026-10-12

## 1. 四通道对照

| 通道 | 定位 | 适合 | 边界 |
|---|---|---|---|
| **1. Gitea Actions `win-ci-gates`**（4090 本机 runner） | 可复现脚本首选 | Playwright、mock SSO、单测 / build gate、合入后 pull+rerun | 固定脚本与 outdir；真人可见点击登录走第 4 通道 |
| **2. `tea`**（Gitea CLI） | forge PR / Actions 元数据 | 开 / 列 / 合 PR、触发 / 盯 workflow、label、issue / PR 元数据 | 不执行 Playwright；forge：http://netgear.seetell.net:13001/ 或 http://120.236.35.58:13001/；DNS 失败优先后者 |
| **3. 4090 上 headless agent CLI** | 本机实现 / review / one-off 默认 | **Cursor Auto**（cursor-agent headless + Auto）；kimi / codex 等按 RACI §6.1；本机 checkout 排障 | 非 Auto 默认模型钉仍为 `grok-4.7-high`；不套用 Bot VM `gpt-6.*`；默认无 TUI |
| **4. 桌面 / 浏览器 GUI 自动化** | 独立的最后手段 | 验证码 / 2FA / 必须真人可见的点击登录 | 不称为 Cursor Auto；不作为脚本或 agent 工作的默认通道 |

**Actions 已核验记录**：2026-10-11 ~20:34 CST mock SSO **7/7 PASS**；Actions http://120.236.35.58:13001/zhentinginfo/newtest/actions/runs/1102 ；outdir `D:\exports\vue3_sso_joint_20261011\mock\`（含 `MOCK_RUN.md`）。当时 checkout PR #62 分支 `feat/tools-mock-sso` @ `50269b74` → `D:\PycharmProjects\newtest-mock-sso\tools\mock-sso`；合入后路径为 pull master `e455dd3` 再跑。

**agent CLI 调用入口**：Cursor Auto 示例 `agent -p --force --trust --model auto "..."`；不使用 Auto 时，RACI §6.1 默认 `agent -p --force --trust --model grok-4.7-high "..."`。kimi / codex DeepSeek 等可用范围、模型钉与后续实测更新仍由 RACI §6.1 管理。

## 2. 决策表

| 任务类型 | 首选通道 | 回退 | 禁止 |
|---|---|---|---|
| 可复现脚本（Playwright / mock SSO / 单测 / build gate） | **1. Actions `win-ci-gates`** | 3. headless agent CLI 在本机 checkout 调用同脚本 | 默认走 GUI；对 169.169 硬联调 |
| 合入后 pull master 再跑 | **1. Actions `win-ci-gates`** | 3. headless agent CLI 执行 git pull + 同脚本 | 手工拷贝散文件 |
| forge PR / Actions 元数据（开 / 列 / 合 PR、触发 / 盯 workflow、label） | **2. `tea`** | forge Web UI（人工） | 用 `tea` 执行 Playwright |
| 本机实现 / review / one-off；Actions YAML 缺失时排障 | **3. headless agent CLI**（含 Cursor Auto；按 RACI §6.1） | 可复现脚本补 YAML 后走 1. Actions | 默认挂 TUI / GUI |
| 验证码 / 2FA / 真人可见点击登录 | **4. 桌面 / 浏览器 GUI 自动化（最后手段）** | 人在机前 | 称为 Cursor Auto；用 headless 硬扛登录墙 |
| 对 169.169.* 真实 SSO 联调 | **禁止**（TCP 不通） | 改用 `tools/mock-sso/`，走 1. Actions | 硬联调 |

## 3. 硬约束

- 169.169.* 真实 SSO 不可达；用 newtest `tools/mock-sso/`。
- 本机 agent 工作默认 headless、无 TUI；Cursor Auto 属于此通道。GUI 仅用于验证码 / 2FA / 真人可见点击登录。
- agent CLI 模型钉与可用清单见 RACI §6.1；不使用 Auto 时默认 `grok-4.7-high`。
- 工具下发 git pull；禁止手工拷贝。
- Cursor 额度 / 桌面断连不挡 Actions；ListMachines `disconnected` ≠ 4090 关机，可走 Actions / SSH / 本机 session / headless agent CLI。
- DNS：Gitea 优先 `120.236.35.58:13001`。

## 4. 证据 / outdir（薄）

- 产物：`D:\exports\<topic>_<YYYYMMDD>\…`，含 `MOCK_RUN.md` 或等价 `RUN.md`（命令、commit、结果、Actions URL）。
- 回执：STATUS / 一句话 / outdir / Actions URL（若有）/ commit SHA。

## 5. 与 RACI 边界

| 文档 | 管什么 |
|---|---|
| RACI | 谁、什么模型、headless、合入规则 |
| 本文 | 在 4090 上**用哪条通道** |

交叉链：RACI §6 / §6.1；RACI 的 §6 指向本文，角色与 agent CLI 模型钉仍回看 RACI。

## 6. 修订

| 日期 | 变更 |
|---|---|
| 2026-10-12 | 初版：四通道 + 决策表；Actions 为可复现脚本首选；agent CLI headless 为默认 agent 面；沉淀 mock SSO Actions #1102 |
| 2026-10-12 | 纠正 Cursor Auto=agent CLI Auto 模型，GUI 另立；明确本机实现 / review / one-off 默认 headless agent CLI，GUI 仅验证码 / 2FA / 真人可见点击登录最后手段 |
