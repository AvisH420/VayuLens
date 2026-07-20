"""CPCB CCR portal connector.

Real mode : HTTP requests to app.cpcbccr.com (scraping the public portal).
Mock mode : deterministic synthetic CAAQMS readings aligned with OpenAQ mock
            data but with slight inter-source bias (as in real life).
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta

import requests

from ingestion.base_connector import BaseConnector
from ingestion import config as cfg

# Subset of known CPCB CAAQMS stations (Delhi)
_CPCB_STATIONS = [
    ("DL001", 28.6508, 77.3152, "Anand Vihar, Delhi - DPCC"),
    ("DL002", 28.5918, 77.2273, "ITO, Delhi - DPCC"),
    ("DL003", 28.6862, 77.2217, "DTU, Delhi - DPCC"),
    ("DL004", 28.5672, 77.2510, "Lajpat Nagar, Delhi - DPCC"),
    ("DL005", 28.6336, 77.2195, "Pusa, Delhi - IMD"),
    ("DL006", 28.7501, 77.1177, "Narela, Delhi - DPCC"),
    ("DL007", 28.5494, 77.2001, "R.K. Puram, Delhi - DPCC"),
    ("DL008", 28.6289, 77.3070, "Patparganj, Delhi - DPCC"),
    ("DL009", 28.5631, 77.1594, "Najafgarh, Delhi - DPCC"),
    ("DL010", 28.7041, 77.1025, "Bawana, Delhi - DPCC"),
    ("DL011", 28.6515, 77.1583, "Punjabi Bagh, Delhi - DPCC"),
    ("DL012", 28.6804, 77.1531, "Rohini, Delhi - DPCC"),
]

_PANAJI_CPCB = [
    ("GA001", 15.4989, 73.8278, "Panaji, Goa - GSPCB"),
]


def _seed(sid: str, ts: datetime) -> int:
    raw = f"{sid}_{ts.isoformat()}"
    return int(hashlib.md5(raw.encode()).hexdigest()[:8], 16)


def _rng(seed: int) -> float:
    return ((seed * 1103515245 + 12345) & 0x7FFF_FFFF) / 0x7FFF_FFFF


class CPCBConnector(BaseConnector):
    source_name = "cpcb"

    # ── REAL implementation ───────────────────────────────────────────
    def _pull_real(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        """Attempt to pull from the CPCB CCR public portal.

        The CPCB portal does not have a stable public API; this implementation
        tries to hit the known internal JSON endpoints.  If they change or
        block scraping, it falls back gracefully to an empty list.
        """
        records: list[dict] = []
        try:
            # The CPCB CCR site exposes station data via an internal XHR
            session = requests.Session()
            session.headers.update({
                "User-Agent": "VayuLens-Research/1.0",
                "Accept": "application/json",
            })

            # Try the station list endpoint
            station_url = f"{cfg.CPCB_CCR_URL}api/station/list"
            resp = session.get(station_url, timeout=30)
            if resp.status_code != 200:
                return records

            stations = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else []
            min_lon, min_lat, max_lon, max_lat = bbox

            for st in stations:
                lat = float(st.get("latitude", 0))
                lon = float(st.get("longitude", 0))
                if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                    continue

                # Try to get data for each station
                self._throttle()
                data_url = f"{cfg.CPCB_CCR_URL}api/station/data"
                data_params = {
                    "station_id": st.get("station_id", ""),
                    "from": since.strftime("%Y-%m-%d"),
                    "to": until.strftime("%Y-%m-%d"),
                }
                dresp = session.get(data_url, params=data_params, timeout=30)
                if dresp.status_code == 200:
                    for item in dresp.json():
                        records.append({
                            "source": "cpcb",
                            "station_id": st.get("station_id"),
                            "station_name": st.get("station_name", ""),
                            "lat": lat,
                            "lon": lon,
                            "pm25": item.get("pm25"),
                            "pm10": item.get("pm10"),
                            "no2": item.get("no2"),
                            "so2": item.get("so2"),
                            "co": item.get("co"),
                            "o3": item.get("o3"),
                            "datetime": item.get("datetime", ""),
                        })
        except Exception:
            pass  # CPCB portal is unreliable; fail gracefully

        return records

    # ── MOCK implementation ───────────────────────────────────────────
    def _pull_mock(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        min_lon, min_lat, max_lon, max_lat = bbox

        stations = [
            s for s in (_CPCB_STATIONS + _PANAJI_CPCB)
            if min_lat <= s[1] <= max_lat and min_lon <= s[2] <= max_lon
        ]
        if not stations:
            stations = _CPCB_STATIONS[:5]

        records: list[dict] = []
        ts = since
        while ts < until:
            for sid, lat, lon, name in stations:
                s = _seed(sid, ts)
                hour = ts.hour
                diurnal = 1.0 + 0.3 * math.sin(math.pi * (hour - 3) / 12)

                # Slight positive bias compared to OpenAQ (realistic inter-source difference)
                bias = 1.05

                records.append({
                    "source": "cpcb",
                    "station_id": sid,
                    "station_name": name,
                    "lat": lat,
                    "lon": lon,
                    "pm25": round(max(1, 88 * diurnal * bias + 35 * (_rng(s) - 0.5)), 2),
                    "pm10": round(max(2, 160 * diurnal * bias + 50 * (_rng(s+1) - 0.5)), 2),
                    "no2": round(max(1, 48 * diurnal * bias + 18 * (_rng(s+2) - 0.5)), 2),
                    "so2": round(max(0.5, 13 * bias + 7 * (_rng(s+3) - 0.3)), 2),
                    "co": round(max(100, 1250 * bias + 500 * (_rng(s+4) - 0.5)), 2),
                    "o3": round(max(1, 38 + 22 * (_rng(s+5) - 0.4)), 2),
                    "datetime": ts.isoformat(),
                })
            ts += timedelta(hours=1)

        return records
