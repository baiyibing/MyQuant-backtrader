"""BT keeps failure policy; calendar coverage and date queries belong to infra."""
from datetime import date, datetime
from unittest.mock import Mock

import pytest
from myquant_infra.reference_data.calendar import CalendarBuildError, SSECalendar

from common.infra import trading_calendar_pmc as host


@pytest.fixture(autouse=True)
def calendar_state(monkeypatch):
    host.invalidate_sse_cache()
    monkeypatch.setattr(host, "shanghai_now", lambda: datetime(2026, 1, 4))
    yield
    host.invalidate_sse_cache()


def test_covered_holiday_and_uncovered_range_are_distinct(monkeypatch):
    provider = Mock()
    provider.valid_days.return_value = [date(2026, 1, 2), date(2026, 1, 5)]
    calendar = SSECalendar(start="20260101", end="20260106", provider=provider)
    monkeypatch.setattr(host, "_SSE_CALENDAR", calendar)
    monkeypatch.setattr(host, "_SSE_CACHE_BUILD_YEAR", 2026)
    assert host.get_trade_days_sse(since="20260103", until="20260104").empty
    assert host.get_trade_days_sse(since="20260102", until="20260105")["cal_date"].tolist() == [
        "20260102", "20260105",
    ]
    assert host.get_trade_days_sse(since="20251231", until="20260102") is None
    provider.valid_days.assert_called_once()


def test_provider_failure_stays_disabled_until_host_reset(monkeypatch):
    query = Mock(side_effect=CalendarBuildError("provider unavailable"))
    monkeypatch.setattr(host, "_query", query)
    assert host.get_trade_days_sse(since="20260101", until="20260105") is None
    assert host.get_trade_days_sse(since="20260101", until="20260105") is None
    query.assert_called_once()
    host.invalidate_sse_cache()
    assert host.get_trade_days_sse(since="20260101", until="20260105") is None
    assert query.call_count == 2
