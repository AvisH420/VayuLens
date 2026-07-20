"""Role 1: ~1 km grid builder.

Tessellates a bounding box into ~1 km cells and attaches static context
(ward, land-use class, road density, industrial flag) from OSM data.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict

from contracts.grid_cell import GridCell


# ── Delhi ward definitions (approximate centroids) ────────────────────
_DELHI_WARDS: list[tuple[str, float, float, float, float]] = [
    ("Civil Lines",     28.68, 77.19, 28.71, 77.24),
    ("Karol Bagh",      28.64, 77.18, 28.67, 77.22),
    ("Sadar Paharganj", 28.63, 77.20, 28.66, 77.24),
    ("Chandni Chowk",   28.64, 77.22, 28.67, 77.25),
    ("South Delhi",     28.50, 77.19, 28.57, 77.28),
    ("New Delhi",       28.58, 77.19, 28.64, 77.25),
    ("West Delhi",      28.60, 77.05, 28.70, 77.18),
    ("North Delhi",     28.70, 77.15, 28.80, 77.25),
    ("North East",      28.67, 77.25, 28.75, 77.33),
    ("East Delhi",      28.60, 77.27, 28.68, 77.35),
    ("South East",      28.50, 77.25, 28.60, 77.32),
    ("South West",      28.45, 77.05, 28.55, 77.19),
    ("Shahdara",        28.65, 77.28, 28.72, 77.34),
    ("North West",      28.72, 77.05, 28.88, 77.18),
]

_GOA_WARDS: list[tuple[str, float, float, float, float]] = [
    ("North Goa",  15.38, 73.67, 15.80, 74.15),
    ("South Goa",  14.89, 73.80, 15.38, 74.34),
]


def _find_ward(
    lat: float, lon: float,
    wards: list[tuple[str, float, float, float, float]],
) -> str:
    """Return the ward whose bounding box contains (lat, lon), else 'Unknown'."""
    for name, lat_lo, lon_lo, lat_hi, lon_hi in wards:
        if lat_lo <= lat <= lat_hi and lon_lo <= lon <= lon_hi:
            return name
    return "Unknown"


def _detect_wards(
    bbox: tuple[float, float, float, float],
) -> list[tuple[str, float, float, float, float]]:
    """Pick the ward table based on which city the bbox most likely covers."""
    min_lon, min_lat, max_lon, max_lat = bbox
    center_lat = (min_lat + max_lat) / 2
    if center_lat > 20:
        return _DELHI_WARDS
    return _GOA_WARDS


def tessellate(
    bbox: tuple[float, float, float, float],
    cell_km: float = 1.0,
) -> list[dict]:
    """Create a regular lat/lon grid covering *bbox*.

    Returns raw cell dicts with ``cell_id``, ``lat``, ``lon`` fields.
    One degree latitude ≈ 111 km, so step ≈ cell_km / 111.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    step = cell_km / 111.0  # ~0.009° for 1 km

    cells: list[dict] = []
    lat = min_lat
    while lat <= max_lat:
        lon = min_lon
        while lon <= max_lon:
            rlat = round(lat, 2)
            rlon = round(lon, 2)
            cells.append({
                "cell_id": f"grid_{rlat}_{rlon}",
                "lat": rlat,
                "lon": rlon,
            })
            lon += step
        lat += step

    return cells


def attach_context(
    cells: list[dict],
    osm_records: list[dict],
    bbox: tuple[float, float, float, float],
) -> list[GridCell]:
    """Join OSM-derived context onto raw cell dicts and return ``GridCell`` list.

    Context attached:
      * ``ward``           — from built-in ward boundaries
      * ``land_use_class`` — from OSM landuse features (nearest)
      * ``road_density``   — road node count → km/km² estimate
      * ``industrial_flag``— True if any industrial feature is nearby
    """
    wards = _detect_wards(bbox)

    # Index OSM records by rounded (lat, lon)
    landuse_map: dict[tuple[float, float], str] = {}
    road_map: dict[tuple[float, float], int] = {}
    industrial_set: set[tuple[float, float]] = set()

    for rec in osm_records:
        key = (round(rec.get("lat", 0), 2), round(rec.get("lon", 0), 2))
        ftype = rec.get("feature_type", "")
        if ftype == "landuse":
            landuse_map[key] = _classify_landuse(rec.get("landuse", ""))
        elif ftype == "road":
            road_map[key] = rec.get("node_count", 10)
        elif ftype == "industrial":
            industrial_set.add(key)

    grid_cells: list[GridCell] = []
    for c in cells:
        key = (c["lat"], c["lon"])
        ward = _find_ward(c["lat"], c["lon"], wards)
        land_use = landuse_map.get(key, "mixed")
        road_nodes = road_map.get(key, 10)
        road_density = round(road_nodes * 0.15, 2)  # heuristic: nodes → km/km²
        industrial = key in industrial_set

        grid_cells.append(GridCell(
            cell_id=c["cell_id"],
            lat=c["lat"],
            lon=c["lon"],
            ward=ward,
            land_use_class=land_use,
            road_density=road_density,
            industrial_flag=industrial,
        ))

    return grid_cells


def _classify_landuse(raw: str) -> str:
    """Map raw OSM landuse tag values to the contract's five classes."""
    raw = raw.lower()
    if raw in ("residential", "garages", "allotments"):
        return "residential"
    if raw in ("commercial", "retail"):
        return "commercial"
    if raw in ("industrial", "railway", "quarry", "landfill"):
        return "industrial"
    if raw in ("forest", "grass", "meadow", "farmland", "orchard",
               "vineyard", "cemetery", "recreation_ground", "park"):
        return "green"
    return "mixed"
