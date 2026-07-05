"""Role 4 — FastAPI gateway.

Single entry point the frontend talks to. Aggregates data, attribution,
forecasting, rag, and decision modules behind one HTTP API.

Every route is live, currently served by ``demo_engine`` — a deterministic
Python port of the frontend's mock engine, returning contracts/ shapes.
As the real modules land, each handler swaps its engine call for the real
one and nothing changes shape:

    data ingestion  -> get_grid, get_measurements
    attribution     -> get_attribution
    forecasting     -> get_forecast, post_simulate
    decision        -> get_recommendations, get_advisory
    rag             -> post_chat

Run:  uvicorn api.gateway:app --reload  (from the repo root)
Docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api import demo_engine as engine
from contracts.attribution import Attribution, SourceShares
from contracts.forecast import Forecast, ForecastPoint
from contracts.measurement import Measurement
from contracts.recommendation import Recommendation

app = FastAPI(
    title="VayuLens API",
    version="0.1.0",
    description="Air-quality intelligence gateway: grid, attribution, forecasts, what-if simulation, grounded chat.",
)

# Dev frontend (Vite) origins. The Vite proxy makes this mostly moot, but
# direct browser calls during development should work too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

IST = timezone(timedelta(hours=5, minutes=30))


def _demo_now() -> datetime:
    """The demo clock: today at the engine's fixed hour, IST."""
    now = datetime.now(IST)
    return now.replace(hour=11, minute=0, second=0, microsecond=0)


def _cell_or_404(cell_id: str) -> tuple[str, dict[str, Any]]:
    found = engine.find_cell(cell_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"unknown cell_id: {cell_id}")
    return found


# ---- request / response envelopes local to the gateway ----
# (contracts/ models are used verbatim where they fit; these wrap them)


class SimulateRequest(BaseModel):
    city: str = Field(..., description="City id, e.g. 'delhi'.")
    action: str = Field(..., description=f"One of: {', '.join(engine.ACTIONS)}.")
    ward: str = Field("all", description="Ward name, or 'all' for the whole city.")
    days: int = Field(3, ge=1, le=7, description="Duration of the intervention in days.")


class CellDelta(BaseModel):
    scenario: list[int] = Field(..., description="Counterfactual AQI per 6h step.")
    delta: list[int] = Field(..., description="scenario - baseline per step (negative = improvement).")


class SimulationSummary(BaseModel):
    zoneCells: int
    avgDelta48: int = Field(..., description="Mean AQI delta in the zone at +48 h.")
    peakDelta: int = Field(..., description="Largest single-cell improvement over the horizon.")
    onsetHours: int


class SimulationResult(BaseModel):
    action: dict[str, Any]
    ward: str
    days: int
    results: dict[str, CellDelta] = Field(..., description="Per-cell counterfactuals, keyed by cell_id.")
    summary: SimulationSummary


class ChatRequest(BaseModel):
    query: str


class Citation(BaseModel):
    doc: str
    ref: str


class ChatAnswer(BaseModel):
    text: str
    citations: list[Citation]
    confidence: float = Field(..., ge=0.0, le=1.0)
    retrieved: int = Field(..., description="Passages retrieved for grounding.")
    abstained: bool = False


# ---- routes ----


@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness + a quick sanity readout of the demo grid."""
    return {
        "status": "ok",
        "engine": "demo",
        "cities": {cid: len(engine.build_city(cid)["cells"]) for cid in engine.CITIES},
    }


@app.get("/grid")
def get_grid(city: str = Query("delhi", description="City id: delhi | panaji")) -> dict[str, Any]:
    """The full city payload: config, enriched ~1km cells, city means.

    Cells carry the GridCell fields plus the live layers (aqi, source
    shares, confidence, pollutant readings, 72h forecast) so one call
    paints the whole dashboard.
    """
    if city not in engine.CITIES:
        raise HTTPException(status_code=404, detail=f"unknown city: {city}")
    return engine.build_city(city)


@app.get("/measurements/{cell_id}", response_model=list[Measurement])
def get_measurements(cell_id: str) -> list[Measurement]:
    """Most recent fused measurement for a cell (demo: one synthetic frame)."""
    city_id, cell = _cell_or_404(cell_id)
    cfg = engine.CITIES[city_id]
    return [
        Measurement(
            cell_id=cell_id,
            timestamp=_demo_now(),
            pm25=cell["pm25"],
            pm10=cell["pm10"],
            no2=cell["no2"],
            aod=cell["aod"],
            aerosol_index=round(0.4 + cell["shares"]["burning"] * 4, 2),
            temp=31.5,
            wind_speed=cfg["wind"]["speed"],
            wind_dir=cfg["wind"]["dir"],
            quality_score=cell["quality_score"],
            uncertainty=cell["uncertainty"],
        )
    ]


@app.get("/attribution/{cell_id}", response_model=Attribution)
def get_attribution(cell_id: str) -> Attribution:
    """Current source apportionment for a cell."""
    _, cell = _cell_or_404(cell_id)
    return Attribution(
        cell_id=cell_id,
        timestamp=_demo_now(),
        sources=SourceShares(**cell["shares"]),
        confidence=cell["confidence"],
    )


@app.get("/forecast/{cell_id}", response_model=Forecast)
def get_forecast(cell_id: str) -> Forecast:
    """72h AQI forecast for a cell at 6h steps."""
    _, cell = _cell_or_404(cell_id)
    t0 = _demo_now()
    return Forecast(
        cell_id=cell_id,
        horizon=[
            ForecastPoint(t=t0 + timedelta(hours=i * engine.FC_STEP_HOURS), aqi=aqi)
            for i, aqi in enumerate(cell["forecast"])
        ],
    )


@app.post("/simulate", response_model=SimulationResult)
def post_simulate(req: SimulateRequest) -> SimulationResult:
    """Run a what-if intervention and return per-cell counterfactuals."""
    if req.city not in engine.CITIES:
        raise HTTPException(status_code=404, detail=f"unknown city: {req.city}")
    if req.action not in engine.ACTIONS:
        raise HTTPException(status_code=422, detail=f"unknown action: {req.action}")
    return SimulationResult(**engine.run_scenario(req.city, req.action, req.ward, req.days))


@app.get("/recommendations/{cell_id}", response_model=list[Recommendation])
def get_recommendations(cell_id: str) -> list[Recommendation]:
    """Prioritized, regulation-grounded actions for a cell."""
    _, cell = _cell_or_404(cell_id)
    return [Recommendation(**r) for r in engine.recommendations_for(cell)]


@app.post("/chat", response_model=ChatAnswer)
def post_chat(req: ChatRequest) -> ChatAnswer:
    """Grounded Q&A over the regulation corpus; abstains on weak retrieval."""
    return ChatAnswer(**engine.chat_answer(req.query))


@app.get("/advisories/{city}")
def get_advisory(city: str) -> dict[str, Any]:
    """Citizen advisories for a city, keyed by language code."""
    if city not in engine.ADVISORIES:
        raise HTTPException(status_code=404, detail=f"unknown city: {city}")
    return engine.ADVISORIES[city]
