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

## 当前卡点

### 现象

`kimi-datasource` 的 `wind_get_stock_events` 返回：

```json
{"code": 401, "message": "原因：未识别到有效的身份凭证。建议：在请求头 Authorization 中以 Bearer 方式携带 apiKey 或 access_token。"}
```

### 排除项

- **模型选型**：highspeed / K2.8 / K3 均出现 401。
- **CLI 版本**：当前 kimi 2.3.3。
- **本地 OAuth**：`C:\Users\wangc\.kimi-code\credentials\kimi-code.json` 存在且未过期。
- **额度/周限额**：401 是鉴权错误，不是 403/429 额度耗尽。

### 结论

401 来自 `kimi-datasource` 的 **wind 后端本身**，不是模型层。某些代码/时段偶尔返回"没找到数据"（可解析），但大量调用被 401 阻断。初步判断为后端凭证/限流策略不稳定，或 wind 数据源已改为需要显式凭证。

## 待办 / 下一步

1. **更新 kimi CLI**：`kimi update` / `kimi upgrade`，观察 OAuth 到 datasource 的链路是否修复。
2. **联系 Kimi 支持**：确认 wind 数据源当前是否需要额外绑定 Wind 账号或 apiKey。
3. **若恢复**：用 `--resume-quota` 续跑当前 run（`D:\exports\bt_corp_actions_incr_20261028`），完成后 `assemble` → `prepare-merge`。
4. **若无法恢复**：评估换数据源（如 tushare/akshare/同花顺 iFind）或延后增量窗口。

## 产物位置

- 当前 run：`D:\exports\bt_corp_actions_incr_20261028`
- 旧 highspeed 失败证据：`D:\exports\bt_corp_actions_incr_20261024_broken_highspeed`
- 旧 kimi-for-coding 失败证据：`D:\exports\bt_corp_actions_incr_20261024_kimi_for_coding_401`
