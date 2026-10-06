"""Keep S8 binding and cash defaults aligned with explicit book admission."""
import ast
import inspect

import pytest

from backtest.research import csv_ledger
from backtest.research.csv_strategy_books import apply_csv_strategy, csv_strategy_names


@pytest.mark.parametrize('name', csv_strategy_names())
def test_registered_book_s8_cash_default(name):
    # TopK books require scores even though this guard only configures hooks.
    hooks = apply_csv_strategy(name, scores_by_day={'20251001': {'000001.SZ': 1.0}})
    hooks.pop('on_short_cash', None)
    st = csv_ledger.SimState()
    csv_ledger.configure_s8(st, hooks)
    bound = csv_ledger.s8_policy(st) is not None
    assert csv_ledger.uses_s8_independent(name, hooks['sizing']) == bound, (
        f'{name}: uses_s8_independent() disagrees with actual S8 binding'
    )
    expected = 'raise' if bound else 'skip'
    assert st.on_short_cash == expected, (
        f'{name} is S8-{ "bound" if bound else "unbound" } but on_short_cash '
        f'default is {st.on_short_cash}; bind path must resolve {expected} '
        f'when policy is {"set" if bound else "absent"}'
    )


@pytest.mark.parametrize('name,expected', [
    (None, False), ('', False), ('version6', False), ('version6_45', True),
    ('version6_999', False), ('version8', True), ('version8_1', False),
    ('version8_7', False), ('version9_1', False), ('version9_2', False),
    ('version12', False),
])
def test_explicit_admission_including_future_books(name, expected):
    assert csv_ledger.uses_s8_independent(name, 'per_name') is expected
    assert not csv_ledger.uses_s8_independent(name, None)
    assert not csv_ledger.uses_s8_independent(name, 'daily_quota')
    if expected:
        # Exercise the bind path too, without registering a new strategy book.
        hooks = {**apply_csv_strategy('version8'), 'name': name}
        st = csv_ledger.SimState()
        csv_ledger.configure_s8(st, hooks)
        assert csv_ledger.s8_policy(st) is not None
        assert st.on_short_cash == 'raise', (
            f'{name} is S8-bound but on_short_cash default is skip; '
            'bind path must resolve raise when policy is set'
        )


def test_no_hardcoded_version6_allowlist():
    tree = ast.parse(inspect.getsource(csv_ledger))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            count = sum(
                isinstance(item, ast.Constant) and isinstance(item.value, str)
                and item.value.startswith('version6_')
                for item in node.elts
            )
            assert count < 10, (
                'csv_ledger._configure_s8 still hardcodes a version6_* allowlist; '
                'use uses_s8_independent() instead'
            )
