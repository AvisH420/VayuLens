"""Pydantic request/response schemas — the versioned API contract.

These are the types Role 1 (geospatial), Role 2 (attribution/forecast), and
Role 4 (dashboard) integrate against. Keep them stable and additive.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from rag.types import Citation


# --------------------------------------------------------------------------
# Shared domain inputs (produced by Role 1 & Role 2, consumed here)
# --------------------------------------------------------------------------
class SourceContribution(BaseModel):
    """One source's share of measured pollution (from Role 2 attribution)."""

    source: str = Field(..., description="e.g. construction, industry, traffic, stubble")
    contribution_pct: float = Field(..., ge=0, le=100)
    subtype: str | None = None


class ForecastPoint(BaseModel):
    horizon_hours: int = Field(..., ge=0)
    aqi: float
    pm25: float | None = None
    pm10: float | None = None


class WeatherContext(BaseModel):
    temperature_c: float | None = None
    wind_speed_ms: float | None = None
    wind_direction_deg: float | None = None
    humidity_pct: float | None = None
    boundary_layer_m: float | None = None
    inversion: bool | None = None


class LocationContext(BaseModel):
    name: str
    lat: float | None = None
    lon: float | None = None
    population: int | None = Field(None, ge=0)
    hospitals_nearby: int | None = Field(None, ge=0)
    schools_nearby: int | None = Field(None, ge=0)


# --------------------------------------------------------------------------
# /ask, /retrieve
# --------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    top_k: int | None = Field(None, ge=1, le=50)
    metadata_filter: dict | None = None
    task: str = Field("qa", description="qa | legal | summarize")


class AskResponse(BaseModel):
    answer: str
    confidence: float
    grounded: bool
    refused: bool
    citations: list[Citation]
    retrieved_sources: list[str]
    reasoning: str | None = None


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int | None = Field(None, ge=1, le=50)
    metadata_filter: dict | None = None
    rerank: bool = True


class RetrievedChunk(BaseModel):
    text: str
    source: str
    doc_type: str | None = None
    page: int | None = None
    section: str | None = None
    score: float
    method: str


class RetrieveResponse(BaseModel):
    query: str
    results: list[RetrievedChunk]


# --------------------------------------------------------------------------
# /recommend
# --------------------------------------------------------------------------
class Priority(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class RecommendRequest(BaseModel):
    location: LocationContext
    current_aqi: float = Field(..., ge=0)
    source_attribution: list[SourceContribution] = Field(default_factory=list)
    forecast: list[ForecastPoint] = Field(default_factory=list)
    weather: WeatherContext | None = None
    language: str = "en"


class ActionRecommendation(BaseModel):
    action: str
    priority: Priority
    target_source: str | None = None
    legal_basis: list[Citation] = Field(default_factory=list)
    justification: str
    expected_impact: str
    grap_stage: str | None = None
    confidence: float


class RecommendResponse(BaseModel):
    location: str
    aqi_band: str
    grap_stage: str | None
    summary: str
    recommendations: list[ActionRecommendation]
    grounded: bool
    generated_reasoning: str | None = None


# --------------------------------------------------------------------------
# Enforcement prioritization
# --------------------------------------------------------------------------
class EnforcementTarget(BaseModel):
    target_id: str
    name: str
    category: str = Field(..., description="industrial | construction | traffic | burning")
    pollution_contribution_pct: float = Field(0, ge=0, le=100)
    population_exposed: int = Field(0, ge=0)
    hospitals_nearby: int = Field(0, ge=0)
    schools_nearby: int = Field(0, ge=0)
    forecast_trend: float = Field(
        0, description="expected AQI change next 24h; positive = worsening"
    )
    lat: float | None = None
    lon: float | None = None


class PrioritizeRequest(BaseModel):
    targets: list[EnforcementTarget]
    current_aqi: float = Field(0, ge=0)


class RankedTarget(BaseModel):
    target_id: str
    name: str
    category: str
    priority: Priority
    score: float
    rank: int
    rationale: str
    component_scores: dict[str, float]
    legal_urgency: str | None = None


class PrioritizeResponse(BaseModel):
    aqi_band: str
    grap_stage: str | None
    ranked_targets: list[RankedTarget]


# --------------------------------------------------------------------------
# /advisory
# --------------------------------------------------------------------------
class AdvisoryRequest(BaseModel):
    location: str
    current_aqi: float = Field(..., ge=0)
    audiences: list[str] = Field(default_factory=lambda: ["citizen"])
    languages: list[str] = Field(default_factory=lambda: ["en"])
    forecast: list[ForecastPoint] = Field(default_factory=list)


class Advisory(BaseModel):
    audience: str
    language: str
    aqi_band: str
    headline: str
    message: str
    actions: list[str]
    citations: list[Citation] = Field(default_factory=list)
    grounded: bool


class AdvisoryResponse(BaseModel):
    location: str
    aqi: float
    aqi_band: str
    advisories: list[Advisory]


# --------------------------------------------------------------------------
# /evaluate
# --------------------------------------------------------------------------
class EvalSample(BaseModel):
    question: str
    relevant_doc_ids: list[str] = Field(default_factory=list)
    ground_truth: str | None = None


class EvaluateRequest(BaseModel):
    samples: list[EvalSample]
    k_values: list[int] | None = None


class EvaluateResponse(BaseModel):
    num_samples: int
    retrieval_metrics: dict[str, float]
    generation_metrics: dict[str, float]
    per_sample: list[dict]


# --------------------------------------------------------------------------
# /health, ingest
# --------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    version: str
    indexed_chunks: int
    embedding_provider: str
    vector_backend: str
    llm_provider: str
    reranker: str


class IngestRequest(BaseModel):
    directory: str | None = None


class IngestResponse(BaseModel):
    indexed_chunks: int
    detail: dict[str, int]
