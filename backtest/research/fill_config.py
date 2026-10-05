"""Shared minute sell policy. Defaults are derived from existing hooks, not book names.

Same-bar decisions may use a line or specified execution price, or a print at
or after the decision. A last-print decision cannot use earlier OHLC prints;
selling at the completed bar high is never a causal same-bar execution.
Next-bar orders always execute at the next eligible open (fill_at is ignored).
"""
from dataclasses import dataclass
import math
from types import MappingProxyType


@dataclass(frozen=True)
class FillConfig:
    trigger_basis: str = "bar_last"
    fill_timing: str = "this_bar"
    fill_at: str | float = "bar_last"

    def __post_init__(self):
        if self.trigger_basis not in {"bar_last", "bar_low"}:
            raise ValueError("trigger_basis must be bar_last or bar_low")
        if self.fill_timing not in {"this_bar", "next_bar_open"}:
            raise ValueError("fill_timing must be this_bar or next_bar_open")
        if isinstance(self.fill_at, str):
            if self.fill_at not in {"bar_open", "bar_high", "bar_low", "bar_last", "line"}:
                raise ValueError("invalid fill_at")
        elif isinstance(self.fill_at, bool) or not isinstance(self.fill_at, (int, float)) or not math.isfinite(self.fill_at) or self.fill_at <= 0:
            raise ValueError("fill_at must be a finite positive price")
        if self.fill_timing == "this_bar":
            if self.fill_at == "bar_high":
                raise ValueError("look-ahead: same-bar sell cannot fill at bar_high")
            if self.fill_at == "bar_open" or (self.trigger_basis == "bar_last" and self.fill_at == "bar_low"):
                raise ValueError("look-ahead: fill print precedes the same-bar decision")


DEFAULT_FILL_CONFIGS = MappingProxyType({
    "shared": FillConfig(),
    "hl": FillConfig("bar_low", "this_bar", "line"),
    "absolute_exit": FillConfig("bar_low", "this_bar", "line"),
    "version9_plan": FillConfig(),
    "trail": FillConfig(),
    "take_profit": FillConfig(),
    "force_sell": FillConfig(),
    "close_clear": FillConfig(),
})


def default_fill_config(minute_stop_trigger="close", *, hooks=None, absolute_exit=False):
    if absolute_exit or (hooks and "bind_absolute_exit" in hooks):
        return DEFAULT_FILL_CONFIGS["absolute_exit"]
    return DEFAULT_FILL_CONFIGS["hl" if minute_stop_trigger == "hl" else "shared"]


def book_fill_defaults(hooks, minute_stop_trigger="close"):
    """Per-book path map derived solely from the existing hooks and H/L flag.

    Callback and time exits still decide on the last print. H/L fixed upward
    targets retain their line/open fill; custom callbacks retain last prints.
    """
    stop = (FillConfig(fill_timing="next_bar_open") if hooks.get("minute_open")
            else default_fill_config(minute_stop_trigger, hooks=hooks))
    target = (DEFAULT_FILL_CONFIGS["hl"] if minute_stop_trigger == "hl"
              and not callable(hooks.get("exit_plan"))
              and not callable(hooks.get("sell_gate")) else DEFAULT_FILL_CONFIGS["take_profit"])
    return MappingProxyType(dict(stop=stop, take_profit=target,
                                 trail=DEFAULT_FILL_CONFIGS["trail"],
                                 force_sell=DEFAULT_FILL_CONFIGS["force_sell"],
                                 close_clear=DEFAULT_FILL_CONFIGS["close_clear"]))


def is_open_fill(reason):
    """Preserve legacy gap metadata; queued executions are opening quotes too."""
    return reason == "stop_loss:gap_open" or reason.endswith(":next_open")
