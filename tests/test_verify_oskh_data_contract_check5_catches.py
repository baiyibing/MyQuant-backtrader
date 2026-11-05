"""Characterize contract check 5 through main(), without changing the gate.

S23: ``scripts/gates/verify_oskh_data_contract.py`` check 5 stays as it is.
The gate is loaded read-only. These tests pin current behavior.

Human open decision: whether check5 should block these; current gate ignores; do not invent a fix.
Ignored today: positional non-none, variable keywords, omitted keywords, and
non-constant values (``**`` unpack, concatenation, f-strings, attributes).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_GATE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts/gates/verify_oskh_data_contract.py"
)


def _load_gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "verify_oskh_data_contract_check5_catches_gate",
        _GATE_PATH,
    )
    if spec is None:
        raise RuntimeError(f"cannot load contract gate: {_GATE_PATH}")
    loader = spec.loader
    if loader is None:
        raise RuntimeError(f"contract gate has no loader: {_GATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _plant_boundary_stubs(root: Path) -> None:
    """Checks 1–4 stay clean: no forbidden imports, sqlite3, or download calls."""
    _write(root / "oskh_data" / "stub.py", "STUB = 1\n")
    _write(root / "backtest" / "stub.py", "STUB = 1\n")
    (root / "live_trading").mkdir(parents=True, exist_ok=True)
    (root / "trade_decision").mkdir(parents=True, exist_ok=True)


def _hot_path_errors(gate: ModuleType) -> list[str]:
    check = getattr(gate, "_check_adjust_type_hot_path")
    found = check()
    if not isinstance(found, list):
        raise AssertionError(f"check 5 returned {found!r}")
    errors: list[str] = []
    for item in found:
        if not isinstance(item, str):
            raise AssertionError(f"check 5 returned non-str {item!r}")
        errors.append(item)
    return errors


def _main_exit_code(gate: ModuleType) -> int:
    main = getattr(gate, "main")
    code = main()
    if not isinstance(code, int):
        raise AssertionError(f"main() returned {code!r}")
    return code


def _captured_text(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


def _assert_currently_ignored(
    gate: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Checker returns no errors and main() exits 0. Expected current behavior."""
    assert _hot_path_errors(gate) == []
    assert _main_exit_code(gate) == 0
    text = _captured_text(capsys)
    assert "oskh_data contract: OK" in text
    assert "must be 'none'" not in text


@pytest.fixture
def patched_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Redirect path globals so main() scans only this tmp tree."""
    gate = _load_gate()
    _plant_boundary_stubs(tmp_path)
    monkeypatch.setattr(gate, "_REPO", tmp_path)
    monkeypatch.setattr(gate, "_OSKH_DATA", tmp_path / "oskh_data")
    monkeypatch.setattr(gate, "_BACKTEST_DIR", tmp_path / "backtest")
    monkeypatch.setattr(
        gate,
        "_HOT_PATH_DIRS",
        (tmp_path / "live_trading", tmp_path / "trade_decision"),
    )
    return gate


def test_main_returns_1_for_live_trading_front_literal(
    patched_gate: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write(
        tmp_path / "live_trading" / "probe.py",
        "reader.read_stock(adjust_type='front')\n",
    )

    assert _main_exit_code(patched_gate) == 1
    text = _captured_text(capsys)
    assert "oskh_data contract violations (1)" in text
    assert "live_trading/probe.py" in text
    assert "adjust_type='front'" in text
    assert "must be 'none'" in text

    errors = _hot_path_errors(patched_gate)
    assert len(errors) == 1
    assert "live_trading/probe.py" in errors[0]
    assert "adjust_type='front'" in errors[0]
    assert "must be 'none'" in errors[0]


def test_main_returns_0_for_clean_tree(
    patched_gate: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write(
        tmp_path / "live_trading" / "probe.py",
        "reader.read_stock(adjust_type='none')\n",
    )
    _write(
        tmp_path / "trade_decision" / "probe.py",
        "stock_daily_bars(adjust='none')\n",
    )

    assert _hot_path_errors(patched_gate) == []
    assert _main_exit_code(patched_gate) == 0
    text = _captured_text(capsys)
    assert "oskh_data contract: OK" in text
    assert "violations" not in text


def test_main_reports_back_and_hfq_literals(
    patched_gate: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Catch is not front-only. Source uses double quotes for hfq; the report does not."""
    _write(
        tmp_path / "live_trading" / "probe.py",
        "stock_daily_bars(adjust='back')\n",
    )
    _write(
        tmp_path / "trade_decision" / "probe.py",
        'reader.read_stock(adjust_type="hfq")\n',
    )

    assert _main_exit_code(patched_gate) == 1
    text = _captured_text(capsys)
    assert "oskh_data contract violations (2)" in text
    assert "live_trading/probe.py" in text
    assert "adjust='back'" in text
    assert "trade_decision/probe.py" in text
    assert "adjust_type='hfq'" in text
    assert "must be 'none'" in text

    errors = _hot_path_errors(patched_gate)
    assert len(errors) == 2
    assert any("adjust='back'" in item and "must be 'none'" in item for item in errors)
    assert any("adjust_type='hfq'" in item and "must be 'none'" in item for item in errors)


def test_human_open_positional_non_none_is_not_reported(
    patched_gate: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Human open decision: whether check5 should block these; current gate ignores; do not invent a fix.
    # (a) positional non-none — read_stock(..., 'front') as the last positional — currently not reported.
    _write(
        tmp_path / "live_trading" / "probe.py",
        "reader.read_stock('600000.SH', None, None, '1d', 'front')\n",
    )
    _assert_currently_ignored(patched_gate, capsys)


def test_human_open_variable_keyword_is_not_reported(
    patched_gate: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Human open decision: whether check5 should block these; current gate ignores; do not invent a fix.
    # (b) variable keyword adjust_type=adj — currently not reported.
    _write(
        tmp_path / "live_trading" / "probe.py",
        "adj = 'front'\nreader.read_stock(adjust_type=adj)\n",
    )
    _assert_currently_ignored(patched_gate, capsys)


def test_human_open_omitted_keyword_is_not_reported(
    patched_gate: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Human open decision: whether check5 should block these; current gate ignores; do not invent a fix.
    # (c) absent/omitted adjust_type keyword — currently not reported.
    _write(
        tmp_path / "live_trading" / "probe.py",
        "reader.read_stock('600000.SH')\n",
    )
    _assert_currently_ignored(patched_gate, capsys)


def test_human_open_unpack_and_non_constant_are_not_reported(
    patched_gate: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Human open decision: whether check5 should block these; current gate ignores; do not invent a fix.
    # (d) **dict unpack (keyword arg is None) and non-Constant values
    # (BinOp, JoinedStr, Attribute) — currently not reported.
    _write(
        tmp_path / "live_trading" / "probe.py",
        "\n".join(
            (
                "opts = {'adjust_type': 'front'}",
                "reader.read_stock(**opts)",
                "reader.read_stock(**{'adjust_type': 'front'})",
                "reader.read_stock(adjust_type='fr' + 'ont')",
                "reader.read_stock(adjust_type=f'front')",
                "reader.read_stock(adjust_type=constants.FRONT)",
                "",
            )
        ),
    )
    _assert_currently_ignored(patched_gate, capsys)


def test_real_repo_main_returns_0(capsys: pytest.CaptureFixture[str]) -> None:
    gate = _load_gate()
    code = _main_exit_code(gate)
    text = _captured_text(capsys)
    assert code == 0, text
    assert "oskh_data contract: OK" in text
