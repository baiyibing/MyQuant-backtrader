# Handoff：本机 Rust 环境已刷新 → OSkhQuant1.3 请重编 qmt-netem 并试跑

- **日期**：2026-09-21（Asia/Shanghai）
- **发件仓**：MyQuant-backtrader（研究脸）
- **收件仓**：OSkhQuant1.3（交易栈；路径 `D:\PycharmProjects\OSkhQuant1.3`）
- **机器**：同一台 Windows 开发机（环境变量与 toolchain 共享）
- **动作建议**：**做**。1.3 只须重编并烟测 **`qmt-netem/`**。不要 `cargo clean`，不要整编 `vendor/nautilus_trader`，不要在 1.3 里编 `turnover-resist`（该 crate 已迁到本仓）。

---

## §0 给 1.3 的结论（先看这 6 条）

1. 本机已升到 **rustc / cargo 1.98.1**（`stable-x86_64-pc-windows-msvc`）+ **rustup 1.29.1**。
2. 已安装 **sccache 0.18.0**（`D:\rust\cargo\bin\sccache.exe`），用户级 **`SCCACHE_DIR=E:\rust-sccache-cache`**（目录已存在）。缓存不要再落到 C 盘。
3. 研究仓 `turnover-resist` 的 crate 级 `[build] rustc-wrapper = "sccache"` 已启用。**1.3 的 `qmt-netem/.cargo/config.toml` 没有 `rustc-wrapper`**，只设了 `linker = "rust-lld"`。用户级 **`RUSTC_WRAPPER=sccache` 现已设**（2026-09-21）；qmt-netem 只要 **新开壳** 就能吃到 sccache。
4. 用户级三件套现已齐：`SCCACHE_DIR`、`RUSTC_WRAPPER`、**`CARGO_TARGET_DIR=E:\rust-targets`**（目录已建）。研究仓 `turnover-resist` 与 1.3 `qmt-netem` **共用这一处产物根**（扁平 `release` / `release-fast`）。**不要设成 Machine 级**，以免 SYSTEM 的 win-ci 写进同一棵树。
5. 请在 **新开的 PowerShell** 里 `cd qmt-netem` 后 `cargo build --profile release-fast`，再 `--help` 烟测。禁止从仓库根 `cargo build --manifest-path`（Cargo 只读 cwd/父目录的 `.cargo/config.toml`）。
6. **禁止 `cargo clean`**。共用 `CARGO_TARGET_DIR` 之后，在 **任一** crate 里 `cargo clean` 都会清空 **两边** 的产物（含研究仓 DuckDB 增量）。缓存坏了只动 `sccache --clear`。

---

## §1 本机实测（2026-09-21，不要猜）

| 项 | 实测值 |
|---|---|
| `CARGO_HOME` | `D:\rust\cargo` |
| `RUSTUP_HOME` | `D:\rust\rustup` |
| rustc / cargo | 1.98.1 |
| rustup | 1.29.1 |
| 工具链 | `stable-x86_64-pc-windows-msvc` |
| sccache | 0.18.0，`D:\rust\cargo\bin\sccache.exe` |
| 用户 `SCCACHE_DIR` | `E:\rust-sccache-cache`（已存在） |
| 用户 `RUSTC_WRAPPER` | `sccache`（2026-09-21 补上） |
| 用户 `CARGO_TARGET_DIR` | `E:\rust-targets`（2026-09-21 落地；Machine 未设） |
| `E:\rust-targets` | **已建**（空目录，待首次 `release-fast`） |
| 盘空间（当日，清 `rust-ci-target` 后） | C: 空 90GB；D: 空 79GB；E: 空 42GB |
| Python | `D:\anaconda3\envs\vanna312\python.exe`（3.12） |

研究仓 crate 配置（`MyQuant-backtrader/turnover-resist/.cargo/config.toml`）：

- `[build] rustc-wrapper = "sccache"` 已开。
- `rust-lld` **注释掉**（DuckDB `duckdb-sys` 与 rust-lld 的 `-L` 传播不兼容）。qmt-netem **没有** DuckDB，继续用 rust-lld 是合理的，不要把研究仓的 lld 禁用抄过去。

研究仓 lockfile 刷新（polars 0.46 / pyo3 0.24 等 semver 内 `cargo update`）只影响本仓 `turnover-resist/`，**不要 cherry-pick 进 1.3**。GitHub PR：MyQuant-backtrader **#160**。

---

## §2 1.3 该编什么、不编什么

| 路径 | 做不做 | 原因 |
|---|---|---|
| `qmt-netem/` | **做**：`release-fast` 重编 + CLI 烟测 | 本仓一等公民 Rust；MockQMT TCP 损伤代理；toolchain 升级后应确认能链、能跑 |
| `vendor/nautilus_trader/` | **默认不做** | 第三方 workspace，全编极重；仅当你们正在改 nautilus 绑定、或现有二进制已坏时才编 |
| `turnover-resist/` | **不要在 1.3 编** | S2 后 crate 在研究仓；1.3 只留 `oskh_factors` chip/bridge 微包消费产物 |
| 测试机 | **不要 cargo** | 测试机永远不需要本机编译（既有纸面部署约定） |

`qmt-netem` 已有 `[profile.release-fast]`（`inherits = "release"`，`lto = false`，`codegen-units = 16`）。与研究仓同一口径。

---

## §3 用户级 env（本机已落地；1.3 新开壳即可）

同机用户级已设：

```text
SCCACHE_DIR=E:\rust-sccache-cache
RUSTC_WRAPPER=sccache
CARGO_TARGET_DIR=E:\rust-targets
```

两仓交互编译共用这一根：`E:\rust-targets\release-fast\turnover-resist.exe` 与 `E:\rust-targets\release-fast\qmt-netem.exe`。1.3 微包 `_find_exe()` 已硬编码前一条路径。crate 名不同，二进制不撞。

**不要设 Machine 级 `CARGO_TARGET_DIR`。** win-ci 三个 runner 是 SYSTEM 服务，读不到 User env——这是故意的，避免再出现 `rust-ci-target` 那种属主混写。

**不要**把 `vendor/nautilus_trader` 编进这个目录（workspace 极大）。若必须编 nautilus，该会话临时把 `CARGO_TARGET_DIR` 指到别处或清空。

D: 上 `turnover-resist\target\` 仍是切换前的旧产物，**先编到 E: 再考虑删旧树**，不要 `cargo clean`。

已开着的终端读不到刚写的用户 env，**必须新开 PowerShell / 重启 IDE**。校验：

```powershell
rustc -V
cargo -V
sccache --version
echo $env:SCCACHE_DIR
echo $env:RUSTC_WRAPPER
echo $env:CARGO_TARGET_DIR
sccache --show-stats
```

`Compile requests` 在第一次编前可以是 0。编完应看到请求数上升；命中率第一次可能低（toolchain 刚升到 1.98.1）。

---

## §4 重编 + 试跑（qmt-netem）

在 **crate 目录内**执行（与研究仓 rust-build 规则同一条：Cargo 只读 cwd/父目录 `.cargo/config.toml`）。

```powershell
cd D:\PycharmProjects\OSkhQuant1.3\qmt-netem
cargo build --profile release-fast
```

预期产物：`E:\rust-targets\release-fast\qmt-netem.exe`。

烟测（不接 miniQMT、不改 live）：

```powershell
E:\rust-targets\release-fast\qmt-netem.exe --help
```

可选：`cargo test`（crate 若几乎无测，空过也算过）。**不要**在试跑里对真 miniQMT 端口做损伤注入，除非操作员明确要做 Mock 联调。

参考用法（仅文档，默认不要在这次执行）：

```powershell
qmt-netem --bind 127.0.0.1:15861 --upstream 127.0.0.1:58610
```

编完再看缓存：

```powershell
sccache --show-stats
```

---

## §5 硬禁止 / 易错

1. **禁止 `cargo clean`**。共用 `E:\rust-targets` 后，任一 crate 的 clean 会清空研究仓 **和** qmt-netem 的产物。缓存坏了只 `sccache --clear`。
2. **禁止从 1.3 仓库根** `cargo build --manifest-path qmt-netem/Cargo.toml`。会跳过 `qmt-netem/.cargo/config.toml` 的 **rust-lld**。
3. 不要把研究仓「lld 已禁用」抄到 qmt-netem。qmt-netem 无 DuckDB，lld 应保留。
4. 不要为了「对齐」去 `cargo update` qmt-netem 的 lockfile，除非编不过。本次研究仓 lockfile 刷新与 1.3 无关。
5. 1.3 旧文档 `docs/handoff/2026-09-10-test-machine-paper-deploy.md` §9.2 可改回三件套已落地（User 级，非 Machine）。`E:\rust-ci-target` 已删，win-ci 不再编 Rust。

---

## §6 1.3 回执（做完请写回）

请回报这四行，研究侧就能判断这次升级是否波及交易栈 Rust：

```
rustc: …
qmt-netem build: exit …
qmt-netem --help: ok/fail
sccache Compile requests / Cache hits: …
```

失败时贴：是否在 `qmt-netem/` 目录内编译、`RUSTC_WRAPPER` 是否进了新壳、rust-lld 是否找不到、以及完整 `cargo` 尾部错误。不要先 `cargo clean` 再重试。
