"""Role 1: per-source calibration and AOD → PM2.5 regression.

Steps:
  1. Unit harmonisation (ppb → µg/m³ where needed).
  2. Inter-source bias correction (paired-station offsets).
  3. Satellite AOD → ground PM2.5 empirical regression.
"""

from __future__ import annotations

import math
from collections import defaultdict


# ── Standard conversion factors (ppb → µg/m³ at 25 °C, 1 atm) ───────
_PPB_TO_UGM3 = {
    "no2": 1.88,
    "so2": 2.62,
    "co":  1.145,   # ppm → mg/m³ ; ppb factor ≈ 1.145e-3
    "o3":  1.96,
}

# ── City-specific regression models ──────────────────────────────────
# Trained on 8,784 hourly co-located (AOD, PM2.5, weather) pairs from
# Open-Meteo CAMS reanalysis (2025-07 to 2026-07).
#
# Model: PM2.5 = intercept + aod*AOD + hum*RH + wind*WS + temp*T
#                + hs*sin(2πh/24) + hc*cos(2πh/24)
#                + ms*sin(2πm/12) + mc*cos(2πm/12)
#
# Delhi:  R²=0.39, MAE=28.2 µg/m³ (vs 45.2 for generic formula, 37.6% better)
# Panaji: R²=0.70, MAE=6.2 µg/m³  (vs 14.8 for generic formula, 57.9% better)
_CITY_MODELS: dict[str, dict[str, float]] = {
    "delhi": {
        "intercept": 182.69,
        "aod_slope": 73.9862,
        "humidity_coeff": -0.8778,
        "wind_coeff": -2.2133,
        "temp_coeff": -2.9778,
        "hour_sin_coeff": -13.5246,
        "hour_cos_coeff": 15.6509,
        "month_sin_coeff": 3.6661,
        "month_cos_coeff": 5.5284,
    },
    "panaji": {
        "intercept": 33.7776,
        "aod_slope": 35.3284,
        "humidity_coeff": -0.0921,
        "wind_coeff": -0.4395,
        "temp_coeff": -0.4947,
        "hour_sin_coeff": -1.6161,
        "hour_cos_coeff": 0.1952,
        "month_sin_coeff": 6.6764,
        "month_cos_coeff": 9.4692,
    },
}

# Fallback generic model (literature-backed)
_FALLBACK_MODEL: dict[str, float] = {
    "intercept": 5.0,
    "aod_slope": 70.0,
    "humidity_coeff": -0.5,
    "wind_coeff": -1.0,
    "temp_coeff": -1.0,
    "hour_sin_coeff": 0.0,
    "hour_cos_coeff": 0.0,
    "month_sin_coeff": 0.0,
    "month_cos_coeff": 0.0,
}


def _select_model(city: str | None = None) -> dict[str, float]:
    """Pick the regression model for a city, falling back to generic."""
    if city:
        city_lower = city.lower()
        if city_lower in _CITY_MODELS:
            return _CITY_MODELS[city_lower]
    return _FALLBACK_MODEL


def harmonise_units(
    source_data: dict[str, float | None],
    source_name: str,
) -> dict[str, float | None]:
    """Ensure all pollutant concentrations are in µg/m³.

    Most Indian ground-monitoring networks already report µg/m³.
    Open-Meteo sometimes reports in ppb for gaseous species.
    """
    result = dict(source_data)

    # Open-Meteo reports gaseous species in µg/m³ already (v1 API).
    # If a source reports ppb, convert here:
    if source_name in ("open_meteo_ppb",):  # placeholder for ppb sources
        for gas, factor in _PPB_TO_UGM3.items():
            if result.get(gas) is not None:
                result[gas] = round(result[gas] * factor, 4)

    return result


def correct_bias(
    source_data_by_source: dict[str, dict[str, float | None]],
) -> dict[str, dict[str, float | None]]:
    """Apply inter-source bias correction.

    Where multiple ground networks report the same parameter for the same
    cell-hour, compute pairwise offsets and adjust toward the CPCB reading
    (the official reference network).
    """
    reference_source = "cpcb"
    corrected = {}

    ref_data = source_data_by_source.get(reference_source)

    for src, data in source_data_by_source.items():
        corrected_data = dict(data)

        if src != reference_source and ref_data is not None:
            for param in ("pm25", "pm10", "no2", "so2", "co", "o3"):
                src_val = data.get(param)
                ref_val = ref_data.get(param)
                if src_val is not None and ref_val is not None and src_val > 0:
                    # Simple ratio correction toward reference
                    ratio = ref_val / src_val
                    # Clamp correction to ±30 % to avoid wild swings
                    ratio = max(0.7, min(1.3, ratio))
                    corrected_data[param] = round(src_val * ratio, 4)

        corrected[src] = corrected_data

    return corrected


def aod_to_pm25(
    aod: float | None,
    humidity: float | None = None,
    wind_speed: float | None = None,
    temperature: float | None = None,
    hour: int | None = None,
    month: int | None = None,
    city: str | None = None,
) -> tuple[float | None, float]:
    """Convert satellite AOD to estimated ground-level PM2.5.

    Uses city-specific multivariate regression models trained on 1 year
    of co-located (AOD, PM2.5, weather) historical data from CAMS reanalysis.

    The model incorporates:
      - AOD (primary predictor)
      - Humidity (high RH inflates AOD without proportionally increasing PM2.5)
      - Wind speed (disperses ground-level PM)
      - Temperature (drives atmospheric mixing height)
      - Diurnal cycle (pollution peaks at night, dips in afternoon)
      - Seasonal cycle (winter highs, monsoon lows)

    Returns:
        (estimated_pm25, uncertainty)
    """
    if aod is None:
        return None, 999.0

    model = _select_model(city)

    # Base: intercept + AOD term
    pm25 = model["intercept"] + model["aod_slope"] * aod

    # Weather corrections
    if humidity is not None:
        pm25 += model["humidity_coeff"] * humidity

    if wind_speed is not None:
        pm25 += model["wind_coeff"] * wind_speed

    if temperature is not None:
        pm25 += model["temp_coeff"] * temperature

    # Diurnal cycle (hour of day)
    if hour is not None:
        pm25 += model["hour_sin_coeff"] * math.sin(2 * math.pi * hour / 24)
        pm25 += model["hour_cos_coeff"] * math.cos(2 * math.pi * hour / 24)

    # Seasonal cycle (month of year)
    if month is not None:
        pm25 += model["month_sin_coeff"] * math.sin(2 * math.pi * month / 12)
        pm25 += model["month_cos_coeff"] * math.cos(2 * math.pi * month / 12)

    pm25 = max(1.0, round(pm25, 2))

    # Uncertainty: based on model RMSE (Delhi ~38.6, Panaji ~8.5)
    if city and city.lower() == "panaji":
        uncertainty = round(pm25 * 0.15, 2)   # Panaji model is tighter
    else:
        uncertainty = round(pm25 * 0.22, 2)   # Delhi model has more scatter

    return pm25, uncertainty


def calibrate_all_sources(
    source_data_by_source: dict[str, dict[str, float | None]],
    city: str | None = None,
    hour: int | None = None,
    month: int | None = None,
) -> dict[str, dict[str, float | None]]:
    """Full calibration pipeline: harmonise → bias-correct → AOD→PM2.5.

    Modifies source data in-place to add satellite-derived PM2.5 where
    ground PM2.5 is missing but AOD is available.

    Args:
        source_data_by_source: Per-source aggregated data for one cell-hour.
        city: City name for city-specific regression model selection.
        hour: Hour of day (0-23) for diurnal correction.
        month: Month of year (1-12) for seasonal correction.
    """
    # Step 1: Unit harmonisation
    harmonised = {}
    for src, data in source_data_by_source.items():
        harmonised[src] = harmonise_units(data, src)

    # Step 2: Inter-source bias correction
    corrected = correct_bias(harmonised)

    # Step 3: AOD → PM2.5 for satellite sources
    gee_data = corrected.get("gee", {})
    aod_val = gee_data.get("aod") or gee_data.get("value")
    if aod_val is not None and gee_data.get("product") == "aod":
        aod_val = gee_data.get("value", aod_val)

    # Check if any source already has AOD
    for src, data in corrected.items():
        if data.get("aod") is not None:
            aod_val = data["aod"]
            break

    if aod_val is not None:
        # Get met covariates
        met = corrected.get("open_meteo", {})
        humidity = met.get("humidity")
        wind_speed = met.get("wind_speed")
        temperature = met.get("temp")

        sat_pm25, sat_unc = aod_to_pm25(
            aod_val,
            humidity=humidity,
            wind_speed=wind_speed,
            temperature=temperature,
            hour=hour,
            month=month,
            city=city,
        )

        # Add satellite-derived PM2.5 as a separate "source"
        if sat_pm25 is not None:
            corrected["satellite_derived"] = {
                "pm25": sat_pm25,
                "uncertainty": sat_unc,
                "aod": aod_val,
            }

    return corrected

