"""G5 contract evidence only: source keys plus a toy, not a replay/pack test."""

import ast
from copy import deepcopy
from itertools import permutations
from pathlib import Path

import pytest


REPLAY = Path(__file__).resolve().parents[1] / "backtest/research/joint_return_replay.py"
CURRENT_KEY = 'lambda x: (x["intent"]["side"] != "SELL", x["intent"]["intent_id"])'


@pytest.fixture(params=["arrivals.get(t, [])", "eligible"], ids=["activation", "fills"])
def current_key(request):
    """Pin and evaluate only the existing lambda; never import the replay module."""
    tree = ast.parse(REPLAY.read_text(encoding="utf-8"))
    replay_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_Replay")
    run = next(n for n in replay_class.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    calls = [n for n in ast.walk(run) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "sorted"
             and ast.unparse(n.args[0]) == request.param]
    assert len(calls) == 1
    key = next(k.value for k in calls[0].keywords if k.arg == "key")
    assert ast.dump(key) == ast.dump(ast.parse(CURRENT_KEY, mode="eval").body)
    return eval(compile(ast.Expression(body=key), str(REPLAY), "eval"), {"__builtins__": {}})


def order(instrument, intent_id, side="BUY"):
    # Deliberately incomplete intents: these are key examples, not valid sealed packs.
    return {"intent": {"instrument": instrument, "intent_id": intent_id,
                       "side": side, "original_target_quantity": 200}}


def lineage_pair():
    original = [order("A", "1" * 64), order("B", "e" * 64)]
    regenerated = deepcopy(original)
    regenerated[0]["intent"]["intent_id"] = "f" * 64
    regenerated[1]["intent"]["intent_id"] = "0" * 64
    return original, regenerated


def toy_cash_split(rows, key):
    """One minute, cash 3000, price 10, 100-share lots, no fee, ample capacity."""
    cash = 3000
    fills = {}
    for row in sorted(rows, key=key):
        intent = row["intent"]
        quantity = min(intent["original_target_quantity"], cash // 1000 * 100)
        fills[intent["instrument"]] = quantity
        cash -= quantity * 10
    return fills


def test_current_sell_first_then_lexical_intent_id(current_key):
    rows = [order("A", "0" * 64), order("Z", "e" * 64, "SELL"),
            order("B", "1" * 64, "SELL"), order("Z", "1" * 64)]
    expected = [rows[2], rows[1], rows[0], rows[3]]
    for permutation in permutations(rows):
        assert sorted(permutation, key=current_key) == expected


def test_current_buy_order_ignores_instrument_priority(current_key):
    # Input sort_intents would put A before Z at equal arm/decision/side.
    rows = [order("A", "f" * 64), order("Z", "0" * 64)]
    assert sorted(rows, key=current_key) == rows[::-1]


def test_only_lineage_ids_change_current_toy_cash_split(current_key):
    original, regenerated = lineage_pair()
    economic = lambda rows: [{k: v for k, v in row["intent"].items() if k != "intent_id"}
                             for row in rows]
    assert economic(original) == economic(regenerated)  # Same semantic sequence.
    assert toy_cash_split(original, current_key) == {"A": 200, "B": 100}
    assert toy_cash_split(regenerated, current_key) == {"A": 100, "B": 200}


def test_candidate_semantic_key_toy_only_is_lineage_invariant():
    # Proposal illustration only; not an adopted policy or production helper.
    def candidate(row):
        intent = row["intent"]
        return (intent["side"] != "SELL", intent["instrument"],
                intent["original_target_quantity"], intent["side"])

    original, regenerated = lineage_pair()
    for rows in (original, regenerated, original[::-1], regenerated[::-1]):
        assert toy_cash_split(rows, candidate) == {"A": 200, "B": 100}
