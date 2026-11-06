"""Data-free guard for the registered economics consumers (not a sandbox)."""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

CONSUMERS = (
    "backtest/research/ashare_exdiv_economics.py",
    "backtest/research/cash_div_events.py",
    "backtest/research/csv_ledger.py",
    "backtest/research/csv_daily_backtest.py",
    "backtest/research/csv_minute_backtest.py",
    "backtest/research/csv_minute_backtest_v7.py",
    "backtest/research/strategy7_engine.py",
)
# 2026-11-06 Human 裁定：BT 只消费成品数据，不处理数据。原白名单四件
# （pull/hithink_incremental/hithink_artifact/corp_actions_econ_gate）全部迁
# MyQuant-infra（corp_actions/candidates + corp_actions/econ_gate）并自本仓删除；
# 白名单清空，机制保留。
READ_ONLY_MAINTENANCE = ()
READERS = {"read_table", "read_parquet", "ParquetFile", "read_csv", "dataset"}
# Existing non-corp-actions reads, reviewed by purpose, expression and count.
EXISTING_READS = {
    "backtest/research/cash_div_events.py": ("pq.read_table(resolve_source_parquet('ex_date_index.parquet'))",),
    "backtest/research/csv_minute_backtest_v7.py": ("pd.read_parquet(path)",),
}


def violations(source, relative):
    if relative in READ_ONLY_MAINTENANCE:
        return []
    if relative not in CONSUMERS:
        raise ValueError("unregistered economics path; explicitly update the consumer inventory")
    tree = ast.parse(source)
    errors = []
    aliases = {alias.asname or alias.name: alias.name for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom) for alias in node.names if alias.name in READERS}
    allowance = Counter(EXISTING_READS.get(relative, ()))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.lower().replace("\\", "/")
            if "corp_actions" in value or value.endswith("events.parquet"):
                errors.append((node.lineno, "corp-actions path must be owned by the gated loader"))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = ([node.module or ""] + [(node.module or "") + "." + a.name for a in node.names]
                       if isinstance(node, ast.ImportFrom) else [a.name for a in node.names])
            # 已迁 infra 的处理模块（2026-11-06）：本仓不再存在，禁入消费侧。
            if any(m.startswith(("scripts.data.hithink_incremental", "scripts.data.pull_corp_actions_incremental",
                                 "oskh_data.hithink_artifact", "backtest.research.corp_actions_econ_gate"))
                   for m in modules):
                errors.append((node.lineno, "corp-actions processing moved to MyQuant-infra; "
                                            "BT consumes finished data only"))
        if isinstance(node, ast.Call):
            reader = node.func.attr if isinstance(node.func, ast.Attribute) else (
                aliases.get(node.func.id, node.func.id) if isinstance(node.func, ast.Name) else "")
            if reader in READERS:
                expression = ast.unparse(node)
                if allowance[expression] > 0:
                    allowance[expression] -= 1
                else:
                    errors.append((node.lineno, "new direct data reader requires explicit scope review"))
    return errors


def main():
    root = Path(__file__).resolve().parents[2]
    errors = [(path, *error) for path in CONSUMERS
              for error in violations((root / path).read_text(encoding="utf-8"), path)]
    for path, line, message in errors:
        print(f"{path}:{line}: {message}")
    print(f"corp-actions economics fence: {len(CONSUMERS)} registered consumers, {len(errors)} violations")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
