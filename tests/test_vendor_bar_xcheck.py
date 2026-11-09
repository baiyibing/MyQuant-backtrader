"""BT comparison entry: explicit scaling, caller provenance and quarantined overlays."""
import importlib.util
import json
from pathlib import Path

import pandas as pd
from myquant_infra.adapters.vendor_bars import compare as shared
from myquant_infra.artifacts.provenance import git_commit

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bt_vendor_compare", ROOT / "scripts/research/vendor_bar_xcheck.py")
x = importlib.util.module_from_spec(spec)
spec.loader.exec_module(x)


def test_shared_functions_and_explicit_scaling_from_another_cwd(tmp_path, monkeypatch):
    assert x.read_bars is shared.read_bars and x.compare is shared.compare
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    wind = inputs / "wind.csv"
    lake = inputs / "lake.parquet"
    pd.DataFrame({"TIME": ["2025-10-24T10:00:00+08:00"], "wind_code": ["002231.SZ"],
                  "OPEN": [10.], "HIGH": [11.], "LOW": [9.], "MATCH": [10.5], "VOLUME": [100]}).to_csv(wind, index=False)
    stamp = int(pd.Timestamp("2025-10-24T10:01:00").value // 1_000_000)
    pd.DataFrame({"time": [stamp], "symbol": ["002231.SZ"], "open": [10.], "high": [11.],
                  "low": [9.], "close": [10.5], "volume": [1]}).to_parquet(lake, index=False)
    before = wind.read_bytes(), lake.read_bytes()
    monkeypatch.chdir(tmp_path)
    args = ["--wind", str(wind), "--lake", str(lake)]
    assert x.main(args + ["--out-dir", str(tmp_path / "unscaled")]) == 1
    out = tmp_path / "scaled"
    assert x.main(args + ["--volume-scale", "100", "--out-dir", str(out)]) == 0
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    status = json.loads((out / "STATUS.json").read_text(encoding="utf-8"))
    assert report["policy"]["volume_scale"] == 100 and report["unit_notes"][0]["acknowledged"]
    assert status["tip"] == git_commit(ROOT)
    assert before == (wind.read_bytes(), lake.read_bytes())


def test_host_market_overlay_is_not_adopted(tmp_path):
    root = tmp_path / "host"
    (root / "market").mkdir(parents=True)
    pd.DataFrame({"dummy": [1]}).to_parquet(root / "market/minute.parquet")
    out = tmp_path / "out"
    assert x.main(["--host-root", str(root), "--out-dir", str(out)]) == 1
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["host_discovery"]["market_not_adopted"] and report["error"] == "missing input paths"
