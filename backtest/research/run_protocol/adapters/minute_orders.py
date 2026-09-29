"""Explicit L2 research delegation; native runner and writer remain owners."""

from __future__ import annotations

from ..types import ApiResult, NativeApiRequest


def run_minute_orders_research(request: NativeApiRequest) -> ApiResult:
    from backtest.research.minute_orders_backend import runner as native

    value = native.run_minute_orders_research(*request.args, **request.kwargs)
    return ApiResult(request=request, native_value=value)


def run_minute_orders_research_with_artifacts(request: NativeApiRequest) -> ApiResult:
    from backtest.research.minute_orders_backend import runner as native

    value = native.run_minute_orders_research_with_artifacts(*request.args, **request.kwargs)
    # The native wrapper returns the root for both completed and failed evidence.
    # A returned envelope does not turn its native status into success.
    return ApiResult(request=request, native_value=value, native_artifact_refs=(value.root,))
