# data/

Turns heterogeneous raw feeds into one clean, gridded, calibrated truth layer that every downstream
module trusts. Produces [`GridCell`](../contracts/grid_cell.py) and [`Measurement`](../contracts/measurement.py)
records on the ~1&nbsp;km grid.

## Pipeline

`grid_builder` → `alignment` → `calibration` → `fusion` → `gap_filling`

- **`grid_builder.py`** — tessellates the city into ~1&nbsp;km cells and joins OpenStreetMap land-use
  context (road density, industrial proximity, construction density).
- **`alignment.py`** — snaps every raw reading to its nearest grid cell.
- **`calibration.py`** — harmonises units and applies an AOD→PM2.5 regression to satellite aerosol data.
- **`fusion.py`** — combines sources by **inverse-variance weighting** (ground stations trusted over
  satellite) into a fused `Measurement` per cell, with a quality score and uncertainty.
- **`gap_filling.py`** — interpolates missing fields with inverse-distance weighting, including proper
  **circular averaging** for wind direction.

## Entry point

`pipeline.py` — `build_grid`, `fetch_source`, `calibrate`, `fuse`, and `run_pipeline` (the full chain
for a city and time window; pass `sources=WORKING_SOURCES` for a fast live run).
