"""Role 1: ingestion configuration.

Central configuration — loads .env, exposes API endpoints, rate limits,
city bounding boxes, and credential helpers.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────
INGESTION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = INGESTION_DIR.parent
DATA_STORE_DIR = PROJECT_ROOT / "data_store"
RAW_STORE_DIR = DATA_STORE_DIR / "raw"
PROCESSED_STORE_DIR = DATA_STORE_DIR / "processed"


# ── .env loader ───────────────────────────────────────────────────────
def _load_env(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file (ignores comments and blanks)."""
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
    return env


_env = _load_env(PROJECT_ROOT / ".env")


def _get(key: str, default: str = "") -> str:
    """Read from parsed .env first, fall back to OS env."""
    return _env.get(key) or os.getenv(key, default)


# ── Feature flags ─────────────────────────────────────────────────────
USE_MOCK: bool = _get("USE_MOCK", "true").lower() == "true"

# ── Credentials ───────────────────────────────────────────────────────
OPENAQ_API_KEY: str = _get("OPENAQ_API_KEY")
WAQI_TOKEN: str = _get("WAQI_TOKEN")
GEE_PROJECT_ID: str = _get("GEE_PROJECT_ID")

# ── API endpoints ─────────────────────────────────────────────────────
OPENAQ_BASE_URL = "https://api.openaq.org/v3"
WAQI_BASE_URL = "https://api.waqi.info"
OPEN_METEO_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPEN_METEO_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CPCB_CCR_URL = "https://app.cpcbccr.com/ccr/"

# ── Target cities: (min_lon, min_lat, max_lon, max_lat) ───────────────
CITY_BBOX: dict[str, tuple[float, float, float, float]] = {
    "delhi": (76.84, 28.40, 77.35, 28.88),
    "goa": (73.67, 14.89, 74.34, 15.80),
}

# ── Rate limits (requests per second) ─────────────────────────────────
RATE_LIMITS: dict[str, float] = {
    "openaq": 1.0,       # safe under 300 calls / 5 min
    "cpcb": 0.1,         # polite scraping: 1 req / 10 s
    "waqi": 10.0,        # generous 1 000 req / s quota
    "open_meteo": 5.0,
    "osm": 0.1,          # Overpass fair-use
    "gee_sentinel5p": 1.0,
    "gee_modis": 1.0,
}

# ── GEE collection IDs ───────────────────────────────────────────────
GEE_COLLECTIONS = {
    "s5p_no2":  "COPERNICUS/S5P/OFFL/L3_NO2",
    "s5p_aer":  "COPERNICUS/S5P/OFFL/L3_AER_AI",
    "s5p_co":   "COPERNICUS/S5P/OFFL/L3_CO",
    "s5p_so2":  "COPERNICUS/S5P/OFFL/L3_SO2",
    "modis_aod": "MODIS/061/MCD19A2",
}
