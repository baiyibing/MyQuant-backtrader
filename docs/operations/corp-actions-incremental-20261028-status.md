# corp-actions 增量更新执行状态 — 2026-10-28

## 当前数据情况

### 基础库（已完成，已备份）

- **快照**：`bt_corp_actions_20261006`
- **覆盖窗口**：2014-01-01 → 2026-10-06
- **代码数**：2774
- **事件数**：21779
- **规模**：
  - 源目录 `D:\exports\bt_corp_actions_20261006`：7.7 MB（raw CSV + 日志）
  - 湖 `E:\stock_data\corp_actions`：465 KB（Parquet）
  - repo handoff `_handoff_corp_actions_20261006/`：2.3 MB
- **备份**：
  - git commit `584538b`（2026-10-24，完整快照 #501）
  - zip：`D:\exports\bt_corp_actions_20261006_bak_20261023.zip`、`G:\backup\bt_corp_actions\bt_corp_actions_20261006_bak_20261023.zip`

### 增量目标

- **窗口**：2026-10-07 → 2026-10-28（基础库 ask_end + 1 至今日）
- **代码数**：2774（沿用策略池 lineage）
- **输出目录**：`D:\exports\bt_corp_actions_incr_20261028`
- **模型**：`kimi-code/k3`（owner override；原 GO 限定 highspeed / kimi-for-coding，代码已同步放开）

## 增量执行时间线

| 时间 | 模型 | 结果 |
|---|---|---|
| 2026-10-25 ~ 10-27 | `kimi-for-coding-highspeed` | 多次被旧版 `quota_hit()` 误停；0 accepted codes；后修复 #508–#511 |
| 2026-10-28 15:20 | `kimi-for-coding-highspeed` | 首次真 401：`ev_0163`、`ev_0166` 返回"未识别到有效的身份凭证" |
| 2026-10-28 15:26–15:27 | `kimi-for-coding` | batch 全部 401，无进展 |
| 2026-10-28 15:50–15:53 | `kimi-code/k3` | 部分 batch 返回"没找到数据"并被拆分，但 singleton 仍频繁 401；0 accepted codes |
| 2026-10-28 ~17:20 | （探针） | wind 短暂恢复：`wind_get_stock_events` 单码探针正常返回"没找到数据" |
| 2026-10-28 17:25–17:45 | `kimi-for-coding-highspeed` | 恢复 10-24 run 续跑（目录已从 `_broken_highspeed` 改回冻结路径），约 6 会话正常处理（batch 无数据→按设计拆 singleton）；会话内 401 与正常响应混杂 |
| 2026-10-28 ~17:55 起 | （探针） | 401 重现且转为持续；同一探针 40 分钟前成功、此刻失败。手动停掉 pull 保任务重试次数（401 在驱动里按普通 error 计，3 次即 exhausted） |

**间歇性是本轮新证据**：401 不是恒定的，wind 后端鉴权在分钟级尺度上抖动（正常↔401 交替）。

## 当前卡点

### 现象

`kimi-datasource` 的 `wind_get_stock_events` 返回：

```json
{"code": 401, "message": "原因：未识别到有效的身份凭证。建议：在请求头 Authorization 中以 Bearer 方式携带 apiKey 或 access_token。"}
```

### 排除项

- **模型选型**：highspeed / K2.8 / K3 均出现 401。
- **CLI 版本**：kimi 2.3.3；10-28 已执行过 CLI 更新，401 依旧。
- **本机凭证**：`C:\Users\wangc\.kimi-code\credentials\kimi-code.json` 存在且未过期。
- **额度/周限额**：401 是鉴权错误，不是 403/429 额度耗尽。
- **插件本地配置**：kimi-datasource 3.4.0 本机不存任何数据源凭证，401 由其上游服务→Wind 段返回。

### 结论

401 来自 `kimi-datasource` 的 **wind 后端本身**，不是模型层。某些代码/时段偶尔返回"没找到数据"（可解析），但大量调用被 401 阻断。初步判断为后端凭证/限流策略不稳定，或 wind 数据源已改为需要显式凭证。

## 待办 / 下一步

1. ~~更新 kimi CLI~~（已做，无效，2.3.3 上 401 依旧）。
2. **联系 Kimi 支持**：确认 wind 数据源当前是否需要额外绑定 Wind 账号或 apiKey（最可能有效的动作）。
3. **换电脑试**（owner 决定，见下节）。
4. **若恢复**：续跑当前 run（`D:\exports\bt_corp_actions_incr_20261028`；pull 前确认无 `work/runner.lock` 残留），完成后 `assemble` → `prepare-merge`。
5. **若无法恢复**：评估换数据源（如 tushare/akshare/同花顺 iFind）或延后增量窗口。

## 换电脑续跑说明

run 的 `run.json` 冻结了**绝对路径**与 base 哈希，换机必须原样复刻，否则 `Run()` 校验直接拒绝：

- `D:\exports\bt_corp_actions_incr_20261028\` —— 整目录拷贝（含 `work/tasks.json` 任务日志、`raw_events/`、`run.json`）
- `E:\stock_data\corp_actions\` —— 基础湖 4 文件（`manifest.json` / `events.parquet` / `listing.parquet` / `failures.parquet`），字节级一致（init 时有 sha256 钉住）
- `D:\exports\bt_corp_actions_20261006\universe.txt` —— 2774 码冻结 universe（同样有 sha256）
- Python 环境：`vanna312`（pyarrow 必需）；kimi CLI + kimi-datasource 插件可用

续跑命令（新机上路径一致时）：

```powershell
D:\anaconda3\envs\vanna312\python.exe scripts\data\pull_corp_actions_incremental.py pending --out-dir D:\exports\bt_corp_actions_incr_20261028
D:\anaconda3\envs\vanna312\python.exe scripts\data\pull_corp_actions_incremental.py pull --out-dir D:\exports\bt_corp_actions_incr_20261028
```

注意：`kimi-code/k3` 模型仅在本分支放开了 `MODELS` 白名单；在 master 上跑 k3 run 会被拒。备选：也可以在新机全新 `init`（窗口起点固定 2026-10-07，end=init 当天），代价是重跑批次拆分阶段；已冻结的旧 run 互不冲突。

## 产物位置

- 当前 run：`D:\exports\bt_corp_actions_incr_20261028`（k3，窗口 10-07→10-28）
- 10-24 highspeed run：`D:\exports\bt_corp_actions_incr_20261024`（已从 `_broken_highspeed` 改回冻结路径；窗口 10-07→10-24，可续跑，状态干净无锁）
- 旧 kimi-for-coding 失败证据：`D:\exports\bt_corp_actions_incr_20261024_kimi_for_coding_401`
