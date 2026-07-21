"""Schema: forecast — AQI trajectory for a cell over a horizon."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ForecastPoint(BaseModel):
    """A single point on the forecast horizon."""

    t: datetime = Field(..., description="UTC timestamp of the forecast step.")
    aqi: float = Field(..., description="Predicted Air Quality Index at time t.")


class Forecast(BaseModel):
    """24-72h AQI forecast for one grid cell."""

    cell_id: str = Field(..., description="Grid cell this forecast belongs to.")
    horizon: list[ForecastPoint] = Field(..., description="Ordered list of (t, aqi) points.")
