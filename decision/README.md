# decision/ — Agentic recommendations, enforcement priority, multi-language advisories

**Owner:** Role 3 (Knowledge & Agents)
**Builds against:** [`contracts/attribution.py`](../contracts/attribution.py), [`contracts/forecast.py`](../contracts/forecast.py), [`contracts/recommendation.py`](../contracts/recommendation.py); uses [`rag/`](../rag/README.md)

## Purpose

Turn *insight* into *action*. An agentic layer fuses attribution + forecast with
the grounded knowledge base to recommend concrete, regulation-cited
interventions, rank them for enforcement, and communicate them to the public in
multiple languages.

- **Agentic recommendations** — what to do, justified and cited.
- **Enforcement priority** — rank actions by `priority_score`.
- **Multi-language advisories** — localize public-facing messaging.

## Inputs

- `Attribution` (from [`attribution/`](../attribution/README.md)).
- `Forecast` (from [`forecasting/`](../forecasting/README.md)).
- Grounded answers/citations from [`rag/`](../rag/README.md).

## Outputs

- `Recommendation` records consumed by [`api/`](../api/README.md) and the frontend.

## Key module

- `agent.py` — `recommend`, `prioritize`, `localize`.
