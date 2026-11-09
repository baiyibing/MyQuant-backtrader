"""BT admits installed infra entrypoints; OP04 processing tests belong to infra."""
from importlib import import_module
from pathlib import Path
import socket

import pytest

from scripts.gates.verify_infra_consumer_boundary import RETIRED, violations
from tests.test_infra_consumer_boundary import minimal_consumer_tree


LEGACY_SOURCES = (
    "oskh_data/cninfo_economic_date_targets.py",
    "scripts/data/export_cninfo_economic_date_targets.py",
    "scripts/data/validate_cninfo_economic_date_evidence.py",
)


@pytest.mark.parametrize("name", LEGACY_SOURCES)
def test_retired_cninfo_processing_cannot_return(tmp_path, name):
    assert name in RETIRED
    minimal_consumer_tree(tmp_path)
    source = tmp_path / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# restored producer\n", encoding="utf-8")
    assert f"retired source restored: {name}" in violations(tmp_path)
    assert not (Path(__file__).resolve().parents[1] / name).exists()


@pytest.mark.parametrize("module_name", (
    "myquant_infra.disclosure.export_cninfo_economic_date_targets",
    "myquant_infra.disclosure.cninfo_economic_date_recommendations",
))
def test_documented_infra_entrypoints_load_and_show_help_offline(monkeypatch, capsys, module_name):
    def offline(*args, **kwargs):
        raise AssertionError("consumer admission must not access the network")

    monkeypatch.setattr(socket.socket, "connect", offline)
    monkeypatch.setattr(socket, "create_connection", offline)
    module = import_module(module_name)
    with pytest.raises(SystemExit) as result:
        module.main(["--help"])
    assert result.value.code == 0
    help_text = capsys.readouterr().out
    assert "--assembled-events" in help_text and "--universe" in help_text
