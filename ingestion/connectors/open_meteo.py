"""Open-Meteo Air Quality + Weather connector.

Real mode : free Open-Meteo API (no key required) for gridded AQ + met data.
Mock mode : deterministic synthetic meteorology and air-quality forecasts.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta

import requests

from ingestion.base_connector import BaseConnector
from ingestion import config as cfg


class OpenMeteoConnector(BaseConnector):
    source_name = "open_meteo"

    def _pull_real(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        min_lon, min_lat, max_lon, max_lat = bbox

        # Sample a coarse grid of points (~0.1° spacing ≈ 10 km)
        step = 0.1
        lats = _arange(min_lat, max_lat, step)
        lons = _arange(min_lon, max_lon, step)
        points = [(round(la, 4), round(lo, 4)) for la in lats for lo in lons]
        if not points:
            return []

        start = since.strftime("%Y-%m-%d")
        end = until.strftime("%Y-%m-%d")

        # One bulk request per endpoint (Open-Meteo accepts comma-separated
        # coordinates and returns a per-location array). This replaces ~80
        # per-point calls with 2, so a slow endpoint no longer means dozens of
        # timeout chances. Weather and air-quality are fetched independently:
        # weather carries wind (required downstream), so it must survive an
        # air-quality outage and vice versa.
        wx = self._bulk(cfg.OPEN_METEO_WEATHER_URL, points, start, end,
                        "temperature_2m,wind_speed_10m,wind_direction_10m,relative_humidity_2m")
        aq = self._bulk(cfg.OPEN_METEO_AQ_URL, points, start, end,
                        "pm2_5,pm10,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide,ozone")

        records: list[dict] = []
        for idx, (lat, lon) in enumerate(points):
            wx_h = wx[idx] if idx < len(wx) else {}
            aq_h = aq[idx] if idx < len(aq) else {}
            times = wx_h.get("time") or aq_h.get("time") or []
            for i, t in enumerate(times):
                records.append({
                    "source": "open_meteo",
                    "lat": lat, "lon": lon,
                    "pm25": _safe_idx(aq_h.get("pm2_5"), i),
                    "pm10": _safe_idx(aq_h.get("pm10"), i),
                    "no2": _safe_idx(aq_h.get("nitrogen_dioxide"), i),
                    "so2": _safe_idx(aq_h.get("sulphur_dioxide"), i),
                    "co": _safe_idx(aq_h.get("carbon_monoxide"), i),
                    "o3": _safe_idx(aq_h.get("ozone"), i),
                    "temp": _safe_idx(wx_h.get("temperature_2m"), i),
                    "wind_speed": _safe_idx(wx_h.get("wind_speed_10m"), i),
                    "wind_dir": _safe_idx(wx_h.get("wind_direction_10m"), i),
                    "humidity": _safe_idx(wx_h.get("relative_humidity_2m"), i),
                    "datetime": t,
                })
        return records

    def _bulk(self, url, points, start, end, hourly) -> list[dict]:
        """One multi-location Open-Meteo call; returns per-point 'hourly' dicts.

        Retries transient failures and returns [] on total failure so the
        other endpoint's data still flows (never raises).
        """
        import logging
        lat_csv = ",".join(str(p[0]) for p in points)
        lon_csv = ",".join(str(p[1]) for p in points)
        params = {"latitude": lat_csv, "longitude": lon_csv,
                  "hourly": hourly, "start_date": start, "end_date": end}
        for attempt in range(1, 4):
            try:
                r = requests.get(url, params=params, timeout=60)
                r.raise_for_status()
                data = r.json()
                # Multi-location responses are a list; single is a dict.
                if isinstance(data, dict):
                    data = [data]
                return [loc.get("hourly", {}) for loc in data]
            except Exception as exc:  # noqa: BLE001 — transient, retry
                logging.getLogger("vayulens.ingestion").warning(
                    "[open_meteo] %s attempt %d/3 failed: %s",
                    url.split("//")[-1][:24], attempt, str(exc)[:80])
                import time
                time.sleep(3 * attempt)
        return []

    def _pull_mock(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        min_lon, min_lat, max_lon, max_lat = bbox
        # ~5 km sampling: the real Open-Meteo grid is ~11 km, but a denser mock
        # keeps meteorology from being a single point over a small city bbox.
        step = 0.05
        lats = _arange(min_lat, max_lat, step)
        lons = _arange(min_lon, max_lon, step)
        prof = cfg.profile_for_bbox(bbox)
        spread = prof["pm25_base"] / 85.0

        records: list[dict] = []
        ts = since
        while ts < until:
            for lat in lats:
                for lon in lons:
                    s = _seed(lat, lon, ts)
                    hour = ts.hour
                    diurnal = 1.0 + 0.25 * math.sin(math.pi * (hour - 3) / 12)

                    # Temperature: peaks mid-afternoon
                    temp = 32 + 8 * math.sin(math.pi * (hour - 6) / 12) + 3 * (_rng(s) - 0.5)
                    wind_speed = (
                        prof["wind_base"]
                        + 1.6 * _rng(s + 1)
                        + 0.8 * math.sin(math.pi * hour / 12)
                    )
                    wind_dir = (180 + 120 * (_rng(s + 2) - 0.5)) % 360
                    humidity = 55 + 20 * math.sin(math.pi * (hour + 6) / 12) + 10 * (_rng(s + 3) - 0.5)

                    records.append({
                        "source": "open_meteo",
                        "lat": round(lat, 4),
                        "lon": round(lon, 4),
                        "pm25": round(max(1, prof["pm25_base"] * 0.82 * diurnal + 30 * spread * (_rng(s + 4) - 0.5)), 2),
                        "pm10": round(max(2, prof["pm25_base"] * 1.53 * diurnal + 50 * spread * (_rng(s + 5) - 0.5)), 2),
                        "no2": round(max(1, prof["no2_base"] * 0.89 * diurnal + 15 * spread * (_rng(s + 6) - 0.5)), 2),
                        "so2": round(max(0.5, prof["so2_base"] * 0.83 + 6 * spread * (_rng(s + 7) - 0.3)), 2),
                        "co": round(max(50, prof["co_base"] * 0.75 + 400 * spread * (_rng(s + 8) - 0.5)), 2),
                        "o3": round(max(1, prof["o3_base"] * 0.86 + 20 * spread * (_rng(s + 9) - 0.4)), 2),
                        "temp": round(temp, 1),
                        "wind_speed": round(max(0.5, wind_speed), 1),
                        "wind_dir": round(wind_dir, 1),
                        "humidity": round(max(20, min(95, humidity)), 1),
                        "datetime": ts.isoformat(),
                    })
            ts += timedelta(hours=1)

        return records


# ── helpers ───────────────────────────────────────────────────────────
def _arange(start: float, stop: float, step: float) -> list[float]:
    vals: list[float] = []
    v = start
    while v <= stop + 1e-9:
        vals.append(round(v, 4))
        v += step
    return vals


def _safe_idx(lst: list | None, i: int):
    if lst is None or i >= len(lst):
        return None
    return lst[i]


def _seed(lat: float, lon: float, ts: datetime) -> int:
    return int(hashlib.md5(f"{lat:.4f},{lon:.4f},{ts.isoformat()}".encode()).hexdigest()[:8], 16)


def _rng(s: int) -> float:
    return ((s * 1103515245 + 12345) & 0x7FFF_FFFF) / 0x7FFF_FFFF
