"""BT compatibility entry; shared implementation lives in grok-bot-ops."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _ops_bootstrap import run_ops  # noqa: E402


def main(argv=None):
    return run_ops('scripts/ops/push_github_pr_via_api.py', argv)


if __name__ == "__main__":
    raise SystemExit(main())
