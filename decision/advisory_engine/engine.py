"""Multilingual advisory engine (Step 11).

Generates audience- and language-specific advisories. Strategy:
  1. Look up a real translated template from the catalog (offline, deterministic).
  2. Attach grounding citations from the CPCB health-advisory corpus via RAG.
  3. Fall back gracefully: audience -> citizen (same lang) -> English.

Extensible: new languages/audiences are added purely as catalog data; optional
LLM translation can be layered on for languages not yet in the catalog.
"""
from __future__ import annotations

from rag.logging_utils import get_logger
from rag.pipeline import RAGPipeline
from rag.types import Citation

from decision.advisory_engine.catalog import BAND_TIER, CATALOG
from decision.schemas.models import (
    Advisory,
    AdvisoryRequest,
    AdvisoryResponse,
)
from decision.utils.aqi import aqi_band

log = get_logger(__name__)

_AUDIENCE_QUERY = {
    "citizen": "health advisory citizens air quality masks outdoor activity",
    "hospital": "hospital respiratory admissions oxygen nebuliser air quality",
    "school": "schools outdoor sports closure hybrid classes air quality",
    "outdoor_worker": "outdoor workers N95 masks exposure air quality advisory",
    "senior_citizen": "elderly senior citizens avoid outdoor severe air quality",
}


class AdvisoryEngine:
    def __init__(self, pipeline: RAGPipeline):
        self.pipeline = pipeline

    def _lookup(self, lang: str, audience: str, tier: str) -> tuple[dict, bool]:
        """Return (template, exact_match). Falls back audience->citizen->English."""
        for lg in (lang, "en"):
            block = CATALOG.get(lg)
            if not block:
                continue
            for aud in (audience, "citizen"):
                if aud in block and tier in block[aud]:
                    return block[aud][tier], (lg == lang and aud == audience)
        # ultimate fallback
        return CATALOG["en"]["citizen"][tier], False

    def _citations(self, audience: str, tier: str) -> list[Citation]:
        query = _AUDIENCE_QUERY.get(audience, _AUDIENCE_QUERY["citizen"])
        chunks = self.pipeline.retrieve(query, top_k=3)
        cites = []
        for c in chunks[:2]:
            cites.append(
                Citation(
                    doc_id=c.chunk.doc_id, source=c.chunk.source, title=c.chunk.title,
                    doc_type=c.chunk.doc_type, page=c.chunk.page,
                    section=c.chunk.section,
                    snippet=c.chunk.text.strip().replace("\n", " ")[:280],
                    score=round(c.score, 4),
                )
            )
        return cites

    def _one(self, req: AdvisoryRequest, audience: str, lang: str,
             band: str, tier: str) -> Advisory:
        template, exact = self._lookup(lang, audience, tier)
        aqi_str = f"{req.current_aqi:.0f}"
        headline = template["headline"].format(location=req.location, aqi=aqi_str)
        message = template["message"].format(location=req.location, aqi=aqi_str)
        actions = [a.format(location=req.location, aqi=aqi_str)
                   for a in template["actions"]]
        citations = self._citations(audience, tier)
        return Advisory(
            audience=audience, language=lang, aqi_band=band, headline=headline,
            message=message, actions=actions, citations=citations,
            grounded=bool(citations),
        )

    def generate(self, req: AdvisoryRequest) -> AdvisoryResponse:
        band = aqi_band(req.current_aqi)
        tier = BAND_TIER.get(band, "caution")
        advisories: list[Advisory] = []
        for audience in req.audiences:
            for lang in req.languages:
                advisories.append(self._one(req, audience, lang, band, tier))
        return AdvisoryResponse(
            location=req.location, aqi=req.current_aqi, aqi_band=band,
            advisories=advisories,
        )
