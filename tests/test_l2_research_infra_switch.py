"""B4 host contracts: fake infra in public CI, tmp-only pinned integration."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from l2_analytics import _infra, board_limit, consumer_dedup, db, ref_data, sql, templates
from scripts.run import run_l2_net_inflow_by_price as inflow
from scripts.run import run_l2_p0b_baseline as baseline


def fake_queries(monkeypatch, **modules):
    def load(name):
        return modules[name.removeprefix("myquant_infra.l2.research.queries.")]

    monkeypatch.setattr(_infra, "import_module", load)


def test_connect_forwards_explicit_paths_and_options(tmp_path, monkeypatch):
    run = Mock(return_value=object())
    fake_queries(monkeypatch, db=SimpleNamespace(connect=run))
    root, temp, adj = tmp_path / "lake", tmp_path / "spill", tmp_path / "adj.parquet"
    monkeypatch.setattr(db, "default_parquet_root", Mock(side_effect=AssertionError("explicit root")))
    monkeypatch.setattr(db, "default_adj_factor_path", Mock(side_effect=AssertionError("explicit ref")))
    assert db.connect(parquet_root=str(root), temp_directory=temp, adj_factor_path=adj,
                      memory_limit="1GB", threads=2) is run.return_value
    run.assert_called_once_with(parquet_root=root, temp_directory=temp, adj_factor_path=adj,
                                memory_limit="1GB", threads=2, register_adj=True)
    assert list(tmp_path.iterdir()) == []


def test_connect_and_reference_views_use_host_resolvers(tmp_path, monkeypatch):
    from common.infra import data_root

    root, adj = tmp_path / "configured", tmp_path / "adj.parquet"
    monkeypatch.setattr(data_root, "resolve_l2_parquet_root", lambda: root)
    resolve_ref = Mock(return_value=adj)
    monkeypatch.setattr(data_root, "resolve_source_parquet", resolve_ref)
    connect, register = Mock(), Mock()
    fake_queries(monkeypatch, db=SimpleNamespace(connect=connect),
                 ref_data=SimpleNamespace(register_ref_views=register))
    db.connect()
    connect.assert_called_once_with(parquet_root=root, memory_limit="18GB", threads=None,
                                    temp_directory=None, adj_factor_path=adj, register_adj=True)
    con = object()
    ref_data.register_ref_views(con)
    register.assert_called_once_with(con, adj_factor_path=adj)
    assert resolve_ref.call_count == 2
    resolve_ref.assert_called_with("adj_factor.parquet")
    assert list(tmp_path.iterdir()) == []


def test_raw_connection_does_not_resolve_reference(tmp_path, monkeypatch):
    run = Mock()
    fake_queries(monkeypatch, db=SimpleNamespace(connect=run))
    monkeypatch.setattr(db, "default_adj_factor_path", Mock(side_effect=AssertionError("raw query")))
    db.connect(parquet_root=tmp_path, register_adj=False)
    assert run.call_args.kwargs["register_adj"] is False
    assert run.call_args.kwargs["adj_factor_path"] is None


def test_unconfigured_lake_fails_before_session_creation(monkeypatch):
    from common.infra import data_root

    def unconfigured():
        raise data_root.UnconfiguredDataRootError("test: configure the lake")

    run = Mock()
    fake_queries(monkeypatch, db=SimpleNamespace(connect=run))
    monkeypatch.setattr(data_root, "resolve_l2_parquet_root", unconfigured)
    with pytest.raises(data_root.UnconfiguredDataRootError, match="configure the lake"):
        db.connect(register_adj=False)
    run.assert_not_called()


def test_templates_and_resources_use_infra(monkeypatch, tmp_path):
    load, run, directory = Mock(), Mock(), Mock(return_value=tmp_path)
    names = {"vwap": "vwap.sql"}
    fake_queries(monkeypatch, templates=SimpleNamespace(
        TEMPLATE_FILES=names, load_template=load, run_template=run, sql_dir=directory))
    assert templates.TEMPLATE_FILES is names
    assert sql.sql_dir() == tmp_path
    assert sql.load_template("vwap") is load.return_value
    load.assert_called_once_with("vwap")
    con, params = object(), {"code": "000001.SZ"}
    assert templates.run_template(con, "vwap", extra_where="stock_code = $code",
                                  limit=3, order_by="vwap DESC", params=params) is run.return_value
    run.assert_called_once_with(con, "vwap", extra_where="stock_code = $code",
                                limit=3, order_by="vwap DESC", params=params)


def test_board_and_dedup_exports_use_infra(monkeypatch):
    pct, main, order, register, audit = (Mock() for _ in range(5))
    main_cols, order_cols = ("main",), ("order",)
    fake_queries(monkeypatch,
        board_limit=SimpleNamespace(board_limit_pct=pct, BOARD_LIMIT_PCT_SQL="infra SQL"),
        consumer_dedup=SimpleNamespace(exact_deduped_main_sql=main, exact_deduped_order_sql=order,
            register_dedup_views=register, audit_main_dup_stats=audit,
            MAIN_EXACT_DUP_COLS=main_cols, ORDER_EXACT_DUP_COLS=order_cols))
    assert board_limit.board_limit_pct("302001.SZ") is pct.return_value
    pct.assert_called_once_with("302001.SZ")
    assert board_limit.BOARD_LIMIT_PCT_SQL == "infra SQL"
    assert consumer_dedup.MAIN_EXACT_DUP_COLS is main_cols
    assert consumer_dedup.ORDER_EXACT_DUP_COLS is order_cols
    consumer_dedup.exact_deduped_main_sql("x", extra_where="date = CAST($date AS DATE)")
    main.assert_called_once_with("x", extra_where="date = CAST($date AS DATE)")
    consumer_dedup.exact_deduped_order_sql()
    order.assert_called_once_with("o", extra_where=None)
    con = object()
    consumer_dedup.register_dedup_views(con)
    register.assert_called_once_with(con)
    assert consumer_dedup.audit_main_dup_stats(con, date="2026-01-15") is audit.return_value
    audit.assert_called_once_with(con, date="2026-01-15")


@pytest.mark.parametrize("module", [templates, board_limit, consumer_dedup])
def test_unknown_export_is_attribute_error(module):
    with pytest.raises(AttributeError):
        getattr(module, "not_an_export")


def test_cli_default_roots_reports_and_exit_status(tmp_path, monkeypatch):
    net, bench = Mock(return_value=4), Mock(return_value=5)
    fake_queries(monkeypatch, net_inflow_by_price=SimpleNamespace(main=net),
                 p0b_baseline=SimpleNamespace(main=bench))
    monkeypatch.setattr(inflow, "default_parquet_root", lambda: tmp_path)
    monkeypatch.setattr(baseline, "default_parquet_root", lambda: tmp_path)
    assert inflow.main(["--date", "2026-01-15", "--stock-code", "000001.SZ"]) == 4
    net.assert_called_once_with([
        "--parquet-root", str(tmp_path), "--date", "2026-01-15", "--stock-code", "000001.SZ",
        "--memory-limit", "18GB", "--bin-width", "0.0", "--order-by", "", "--limit", "0",
        "--out-json", "", "--out-csv", "",
    ])
    assert baseline.main([]) == 5
    bench.assert_called_once_with([
        "--parquet-root", str(tmp_path), "--date", "2026-07-17", "--memory-limit", "18GB",
        "--out-json", str(tmp_path / "p0b_baseline_2026-07-17.json"),
    ])
    assert list(tmp_path.iterdir()) == []


def test_cli_explicit_options_override_host_defaults(tmp_path, monkeypatch):
    net, bench = Mock(return_value=0), Mock(return_value=0)
    fake_queries(monkeypatch, net_inflow_by_price=SimpleNamespace(main=net),
                 p0b_baseline=SimpleNamespace(main=bench))
    fail = Mock(side_effect=AssertionError("explicit root"))
    monkeypatch.setattr(inflow, "default_parquet_root", fail)
    monkeypatch.setattr(baseline, "default_parquet_root", fail)
    common = ["--parquet-root", str(tmp_path), "--date", "2026-01-15", "--memory-limit", "1GB"]
    inflow.main(common + ["--stock-code", "000001.SZ", "--bin-width", "0.5",
                         "--order-by", "net_inflow", "--limit", "2",
                         "--out-json", "report.json", "--out-csv", "report.csv"])
    assert net.call_args.args[0] == [
        "--parquet-root", str(tmp_path), "--date", "2026-01-15", "--stock-code", "000001.SZ",
        "--memory-limit", "1GB", "--bin-width", "0.5", "--order-by", "net_inflow", "--limit", "2",
        "--out-json", "report.json", "--out-csv", "report.csv",
    ]
    baseline.main(common + ["--out-json", "bench.json", "--raw-bc", "--adj-factor-path", "adj.parquet"])
    bench.assert_called_once_with(common + ["--out-json", "bench.json", "--raw-bc",
                                           "--adj-factor-path", "adj.parquet"])
    assert list(tmp_path.iterdir()) == []


def test_public_imports_and_cli_help_without_private_package():
    code = '''
import importlib.abc, runpy, sys
class BlockPrivate(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "myquant_infra" or fullname.startswith("myquant_infra.") or fullname == "duckdb":
            raise ModuleNotFoundError(fullname, name=fullname)
sys.meta_path.insert(0, BlockPrivate())
from l2_analytics import templates, sql, db, ref_data, board_limit, consumer_dedup
for script in ("scripts/run/run_l2_net_inflow_by_price.py", "scripts/run/run_l2_p0b_baseline.py"):
    sys.argv = [script, "--help"]
    try:
        runpy.run_path(script, run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 0
for operation in (
    lambda: templates.load_template("vwap"), sql.sql_dir,
    lambda: db.connect(parquet_root="missing", register_adj=False),
    lambda: ref_data.register_ref_views(object(), adj_factor_path="missing"),
    lambda: board_limit.board_limit_pct("302001.SZ"),
    lambda: consumer_dedup.exact_deduped_main_sql(),
):
    try:
        operation()
    except ImportError as exc:
        assert "requirements-infra.txt" in str(exc)
    else:
        raise AssertionError("operation must require infra")
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parents[1], timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.fixture(params=["hive", "legacy", "mixed"])
def tiny_research_lake(tmp_path, request):
    pytest.importorskip("myquant_infra.l2.research.queries")
    from l2_analytics.etl_day import etl_one_day

    source = tmp_path / "2026-01-15"
    source.mkdir()
    row = "1,09:30:00,10,100,100,100,B,1,10,2,10\n"
    (source / "000001.csv").write_text(
        "TranID,Time,Price,Volume,SaleOrderVolume,BuyOrderVolume,Type,"
        "SaleOrderID,SaleOrderPrice,BuyOrderID,BuyOrderPrice\n" + row + row +
        "2,09:31:00,11,50,50,50,S,3,11,4,11\n"
        "3,09:32:00,12,100,100,100,B,5,12,6,12\n", encoding="utf-8")
    root = tmp_path / "lake"
    etl_one_day(source, out_root=root, threads=1, engine="duckdb", validate_gap_free=False)
    for side in ("main", "order"):
        path = root / "date=2026-01-15" / f"{side}.parquet"
        if request.param != "hive":
            flat = root / f"2026-01-15.part-0000.{side}.parquet"
            flat.write_bytes(path.read_bytes())
            if request.param == "legacy":
                path.unlink()
    return root, 2 if request.param == "mixed" else 1


def test_real_templates_dedup_and_reports_leave_sources_unchanged(tiny_research_lake, tmp_path):
    root, copies = tiny_research_lake
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    con = db.connect(parquet_root=root, register_adj=False, threads=1, memory_limit="1GB")
    try:
        rows = templates.run_template(con, "net_inflow", extra_where="stock_code = $code",
                                      params={"code": "000001.SZ"})
        assert float(rows[0][2]) == pytest.approx(2650 * copies)
        stats = consumer_dedup.audit_main_dup_stats(con, date="2026-01-15")
        assert stats["rows_raw"] == 4 * copies
        assert stats["rows_exact_unique"] == 3
        consumer_dedup.register_dedup_views(con)
        assert con.execute("SELECT COUNT(*) FROM l2_main").fetchone()[0] == 4 * copies
        assert con.execute("SELECT COUNT(*) FROM l2_main_exact_dedup").fetchone()[0] == 3
    finally:
        con.close()

    report, table = tmp_path / "report.json", tmp_path / "report.csv"
    assert inflow.main(["--parquet-root", str(root), "--date", "2026-01-15",
                        "--stock-code", "000001.SZ", "--limit", "1",
                        "--out-json", str(report), "--out-csv", str(table)]) == 0
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["n_price_levels"] == 1
    assert result["totals"]["net_inflow"] == pytest.approx(2650 * copies)
    assert result["totals"]["ticks"] == 4 * copies
    with table.open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 1

    assert baseline.main(["--parquet-root", str(root), "--date", "2026-01-15",
                          "--memory-limit", "1GB"]) == 0
    bench = json.loads((root / "p0b_baseline_2026-01-15.json").read_text(encoding="utf-8"))
    assert bench["smoke"]["main_rows"] == 4 * copies
    assert bench["templates"]["vwap_adj_sample"]["skipped"] is True
    assert bench["templates"]["limit_up_down_true_sample"]["skipped"] is True
    assert set(bench["access_modes"]) == {
        "A_single_stock_net_inflow", "B_cross_section_top50", "C_large_order_clusters", "D_open30m_tick_speed",
    }
    assert before == {rel: (root / rel).read_bytes() for rel in before}


def test_requested_missing_reference_fails_without_creating_output(tmp_path):
    pytest.importorskip("myquant_infra.l2.research.queries")
    with pytest.raises(FileNotFoundError, match="adj_factor_path"):
        db.connect(parquet_root=tmp_path / "lake", adj_factor_path=tmp_path / "missing.parquet")
    with pytest.raises(FileNotFoundError, match="adj_factor_path"):
        ref_data.register_ref_views(object(), adj_factor_path=tmp_path / "missing.parquet")
    assert list(tmp_path.iterdir()) == []


def test_installed_sql_resources_match_frozen_host_templates():
    pytest.importorskip("myquant_infra.l2.research.queries")
    expected = {
        "buy_order_cluster": "29d58a76e8eafddd2d1c26c1b7ee3b6ed05fc094b993389c119e7d61b4eff353",
        "large_order_cluster": "bd168384b67986b8564e2a0c788abff607e96670398fa6fb809c6d020d105cfe",
        "large_order_cluster_agg": "15e0552b53aa27464fd376b420972e80a3aa5b7334fc66818379eb2c4c678669",
        "limit_up_down": "a91fbd6e8ccfde08748ba912d6c54c8a134dc909108f18c9de121087d950a80d",
        "limit_up_down_true": "dd117bd8798d3acc99e3f36c87913a5dae2c5a0b3f17e0df656146296d1b6488",
        "net_inflow": "41d99bdac4064ae45219e5b744d80109a4fc27b49d9c9c88def9bf9526792670",
        "opening_auction": "6df8c93b7be03f5e87b50a454b51a9e3940ca6f06551b29b5328942dc39df352",
        "price_impact": "4dfb12e40226094796fdf0550f083320829d48a762ec25b3018c70d54501d3cf",
        "session_distribution": "d659c9811cf57ea788a5adb478e197bce689e6d8b07febfbf28a7da3e56f73c6",
        "tick_speed": "da709998abdc782177b927f7e7731f526ed4ef22a0c5e666bde0d0663b493679",
        "vwap": "31d9cf6fc4a808707c63040191170c25633f08562c6545046991c0316fe024fa",
        "vwap_adj": "349095d39ccf51789771a3aa6774fec82816a5c36e8a9695ee0c0d3f14739304",
    }
    assert set(templates.TEMPLATE_FILES) == set(expected)
    assert sql.sql_dir().is_dir()
    assert not list(Path(sql.__file__).parent.glob("*.sql"))
    for name, digest in expected.items():
        assert hashlib.sha256(sql.load_template(name).encode("utf-8")).hexdigest() == digest
        assert (sql.sql_dir() / templates.TEMPLATE_FILES[name]).is_file()
