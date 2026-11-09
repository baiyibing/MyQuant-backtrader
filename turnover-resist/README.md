# Turnover-resist source moved

The numerical Rust source is owned by MyQuant at
`myquant_factors/rust/turnover-resist`. BT retains no Rust implementation copy.
Build in that directory, or set `TURNOVER_RESIST_EXE` / `CARGO_TARGET_DIR` to
an explicit compiled artifact. The Python bridge is a compatibility import
from the required `myquant-research-factors` distribution.
