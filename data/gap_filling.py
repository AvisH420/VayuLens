"""Role 1: spatial gap-filling via Inverse Distance Weighting (IDW).

For cells that have no direct reading after fusion, interpolate from
neighbouring cells that do have readings.  Gap-filled cells receive a
quality-score penalty so downstream models can weight by reliability.
"""

from __future__ import annotations

import math

from contracts.measurement import Measurement


# Fields interpolated independently of one another.  Wind and temperature
# come from a ~10 km reanalysis grid, so only a handful of cells receive them
# directly even when almost every cell already has PM2.5 from satellite AOD.
_FILLABLE_FIELDS = (
    "pm25", "pm10", "no2", "aod", "uv_aerosol_index",
    "temp", "wind_speed", "wind_direction",
)

_FIELD_DECIMALS = {"aod": 4, "uv_aerosol_index": 2, "temp": 1, "wind_speed": 1, "wind_direction": 1}


def fill_gaps(
    measurements: list[Measurement],
    max_neighbours: int = 8,
    max_distance_km: float = 5.0,
    power: float = 2.0,
    gap_quality_cap: float = 0.5,
) -> list[Measurement]:
    """IDW gap-fill, applied per field rather than per cell.

    Each field in ``_FILLABLE_FIELDS`` is filled independently: a cell that
    already has PM2.5 but no wind still gets its wind interpolated.  Filling
    on a whole-cell basis (gated on ``pm25 is None``) left meteorology at
    ~1% coverage, since satellite AOD gives nearly every cell a PM2.5 value
    and the cell was therefore never considered a gap.

    Args:
        measurements: Full grid of Measurement records (one per cell).
        max_neighbours: Max number of neighbours to interpolate from.
        max_distance_km: Max interpolation radius.
        power: IDW power parameter (default 2 = inverse-square).
        gap_quality_cap: Max quality_score for a cell whose PM2.5 was filled.

    Returns:
        The same list with gap-filled cells updated in place.
    """
    if not measurements:
        return measurements

    coords = [_cell_coords(m.cell_id) for m in measurements]

    # Donor pool per field: cells that actually carry a value for it.
    donors: dict[str, list[int]] = {
        field: [i for i, m in enumerate(measurements) if getattr(m, field, None) is not None]
        for field in _FILLABLE_FIELDS
    }

    # Nothing to do if every field is either fully present or fully absent.
    if all(len(d) in (0, len(measurements)) for d in donors.values()):
        return measurements

    for idx, m in enumerate(measurements):
        missing = [f for f in _FILLABLE_FIELDS if getattr(m, f, None) is None]
        if not missing:
            continue

        lat, lon = coords[idx]
        updates: dict[str, float | None] = {}
        fill_distances: list[float] = []

        for field in missing:
            pool = donors[field]
            if not pool:
                continue

            neighbours: list[tuple[float, int]] = []
            for j in pool:
                if j == idx:
                    continue
                d = _haversine_km(lat, lon, coords[j][0], coords[j][1])
                if 0 < d <= max_distance_km:
                    neighbours.append((d, j))

            if not neighbours:
                continue

            neighbours.sort(key=lambda x: x[0])
            neighbours = neighbours[:max_neighbours]
            dists = [d for d, _ in neighbours]

            if field == "wind_direction":
                value = _idw_circular(
                    [measurements[j].wind_direction for _, j in neighbours], dists, power
                )
            else:
                value = _idw(
                    [getattr(measurements[j], field) for _, j in neighbours], dists, power
                )

            if value is None:
                continue

            updates[field] = round(value, _FIELD_DECIMALS.get(field, 2))
            fill_distances.append(sum(dists) / len(dists))

        if not updates:
            continue

        # Only penalise quality when the pollutant itself was interpolated.
        # Borrowing wind from 3 km away says nothing about the PM2.5 reading.
        if "pm25" in updates:
            quality = min(gap_quality_cap, m.quality_score)
            mean_dist = sum(fill_distances) / len(fill_distances)
            uncertainty = round(
                updates["pm25"] * 0.3 * (1 + mean_dist / max_distance_km), 2
            )
        else:
            quality = m.quality_score
            uncertainty = m.uncertainty

        measurements[idx] = m.model_copy(
            update={**updates, "quality_score": quality, "uncertainty": uncertainty}
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


def _idw_circular(
    values: list[float | None],
    distances: list[float],
    power: float,
) -> float | None:
    """IDW average of compass bearings, in degrees.

    Bearings wrap at 360, so a linear mean of 350 and 10 yields 180 -- the
    opposite direction.  Average the unit vectors instead and convert back.
    """
    total_w = 0.0
    sin_sum = 0.0
    cos_sum = 0.0
    for v, d in zip(values, distances):
        if v is not None and d > 0:
            w = 1.0 / (d ** power)
            rad = math.radians(v)
            total_w += w
            sin_sum += w * math.sin(rad)
            cos_sum += w * math.cos(rad)

    if total_w == 0 or (sin_sum == 0 and cos_sum == 0):
        return None
    return math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0


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
