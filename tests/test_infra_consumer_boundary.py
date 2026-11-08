"""Regression checks for the no-copies infra consumer boundary."""
from pathlib import Path

from scripts.gates.verify_infra_consumer_boundary import EXPORTS, FACADES, RETIRED, violations


def test_repository_consumes_migrated_implementations():
    assert violations(Path(__file__).resolve().parents[1]) == []


def minimal_consumer_tree(root):
    for name, module in EXPORTS.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"from {module} import exported\n", encoding="utf-8")
    for name in FACADES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('"""Host policy only."""\n', encoding="utf-8")


def test_gate_rejects_retired_producer_and_l2_code(tmp_path):
    minimal_consumer_tree(tmp_path)
    path = tmp_path / RETIRED[0]
    path.write_text("# restored producer\n", encoding="utf-8")
    l2 = tmp_path / "l2_analytics/etl_day.py"
    l2.parent.mkdir()
    l2.write_text("# restored ETL\n", encoding="utf-8")
    errors = violations(tmp_path)
    assert any("retired source restored" in error for error in errors)
    assert any("migrated L2 source restored" in error for error in errors)


def test_gate_rejects_local_fallback_implementation(tmp_path):
    minimal_consumer_tree(tmp_path)
    name = "oskh_data/period_schema.py"
    with (tmp_path / name).open("a", encoding="utf-8") as stream:
        stream.write("def fallback():\n    return []\n")
    assert any("local implementation" in error for error in violations(tmp_path))


def test_gate_rejects_storage_inside_host_facade(tmp_path):
    minimal_consumer_tree(tmp_path)
    path = tmp_path / "oskh_data/reader.py"
    path.write_text("def read(pd, path):\n    return pd.read_parquet(path)\n", encoding="utf-8")
    assert any("local storage implementation" in error for error in violations(tmp_path))
