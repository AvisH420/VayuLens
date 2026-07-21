# data/ — Source connectors, grid builder, calibration & fusion

**Owner:** Role 1 (Data Engineer)
**Builds against:** [`contracts/grid_cell.py`](../contracts/grid_cell.py), [`contracts/measurement.py`](../contracts/measurement.py)

## Purpose

Turn heterogeneous raw inputs into a clean, gridded, calibrated truth layer that
every downstream module trusts.

- **Source connectors** — ground monitoring stations, satellite products,
  meteorology reanalysis, road/land-use GIS.
- **~1km grid builder** — defines the canonical `GridCell` mesh over the city.
- **Calibration / fusion** — bias-corrects each source and fuses them into
  `Measurement` records with `quality_score` and `uncertainty`.

## Inputs

- Raw source records (pulled by [`ingestion/`](../ingestion/README.md)).
- Bounding box / area-of-interest definition.
- GIS layers for ward, land use, road density, industrial sites.

## Outputs

- `list[GridCell]` — the canonical analysis grid.
- `list[Measurement]` — fused, calibrated observations per cell per timestamp.

## Key module

- `pipeline.py` — `build_grid`, `fetch_source`, `calibrate`, `fuse`.
