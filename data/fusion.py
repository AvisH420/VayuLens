"""Role 1: multi-source fusion with quality scoring.

Combines calibrated data from all sources into a single ``Measurement``
per grid cell per timestamp using inverse-variance weighted averaging.
"""

from __future__ import annotations

import math
from datetime import datetime

from contracts.grid_cell import GridCell
from contracts.measurement import Measurement


# ── Source reliability weights (inverse of typical variance) ──────────
# Higher = more trusted.  Ground stations > satellite-derived > reanalysis.
_SOURCE_WEIGHTS: dict[str, float] = {
    "cpcb": 1.0,                # official CAAQMS — highest trust
    "openaq": 0.9,              # ground stations via OpenAQ
    "waqi": 0.8,                # WAQI aggregator
    "open_meteo": 0.5,          # gridded model reanalysis (~10 km)
    "satellite_derived": 0.4,   # AOD → PM2.5 regression
    "gee": 0.3,                 # raw satellite value (pre-calibration)
}


def fuse_cell(
    cell: GridCell,
    calibrated_by_source: dict[str, dict[str, float | None]],
    timestamp: datetime,
) -> Measurement:
    """Fuse all calibrated sources for one cell into a single ``Measurement``.

    Uses inverse-variance (weight-based) averaging for pollutant fields
    and computes a composite quality score.
    """
    # ── Weighted fusion for each field ────────────────────────────────
    pm25  = _weighted_mean("pm25", calibrated_by_source)
    pm10  = _weighted_mean("pm10", calibrated_by_source)
    no2   = _weighted_mean("no2",  calibrated_by_source)

    # Satellite-specific
    aod   = _first_available("aod", calibrated_by_source)
    ai    = _first_available("aerosol_index", calibrated_by_source)

    # Missing gaseous pollutants
    so2   = _weighted_mean("so2",  calibrated_by_source)

    # Meteorology (single source — Open-Meteo)
    met = calibrated_by_source.get("open_meteo", {})
    temp       = met.get("temp")
    wind_speed = met.get("wind_speed")
    wind_dir   = met.get("wind_dir")

    # ── Quality score (0–1) ───────────────────────────────────────────
    n_sources = sum(
        1 for src, data in calibrated_by_source.items()
        if any(data.get(f) is not None for f in ("pm25", "pm10", "no2"))
    )
    source_score = min(1.0, n_sources / 4.0)          # 4 sources = perfect

    has_ground = any(
        src in calibrated_by_source and
        calibrated_by_source[src].get("pm25") is not None
        for src in ("cpcb", "openaq", "waqi")
    )
    proximity_score = 1.0 if has_ground else 0.3

    quality_score = round(0.5 * source_score + 0.5 * proximity_score, 3)
    quality_score = max(0.05, min(1.0, quality_score))

    # ── Uncertainty ───────────────────────────────────────────────────
    if pm25 is not None:
        # Use spread of source estimates as uncertainty
        pm25_vals = [
            v for src, data in calibrated_by_source.items()
            if (v := data.get("pm25")) is not None
        ]
        if len(pm25_vals) >= 2:
            mean_v = sum(pm25_vals) / len(pm25_vals)
            variance = sum((x - mean_v)**2 for x in pm25_vals) / len(pm25_vals)
            uncertainty = round(math.sqrt(variance), 2)
        else:
            uncertainty = round(pm25 * 0.2, 2)  # 20 % default
    else:
        uncertainty = 999.0

    def _clean_pollutant(v: float | None) -> float | None:
        if v is None or v < 0:
            return None
        return round(v, 2)

    return Measurement(
        cell_id=cell.cell_id,
        lat=cell.lat,
        lon=cell.lon,
        timestamp=timestamp,
        pm25=_clean_pollutant(pm25),
        pm10=_clean_pollutant(pm10),
        no2=_clean_pollutant(no2),
        so2=_clean_pollutant(so2),
        aod=_round_or_none(aod, 4),
        uv_aerosol_index=_round_or_none(ai, 2),
        temp=_round_or_none(temp, 1),
        wind_speed=_round_or_none(wind_speed, 1),
        wind_direction=_round_or_none(wind_dir, 1),
        quality_score=quality_score,
        uncertainty=uncertainty,
    )


def fuse_grid(
    grid: list[GridCell],
    aligned_data: dict[str, dict[str, dict[str, float | None]]],
    timestamp: datetime,
) -> list[Measurement]:
    """Fuse across the whole grid.

    ``aligned_data`` is ``{cell_id: {source: {field: value}}}``
    as produced by ``alignment.aggregate_by_source`` (one hour slice).
    """
    measurements: list[Measurement] = []
    cell_map = {c.cell_id: c for c in grid}

    for cell in grid:
        cell_sources = aligned_data.get(cell.cell_id, {})
        m = fuse_cell(cell, cell_sources, timestamp)
        measurements.append(m)

    return measurements


# ── helpers ───────────────────────────────────────────────────────────

def _weighted_mean(
    field: str,
    calibrated: dict[str, dict[str, float | None]],
) -> float | None:
    """Inverse-variance weighted mean of *field* across sources."""
    total_w = 0.0
    total_v = 0.0
    for src, data in calibrated.items():
        val = data.get(field)
        if val is not None:
            w = _SOURCE_WEIGHTS.get(src, 0.3)
            total_w += w
            total_v += w * val
    if total_w == 0:
        return None
    return total_v / total_w


def _first_available(
    field: str,
    calibrated: dict[str, dict[str, float | None]],
) -> float | None:
    """Return the first non-None value for *field* across sources."""
    for data in calibrated.values():
        v = data.get(field)
        if v is not None:
            return v
    return None


def _round_or_none(v: float | None, decimals: int = 2) -> float | None:
    return round(v, decimals) if v is not None else None
