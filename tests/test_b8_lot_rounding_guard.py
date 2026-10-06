"""H-B8-10=A: file-based quantity guard; exceptions pin contracts, not lines."""
import ast
from pathlib import Path

import pytest

from backtest.research.csv_strategy_books import csv_strategy_names

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = ('backtest/research', 'strategies')
HELPER = 'backtest/research/lot_rounding.py'


def _lot(node):
    return (
        isinstance(node, ast.Constant) and type(node.value) in (int, float)
        and node.value == 100
    ) or isinstance(node, (ast.Name, ast.Attribute)) and (
        getattr(node, 'id', getattr(node, 'attr', '')) == 'lot_size'
    )


def _floor_chain(node, lot):
    # Only follow the quantity operand through truncation/rounding wrappers.
    # Do not mistake a division buried in an unrelated call argument for sizing.
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv)):
        if ast.dump(node.right) == ast.dump(lot) or _lot(node.right) and _lot(lot):
            return True
        # Decimal contracts sometimes divide by price * 100.
        if isinstance(node.right, ast.BinOp) and isinstance(node.right.op, ast.Mult):
            if any(_lot(x) for x in (node.right.left, node.right.right)):
                return True
        return _floor_chain(node.left, lot)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in {'int', 'round', 'floor'}:
            return bool(node.args) and _floor_chain(node.args[0], lot)
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'to_integral_value':
            return _floor_chain(node.func.value, lot)
    return False


def scan_source(source, relative_file):
    """Return (file, lexical function qualname, canonical expression) hits."""
    hits = set()

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.scope = []

        def scoped(self, node):
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        visit_ClassDef = scoped
        visit_FunctionDef = scoped
        visit_AsyncFunctionDef = scoped

        def record(self, node):
            hits.add((relative_file, '.'.join(self.scope) or '<module>', ast.unparse(node)))

        def visit_BinOp(self, node):
            if isinstance(node.op, ast.Mult):
                for lot, quantity in ((node.right, node.left), (node.left, node.right)):
                    if _lot(lot) and _floor_chain(quantity, lot):
                        self.record(node)
            self.generic_visit(node)

        def visit_Compare(self, node):
            operands = [node.left, *node.comparators]
            for left, op, right in zip(operands, node.ops, operands[1:]):
                if isinstance(op, ast.Eq):
                    for mod, zero in ((left, right), (right, left)):
                        if (isinstance(mod, ast.BinOp) and isinstance(mod.op, ast.Mod)
                                and _lot(mod.right) and isinstance(zero, ast.Constant)
                                and zero.value == 0):
                            self.record(node)
            self.generic_visit(node)

        def visit_If(self, node):
            # L2's typed-lot divisibility contracts use truthy remainders.
            if isinstance(node.test, ast.BinOp) and isinstance(node.test.op, ast.Mod) and _lot(node.test.right):
                self.record(node.test)
            self.generic_visit(node)

    Visitor().visit(ast.parse(source))
    return hits


def scanned_files(root=ROOT):
    return sorted(path for directory in SCAN_ROOTS for path in (root / directory).rglob('*.py')
                  if path.relative_to(root).as_posix() != HELPER)


def repository_hits():
    return set().union(*(scan_source(path.read_text(encoding='utf-8'), path.relative_to(ROOT).as_posix())
                         for path in scanned_files()))


# Sensitivity and csv_analysis_export were audited: no matching floor/lot-check
# expression remains in this scan scope. Their FIFO/min and statistics arithmetic
# is not order sizing; do not add stale or wildcard exceptions for them.
ALLOWLIST = {
    ('backtest/research/ashare_volume_cap.py', 'VolumeCap.clamp',
     'filled // 100 * 100'):
        'Frozen core: KNIFE_BASE guard pins this source; B8 leaves capacity unchanged.',
    ('backtest/research/joint_return_replay.py', '_Replay.attempt',
     '(quantity / 100).to_integral_value(rounding=ROUND_FLOOR) * 100'):
        'Inventory-only joint-return execution contract; no CSV sizing migration authorization.',
    ('backtest/research/joint_return_replay.py', 'validate_intents',
     'q % 100 == 0'):
        'Inventory-only joint-return BUY LOT_ROUNDING contract validation.',
    ('backtest/research/joint_return_replay.py', 'validate_manifest',
     "((budget + EPS) / (num(r['reference_price'], 'reference price') * 100)).to_integral_value(rounding=ROUND_FLOOR) * 100"):
        'Inventory-only joint-return Decimal/EPS reference-budget contract.',
    ('backtest/research/minute_orders_backend/ledger.py', 'Ledger.register_bucket',
     'capacity % lot_size'):
        'Inventory-only L2 typed lot_size bucket contract, independent of CSV profiles.',
    ('backtest/research/minute_orders_backend/ledger.py', '_quantity',
     'qty % lot_size'):
        'Inventory-only L2 typed lot_size reservation/ledger validation.',
    ('backtest/research/minute_orders_backend/match.py', 'compute_bucket_capacity',
     'lot_size * (numerator * volume_shares // (denominator * lot_size))'):
        'Inventory-only L2 typed lot_size exact-ratio capacity contract.',
    ('backtest/research/minute_orders_backend/match.py', 'match_candidates',
     'min(order.remaining_qty, capacity_remaining) // order.lot_size * order.lot_size'):
        'Inventory-only L2 typed lot_size candidate fill contract.',
    ('backtest/research/minute_orders_backend/types.py', 'LimitOrderMatchInput.__post_init__',
     'self.remaining_qty % self.lot_size'):
        'Inventory-only L2 typed lot_size input validation.',
    ('backtest/research/verify_chip_factor_consistency.py', 'main',
     'done % 100 == 0'):
        'Non-sizing progress counter: print every 100 processed names.',
}


def assert_allowed(hits, allowlist=ALLOWLIST):
    unexpected = hits - allowlist.keys()
    assert not unexpected, f'Ad-hoc board-lot arithmetic outside helper: {sorted(unexpected)}'


def test_no_ad_hoc_board_lot_arithmetic():
    assert_allowed(repository_hits())


def test_allowlist_has_no_stale_entries():
    assert not (ALLOWLIST.keys() - repository_hits()), 'Remove stale B8 exceptions'
    assert all(reason.strip() for reason in ALLOWLIST.values())


@pytest.mark.parametrize('expr', [
    'x//100*100', 'x // 100.0 * 100.0', 'int(x / 100) * 100',
    'int(x / 100.0) * 100', 'int(x // 100) * 100',
    'x // 10 // 100 * 100', 'int(round(x * fraction, 8)) // 100 * 100',
    'round(x // 100) * 100', 'q % 100 == 0', '100 * int(x / 100)',
])
def test_injected_sizing_is_rejected(expr):
    hits = scan_source(f'def buy(x):\n    return {expr}\n', 'backtest/research/new_book.py')
    assert hits == {('backtest/research/new_book.py', 'buy', ast.unparse(ast.parse(expr).body[0].value))}
    with pytest.raises(AssertionError, match='Ad-hoc board-lot'):
        assert_allowed(hits)


def test_non_sizing_arithmetic_is_not_blanket_banned():
    assert not scan_source('price = round(price, 2)\npercent = x / 100\nlatch = shares < 100\n', 'new.py')


# Each entry pins the lexical owner and the imported arithmetic profile.
CALL_SITES = {
    ('csv_ledger.py', '_buy_size'): {'budget_board_lots', 'budget_integer_shares'},
    ('csv_ledger.py', 'execute_buy'): {'nonnegative_override_board_lots'},
    ('csv_simulate_loop.py', 'run_pool_buys_day'): {'budget_board_lots'},
    ('minute_cash_order.py', 'scale_out_exits'): {'scale_out_board_lots', 'floor_board_lots'},
    ('tail_window_buy.py', 'tail_quote'): {'tail_capacity_board_lots'},
    ('tail_window_buy.py', 'TailParent.from_budget'): {'tail_budget_board_lots', 'tail_slice_board_lots'},
    ('strategy9_1_rules.py', 'unit_shares'): {'risk_unit_board_lots'},
    ('strategy9_2_engine.py', 'plan_exit'): {'rounded_partial_board_lots'},
    ('strategy12_rules.py', 'scale_memory'): {'floordiv_board_lots'},
    ('strategy7_engine.py', '_buy'): {'native_budget_board_lots'},
    ('fullstrat_research_v7.py', 'simulate'): {'native_budget_board_lots'},
    ('unified_exit_modea.py', '_lot_shares'): {'double_floordiv_budget_board_lots'},
}


@pytest.mark.parametrize('site,expected', CALL_SITES.items())
def test_migrated_call_site_uses_imported_helper(site, expected):
    filename, qualname = site
    tree = ast.parse((ROOT / 'backtest/research' / filename).read_text(encoding='utf-8'))
    imports = {
        alias.asname or alias.name: alias.name
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        and node.module == 'backtest.research.lot_rounding'
        for alias in node.names
    }
    owner = tree
    for name in qualname.split('.'):
        owner = next(node for node in owner.body
                     if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name == name)
    calls = {imports[node.func.id] for node in ast.walk(owner)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
             and node.func.id in imports}
    assert expected <= calls, f'{site}: missing helper calls {expected - calls}'
    # A local rebinding could otherwise make the import/call assertion misleading.
    assert not any(isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
                   and node.id in imports for node in ast.walk(owner))


@pytest.mark.parametrize('name', csv_strategy_names())
def test_registered_books_are_scanned_without_a_version_allowlist(name):
    # No book-name filter participates in discovery or expression matching.
    # Exercise the same detector for every registered name, including TopK.
    relative = f'backtest/research/nested/{name}_rules.py'
    hits = scan_source('def size(x):\n    return x // 100 * 100\n', relative)
    assert hits == {(relative, 'size', 'x // 100 * 100')}
    with pytest.raises(AssertionError):
        assert_allowed(hits)


@pytest.mark.parametrize('name', ['version6_45', 'version6_46', 'version6_47', 'version6_future'])
def test_future_book_files_are_discovered_and_guarded(tmp_path, name):
    path = tmp_path / 'backtest/research/nested' / f'{name}_rules.py'
    path.parent.mkdir(parents=True)
    path.write_text('def size(x):\n    return x // 100 * 100\n', encoding='utf-8')
    assert scanned_files(tmp_path) == [path]
    with pytest.raises(AssertionError, match='Ad-hoc board-lot'):
        assert_allowed(scan_source(path.read_text(), path.relative_to(tmp_path).as_posix()))


@pytest.mark.parametrize('name', [name for name in csv_strategy_names() if name.startswith('version6_')])
def test_registered_version6_books_have_current_baseline_owner(name):
    # Read existing owners only; do not regenerate fixtures or run a backtest.
    from scripts.research.generate_off_byte_baseline import expected_case

    for engine in ('daily', 'minute'):
        case, canonical, _ = expected_case(name, engine)
        assert case and canonical, f'{name}/{engine}: missing current baseline owner'


def test_lot_rounding_is_pure():
    tree = ast.parse((ROOT / HELPER).read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module]
            assert all(module in {'decimal', 'typing', '__future__'} for module in modules)
        assert not isinstance(node, (ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith))
        if isinstance(node, ast.Call):
            # Positive arithmetic-only call vocabulary excludes I/O, dynamic
            # imports, attribute mutation and hidden external function calls.
            assert isinstance(node.func, ast.Name)
            assert node.func.id in {'int', 'float', 'str', 'max', 'round', 'Decimal'}
    for node in tree.body:
        if isinstance(node, ast.Expr):
            assert isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            assert isinstance(node.value, ast.Constant)
            assert type(node.value.value) in (int, float, str, bool, type(None))
        else:
            assert isinstance(node, (ast.FunctionDef, ast.Import, ast.ImportFrom))
