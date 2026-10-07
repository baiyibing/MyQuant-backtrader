"""Data-free tags for isolated research execution families.

Leaves may be reused; non-default clocks/slip, joint-return, and minute_orders
execution stay isolated from the simulate hot path. Tags do not register books
or change execution behavior.
"""

FULLSTRAT_MODULES = frozenset({
    "fullstrat_research_book",
    "fullstrat_research_hooks",
    "fullstrat_research_modeb",
    "fullstrat_research_runners",
    "fullstrat_research_v7",
})
JOINT_RETURN_MODULES = frozenset({
    "joint_return_columnar_pack",
    "joint_return_qlib_bin_pack",
    "joint_return_replay",
    "joint_return_validate_v2",
    "run_protocol.adapters.joint_return",
})
MINUTE_ORDERS_MODULES = frozenset({"minute_orders_backend"})

ISOLATED_RESEARCH_FAMILIES = {
    "fullstrat_research": FULLSTRAT_MODULES,
    "joint_return": JOINT_RETURN_MODULES,
    "minute_orders_backend": MINUTE_ORDERS_MODULES,
}


def isolated_import_prefixes() -> tuple[str, ...]:
    """Return bare and qualified family prefixes, including adapter modules."""
    stems = set(ISOLATED_RESEARCH_FAMILIES)
    for modules in ISOLATED_RESEARCH_FAMILIES.values():
        stems.update(modules)
    return tuple(sorted(
        prefix
        for stem in stems
        for prefix in (stem, f"backtest.research.{stem}")
    ))
