"""Private dependency credentials and test isolation must keep their boundaries."""
from pathlib import Path
import re
import tomllib
from types import SimpleNamespace
from unittest.mock import Mock

import yaml

from tests import conftest as bootstrap


def workflow():
    root = Path(__file__).resolve().parents[1]
    return yaml.safe_load((root / ".github/workflows/python-tests.yml").read_text(encoding="utf-8"))


def test_private_read_token_is_scoped_to_install_and_not_stored_in_checkout():
    job = workflow()["jobs"]["pytest-and-gates"]
    steps = job["steps"]
    install = next(step for step in steps if step.get("name") == "Install dependencies")
    assert "MYQUANT_INFRA_READ_TOKEN" not in job["env"]
    assert install["env"]["MYQUANT_INFRA_READ_TOKEN"] == "${{ secrets.MYQUANT_INFRA_READ_TOKEN }}"
    assert install["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert install["env"]["PIP_NO_CACHE_DIR"] == "1"
    setup = next(step for step in steps if step.get("uses", "").startswith("actions/setup-python@"))
    assert "cache" not in setup["with"]
    assert install["run"].index('exit 1') < install["run"].index("pip install -r requirements.txt")
    assert 'GIT_ASKPASS="$askpass"' in install["run"]
    assert "https://$" not in install["run"]
    assert steps[0]["with"]["persist-credentials"] is False
    assert all("MYQUANT_INFRA_READ_TOKEN" not in step.get("env", {})
               for step in steps if step is not install)
    assert job["runs-on"] == "ubuntu-latest"
    assert job["env"]["BT_REQUIRE_SYMLINK_TESTS"] == "1"


def test_pytest_respects_explicit_external_basetemp(tmp_path, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "loguru", SimpleNamespace(logger=Mock()))
    chosen = tmp_path / "chosen"
    config = SimpleNamespace(option=SimpleNamespace(basetemp=str(chosen)), rootpath=tmp_path)
    bootstrap.pytest_configure(config)
    assert config.option.basetemp == str(chosen)
    assert not (tmp_path / "artifacts").exists()


def test_default_test_temp_does_not_overlap_the_repository(tmp_path, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "loguru", SimpleNamespace(logger=Mock()))
    config = SimpleNamespace(option=SimpleNamespace(basetemp=None), rootpath=tmp_path)
    bootstrap.pytest_configure(config)
    assert not Path(config.option.basetemp).is_relative_to(tmp_path)


def test_dependency_pins_agree_across_install_entrypoints():
    root = Path(__file__).resolve().parents[1]
    requirement = (root / "requirements-infra.txt").read_text(encoding="utf-8")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dependency = next(value for value in project["project"]["dependencies"]
                      if value.startswith("myquant-infra"))
    required_pin = re.findall(r"@([0-9a-f]{40})\b", requirement)
    assert len(required_pin) == 1
    assert re.findall(r"@([0-9a-f]{40})\b", dependency) == required_pin
    root_pandas = re.findall(r"^pandas==([^\s]+)$", (root / "requirements.txt").read_text(encoding="utf-8"), re.M)
    optional_pandas = re.findall(r"^pandas==([^\s]+)$", (root / "qlib_cost/requirements.txt").read_text(encoding="utf-8"), re.M)
    assert root_pandas == optional_pandas == ["3.0.6"]
