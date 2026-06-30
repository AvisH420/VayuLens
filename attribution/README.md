# attribution/ — Source-attribution engine

**Owner:** Role 2 (Modeling)
**Builds against:** [`contracts/measurement.py`](../contracts/measurement.py), [`contracts/grid_cell.py`](../contracts/grid_cell.py), [`contracts/attribution.py`](../contracts/attribution.py)

## Purpose

Answer *"where is this pollution coming from?"* for each cell. Apportions
measured concentrations to source classes — traffic, construction, industry,
burning, dust — with a confidence score.

## Inputs

- `Measurement` records from [`data/`](../data/README.md).
- `GridCell` context (land use, road density, industrial flag).

## Outputs

- `Attribution` records (per-source shares + confidence) consumed by
  [`decision/`](../decision/README.md), [`api/`](../api/README.md), and the frontend.

## Key module

- `engine.py` — `attribute_cell`, `attribute_batch`.
