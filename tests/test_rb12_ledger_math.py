"""Exact deterministic equivalence and dependency fence for RB-12."""
import ast
from itertools import product
from pathlib import Path

from backtest.research import ledger_math
from backtest.research.ashare_fees import trade_commission


def original_commission(notional, rate, min_cost=0.0):
    if notional <= 0 or rate < 0:
        return 0.0
    fee = float(notional) * float(rate)
    floor = float(min_cost)
    if floor > 0:
        return max(fee, floor)
    return fee


def test_exact_commission_grid():
    for qty, price, rate, floor in product(
        (0, 1, 99, 100, 101, 2801, 10**9),
        (0.0, 0.01, 1.23456789, 49.999999999, 10**6),
        (-0.001, -0.0, 0.0, 0.0005, 0.001, 0.0015),
        (-1.0, 0.0, 5.0, 1e6),
    ):
        notional = qty * price
        assert ledger_math.trade_commission(notional, rate, floor) == original_commission(notional, rate, floor)
    for notional in (-1.0, -0.0, 4999.999999, 5000.0, 5000.000001, float('inf')):
        assert ledger_math.trade_commission(notional, 0.001, 5.0) == original_commission(notional, 0.001, 5.0)
    assert trade_commission is ledger_math.trade_commission


def test_leaf_ast_fence_and_verbatim_body():
    tree = ast.parse(Path(ledger_math.__file__).read_text(encoding='utf-8'))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert all(isinstance(node, ast.ImportFrom) and node.module == '__future__' for node in imports)
    original = ast.parse(Path(__file__).read_text(encoding='utf-8'))
    old = next(node for node in original.body if isinstance(node, ast.FunctionDef) and node.name == 'original_commission')
    new = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    # The moved function retains its original docstring; arithmetic/control flow are identical.
    assert [ast.dump(node) for node in new.body[1:]] == [ast.dump(node) for node in old.body]
