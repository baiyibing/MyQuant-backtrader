from __future__ import annotations

import subprocess

import pytest

from scripts.research import run_minute_sensitivity_b as sensb


def test_current_tree_default_fence_explains_frozen_base_and_worktree():
    with pytest.raises(ValueError) as caught:
        sensb.check_source_fence()

    message = str(caught.value)
    assert sensb.BASE in message
    assert "git worktree add --detach <dir>" in message
    assert "frozen sensitivity-B experiment" in message
    assert "Drifted source paths:" in message


def test_missing_at_base_is_clear_value_error(monkeypatch):
    path = "backtest/research/added_after_base.py"
    monkeypatch.setattr(sensb, "source_hashes", lambda: {path: "current-digest"})

    def missing(*args, **kwargs):
        raise subprocess.CalledProcessError(128, args[0], stderr=b"missing at BASE")

    monkeypatch.setattr(sensb.subprocess, "check_output", missing)

    with pytest.raises(ValueError) as caught:
        sensb.check_source_fence()

    message = str(caught.value)
    assert path in message
    assert "Missing or unreadable at BASE" in message
    assert sensb.BASE in message


def test_allow_source_drift_marks_manifest_and_lists_paths(monkeypatch, capsys):
    path = "backtest/research/drifted.py"
    monkeypatch.setattr(sensb, "source_hashes", lambda: {path: "current-digest"})
    monkeypatch.setattr(sensb.subprocess, "check_output", lambda *args, **kwargs: b"base")

    fence = sensb.check_source_fence(allow_source_drift=True)
    manifest = sensb.source_fence_manifest(fence)

    assert manifest["checked_sources_match_base"] is False
    assert manifest["drifted_source_paths"] == [path]
    assert "RESULTS ARE NOT THE FROZEN SENSITIVITY-B EXPERIMENT" in capsys.readouterr().err
