"""WAQI / AQICN API connector.

Real mode : map/bounds lists the stations in view and their headline AQI, then
            feed/@{uid} is called per station for the pollutant breakdown
            (pm25/pm10/no2/so2/co/o3).  bounds alone returns *only* an AQI
            integer, which is not enough for calibration or fusion.
Mock mode : deterministic AQI + PM2.5/PM10/NO2 readings for known stations.
"""

from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime, timedelta, timezone

import requests

from ingestion.base_connector import BaseConnector
from ingestion import config as cfg

logger = logging.getLogger("vayulens.ingestion")

# CPCB (India) AQI breakpoints for PM2.5: (conc_lo, conc_hi, aqi_lo, aqi_hi)
_PM25_AQI_BREAKPOINTS = [
    (0.0,   30.0,    0,  50),
    (30.0,  60.0,   51, 100),
    (60.0,  90.0,  101, 200),
    (90.0, 120.0,  201, 300),
    (120.0, 250.0, 301, 400),
    (250.0, 1000.0, 401, 500),
]


def _pm25_to_aqi(pm25: float) -> float:
    """Convert a PM2.5 concentration (ug/m3) to a CPCB AQI value."""
    for c_lo, c_hi, a_lo, a_hi in _PM25_AQI_BREAKPOINTS:
        if c_lo <= pm25 <= c_hi:
            return a_lo + (a_hi - a_lo) * (pm25 - c_lo) / (c_hi - c_lo)
    return 500.0


def _aqi_to_pm25(aqi: float) -> float:
    """Invert the CPCB PM2.5 AQI scale.

    Used only as a fallback when a station reports an AQI but no ``pm25``
    in its ``iaqi`` block, so the record still carries a usable
    concentration downstream.  Lossy: WAQI's headline AQI may be driven by
    a pollutant other than PM2.5, so treat these values as approximate.
    """
    for c_lo, c_hi, a_lo, a_hi in _PM25_AQI_BREAKPOINTS:
        if a_lo <= aqi <= a_hi:
            return c_lo + (c_hi - c_lo) * (aqi - a_lo) / (a_hi - a_lo)
    return 1000.0

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


def _iaqi_value(iaqi: dict, key: str) -> float | None:
    """Read one species out of a WAQI ``iaqi`` block, e.g. ``{"pm25": {"v": 154}}``."""
    entry = iaqi.get(key)
    if not isinstance(entry, dict):
        return None
    try:
        return float(entry.get("v"))
    except (TypeError, ValueError):
        return None


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
        if not cfg.WAQI_TOKEN:
            raise RuntimeError(
                "WAQI_TOKEN is not set. Add it to .env "
                "(free token: https://aqicn.org/data-platform/token/)"
            )

        min_lon, min_lat, max_lon, max_lat = bbox

        # ── Step 1: which stations are in view ────────────────────────
        resp = requests.get(
            f"{cfg.WAQI_BASE_URL}/map/bounds/",
            params={
                "latlng": f"{min_lat},{min_lon},{max_lat},{max_lon}",
                "token": cfg.WAQI_TOKEN,
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()

        # WAQI signals auth/quota problems in the body with HTTP 200.
        if payload.get("status") != "ok":
            raise RuntimeError(f"WAQI bounds query failed: {payload.get('data')!r}")

        stations = payload.get("data", [])
        logger.info("[waqi] %d stations in bbox", len(stations))

        # ── Step 2: pollutant breakdown, one call per station ─────────
        records: list[dict] = []
        for station in stations:
            lat, lon = station.get("lat"), station.get("lon")
            if lat is None or lon is None:
                continue

            uid = station.get("uid")
            name = station.get("station", {}).get("name", "")

            try:
                aqi = float(station.get("aqi"))
            except (TypeError, ValueError):
                aqi = None          # WAQI sends "-" for offline stations

            record = {
                "source": "waqi",
                "station_id": uid,
                "station_name": name,
                "lat": float(lat),
                "lon": float(lon),
                "aqi": aqi,
                "datetime": datetime.now(timezone.utc).isoformat(),
            }

            detail = self._fetch_station_detail(uid) if uid is not None else {}
            record.update(detail)

            # Keep a PM2.5 value on the record even if the station omits one,
            # otherwise calibration and fusion silently drop this station.
            if record.get("pm25") is None and aqi is not None:
                record["pm25"] = round(_aqi_to_pm25(aqi), 2)
                record["pm25_derived_from_aqi"] = True

            # Offline stations report aqi "-" and carry no iaqi block. Passing
            # them on would add a station to fusion that measures nothing.
            if not any(record.get(k) is not None
                       for k in ("pm25", "pm10", "no2", "so2", "co", "o3")):
                logger.info("[waqi] skipping %s (uid %s): no readings", name, uid)
                continue

            records.append(record)

        logger.info("[waqi] %d/%d stations returned usable readings",
                    len(records), len(stations))
        return records

    def _fetch_station_detail(self, uid) -> dict:
        """Pull the ``iaqi`` pollutant breakdown for one station.

        Returns ``{}`` when the station is unreachable or reports nothing —
        a single bad station must not abort the whole pull.
        """
        try:
            self._throttle()
            resp = requests.get(
                f"{cfg.WAQI_BASE_URL}/feed/@{uid}/",
                params={"token": cfg.WAQI_TOKEN},
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("status") != "ok":
                logger.warning("[waqi] station %s: %s", uid, payload.get("data"))
                return {}

            iaqi = payload.get("data", {}).get("iaqi", {})
            observed = payload.get("data", {}).get("time", {}).get("iso")

            # WAQI reports each species as its own sub-index, not a raw
            # concentration.  For PM2.5 the sub-index uses the same scale we
            # invert above; the gases are close enough to ug/m3 for fusion.
            detail: dict = {}
            if (pm25 := _iaqi_value(iaqi, "pm25")) is not None:
                detail["pm25"] = round(_aqi_to_pm25(pm25), 2)
            if (pm10 := _iaqi_value(iaqi, "pm10")) is not None:
                detail["pm10"] = pm10
            for species in ("no2", "so2", "co", "o3"):
                if (val := _iaqi_value(iaqi, species)) is not None:
                    detail[species] = val
            if observed:
                detail["datetime"] = observed

            return detail

        except Exception as exc:
            logger.warning("[waqi] station %s detail failed: %s", uid, exc)
            return {}

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

        prof = cfg.profile_for_bbox(bbox)
        spread = prof["pm25_base"] / 85.0   # keep noise proportional to level

        records: list[dict] = []
        ts = since
        while ts < until:
            for lat, lon, name in stations:
                s = _seed(lat, lon, ts)
                hour = ts.hour
                diurnal = 1.0 + 0.3 * math.sin(math.pi * (hour - 3) / 12)
                pm25 = prof["pm25_base"] * 0.94 * diurnal + 35 * spread * (_rng(s + 1) - 0.5)
                aqi_base = _pm25_to_aqi(max(1.0, pm25)) * diurnal
                pm10 = pm25 * 1.7 + 25 * spread * _rng(s + 2)
                no2 = prof["no2_base"] * 0.93 * diurnal + 18 * spread * (_rng(s + 3) - 0.5)

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
