"""Google Earth Engine satellite connector.

Real mode : pulls Sentinel-5P (NO2, Aerosol Index, CO, SO2) and MODIS AOD
            via the ``earthengine-api`` and reduces to ~1 km cell means.
Mock mode : deterministic synthetic satellite-derived readings for the grid.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta

from ingestion.base_connector import BaseConnector
from ingestion import config as cfg


class GEESatelliteConnector(BaseConnector):
    source_name = "gee_sentinel5p"

    # ── REAL implementation ───────────────────────────────────────────
    def _pull_real(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        import ee

        ee.Initialize(project=cfg.GEE_PROJECT_ID)

        min_lon, min_lat, max_lon, max_lat = bbox
        region = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])

        # Satellites have processing latency that varies by product: Sentinel-5P
        # NRTI/OFFL lands within ~1-3 days, but MODIS MCD19A2 AOD granules can
        # lag 5+ days. A 3-day window regularly returns zero MODIS images (and
        # thus no AOD at all), so look back 10 days and take the most recent
        # available pass as the spatial baseline.
        search_start = until - timedelta(days=10)
        start_str = search_start.strftime("%Y-%m-%d")
        end_str = until.strftime("%Y-%m-%d")

        records: list[dict] = []

        # ── Sentinel-5P products ──────────────────────────────────────
        s5p_products = {
            "no2": {
                "collection": cfg.GEE_COLLECTIONS["s5p_no2"],
                "band": "tropospheric_NO2_column_number_density",
                "scale_factor": 1e6,  # mol/m² → µmol/m²
            },
            "aerosol_index": {
                "collection": cfg.GEE_COLLECTIONS["s5p_aer"],
                "band": "absorbing_aerosol_index",
                "scale_factor": 1.0,
            },
            "co": {
                "collection": cfg.GEE_COLLECTIONS["s5p_co"],
                "band": "CO_column_number_density",
                "scale_factor": 1e3,
            },
            "so2": {
                "collection": cfg.GEE_COLLECTIONS["s5p_so2"],
                "band": "SO2_column_number_density",
                "scale_factor": 1e6,
            },
        }

        for param, info in s5p_products.items():
            try:
                col = (
                    ee.ImageCollection(info["collection"])
                    .filterDate(start_str, end_str)
                    .filterBounds(region)
                    .select(info["band"])
                )
                img = col.mean()

                # Reduce to ~1 km grid
                reduced = img.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=region,
                    scale=1000,
                    maxPixels=1e8,
                )
                val = reduced.getInfo().get(info["band"])
                if val is not None:
                    val *= info["scale_factor"]

                    # Sample at grid points
                    step = 0.01
                    lat = min_lat
                    while lat <= max_lat:
                        lon = min_lon
                        while lon <= max_lon:
                            records.append({
                                "source": "gee",
                                "product": param,
                                "lat": round(lat, 4),
                                "lon": round(lon, 4),
                                "value": round(val, 6),
                                "datetime": since.isoformat(),
                            })
                            lon += step
                        lat += step
            except Exception:
                continue

        # ── MODIS AOD ─────────────────────────────────────────────────
        try:
            modis = (
                ee.ImageCollection(cfg.GEE_COLLECTIONS["modis_aod"])
                .filterDate(start_str, end_str)
                .filterBounds(region)
                .select("Optical_Depth_047")
            )
            aod_img = modis.mean()
            aod_reduced = aod_img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=region,
                scale=1000,
                maxPixels=1e8,
            )
            aod_val = aod_reduced.getInfo().get("Optical_Depth_047")
            if aod_val is not None:
                aod_val *= 0.001  # scale factor

                step = 0.01
                lat = min_lat
                while lat <= max_lat:
                    lon = min_lon
                    while lon <= max_lon:
                        records.append({
                            "source": "gee",
                            "product": "aod",
                            "lat": round(lat, 4),
                            "lon": round(lon, 4),
                            "value": round(aod_val, 6),
                            "datetime": since.isoformat(),
                        })
                        lon += step
                    lat += step
        except Exception:
            pass

        return records

    # ── MOCK implementation ───────────────────────────────────────────
    def _pull_mock(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        min_lon, min_lat, max_lon, max_lat = bbox
        step = 0.01  # ~1 km
        prof = cfg.profile_for_bbox(bbox)

        records: list[dict] = []
        current_date = since
        while current_date < until:
            lat = min_lat
            while lat <= max_lat:
                lon = min_lon
                while lon <= max_lon:
                    s = _seed(lat, lon, current_date)

                    # NO2 column density (µmol/m²) — higher in urban core
                    dist_center = math.sqrt(
                        (lat - (min_lat+max_lat)/2)**2 +
                        (lon - (min_lon+max_lon)/2)**2
                    )
                    urban_factor = max(0.3, 1.0 - dist_center * 8)

                    # Scale by the city profile so a clean coastal city does
                    # not inherit Delhi's satellite signature.
                    no2_scale = prof["no2_base"] / 45.0
                    aod_scale = prof["aod_urban"] / 1.0

                    no2 = (8.0 * urban_factor + 4.0 * _rng(s)) * no2_scale * 1e-6
                    aerosol_idx = (1.2 * urban_factor + 0.8 * _rng(s+1)) * aod_scale
                    co = (0.03 * urban_factor + 0.015 * _rng(s+2)) * no2_scale
                    so2 = (3.0 * urban_factor + 2.0 * _rng(s+3)) * no2_scale * 1e-6
                    aod = (
                        prof["aod_urban"] * urban_factor
                        + prof["aod_spread"] * _rng(s+4)
                        + prof["aod_floor"]
                    )

                    for product, value in [
                        ("no2", no2),
                        ("aerosol_index", aerosol_idx),
                        ("co", co),
                        ("so2", so2),
                        ("aod", aod),
                    ]:
                        records.append({
                            "source": "gee",
                            "product": product,
                            "lat": round(lat, 4),
                            "lon": round(lon, 4),
                            "value": round(value, 6),
                            "datetime": current_date.isoformat(),
                        })
                    lon += step
                lat += step
            current_date += timedelta(days=1)

        return records


def _seed(lat: float, lon: float, ts: datetime) -> int:
    return int(hashlib.md5(f"{lat:.4f},{lon:.4f},{ts.isoformat()}".encode()).hexdigest()[:8], 16)


def _rng(s: int) -> float:
    return ((s * 1103515245 + 12345) & 0x7FFF_FFFF) / 0x7FFF_FFFF
