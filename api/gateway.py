"""Role 4 — FastAPI gateway stubs.

Single entry point the frontend talks to. Aggregates data, attribution,
forecasting, rag, and decision modules behind one HTTP API.

The route handlers are stubs that raise NotImplementedError. They are wired to
a FastAPI app so the shape of the API is visible, but no logic is implemented.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from contracts.attribution import Attribution
from contracts.forecast import Forecast
from contracts.grid_cell import GridCell
from contracts.measurement import Measurement
from contracts.recommendation import Recommendation

app = FastAPI(title="VayuLens API", version="0.0.1")


@app.get("/grid", response_model=list[GridCell])
def get_grid() -> list[GridCell]:
    """Return the canonical ~1km analysis grid."""
    raise NotImplementedError


@app.get("/measurements/{cell_id}", response_model=list[Measurement])
def get_measurements(cell_id: str) -> list[Measurement]:
    """Return recent fused measurements for a cell."""
    raise NotImplementedError


@app.get("/attribution/{cell_id}", response_model=Attribution)
def get_attribution(cell_id: str) -> Attribution:
    """Return the current source attribution for a cell."""
    raise NotImplementedError


@app.get("/forecast/{cell_id}", response_model=Forecast)
def get_forecast(cell_id: str) -> Forecast:
    """Return the 24-72h AQI forecast for a cell."""
    raise NotImplementedError


@app.post("/simulate", response_model=list[Forecast])
def post_simulate(scenario: dict[str, Any]) -> list[Forecast]:
    """Run a what-if scenario and return the counterfactual forecasts."""
    raise NotImplementedError


@app.get("/recommendations/{cell_id}", response_model=list[Recommendation])
def get_recommendations(cell_id: str, language: str = "en") -> list[Recommendation]:
    """Return prioritized, localized recommendations for a cell."""
    raise NotImplementedError


@app.post("/chat", response_model=dict)
def post_chat(query: str) -> dict[str, Any]:
    """Answer a grounded natural-language question via the RAG pipeline."""
    raise NotImplementedError
