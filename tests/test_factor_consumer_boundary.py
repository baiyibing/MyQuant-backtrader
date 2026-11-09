"""BT owns the call policy, MyQuant owns the factor function objects."""
import importlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.gates.verify_factor_consumer_boundary import ROOT, violations


def test_migrated_factor_sources_stay_out_of_bt():
    assert violations(ROOT) == []


def test_yearly_subprocess_keeps_bt_admission_entry():
    from scripts.tr import backfill_turnover_resistance_yearly as yearly
    assert yearly.BACKFILL == ROOT / "scripts/tr/backfill_turnover_resistance_bands.py"


@pytest.mark.parametrize("old,new", [
    ("qlib_cost.cyq", "myquant_factors.cyq"),
    ("qlib_cost.distribution_of_chips", "myquant_factors.distribution_of_chips"),
    ("oskh_factors.chip.core", "myquant_factors.chip.core"),
    ("oskh_factors.chip.bands", "myquant_factors.chip.bands"),
    ("oskh_factors.weekly_macd_divergence", "myquant_factors.weekly_macd_divergence"),
    ("oskh_factors.bridge.turnover_resist", "myquant_factors.bridge.turnover_resist"),
])
def test_compatibility_names_resolve_to_the_shared_module(old, new):
    assert importlib.import_module(old) is importlib.import_module(new)


def test_missing_myquant_dependency_fails_without_local_factor_fallback(tmp_path):
    code = '''
import importlib.abc, sys
class MissingFactors(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] == 'myquant_factors':
            raise ModuleNotFoundError('required MyQuant factor dependency missing')
sys.meta_path.insert(0, MissingFactors())
import qlib_cost
'''
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "required MyQuant factor dependency missing" in result.stderr
