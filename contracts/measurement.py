"""Schema: measurement — a calibrated/fused observation for a cell at a time."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Measurement(BaseModel):
    """One fused air-quality + meteorology observation for a grid cell."""

    cell_id: str = Field(..., description="Grid cell this measurement belongs to.")
    lat: float = Field(..., description="Latitude of the cell centroid.")
    lon: float = Field(..., description="Longitude of the cell centroid.")
    timestamp: datetime = Field(..., description="UTC timestamp of the observation.")

    # Pollutants
    pm25: float | None = Field(None, description="PM2.5 concentration (ug/m^3).")
    pm10: float | None = Field(None, description="PM10 concentration (ug/m^3).")
    no2: float | None = Field(None, description="NO2 concentration (ug/m^3).")
    so2: float | None = Field(None, description="SO2 concentration (ug/m^3).")

    # Satellite-derived
    aod: float | None = Field(None, description="Aerosol Optical Depth (unitless).")
    uv_aerosol_index: float | None = Field(None, description="UV Aerosol Index (unitless).")

    # Meteorology
    temp: float | None = Field(None, description="Temperature (deg C).")
    wind_speed: float | None = Field(None, description="Wind speed (m/s).")
    wind_direction: float | None = Field(None, description="Wind direction (degrees from North).")

    # Quality / fusion metadata
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in the fused value [0,1].")
    uncertainty: float = Field(..., ge=0.0, description="Estimated uncertainty (same unit as the primary pollutant).")
