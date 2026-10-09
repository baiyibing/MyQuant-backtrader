"""Wall-clock and simulate-phase timings for CSV daily/minute host runs.

Default on for ``run()``. ``OSKH_PROFILE_SIM=0`` turns it off.
Library ``simulate()`` stays off unless a clock is passed, so unit goldens
do not pick up timestamps. Timings must not change fills or NAV.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager, nullcontext
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

PHASE_LABELS = {
    "init": "初始化",
    "exdiv": "除权图",
    "index_gate": "指数闸门",
    "day_spans": "日切片",
    "parking": "停泊开盘",
    "index_cut": "指数减半",
    "held_scan": "持仓扫描",
    "chase": "追买",
    "pool_buy": "名单买入",
    "post_group": "组后扫描",
    "eod": "收盘记账",
    "finish": "收尾",
    "v7_day": "v7日循环",
    "chronological_day": "时序日",
    "run_daily_day": "日线自定义日",
    "post_add": "加仓后再评",
    "day_loop": "日循环合计",
}

# Parent timers wrap children. Do not fold them into phase_share.
WRAPPER_PHASES = frozenset({"day_loop"})


class SimPhaseClock:
    """Accumulate named phase seconds and counters. Not on the fill hot path."""

    def __init__(self) -> None:
        self.started_at = datetime.now().astimezone()
        self.seconds: dict[str, float] = {}
        self.counts: dict[str, int] = {}
        self._open: dict[str, float] = {}

    def begin(self, name: str) -> None:
        self._open[name] = time.perf_counter()

    def end(self, name: str) -> None:
        started = self._open.pop(name, None)
        if started is None:
            return
        self.seconds[name] = self.seconds.get(name, 0.0) + (time.perf_counter() - started)

    def count(self, name: str, n: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + int(n)

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        self.begin(name)
        try:
            yield
        finally:
            self.end(name)

    def report(self, **extra: Any) -> dict[str, Any]:
        finished = datetime.now().astimezone()
        phases = {key: round(val, 6) for key, val in sorted(self.seconds.items())}
        leaves = {key: val for key, val in phases.items() if key not in WRAPPER_PHASES}
        leaf_total = sum(leaves.values())
        payload = {
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "finished_at": finished.isoformat(timespec="seconds"),
            "wall_s": round((finished - self.started_at).total_seconds(), 3),
            "phases_s": phases,
            "phase_share": {
                key: (round(val / leaf_total, 4) if leaf_total else 0.0)
                for key, val in leaves.items()
            },
            "counts": dict(sorted(self.counts.items())),
        }
        payload.update(extra)
        return payload


class _NullPhaseClock:
    def begin(self, name: str) -> None:
        return None

    def end(self, name: str) -> None:
        return None

    def count(self, name: str, n: int = 1) -> None:
        return None

    def phase(self, name: str):
        return nullcontext()


NULL_CLOCK = _NullPhaseClock()


def profile_sim_enabled(explicit: bool | None = None) -> bool:
    """Host default is on. Env 0/false/off or explicit False disables."""

    flag = os.environ.get("OSKH_PROFILE_SIM", "").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    if explicit is False:
        return False
    return True


def resolve_sim_clock(enabled: bool) -> SimPhaseClock | _NullPhaseClock:
    return SimPhaseClock() if enabled else NULL_CLOCK


def format_profile_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        f"  开始: {report.get('started_at', '')}",
        f"  结束: {report.get('finished_at', '')}",
        f"  墙钟: {float(report.get('wall_s', 0.0)):.1f}s",
    ]
    phases = report.get("phases_s") or {}
    share = report.get("phase_share") or {}
    if phases:
        bits = []
        for key, val in phases.items():
            label = PHASE_LABELS.get(key, key)
            if key in WRAPPER_PHASES:
                bits.append(f"{label} {float(val):.1f}s")
                continue
            pct = float(share.get(key, 0.0)) * 100.0
            bits.append(f"{label} {float(val):.1f}s ({pct:.0f}%)")
        lines.append("  模拟分相: " + " | ".join(bits))
    counts = report.get("counts") or {}
    if counts:
        lines.append("  埋点计数: " + " | ".join(f"{key}={val}" for key, val in counts.items()))
    return lines


def attach_host_profile(
    st: Any,
    clock: SimPhaseClock,
    *,
    strategy: str,
    rule_profile: str,
    load_s: dict[str, float],
    cache: str | None = None,
) -> dict[str, Any]:
    """Stamp ``st.sim_profile`` after a host ``run()``. Does not touch fills."""

    clock.count("trades", len(getattr(st, "trades", []) or []))
    phases_now = dict(clock.seconds)
    leftover_init = (
        float(load_s.get("t_sim_s", 0.0))
        - float(phases_now.get("day_loop", 0.0))
        - float(phases_now.get("finish", 0.0))
    )
    extra: dict[str, Any] = {
        "strategy": strategy,
        "rule_profile": rule_profile,
        "leftover_init_s": round(leftover_init, 3),
        "load_s": load_s,
    }
    if cache is not None:
        extra["cache"] = cache
    report = clock.report(**extra)
    st.sim_profile = report
    return report


def write_profile_sim(out_dir: Path, report: dict[str, Any]) -> Path:
    path = Path(out_dir) / "profile_sim.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path
