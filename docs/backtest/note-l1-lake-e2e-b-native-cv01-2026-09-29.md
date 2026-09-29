# B-native-CV-01：CSV/v7 原生 CLI ↔ L1 真湖验收 harness

2026-09-29 · Human「B GO」· 基线 `b3a76a9` · Track B 首刀。
授权冻结：`/workspace/handoffs/b_native_cv01_20260929/HUMAN_GO.md`；
规格：`/workspace/handoffs/next_tracks_abcde_order_20260929/ORDER_EVAL.md` §5。

入口：`scripts/research/verify_run_protocol_lake_parity.py`。
只测 `csv_minute/version8`、独立 `v7`，每家自己的原生 CLI 与
`NativeCliRequest` / `run()` 对照，不建立跨家族等价关系。
无 engine / loader / writer / adapter / facade 修改；`production_C=frozen`。

## PASS 的边界

PASS 是 **固定湖配方下 native↔L1 委托保真**，需要输入身份稳定、完整输出对照
及该格实际触发条件同时成立。正常格必须真实买入及卖出、至少两行权益和审计事件；
成功空跑记 `NOT_COVERED / 未覆盖`。正常现金 1,000,000,000（宽资金配方），
低现金 1，名单预算 1,000,000；这些显式参数不改生产默认。
version8 低现金须原生 `InsufficientCashError` 非零退出；v7 须真实 `skip/skip_cash`。
同样报另一个错误是 FAIL，未触发目标资金路径是未覆盖。

此 PASS 不证明湖数据质量、模型经济正确性、可执行收益、收益排名或完整策略认证；
不授权 SSOT 绿 R/S、不接 L2 湖、不改 `no_ssot_compare_authorization`。
不比较 version8 与 v7 的 NAV，不重录 golden。

## 配方与身份

默认 `20251023..20251104` 来自原生 CLI 的 start 默认和 short parity window 文案。
两家均显式传入仓内现有 `stock_pool/`，只接受窗口内真实存在、原生 parser 可读的
`YYYYMMDD.csv`；不生成或裁剪新池。v7 这是同格式名单的委托验收配方，
不宣称其名单是金榕元信号。可显式指定已有池和窗口，不能看结果后自动挑窗。

任何 native 运行之前，以独占创建并 fsync 的 `recipe.json` 登记：

- 完整 SHA、branch、dirty 状态/差异 digest、harness hash；解释器路径及路径/binary
  SHA256、版本和包版本；安全环境字段及完整环境的 hash（不导出其他环境明文）。
- resolver 实际根或原样异常；池文件、全部所涉 none 日/分钟分区、指数分区、
  adj_factor / ex_date_index 文件 hashes；native 指数日历及 preload。
  缺源不补 bar、不宣称无公司行动；哈希整个分区包含原生 warmup 读取范围。
- 原生 summary 可能读取的既有 CSV 日线权益文件集合与 hashes；配置/authority 身份。
- 每格精确 argv、child cwd、相对输出名、现金、费用、价域、开关、缓存及比较政策。

live 调用前后均重新核对输入身份，变化即 FAIL。CSV `--no-cache`，v7 原生
`bars_from_pool` 已关闭窗口缓存；仅 numba 代码缓存放在新 receipt 根内。
每侧 fresh process / fresh cwd，native argv 完全相同，输出名都为 `artifacts`。
child resolver 环境显式固定到已解析的绝对根；不更改宿主环境或数据。

## 输出与比较政策（预登记）

保存每侧原始 `stdout.bin`、`stderr.bin`、native exit、request 和所有原生工件。
`comparison.json` 同时保留原字节 hashes、`byte_identical` 与逐字段差异；
原始字节不同始终追加不允许的 `<name>/bytes` 差异并判 FAIL，即使已有允许的解析差异；**不称 byte-identical**。

- 文件集合、CSV 列和行序、数量/价费/position_id、权益、审计 phase/cash/commission
  严格比较，不排序、不做浮点容差。v7 不暴露独立持仓快照；比较其 holdings 和
  原生审计，不造持仓/阶段工件。完整内部状态不在 CLI 可观察合同内。
- 两家成功均要求 trades、daily_equity、summary、execution-audit；CSV 显式
  `--emit-run-manifest`，v7 要求原生 run-config。其他实际文件也全部比较。
- stdout 与 summary 仅允许代码中列出的完整格式行里的**耗时数值**变化；
  行内代码数、缓存状态、经济数值仍必须一致。stderr 字节严格相同。
- 相对输出名消除路径差异；无路径/时间戳通配豁免。
  manifest 的 summary 原始 hashes 必须先各自验真；因已声明耗时造成的派生 hash
  差异单独列出，其他 hashes 严格比较。JSON/CSV 未声明的序列化变化失败。

## 拒绝格与 BLOCKED

每家四格：normal、low_cash、invalid_config、bad_output。
invalid_config 的非法 `--minute-source` 在 argparse 阶段拒绝，无湖也运行。
bad_output 在新隔离 cwd 创建一个 `artifacts` 普通文件，验证 native writer 拒绝，
并检查 sentinel 没被改写。两家均先加载/模拟再写出，所以该格依赖真实湖。
v7 本身没有通用“已有目录拒覆写”合同，不能用历史目录试验或伪称其具备此保证。

GO 宿主只设 `OSKH_DATA_ROOT=/workspace/OSkhQuant1.3`；minute lake 未配置。
这不是空湖，resolver `UnconfiguredDataRootError` 原文写入 receipt。
normal、low_cash、bad_output 均 `NOT_RUN`，reason=`BLOCKED: <真实异常>`。
不得以合成数据、help 或两家 invalid_config PASS 代替 live PASS。

退出码：0=全部格 PASS；1=任一 FAIL；2=存在 BLOCKED/NOT_RUN 且无 FAIL；
3=存在 NOT_COVERED 且无 FAIL/BLOCKED。部分拒绝格 PASS 不能把总退出码改成 0。
本首刀交付完成条件为 PR + 外部 receipt，不要求无湖宿主的 harness exit 0。

## 配置宿主运行

由操作者先通过 `OSKH_SOURCE_PARQUET_ROOT` 或 `.authority` 配好真实湖，
不可按本文猜盘符。需有 minute/daily none、指数 preload、adj/ex-date 源。
使用同一个显式解释器启动 harness 和 native 子进程；新输出根必须在仓库和输入源外。

```bash
OSKH_MERGE_PYTHON=/workspace/vanna312/bin/python \
  /workspace/vanna312/bin/python scripts/research/verify_run_protocol_lake_parity.py \
  --output-root /tmp/B-native-CV-01-host-run-01
```

可加 `--csv-pool-dir <existing-dir> --v7-pool-dir <existing-dir> --start YYYYMMDD --end YYYYMMDD`。
输出根必须不存在；每次新建 recipe，不续写旧证据。
`result.json` 是总矩阵；各格 JSON、comparison 和 raw files 保留审查链。

```bash
/tmp/l2s2-ledger-venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_verify_run_protocol_lake_parity.py \
  tests/test_research_run_protocol_csv_minute.py tests/test_research_run_protocol_v7.py
```

测试只用明确标注的 comparator 工件 fixtures，无湖依赖，无合成湖认证。
交接：`/workspace/handoffs/b_native_cv01_20260929/B_NATIVE_CV01_RECEIPT.md`。
待 Human「合」，本刀不合并。
