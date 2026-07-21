"""Schema: attribution — source apportionment for a cell at a time."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SourceShares(BaseModel):
    """Fractional contribution of each source class. Shares should sum to ~1.0."""

    traffic: float = Field(..., ge=0.0, le=1.0, description="Share attributed to vehicular traffic.")
    construction: float = Field(..., ge=0.0, le=1.0, description="Share attributed to construction dust.")
    industry: float = Field(..., ge=0.0, le=1.0, description="Share attributed to industrial emissions.")
    burning: float = Field(..., ge=0.0, le=1.0, description="Share attributed to biomass/waste burning.")
    dust: float = Field(..., ge=0.0, le=1.0, description="Share attributed to natural/road dust.")


class Attribution(BaseModel):
    """Source-attribution result for one grid cell at one timestamp."""

    cell_id: str = Field(..., description="Grid cell this attribution belongs to.")
    timestamp: datetime = Field(..., description="UTC timestamp of the attributed window.")
    sources: SourceShares = Field(..., description="Per-source fractional contributions.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence in the apportionment [0,1].")
