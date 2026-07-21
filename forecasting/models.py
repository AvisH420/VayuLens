from pydantic import BaseModel, Field
from typing import List, Optional
from attribution.models import GridCellInput

class ForecastPoint(BaseModel):
    t: str = Field(..., description="UTC ISO 8601 timestamp for the forecast point")
    aqi: int = Field(..., description="Predicted CPCB Air Quality Index value (integer)")

class ForecastCell(BaseModel):
    cell_id: str
    lat: float
    lon: float
    horizon: List[ForecastPoint] = Field(..., description="List of forecasted points (time & AQI)")

class ForecastResponse(BaseModel):
    forecasts: List[ForecastCell]
    forecast_horizon_hours: int = Field(..., description="Length of forecast in hours (e.g. 24, 48, 72)")

class SimulationScenario(BaseModel):
    name: str = Field(..., description="Name/Description of the simulation scenario (e.g., 'Green Zone Ward 12')")
    
    # Intervention targets
    affected_cell_ids: List[str] = Field(..., description="List of cell IDs where the intervention will be active")
    
    # Reductions: 0.0 means no reduction (0%), 1.0 means complete shutdown (100% reduction)
    traffic_reduction: float = Field(0.0, ge=0.0, le=1.0, description="Fractional reduction of vehicular traffic emissions")
    industrial_reduction: float = Field(0.0, ge=0.0, le=1.0, description="Fractional reduction of industrial emissions")
    construction_halted: bool = Field(False, description="True if all construction activity in target cells is halted")
    biomass_burning_banned: bool = Field(False, description="True if crop/biomass burning in target cells is prohibited")

class SimulationCellResult(BaseModel):
    cell_id: str
    original_pm25: float = Field(..., description="Pre-intervention PM2.5 concentration")
    simulated_pm25: float = Field(..., description="Post-intervention PM2.5 concentration")
    delta_pm25: float = Field(..., description="Absolute change in PM2.5 (simulated - original)")
    delta_percent: float = Field(..., description="Percentage change in PM2.5 relative to original")

class SimulationResponse(BaseModel):
    scenario_name: str
    results: List[SimulationCellResult]
    average_reduction_percent: float = Field(..., description="Average pollution reduction across all simulated cells")
