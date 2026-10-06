"""RB-10 static hook descriptions and engine import fence."""

import ast
import inspect
from collections.abc import Mapping
from typing import Any, get_type_hints, is_typeddict

from backtest.research import strategy_hooks_types
from backtest.research.strategy_hooks_types import StrategyApply, StrategyHooks


def test_strategy_hooks_is_optional_typed_dict():
    assert is_typeddict(StrategyHooks)
    assert StrategyHooks.__total__ is False
    assert StrategyHooks.__required_keys__ == frozenset()
    assert {"name", "sizing", "stop_pct", "take_profit", "record_params",
            "name_lot_budget", "name_budget", "allow_new_name", "add_step",
            "step_frac"} <= StrategyHooks.__optional_keys__


def test_subset_literal_remains_a_plain_mapping():
    # A contextual TypedDict literal demonstrates the static assignment shape.
    # No runtime cast, wrapper, validation, or coercion is needed.
    hooks: StrategyHooks = {"name": "example", "stop_pct": None}
    mapping: Mapping[str, Any] = hooks
    assert type(hooks) is dict
    assert mapping is hooks
    assert mapping == {"name": "example", "stop_pct": None}


def test_apply_protocol_accepts_plain_dict_return():
    def apply(**kwargs: Any) -> Mapping[str, Any]:
        return {"name": kwargs["name"], "legacy_extra": True}

    callback: StrategyApply = apply
    assert callback(name="example") == {"name": "example", "legacy_extra": True}
    assert get_type_hints(StrategyApply.__call__)["return"] == Mapping[str, Any]


def test_leaf_imports_only_standard_library_types_and_no_engines():
    tree = ast.parse(inspect.getsource(strategy_hooks_types))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            imports.append(node.module)
    assert imports == ["collections.abc", "typing"]
    assert not any(isinstance(node, ast.Call) for node in ast.walk(tree))
