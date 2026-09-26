"""Inspect load/validate requirements for sealed subset construction."""
from pathlib import Path
import ast
src = Path("backtest/research/joint_return_replay.py").read_text(encoding="utf-8")
# find content_hash / load bars seal checks
for needle in ["content_sha256", "def load_bars", "def validate_bars", "INPUT_BLOCKED", "reference_marks", "initial_lots"]:
    print("---", needle, src.count(needle))
# print relevant snippets by line
lines = src.splitlines()
for i, line in enumerate(lines, 1):
    if "content_sha256" in line or "def load_" in line or "def run_replay" in line or "bars_json" in line:
        if i < 400 or "def " in line or "content_sha" in line:
            print(f"{i}: {line}")
