"""Role 1 — ingestion stubs.

Schedules and performs raw pulls from upstream sources, including the Google
Earth Engine (GEE) satellite pipeline. Hands raw records to `data/` for
calibration and fusion.

All functions are stubs that raise NotImplementedError.
"""

from __future__ import annotations

from datetime import datetime


def schedule_pull(source_name: str, cron: str) -> str:
    """Register a recurring raw pull for a source.

    Args:
        source_name: Connector key, e.g. 'cpcb', 'gee_s5p', 'era5'.
        cron: Cron expression describing the pull cadence.

    Returns:
        A job id for the registered schedule.
    """
    raise NotImplementedError


def pull_raw(source_name: str, since: datetime, until: datetime) -> list[dict]:
    """Perform a one-off raw pull for a source over a time window.

    Args:
        source_name: Connector key.
        since: Inclusive start (UTC).
        until: Exclusive end (UTC).

    Returns:
        Raw, source-native records persisted to the raw store.
    """
    raise NotImplementedError


def pull_gee_satellite(
    product: str,
    bbox: tuple[float, float, float, float],
    since: datetime,
    until: datetime,
) -> list[dict]:
    """Pull a satellite product via the Google Earth Engine pipeline.

    Args:
        product: GEE product id (e.g. Sentinel-5P NO2, MODIS AOD).
        bbox: (min_lon, min_lat, max_lon, max_lat) area of interest.
        since: Inclusive start (UTC).
        until: Exclusive end (UTC).

    Returns:
        Raw raster/tabular records (AOD, aerosol index, NO2, ...) for `data/`.
    """
    raise NotImplementedError
