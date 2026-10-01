"""脚手架合成输入验证；通过不代表宿主真分数/行情已取得。"""

import json
from pathlib import Path
import tempfile

import pandas as pd
import pytest

from scripts.research import run_topk_cap_compare as harness


@pytest.fixture
def source(monkeypatch):
    monkeypatch.setattr(harness, "git", lambda *args: "test-only-tip" if args[0] == "rev-parse" else "")
    with tempfile.TemporaryDirectory(prefix="topk_cap_synthetic_") as folder:
        root = Path(folder)
        inputs = root / "inputs"
        inputs.mkdir()
        for name in ("pool", "scores"):
            (inputs / name).mkdir()
        codes = [f"{600000 + index:06d}" for index in range(60)]
        pred_rows = []
        for offset, day in enumerate([harness.PREVIOUS[0], *harness.DAYS]):
            # 改变真实候选集合以测试多证券/dropout；数值仍是测试生成，不能当真分。
            ordered = codes[offset * 3:] + codes[:offset * 3]
            values = {code: 100 - rank for rank, code in enumerate(ordered)}
            pred_rows += [{"datetime": pd.Timestamp(day).strftime("%Y-%m-%d"),
                           "instrument": "SH" + code, "score": values[code]} for code in codes]
            if offset < 3:
                buy_day = harness.DAYS[offset]
                pd.DataFrame([{"code": code, "score": values[code]} for code in ordered]).to_csv(
                    inputs / "scores" / f"{buy_day}.csv", index=False)
                (inputs / "pool" / f"{buy_day}.csv").write_text(
                    "".join(f"{code},测试证券\n" for code in ordered[:50]), encoding="utf-8")
        pd.DataFrame(pred_rows).to_csv(inputs / "pred.csv", index=False)
        artifacts = []
        for period in ("1m", "1d"):
            rows = []
            for code in codes:
                for day in [harness.PREVIOUS[0], *harness.DAYS]:
                    grid = [0] if period == "1d" else [570, *range(571, 691), *range(781, 901)]
                    for hm in grid:
                        stamp = pd.Timestamp(day) + pd.Timedelta(minutes=hm)
                        rows.append({"symbol": code + ".SH", "timestamp": stamp.strftime("%Y-%m-%d %H:%M:%S"),
                                     "time_ms": stamp.value // 10**6, "day": day,
                                     "open": 10., "high": 10., "low": 10., "close": 10.,
                                     "volume": 2500, "period": period, "unit": harness.UNIT,
                                     "dividend_type": "none"})
            path = inputs / f"{period}.parquet"
            pd.DataFrame(rows).to_parquet(path, index=False)
            artifacts.append({"path": str(path), "sha256": harness.digest(path), "rows": len(rows)})
        harness.write_json(inputs / "PIN.json", {"unit": harness.UNIT, "transformations": [], "artifacts": artifacts,
                           "time_encoding": "local_wall_as_utc_ms", "minute_label": "END"})
        argv = ["--scores-dir", str(inputs / "scores"), "--pool-dir", str(inputs / "pool"),
                "--pred-source", str(inputs / "pred.csv"), "--pred-sha256", harness.digest(inputs / "pred.csv"),
                "--recorder-id", harness.RECORDER, "--minute-parquet", str(inputs / "1m.parquet"),
                "--daily-parquet", str(inputs / "1d.parquet"), "--source-pin", str(inputs / "PIN.json"),
                "--participation-rate", ".1", "--out-dir", str(root / "run")]
        yield root, inputs, argv


def test_two_independent_top50_arms_and_reproducible_pins(source):
    root, inputs, argv = source
    before = {str(p): harness.digest(p) for p in inputs.rglob("*") if p.is_file()}
    assert harness.main(argv) == 0
    out = root / "run"
    status = json.loads((out / "STATUS.json").read_text())
    assert status["status"] == "OK" and len(status) == 5
    compare = json.loads((out / "comparison.json").read_text())["arms"]
    assert compare["cap_off"]["participation_rate"] is None
    assert compare["cap_on"]["participation_rate"] == .1
    assert compare["cap_on"]["buy_shares"] < compare["cap_off"]["buy_shares"]
    for arm in ("cap_on", "cap_off"):
        fills = pd.read_csv(out / arm / "fills.csv")
        assert fills.loc[fills.side == "BUY", "code"].nunique() >= 50
        assert (out / arm / "daily_equity.csv").is_file()
        assert (out / arm / "summary.txt").is_file()
    pin = json.loads((out / "PIN.json").read_text())
    assert pin["source_unchanged"] and pin["score_split"] == "validation_not_oos"
    assert pin["pred_source_summary"]["rows"] == 240
    assert pin["pred_source_summary"]["calendar"] == [harness.PREVIOUS[0], *harness.DAYS]
    assert (pin["topk"], pin["n_drop"]) == (50, 5)
    for name, expected in pin["output_sha256"].items():
        assert harness.digest(out / name) == expected
    assert before == {str(p): harness.digest(p) for p in inputs.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="out-dir must be new"):
        harness.main(argv)


@pytest.mark.parametrize("failure", ["single_name", "wrong_shift", "bad_pin", "missing_symbol", "missing_minute", "missing_daily", "wrong_unit", "unknown_clock"])
def test_bad_inputs_never_run_partial_universe(source, failure):
    root, inputs, argv = source
    if failure in ("single_name", "wrong_shift"):
        path = inputs / "scores" / f"{harness.DAYS[0]}.csv"
        frame = pd.read_csv(path)
        if failure == "single_name":
            frame = frame.iloc[:1]
        else:
            frame["score"] += 1
        frame.to_csv(path, index=False)
    else:
        pin = json.loads((inputs / "PIN.json").read_text())
        if failure == "bad_pin":
            pin["artifacts"][0]["sha256"] = "0" * 64
        elif failure == "wrong_unit":
            pin["unit"] = "lots"
        elif failure == "unknown_clock":
            pin.pop("minute_label")
        else:
            period = "1d" if failure == "missing_daily" else "1m"
            path = inputs / f"{period}.parquet"
            frame = pd.read_parquet(path)
            if failure == "missing_symbol":
                frame = frame.loc[frame.symbol != "600000.SH"]
            else:
                drop = (frame.symbol == "600000.SH") & (frame.day == "20251024")
                if period == "1m":
                    drop &= frame.timestamp.str.endswith("09:31:00")
                frame = frame.drop(index=frame.index[drop][0])
            frame.to_parquet(path, index=False)
            entry = next(row for row in pin["artifacts"] if row["path"] == str(path))
            entry.update(sha256=harness.digest(path), rows=len(frame))
        harness.write_json(inputs / "PIN.json", pin)
    assert harness.main(argv) == 2
    out = root / "run"
    assert json.loads((out / "STATUS.json").read_text())["status"] == "INPUT_BLOCKED"
    assert not (out / "cap_off").exists() and not (out / "cap_on").exists()


def test_prepare_without_bars_lists_scope_and_leaves_both_arms_not_run(source):
    root, inputs, argv = source
    (inputs / "1m.parquet").unlink()
    assert harness.main([*argv, "--prepare-only"]) == 0
    out = root / "run"
    assert json.loads((out / "STATUS.json").read_text())["status"] == "NOT_RUN"
    required = json.loads((out / "required_symbols.json").read_text())
    assert len(required["symbols"]) == 60
    assert not (out / "cap_off").exists()


def test_output_overlap_does_not_create_directory(source):
    _, inputs, argv = source
    argv[-1] = str(inputs / "scores" / "unsafe")
    with pytest.raises(ValueError, match="overlaps"):
        harness.main(argv)
    assert not (inputs / "scores" / "unsafe").exists()
