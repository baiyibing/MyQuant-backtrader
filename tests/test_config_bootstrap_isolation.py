# -*- coding: utf-8 -*-
"""配置引导隔离回归（codex 复核 R2，2026-09-09）。

背景：继承主仓相对 ``MINIQMT_CONFIG_PATH``（指向本仓不存在的
``config/runtime.ci.yaml``）时，``constants`` 模块体的 env 引导
（``QMTConstants.*`` 等 ``_get_env_int_in_range``）走
``runtime_config._log_yaml_failure``，其无守卫 import ``quant_logger``
回撞半初始化的 ``constants`` —— ``l2_analytics`` 链路循环导入，
``pytest tests/test_l2_aggregates.py`` 9 failed。

契约：缺失配置文件必须 fail-open（RuntimeWarning + 默认值），不得要求
评审者手工 ``env -u MINIQMT_CONFIG_PATH``（canonical 环境直接绿）。
循环导入是导入期现象，须以子进程复现，不能依赖进程内测试顺序。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _import_l2_with_env(config_path: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["MINIQMT_CONFIG_PATH"] = config_path
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-c", "import l2_analytics.ref_data"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_missing_relative_config_no_circular_import() -> None:
    """主仓相对路径（本仓无该文件）——import 必须 fail-open 而非循环导入。"""
    r = _import_l2_with_env("config/runtime.ci.yaml")
    assert r.returncode == 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"


def test_missing_absolute_config_no_circular_import(tmp_path: Path) -> None:
    """绝对路径缺失文件——同一 fail-open 契约。"""
    r = _import_l2_with_env(str(tmp_path / "nope.runtime.yaml"))
    assert r.returncode == 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
