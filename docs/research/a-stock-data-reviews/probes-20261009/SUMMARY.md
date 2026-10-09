DONE

- 离线单测：隔离 venv 执行177项，**173通过、4项联网测试跳过、0失败/错误**；测试阶段阻断 socket 联网。
- 补充探针复现：东财旧 helper 将业务错误/缺schema变成空结果；复权因子 NaN、±Inf、负数未被拒绝，现有测试全绿不代表这些边界安全。
- 申万官方 XLS 一次成功 HTTP 落地，**12,925行 / 5,930代码**；补齐中间证书后完整TLS校验通过，原始响应、哈希与失败日志齐备。
- **今日1.3权威行业表核验受阻**：本机无湖根配置及实表。改用明确标注的9月13日本地Wind历史副本做辅助对照：5,238一致、2差异、690仅申万覆盖；两处变更日期均为9月24日，不能声称今日Wind核验通过。
- 申万表是有效日期历史，尚非严格“当时已知”PIT证明：12,652行更新时间晚于计入时间；as_of截面包含历史旧分类/可能退市标的，不能直接当在市股票清单。
- 四票×2026-10-08量价：**OHLC全部精确一致**；688按股，其余主板/创业板/588 ETF按手×100，量差分别+43、+35、0、−48股/份，符合#57整手取整口径。
- 分红实证发现两处错误：**PRETAX_BONUS_RMB每10股被标成每股（现金放大10倍）**；真实转增字段IT_RATIO被误读为TRANSFER_RATIO而丢失。完整schema缺口表已给出，不能直接替代BT ExDivEvent。
- 全部执行及新增结果在Bot VM本地；**无PR/推送、未访问4090、未调用Kimi或使用其额度**。四条探针执行与证据整理完成；DONE不表示所有探针通过，行业今日权威对照的限制见第4条。

## 结果入口

| 探针 | 中文报告 | 机器可读结果/证据 |
| --- | --- | --- |
| 1 离线单测/边界 | [01-offline-tests.md](01-offline-tests.md) | 01-unittest.log、01-results.json、offline_probe.py |
| 2 申万PIT/行业对照 | [02-industry-pit.md](02-industry-pit.md) | 02-sw-history.csv、02-sw-asof-20261009.csv、02-industry-comparison.csv、02-industry-differences.csv |
| 3 四票量价/#57 | [03-price-volume.md](03-price-volume.md) | 03-price-volume.csv、03-results.json、http-manifest.json、raw/ |
| 4 分红schema | [04-dividend-schema.md](04-dividend-schema.md) | 04-schema-gaps.csv、04-corp-actions-stats.json、04-dividend-replay.csv |

执行日期：2026-10-09（Asia/Shanghai）；a-stock-data检出标签v3.10.1。运行环境、源码身份与哈希见 environment.json；依赖见 requirements.freeze.txt；产物校验见 SHA256SUMS（排除venv及仍可能追加的外部会话日志）。

本轮只写探针目录，未修复源仓实现、未写行情湖。后续最小动作是提供Bot VM本地的今日 vendor_wind_sw_l1 实表并重做同日对照；其余接入缺口均已有可复跑证据，无需Kimi补采即可审阅。
