"""S1 三买日真实分数研究对照；显式 scoped 输入，只读，不调用 certified/R4。

P2-B：loader 出口做单位 + 完成桶外壳预检；≠δ5 certified ≠R4；不改 simulate/MatchCore/Fees/VolumeCap。
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from backtest.research import csv_minute_backtest as minute
from backtest.research.csv_artifacts import summarize, write_run_artifacts
from backtest.research.csv_minute_volume import UNIT, completed_minute_volumes, validate_participation_rate
from backtest.research.participation_rate_precheck import (
    precheck_completed_bucket_samples,
    precheck_source_pin_unit,
)
from backtest.research.csv_pool import load_pool_day_map, load_pool_names_by_day, validate_pool_dir
from backtest.research.topk_dropout_rules import sort_by_score_desc
from backtest.research.topk_dropout_scores import _bare_or_canon

DAYS = ("20251024", "20251027", "20251028")
PREVIOUS = ("20251023", "20251024", "20251027")
RECORDER = "8a061ea428e04bb3a199a485ade49d0e"
TOPK, N_DROP = 50, 5


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return sha256_stream(stream)


def sha256_stream(stream):
    result = sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        result.update(chunk)
    return result.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def score_map(frame, column):
    require({column, "score"} <= set(frame), f"scores require {column},score")
    pattern = r"(?:SH|SZ|BJ)?\d{6}" if column == "instrument" else r"\d{6}"
    require(frame[column].str.fullmatch(pattern).fillna(False).all(), "invalid score instrument format")
    codes = frame[column].map(_bare_or_canon)
    values = pd.to_numeric(frame.score, errors="raise")
    require(codes.notna().all() and not codes.duplicated().any(), "invalid/duplicate score symbols")
    require(np.isfinite(values).all(), "nonfinite score")
    require(len(codes) >= TOPK, "full cross-section must contain at least Top50; no single-name control")
    return dict(zip(codes, values))


def read_signals(args, pin):
    """完整原始预测日历验证相邻日后再截窗；scores T 文件不再 shift。"""
    pred = args.pred_source.resolve(strict=True)
    pin[str(pred)] = digest(pred)
    require(pin[str(pred)] == args.pred_sha256.lower(), "pred source SHA mismatch")
    original = pd.read_csv(pred, dtype=str)
    require({"datetime", "instrument", "score"} <= set(original), "pred requires datetime,instrument,score")
    original["day"] = pd.to_datetime(original.datetime, errors="raise").dt.strftime("%Y%m%d")
    require(original.day.notna().all(), "missing pred date")
    calendar = sorted(original.day.unique())
    adjacent = dict(zip(calendar[1:], calendar[:-1]))
    require(all(adjacent.get(day) == prev for day, prev in zip(DAYS, PREVIOUS)),
            "full prediction calendar does not prove fixed pred_minus_one mapping")
    require(validate_pool_dir(args.pool_dir) == [], "invalid pool CSV contract")
    pool = load_pool_day_map(args.pool_dir, DAYS[0], DAYS[-1], key="ymd", empty_in_map=False)
    require(set(pool) == set(DAYS), "require all three buy-day pools")
    scores, date_map, needed = {}, [], set()
    for day, prev in zip(DAYS, PREVIOUS):
        score_path = args.scores_dir / f"{day}.csv"
        pool_path = args.pool_dir / f"{day}.csv"
        for path in (score_path, pool_path):
            pin[str(path.resolve(strict=True))] = digest(path)
        exported = pd.read_csv(score_path, dtype=str)
        require(exported.code.str.fullmatch(r"\d{6}").all(), "scores require bare six-digit code")
        scores[day] = score_map(exported, "code")
        original_day = original.loc[original.day == prev].copy()
        expected = score_map(original_day, "instrument")
        require(scores[day].keys() == expected.keys(), f"incomplete cross-section: {day}")
        require(all(math.isclose(value, expected[code], rel_tol=1e-12, abs_tol=1e-15)
                    for code, value in scores[day].items()), f"scores differ from pred[{prev}]")
        ranked = sort_by_score_desc(list(scores[day]), scores[day])
        # MyQuant 导出以原 instrument 打破同分；引擎继续既有 canonical-code 排序。
        original_day["score"] = pd.to_numeric(original_day.score)
        export_ranked = original_day.sort_values(["score", "instrument"], ascending=[False, True],
                                                kind="mergesort").instrument.map(_bare_or_canon).tolist()
        require(pool[day] == export_ranked[:TOPK], f"pool is not exported Top50: {day}")
        # H 个持仓时最多选 max(0,55-H) 个非持仓候选，其全局名次不超过 55。
        # 部分卖出后即使 H>50，该上界仍成立；H>=55 时不产生新候选。
        # 此证明仅用于默认无 eligibility/walkdown 的本脚手架，分数从不裁掉。
        needed.update(ranked[:TOPK + N_DROP])
        rank = export_ranked.index("603196.SH") + 1 if "603196.SH" in scores[day] else None
        date_map.append({"buy_day": day, "pred_day": prev, "rows": len(expected),
                         "603196_score": expected.get("603196.SH"), "603196_rank": rank,
                         "603196_top50": rank is not None and rank <= TOPK})
    source_summary = {"rows": len(original), "columns": [key for key in original if key != "day"],
                      "first_pred_day": calendar[0], "last_pred_day": calendar[-1],
                      "calendar": calendar}
    return pool, scores, date_map, sorted(needed), source_summary


def read_bars(args, needed, pins):
    require(all((args.minute_parquet, args.daily_parquet, args.source_pin)),
            "run requires --minute-parquet, --daily-parquet and --source-pin")
    pin_path = args.source_pin.resolve(strict=True)
    pins[str(pin_path)] = digest(pin_path)
    source = json.loads(pin_path.read_text(encoding="utf-8"))
    # P2-B loader-exit unit precheck (shell; ≠δ5 certified ≠R4).
    try:
        precheck_source_pin_unit(source)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    require(source.get("time_encoding") == "local_wall_as_utc_ms" and source.get("minute_label") == "END",
            "source PIN must declare S1 wall-clock encoding and END minute labels")
    frames = {}
    for period, path in (("1m", args.minute_parquet), ("1d", args.daily_parquet)):
        path = path.resolve(strict=True)
        pins[str(path)] = digest(path)
        entries = [entry for entry in source["artifacts"] if entry["sha256"] == pins[str(path)]]
        require(len(entries) == 1, f"source PIN does not uniquely bind {path}")
        frame = pd.read_parquet(path)
        require(len(frame) == entries[0]["rows"], f"PIN row count: {path}")
        required = {"symbol", "timestamp", "day", "time_ms", "open", "high", "low", "close",
                    "volume", "period", "dividend_type", "unit"}
        require(required <= set(frame), f"S1 scoped columns missing: {sorted(required - set(frame))}")
        for key, value in (("unit", UNIT), ("period", period), ("dividend_type", "none")):
            require(frame[key].eq(value).all(), f"invalid {key}: {path}")
        require(frame.symbol.map(_bare_or_canon).eq(frame.symbol).all(), "canonical source symbols required")
        stamp = pd.to_datetime(frame.timestamp, format="%Y-%m-%d %H:%M:%S", errors="raise")
        # pandas 3 parses strings as us and epoch milliseconds as ms; compare exact ns values.
        epoch_stamp = pd.to_datetime(frame.time_ms, unit="ms").astype("datetime64[ns]")
        require(stamp.notna().all() and stamp.astype("datetime64[ns]").equals(epoch_stamp),
                "S1 wall-clock mismatch")
        require(stamp.dt.strftime("%Y%m%d").eq(frame.day).all(), "S1 day mismatch")
        require((stamp.dt.second == 0).all(), "minute-aligned source required")
        require(not frame.duplicated(["symbol", "timestamp"]).any(), "duplicate source bucket")
        prices = frame[["open", "high", "low", "close"]]
        require(np.isfinite(prices.to_numpy()).all() and (prices > 0).all().all(), "invalid raw OHLC")
        require(frame.high.ge(prices.max(axis=1)).all() and frame.low.le(prices.min(axis=1)).all(), "OHLC order")
        frame.index = pd.DatetimeIndex(stamp)
        frame["ymd"] = frame.day
        frame["hm"] = stamp.dt.hour.to_numpy() * 60 + stamp.dt.minute.to_numpy()
        selected = {}
        for code, rows in frame.groupby("symbol", sort=True):
            require(rows.index.is_monotonic_increasing, f"unsorted source: {code}")
            if code in needed:
                selected[code] = rows.loc[(rows.day >= PREVIOUS[0]) & (rows.day <= DAYS[-1])].copy()
        require(not (missing := set(needed) - selected.keys()), f"missing {period} symbols: {sorted(missing)}")
        frames[period] = selected
    # 不造停牌；此窄窗脚手架要求每个候选的三日成交域和四日日线参考/估值完整。
    # 缺日返回 INPUT_BLOCKED，交接缺口；不缩宇宙，不把缺日当零收益。
    grid = set(range(571, 691)) | set(range(781, 901))
    for code in needed:
        daily, bars = frames["1d"][code], frames["1m"][code]
        require(list(daily.day) == [PREVIOUS[0], *DAYS], f"missing/duplicate daily reference or mark: {code}")
        for day in DAYS:
            rows = bars.loc[bars.day == day]
            require(grid <= set(rows.hm), f"missing completed minute buckets: {code} {day}")
        frames["1m"][code] = bars.loc[bars.day.isin(DAYS)].copy()
    samples = completed_minute_volumes(frames["1m"])
    # P2-B loader-exit completed-bucket precheck (does not redefine buckets).
    precheck_completed_bucket_samples(samples)
    return frames["1m"], frames["1d"], samples


def run_arms(args, pool, scores, bars, daily, samples):
    result = {}
    names = load_pool_names_by_day(args.pool_dir, DAYS[0], DAYS[-1])
    for label, rate in (("cap_off", None), ("cap_on", args.participation_rate)):
        state = minute.simulate(
            deepcopy(bars), deepcopy(daily), deepcopy(pool), DAYS[0], DAYS[-1],
            strategy="topk_dropout", total_cash=args.cash_total, daily_quota=args.cash_total,
            scores_by_day=deepcopy(scores), pool_names_by_day=deepcopy(names),
            participation_rate=rate, volume_for_bucket=samples if rate is not None else None,
        )
        require(state.stats["topk"] == TOPK and state.stats["n_drop"] == N_DROP, "Top50/5 default drift")
        arm = args.out_dir / label
        write_run_artifacts(arm, state, summarize(state, args.cash_total, DAYS[0], DAYS[-1],
                            engine="csv_minute_topk_dropout"), minute.help_lock_for("topk_dropout", shared=minute.HELP_LOCK))
        fills = [row for row in state.trades if row["side"] in ("BUY", "SELL")]
        pd.DataFrame(fills, columns=pd.DataFrame(state.trades).columns).to_csv(arm / "fills.csv", index=False)
        usage = [{"symbol": key[0], "day": key[1], "bucket_end": key[2],
                  "volume_shares": samples[key].shares, "used_shares": used}
                 for key, used in (state.volume_cap.used.items() if rate is not None else [])]
        write_json(arm / "capacity_used.json", usage)
        write_json(arm / "stats.json", state.stats)
        equity = float(state.equity_curve[-1][1])
        result[label] = {"participation_rate": rate, "fills": len(fills), "cash": state.cash,
                         "final_equity": equity, "return_pct": (equity / args.cash_total - 1) * 100,
                         "buy_shares": sum(row["shares"] for row in fills if row["side"] == "BUY"),
                         "sell_shares": sum(row["shares"] for row in fills if row["side"] == "SELL"),
                         "fees": sum(
                             row["commission"]
                             + row.get("stamp_duty", 0.0)
                             + row.get("transfer_fee", 0.0)
                             for row in fills
                         ),
                         "skip_volume_unavailable": state.stats.get("skip_volume_unavailable", 0)}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("scores-dir", "pool-dir", "pred-source", "out-dir"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--pred-sha256", required=True, help="4090 实测完整原始 CSV SHA-256")
    parser.add_argument("--recorder-id", required=True, choices=(RECORDER,))
    for flag in ("minute-parquet", "daily-parquet", "source-pin"):
        parser.add_argument("--" + flag, type=Path)
    parser.add_argument(
        "--participation-rate", type=float, required=True,
        help="cap_on [0,1]; cap_off always None. Shell unit+completed-bucket precheck (P2-B); "
             "≠δ5 certified ≠R4 (not capacity certified)",
    )
    parser.add_argument("--cash-total", type=float, default=minute.DEFAULT_TOTAL_CASH)
    parser.add_argument("--prepare-only", action="store_true", help="验证分数并输出所需证券/date-map，不加载行情")
    args = parser.parse_args(argv)
    args.out_dir = args.out_dir.resolve()
    # 在 mkdir 前拒绝覆盖及输出/输入重叠；已有输出不写失败回执。
    require(not args.out_dir.exists(), "out-dir must be new")
    protected = [REPO, args.scores_dir.resolve(), args.pool_dir.resolve()]
    protected += [path.resolve().parent for path in (args.minute_parquet, args.daily_parquet) if path]
    protected += [path.resolve() for path in (args.pred_source, args.source_pin) if path]
    require(all(not args.out_dir.is_relative_to(root) and not root.is_relative_to(args.out_dir)
                for root in protected), "output overlaps code/input roots")
    args.out_dir.mkdir(parents=True, exist_ok=False)
    receipt = {"status": "NOT_RUN", "stage": "inputs", "reason": "", "tip": git("rev-parse", "HEAD"),
               "out_dir": str(args.out_dir)}
    pins = {}
    manifest = {"tip": receipt["tip"], "argv": vars(args).copy(), "input_sha256": pins,
                "python": sys.version, "pandas": pd.__version__, "numpy": np.__version__,
                "strategy": "topk_dropout", "topk": TOPK, "n_drop": N_DROP,
                "score_origin": "caller_supplied_pred_csv", "score_split": "validation_not_oos",
                "unit": UNIT, "available_at": "bucket_end_research_approximation",
                "time_encoding": "local_wall_as_utc_ms", "minute_label": "END; 09:30 auction excluded",
                "exdiv": None, "exdiv_economics": None,
                "limitations": ["no corporate-action economics supplied", "no independent security-status table",
                                "pool names only; missing names remain unknown", "not certified or execution attestation"],
                "certified": False, "R4": False, "comparison_status": "no_ssot_compare_authorization"}
    manifest["argv"] = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    code = 0
    try:
        validate_participation_rate(args.participation_rate)
        require(math.isfinite(args.cash_total) and args.cash_total > 0, "cash-total must be finite and positive")
        require(not git("status", "--porcelain", "--untracked-files=normal"), "clean PR tip required")
        pool, scores, date_map, needed, source_summary = read_signals(args, pins)
        manifest["pred_source_summary"] = source_summary
        write_json(args.out_dir / "date-map.json", date_map)
        write_json(args.out_dir / "required_symbols.json", {"symbols": needed, "daily_days": [PREVIOUS[0], *DAYS],
                   "minute_days": list(DAYS), "reason": "union of each full cross-section Top55; no eligibility/walkdown"})
        if args.prepare_only:
            receipt.update(stage="prepared", reason="scores pinned; bars and both arms NOT_RUN")
        else:
            bars, daily, samples = read_bars(args, needed, pins)
            receipt["stage"] = "simulate"
            arms = run_arms(args, pool, scores, bars, daily, samples)
            write_json(args.out_dir / "comparison.json", {"arms": arms, "score_split": "validation_not_oos",
                       "comparison_status": "no_ssot_compare_authorization"})
            receipt.update(status="OK", stage="complete", reason="two research arms completed")
        require(all(digest(path) == expected for path, expected in pins.items()), "source changed during run")
        manifest["source_unchanged"] = True
    except Exception as exc:
        receipt.update(status="INPUT_BLOCKED" if receipt["stage"] == "inputs" else "FAILED",
                       reason=f"{type(exc).__name__}: {exc}")
        code = 2 if receipt["status"] == "INPUT_BLOCKED" else 1
    finally:
        write_json(args.out_dir / "STATUS.json", receipt)
        manifest["output_sha256"] = {str(path.relative_to(args.out_dir)): digest(path)
                                      for path in sorted(args.out_dir.rglob("*")) if path.is_file()}
        write_json(args.out_dir / "PIN.json", manifest)
    print(json.dumps(receipt, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
