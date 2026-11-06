"""Characterize contract check 5 using synthetic source, without market data."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_gate() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/gates/verify_oskh_data_contract.py"
    spec = importlib.util.spec_from_file_location("verify_oskh_data_contract", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = _load_gate()
    hot_dirs = tuple(
        tmp_path / directory.relative_to(module._REPO) for directory in module._HOT_PATH_DIRS
    )
    monkeypatch.setattr(module, "_REPO", tmp_path)
    monkeypatch.setattr(module, "_HOT_PATH_DIRS", hot_dirs)
    return module


def _write_source(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


@pytest.mark.parametrize("hot_dir", ["live_trading", "trade_decision"])
@pytest.mark.parametrize(
    ("call", "keyword"),
    [
        ("reader.read_stock", "adjust_type"),
        ("stock_daily_bars", "adjust"),
        ("adapter.stock_daily_bars_cfg_only", "adjust"),
    ],
)
@pytest.mark.parametrize(
    ("argument", "expected_snippet"),
    [
        ("{keyword}='front'", "{keyword}='front'"),
        ("{keyword}='none'", None),
        ("", "omitted {keyword} (defaults may be non-none)"),
        ("{keyword}=mode", "non-literal {keyword} —"),
    ],
    ids=["front", "none", "omitted", "variable"],
)
def test_hot_path_adjust_keyword(
    gate: ModuleType,
    tmp_path: Path,
    hot_dir: str,
    call: str,
    keyword: str,
    argument: str,
    expected_snippet: str | None,
) -> None:
    relative = f"{hot_dir}/probe.py"
    _write_source(
        tmp_path / relative,
        f"mode = 'front'\n{call}({argument.format(keyword=keyword)})\n",
    )

    errors = gate._check_adjust_type_hot_path()

    if expected_snippet is not None:
        assert len(errors) == 1
        assert relative in errors[0]
        assert expected_snippet.format(keyword=keyword) in errors[0]
        assert "adjust_type must be 'none'" in errors[0]
    else:
        assert errors == []


def test_positional_non_none_adjust_type_is_reported(gate: ModuleType, tmp_path: Path) -> None:
    # Bound-call index 4 is adjust_type on StockDataReader.read_stock.
    relative = "trade_decision/probe.py"
    _write_source(
        tmp_path / relative,
        "reader.read_stock('600000.SH', None, None, '1d', 'front')\n",
    )
    errors = gate._check_adjust_type_hot_path()
    assert len(errors) == 1
    assert relative in errors[0]
    assert "positional adjust_type='front'" in errors[0]
    assert "adjust_type must be 'none'" in errors[0]


def test_positional_none_adjust_type_is_allowed(gate: ModuleType, tmp_path: Path) -> None:
    _write_source(
        tmp_path / "trade_decision/probe.py",
        "reader.read_stock('600000.SH', None, None, '1d', 'none')\n",
    )
    assert gate._check_adjust_type_hot_path() == []


def test_non_hot_path_is_not_checked(gate: ModuleType, tmp_path: Path) -> None:
    _write_source(
        tmp_path / "research/probe.py",
        "\n".join(
            [
                "reader.read_stock(adjust_type='front')",
                "reader.read_stock()",
                "reader.read_stock(adjust_type=mode)",
                "reader.read_stock(**kw)",
                "reader.read_stock('600000.SH', None, None, '1d', 'front')",
                "stock_daily_bars(adjust='front')",
            ]
        )
        + "\n",
    )
    assert gate._check_adjust_type_hot_path() == []


def test_allowlisted_module_is_not_reported(gate: ModuleType, tmp_path: Path) -> None:
    relative = "live_trading/indicators/ma_provider.py"
    assert relative in gate._ADJUST_TYPE_WHITELIST
    _write_source(
        tmp_path / relative,
        "\n".join(
            [
                "reader.read_stock(adjust_type='front')",
                "reader.read_stock()",
                "reader.read_stock(adjust_type=mode)",
                "reader.read_stock(**kw)",
                "reader.read_stock('600000.SH', None, None, '1d', 'front')",
                "stock_daily_bars()",
            ]
        )
        + "\n",
    )
    assert gate._check_adjust_type_hot_path() == []


def test_real_repo_hot_path_is_clean() -> None:
    assert _load_gate()._check_adjust_type_hot_path() == []
