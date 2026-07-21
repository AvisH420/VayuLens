"""Schema: recommendation — an actionable, regulation-grounded advisory."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Recommendation(BaseModel):
    """A grounded enforcement/mitigation recommendation for a grid cell."""

    cell_id: str = Field(..., description="Grid cell the recommendation targets.")
    action: str = Field(..., description="Concrete action to take, e.g. 'Halt construction at site X'.")
    justification: str = Field(..., description="Why this action, grounded in attribution + forecast.")
    regulation_citation: str = Field(..., description="Citation to the regulation/policy backing the action.")
    priority_score: float = Field(..., ge=0.0, le=1.0, description="Enforcement priority [0,1]; higher = act sooner.")
