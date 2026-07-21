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

# Literature-backed empirical PM2.5 / AOD slope for Indian cities
# PM2.5 ≈ k × AOD  where k ∈ [60, 80] — we use 70 as default
_AOD_PM25_SLOPE = 70.0
_AOD_PM25_INTERCEPT = 5.0


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
) -> tuple[float | None, float]:
    """Convert MODIS/satellite AOD to estimated ground-level PM2.5.

    Uses the empirical relationship:
        PM2.5 = β₀ + β₁·AOD + β₂·f(RH) + β₃·f(wind)

    Returns:
        (estimated_pm25, uncertainty)
    """
    if aod is None:
        return None, 999.0

    # Base regression
    pm25 = _AOD_PM25_INTERCEPT + _AOD_PM25_SLOPE * aod

    # Humidity correction: higher RH inflates AOD without proportionally
    # increasing PM2.5, so we dampen the estimate
    if humidity is not None and humidity > 60:
        rh_factor = 1.0 - 0.005 * (humidity - 60)
        pm25 *= max(0.7, rh_factor)

    # Wind correction: higher wind disperses PM
    if wind_speed is not None and wind_speed > 3:
        wind_factor = 1.0 - 0.03 * (wind_speed - 3)
        pm25 *= max(0.6, wind_factor)

    pm25 = max(1.0, round(pm25, 2))

    # Uncertainty: ±25 % of the estimate (empirical regression scatter)
    uncertainty = round(pm25 * 0.25, 2)

    return pm25, uncertainty


def calibrate_all_sources(
    source_data_by_source: dict[str, dict[str, float | None]],
) -> dict[str, dict[str, float | None]]:
    """Full calibration pipeline: harmonise → bias-correct → AOD→PM2.5.

    Modifies source data in-place to add satellite-derived PM2.5 where
    ground PM2.5 is missing but AOD is available.
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

        sat_pm25, sat_unc = aod_to_pm25(aod_val, humidity, wind_speed)

        # Add satellite-derived PM2.5 as a separate "source"
        if sat_pm25 is not None:
            corrected["satellite_derived"] = {
                "pm25": sat_pm25,
                "uncertainty": sat_unc,
                "aod": aod_val,
            }

    return corrected
