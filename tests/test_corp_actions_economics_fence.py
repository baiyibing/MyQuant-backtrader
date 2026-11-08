"""Consumer-side corp-actions economics fence tests (post 2026-11-06 migration).

处理域（pull/hithink_incremental/hithink_artifact/econ_gate）已迁 MyQuant-infra
并自本仓删除；fence 保留消费侧守卫语义：注册消费者禁止直接读 corp-actions
数据、禁止 import 已迁走的处理模块（econ gate 用例随迁 infra
tests/corp_actions/test_econ_gate.py）。
"""

import pytest

from scripts.gates import verify_corp_actions_economics_fence as fence


def test_fence_inventory_and_maintenance_exemptions():
    path = "backtest/research/csv_daily_backtest.py"
    bypass = "from pyarrow import parquet as pq\nx = pq.read_table(root / 'corp_actions' / 'events.parquet')"
    assert fence.violations(bypass, path)
    assert fence.violations("from scripts.data.hithink_incremental import imported", path)
    assert fence.violations("from myquant_infra.corp_actions.candidates import driver", path)
    assert fence.violations("import myquant_infra.hithink.artifacts", path)
    assert fence.violations(
        "import backtest.research.corp_actions_econ_gate as eg\neg.gate_rows_for_economics(rows)",
        path,
    )
    # 2026-11-06 迁移后：消费侧也不得 import 已迁 infra 的门（含直名 import）
    assert fence.violations("from backtest.research import corp_actions_econ_gate as eg", path)
    assert fence.violations(
        "from backtest.research.corp_actions_econ_gate import load_corp_actions_for_economics\n"
        "x=load_corp_actions_for_economics()",
        path,
    )
    assert fence.violations("pq.read_table(events_path)", path)
    assert fence.violations("from pyarrow.parquet import read_table as rt\nrt(events_path)", path)
    assert fence.main() == 0


def test_removed_maintenance_paths_are_no_longer_whitelisted():
    bypass = "from pyarrow import parquet as pq\nx = pq.read_table(root / 'corp_actions' / 'events.parquet')"
    for removed in (
        "scripts/data/pull_corp_actions_incremental.py",
        "scripts/data/hithink_incremental.py",
        "oskh_data/hithink_artifact.py",
        "backtest/research/corp_actions_econ_gate.py",
    ):
        with pytest.raises(ValueError, match="unregistered"):
            fence.violations(bypass, removed)


def test_unregistered_paths_fail_closed():
    with pytest.raises(ValueError, match="unregistered"):
        fence.violations("x = 1", "backtest/research/not_registered.py")
