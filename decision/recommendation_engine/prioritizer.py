"""Enforcement prioritization (Step 10).

Ranks enforcement targets (industrial clusters, construction sites, traffic
corridors, burning hotspots) by a transparent weighted score over:
pollution contribution, population exposed, hospitals nearby, schools nearby,
forecast trend, and legal urgency. Weights are config-driven; every ranked
target carries its component scores for full explainability on the dashboard.
"""
from __future__ import annotations

from rag.config import DecisionCfg
from rag.logging_utils import get_logger

from decision.schemas.models import (
    EnforcementTarget,
    PrioritizeRequest,
    PrioritizeResponse,
    Priority,
    RankedTarget,
)
from decision.utils.aqi import aqi_band, grap_stage, grap_stage_number, legal_urgency

log = get_logger(__name__)


def _norm(value: float, cap: float) -> float:
    if cap <= 0:
        return 0.0
    return max(0.0, min(1.0, value / cap))


class EnforcementPrioritizer:
    def __init__(self, cfg: DecisionCfg):
        self.weights = cfg.weights

    def _component_scores(
        self, t: EnforcementTarget, caps: dict[str, float], stage_num: int
    ) -> dict[str, float]:
        return {
            "pollution_contribution": _norm(t.pollution_contribution_pct, 100.0),
            "population": _norm(t.population_exposed, caps["population"]),
            "hospitals": _norm(t.hospitals_nearby, caps["hospitals"]),
            "schools": _norm(t.schools_nearby, caps["schools"]),
            # positive forecast trend (worsening) increases urgency
            "forecast_trend": _norm(max(0.0, t.forecast_trend), caps["forecast"]),
            "legal_urgency": _norm(stage_num, 4.0),
        }

    def _weighted(self, comp: dict[str, float]) -> float:
        w = self.weights
        score = (
            w["pollution_contribution"] * comp["pollution_contribution"]
            + w["population"] * comp["population"]
            + w["hospitals"] * comp["hospitals"]
            + w["schools"] * comp["schools"]
            + w["forecast_trend"] * comp["forecast_trend"]
            + w["legal_urgency"] * comp["legal_urgency"]
        )
        total_w = sum(w.values()) or 1.0
        return round(score / total_w, 4)

    @staticmethod
    def _priority(score: float) -> Priority:
        if score >= 0.66:
            return Priority.critical
        if score >= 0.45:
            return Priority.high
        if score >= 0.25:
            return Priority.medium
        return Priority.low

    @staticmethod
    def _rationale(t: EnforcementTarget, comp: dict[str, float]) -> str:
        drivers = sorted(comp.items(), key=lambda x: x[1], reverse=True)[:3]
        parts = []
        label = {
            "pollution_contribution": f"{t.pollution_contribution_pct:.0f}% pollution share",
            "population": f"{t.population_exposed:,} people exposed",
            "hospitals": f"{t.hospitals_nearby} hospital(s) nearby",
            "schools": f"{t.schools_nearby} school(s) nearby",
            "forecast_trend": f"forecast worsening (+{t.forecast_trend:.0f} AQI)",
            "legal_urgency": "high legal enforceability",
        }
        for key, val in drivers:
            if val > 0:
                parts.append(label[key])
        return "Prioritized due to " + ", ".join(parts) + "." if parts else \
            "Low aggregate risk."

    def prioritize(self, req: PrioritizeRequest) -> PrioritizeResponse:
        targets = req.targets
        stage_num = grap_stage_number(req.current_aqi)
        caps = {
            "population": max((t.population_exposed for t in targets), default=1) or 1,
            "hospitals": max((t.hospitals_nearby for t in targets), default=1) or 1,
            "schools": max((t.schools_nearby for t in targets), default=1) or 1,
            "forecast": max(
                (max(0.0, t.forecast_trend) for t in targets), default=1.0
            ) or 1.0,
        }
        ranked: list[RankedTarget] = []
        for t in targets:
            comp = self._component_scores(t, caps, stage_num)
            score = self._weighted(comp)
            ranked.append(
                RankedTarget(
                    target_id=t.target_id, name=t.name, category=t.category,
                    priority=self._priority(score), score=score, rank=0,
                    rationale=self._rationale(t, comp),
                    component_scores=comp,
                    legal_urgency=legal_urgency(req.current_aqi),
                )
            )
        ranked.sort(key=lambda r: r.score, reverse=True)
        for i, r in enumerate(ranked, start=1):
            r.rank = i
        return PrioritizeResponse(
            aqi_band=aqi_band(req.current_aqi),
            grap_stage=grap_stage(req.current_aqi),
            ranked_targets=ranked,
        )
