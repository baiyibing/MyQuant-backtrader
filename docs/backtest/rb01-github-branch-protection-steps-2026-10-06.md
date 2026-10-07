# RB-01 · GitHub master 保护设置步骤（只读审计 → 待你操作）

审计时间：2026-10-06 Asia/Shanghai。仓库：`baiyibing/MyQuant-backtrader`。tip：`51f0113`。

## 审计结果（只读 API）

| 项 | 现状 |
|---|---|
| `branches/master.protected` | **false** |
| Branch protection API | **404 Branch not protected** |
| Repository rulesets | **[]（空）** |
| Required status checks | **无** |
| Allow squash / merge / rebase | 均 true |
| CI workflow `python-tests` / job `pytest-and-gates` | 存在；PR 与 push master 均触发 |

结论：任何人（含业务直推）都可以不经 PR、不经 required checks 写入 master。本地 pre-push 可被 `--no-verify` / `SKIP_PREPUSH=1` 绕过。这与脑暴 RB-01 的「疑似缺口」一致，现已核验。

本文件**不**由 agent 改远端设置；下列步骤需仓库管理员在 GitHub UI 或 API 自行操作。

## 推荐设置（点击路径）

1. 打开 https://github.com/baiyibing/MyQuant-backtrader/settings/branches
2. **Add branch protection rule**（或 Edit `master`）
3. Branch name pattern：`master`
4. 勾选：
   - **Require a pull request before merging**
     - 建议：Require approvals ≥ 1（可按团队调整）
     - 可选：Dismiss stale PR approvals when new commits are pushed
   - **Require status checks to pass before merging**
     - Require branches to be up to date before merging：建议勾选
     - Status checks 搜索并勾选：**`pytest-and-gates`**  
       （来自 `.github/workflows/python-tests.yml` 的 job 名；若 UI 尚未出现该检查，先合并含该 workflow 的 PR 并跑一次后再勾）
   - **Do not allow bypassing the above settings**（关闭管理员绕过；紧急例外见下）
5. 可选加固：
   - Restrict who can push to matching branches（去掉个人直推名单，只留 bot/管理员紧急身份）
   - Block force pushes / deletions：勾选
6. Save changes

## 等价 REST API（需 `repo` admin token；agent 不会执行）

```bash
# 创建/更新 branch protection（示例；按组织策略调整 reviewers 数量）
gh api -X PUT repos/baiyibing/MyQuant-backtrader/branches/master/protection \
  -H "Accept: application/vnd.github+json" \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["pytest-and-gates"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

Rulesets（新版）亦可：Settings → Rules → Rulesets → New → target `master`，加同样的 PR + required checks 规则。

## 紧急例外（建议流程，不是隐式跳过）

1. 指定责任人临时关闭 `enforce_admins` 或使用有 bypass 的身份。
2. 直推后立刻重开保护，并补 PR/事后说明（链接 CI run）。
3. 不在 CI 或 hook 里提供「静默跳过准入」开关。

## 仓内配套（由 RB-01 PR 落地，不替代远端保护）

- MC-1：`cancel-in-progress` 仅对 `pull_request`，避免取消进行中的 master push 检查。
- 新书/注册准入诊断脚本接入 CI（缺项报哪个书、漏哪个契约），**不**自动刷 golden。

设置完成后可用：

```bash
gh api repos/baiyibing/MyQuant-backtrader/branches/master/protection --jq '{required_status_checks,enforce_admins,required_pull_request_reviews}'
```

期望：`required_status_checks.contexts` 含 `pytest-and-gates`，`enforce_admins=true`（或等价 ruleset）。
