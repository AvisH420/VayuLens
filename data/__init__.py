"""Role 1: data layer — source connectors, ~1km grid builder, calibration/fusion.

Public API::

    from data.pipeline import build_grid, fetch_source, calibrate, fuse, run_pipeline
"""

from data.pipeline import build_grid, fetch_source, calibrate, fuse, run_pipeline

__all__ = [
    "build_grid",
    "fetch_source",
    "calibrate",
    "fuse",
    "run_pipeline",
]
