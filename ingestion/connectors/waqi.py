"""WAQI / AQICN API connector.

Real mode : map/bounds endpoint returning real-time AQI for stations.
Mock mode : deterministic AQI + PM2.5/PM10/NO2 readings for known stations.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta

import requests

from ingestion.base_connector import BaseConnector
from ingestion import config as cfg

_STATIONS = [
    (28.6508, 77.3152, "Anand Vihar"),
    (28.5918, 77.2273, "ITO"),
    (28.6862, 77.2217, "DTU"),
    (28.5672, 77.2510, "Lajpat Nagar"),
    (28.6336, 77.2195, "Pusa"),
    (28.5494, 77.2001, "R.K. Puram"),
    (28.6289, 77.3070, "Patparganj"),
    (28.6515, 77.1583, "Punjabi Bagh"),
    (28.6804, 77.1531, "Rohini"),
    (15.4989, 73.8278, "Panaji"),
]


def _seed(lat: float, lon: float, ts: datetime) -> int:
    return int(hashlib.md5(f"{lat:.4f},{lon:.4f},{ts.isoformat()}".encode()).hexdigest()[:8], 16)


def _rng(s: int) -> float:
    return ((s * 1103515245 + 12345) & 0x7FFF_FFFF) / 0x7FFF_FFFF


class WAQIConnector(BaseConnector):
    source_name = "waqi"

    def _pull_real(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        min_lon, min_lat, max_lon, max_lat = bbox
        url = f"{cfg.WAQI_BASE_URL}/map/bounds/"
        params = {
            "latlng": f"{min_lat},{min_lon},{max_lat},{max_lon}",
            "token": cfg.WAQI_TOKEN,
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        records: list[dict] = []
        for station in data:
            lat = station.get("lat")
            lon = station.get("lon")
            aqi = station.get("aqi")
            name = station.get("station", {}).get("name", "")

            if lat is None or lon is None:
                continue
            try:
                aqi = float(aqi)
            except (TypeError, ValueError):
                continue

            records.append({
                "source": "waqi",
                "station_name": name,
                "lat": float(lat),
                "lon": float(lon),
                "aqi": aqi,
                "datetime": datetime.utcnow().isoformat(),
            })

        return records

    def _pull_mock(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        min_lon, min_lat, max_lon, max_lat = bbox
        stations = [
            s for s in _STATIONS
            if min_lat <= s[0] <= max_lat and min_lon <= s[1] <= max_lon
        ]
        if not stations:
            stations = _STATIONS[:5]

        records: list[dict] = []
        ts = since
        while ts < until:
            for lat, lon, name in stations:
                s = _seed(lat, lon, ts)
                hour = ts.hour
                diurnal = 1.0 + 0.3 * math.sin(math.pi * (hour - 3) / 12)
                aqi_base = 140 * diurnal + 60 * (_rng(s) - 0.5)
                pm25 = 80 * diurnal + 35 * (_rng(s + 1) - 0.5)
                pm10 = pm25 * 1.7 + 25 * _rng(s + 2)
                no2 = 42 * diurnal + 18 * (_rng(s + 3) - 0.5)

                records.append({
                    "source": "waqi",
                    "station_name": name,
                    "lat": lat,
                    "lon": lon,
                    "aqi": round(max(10, aqi_base), 1),
                    "pm25": round(max(1, pm25), 2),
                    "pm10": round(max(2, pm10), 2),
                    "no2": round(max(1, no2), 2),
                    "datetime": ts.isoformat(),
                })
            ts += timedelta(hours=1)

        return records
