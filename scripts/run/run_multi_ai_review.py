"""BT compatibility entry; shared implementation lives in grok-bot-ops."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _ops_bootstrap import run_ops  # noqa: E402


def main(argv=None):
    return run_ops('scripts/run/run_multi_ai_review.py', argv, profile='config/ops/bt-review.json')


if __name__ == "__main__":
    raise SystemExit(main())
