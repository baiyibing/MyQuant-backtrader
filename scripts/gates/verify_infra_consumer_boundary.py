"""Data-free gate: migrated implementations must stay in MyQuant-infra."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

RETIRED = (
    "oskh_data/adj_factor.py", "oskh_data/daily_parquet_write.py",
    "oskh_data/repair_daily_parquet_schema.py", "oskh_data/seed_missing_front.py",
    "oskh_data/float_shares_history.py", "oskh_data/audit.py",
    "scripts/tr/rebuild_front_duckdb_standalone.py", "scripts/gates/verify_l2_manifest.py",
    "scripts/misc/l2_phase3_pipeline.py", "scripts/misc/l2_phase3_watch_check.ps1",
    "scripts/misc/extract_stock_rar_data.py", "scripts/misc/compare_l2_etl_engines.py",
    "bt_contract/schema/signal-bundle-1.schema.json", "requirements-l2-polars.txt",
    "scripts/data/pull_corp_actions_incremental.py", "scripts/data/hithink_incremental.py",
    "scripts/gates/verify_corp_actions_hithink_parity.py",
    "oskh_data/hithink_artifact.py", "backtest/research/corp_actions_econ_gate.py",
)
EXPORTS = {
    "oskh_data/period_schema.py": "myquant_infra.lake.metadata",
    "oskh_data/parquet_meta.py": "myquant_infra.lake.metadata",
    "oskh_data/pandas_typing.py": "myquant_infra.bars.pandas_typing",
    "oskh_data/symbol_format.py": "myquant_infra.reference_data.symbols",
    "oskh_data/lake_kind.py": "myquant_infra.bars.lake_kind",
    "oskh_data/adj_factor_meta.py": "myquant_infra.bars.adj_factor_meta",
    "oskh_core/a_share_symbol_normalize.py": "myquant_infra.reference_data.symbols",
    "common/infra/pool_csv.py": "myquant_infra.reference_data.pool_csv",
    "common/infra/pandas_frame_utils.py": "myquant_infra.utils.pandas_frame_utils",
}
# Host wrappers may configure paths, readers, locks and policy, never duplicate IO.
FACADES = (
    "oskh_data/reader.py", "oskh_data/cache_port.py", "oskh_data/etf_local_bars.py",
    "oskh_data/industry_sw_l1.py", "oskh_data/turnover_resistance_store.py",
    "bt_contract/run_manifest.py", "bt_contract/signal_bundle.py",
    "common/integrations/duckdb_daily_bars_adapter.py",
    "common/infra/trading_calendar_pmc.py",
    "common/infra/qmt_utils_adv.py",
)
FORBIDDEN_IO = {"read_parquet", "to_parquet", "read_metadata", "connect", "execute", "executemany"}


def violations(root: Path) -> list[str]:
    errors = [f"retired source restored: {name}" for name in RETIRED if (root / name).exists()]
    sources = []
    l2 = root / "l2_analytics"
    if l2.exists():
        sources.extend(p for p in l2.rglob("*") if p.suffix in {".py", ".sql"})
    sources.extend((root / "scripts/run").glob("run_l2_*.py"))
    errors.extend(f"migrated L2 source restored: {p.relative_to(root)}" for p in sources)
    for name, module in EXPORTS.items():
        path = root / name
        if not path.is_file():
            errors.append(f"missing consumer exports: {name}")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not any(isinstance(n, ast.ImportFrom) and n.module == module for n in tree.body):
            errors.append(f"missing infra import: {name}: {module}")
        if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))
               for n in ast.walk(tree)):
            errors.append(f"local implementation in export module: {name}")
    for name in FACADES:
        path = root / name
        if not path.is_file():
            errors.append(f"missing consumer facade: {name}")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in FORBIDDEN_IO:
                    errors.append(f"local storage implementation: {name}:{node.lineno}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    errors = violations(args.root.resolve())
    for error in errors:
        print(error)
    print(f"[infra-consumer-boundary] {'FAIL' if errors else 'PASS'}")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
