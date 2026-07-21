"""Role 3 — decision/agent stubs.

Combines attribution + forecast + grounded knowledge (RAG) into actionable,
regulation-cited recommendations, ranks them by enforcement priority, and
renders multi-language advisories for the public.

All functions are stubs that raise NotImplementedError.
"""

from __future__ import annotations

from contracts.attribution import Attribution
from contracts.forecast import Forecast
from contracts.recommendation import Recommendation


def recommend(
    attribution: Attribution,
    forecast: Forecast,
) -> list[Recommendation]:
    """Produce grounded, regulation-cited recommendations for a cell.

    Uses an agentic loop over the RAG knowledge base to justify each action and
    attach a `regulation_citation`.

    Args:
        attribution: Source apportionment for the cell.
        forecast: AQI trajectory for the cell.

    Returns:
        Candidate `Recommendation`s for the cell.
    """
    raise NotImplementedError


def prioritize(recommendations: list[Recommendation]) -> list[Recommendation]:
    """Rank recommendations by enforcement priority.

    Args:
        recommendations: Candidate recommendations across cells.

    Returns:
        The same recommendations sorted by `priority_score` (desc).
    """
    raise NotImplementedError


def localize(recommendation: Recommendation, language: str) -> Recommendation:
    """Render a recommendation as a public advisory in the given language.

    Args:
        recommendation: The recommendation to translate/adapt.
        language: Target language code (e.g. 'en', 'hi', 'mr').

    Returns:
        A `Recommendation` whose `action`/`justification` are localized.
    """
    raise NotImplementedError
