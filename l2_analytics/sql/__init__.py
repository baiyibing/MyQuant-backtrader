"""Compatibility access to SQL resources shipped by the optional infra package.

Use sql_dir() for the installed resource directory, or load_template(name).
There is no second host copy of the SQL files.
"""
from l2_analytics.templates import load_template, sql_dir

__all__ = ["load_template", "sql_dir"]
