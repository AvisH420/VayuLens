# attribution/

Answers *"where is this pollution coming from?"* for each grid cell. Apportions a cell's PM2.5 across
six source classes — traffic, construction, industry, biomass burning, dust and other — with a
confidence score.

## How it works

Chemical and land-use proxies are normalised onto a common scale before they are combined, so sources
measured in very different units are comparable:

- **NO₂ × road density** → traffic
- **SO₂ × industrial proximity** → industry
- **UV-aerosol index** → biomass burning
- **AOD × wind** → dust
- **construction density × AOD** → construction

The normalised scores are apportioned to shares that sum to 1.0, and confidence is derived from the
strength of the underlying signals.

## Layout

- `models.py` — typed input (`GridCellInput`) and output schemas.
- `engine.py` — `attribute_sources` (batch apportionment over a grid).

**Input:** `Measurement` + `GridCell` context. **Output:** per-cell source shares + confidence
([`Attribution`](../contracts/attribution.py) via the gateway adapter).
