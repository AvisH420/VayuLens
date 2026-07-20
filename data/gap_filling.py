"""Role 1: spatial gap-filling via Inverse Distance Weighting (IDW).

For cells that have no direct reading after fusion, interpolate from
neighbouring cells that do have readings.  Gap-filled cells receive a
quality-score penalty so downstream models can weight by reliability.
"""

from __future__ import annotations

import math

from contracts.measurement import Measurement


def fill_gaps(
    measurements: list[Measurement],
    max_neighbours: int = 8,
    max_distance_km: float = 5.0,
    power: float = 2.0,
    gap_quality_cap: float = 0.5,
) -> list[Measurement]:
    """IDW gap-fill for cells with missing PM2.5.

    Args:
        measurements: Full grid of Measurement records (one per cell).
                      Cells with ``pm25 is None`` are gap-filled.
        max_neighbours: Max number of neighbours to interpolate from.
        max_distance_km: Max interpolation radius.
        power: IDW power parameter (default 2 = inverse-square).
        gap_quality_cap: Max quality_score for a gap-filled cell.

    Returns:
        The same list with gap-filled cells updated in place.
    """
    # Separate cells with readings vs gaps
    has_data: list[Measurement] = []
    gaps: list[int] = []

    for i, m in enumerate(measurements):
        if m.pm25 is not None:
            has_data.append(m)
        else:
            gaps.append(i)

    if not has_data or not gaps:
        return measurements

    # Pre-extract coords of cells with data (parsed from cell_id)
    data_coords = [_cell_coords(m.cell_id) for m in has_data]
    data_lats = [c[0] for c in data_coords]
    data_lons = [c[1] for c in data_coords]

    for idx in gaps:
        gap = measurements[idx]
        glat, glon = _cell_coords(gap.cell_id)

        # Find nearest neighbours with data
        neighbours: list[tuple[float, Measurement]] = []
        for j, dm in enumerate(has_data):
            d = _haversine_km(glat, glon, data_lats[j], data_lons[j])
            if d <= max_distance_km and d > 0:
                neighbours.append((d, dm))

        if not neighbours:
            continue

        # Sort by distance, take top-N
        neighbours.sort(key=lambda x: x[0])
        neighbours = neighbours[:max_neighbours]

        # IDW interpolation
        pm25  = _idw([n.pm25  for _, n in neighbours], [d for d, _ in neighbours], power)
        pm10  = _idw([n.pm10  for _, n in neighbours], [d for d, _ in neighbours], power)
        no2   = _idw([n.no2   for _, n in neighbours], [d for d, _ in neighbours], power)
        aod   = _idw([n.aod   for _, n in neighbours], [d for d, _ in neighbours], power)
        ai    = _idw([n.aerosol_index for _, n in neighbours], [d for d, _ in neighbours], power)
        temp  = _idw([n.temp  for _, n in neighbours], [d for d, _ in neighbours], power)
        ws    = _idw([n.wind_speed for _, n in neighbours], [d for d, _ in neighbours], power)
        wd    = _idw([n.wind_dir   for _, n in neighbours], [d for d, _ in neighbours], power)

        # Quality downgrade for gap-filled cells
        quality = min(gap_quality_cap, gap.quality_score)

        # Uncertainty: inflate based on mean interpolation distance
        mean_dist = sum(d for d, _ in neighbours) / len(neighbours)
        unc = round((pm25 or 50) * 0.3 * (1 + mean_dist / max_distance_km), 2) if pm25 else 999.0

        measurements[idx] = Measurement(
            cell_id=gap.cell_id,
            timestamp=gap.timestamp,
            pm25=_round_or_none(pm25),
            pm10=_round_or_none(pm10),
            no2=_round_or_none(no2),
            aod=_round_or_none(aod, 4),
            aerosol_index=_round_or_none(ai, 2),
            temp=_round_or_none(temp, 1),
            wind_speed=_round_or_none(ws, 1),
            wind_dir=_round_or_none(wd, 1),
            quality_score=quality,
            uncertainty=unc,
        )

    return measurements


# ── helpers ───────────────────────────────────────────────────────────

def _idw(
    values: list[float | None],
    distances: list[float],
    power: float,
) -> float | None:
    """Inverse distance weighted average, skipping None values."""
    total_w = 0.0
    total_v = 0.0
    for v, d in zip(values, distances):
        if v is not None and d > 0:
            w = 1.0 / (d ** power)
            total_w += w
            total_v += w * v
    if total_w == 0:
        return None
    return total_v / total_w


def _cell_coords(cell_id: str) -> tuple[float, float]:
    """Parse lat, lon from cell_id = 'grid_{lat}_{lon}'."""
    parts = cell_id.split("_")
    return float(parts[1]), float(parts[2])


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in km using the Haversine formula."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _round_or_none(v: float | None, decimals: int = 2) -> float | None:
    return round(v, decimals) if v is not None else None
