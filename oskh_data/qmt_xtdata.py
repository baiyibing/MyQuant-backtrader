"""oskh_data-side xtdata access — no bare ``import xtquant``.

Layering: ``oskh_data`` depends on ``common`` only (not ``oskh_core``).
Vendor SDK entry is centralized in ``common.integrations.qmt_client._get_xtdata``
(same path used by ``XQuantDataIngestionAdapter``). G4 / residual-fence: replace
direct ``from xtquant import xtdata`` in oskh_data with this helper.

Bulk history download (get_market_data_ex / download_history_data2 /
get_divid_factors / get_financial_data / sector lists) has no daqmt shim
surface. When the vendor forbids xtdata.init, skip — do not enter mini
lifecycle and do not mix this package into the live trade chain
(no get_broker_trader here).
"""

from __future__ import annotations

from typing import Any, Optional, TextIO


def forbids_bulk_xtdata() -> bool:
    """True when configured vendor capability ``forbids_xtdata_init`` is set."""
    from common.integrations.vendor_capabilities import (
        resolve_configured_vendor,
        vendor_capability,
    )

    return vendor_capability(resolve_configured_vendor(), "forbids_xtdata_init") is True


def skip_bulk_xtdata_message() -> str:
    return "skip: vendor forbids_xtdata_init (no mini xtdata.init / bulk download on shim)"


def skip_if_forbids_xtdata_init(*, stream: Optional[TextIO] = None) -> bool:
    """Print skip line and return True when shim forbids mini xtdata lifecycle."""
    if not forbids_bulk_xtdata():
        return False
    import sys

    out = stream if stream is not None else sys.stdout
    print(skip_bulk_xtdata_message(), file=out)
    return True


def get_xtdata() -> Any:
    """Return the process xtdata module (lazy; respects mock routing)."""
    if forbids_bulk_xtdata():
        raise RuntimeError(skip_bulk_xtdata_message())
    from common.integrations.qmt_client import _get_xtdata

    return _get_xtdata()


def try_get_xtdata() -> Optional[Any]:
    """Like ``get_xtdata`` but returns None when xtquant / shim / entry is unavailable."""
    if forbids_bulk_xtdata():
        return None
    try:
        return get_xtdata()
    except Exception:
        return None


def ensure_xtdata_session() -> Any:
    """get_xtdata + best-effort init/connect/reconnect (Capital / financial download)."""
    if forbids_bulk_xtdata():
        raise RuntimeError(skip_bulk_xtdata_message())
    xtdata = get_xtdata()
    for name in ("init", "connect", "reconnect"):
        fn = getattr(xtdata, name, None)
        if callable(fn):
            fn()
            return xtdata
    raise RuntimeError("xtdata 无 init/connect/reconnect 方法，请确认 xtquant 已安装")
