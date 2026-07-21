"""Tests for the decision layer: recommendations, prioritization, advisories."""
from __future__ import annotations

from decision.recommendation_engine import EnforcementPrioritizer, RecommendationEngine
from decision.advisory_engine import AdvisoryEngine
from decision.schemas.models import (
    AdvisoryRequest,
    EnforcementTarget,
    LocationContext,
    PrioritizeRequest,
    Priority,
    RecommendRequest,
    SourceContribution,
)
from decision.utils.aqi import aqi_band, grap_stage


def test_aqi_banding_and_grap_stage():
    assert aqi_band(50) == "Good"
    assert aqi_band(432) == "Severe"
    assert grap_stage(432) == "Stage III"
    assert grap_stage(120) is None  # below GRAP trigger


def test_recommendation_prioritizes_dominant_source(pipeline):
    engine = RecommendationEngine(pipeline)
    req = RecommendRequest(
        location=LocationContext(name="Anand Vihar"),
        current_aqi=432,
        source_attribution=[
            SourceContribution(source="construction", contribution_pct=42),
            SourceContribution(source="traffic", contribution_pct=28),
            SourceContribution(source="industry", contribution_pct=18),
        ],
    )
    resp = engine.recommend(req)
    assert resp.grap_stage == "Stage III"
    assert resp.recommendations
    top = resp.recommendations[0]
    assert top.target_source == "construction"
    assert top.priority == Priority.critical
    assert top.legal_basis, "recommendation must be legally grounded"


def test_prioritizer_ranks_and_explains(pipeline):
    prioritizer = EnforcementPrioritizer(pipeline.settings.decision)
    req = PrioritizeRequest(
        current_aqi=432,
        targets=[
            EnforcementTarget(target_id="A", name="Cluster A", category="industrial",
                              pollution_contribution_pct=35, population_exposed=180000,
                              hospitals_nearby=2, schools_nearby=8, forecast_trend=20),
            EnforcementTarget(target_id="B", name="Site B", category="construction",
                              pollution_contribution_pct=10, population_exposed=1000,
                              hospitals_nearby=0, schools_nearby=0, forecast_trend=0),
        ],
    )
    resp = prioritizer.prioritize(req)
    assert resp.ranked_targets[0].rank == 1
    assert resp.ranked_targets[0].score >= resp.ranked_targets[1].score
    assert resp.ranked_targets[0].component_scores
    assert resp.ranked_targets[0].rationale


def test_advisory_multilingual_and_grounded(pipeline):
    engine = AdvisoryEngine(pipeline)
    req = AdvisoryRequest(
        location="Anand Vihar", current_aqi=432,
        audiences=["citizen", "school"], languages=["en", "hi", "ta"],
    )
    resp = engine.generate(req)
    assert resp.aqi_band == "Severe"
    assert len(resp.advisories) == 6  # 2 audiences x 3 languages
    langs = {a.language for a in resp.advisories}
    assert {"en", "hi", "ta"}.issubset(langs)
    # Hindi citizen advisory should be in Devanagari
    hi = next(a for a in resp.advisories if a.language == "hi" and a.audience == "citizen")
    assert any("ऀ" <= ch <= "ॿ" for ch in hi.headline)


def test_advisory_falls_back_for_untranslated_audience(pipeline):
    engine = AdvisoryEngine(pipeline)
    # 'school' audience is not separately translated to Tamil -> falls back
    req = AdvisoryRequest(
        location="X", current_aqi=432, audiences=["school"], languages=["ta"]
    )
    resp = engine.generate(req)
    assert resp.advisories
    assert resp.advisories[0].headline  # non-empty fallback
