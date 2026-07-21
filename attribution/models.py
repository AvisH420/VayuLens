from pydantic import BaseModel, Field
from typing import List, Optional

class GridCellInput(BaseModel):
    cell_id: str = Field(..., description="Unique identifier for the grid cell (e.g., cell_row_col)")
    lat: float = Field(..., description="Latitude of the center of the cell")
    lon: float = Field(..., description="Longitude of the center of the cell")
    pm25: float = Field(..., description="Calibrated PM2.5 concentration in ug/m3")
    pm10: Optional[float] = Field(None, description="PM10 concentration in ug/m3")
    
    # Satellite and ground chemical proxies
    no2: float = Field(..., description="Sentinel-5P or ground sensor NO2 column density/concentration (traffic proxy)")
    so2: float = Field(..., description="Sentinel-5P or ground sensor SO2 column density/concentration (industry proxy)")
    co: Optional[float] = Field(None, description="Carbon Monoxide concentration")
    aod: float = Field(..., description="MODIS Aerosol Optical Depth (particles/dust/haze)")
    uv_aerosol_index: float = Field(..., description="Sentinel-5P UV Aerosol Index (biomass burning / desert dust proxy)")
    
    # Meteorological factors
    wind_speed: float = Field(..., description="Wind speed in meters per second")
    wind_direction: float = Field(..., description="Wind direction in degrees (0-360, 0=North, 90=East)")
    
    # Static land use proxies (from OpenStreetMap / Role 1)
    road_density: float = Field(..., description="Road density score representing traffic heavy areas")
    industrial_proximity: float = Field(..., description="Distance in meters or proximity index to nearest industrial zone")
    construction_density: float = Field(..., description="Density or area score of construction activities nearby")

class SourceAttributionDict(BaseModel):
    traffic: float = Field(..., ge=0.0, le=1.0, description="Fraction of PM2.5 attributed to vehicular traffic")
    construction: float = Field(..., ge=0.0, le=1.0, description="Fraction of PM2.5 attributed to construction activity")
    industry: float = Field(..., ge=0.0, le=1.0, description="Fraction of PM2.5 attributed to industrial emissions")
    biomass: float = Field(..., ge=0.0, le=1.0, description="Fraction of PM2.5 attributed to biomass burning (e.g. stubble)")
    dust: float = Field(..., ge=0.0, le=1.0, description="Fraction of PM2.5 attributed to dust (road/soil/desert)")
    other: float = Field(..., ge=0.0, le=1.0, description="Fraction of PM2.5 attributed to other unclassified sources")

class SourceAttributionOutput(BaseModel):
    cell_id: str
    sources: SourceAttributionDict
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the attribution model (0.0 to 1.0)")
    timestamp: str = Field(..., description="UTC ISO 8601 timestamp for the attribution calculation")

class GridAttributionRequest(BaseModel):
    cells: List[GridCellInput]

class GridAttributionResponse(BaseModel):
    attributions: List[SourceAttributionOutput]
