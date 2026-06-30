"""Role 1 — data layer stubs.

Builds the ~1km analysis grid, connects to ground/satellite/meteorology
sources, and calibrates + fuses everything into `Measurement` records.

All functions are stubs that raise NotImplementedError.
"""

from __future__ import annotations

from datetime import datetime

from contracts.grid_cell import GridCell
from contracts.measurement import Measurement


def build_grid(bbox: tuple[float, float, float, float], cell_km: float = 1.0) -> list[GridCell]:
    """Build the ~1km analysis grid covering a bounding box.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) of the area of interest.
        cell_km: Target cell edge length in kilometres.

    Returns:
        One `GridCell` per cell, with ward / land-use / road-density / industrial
        attributes joined in.
    """
    raise NotImplementedError


def fetch_source(source_name: str, since: datetime, until: datetime) -> list[dict]:
    """Pull raw records from a single connected source (ground station, sat, met).

    Args:
        source_name: Connector key, e.g. 'cpcb', 'gee_s5p', 'era5'.
        since: Inclusive start of the window (UTC).
        until: Exclusive end of the window (UTC).

    Returns:
        Raw, source-native records (not yet calibrated or gridded).
    """
    raise NotImplementedError


def calibrate(raw_records: list[dict], source_name: str) -> list[dict]:
    """Apply per-source calibration (bias correction, unit harmonisation).

    Args:
        raw_records: Output of `fetch_source`.
        source_name: Connector key the records came from.

    Returns:
        Calibrated records in a common intermediate representation.
    """
    raise NotImplementedError


def fuse(
    grid: list[GridCell],
    calibrated_by_source: dict[str, list[dict]],
    timestamp: datetime,
) -> list[Measurement]:
    """Fuse multi-source calibrated data onto the grid for one timestamp.

    Args:
        grid: The analysis grid from `build_grid`.
        calibrated_by_source: Calibrated records keyed by source name.
        timestamp: The observation time to produce measurements for (UTC).

    Returns:
        One `Measurement` per grid cell, with `quality_score` and `uncertainty`
        reflecting the fusion.
    """
    raise NotImplementedError
