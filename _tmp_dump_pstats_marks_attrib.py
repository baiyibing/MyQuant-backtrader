"""Dump cProfile pstats for marks attribution at be3ce4f (attribution only)."""
import pstats
from pathlib import Path

phase = Path(r"D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase")
pstats_path = phase / "cprofile_B_be3ce4f_marks.pstats"
out_path = phase / "cprofile_B_be3ce4f_marks_dump.txt"

with out_path.open("w", encoding="utf-8") as f:
    st = pstats.Stats(str(pstats_path), stream=f)
    st.sort_stats("tottime").print_stats(45)
    st.sort_stats("cumulative").print_stats(45)
    st.print_callers("update_marks")
    st.print_callees("update_marks")
    st.print_callers("_bar_number")
    st.print_callees("_bar_number")
    st.print_callers("_bar_decimal_unchecked")
    st.print_callers("expire")
    st.print_callees("expire")
    st.print_callers("deepcopy")
    st.print_callers("__getitem__")
    st.print_callees("__getitem__")
    st.print_callers(r"joint_return_validate_v2")
print(f"wrote {out_path}")
print(f"total_tt={pstats.Stats(str(pstats_path)).total_tt:.3f}")
