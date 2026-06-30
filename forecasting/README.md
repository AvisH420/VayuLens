# forecasting/ — Dispersion model, 24-72h forecast & scenario simulation

**Owner:** Role 2 (Modeling)
**Builds against:** [`contracts/measurement.py`](../contracts/measurement.py), [`contracts/grid_cell.py`](../contracts/grid_cell.py), [`contracts/forecast.py`](../contracts/forecast.py)

## Purpose

Answer *"where is this pollution going?"*. A dispersion model produces 24-72h
AQI forecasts per cell, and `simulate(scenario)` powers the frontend what-if
panel with counterfactual runs.

## Inputs

- Recent `Measurement` history (from [`data/`](../data/README.md)).
- `GridCell` mesh.
- A `scenario` dict for counterfactual runs.

## Outputs

- `Forecast` records (per-cell `horizon[{t, aqi}]`) consumed by
  [`decision/`](../decision/README.md), [`api/`](../api/README.md), and the frontend.

## Key module

- `model.py` — `forecast_cell`, `forecast_grid`, `simulate`.
