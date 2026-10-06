from __future__ import annotations

import argparse
import json
from dataclasses import FrozenInstanceError, asdict
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research.csv_artifacts import summarize, write_run_artifacts
from backtest.research.csv_strategy_books import add_csv_backtest_common_args
from backtest.research.rule_profile import (
    INDUSTRY,
    LEGACY,
    RuleProfile,
    resolve_rule_profile,
)

SYMBOL = "600000.SH"


def test_resolve_rule_profile_and_frozen_switches():
    assert resolve_rule_profile("legacy") is LEGACY
    assert resolve_rule_profile("industry") is INDUSTRY
    assert resolve_rule_profile(INDUSTRY) is INDUSTRY
    switches = {
        key: value
        for key, value in asdict(INDUSTRY).items()
        if key not in {"name", "revision", "slippage_bp"}
    }
    assert switches and not any(switches.values())
    assert LEGACY.slippage_bp == INDUSTRY.slippage_bp == 0
    assert INDUSTRY.revision == "industry-p01-20261006"
    with pytest.raises(FrozenInstanceError):
        INDUSTRY.account_fee_schedule = True
    with pytest.raises(ValueError, match="legacy.*industry.*RuleProfile"):
        resolve_rule_profile("unknown")
    with pytest.raises(ValueError, match="got 7"):
        resolve_rule_profile(7)  # type: ignore[arg-type]


def _common_parser(repo: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    add_csv_backtest_common_args(
        parser,
        repo=repo,
        end_default="20261006",
        cash_total_default=21_000_000,
        daily_quota_default=1_000_000,
    )
    return parser


@pytest.mark.parametrize("entry", ["daily", "minute"])
def test_shared_csv_cli_rule_profile_default_choices_and_invalid(tmp_path, entry):
    parser = _common_parser(tmp_path)
    base = ["--strategy", "version6"]
    assert parser.parse_args(base).rule_profile == "legacy"
    assert parser.parse_args([*base, "--rule-profile", "legacy"]).rule_profile == "legacy"
    assert parser.parse_args([*base, "--rule-profile", "industry"]).rule_profile == "industry"
    with pytest.raises(SystemExit) as raised:
        parser.parse_args([*base, "--rule-profile", "other"])
    assert raised.value.code == 2


def test_v7_cli_rule_profile_default_choices_and_invalid(tmp_path):
    parser = v7.build_parser()
    base = [
        "--start",
        "20260901",
        "--end",
        "20260902",
        "--pool-dir",
        str(tmp_path),
    ]
    assert parser.parse_args(base).rule_profile == "legacy"
    assert parser.parse_args([*base, "--rule-profile", "legacy"]).rule_profile == "legacy"
    assert parser.parse_args([*base, "--rule-profile", "industry"]).rule_profile == "industry"
    with pytest.raises(SystemExit) as raised:
        parser.parse_args([*base, "--rule-profile", "other"])
    assert raised.value.code == 2


def _daily_case(rule_profile: str | RuleProfile = "legacy"):
    index = pd.to_datetime(["2025-10-31", "2025-11-03", "2025-11-04"])
    bars = {
        SYMBOL: pd.DataFrame(
            {
                "open": [10.0, 10.0, 9.4],
                "high": [10.0, 10.1, 9.5],
                "low": [10.0, 9.9, 9.3],
                "close": [10.0, 10.0, 9.4],
            },
            index=index,
        )
    }
    return daily.simulate(
        bars,
        {"20251103": [SYMBOL]},
        "20251103",
        "20251104",
        strategy="version6",
        stop_pct=0.02,
        rule_profile=rule_profile,
    )


def _minute_case(rule_profile: str | RuleProfile = "legacy"):
    minute_index = pd.to_datetime(
        ["2025-11-03 14:55:00", "2025-11-04 09:30:00", "2025-11-04 14:55:00"]
    )
    minute_bars = {
        SYMBOL: pd.DataFrame(
            {
                "open": [10.0, 9.4, 9.4],
                "high": [10.0, 9.5, 9.5],
                "low": [10.0, 9.3, 9.3],
                "close": [10.0, 9.4, 9.4],
                "ymd": ["20251103", "20251104", "20251104"],
                "hm": [895, 570, 895],
            },
            index=minute_index,
        )
    }
    daily_bars = {
        SYMBOL: pd.DataFrame(
            {"close": [10.0, 10.0, 9.4]},
            index=pd.to_datetime(["2025-10-31", "2025-11-03", "2025-11-04"]),
        )
    }
    return minute.simulate(
        minute_bars,
        daily_bars,
        {"20251103": [SYMBOL]},
        "20251103",
        "20251104",
        strategy="version6",
        stop_pct=0.02,
        rule_profile=rule_profile,
    )


def _v7_case(rule_profile: str | RuleProfile = "legacy"):
    d1, d2 = date(2026, 9, 1), date(2026, 9, 2)

    def bar(day, hm, close):
        return {
            "date": day,
            "hm": hm,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
        }

    return v7.simulate_v7(
        {SYMBOL: [bar(d1, 895, 100), bar(d2, 570, 89)]},
        {SYMBOL: {date(2026, 8, 31): 100, d1: 98}},
        {d1: [SYMBOL]},
        [d1, d2],
        rule_profile=rule_profile,
    )


def _write_shared(state, root: Path, engine: str):
    text = summarize(state, 21_000_000, "20251103", "20251104", engine=engine)
    write_run_artifacts(root, state, text, "LOCK")


@pytest.mark.parametrize(
    ("engine", "factory", "writer"),
    [
        ("daily", _daily_case, lambda state, root: _write_shared(state, root, "daily")),
        ("minute", _minute_case, lambda state, root: _write_shared(state, root, "minute")),
        ("v7", _v7_case, v7.write_run_artifacts),
    ],
)
def test_legacy_omitted_and_explicit_are_byte_identical_and_industry_is_stats_only(
    tmp_path, engine, factory, writer
):
    omitted = factory()
    explicit = factory("legacy")
    industry = factory("industry")

    omitted_dir = tmp_path / engine / "omitted"
    explicit_dir = tmp_path / engine / "explicit"
    industry_dir = tmp_path / engine / "industry"
    writer(omitted, omitted_dir)
    writer(explicit, explicit_dir)
    writer(industry, industry_dir)

    filenames = ("summary.txt", "daily_equity.csv", "trades.csv")
    for filename in filenames:
        assert (omitted_dir / filename).read_bytes() == (explicit_dir / filename).read_bytes()
        assert (omitted_dir / filename).read_bytes() == (industry_dir / filename).read_bytes()

    assert omitted.trades
    assert any(str(row["side"]).lower() == "buy" for row in omitted.trades)
    assert any(str(row["side"]).lower() == "sell" for row in omitted.trades)
    omitted_stats = getattr(omitted, "stats", {})
    explicit_stats = getattr(explicit, "stats", {})
    assert "rule_profile" not in omitted_stats
    assert "rule_profile_revision" not in explicit_stats
    assert industry.stats == {
        **omitted_stats,
        "rule_profile": "industry",
        "rule_profile_revision": INDUSTRY.revision,
    }


def test_profile_keys_do_not_change_run_manifest_config(tmp_path):
    state = _daily_case("industry")
    text = summarize(state, 21_000_000, "20251103", "20251104", engine="daily")
    base_config = {"strategy": "version6", "dividend_type": "none"}
    hashes = []
    for name, config in (
        ("base", base_config),
        (
            "profile",
            {
                **base_config,
                "rule_profile": "industry",
                "rule_profile_revision": INDUSTRY.revision,
            },
        ),
    ):
        output = tmp_path / name
        write_run_artifacts(
            output,
            state,
            text,
            "LOCK",
            emit_run_manifest=True,
            manifest_config=config,
        )
        manifest = json.loads((output / "run-manifest.json").read_text(encoding="utf-8"))
        hashes.append(manifest["config_sha256"])
    assert hashes[0] == hashes[1]
