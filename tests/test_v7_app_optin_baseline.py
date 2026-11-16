"""Frozen standalone execution and real APP preparation/writer contracts."""

import json

import pytest
from scripts.research.generate_off_byte_baseline import byte_skip_reason
from scripts.research.generate_v7_app_baseline import CASES, FIXTURE, capture_case


@pytest.mark.parametrize("case", CASES)
def test_v7_app_optin_baseline(case, tmp_path):
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert set(golden["cases"]) == set(CASES)
    actual = capture_case(case, tmp_path / case)
    expected = golden["cases"][case]
    assert actual["evidence"] == expected["evidence"]
    assert actual["canonical"] == expected["canonical"]
    reason = byte_skip_reason(golden["pandas"])
    if reason:
        pytest.skip(reason)
    assert actual["sha256"] == expected["sha256"]


def test_record_refuses_existing_fixture():
    from unittest.mock import patch

    from scripts.research.generate_v7_app_baseline import main

    before = FIXTURE.read_bytes()
    with (
        patch("sys.argv", ["generate_v7_app_baseline.py", "--record"]),
        pytest.raises(SystemExit) as error,
    ):
        main()
    assert error.value.code == 2
    assert FIXTURE.read_bytes() == before
