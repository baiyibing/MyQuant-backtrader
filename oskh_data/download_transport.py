"""Daily-bars download transport seam.

plan-daily-download-backend-switch-2026-08-24 B1（seam-only）：
- 旋钮 ``OSKH_DAILY_DOWNLOAD_BACKEND = xtdata|daqmt（默认）``（env > YAML > default）
- ``DailyBarsTransport`` Protocol + ``XtdataDownloadTransport`` + 工厂
- **B1 不动 ``downloader.py`` 内部**：430 行 watchdog 闭包的深抽取并入 B3 与
  daqmt 同批 diff 验证（两次搬动风险 > 一次；人裁可推翻，见 plan §4 B1 注）

fail-closed 语义（plan §3.1，教训 46 口径）：
- 非法旋钮值 → 硬失败（不静默当 xtdata）
- 两旋钮生命周期正交，但部署组合必须与 vendor capability 一致：
  mini × xtdata / daqmt-shim × daqmt 合法，交叉两组硬失败。

divid_factors 预算语义归 transport（plan §3.4 v1.1）：xtdata 实现内部保留
``xtdata_call_with_budget_sync`` 包装（detect 现状依赖 budget_s=5/retries=2），
调用方不再自包 budget；daqmt 实现（B3）用 adapter op timeout。
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Protocol, runtime_checkable

import pandas as pd

from common.infra.exceptions import ConfigurationError
from common.infra.quant_logger import get_logger

logger = get_logger(__name__)

# ---- B3c：自 downloader 迁入的 xtdata 下载/读取机器（行为零变化）----
import os
import threading
import time
from dataclasses import dataclass, field

from common.infra.constants import EnvVarKeys, StreamObservabilityEvent
from common.infra.exceptions import MarketDataError
from common.infra.timekeeping import mono_now
from common.integrations.xtdata_call_budget import xtdata_call_with_budget_sync

def _chunks(lst, n):
    """Yield successive n-sized chunks (Phase 2 get_market_data_ex 分批)."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _resolve_download_watchdog_timeouts(stock_count: int):
    """download_history_data2 watchdog 三超时（env 可覆盖；搬自 downloader，行为不变）。"""
    import os as _os

    big_batch = stock_count >= 200
    raw_start = _os.environ.get("OSKH_DOWNLOAD_START_TIMEOUT_SEC", "")
    raw_stall = _os.environ.get("OSKH_DOWNLOAD_STALL_TIMEOUT_SEC", "")
    raw_total = _os.environ.get("OSKH_DOWNLOAD_TOTAL_TIMEOUT_SEC", "")
    try:
        start = float(raw_start) if raw_start else (90.0 if big_batch else 30.0)
    except ValueError:
        start = 90.0 if big_batch else 30.0
    try:
        stall = float(raw_stall) if raw_stall else 120.0
    except ValueError:
        stall = 120.0
    try:
        total = float(raw_total) if raw_total else None
    except ValueError:
        total = None
    if total is None:
        total = min(7200.0, max(600.0, stock_count * 1.5 + 120.0))
    return start, stall, total


def _xt_get_xtdata():
    from oskh_data.qmt_xtdata import get_xtdata

    return get_xtdata()


@dataclass
class DownloadOutcome:
    """download_bulk 契约：frames + 批失败元数据（downloader fail-rate 消费）。"""

    frames: dict
    timeout_stock_set: set = field(default_factory=set)
    failed_batches: list = field(default_factory=list)



DOWNLOAD_BACKEND_KEY = "OSKH_DAILY_DOWNLOAD_BACKEND"
DOWNLOAD_BACKENDS = ("xtdata", "daqmt")
# A2 人裁 GO 2026-09-01：repo default 翻 daqmt；mini hosts 必须显式 xtdata。
DEFAULT_DOWNLOAD_BACKEND = "daqmt"

# 与 detect_ex_date_changes 现状一致的 per-call 预算（plan §3.4：预算语义归 transport）
DIVID_FACTORS_BUDGET_S = 5.0
DIVID_FACTORS_RETRIES = 2


def validate_download_backend_vendor_compatibility(backend: str, vendor: str) -> str:
    """Validate the four vendor × daily-download combinations from capability SSOT."""
    resolved = str(backend or "").strip().lower()
    if resolved not in DOWNLOAD_BACKENDS:
        raise ConfigurationError(
            f"{DOWNLOAD_BACKEND_KEY}={resolved!r} 非法；合法值: {DOWNLOAD_BACKENDS}"
            "（fail-closed，不静默回落）"
        )

    from common.integrations.vendor_capabilities import vendor_capability

    normalized_vendor = str(vendor or "").strip().lower().replace("-", "_")
    forbids_xtdata = vendor_capability(normalized_vendor, "forbids_xtdata_init")
    daily_bars_via_shim = vendor_capability(
        normalized_vendor,
        "query_daily_bars_via_shim",
    )
    if resolved == "xtdata" and forbids_xtdata is True:
        raise ConfigurationError(
            f"QMT_BROKER_VENDOR={normalized_vendor!r} forbids_xtdata_init；"
            f"{DOWNLOAD_BACKEND_KEY}=xtdata 非法（fail-closed）"
        )
    if resolved == "daqmt" and daily_bars_via_shim is not True:
        raise ConfigurationError(
            f"QMT_BROKER_VENDOR={normalized_vendor!r} 未声明 "
            f"query_daily_bars_via_shim；{DOWNLOAD_BACKEND_KEY}=daqmt "
            "非法（fail-closed）"
        )
    return resolved


def resolve_download_backend() -> str:
    """旋钮解析：env > YAML runtime > default（原则⑧）；组合不兼容亦硬失败。"""
    from common.infra.runtime_config import get_raw
    from common.integrations.vendor_capabilities import resolve_configured_vendor

    raw = str(get_raw(DOWNLOAD_BACKEND_KEY) or "").strip()
    if not raw:
        raw = DEFAULT_DOWNLOAD_BACKEND
    return validate_download_backend_vendor_compatibility(
        raw,
        resolve_configured_vendor(force_refresh=True),
    )


class TransportHealth:
    """transport 探活结果（backend / ok / detail）。"""

    def __init__(self, backend: str, ok: bool, detail: str = "") -> None:
        self.backend = backend
        self.ok = ok
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"TransportHealth(backend={self.backend!r}, ok={self.ok}, detail={self.detail!r})"


@runtime_checkable
class DailyBarsTransport(Protocol):
    """日线数据传输层契约（plan §3.2；消费方 = downloader / detect / 副轨 / 编排器）。

    ``read_frames`` 返回 frame schema 与 xtdata 路径对齐（time epoch-ms +
    OHLCV/amount；``fill_data=True`` 钉死——两后端行数口径一致，coverage 不漂移，
    kimi R5）。
    """

    def probe(self) -> TransportHealth:
        """探活 + 能力；不可用必须 ok=False（fail-closed，调用方硬失败）。"""
        ...

    def sector_codes(self, sector: str) -> List[str]:
        ...

    def download(
        self,
        stock_list: List[str],
        start_time: str,
        end_time: str,
        *,
        period: str = "1d",
        adjust_type: str = "front",
        incrementally: bool = False,
        callback: Optional[Callable] = None,
        progress_log_interval_sec: Optional[float] = 10.0,
    ) -> Dict[str, pd.DataFrame]:
        ...

    def read_frames(
        self,
        stock_list: List[str],
        *,
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        dividend_type: str = "none",
    ) -> Dict[str, pd.DataFrame]:
        ...

    def download_bulk(
        self,
        codes: List[str],
        start_time: str,
        end_time: str,
        *,
        period: str = "1d",
        adjust_type: str = "front",
        incrementally: bool = False,
        callback: Optional[Callable] = None,
        progress_log_interval_sec: Optional[float] = 10.0,
    ) -> "DownloadOutcome":
        """管线面：下载+读取+批失败元数据（downloader fail-rate 消费）。"""
        ...

    def divid_factors(
        self, code: str, start_time: str = "", end_time: str = ""
    ) -> pd.DataFrame:
        """除权因子；超时/重试预算归 transport 实现（调用方不自包 budget）。"""
        ...


class XtdataDownloadTransport(DailyBarsTransport):
    """xtdata（miniQMT）后端——B1 现状路径的薄壳，行为零变化。

    download 委托 ``DataDownloader.download_data``（watchdog/增量过滤/写盘全保留）；
    read_frames/divid_factors/sector_codes 直连 ``oskh_data.qmt_xtdata``。
    """

    backend = "xtdata"

    def probe(self) -> TransportHealth:
        try:
            from oskh_data.qmt_xtdata import get_xtdata

            xtdata = get_xtdata()
            if xtdata is None:
                return TransportHealth(self.backend, False, "get_xtdata returned None")
            return TransportHealth(self.backend, True, "xtdata handle ok")
        except Exception as exc:
            # 含 guojin_daqmt forbids_xtdata_init 闸：数据面选 xtdata 但交易 vendor
            # 禁 xtdata 时在此显式失败（fail-closed）
            return TransportHealth(
                self.backend, False, f"{type(exc).__name__}: {str(exc)[:160]}"
            )

    def sector_codes(self, sector: str) -> List[str]:
        from oskh_data.qmt_xtdata import get_xtdata

        xtdata = get_xtdata()
        return list(xtdata.get_stock_list_in_sector(sector) or [])


    def download_bulk(
        self,
        codes: List[str],
        start_time: str,
        end_time: str,
        *,
        period: str = "1d",
        adjust_type: str = "front",
        incrementally: bool = False,
        callback: Optional[Callable] = None,
        progress_log_interval_sec: Optional[float] = 10.0,
    ) -> "DownloadOutcome":
        """xtdata 批量下载+读取（B3c 自 DataDownloader.download_data 迁入，行为零变化）。

        - 调用方负责增量过滤与 end_time 的 +1min 修正（end_time 传已修正值）。
        - ``incrementally`` 收下不驱动行为（与旧路径一致：过滤在调用方）。
        - 三超时 watchdog + Phase2 分批预算读取原样保留；异常上抛，
          由调用方（downloader）包装 _download_error / 通道腐坏标记。
        """
        xtdata = _xt_get_xtdata()
        total_stocks = len(codes)
        downloaded_set: set = set()
        download_complete = False
        download_started = False
        last_progress_time = mono_now()
        # 0.0 forces first progress line; thereafter throttle when interval > 0.
        last_progress_log_time = 0.0
        _log_interval = (
            float(progress_log_interval_sec)
            if progress_log_interval_sec is not None
            and progress_log_interval_sec > 0
            else 0.0
        )
        (
            _DOWNLOAD_START_TIMEOUT_SEC,
            _DOWNLOAD_STALL_TIMEOUT_SEC,
            _DOWNLOAD_TOTAL_TIMEOUT_SEC,
        ) = _resolve_download_watchdog_timeouts(total_stocks)

        def on_progress(data):
            nonlocal downloaded_set, download_complete, download_started
            nonlocal last_progress_time, last_progress_log_time
            download_started = True
            last_progress_time = mono_now()
            finished = data.get("finished", 0)
            total = data.get("total", 0)
            stock_code = data.get("message", "N/A")
            if stock_code and stock_code != "N/A":
                downloaded_set.add(stock_code)
            if finished > 0 and total > 0:
                now = last_progress_time
                should_log = (
                    _log_interval <= 0
                    or finished == total
                    or last_progress_log_time <= 0
                    or (now - last_progress_log_time) >= _log_interval
                )
                if should_log:
                    last_progress_log_time = now
                    logger.info(
                        f"下载进度: {finished}/{total} "
                        f"({(finished / total) * 100:.2f}%) - 当前: {stock_code}"
                    )
            if total > 0 and finished == total:
                download_complete = True
            if callback is not None:
                try:
                    callback(data)
                except Exception as _cb_exc:
                    # Phase 2 P1 fix: log callback failures instead of
                    # silently swallowing them.  Callback side effects
                    # (audit records, progress updates) must not fail
                    # invisibly.
                    logger.warning(
                        "download progress callback failed; download continues "
                        "but caller side effects may be lost",
                        context={
                            "error_type": type(_cb_exc).__name__,
                            "error": str(_cb_exc)[:200],
                        },
                    )

        # NOTE: xtquant.download_history_data2 is blocking and does not accept
        # `incrementally`. Incremental filtering is done above; here we request
        # the target range for stocks that need updating. Watchdog runs on the
        # main thread while the SDK call runs in a daemon thread (2026-07-15:
        # hung SDK with zero callbacks made the old post-call wait loop useless).
        logger.info(
            "download_history_data2 watchdog "
            f"start={_DOWNLOAD_START_TIMEOUT_SEC:.0f}s "
            f"stall={_DOWNLOAD_STALL_TIMEOUT_SEC:.0f}s "
            f"total={_DOWNLOAD_TOTAL_TIMEOUT_SEC:.0f}s "
            f"(stock_count={total_stocks})"
        )
        dl_exc: list[BaseException] = []

        def _run_download_history() -> None:
            try:
                xtdata.download_history_data2(
                    stock_list=codes,
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                    callback=on_progress,
                )
            except BaseException as exc:  # noqa: BLE001 — surface to watchdog
                dl_exc.append(exc)

        dl_thread = threading.Thread(
            target=_run_download_history,
            name="xtdata-download_history_data2",
            daemon=True,
        )
        dl_thread.start()

        logger.info(f"等待{total_stocks}只股票下载完成...")
        t0 = mono_now()
        while not download_complete:
            now = mono_now()
            elapsed = now - t0

            if dl_exc:
                raise dl_exc[0]

            if not download_started and elapsed > _DOWNLOAD_START_TIMEOUT_SEC:
                raise TimeoutError(
                    f"数据下载未在 {_DOWNLOAD_START_TIMEOUT_SEC:.0f}s 内启动，"
                    f"可能 QMT 未连接/挂起或回调未注册 (stock_count={total_stocks})；"
                    f"请杀本进程、重启国金 miniQMT 后 --resume"
                )

            if elapsed > _DOWNLOAD_TOTAL_TIMEOUT_SEC:
                raise TimeoutError(
                    f"数据下载总超时 {_DOWNLOAD_TOTAL_TIMEOUT_SEC:.0f}s，"
                    f"已完成 {len(downloaded_set)}/{total_stocks}；"
                    f"请杀本进程、重启国金 miniQMT 后 --resume"
                )

            if (
                download_started
                and (now - last_progress_time) > _DOWNLOAD_STALL_TIMEOUT_SEC
            ):
                raise TimeoutError(
                    f"数据下载停滞 {_DOWNLOAD_STALL_TIMEOUT_SEC:.0f}s 无新进度，"
                    f"已完成 {len(downloaded_set)}/{total_stocks}；"
                    f"请杀本进程、重启国金 miniQMT 后 --resume"
                )

            if not dl_thread.is_alive():
                if dl_exc:
                    raise dl_exc[0]
                # SDK returned without a final finished==total callback
                if len(downloaded_set) >= total_stocks:
                    download_complete = True
                    break
                raise TimeoutError(
                    f"download_history_data2 线程退出但未完成 "
                    f"({len(downloaded_set)}/{total_stocks})；"
                    f"请杀本进程、重启国金 miniQMT 后 --resume"
                )

            time.sleep(0.2)

        dl_thread.join(timeout=5.0)
        if dl_exc and not download_complete:
            raise dl_exc[0]

        logger.info(f"下载完成！共 {total_stocks} 个股票")

        # ── Phase 2: get_market_data_ex 分批 + 单批墙钟预算（防 SDK 卡死永久挂起）──
        # v3.1 修正：实际抛 MarketDataError（非 TimeoutError）；extra 在 e.context.extra；
        # 模块级 logger（DataDownloader 无 self.logger）；mono_now（非 time.monotonic）。
        BATCH_SIZE = int(
            os.environ.get(EnvVarKeys.OSKH_FASTPATH_READ_BATCH_SIZE, "300")
        )
        BATCH_TIMEOUT_SEC = float(
            os.environ.get(EnvVarKeys.OSKH_FASTPATH_READ_BATCH_TIMEOUT_SEC, "120")
        )
        FAIL_RATE_THRESHOLD = float(
            os.environ.get(
                EnvVarKeys.OSKH_FASTPATH_READ_FAIL_RATE_THRESHOLD, "0.05"
            )
        )
        _read_total = os.environ.get(
            EnvVarKeys.OSKH_FASTPATH_READ_TOTAL_TIMEOUT_SEC, ""
        )
        try:
            READ_TOTAL_TIMEOUT_SEC = (
                float(_read_total) if str(_read_total).strip() else 0.0
            )
        except ValueError:
            READ_TOTAL_TIMEOUT_SEC = 0.0
        if READ_TOTAL_TIMEOUT_SEC <= 0:
            # 默认 = ceil(N/batch) × batch_timeout × 1.2（N=5538/300 → ~46min）
            _n_batches = max(
                1,
                (len(codes) + BATCH_SIZE - 1) // max(1, BATCH_SIZE),
            )
            READ_TOTAL_TIMEOUT_SEC = _n_batches * BATCH_TIMEOUT_SEC * 1.2

        phase2_t0 = mono_now()
        phase2_deadline = phase2_t0 + READ_TOTAL_TIMEOUT_SEC
        batch_results: dict = {}
        failed_batches: list = []
        timeout_stock_set: set = set()

        for batch_no, batch in enumerate(_chunks(codes, BATCH_SIZE)):
            # 总超时：超时后不开新批、已开批照常合并（同步循环无"还在跑"的批）
            if mono_now() > phase2_deadline:
                logger.warning(
                    "Phase 2 总超时，停止开新批",
                    context={
                        "event": StreamObservabilityEvent.FASTPATH_READ_BATCH_TIMEOUT,
                        "batch_no": batch_no,
                        "remaining": len(codes)
                        - sum(len(b["stocks"]) for b in failed_batches)
                        - len(batch_results),
                    },
                )
                break
            try:
                partial = xtdata_call_with_budget_sync(
                    fn=lambda b=batch: xtdata.get_market_data_ex(
                        field_list=[
                            "time",
                            "open",
                            "high",
                            "low",
                            "close",
                            "volume",
                            "amount",
                        ],
                        stock_list=b,
                        period=period,
                        start_time=start_time,
                        end_time=end_time,
                        count=-1,
                        dividend_type=adjust_type,
                        fill_data=True,
                    ),
                    budget_s=BATCH_TIMEOUT_SEC,  # 120s 直传 budget_s，绕过 10s cap（离线批量）
                )
                batch_results.update(partial)
                logger.info(
                    f"批 {batch_no} 完成 {len(partial)} 只",
                    context={
                        "event": StreamObservabilityEvent.FASTPATH_READ_BATCH_SUMMARY,
                        "batch_no": batch_no,
                        "got": len(partial),
                        "asked": len(batch),
                    },
                )
            except MarketDataError as e:
                # 预算超时 vs fn 自身 MarketDataError，用 reason_code 区分（v3.1：extra 在 e.context.extra）
                kind = (
                    "budget_timeout"
                    if e.context.extra.get("reason_code")
                    == "xtdata_budget_zombie_risk"
                    else "marketdata_error"
                )
                failed_batches.append(
                    {
                        "batch_no": batch_no,
                        "stocks": batch,
                        "kind": kind,
                        "err": str(e),
                    }
                )
                timeout_stock_set.update(batch)
                logger.warning(
                    f"批 {batch_no} {kind}（{BATCH_TIMEOUT_SEC}s），{len(batch)} 只标记失败",
                    context={
                        "event": StreamObservabilityEvent.FASTPATH_READ_BATCH_TIMEOUT,
                        "batch_no": batch_no,
                        "kind": kind,
                        "stocks_head20": batch[:20],
                    },
                )
                time.sleep(0.5)  # 给 daemon orphan 退出窗口，降低下批并发风险
                continue
            except Exception as e:
                failed_batches.append(
                    {
                        "batch_no": batch_no,
                        "stocks": batch,
                        "kind": "sdk_exception",
                        "err": repr(e),
                    }
                )
                timeout_stock_set.update(batch)
                logger.warning(
                    f"批 {batch_no} SDK 异常: {e!r}",
                    context={
                        "event": StreamObservabilityEvent.FASTPATH_READ_BATCH_TIMEOUT,
                        "batch_no": batch_no,
                        "kind": "sdk_exception",
                    },
                )
                continue
        return DownloadOutcome(
            frames=batch_results,
            timeout_stock_set=timeout_stock_set,
            failed_batches=failed_batches,
        )

    def download(
        self,
        stock_list: List[str],
        start_time: str,
        end_time: str,
        *,
        period: str = "1d",
        adjust_type: str = "front",
        incrementally: bool = False,
        callback: Optional[Callable] = None,
        progress_log_interval_sec: Optional[float] = 10.0,
    ) -> Dict[str, pd.DataFrame]:
        """简单消费面（shadow/外部）：仅 frames；管线用 download_bulk。"""
        return self.download_bulk(
            stock_list, start_time, end_time,
            period=period, adjust_type=adjust_type, incrementally=incrementally,
            callback=callback,
            progress_log_interval_sec=progress_log_interval_sec,
        ).frames

    def read_frames(
        self,
        stock_list: List[str],
        *,
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        dividend_type: str = "none",
    ) -> Dict[str, pd.DataFrame]:
        from oskh_data.qmt_xtdata import get_xtdata

        xtdata = get_xtdata()
        data = xtdata.get_market_data_ex(
            [],
            list(stock_list),
            period=period,
            start_time=start_time,
            end_time=end_time,
            count=-1,
            dividend_type=dividend_type,
            fill_data=True,
        )
        return {str(k): v for k, v in (data or {}).items() if v is not None}

    def divid_factors(
        self, code: str, start_time: str = "", end_time: str = ""
    ) -> pd.DataFrame:
        from common.integrations.xtdata_call_budget import xtdata_call_with_budget_sync
        from oskh_data.qmt_xtdata import get_xtdata

        xtdata = get_xtdata()
        df = xtdata_call_with_budget_sync(
            lambda: xtdata.get_divid_factors(code, start_time, end_time),
            budget_s=DIVID_FACTORS_BUDGET_S,
            retries=DIVID_FACTORS_RETRIES,
        )
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


_DAQMT_TRANSPORT_FACTORY: Optional[Callable[[], "DailyBarsTransport"]] = None


def register_daqmt_transport_factory(
    factory: Callable[[], "DailyBarsTransport"],
) -> None:
    """oskh_core registers DaqmtShimTransport here.

    ``oskh_data`` must not import ``oskh_core`` (verify_oskh_data_contract
    ``_FORBIDDEN_ANYWHERE_IMPORTS``). The daqmt constructor lives in
    ``oskh_core.daqmt_download_transport`` and registers on import.
    """
    global _DAQMT_TRANSPORT_FACTORY
    _DAQMT_TRANSPORT_FACTORY = factory


def resolve_download_transport(backend: Optional[str] = None) -> DailyBarsTransport:
    """工厂（plan §3.2）。xtdata 在本包构造；daqmt 由 oskh_core 注册（分层 orthogonal）。"""
    resolved = (backend or resolve_download_backend()).strip()
    if resolved == "xtdata":
        return XtdataDownloadTransport()
    if resolved == "daqmt":
        factory = _DAQMT_TRANSPORT_FACTORY
        if factory is None:
            raise ConfigurationError(
                "OSKH_DAILY_DOWNLOAD_BACKEND=daqmt is owned by "
                "oskh_core.daqmt_download_transport (oskh_data must not import "
                "oskh_core). Import that module first so it can register the "
                "factory, or inject transport= into DataDownloader."
            )
        return factory()
    raise ConfigurationError(
        f"未知下载后端 {resolved!r}；合法值: {DOWNLOAD_BACKENDS}"
    )
