"""Role 1: spatio-temporal alignment.

Snaps heterogeneous raw records (ground stations, satellite, met) onto the
~1 km analysis grid and resamples to a common **hourly UTC** time base.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

from contracts.grid_cell import GridCell


def build_cell_index(grid: list[GridCell]) -> dict[str, GridCell]:
    """Create a fast cell_id → GridCell lookup."""
    return {c.cell_id: c for c in grid}


def snap_to_grid(
    records: list[dict],
    grid: list[GridCell],
    max_distance_km: float = 2.0,
) -> list[dict]:
    """Attach the nearest ``cell_id`` to each raw record.

    Records beyond *max_distance_km* from any cell centroid are dropped.

    Uses a simple brute-force nearest-neighbour for small-to-medium grids
    (< 5 000 cells). For larger grids a KD-tree could be plugged in.
    """
    if not grid or not records:
        return []

    # Pre-compute cell coords as arrays
    cell_lats = np.array([c.lat for c in grid])
    cell_lons = np.array([c.lon for c in grid])
    cell_ids  = [c.cell_id for c in grid]

    snapped: list[dict] = []
    for rec in records:
        rlat = rec.get("lat")
        rlon = rec.get("lon")
        if rlat is None or rlon is None:
            continue

        # Haversine-lite: at ~28°N, 1° lat ≈ 111 km, 1° lon ≈ 98 km
        dlat = (cell_lats - rlat) * 111.0
        dlon = (cell_lons - rlon) * 98.0
        dists = np.sqrt(dlat**2 + dlon**2)

        idx = int(np.argmin(dists))
        if dists[idx] <= max_distance_km:
            rec = dict(rec)          # shallow copy
            rec["cell_id"] = cell_ids[idx]
            snapped.append(rec)

    return snapped


def resample_hourly(
    records: list[dict],
) -> dict[str, dict[str, list[dict]]]:
    """Resample records to hourly buckets keyed by ``(cell_id, hour_key)``.

    Returns::

        {
            cell_id: {
                "2025-07-19T10:00": [rec, rec, ...],
                ...
            },
            ...
        }

    Timestamps are floored to the hour.  Satellite records (daily) are
    replicated into each hour of their day.
    """
    buckets: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

    for rec in records:
        cell_id = rec.get("cell_id")
        dt_raw = rec.get("datetime", "")
        if not cell_id or not dt_raw:
            continue

        try:
            dt = datetime.fromisoformat(str(dt_raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        source = rec.get("source", "")

        if source == "gee":
            # Satellite records are daily — replicate to every hour
            for h in range(24):
                hour_dt = dt.replace(hour=h, minute=0, second=0, microsecond=0)
                hour_key = hour_dt.strftime("%Y-%m-%dT%H:00")
                enriched = dict(rec)
                enriched["_is_satellite_replicated"] = True
                buckets[cell_id][hour_key].append(enriched)
        else:
            # Floor to hour
            hour_dt = dt.replace(minute=0, second=0, microsecond=0)
            hour_key = hour_dt.strftime("%Y-%m-%dT%H:00")
            buckets[cell_id][hour_key].append(rec)

    return dict(buckets)


def aggregate_by_source(
    hourly_records: list[dict],
) -> dict[str, dict[str, float | None]]:
    """Within one cell-hour bucket, group records by source and take means.

    Returns::

        {
            "openaq": {"pm25": 82.3, "no2": 44.1, ...},
            "cpcb":   {"pm25": 86.0, ...},
            ...
        }
    """
    from collections import defaultdict as dd

    source_vals: dict[str, dict[str, list[float]]] = dd(lambda: dd(list))

    NUMERIC_FIELDS = [
        "pm25", "pm10", "no2", "so2", "co", "o3",
        "aod", "aerosol_index",
        "temp", "wind_speed", "wind_dir", "humidity",
        "value",     # GEE satellite generic value field
        "aqi",       # WAQI AQI
    ]

    for rec in hourly_records:
        src = rec.get("source", "unknown")
        for field in NUMERIC_FIELDS:
            v = rec.get(field)
            if v is not None:
                try:
                    source_vals[src][field].append(float(v))
                except (ValueError, TypeError):
                    pass

    result: dict[str, dict[str, float | None]] = {}
    for src, fields in source_vals.items():
        means: dict[str, float | None] = {}
        for field, vals in fields.items():
            means[field] = round(sum(vals) / len(vals), 4) if vals else None
        result[src] = means

    return result
