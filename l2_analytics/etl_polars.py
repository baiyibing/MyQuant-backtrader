"""Compatibility entrance for infra's optional Polars L2 engine."""
from l2_analytics._infra import require_l2


def configure_threads(threads):
    return require_l2("ingest.polars").configure_threads(threads)


def write_chunk(*args, **kwargs):
    return require_l2("ingest.polars").write_chunk(*args, **kwargs)


def merge_chunks(*args, **kwargs):
    return require_l2("ingest.polars").merge_chunks(*args, **kwargs)
