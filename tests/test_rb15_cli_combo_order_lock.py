"""RB-15: literal errors and precedence at the existing run/apply boundaries."""
import pytest
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_strategy_books as books

CASES = [
    ({'max_hold': True}, ValueError, 'max_hold is supported only by version9'),
    ({'version9_sell': 'bad'}, ValueError, "version9_sell requires version9 and one of ('mean_tr3_tp10', 'range_amp_tp_amp', 'mean_tr2_or_prior10_low')"),
    ({'strategy': 'version9', 'version9_sell': 'mean_tr2_or_prior10_low', 'max_hold': True}, ValueError, 'mean_tr2_or_prior10_low rejects max_hold'),
    ({'participation_rate': 0.1, 'minute_source': 'qlib_1min'}, ValueError, 'participation_rate requires raw lake minute volume in shares'),
    ({'participation_rate': 0.1, 'tail_window_buy': True, 'tail_volume_unit': 'lots'}, ValueError, 'participation_rate requires shares, not tail volume lots'),
    ({'fix_s81_band_precision': True}, ValueError, 'fix_s81_band_precision is supported only by version8_1'),
    ({'minute_stop_trigger': 'bad'}, ValueError, '--minute-stop-trigger must be hl or close'),
    ({'strategy': 'version12', 'minute_stop_trigger': 'hl'}, ValueError, '--minute-stop-trigger hl rejects version12 and --fix-s11-exit-domain'),
    ({'topk_limit_rule': 'bad'}, ValueError, "unknown --topk-limit-rule 'bad'; choose qlib or real"),
    ({'topk_exec': 'bad'}, ValueError, "unknown --topk-exec 'bad'; choose close, open, intraday or vwap"),
    ({'topk_exec': 'vwap', 'limit_walkdown': True}, ValueError, '--topk-exec vwap x --limit-walkdown is refused'),
    ({'topk_exec': 'open'}, ValueError, '--topk-exec open/intraday/vwap, --limit-walkdown and --topk-limit-rule real apply only to topk_dropout'),
    ({'tail_window_buy': True}, ValueError, '--tail-window-buy requires --fix-minute-cash-order'),
    ({'tail_window_buy': True, 'fix_minute_cash_order': True, 'tail_volume_unit': 'bad'}, ValueError, 'tail volume unit (--tail-volume-unit) must be shares or lots'),
    ({'tail_window_buy': True, 'fix_minute_cash_order': True}, ValueError, '--tail-window-buy applies only to version8 / version8.x in the shared entry'),
    ({'strategy': 'version8', 'tail_window_buy': True, 'fix_minute_cash_order': True, 'daily_source': 'qlib'}, ValueError, '--tail-window-buy requires raw lake minute and daily data'),
    ({'fix_s11_exit_domain': True}, ValueError, 'fix_s11_exit_domain is supported only by version11'),
    ({'strategy': 'version11', 'fix_s11_exit_domain': True, 'daily_source': 'qlib'}, ValueError, 'fix_s11_exit_domain requires raw lake execution + independent lake front'),
    ({'stop_fill': ' CLOSE '}, SystemExit, '--stop-fill close is daily EOD close only; minute entry refuses it (bar close is not 当日收盘)'),
    ({'fix_s12_price_domain': True}, ValueError, '--fix-s12-price-domain requires version12 + lake/lake + --dividend-type none'),
    ({'s12_price_transform_file': 'unused'}, ValueError, '--s12-price-transform-file requires --fix-s12-price-domain'),
    ({'strategy': 'version9_1', 'fix_minute_cash_order': True}, ValueError, '--fix-minute-cash-order is not applicable to version9_1'),
    ({'strategy': 'version12', 'audit_sink': True}, ValueError, 'X-02 execution audit is not applicable to version12'),
    ({'strategy': 'version12', 'daily_source': 'qlib'}, ValueError, 'version12 minute requires lake daily/minute and --dividend-type none|front'),
    ({'dividend_type': 'front'}, ValueError, 'minute --dividend-type front is supported only by version12'),
    ({'strategy': 'version11', 'minute_source': 'qlib_1min'}, ValueError, 'version11 requires lake minute volume; qlib_1min frames do not carry it'),
 ]

@pytest.mark.parametrize("overrides,kind,message", CASES)
def test_run_errors(overrides, kind, message):
    kwargs = {"strategy": "version6", **overrides}
    with pytest.raises(kind) as caught:
        minute.run("20260101", "20260102", **kwargs)
    assert type(caught.value) is kind
    assert str(caught.value) == message

# Every adjacent rejection locks precedence, including nested validator blocks.
@pytest.mark.parametrize("index", range(len(CASES) - 1))
def test_run_error_order(index):
    first, kind, message = CASES[index]
    second = CASES[index + 1][0]
    combined = {"strategy": "version6", **second, **first}
    if index == 0:
        message = CASES[1][2]  # sell-mode validation precedes max_hold
    if index == 12:
        combined["fix_minute_cash_order"] = False
    if index in (14, 16):
        combined["strategy"] = "version6"
    # Explicit selectors retain both incompatible predicates where possible.
    with pytest.raises(kind) as caught:
        minute.run("20260101", "20260102", **{"strategy": "version6", **combined})
    assert type(caught.value) is kind
    assert str(caught.value) == message

class ValidationPassed(Exception):
    pass

@pytest.mark.parametrize("overrides", [
    {}, {"strategy": "version8_1", "fix_s81_band_precision": True},
    {"strategy": "version8", "tail_window_buy": True, "fix_minute_cash_order": True},
    {"strategy": "topk_dropout", "topk_exec": "vwap"},
    {"strategy": "version12", "dividend_type": "front"},
    {"strategy": "version11", "fix_s11_exit_domain": True},
])
def test_valid_run_reaches_pool_resolution(monkeypatch, overrides):
    def reached(*args, **kwargs):
        raise ValidationPassed
    monkeypatch.setattr(minute, "resolve_research_pool_dir", reached)
    with pytest.raises(ValidationPassed):
        minute.run("20260101", "20260102", **{"strategy": "version6", **overrides})

@pytest.mark.parametrize("overrides,message", [
    ({"version9_sell": "bad", "fix_s81_band_precision": True}, CASES[1][2]),
    ({"fix_s81_band_precision": True, "ration_seed": "bad"}, CASES[5][2]),
])
def test_apply_error_order(overrides, message):
    with pytest.raises(ValueError) as caught:
        books.apply_csv_strategy("version6", **overrides)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message

@pytest.mark.parametrize("strategy,kwargs", [("version6", {}), ("version8_1", {"fix_s81_band_precision": True}), ("version9", {"version9_sell": "mean_tr3_tp10"})])
def test_valid_apply(strategy, kwargs):
    assert books.apply_csv_strategy(strategy, **kwargs)["name"] == strategy

@pytest.mark.parametrize("rate", [-.1, 1.1, float("nan"), float("inf")])
def test_rate_precedes_source_and_band(rate):
    with pytest.raises(ValueError) as caught:
        minute.run("20260101", "20260102", strategy="version6",
                   participation_rate=rate, minute_source="qlib_1min",
                   fix_s81_band_precision=True)
    assert type(caught.value) is ValueError
    assert str(caught.value) == "participation_rate must be finite and in [0, 1]"

@pytest.mark.parametrize("flags,message", [
    (["--topk-exec", "bad"], "unknown --topk-exec 'bad'; choose close, open, intraday or vwap"),
    (["--topk-exec", "open"], CASES[11][2]),
    (["--strategy", "version12", "--minute-stop-trigger", "hl", "--topk-exec", "open"], CASES[7][2]),
])
def test_argparse_errors_and_order(capsys, flags, message):
    with pytest.raises(SystemExit) as caught:
        minute.main(["--strategy", "version6", "--start", "20260101", "--end", "20260102", *flags])
    assert type(caught.value) is SystemExit
    assert caught.value.code == 2
    assert message in capsys.readouterr().err
