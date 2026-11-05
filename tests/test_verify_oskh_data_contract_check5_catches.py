"""Check 5 reports non-literal, omitted, unpacked, and positional adjust forms.

Positional indexes are pinned to the real signatures (bound call, ``self``
excluded):

* ``StockDataReader.read_stock`` — ``adjust_type`` is index 4 (default ``front``)
* ``DuckDBDailyBarsProxy.stock_daily_bars`` / ``stock_daily_bars_cfg_only`` —
  ``adjust`` is keyword-only (default ``none``); a positional does not occupy it
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_gate() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/gates/verify_oskh_data_contract.py"
    spec = importlib.util.spec_from_file_location("verify_oskh_data_contract_check5", path)
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


def _find_method(path: Path, class_name: str, func_name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == func_name:
                return item
    raise AssertionError(f"{class_name}.{func_name} not found in {path}")


def _bound_positional_index(func: ast.FunctionDef, param: str) -> int | None:
    positional = [arg.arg for arg in func.args.posonlyargs]
    positional.extend(arg.arg for arg in func.args.args)
    if positional and positional[0] == "self":
        positional = positional[1:]
    if param in positional:
        return positional.index(param)
    if param in {arg.arg for arg in func.args.kwonlyargs}:
        return None
    raise AssertionError(f"{param} is not a parameter of {func.name}")


def _default_for(func: ast.FunctionDef, param: str) -> ast.expr | None:
    positional = list(func.args.posonlyargs) + list(func.args.args)
    offset = len(positional) - len(func.args.defaults)
    for index, arg in enumerate(positional):
        if arg.arg != param:
            continue
        default_index = index - offset
        if default_index < 0:
            return None
        return func.args.defaults[default_index]
    for arg, default in zip(func.args.kwonlyargs, func.args.kw_defaults, strict=True):
        if arg.arg == param:
            return default
    raise AssertionError(param)


def test_positional_indexes_match_real_signatures() -> None:
    gate = _load_gate()
    repo = gate._REPO
    specs = (
        (
            "read_stock",
            repo / "oskh_data/reader.py",
            "StockDataReader",
            "read_stock",
            "adjust_type",
            "front",
        ),
        (
            "stock_daily_bars",
            repo / "common/integrations/duckdb_daily_bars_adapter.py",
            "DuckDBDailyBarsProxy",
            "stock_daily_bars",
            "adjust",
            "none",
        ),
        (
            "stock_daily_bars_cfg_only",
            repo / "common/integrations/duckdb_daily_bars_adapter.py",
            "DuckDBDailyBarsProxy",
            "stock_daily_bars_cfg_only",
            "adjust",
            "none",
        ),
    )
    indexes = {name: index for name, _kw, index in gate._ADJUST_KEYWORD_TARGETS}
    for call_name, path, class_name, func_name, param, default in specs:
        func = _find_method(path, class_name, func_name)
        assert indexes[call_name] == _bound_positional_index(func, param)
        default_node = _default_for(func, param)
        assert isinstance(default_node, ast.Constant)
        assert default_node.value == default


def test_read_stock_index_is_adjust_slot_not_neighbors(gate: ModuleType, tmp_path: Path) -> None:
    """Index 4 is adjust_type. Period (index 3) and columns (index 5) are not."""
    relative = "trade_decision/probe.py"
    _write_source(
        tmp_path / relative,
        "\n".join(
            [
                # 'front' sits in period; adjust_type is omitted.
                "reader.read_stock('600000.SH', None, None, 'front')",
                # 'none' is adjust_type; the following string is columns.
                "reader.read_stock('600000.SH', None, None, '1d', 'none', 'close')",
                # index 3 is a non-none period, index 4 is the literal none.
                "reader.read_stock('600000.SH', None, None, 'front', 'none')",
            ]
        )
        + "\n",
    )
    errors = gate._check_adjust_type_hot_path()
    assert len(errors) == 1
    assert "omitted adjust_type (defaults may be non-none)" in errors[0]
    assert "positional" not in errors[0]


def test_keyword_only_adjust_positional_is_omitted_not_positional(
    gate: ModuleType, tmp_path: Path
) -> None:
    relative = "live_trading/probe.py"
    _write_source(
        tmp_path / relative,
        "stock_daily_bars('600000.SH', '20200101', '20200102', 'front')\n"
        "adapter.stock_daily_bars_cfg_only("
        "'600000.SH', '20200101', '20200102', 'back')\n",
    )
    errors = gate._check_adjust_type_hot_path()
    assert len(errors) == 2
    assert all("positional" not in error for error in errors)
    assert all("omitted adjust (defaults may be non-none)" in error for error in errors)
    assert {error.split(":", 1)[0] for error in errors} == {relative}


@pytest.mark.parametrize(
    ("call", "snippet"),
    [
        ("reader.read_stock(adjust_type=mode)", "non-literal adjust_type —"),
        ("reader.read_stock(adjust_type=mode.front)", "non-literal adjust_type —"),
        ('reader.read_stock(adjust_type="fr" + "ont")', "non-literal adjust_type —"),
        ('reader.read_stock(adjust_type=f"front")', "non-literal adjust_type —"),
        ("reader.read_stock(adjust_type=None)", "non-literal adjust_type —"),
        ("stock_daily_bars(adjust=obj.attr)", "non-literal adjust —"),
        ('adapter.stock_daily_bars_cfg_only(adjust="no" + "ne")', "non-literal adjust —"),
    ],
    ids=["name", "attribute", "binop", "joinedstr", "none-constant", "daily-attr", "cfg-binop"],
)
def test_non_literal_keyword_values_are_reported(
    gate: ModuleType, tmp_path: Path, call: str, snippet: str
) -> None:
    relative = "trade_decision/probe.py"
    _write_source(tmp_path / relative, f"mode = 'front'\n{call}\n")
    errors = gate._check_adjust_type_hot_path()
    assert len(errors) == 1
    assert relative in errors[0]
    assert snippet in errors[0]
    assert "unpacked keywords" not in errors[0]
    assert "omitted" not in errors[0]


def test_unpacked_keywords_are_reported(gate: ModuleType, tmp_path: Path) -> None:
    relative = "trade_decision/probe.py"
    _write_source(
        tmp_path / relative,
        "reader.read_stock(**kw)\nstock_daily_bars(**{'adjust': 'none'})\n",
    )
    errors = gate._check_adjust_type_hot_path()
    unpack = [error for error in errors if "unpacked keywords may set non-literal" in error]
    omitted = [error for error in errors if "omitted" in error]
    assert len(unpack) == 2
    assert omitted == []
    assert len(errors) == 2
    assert any("unpacked keywords may set non-literal adjust_type" in error for error in unpack)
    assert any("unpacked keywords may set non-literal adjust —" in error for error in unpack)


def test_explicit_none_plus_unpack_reports_only_unpack(gate: ModuleType, tmp_path: Path) -> None:
    relative = "live_trading/probe.py"
    _write_source(
        tmp_path / relative,
        "reader.read_stock(adjust_type='none', **kw)\nstock_daily_bars(**kw, adjust='none')\n",
    )
    errors = gate._check_adjust_type_hot_path()
    assert len(errors) == 2
    assert all("unpacked keywords may set non-literal" in error for error in errors)
    assert all("omitted" not in error for error in errors)
    assert all("='front'" not in error for error in errors)


def test_bad_literal_plus_unpack_reports_both(gate: ModuleType, tmp_path: Path) -> None:
    relative = "trade_decision/probe.py"
    _write_source(tmp_path / relative, "reader.read_stock(adjust_type='front', **kw)\n")
    errors = gate._check_adjust_type_hot_path()
    assert len(errors) == 2
    assert any("adjust_type='front'" in error for error in errors)
    assert any("unpacked keywords may set non-literal adjust_type" in error for error in errors)


def test_starred_args_hide_read_stock_adjust_slot(gate: ModuleType, tmp_path: Path) -> None:
    relative = "trade_decision/probe.py"
    _write_source(
        tmp_path / relative,
        "\n".join(
            [
                "reader.read_stock(*args)",
                "reader.read_stock(code, start, end, period, *rest, 'front')",
                "reader.read_stock(code, start, end, period, 'none', *rest)",
                "reader.read_stock(*args, adjust_type='none')",
            ]
        )
        + "\n",
    )
    errors = gate._check_adjust_type_hot_path()
    assert len(errors) == 2
    assert all("positional non-literal adjust_type" in error for error in errors)


def test_positional_non_literal_name_is_reported(gate: ModuleType, tmp_path: Path) -> None:
    relative = "trade_decision/probe.py"
    _write_source(
        tmp_path / relative,
        "reader.read_stock('600000.SH', None, None, '1d', mode)\n",
    )
    errors = gate._check_adjust_type_hot_path()
    assert len(errors) == 1
    assert "positional non-literal adjust_type" in errors[0]


def test_wrong_keyword_name_does_not_satisfy_the_signature(
    gate: ModuleType, tmp_path: Path
) -> None:
    relative = "trade_decision/probe.py"
    _write_source(
        tmp_path / relative,
        "reader.read_stock(adjust='none')\nstock_daily_bars(adjust_type='none')\n",
    )
    errors = gate._check_adjust_type_hot_path()
    assert len(errors) == 2
    joined = "\n".join(errors)
    assert "omitted adjust_type (defaults may be non-none)" in joined
    assert "omitted adjust (defaults may be non-none)" in joined


def test_parenthesized_none_literal_is_allowed(gate: ModuleType, tmp_path: Path) -> None:
    _write_source(
        tmp_path / "trade_decision/probe.py",
        'reader.read_stock(adjust_type=("none"))\n'
        'stock_daily_bars(symbol="600000.SH", adjust="none")\n',
    )
    assert gate._check_adjust_type_hot_path() == []


def test_scan_dirs_stay_live_trading_and_trade_decision() -> None:
    gate = _load_gate()
    relatives = {path.relative_to(gate._REPO).as_posix() for path in gate._HOT_PATH_DIRS}
    assert relatives == {"live_trading", "trade_decision"}
