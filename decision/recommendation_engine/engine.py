"""Agentic decision engine (Step 9).

Converts forecast + AQI + source attribution + location + weather into specific,
legally-grounded enforcement actions. Each action is justified by regulations
retrieved from the RAG corpus (real citations, not hardcoded law text).

The engine is knowledge-driven: a source-to-intervention playbook defines the
candidate action for each pollution source; the RAG layer supplies the legal
basis and the LLM composes the grounded justification. Priority is derived from
the source's contribution share and the AQI-linked GRAP stage.
"""
from __future__ import annotations

from rag.logging_utils import get_logger
from rag.pipeline import RAGPipeline
from rag.types import Citation

from decision.schemas.models import (
    ActionRecommendation,
    Priority,
    RecommendRequest,
    RecommendResponse,
    SourceContribution,
)
from decision.utils.aqi import aqi_band, grap_stage, grap_stage_number, legal_urgency

log = get_logger(__name__)


# Source -> candidate intervention playbook. The retrieval query pulls the
# governing regulation; the action/impact are the operational response.
PLAYBOOK: dict[str, dict[str, str]] = {
    "construction": {
        "action": "Halt non-essential construction and demolition activity; enforce "
                  "dust-control SOP (anti-smog guns, wind barriers, water sprinkling).",
        "query": "construction and demolition ban dust control GRAP stage",
        "impact": "Rapid reduction in coarse particulate (PM10) from dust "
                  "re-suspension within 24-72 hours around affected clusters.",
    },
    "industry": {
        "action": "Direct closure or fuel-switching of industries on unapproved "
                  "fuels; inspect emission compliance under the Air Act.",
        "query": "closure of polluting industries unapproved fuel Air Act directions",
        "impact": "Cuts SO2 and industrial particulate at source; effect sustained "
                  "while directions remain in force.",
    },
    "traffic": {
        "action": "Intensify PUC enforcement, augment public transport, and consider "
                  "vehicle-use restrictions (BS-III petrol / BS-IV diesel).",
        "query": "vehicular emissions PUC restriction public transport GRAP traffic",
        "impact": "Moderate PM2.5 reduction in traffic corridors; benefit "
                  "concentrated during the restriction window.",
    },
    "stubble": {
        "action": "Coordinate regional stubble-burning controls; deploy bio-decomposer "
                  "and in-situ residue management; alert adjoining states.",
        "query": "stubble burning crop residue management regional coordination",
        "impact": "Reduces transboundary PM2.5 loading during burning weeks; "
                  "requires cross-state coordination for full effect.",
    },
    "burning": {
        "action": "Enforce ban on open burning of waste and biomass; deploy municipal "
                  "patrols to hotspots.",
        "query": "open burning solid waste biomass ban enforcement",
        "impact": "Eliminates a localized combustion source; fast local improvement.",
    },
    "road_dust": {
        "action": "Mechanized road sweeping and water sprinkling on haulage roads and "
                  "exposed soil.",
        "query": "road dust mechanized sweeping water sprinkling control",
        "impact": "Lowers re-suspended road dust (PM10); benefit within hours.",
    },
}

_ALIASES = {
    "construction_dust": "construction",
    "c&d": "construction",
    "industrial": "industry",
    "factories": "industry",
    "vehicular": "traffic",
    "vehicles": "traffic",
    "transport": "traffic",
    "biomass": "burning",
    "waste_burning": "burning",
    "agriculture": "stubble",
    "crop_burning": "stubble",
    "dust": "road_dust",
}


def _canonical_source(name: str) -> str:
    key = name.strip().lower().replace(" ", "_")
    if key in PLAYBOOK:
        return key
    return _ALIASES.get(key, key)


class RecommendationEngine:
    def __init__(self, pipeline: RAGPipeline):
        self.pipeline = pipeline

    def _priority_for(self, contribution_pct: float, stage_num: int) -> Priority:
        """Blend the source's contribution share with regulatory urgency.

        Contribution dominates (it determines which lever moves the needle);
        the GRAP stage provides a bounded escalation so the same source ranks
        higher during a more severe episode.
        """
        share = contribution_pct / 100.0
        stage_lift = 0.08 * stage_num  # max +0.32 at Stage IV
        score = share + stage_lift
        # A dominant source during an enforceable stage is always critical.
        if contribution_pct >= 40 and stage_num >= 3:
            return Priority.critical
        if score >= 0.65:
            return Priority.critical
        if score >= 0.45:
            return Priority.high
        if score >= 0.25:
            return Priority.medium
        return Priority.low

    def _build_action(
        self, src: SourceContribution, aqi: float, stage: str | None,
        stage_num: int, language: str,
    ) -> ActionRecommendation | None:
        canon = _canonical_source(src.source)
        play = PLAYBOOK.get(canon)
        if play is None:
            # unknown source: still retrieve generic guidance
            play = {
                "action": f"Investigate and mitigate emissions from {src.source}.",
                "query": f"{src.source} air pollution control measures regulation",
                "impact": "Impact depends on source-specific controls.",
            }
        chunks = self.pipeline.retrieve(play["query"], top_k=4)
        legal_basis: list[Citation] = [
            Citation(
                doc_id=c.chunk.doc_id, source=c.chunk.source, title=c.chunk.title,
                doc_type=c.chunk.doc_type, page=c.chunk.page, section=c.chunk.section,
                snippet=c.chunk.text.strip().replace("\n", " ")[:280],
                score=round(c.score, 4),
            )
            for c in chunks[:2]
        ]
        # Grounded justification via the RAG legal-reasoning task.
        situation = (
            f"Source '{src.source}' contributes {src.contribution_pct:.0f}% of "
            f"pollution at AQI {aqi:.0f} ({aqi_band(aqi)}, GRAP {stage}). "
            f"Proposed action: {play['action']} Explain the legal basis and why "
            f"this action is warranted."
        )
        grounded = self.pipeline.recommend(situation, top_k=5)
        justification = (
            grounded.answer if grounded.grounded
            else f"{src.source} is a major contributor ({src.contribution_pct:.0f}%). "
                 f"{play['action']}"
        )
        confidence = round(
            0.5 * (src.contribution_pct / 100.0)
            + 0.3 * (grounded.confidence if grounded.grounded else 0.2)
            + 0.2 * (stage_num / 4.0),
            4,
        )
        return ActionRecommendation(
            action=play["action"],
            priority=self._priority_for(src.contribution_pct, stage_num),
            target_source=src.source,
            legal_basis=legal_basis or grounded.citations[:2],
            justification=justification,
            expected_impact=play["impact"],
            grap_stage=stage,
            confidence=confidence,
        )

    def recommend(self, req: RecommendRequest) -> RecommendResponse:
        aqi = req.current_aqi
        stage = grap_stage(aqi)
        stage_num = grap_stage_number(aqi)
        band = aqi_band(aqi)

        # Rank sources by contribution, keep meaningful ones.
        sources = sorted(
            req.source_attribution, key=lambda s: s.contribution_pct, reverse=True
        )
        recs: list[ActionRecommendation] = []
        for src in sources:
            if src.contribution_pct < 5:  # ignore negligible sources
                continue
            action = self._build_action(src, aqi, stage, stage_num, req.language)
            if action:
                recs.append(action)

        # If no attribution provided, fall back to AQI-band standard response.
        if not recs and stage:
            for canon in ("construction", "industry", "traffic"):
                dummy = SourceContribution(source=canon, contribution_pct=25)
                action = self._build_action(dummy, aqi, stage, stage_num, req.language)
                if action:
                    action.confidence = round(action.confidence * 0.7, 4)
                    recs.append(action)

        recs.sort(key=lambda r: (_PRIORITY_ORDER[r.priority], -r.confidence))

        forecast_note = ""
        if req.forecast:
            peak = max(req.forecast, key=lambda f: f.aqi)
            trend = "worsening" if peak.aqi > aqi else "improving/stable"
            forecast_note = (
                f" Forecast peak AQI {peak.aqi:.0f} in {peak.horizon_hours}h "
                f"({trend})."
            )
        summary = (
            f"{req.location.name}: AQI {aqi:.0f} ({band}), "
            f"GRAP {stage or 'not triggered'}. "
            f"{len(recs)} enforcement action(s) recommended.{forecast_note}"
        )
        grounded_any = any(r.legal_basis for r in recs)
        return RecommendResponse(
            location=req.location.name,
            aqi_band=band,
            grap_stage=stage,
            summary=summary,
            recommendations=recs,
            grounded=grounded_any,
            generated_reasoning=(
                f"Legal urgency level: {legal_urgency(aqi)}. Actions ranked by "
                f"source contribution and GRAP enforceability."
            ),
        )


_PRIORITY_ORDER = {
    Priority.critical: 0,
    Priority.high: 1,
    Priority.medium: 2,
    Priority.low: 3,
}
