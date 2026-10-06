# H-RB-10 / RB-10 typed hooks and limited lint — 2026-10-06

RB-10 is **ZERO-DIFF**: static typing descriptions and a narrow CI lint extension.
`backtest/research/strategy_hooks_types.py` is a standalone leaf importing only
standard-library `typing` and `collections.abc` modules. It exports `StrategyHooks`, a
`TypedDict(total=False)` describing a practical subset of common apply-output
keys, and `StrategyApply`, a callable protocol accepting keyword arguments and
returning `Mapping[str, Any]`.

All described keys are optional; the subset is not an exhaustive schema.
Callbacks retain flexible signatures because books have different contracts.
Legacy hook dictionaries remain plain dictionaries, including extra keys.
There are no runtime validators, coercions, wrappers, or default injections.
The registry and its `CsvStrategyBook.apply` annotation remain untouched.

```python
from typing import Any, Mapping
from backtest.research.strategy_hooks_types import StrategyHooks

hooks: StrategyHooks = {"name": "example", "stop_pct": None}
view: Mapping[str, Any] = hooks
```

CI runs Ruff on exactly `bt_contract` and the new leaf file. The pandas pin,
gate ordering, and existing lint rules remain unchanged. Other research modules
are outside this lint expansion.

`tests/test_rb10_strategy_hooks_types.py` checks TypedDict identity, optional
keys, plain-dict subset construction and Mapping use, the protocol return
annotation, and an AST fence permitting only those standard-library imports and no calls.
The existing CI lint-scope test locks the exact two targets. These runtime
tests illustrate static assignment shapes; they do not run a type checker.

No simulate engine, fixture, baseline, HELP_LOCK, strategy rules, CLI, or trading
behavior changes. RB-11 and later work are outside this change.
