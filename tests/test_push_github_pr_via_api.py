from __future__ import annotations

import pytest

from scripts.ops.push_github_pr_via_api import (
    is_protected_branch,
    parse_github_repo,
    parse_name_status,
)


@pytest.mark.parametrize(
    "url, owner, name",
    [
        ("https://github.com/baiyibing/MyQuant-backtrader.git", "baiyibing", "MyQuant-backtrader"),
        ("https://github.com/baiyibing/MyQuant-backtrader", "baiyibing", "MyQuant-backtrader"),
        ("git@github.com:baiyibing/MyQuant-backtrader.git", "baiyibing", "MyQuant-backtrader"),
        (
            "ssh://git@github.com/baiyibing/MyQuant-backtrader.git",
            "baiyibing",
            "MyQuant-backtrader",
        ),
    ],
)
def test_parse_github_repo(url: str, owner: str, name: str) -> None:
    repo = parse_github_repo(url)
    assert repo.owner == owner
    assert repo.name == name
    assert repo.slug == f"{owner}/{name}"


def test_parse_github_repo_rejects_non_github() -> None:
    with pytest.raises(ValueError, match="not a github.com remote"):
        parse_github_repo("http://netgear.seetell.net:13001/baiyibing/MyQuant-backtrader.git")


def test_protected_branches() -> None:
    assert is_protected_branch("master")
    assert is_protected_branch("main")
    assert not is_protected_branch("feat/v6-50-53-parking-skim-index")


def test_parse_name_status_rename_becomes_delete_and_add() -> None:
    assert parse_name_status("M\ta.py\nR100\told.py\tnew.py\nD\tgone.py\n") == [
        ("M", "a.py"),
        ("D", "old.py"),
        ("A", "new.py"),
        ("D", "gone.py"),
    ]
