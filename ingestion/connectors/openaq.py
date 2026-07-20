"""OpenAQ API v3 connector.

Real mode : paginated GET to api.openaq.org/v3 with X-API-Key header.
Mock mode : deterministic synthetic ground-station readings for Indian
            cities (PM2.5, PM10, NO2, SO2, CO, O3).
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta

import requests

from ingestion.base_connector import BaseConnector
from ingestion import config as cfg

# ── Known CAAQMS-class stations in Delhi (lat, lon, name) ─────────────
_DELHI_STATIONS = [
    (28.6508, 77.3152, "Anand Vihar"),
    (28.5918, 77.2273, "ITO"),
    (28.6862, 77.2217, "DTU"),
    (28.5672, 77.2510, "Lajpat Nagar"),
    (28.6336, 77.2195, "Pusa, New Delhi"),
    (28.7501, 77.1177, "Narela"),
    (28.5494, 77.2001, "R.K. Puram"),
    (28.6127, 77.2773, "Pragati Maidan"),
    (28.5244, 77.1855, "Dwarka Sector 8"),
    (28.6289, 77.3070, "Patparganj"),
    (28.5631, 77.1594, "Najafgarh"),
    (28.7041, 77.1025, "Bawana"),
    (28.4985, 77.3066, "Okhla Phase 2"),
    (28.5733, 77.1580, "Palam"),
    (28.6515, 77.1583, "Punjabi Bagh"),
    (28.6804, 77.1531, "Rohini"),
    (28.5435, 77.2709, "Sarita Vihar"),
    (28.5985, 77.1632, "Moti Bagh"),
]

_PANAJI_STATIONS = [
    (15.4989, 73.8278, "Panaji - Patto"),
    (15.3960, 73.8758, "Margao"),
    (15.5376, 73.8665, "Mapusa"),
]


def _seed(lat: float, lon: float, ts: datetime) -> int:
    """Deterministic seed from coordinates + timestamp."""
    raw = f"{lat:.4f},{lon:.4f},{ts.isoformat()}"
    return int(hashlib.md5(raw.encode()).hexdigest()[:8], 16)


def _pseudo(seed: int) -> float:
    """Simple LCG pseudo-random in [0, 1)."""
    return ((seed * 1103515245 + 12345) & 0x7FFF_FFFF) / 0x7FFF_FFFF


class OpenAQConnector(BaseConnector):
    source_name = "openaq"

    # ── REAL implementation ───────────────────────────────────────────
    def _pull_real(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        min_lon, min_lat, max_lon, max_lat = bbox
        headers = {"X-API-Key": cfg.OPENAQ_API_KEY}
        params = {
            "bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}",
            "limit": 100,
            "page": 1,
        }

        # Step 1: get locations
        locations_url = f"{cfg.OPENAQ_BASE_URL}/locations"
        resp = requests.get(locations_url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        locations = resp.json().get("results", [])

        records: list[dict] = []
        for loc in locations:
            loc_id = loc.get("id")
            lat = loc.get("coordinates", {}).get("latitude")
            lon = loc.get("coordinates", {}).get("longitude")
            name = loc.get("name", "")

            # Skip locations outside bbox
            if lat is None or lon is None:
                continue
            if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                continue

            # Step 2: get measurements for each location
            self._throttle()
            meas_url = f"{cfg.OPENAQ_BASE_URL}/locations/{loc_id}/measurements"
            meas_params = {
                "date_from": since.isoformat(),
                "date_to": until.isoformat(),
                "limit": 1000,
            }
            try:
                mresp = requests.get(meas_url, headers=headers, params=meas_params, timeout=30)
                mresp.raise_for_status()
                measurements = mresp.json().get("results", [])
            except Exception as exc:
                # If a specific station 404s (no data today), just skip it and continue
                continue

            for m in measurements:
                records.append({
                    "source": "openaq",
                    "station_name": name,
                    "lat": lat,
                    "lon": lon,
                    "parameter": m.get("parameter", {}).get("name", ""),
                    "value": m.get("value"),
                    "unit": m.get("parameter", {}).get("units", ""),
                    "datetime": m.get("period", {}).get("datetimeFrom", {}).get("utc", ""),
                })

        return records

    # ── MOCK implementation ───────────────────────────────────────────
    def _pull_mock(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        min_lon, min_lat, max_lon, max_lat = bbox

        # Pick stations inside bbox
        stations = [
            s for s in (_DELHI_STATIONS + _PANAJI_STATIONS)
            if min_lat <= s[0] <= max_lat and min_lon <= s[1] <= max_lon
        ]
        if not stations:
            stations = _DELHI_STATIONS[:5]

        records: list[dict] = []
        ts = since
        while ts < until:
            for lat, lon, name in stations:
                s = _seed(lat, lon, ts)
                hour = ts.hour

                # Diurnal pattern: peaks ~9 AM and ~9 PM
                diurnal = 1.0 + 0.3 * math.sin(math.pi * (hour - 3) / 12)

                pm25_base = 85.0 * diurnal + 40 * (_pseudo(s) - 0.5)
                pm10_base = pm25_base * 1.8 + 20 * _pseudo(s + 1)
                no2_base = 45.0 * diurnal + 20 * (_pseudo(s + 2) - 0.5)
                so2_base = 12.0 + 8 * (_pseudo(s + 3) - 0.3)
                co_base = 1200.0 + 600 * (_pseudo(s + 4) - 0.5)
                o3_base = 35.0 + 25 * (_pseudo(s + 5) - 0.4)

                for param, val, unit in [
                    ("pm25", max(1, pm25_base), "µg/m³"),
                    ("pm10", max(2, pm10_base), "µg/m³"),
                    ("no2", max(1, no2_base), "µg/m³"),
                    ("so2", max(0.5, so2_base), "µg/m³"),
                    ("co", max(100, co_base), "µg/m³"),
                    ("o3", max(1, o3_base), "µg/m³"),
                ]:
                    records.append({
                        "source": "openaq",
                        "station_name": name,
                        "lat": lat,
                        "lon": lon,
                        "parameter": param,
                        "value": round(val, 2),
                        "unit": unit,
                        "datetime": ts.isoformat(),
                    })
            ts += timedelta(hours=1)

        return records
