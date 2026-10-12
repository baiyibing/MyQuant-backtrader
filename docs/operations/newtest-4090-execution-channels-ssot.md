# newtest_4090 执行通道 SSOT（Actions / tea / runner+agent CLI / Cursor Auto）

- 适用范围：Grok Bot 协作下，在 **newtest_4090** 上选**执行通道**（谁跑脚本、谁管 forge、谁点 GUI）。
- 角色 / 模型钉 / headless 仍以 [`grok-bot-raci-workflow-ssot.md`](grok-bot-raci-workflow-ssot.md) §3/§6/§6.1 为准；**本文只定通道选型**。
- **agent CLI headless**（cursor-agent / kimi / codex 等，见 RACI §6.1）是 4090 上默认的 *agent 执行面*；Cursor Auto 不是与 Actions 并列的默认通道。
- 生效：2026-10-12

## 1. 四通道对照

| 通道 | 是什么 | 适合 | 不适合 | 备注 |
|---|---|---|---|---|
| **A. Gitea Actions**（`win-ci-gates`，跑在 4090 本机） | 可复现脚本的**首选** | Playwright、mock SSO（`zhentinginfo/newtest` 的 `tools/mock-sso`）、单测 / build gate；固定 outdir `D:\exports\…`；合入后 pull+rerun | 真人可见 GUI 登录墙 | 不依赖 Cursor 桌面连接、不吃 Cursor 配额；runner 在同机时更快更稳；已核验证据见下方 |
| **B. `tea`**（Gitea CLI） | forge 元数据首选 | 开 / 列 / 合 PR、触发 / 盯 workflow、label、issue / PR 元数据 | 执行 Playwright 本身 | forge：http://netgear.seetell.net:13001/ 或 http://120.236.35.58:13001/；DNS 失败优先 `120.236.35.58` |
| **C. Gitea runner 本机 / 本地 checkout + headless** | 一次性排障执行面 | Actions YAML 缺失，或已 checkout 树上的 one-off debug；优先 **headless 脚本**或 **agent CLI headless** | 默认挂 TUI；手工拷贝散文件 | agent CLI 按 RACI §6.1；工具下发对仓库 **git pull** |
| **D. Cursor Auto / 桌面 GUI 自动化** | **仅最后手段** | 必须真人可见 GUI：点登录、验证码、2FA、看实页状态 | mock SSO 链默认执行；与 Actions 并列的默认 agent 通道 | ListMachines `disconnected` ≠ 主机离线；改走 Actions / SSH / 本机 session / agent CLI headless |

**A 已核验记录**：2026-10-11 ~20:34 CST mock SSO **7/7 PASS**；Actions http://120.236.35.58:13001/zhentinginfo/newtest/actions/runs/1102 ；outdir `D:\exports\vue3_sso_joint_20261011\mock\`（含 `MOCK_RUN.md`）。当时 checkout PR #62 分支 `feat/tools-mock-sso` @ `50269b74` → `D:\PycharmProjects\newtest-mock-sso\tools\mock-sso`；合入后路径为 pull master `e455dd3` 再跑。

**C 调用入口**：RACI §6.1 默认 `agent -p --force --trust --model grok-4.7-high`；亦可 kimi / codex DeepSeek；勿套用 Bot VM `gpt-6.*`。模型钉及后续实测更新仍由 RACI §6.1 管理。

## 2. 决策表

| 任务类型 | 首选通道 | 回退 | 禁止 |
|---|---|---|---|
| 可复现脚本（Playwright / mock SSO / 单测 / build gate） | **Actions `win-ci-gates`** | runner 本机 headless 脚本 | 禁止默认 Cursor Auto / 禁止对 169.169 硬联调 |
| 合入后 pull master 再跑 | **Actions** | runner checkout + git pull + 同脚本 | 禁止 Cursor Auto |
| 开 / 列 / 合 PR、触发 / 盯 workflow、打 label | **`tea`** | forge Web UI（人） | 禁止用 Playwright 冒充 forge 操作 |
| Actions YAML 缺失或本机 checkout 一次性排障 | **runner checkout + headless 脚本 / agent CLI headless** | 补 YAML 后改回 Actions | 禁止默认挂 TUI / Cursor Auto |
| 需 agent 改码 / 排障（非 GUI 墙） | **agent CLI headless**（RACI §6.1） | 同机 headless 脚本 | 禁止默认 Cursor Auto / TUI |
| 需真人可见 GUI（点登录 / 验证码 / 2FA / 看实页） | **Cursor Auto（最后手段）** | 人在机前 | 禁止用 headless 硬扛登录墙 |
| 对 169.169.* 真实 SSO 联调 | **禁止**（TCP 不通） | 改用 `tools/mock-sso/` | — |

## 3. 硬约束

- 169.169.* 直播 SSO 不可达；用 newtest `tools/mock-sso/`。
- Headless 默认；无 TUI；与 RACI §3/§6 对齐，**通道选型以本文为准**。
- agent CLI 模型钉见 RACI §6.1；本文不重复钉模型。
- 工具下发 git pull；禁止手工拷贝。
- Cursor 额度 / 桌面断连不挡 Actions；ListMachines `disconnected` ≠ 4090 关机。
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
| 2026-10-12 | 初版：四通道 + 决策表；Actions 为可复现脚本首选；agent CLI headless 为默认 agent 面；Cursor Auto 仅 GUI 最后手段；沉淀 mock SSO Actions #1102 |
