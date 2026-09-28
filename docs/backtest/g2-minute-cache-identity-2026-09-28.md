# G2｜共享分钟缓存来源 / 快照身份守卫（2026-09-28）

本刀获得 Human sequential GO，仅实施审计 G2。**勿合：Do NOT merge without human 合。**
同窗口命中不等于相同研究输入；本刀接受缺认证导致命中率下降与重建耗时变化。
G3–G8 均未启动；不重开 #135 P1/P4、R3/R4、δ1/δ2/δ5/δ6 deferred，
不改 hl/fen/TopK/X-* 默认值，不恢复 Cerebro/PortAna。

## 冻结合同

`ashare_bars.minute_cache_identity` 为共享 minute-none 缓存生成以下认证字段，
每次新写缓存均写入同名 `.json` sidecar 顶层：

| 字段 | 当前合同 |
| --- | --- |
| `identity_version` | 整数 `1` |
| `start` / `end` | 规范化 `YYYYMMDD` 窗口 |
| `dividend_type` | 显式 `none`，代表当前共享缓存价格域 |
| `schema` | `_cache_schema()` 按列顺序组成 `[名称, Arrow 类型字符串, nullable]` 列表的 SHA-256 |
| `resolver_identity` | `lake_root`，或 `resolve_period_root("1m") / "dividend_type=none"`，经 `resolve(strict=True)` 得到的绝对目录字符串 |
| `source_snapshot` | 非空调用方 `source_snapshot=` token，或下述廉价默认指纹 |

认证字段必须全部存在、类型及值均与本次解析的身份一致，才允许命中或补齐代码时合并旧缓存。
缺 sidecar、非法 JSON、非对象 JSON、缺字段或任一不匹配均不可复用（**缺认证视为不可复用**）。
默认 `use_cache=True` 时从湖加载所需代码后重建；不继承认证失败文件的其他代码。
认证所用绝对根路径同时用于本次 fill，避免二次 resolver / symlink 解析漂移。
源目录不存在即报错，即便提供显式 token 也不绕过目录存在性检查。

所有指纹使用 UTF-8 JSON（`sort_keys=True, separators=(",", ":"), ensure_ascii=False`）的 SHA-256。
默认快照 `shallow-v1:<sha256>` 的输入为 `[根目录记录, 直属条目记录列表]`：
每条记录为 `[name, st_mode, st_size, st_mtime_ns]`，直属条目按名称排序；
仅调用根目录与直属条目的 `stat()`，不递归、不读行情内容。复杂度为根目录直属条目数。

**边界：这不是全湖内容 hash 或完整 PIT 认证。** 深层 `data.parquet` 原地修数可能不改变父分区目录元数据；
保留元数据的快照替换也可能不可辨认。此类更新必须由调用方更换 `source_snapshot=`（不可跨修数复用 token），
或由上游发布流程更新直属分区目录 mtime。运行期间源应保持冻结，本守卫不提供源的原子快照。
本刀不改采集/merge，不增加全湖扫描。显式 token 的真实性由调用方负责。

## 路径与迁移

新路径为 `minute_none_{start}_{end}_{digest}.parquet`，`digest` 为全部认证字段
JSON SHA-256 的前 12 位十六进制。不同源 / 快照通常落到不同路径；完整 sidecar 比较仍是复用条件，
短摘要本身不是认证。旧 `minute_none_{start}_{end}.parquet` 及旧 JSON 不迁移、不删除、永不自动复用。

保留 `--no-cache` / `--rebuild-cache`：前者绕过身份构建及缓存 I/O，后者不读取或合并旧缓存。
`status["cache"]` 保留 `hit/partial/miss/off/rebuild`；当前摘要路径存在但认证失败为 `miss:identity`。
换源 / 换快照产生新路径时为普通 `miss`。
volume/amount-required 路径继续绕过无量缓存，状态仍为 `off:volume_required`。
v7 小名单 CLI 不使用此共享缓存，本刀不强接线、不宣称改变其行为。

## 合成验证矩阵

全部使用 `tmp_path` / 合成 frame，无真实湖、无 4090、无全湖读取或回测。

| 用例 | 预期 |
| --- | --- |
| 同窗同身份写后再读 | hit，数值一致 |
| 同窗换 snapshot / lake_root | miss，新路径，旧文件保留 |
| 旧日期路径 + 旧 JSON | miss，不读取旧数据 |
| 每个认证字段缺失 / 不匹配（含 schema、价格域） | miss:identity，禁止合并未请求代码 |
| 缺 / 损坏 / 非对象 sidecar | miss:identity |
| 同身份补齐代码 | partial，保留此前认证代码 |
| 默认快照稳定性 / 直属目录 mtime 或条目变化 | 稳定 / 失效 |
| resolver 根路径与 fill | 同一解析后的根目录 |
| no-cache / rebuild / volume / amount | 保持各自旁路或重建语义 |
| 源目录不存在 | fail-closed 报错 |

测试入口：`tests/test_minute_cache_identity.py`，并回归 ashare bars、分钟 frame migration、
CSV minute、strategy11、tail primitives。这里只证明合成身份失效规则，**不声称湖验证**。
本次聚焦 pytest：**208 passed**（Python 3.12）；四项无数据门禁
`verify_oskh_data_contract` / `verify_data_path_ssot` / `verify_no_hardcoded_machine_paths` /
`verify_tr_bridge_import_ssot` 均通过。变更文本 UTF-8 无 BOM，NUL 数为 0。
剩余 G3–G7 仍须逐刀独立 Human GO，G8 亦不在本次范围。
