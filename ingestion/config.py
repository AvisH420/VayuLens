"""Role 1: ingestion configuration.

Central configuration — loads .env, exposes API endpoints, rate limits,
city bounding boxes, and credential helpers.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> datetime:
    """Current UTC time as a *naive* datetime.

    ``datetime.utcnow()`` is deprecated from Python 3.12.  The pipeline
    treats every timestamp as naive-UTC end to end (connectors, alignment,
    ``Measurement.timestamp``), so this preserves that convention while
    dropping the deprecated call.  Do not swap this for an aware datetime
    without converting the whole chain at once -- mixing the two raises
    ``TypeError`` on comparison.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)

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


# Export parsed .env values into the process environment (without clobbering
# anything already set) so plain os.getenv(...) — used by the RAG LLM adapters
# and other modules that don't import this config — sees them too.
for _k, _v in _env.items():
    os.environ.setdefault(_k, _v)


# ── Feature flags ─────────────────────────────────────────────────────
USE_MOCK: bool = _get("USE_MOCK", "true").lower() == "true"

# ── Credentials ───────────────────────────────────────────────────────
OPENAQ_API_KEY: str = _get("OPENAQ_API_KEY")
WAQI_TOKEN: str = _get("WAQI_TOKEN")
GEE_PROJECT_ID: str = _get("GEE_PROJECT_ID")
# Path to a GCP service-account JSON key for headless Earth Engine auth
# (CI / servers where interactive `earthengine authenticate` is impossible).
# If empty, EE falls back to any locally-authenticated user credentials.
GEE_SERVICE_ACCOUNT_KEY: str = _get("GEE_SERVICE_ACCOUNT_KEY")
# LLM gateway (OpenRouter — OpenAI-compatible). Key name matches the .env.
OPEN_ROUTER_API_KEY: str = _get("OPEN_ROUTER_API_KEY")

# ── API endpoints ─────────────────────────────────────────────────────
OPENAQ_BASE_URL = "https://api.openaq.org/v3"
WAQI_BASE_URL = "https://api.waqi.info"
OPEN_METEO_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPEN_METEO_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CPCB_CCR_URL = "https://app.cpcbccr.com/ccr/"

# ── Target cities: (min_lon, min_lat, max_lon, max_lat) ───────────────
# Bounds mirror api/demo_engine.py so the ingested grid lines up with the
# grid the dashboard renders.
CITY_BBOX: dict[str, tuple[float, float, float, float]] = {
    "delhi": (76.92, 28.42, 77.38, 28.82),
    "panaji": (73.76, 15.42, 73.90, 15.56),
}


# ── Per-city pollution profiles ───────────────────────────────────────
# Mock generators read these so synthetic data reflects each city's actual
# character rather than one hardcoded Delhi-like baseline.  Anchored to the
# demo_engine headline numbers: Delhi AQI ~210, Panaji ~52.
#
# The AOD terms feed calibration's PM2.5 = 70 x AOD + 5 regression, so they
# set the concentration for the ~98% of cells that have no ground station.
CITY_PROFILES: dict[str, dict[str, float]] = {
    "delhi": {
        "pm25_base":  88.0,   # station mean ug/m3 -> CPCB AQI ~200
        "no2_base":   45.0,
        "so2_base":   12.0,
        "co_base":  1200.0,
        "o3_base":    35.0,
        "aod_urban":   1.33,  # tuned so fused PM2.5 lands near 90 ug/m3
        "aod_spread":  0.66,
        "aod_floor":   0.48,
        "wind_base":   2.3,
    },
    "panaji": {
        "pm25_base":  30.0,   # coastal, sea breeze -> CPCB AQI ~50
        "no2_base":   14.0,
        "so2_base":    4.0,
        "co_base":   450.0,
        "o3_base":    28.0,
        "aod_urban":   0.25,  # mean AOD ~0.36 -> 70x0.36+5 ~= 30 ug/m3
        "aod_spread":  0.15,
        "aod_floor":   0.13,
        "wind_base":   4.1,
    },
}

DEFAULT_CITY = "delhi"


def profile_for_bbox(
    bbox: tuple[float, float, float, float],
) -> dict[str, float]:
    """Return the pollution profile of whichever city *bbox* falls in.

    Matches on the centre of *bbox* against ``CITY_BBOX``.  Falls back to
    the ``DEFAULT_CITY`` profile when nothing matches, so an unknown area
    still produces plausible data rather than crashing.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    c_lon = (min_lon + max_lon) / 2.0
    c_lat = (min_lat + max_lat) / 2.0

    for city, (b_min_lon, b_min_lat, b_max_lon, b_max_lat) in CITY_BBOX.items():
        if b_min_lat <= c_lat <= b_max_lat and b_min_lon <= c_lon <= b_max_lon:
            profile = CITY_PROFILES.get(city)
            if profile is not None:
                return profile

    return CITY_PROFILES[DEFAULT_CITY]

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
    # MCD19A2 (the non-granule id) is superseded and resolves to an empty
    # collection in Earth Engine — AOD silently never loads. The _GRANULES
    # asset is the live one.
    "modis_aod": "MODIS/061/MCD19A2_GRANULES",
}
