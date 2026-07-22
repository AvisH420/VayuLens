# decision/

Turns *insight* into *action*. Fuses attribution and forecast with the grounded knowledge base to
recommend concrete, regulation-cited interventions, rank them for enforcement, and communicate them to
the public.

## Components

- **`recommendation_engine/`** — produces prioritised, regulation-backed actions for a cell, ranked by an
  enforcement `priority_score`.
- **`advisory_engine/`** — plain-language, audience-specific public advisories (e.g. schools, outdoor
  workers, at-risk groups) generated from the live grid.
- **`schemas/`, `utils/`** — request/response models and AQI helpers.

**Input:** `Attribution`, `Forecast`, and grounded answers from [`rag/`](../rag/).
**Output:** [`Recommendation`](../contracts/recommendation.py) records.
