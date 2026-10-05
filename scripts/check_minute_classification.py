"""Fast, data-free gate for the registered minute strategy catalog."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.research.minute_classification import minute_strategy_entries


def main() -> int:
    try:
        entries = minute_strategy_entries()
    except RuntimeError as exc:
        print(f"Minute classification gate FAILED:\n{exc}", file=sys.stderr)
        return 1
    print(f"Minute classification gate OK: {len(entries)} strategies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
